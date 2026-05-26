import os
import socket
from functools import lru_cache
from pathlib import Path

from typing import Literal

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
    # Explicit advertise address for VPN / multi-homed setups.
    # If empty, auto-detected from the default route.
    UDP_ADVERTISE_HOST: str = ""
    STORAGE_PATH: str = _default_storage_path()
    NETWORK_HINT: str = "auto"
    AGENT_SERVICE_TOKEN: str = ""
    INVITE_TOKEN: str = ""
    TRANSPORT_MODE: Literal["udp", "quic"] = "udp"

    # Relay configuration
    RELAY_CAPABLE: bool = False
    # Comma-separated tags: "ephemeral" | "restricted" | "gateway"
    RELAY_TAGS: str = ""
    # For restricted tag: comma-separated peer_ids allowed to use this relay
    RELAY_ALLOWED_PEERS: str = ""
    # For restricted tag: comma-separated groups allowed to use this relay
    RELAY_ALLOWED_GROUPS: str = ""
    # For gateway tag: JSON mapping peer_id → {host, port, api_port?}
    # e.g. '{"satellite-sta-1": {"host": "10.5.0.2", "port": 9001}}'
    RELAY_STATIC_ROUTES: str = "{}"

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def _resolve_agent_url(self) -> "Settings":
        if not self.AGENT_API_URL:
            self.AGENT_API_URL = f"http://{_detect_local_ip()}:{self.AGENT_PORT}"
        return self

    @property
    def udp_advertise_host(self) -> str:
        """Routable IP to register for UDP — explicit override wins, then auto-detect."""
        if self.UDP_ADVERTISE_HOST:
            return self.UDP_ADVERTISE_HOST
        if self.UDP_HOST in ("0.0.0.0", "::"):
            return _detect_local_ip()
        return self.UDP_HOST


@lru_cache
def get_settings() -> Settings:
    return Settings()
