import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

import token_store
from config import get_settings
from rs.decoder import decode_transfer
from rs.encoder import encode_file
from rs.models import TransferStatus
from rs.transport import QUICTransport, UDPTransport, get_transport, set_transport
from server_client import server_client
from metrics.otel import get_meter
from storage.db import insert_transfer, list_history
from storage.store import FileStorage
from transfers.models import HistoryEntry, IncomingConnection, ReceiveRequest, SendRequest, TransferResult

router = APIRouter()

_transfers: dict[str, dict] = {}
_transport_requests: dict[str, dict] = {}


@router.post("/send", response_model=TransferResult)
async def send_file(req: SendRequest) -> TransferResult:
    get_meter().create_counter("rs_transfers_total").add(1, {"direction": "sent"})
    settings = get_settings()
    storage = FileStorage(settings.STORAGE_PATH)

    meta = storage.get_meta(req.file_id)
    if not meta:
        raise HTTPException(404, "File not found")
    file_bytes = storage.get_bytes(req.file_id)
    if file_bytes is None:
        raise HTTPException(404, "File bytes not found")

    redundancy_level = req.redundancy_level
    effective_quality: str | None = None
    effective_profile: str | None = None
    if redundancy_level is None:
        sender_rec, target_rec = await asyncio.gather(
            server_client.get_full_recommendation(settings.PEER_ID),
            server_client.get_full_recommendation(req.target_peer_id),
        )
        # Worst endpoint drives redundancy — if either side is degraded, protect the transfer
        if target_rec["redundancy_level"] >= sender_rec["redundancy_level"]:
            chosen = target_rec
        else:
            chosen = sender_rec
        redundancy_level = chosen["redundancy_level"]
        effective_quality = chosen.get("quality")
        effective_profile = chosen.get("profile_name")

    try:
        peer = await server_client.get_peer(req.target_peer_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    peer_transport = peer.get("transport", "udp")
    requested_transport = req.transport or peer_transport
    if requested_transport != peer_transport:
        raise HTTPException(
            400,
            f"Transport mismatch: peer is registered as '{peer_transport}', requested '{requested_transport}'",
        )

    target_api_url = peer["api_url"]
    target_udp_host = peer["udp_host"]
    target_udp_port = peer["udp_port"]

    packets, transfer_id, n, k, chunk_size = encode_file(file_bytes, redundancy_level)

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            r = await client.post(
                f"{target_api_url}/transfer/receive",
                json={
                    "transfer_id": transfer_id,
                    "checksum": meta["sha256"],
                    "file_size": len(file_bytes),
                    "n": n, "k": k, "chunk_size": chunk_size,
                    "filename": meta.get("filename", ""),
                },
            )
            if r.status_code not in (200, 202):
                raise HTTPException(502, f"Peer rejected transfer: {r.text}")
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Cannot reach peer: {exc}")

    t_send = time.monotonic()
    await get_transport().send(packets, target_udp_host, target_udp_port)
    get_meter().create_counter("rs_packets_sent_total").add(len(packets))

    result = TransferResult(
        transfer_id=transfer_id,
        status=TransferStatus.failed,
        reason="timeout_waiting_for_peer_result",
    )
    async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
        for _ in range(70):
            await asyncio.sleep(0.5)
            try:
                r = await client.get(f"{target_api_url}/transfer/{transfer_id}/status")
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") not in ("pending", None):
                        result = TransferResult(**data)
                        break
            except httpx.RequestError:
                pass

    elapsed_ms = (time.monotonic() - t_send) * 1000.0
    loss_rate = (
        result.recovered_blocks / result.total_blocks
        if result.total_blocks > 0
        else 0.0
    )
    asyncio.create_task(
        server_client.report_metrics(
            settings.PEER_ID,
            rtt_ms=elapsed_ms,
            jitter_ms=0.0,
            loss_rate=loss_rate,
        )
    )
    asyncio.create_task(
        insert_transfer(
            transfer_id=transfer_id,
            direction="sent",
            peer_id=req.target_peer_id,
            filename=meta.get("filename"),
            bytes_=len(file_bytes),
            status=str(result.status.value if hasattr(result.status, "value") else result.status),
            redundancy=redundancy_level,
            recovered_blocks=result.recovered_blocks,
            total_blocks=result.total_blocks,
            quality=effective_quality,
            profile_name=effective_profile,
        )
    )

    base = result.model_dump(exclude={"effective_redundancy", "quality", "profile_name"})
    return TransferResult(
        **base,
        effective_redundancy=redundancy_level,
        quality=effective_quality,
        profile_name=effective_profile,
    )


@router.post("/receive", status_code=202)
async def receive_transfer(req: ReceiveRequest, background_tasks: BackgroundTasks) -> dict:
    _transfers[req.transfer_id] = {"status": "pending"}
    background_tasks.add_task(_process_incoming, req)
    return {"transfer_id": req.transfer_id, "status": "pending"}


async def _process_incoming(req: ReceiveRequest) -> None:
    get_meter().create_counter("rs_transfers_total").add(1, {"direction": "received"})
    settings = get_settings()
    transport = get_transport()

    # If QUIC: wait for operator to approve the incoming cert-authenticated connection
    # before decoding.  Auto-approves on timeout so the transfer never stalls.
    if isinstance(transport, QUICTransport):
        approved = await transport.wait_for_approval(req.transfer_id, timeout=30.0)
        if not approved:
            transport.clear_buffer(req.transfer_id)
            _transfers[req.transfer_id] = {
                "transfer_id": req.transfer_id,
                "status": TransferStatus.failed,
                "recovered_blocks": 0,
                "total_blocks": 0,
                "file_id": None,
                "reason": "rejected_by_operator",
            }
            return

    packets = await transport.collect(req.transfer_id, timeout=req.timeout)
    result = decode_transfer(packets, req.checksum)
    
    if result.recovered_blocks > 0:
        get_meter().create_counter("rs_packets_recovered_total").add(result.recovered_blocks)

    file_id = None
    if result.status != TransferStatus.failed and result.file_bytes:
        storage = FileStorage(settings.STORAGE_PATH)
        saved = storage.save(result.file_bytes, req.filename or f"transfer_{req.transfer_id}")
        file_id = saved["file_id"]

    _transfers[req.transfer_id] = {
        "transfer_id": req.transfer_id,
        "status": result.status,
        "recovered_blocks": result.recovered_blocks,
        "total_blocks": result.total_blocks,
        "file_id": file_id,
        "reason": result.reason,
    }
    asyncio.create_task(
        insert_transfer(
            transfer_id=req.transfer_id,
            direction="received",
            peer_id=None,
            filename=f"transfer_{req.transfer_id}",
            bytes_=req.file_size,
            status=str(result.status.value if hasattr(result.status, "value") else result.status),
            recovered_blocks=result.recovered_blocks,
            total_blocks=result.total_blocks,
        )
    )


@router.get("/{transfer_id}/status", response_model=TransferResult)
async def get_status(transfer_id: str) -> TransferResult:
    if transfer_id not in _transfers:
        raise HTTPException(404, "Transfer not found")
    return TransferResult(**_transfers[transfer_id])


@router.get("/history", response_model=list[HistoryEntry])
async def get_history(limit: int = 50) -> list[HistoryEntry]:
    rows = await list_history(limit=limit)
    return [HistoryEntry(**r) for r in rows]


@router.get("/", response_model=list[TransferResult])
async def list_transfers() -> list[TransferResult]:
    return [TransferResult(**v) for v in _transfers.values()]


# ── Transport negotiation ─────────────────────────────────────────────────────

class TransportRequestBody(BaseModel):
    sender_peer_id: str
    requested_transport: Literal["udp", "quic"]


async def _switch_transport(mode: str) -> None:
    """Stop the current transport, start a new one, update token_store, re-register."""
    import config_store
    settings = get_settings()
    udp_host = config_store.get("udp_host", settings.UDP_HOST)
    udp_port = config_store.get("udp_port", settings.UDP_PORT)

    old_transport = get_transport()
    new_transport = QUICTransport() if mode == "quic" else UDPTransport()

    old_transport.stop()
    set_transport(new_transport)
    await new_transport.start(udp_host, udp_port)

    token_store.set_transport_mode(mode)

    pid = token_store.get_peer_id() or config_store.get("peer_id", settings.PEER_ID)
    try:
        advertise = config_store.get("udp_advertise_host", "") or settings.udp_advertise_host
        result = await server_client.register(
            peer_id=pid,
            api_url=config_store.get("agent_api_url", "") or settings.AGENT_API_URL,
            udp_host=advertise,
            udp_port=udp_port,
            transport=mode,
        )
        token_store.set_peer_id(result.get("peer_id", pid))
    except Exception:
        pass


@router.post("/transport-request")
async def receive_transport_request(body: TransportRequestBody) -> dict:
    """Called by a remote peer's sender to ask us to switch transport."""
    req_id = str(uuid.uuid4())
    _transport_requests[req_id] = {
        "request_id": req_id,
        "sender_peer_id": body.sender_peer_id,
        "requested_transport": body.requested_transport,
        "arrived_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    return {"request_id": req_id}


@router.get("/transport-requests")
async def list_transport_requests() -> list[dict]:
    """Return all pending transport-switch requests."""
    return list(_transport_requests.values())


@router.post("/transport-requests/{req_id}/accept")
async def accept_transport_request(req_id: str) -> dict:
    """Accept a transport-switch request, switch transport, and re-register."""
    req = _transport_requests.get(req_id)
    if req is None:
        raise HTTPException(404, "Transport request not found")

    mode = req["requested_transport"]

    try:
        await _switch_transport(mode)
    except Exception as exc:
        raise HTTPException(500, f"Failed to switch transport to {mode!r}: {exc}")

    del _transport_requests[req_id]
    return {"ok": True, "transport_mode": mode}


@router.post("/transport-requests/{req_id}/reject")
async def reject_transport_request(req_id: str) -> dict:
    """Reject a transport-switch request without switching."""
    _transport_requests.pop(req_id, None)
    return {"ok": True}


@router.post("/request-transport")
async def request_transport_from_peer(
    target_peer_id: str,
    requested_transport: str,
) -> dict:
    """Ask a remote peer (via their agent API) to switch transport."""
    settings = get_settings()
    effective_pid = token_store.get_peer_id() or settings.PEER_ID

    try:
        peer = await server_client.get_peer(target_peer_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    api_url: str = peer["api_url"]

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        try:
            r = await client.post(
                f"{api_url}/transfer/transport-request",
                json={
                    "sender_peer_id": effective_pid,
                    "requested_transport": requested_transport,
                },
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                502,
                f"Remote peer returned {exc.response.status_code}: {exc.response.text}",
            )
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Cannot reach peer {target_peer_id!r}: {exc}")


# ── Incoming QUIC connection management ───────────────────────────────────────

@router.get("/incoming", response_model=list[IncomingConnection])
async def list_incoming() -> list[IncomingConnection]:
    """Return pending/accepted/rejected incoming QUIC connections with cert info."""
    transport = get_transport()
    if not isinstance(transport, QUICTransport):
        return []
    return [IncomingConnection(**c) for c in transport.list_pending()]


@router.post("/incoming/{transfer_id}/accept")
async def accept_incoming(transfer_id: str) -> dict:
    """Approve an incoming QUIC connection — the buffered RS blocks will be decoded."""
    transport = get_transport()
    if not isinstance(transport, QUICTransport):
        raise HTTPException(400, "Not running QUIC transport")
    if transfer_id not in transport._pending_conns:
        raise HTTPException(404, "Incoming connection not found")
    transport.approve_connection(transfer_id)
    return {"ok": True}


@router.post("/incoming/{transfer_id}/reject")
async def reject_incoming(transfer_id: str) -> dict:
    """Reject an incoming QUIC connection — buffered packets are discarded."""
    transport = get_transport()
    if not isinstance(transport, QUICTransport):
        raise HTTPException(400, "Not running QUIC transport")
    if transfer_id not in transport._pending_conns:
        raise HTTPException(404, "Incoming connection not found")
    transport.reject_connection(transfer_id)
    return {"ok": True}
