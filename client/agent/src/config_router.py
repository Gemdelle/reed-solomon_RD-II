"""
Runtime configuration router.

GET  /config  — returns the current effective configuration.
PUT  /config  — switches the active transport at runtime and re-registers
                with the server under the new transport.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import token_store
from config import get_settings
from rs.transport import QUICTransport, UDPTransport, get_transport, set_transport
from server_client import server_client

router = APIRouter()


class ConfigResponse(BaseModel):
    transport_mode: str
    peer_id: str
    udp_host: str
    udp_port: int


class ConfigUpdateRequest(BaseModel):
    transport_mode: Literal["udp", "quic"]


class ConfigUpdateResponse(BaseModel):
    transport_mode: str
    ok: bool


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        transport_mode=token_store.get_transport_mode() or settings.TRANSPORT_MODE,
        peer_id=token_store.get_peer_id() or settings.PEER_ID,
        udp_host=settings.udp_advertise_host,
        udp_port=settings.UDP_PORT,
    )


@router.put("", response_model=ConfigUpdateResponse)
async def update_config(body: ConfigUpdateRequest) -> ConfigUpdateResponse:
    settings = get_settings()
    mode = body.transport_mode

    old_transport = get_transport()

    if mode == "quic":
        new_transport = QUICTransport()
    else:
        new_transport = UDPTransport()

    # Stop existing transport before binding the new one on the same port.
    old_transport.stop()

    try:
        set_transport(new_transport)
        await new_transport.start(settings.UDP_HOST, settings.UDP_PORT)
    except Exception as exc:
        # Revert: restore old transport and attempt a re-bind so the agent
        # remains operational.
        set_transport(old_transport)
        try:
            await old_transport.start(settings.UDP_HOST, settings.UDP_PORT)
        except Exception:
            pass  # Best-effort recovery; old socket may still be open.
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start {mode!r} transport: {exc}",
        )

    token_store.set_transport_mode(mode)

    pid = token_store.get_peer_id() or settings.PEER_ID
    try:
        result = await server_client.register(
            peer_id=pid,
            api_url=settings.AGENT_API_URL,
            udp_host=settings.udp_advertise_host,
            udp_port=settings.UDP_PORT,
            transport=mode,
        )
        token_store.set_peer_id(result.get("peer_id", pid))
    except Exception:
        # Registration failure is non-fatal; transport switch already succeeded.
        pass

    return ConfigUpdateResponse(transport_mode=mode, ok=True)
