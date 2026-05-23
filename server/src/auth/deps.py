"""
FastAPI dependency: extract and validate caller identity.

Dev mode  (OIDC_ENABLED=False) — no auth required; peer_id from request body.
OIDC mode (OIDC_ENABLED=True):
  Bearer <keycloak_jwt>    → verify via JWKS; sub → peer_id
  Bearer <service_token>   → compare with AGENT_SERVICE_TOKEN setting
"""
import jwt
from fastapi import Header, HTTPException

from config import get_settings
from .verifier import verify_token


class CallerInfo:
    def __init__(self, peer_id: str | None, is_service: bool = False) -> None:
        self.peer_id = peer_id
        self.is_service = is_service


async def extract_auth(
    authorization: str | None = Header(default=None),
) -> CallerInfo:
    settings = get_settings()

    if not settings.OIDC_ENABLED:
        return CallerInfo(peer_id=None, is_service=False)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization header required")

    token = authorization.removeprefix("Bearer ").strip()

    if settings.AGENT_SERVICE_TOKEN and token == settings.AGENT_SERVICE_TOKEN:
        return CallerInfo(peer_id=None, is_service=True)

    try:
        payload = verify_token(token)
        return CallerInfo(peer_id=payload.get("sub"), is_service=False)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid token: {exc}")
