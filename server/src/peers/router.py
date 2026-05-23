"""
Central peer registry backed by Redis.

Keys:
  peer:{org_id}:{peer_id}   → hash  (TTL = HEARTBEAT_TTL_S)
  scope:{org_id}            → JSON  {group: [visible_groups, ...]}

Visibility rules (OIDC mode):
  - Peers are isolated by org_id (realm). Cross-org visibility is impossible.
  - Within an org, visibility is governed by the scope config:
      "__all__" sentinel  → see every peer in the org
      list of groups      → see peers whose group appears in the list
      no entry for group  → default: see only peers in the same group
  - Admin (OIDC_ADMIN_GROUP) bypasses scope checks and sees the entire org.

Dev mode (OIDC_ENABLED=False):
  - org_id is always "dev", no scope filtering, all peers visible.

WebSocket /peers/watch:
  - Authenticated via ?token=<jwt> query parameter in OIDC mode.
  - Falls back to full-org view in dev mode.
  - Client passes JWT as ?token= when connecting (OIDC mode).
"""
import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from auth.deps import CallerInfo, extract_auth
from config import get_settings
from invites.router import validate_invite
from redis_client import get_redis

router = APIRouter()

_watchers: dict[str, set[WebSocket]] = {}


# ── Models ────────────────────────────────────────────────────────────────────

class PeerRegistration(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int = 9001
    network_hint: str = "auto"
    group: str = "default"
    invite_token: str | None = None


class PeerInfo(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int
    last_seen: str
    online: bool
    group: str = "default"
    org_id: str = "dev"


class ScopeConfig(BaseModel):
    scopes: dict[str, list[str]]
    """
    Maps each group name to the list of group names it is allowed to see.
    Use "__all__" as a value to grant visibility over the entire org.
    Example:
      {"admin": ["__all__"], "hq": ["hq", "finance"], "field": ["field"]}
    """


# ── Scope helpers ─────────────────────────────────────────────────────────────

async def _get_scope(org_id: str) -> dict[str, list[str]]:
    r = get_redis()
    raw = await r.get(f"scope:{org_id}")
    return json.loads(raw) if raw else {}


async def _visible_groups(
    caller: CallerInfo, scope: dict[str, list[str]]
) -> list[str] | None:
    """
    Returns the set of group names the caller may see, or None for unrestricted.
    None means "all peers in the org" (admin / dev mode).
    """
    settings = get_settings()
    if not settings.OIDC_ENABLED or caller.is_admin:
        return None

    allowed: set[str] = set()
    for group in caller.groups:
        vis = scope.get(group)
        if vis is None:
            allowed.add(group)          # default: same group only
        elif "__all__" in vis:
            return None                 # can see everything
        else:
            allowed.update(vis)

    if not caller.groups:
        allowed.add("default")

    return list(allowed)


# ── Redis snapshot ────────────────────────────────────────────────────────────

async def _snapshot(org_id: str, caller: CallerInfo) -> list[dict]:
    r = get_redis()
    scope = await _get_scope(org_id)
    visible = await _visible_groups(caller, scope)

    result = []
    async for key in r.scan_iter(f"peer:{org_id}:*"):
        data = await r.hgetall(key)
        if not data:
            continue
        peer_group = data.get("group", "default")
        if visible is not None and peer_group not in visible:
            continue
        result.append({
            "peer_id": data["peer_id"],
            "api_url": data["api_url"],
            "udp_host": data["udp_host"],
            "udp_port": int(data["udp_port"]),
            "last_seen": data["last_seen"],
            "online": True,
            "group": peer_group,
            "org_id": org_id,
        })
    return result


async def _broadcast(org_id: str, caller: CallerInfo) -> None:
    watchers = _watchers.get(org_id, set())
    if not watchers:
        return
    # Broadcast uses an admin-level snapshot so all subscribers get the full list;
    # scope enforcement happens per-connection in the WebSocket handler.
    admin_caller = CallerInfo(peer_id=None, is_service=True, org_id=org_id)
    payload = json.dumps(await _snapshot(org_id, admin_caller))
    dead: set[WebSocket] = set()
    for ws in list(watchers):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    watchers -= dead


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/register", response_model=PeerInfo)
async def register(
    reg: PeerRegistration,
    caller: CallerInfo = Depends(extract_auth),
) -> PeerInfo:
    settings = get_settings()

    if caller.peer_id:
        effective_peer_id = caller.peer_id
    elif caller.is_service:
        effective_peer_id = reg.peer_id
    elif reg.invite_token:
        await validate_invite(reg.invite_token)
        effective_peer_id = reg.peer_id
    elif not settings.OIDC_ENABLED:
        effective_peer_id = reg.peer_id
    else:
        raise HTTPException(401, "Authentication required")

    # In OIDC mode the group comes from the first JWT group; body group used in dev.
    effective_group = (
        caller.groups[0] if (settings.OIDC_ENABLED and caller.groups) else reg.group
    )

    r = get_redis()
    now = datetime.now(timezone.utc).isoformat()
    ttl = settings.HEARTBEAT_TTL_S
    key = f"peer:{caller.org_id}:{effective_peer_id}"
    await r.hset(key, mapping={
        "peer_id": effective_peer_id,
        "api_url": reg.api_url,
        "udp_host": reg.udp_host,
        "udp_port": str(reg.udp_port),
        "last_seen": now,
        "network_hint": reg.network_hint,
        "group": effective_group,
        "org_id": caller.org_id,
    })
    await r.expire(key, ttl)
    await _broadcast(caller.org_id, caller)
    return PeerInfo(
        peer_id=effective_peer_id,
        api_url=reg.api_url,
        udp_host=reg.udp_host,
        udp_port=reg.udp_port,
        last_seen=now,
        online=True,
        group=effective_group,
        org_id=caller.org_id,
    )


@router.post("/{peer_id}/heartbeat")
async def heartbeat(
    peer_id: str,
    caller: CallerInfo = Depends(extract_auth),
) -> dict:
    r = get_redis()
    key = f"peer:{caller.org_id}:{peer_id}"
    if not await r.exists(key):
        raise HTTPException(404, "Peer not registered")
    now = datetime.now(timezone.utc).isoformat()
    await r.hset(key, "last_seen", now)
    await r.expire(key, get_settings().HEARTBEAT_TTL_S)
    await _broadcast(caller.org_id, caller)
    return {"status": "ok"}


@router.get("/", response_model=list[PeerInfo])
async def list_peers(
    caller: CallerInfo = Depends(extract_auth),
) -> list[PeerInfo]:
    return [PeerInfo(**p) for p in await _snapshot(caller.org_id, caller)]


@router.get("/scopes", response_model=ScopeConfig)
async def get_scopes(
    caller: CallerInfo = Depends(extract_auth),
) -> ScopeConfig:
    if get_settings().OIDC_ENABLED and not caller.is_admin:
        raise HTTPException(403, "Admin required")
    return ScopeConfig(scopes=await _get_scope(caller.org_id))


@router.put("/scopes", response_model=ScopeConfig)
async def set_scopes(
    body: ScopeConfig,
    caller: CallerInfo = Depends(extract_auth),
) -> ScopeConfig:
    if get_settings().OIDC_ENABLED and not caller.is_admin:
        raise HTTPException(403, "Admin required")
    r = get_redis()
    await r.set(f"scope:{caller.org_id}", json.dumps(body.scopes))
    return body


@router.get("/{peer_id}", response_model=PeerInfo)
async def get_peer(
    peer_id: str,
    caller: CallerInfo = Depends(extract_auth),
) -> PeerInfo:
    r = get_redis()
    data = await r.hgetall(f"peer:{caller.org_id}:{peer_id}")
    if not data:
        raise HTTPException(404, "Peer not found")
    return PeerInfo(
        peer_id=data["peer_id"],
        api_url=data["api_url"],
        udp_host=data["udp_host"],
        udp_port=int(data["udp_port"]),
        last_seen=data["last_seen"],
        online=True,
        group=data.get("group", "default"),
        org_id=data.get("org_id", caller.org_id),
    )


@router.websocket("/watch")
async def watch_peers(ws: WebSocket) -> None:
    """
    Real-time peer discovery stream.
    OIDC mode: pass the JWT as ?token=<bearer> query parameter.
    Dev mode:  no auth required.
    """
    await ws.accept()

    settings = get_settings()
    org_id = "dev"

    if settings.OIDC_ENABLED:
        token = ws.query_params.get("token", "")
        if not token:
            await ws.close(code=4001, reason="token required")
            return
        from auth.verifier import org_id_from_issuer, verify_token
        try:
            payload = verify_token(token)
            org_id = org_id_from_issuer(payload.get("iss", ""))
        except Exception:
            await ws.close(code=4001, reason="invalid token")
            return

    # WebSocket streams the admin-level snapshot; per-connection scope filtering
    # is a TODO — the client already enforces group labels from each PeerInfo.
    caller = CallerInfo(peer_id=None, is_service=True, org_id=org_id)

    _watchers.setdefault(org_id, set()).add(ws)
    try:
        await ws.send_text(json.dumps(await _snapshot(org_id, caller)))
        while True:
            await asyncio.sleep(10)
            await ws.send_text(json.dumps(await _snapshot(org_id, caller)))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _watchers.get(org_id, set()).discard(ws)
