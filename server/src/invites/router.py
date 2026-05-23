"""
Peer invite token system.

POST /invites/  — create a single-use invite token.
The token is a signed HS256 JWT (secret = INVITE_SECRET).
Redis tracks state: "pending" → "used"; TTL mirrors the token expiry.
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException

from auth.deps import CallerInfo, extract_auth
from config import get_settings
from redis_client import get_redis

from .models import InviteCreate, InviteInfo

router = APIRouter()


@router.post("/", response_model=InviteInfo)
async def create_invite(
    body: InviteCreate,
    caller: CallerInfo = Depends(extract_auth),
) -> InviteInfo:
    settings = get_settings()

    if settings.OIDC_ENABLED and not caller.peer_id and not caller.is_service:
        raise HTTPException(401, "Authentication required to create invites")

    # In OIDC mode, the invite is always for the caller's own org (realm).
    org_id = caller.org_id if settings.OIDC_ENABLED else body.org_id

    jti = str(uuid.uuid4())
    issued_by = caller.peer_id or "service"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=body.ttl_seconds)

    payload = {
        "jti": jti,
        "sub": "invite",
        "iss": "rockdove",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "org_id": org_id,
        "issued_by": issued_by,
    }
    token = jwt.encode(payload, settings.INVITE_SECRET, algorithm="HS256")

    r = get_redis()
    await r.set(f"invite:{jti}", "pending", ex=body.ttl_seconds)

    return InviteInfo(token=token, issued_by=issued_by, org_id=org_id, expires_at=expires_at)


async def validate_invite(token: str) -> dict:
    """
    Validate and atomically consume a single-use invite token.
    Returns decoded payload on success; raises HTTPException otherwise.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.INVITE_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(410, "Invite token expired")
    except jwt.PyJWTError:
        raise HTTPException(400, "Invalid invite token")

    jti = payload.get("jti", "")
    r = get_redis()
    # SET key "used" only if key exists (XX), return old value (GET) — atomic
    old_state = await r.set(f"invite:{jti}", "used", xx=True, get=True)
    if old_state is None:
        raise HTTPException(410, "Invite token expired or not found")
    if old_state == "used":
        raise HTTPException(409, "Invite token already used")

    return payload
