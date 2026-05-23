import os
import socket
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


def _detect_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _default_storage_path() -> str:
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return str(base / "rockdove")


class Settings(BaseSettings):
    SERVER_URL: str = "http://localhost:8080"
    PEER_ID: str = "default-peer"
    AGENT_API_URL: str = ""
    AGENT_PORT: int = 8000
    UDP_HOST: str = "0.0.0.0"
    UDP_PORT: int = 9001
    STORAGE_PATH: str = _default_storage_path()
    NETWORK_HINT: str = "auto"
    AGENT_SERVICE_TOKEN: str = ""
    INVITE_TOKEN: str = ""

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def _resolve_agent_url(self) -> "Settings":
        if not self.AGENT_API_URL:
            self.AGENT_API_URL = f"http://{_detect_local_ip()}:{self.AGENT_PORT}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
