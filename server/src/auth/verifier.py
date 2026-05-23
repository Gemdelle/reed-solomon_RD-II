"""
Verify Keycloak JWTs via JWKS key discovery.
"""
import jwt
from jwt import PyJWKClient

from config import get_settings

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        issuer = get_settings().OIDC_ISSUER
        _jwks_client = PyJWKClient(f"{issuer}/protocol/openid-connect/certs")
    return _jwks_client


def verify_token(token: str) -> dict:
    """Decode and verify a Keycloak JWT. Raises jwt.PyJWTError on failure."""
    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
