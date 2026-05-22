"""
Simple in-memory peer registry.
TODO: replace with Keycloak group membership lookup for multi-org support.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_HEARTBEAT_TTL = timedelta(seconds=30)
_peers: dict[str, dict] = {}


class PeerRegistration(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int = 9001


class PeerInfo(BaseModel):
    peer_id: str
    api_url: str
    udp_host: str
    udp_port: int
    last_seen: str
    online: bool


def _is_online(last_seen_iso: str) -> bool:
    last = datetime.fromisoformat(last_seen_iso)
    return (datetime.now(timezone.utc) - last) < _HEARTBEAT_TTL


@router.post("/register", response_model=PeerInfo)
async def register(reg: PeerRegistration) -> PeerInfo:
    _peers[reg.peer_id] = {
        "peer_id": reg.peer_id,
        "api_url": reg.api_url,
        "udp_host": reg.udp_host,
        "udp_port": reg.udp_port,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    return PeerInfo(**_peers[reg.peer_id], online=True)


@router.post("/{peer_id}/heartbeat")
async def heartbeat(peer_id: str) -> dict:
    if peer_id not in _peers:
        raise HTTPException(404, "Peer not registered")
    _peers[peer_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
    return {"status": "ok"}


@router.get("/", response_model=list[PeerInfo])
async def list_peers() -> list[PeerInfo]:
    return [
        PeerInfo(**p, online=_is_online(p["last_seen"]))
        for p in _peers.values()
    ]


@router.get("/{peer_id}", response_model=PeerInfo)
async def get_peer(peer_id: str) -> PeerInfo:
    if peer_id not in _peers:
        raise HTTPException(404, "Peer not found")
    p = _peers[peer_id]
    return PeerInfo(**p, online=_is_online(p["last_seen"]))
