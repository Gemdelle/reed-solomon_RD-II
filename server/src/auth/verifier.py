"""
Verify Keycloak JWTs via JWKS key discovery.

Multi-realm support: trusts any realm on the same Keycloak instance as the
configured OIDC_ISSUER (or OIDC_KEYCLOAK_URL if set explicitly). JWKS clients
are cached per issuer so key rotation is handled transparently.
"""
import jwt
from jwt import PyJWKClient

from config import get_settings

_jwks_clients: dict[str, PyJWKClient] = {}


def _keycloak_base() -> str:
    settings = get_settings()
    if settings.OIDC_KEYCLOAK_URL:
        return settings.OIDC_KEYCLOAK_URL.rstrip("/")
    if "/realms/" in settings.OIDC_ISSUER:
        return settings.OIDC_ISSUER.split("/realms/")[0]
    return settings.OIDC_ISSUER.rstrip("/")


def _trusted_issuer(issuer: str) -> bool:
    """Accept tokens from any realm on our Keycloak host."""
    settings = get_settings()
    if settings.OIDC_ISSUER and issuer == settings.OIDC_ISSUER:
        return True
    base = _keycloak_base()
    return bool(base) and issuer.startswith(f"{base}/realms/")


def _jwks_url(issuer: str) -> str:
    """
    Build the JWKS endpoint URL.
    When OIDC_KEYCLOAK_URL is set (e.g. internal docker hostname), we replace the
    external base in the issuer URL so the server can reach Keycloak from inside
    the container, while still accepting tokens whose `iss` uses the public URL.
    """
    settings = get_settings()
    if settings.OIDC_KEYCLOAK_URL and "/realms/" in issuer:
        realm_path = issuer.split("/realms/", 1)[1]
        internal_base = settings.OIDC_KEYCLOAK_URL.rstrip("/")
        return f"{internal_base}/realms/{realm_path}/protocol/openid-connect/certs"
    return f"{issuer}/protocol/openid-connect/certs"


def _get_jwks_client(issuer: str) -> PyJWKClient:
    if issuer not in _jwks_clients:
        _jwks_clients[issuer] = PyJWKClient(_jwks_url(issuer))
    return _jwks_clients[issuer]


def verify_token(token: str) -> dict:
    """
    Decode and verify a Keycloak JWT.
    Returns the full payload; raises jwt.PyJWTError on failure.
    """
    unverified = jwt.decode(token, options={"verify_signature": False})
    issuer = unverified.get("iss", "")
    if not _trusted_issuer(issuer):
        raise jwt.InvalidIssuerError(f"Untrusted issuer: {issuer!r}")
    signing_key = _get_jwks_client(issuer).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


def org_id_from_issuer(issuer: str) -> str:
    """Extract realm name from a Keycloak issuer URL."""
    if "/realms/" in issuer:
        return issuer.split("/realms/")[-1].rstrip("/")
    return issuer


def groups_from_payload(payload: dict) -> list[str]:
    """
    Normalize the groups claim from Keycloak.
    Keycloak emits paths like ["/admin", "/hq"] — strip the leading slash.
    """
    return [g.lstrip("/") for g in payload.get("groups", []) if isinstance(g, str)]
