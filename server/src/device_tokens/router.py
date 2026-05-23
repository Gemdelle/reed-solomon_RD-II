from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from auth.deps import CallerInfo, extract_auth
from config import get_settings

from .models import DeviceTokenCreate, DeviceTokenInfo
from . import store

router = APIRouter()


def _to_info(meta: dict, token: str | None = None) -> DeviceTokenInfo:
    expires_raw = meta.get("expires_at") or None
    return DeviceTokenInfo(
        id=meta["id"],
        label=meta["label"],
        peer_id=meta.get("peer_id") or None,
        org_id=meta["org_id"],
        created_by=meta["created_by"],
        created_at=datetime.fromisoformat(meta["created_at"]),
        expires_at=datetime.fromisoformat(expires_raw) if expires_raw else None,
        token_preview=meta.get("token_preview", (token or "")[:12] + "..."),
        token=token,
    )


def _require_admin(caller: CallerInfo) -> None:
    if get_settings().OIDC_ENABLED and not caller.is_admin:
        raise HTTPException(403, "Admin required")


@router.post("/", response_model=DeviceTokenInfo, status_code=201)
async def create_device_token(
    body: DeviceTokenCreate,
    caller: CallerInfo = Depends(extract_auth),
) -> DeviceTokenInfo:
    _require_admin(caller)
    token, meta = await store.create(
        org_id=caller.org_id,
        label=body.label,
        created_by=caller.peer_id or "service",
        peer_id=body.peer_id,
        ttl_seconds=body.ttl_seconds,
    )
    return _to_info(meta, token=token)


@router.get("/", response_model=list[DeviceTokenInfo])
async def list_device_tokens(
    caller: CallerInfo = Depends(extract_auth),
) -> list[DeviceTokenInfo]:
    _require_admin(caller)
    rows = await store.list_for_org(caller.org_id)
    return [_to_info(r) for r in rows]


@router.delete("/{token_id}", status_code=204)
async def revoke_device_token(
    token_id: str,
    caller: CallerInfo = Depends(extract_auth),
) -> None:
    _require_admin(caller)
    if not await store.revoke(caller.org_id, token_id):
        raise HTTPException(404, "Token not found or already expired")
