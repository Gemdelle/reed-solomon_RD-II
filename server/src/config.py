from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HEARTBEAT_TTL_S: int = 30
    REDIS_URL: str = "redis://localhost:6379/0"

    # Keycloak / OIDC
    OIDC_ENABLED: bool = False
    OIDC_ISSUER: str = ""         # internal URL used for token validation
    OIDC_ISSUER_PUBLIC: str = ""  # public URL shown to the UI (set when Keycloak is behind a proxy)
    OIDC_CLIENT_ID: str = ""

    # Invite tokens
    INVITE_SECRET: str = "change-me-in-production"

    # Headless agent service accounts
    AGENT_SERVICE_TOKEN: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
