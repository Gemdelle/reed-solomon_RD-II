"""
HTTP client for the central RS Transfer Server.
Handles peer registration, heartbeat, peer discovery, and metrics reporting.
"""
import httpx

from config import get_settings

_DEFAULT_REDUNDANCY = 0.25


class ServerClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def _base(self) -> str:
        return self._settings.SERVER_URL

    @property
    def _auth_headers(self) -> dict[str, str]:
        token = self._settings.AGENT_SERVICE_TOKEN
        return {"Authorization": f"Bearer {token}"} if token else {}

    async def register(
        self, peer_id: str, api_url: str, udp_host: str, udp_port: int
    ) -> dict:
        body: dict = {
            "peer_id": peer_id,
            "api_url": api_url,
            "udp_host": udp_host,
            "udp_port": udp_port,
            "network_hint": self._settings.NETWORK_HINT,
        }
        if self._settings.INVITE_TOKEN:
            body["invite_token"] = self._settings.INVITE_TOKEN
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{self._base}/peers/register",
                json=body,
                headers=self._auth_headers,
            )
            r.raise_for_status()
            return r.json()

    async def heartbeat(self, peer_id: str) -> None:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"{self._base}/peers/{peer_id}/heartbeat",
                headers=self._auth_headers,
            )

    async def get_peers(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/peers", headers=self._auth_headers)
            r.raise_for_status()
            return r.json()

    async def get_peer(self, peer_id: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/peers/{peer_id}", headers=self._auth_headers)
            if r.status_code == 404:
                raise ValueError(f"Peer {peer_id!r} not found on server")
            r.raise_for_status()
            return r.json()

    async def report_metrics(
        self, peer_id: str, rtt_ms: float, jitter_ms: float, loss_rate: float
    ) -> None:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                f"{self._base}/metrics/report",
                json={"peer_id": peer_id, "rtt_ms": rtt_ms, "jitter_ms": jitter_ms, "loss_rate": loss_rate},
                headers=self._auth_headers,
            )

    async def get_recommendation(self, peer_id: str) -> float:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(
                    f"{self._base}/metrics/recommendation/{peer_id}",
                    headers=self._auth_headers,
                )
                if r.status_code == 200:
                    return r.json()["redundancy_level"]
        except Exception:
            pass
        return _DEFAULT_REDUNDANCY


server_client = ServerClient()
