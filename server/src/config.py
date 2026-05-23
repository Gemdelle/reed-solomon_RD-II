from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HEARTBEAT_TTL_S: int = 30
    REDIS_URL: str = "redis://localhost:6379/0"

    # Keycloak / OIDC
    OIDC_ENABLED: bool = False
    OIDC_ISSUER: str = ""
    OIDC_ISSUER_PUBLIC: str = ""
    OIDC_CLIENT_ID: str = ""
    # Base URL of the Keycloak host (e.g. http://keycloak:8081).
    # Any realm under this host is trusted for multi-org support.
    # Derived automatically from OIDC_ISSUER when not set explicitly.
    OIDC_KEYCLOAK_URL: str = ""
    # Keycloak group name that grants admin privileges within an org.
    OIDC_ADMIN_GROUP: str = "admin"

    # Invite tokens
    INVITE_SECRET: str = "change-me-in-production"

    # Headless agent service accounts
    AGENT_SERVICE_TOKEN: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
