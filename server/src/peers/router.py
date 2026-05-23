"""
Central peer registry backed by Redis.

Peers are stored as Redis hashes at key peer:{peer_id} with a TTL equal to
HEARTBEAT_TTL_S. A peer is considered online as long as its key exists — Redis
expiry handles the offline transition automatically. WebSocket /peers/watch
pushes the full peer list to subscribers on every register/heartbeat event,
and falls back to a 10s periodic refresh to catch TTL expirations.

Auth (when OIDC_ENABLED=True):
  - Keycloak JWT   → sub used as peer_id (user's identity)
  - Service token  → body peer_id trusted directly
  - Invite token   → validated + consumed; body peer_id trusted
  - No token       → rejected in OIDC mode, allowed in dev mode
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

_watchers: set[WebSocket] = set()


class PeerRegistration(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int = 9001
    network_hint: str = "auto"
    invite_token: str | None = None


class PeerInfo(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int
    last_seen: str
    online: bool


async def _snapshot() -> list[dict]:
    r = get_redis()
    result = []
    async for key in r.scan_iter("peer:*"):
        data = await r.hgetall(key)
        if data:
            result.append({
                "peer_id": data["peer_id"],
                "api_url": data["api_url"],
                "udp_host": data["udp_host"],
                "udp_port": int(data["udp_port"]),
                "last_seen": data["last_seen"],
                "online": True,
            })
    return result


async def _broadcast() -> None:
    if not _watchers:
        return
    payload = json.dumps(await _snapshot())
    dead: set[WebSocket] = set()
    for ws in list(_watchers):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _watchers -= dead


@router.post("/register", response_model=PeerInfo)
async def register(
    reg: PeerRegistration,
    caller: CallerInfo = Depends(extract_auth),
) -> PeerInfo:
    settings = get_settings()

    # Determine effective peer_id based on auth method
    if caller.peer_id:
        # OIDC JWT — identity comes from the token
        effective_peer_id = caller.peer_id
    elif caller.is_service:
        # Service account — trust the body
        effective_peer_id = reg.peer_id
    elif reg.invite_token:
        # Invite token — validate + consume, then trust body peer_id
        await validate_invite(reg.invite_token)
        effective_peer_id = reg.peer_id
    elif not settings.OIDC_ENABLED:
        # Dev mode — no auth required
        effective_peer_id = reg.peer_id
    else:
        raise HTTPException(401, "Authentication required")

    r = get_redis()
    now = datetime.now(timezone.utc).isoformat()
    ttl = settings.HEARTBEAT_TTL_S
    await r.hset(f"peer:{effective_peer_id}", mapping={
        "peer_id": effective_peer_id,
        "api_url": reg.api_url,
        "udp_host": reg.udp_host,
        "udp_port": str(reg.udp_port),
        "last_seen": now,
        "network_hint": reg.network_hint,
    })
    await r.expire(f"peer:{effective_peer_id}", ttl)
    await _broadcast()
    return PeerInfo(
        peer_id=effective_peer_id,
        api_url=reg.api_url,
        udp_host=reg.udp_host,
        udp_port=reg.udp_port,
        last_seen=now,
        online=True,
    )


@router.post("/{peer_id}/heartbeat")
async def heartbeat(peer_id: str) -> dict:
    r = get_redis()
    if not await r.exists(f"peer:{peer_id}"):
        raise HTTPException(404, "Peer not registered")
    now = datetime.now(timezone.utc).isoformat()
    ttl = get_settings().HEARTBEAT_TTL_S
    await r.hset(f"peer:{peer_id}", "last_seen", now)
    await r.expire(f"peer:{peer_id}", ttl)
    await _broadcast()
    return {"status": "ok"}


@router.get("/", response_model=list[PeerInfo])
async def list_peers() -> list[PeerInfo]:
    return [PeerInfo(**p) for p in await _snapshot()]


@router.get("/{peer_id}", response_model=PeerInfo)
async def get_peer(peer_id: str) -> PeerInfo:
    r = get_redis()
    data = await r.hgetall(f"peer:{peer_id}")
    if not data:
        raise HTTPException(404, "Peer not found")
    return PeerInfo(
        peer_id=data["peer_id"],
        api_url=data["api_url"],
        udp_host=data["udp_host"],
        udp_port=int(data["udp_port"]),
        last_seen=data["last_seen"],
        online=True,
    )


@router.websocket("/watch")
async def watch_peers(ws: WebSocket) -> None:
    """
    Real-time peer discovery stream.
    Pushes the full peer list on connect, then on every register/heartbeat event.
    Periodic 10s refresh catches TTL-expired peers.
    """
    await ws.accept()
    _watchers.add(ws)
    try:
        await ws.send_text(json.dumps(await _snapshot()))
        while True:
            await asyncio.sleep(10)
            await ws.send_text(json.dumps(await _snapshot()))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _watchers.discard(ws)
