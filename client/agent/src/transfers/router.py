import asyncio
import time

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from config import get_settings
from rs.decoder import decode_transfer
from rs.encoder import encode_file
from rs.models import TransferStatus
from rs.transport import udp
from server_client import server_client
from storage.store import FileStorage
from transfers.models import ReceiveRequest, SendRequest, TransferResult

router = APIRouter()

_transfers: dict[str, dict] = {}


@router.post("/send", response_model=TransferResult)
async def send_file(req: SendRequest) -> TransferResult:
    settings = get_settings()
    storage = FileStorage(settings.STORAGE_PATH)

    meta = storage.get_meta(req.file_id)
    if not meta:
        raise HTTPException(404, "File not found")
    file_bytes = storage.get_bytes(req.file_id)
    if file_bytes is None:
        raise HTTPException(404, "File bytes not found")

    redundancy_level = req.redundancy_level
    if redundancy_level is None:
        redundancy_level = await server_client.get_recommendation(settings.PEER_ID)

    try:
        peer = await server_client.get_peer(req.target_peer_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    target_api_url = peer["api_url"]
    target_udp_host = peer["udp_host"]
    target_udp_port = peer["udp_port"]

    packets, transfer_id, n, k, chunk_size = encode_file(file_bytes, redundancy_level)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                f"{target_api_url}/transfer/receive",
                json={
                    "transfer_id": transfer_id,
                    "checksum": meta["sha256"],
                    "file_size": len(file_bytes),
                    "n": n, "k": k, "chunk_size": chunk_size,
                },
            )
            if r.status_code not in (200, 202):
                raise HTTPException(502, f"Peer rejected transfer: {r.text}")
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Cannot reach peer: {exc}")

    t_send = time.monotonic()
    await udp.send(packets, target_udp_host, target_udp_port)

    result = TransferResult(
        transfer_id=transfer_id,
        status=TransferStatus.failed,
        reason="timeout_waiting_for_peer_result",
    )
    async with httpx.AsyncClient(timeout=5) as client:
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

    return result


@router.post("/receive", status_code=202)
async def receive_transfer(req: ReceiveRequest, background_tasks: BackgroundTasks) -> dict:
    _transfers[req.transfer_id] = {"status": "pending"}
    background_tasks.add_task(_process_incoming, req)
    return {"transfer_id": req.transfer_id, "status": "pending"}


async def _process_incoming(req: ReceiveRequest) -> None:
    settings = get_settings()
    packets = await udp.collect(req.transfer_id, timeout=req.timeout)
    result = decode_transfer(packets, req.checksum)

    file_id = None
    if result.status != TransferStatus.failed and result.file_bytes:
        storage = FileStorage(settings.STORAGE_PATH)
        saved = storage.save(result.file_bytes, f"transfer_{req.transfer_id}")
        file_id = saved["file_id"]

    _transfers[req.transfer_id] = {
        "transfer_id": req.transfer_id,
        "status": result.status,
        "recovered_blocks": result.recovered_blocks,
        "total_blocks": result.total_blocks,
        "file_id": file_id,
        "reason": result.reason,
    }


@router.get("/{transfer_id}/status", response_model=TransferResult)
async def get_status(transfer_id: str) -> TransferResult:
    if transfer_id not in _transfers:
        raise HTTPException(404, "Transfer not found")
    return TransferResult(**_transfers[transfer_id])


@router.get("/", response_model=list[TransferResult])
async def list_transfers() -> list[TransferResult]:
    return [TransferResult(**v) for v in _transfers.values()]
