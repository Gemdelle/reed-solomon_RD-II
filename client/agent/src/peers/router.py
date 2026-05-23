"""
Peer discovery proxy — delegates to the central server via server_client.
Exposes /peers on the agent so the UI only needs one base URL.
"""
from fastapi import APIRouter, HTTPException

from server_client import server_client

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_peers() -> list[dict]:
    try:
        return await server_client.get_peers()
    except Exception as exc:
        raise HTTPException(503, f"Server unreachable: {exc}")


@router.get("/{peer_id}", response_model=dict)
async def get_peer(peer_id: str) -> dict:
    try:
        return await server_client.get_peer(peer_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(503, f"Server unreachable: {exc}")
