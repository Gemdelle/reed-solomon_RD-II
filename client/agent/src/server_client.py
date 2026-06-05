from __future__ import annotations
import urllib.parse
import logging
from typing import Optional

import token_store
import config_store as _config_store
from config import get_settings
from quic_client import ServerQuicClient

_DEFAULT_REDUNDANCY = 0.25
logger = logging.getLogger(__name__)

class ServerClient:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._quic_instance: Optional[ServerQuicClient] = None
        self._last_quic_base: Optional[str] = None

    @property
    def _base(self) -> str:
        return token_store.get_server_url() or self._settings.SERVER_URL

    @property
    def _quic(self) -> ServerQuicClient:
        base = self._base
        if self._quic_instance is None or self._last_quic_base != base:
            u = urllib.parse.urlparse(base)
            self._quic_instance = ServerQuicClient(u.hostname or "localhost", 9000)
            self._last_quic_base = base
        return self._quic_instance

    @property
    def _token(self) -> str | None:
        return self._settings.AGENT_SERVICE_TOKEN or token_store.get_token()

    async def start_quic(self) -> None:
        """Eagerly establish the QUIC server connection at startup."""
        try:
            await self._quic.start()
        except Exception:
            logger.warning("QUIC early connect failed — will retry on first call")

    async def register(
        self,
        peer_id: str,
        api_url: str,
        udp_host: str,
        udp_port: int,
        transport: str = "udp",
        owner: str | None = None,
    ) -> dict:
        params: dict = {
            "peer_id": peer_id,
            "api_url": api_url,
            "udp_host": udp_host,
            "udp_port": udp_port,
            "transport": transport,
            "relay_capable": self._settings.RELAY_CAPABLE,
            "relay_tags": [t.strip() for t in self._settings.RELAY_TAGS.split(",") if t.strip()],
            "owner": owner or self._settings.PEER_OWNER or None,
        }
        try:
            invite = _config_store.get("invite_token", "") or self._settings.INVITE_TOKEN
            params["invite_token"] = invite
            params["network_hint"] = _config_store.get("network_hint", self._settings.NETWORK_HINT)
        except Exception:
            params["invite_token"] = self._settings.INVITE_TOKEN
            params["network_hint"] = self._settings.NETWORK_HINT
            
        return await self._quic.call("peers.register", params, self._token)

    async def heartbeat(self, peer_id: str) -> None:
        await self._quic.call("peers.heartbeat", {"peer_id": peer_id}, self._token)

    async def get_peers(self) -> list[dict]:
        return await self._quic.call("peers.list", {}, self._token)

    async def get_peer(self, peer_id: str) -> dict:
        return await self._quic.call("peers.get", {"peer_id": peer_id}, self._token)

    async def report_metrics(
        self, peer_id: str, rtt_ms: float, jitter_ms: float, loss_rate: float, target_peer_id: str = "server"
    ) -> None:
        params = {
            "peer_id": peer_id,
            "target_peer_id": target_peer_id,
            "rtt_ms": rtt_ms,
            "jitter_ms": jitter_ms,
            "loss_rate": loss_rate
        }
        await self._quic.call("metrics.report", params, self._token)

    async def get_full_recommendation(self, peer_id: str) -> dict:
        """Returns {redundancy_level, quality, profile_name, based_on_samples}."""
        try:
            return await self._quic.call("metrics.recommendation", {"peer_id": peer_id}, self._token)
        except Exception as e:
            logger.error(f"Failed to get recommendation via QUIC: {e}")
            return {
                "redundancy_level": _DEFAULT_REDUNDANCY,
                "quality": "unknown",
                "profile_name": "unknown",
                "based_on_samples": 0,
            }

    async def get_recommendation(self, peer_id: str) -> float:
        rec = await self.get_full_recommendation(peer_id)
        return rec["redundancy_level"]

    async def get_incoming_policy(self, peer_id: str) -> dict:
        """Fetch the server-side incoming policy for this peer (admin-configured)."""
        try:
            return await self._quic.call("peers.incoming_policy", {"peer_id": peer_id}, self._token)
        except Exception:
            return {}

    async def get_relay_for_peer(self, target_id: str) -> dict:
        """Ask the server for the best relay peer to reach target_id."""
        return await self._quic.call("peers.relay", {"target": target_id}, self._token)

server_client = ServerClient()
