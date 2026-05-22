import asyncio

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..config import get_settings
from .decoder import decode_transfer
from .encoder import encode_file
from .models import ReceiveRequest, SendRequest, TransferResult, TransferStatus
from .transport import udp

router = APIRouter()

# In-memory transfer registry.
# TODO: replace with Redis for multi-process / multi-replica deployments.
_transfers: dict[str, dict] = {}


@router.post("/send", response_model=TransferResult)
async def send_file(req: SendRequest) -> TransferResult:
    settings = get_settings()

    # Fetch file from local fileserver
    async with httpx.AsyncClient(timeout=30) as client:
        meta_r = await client.get(f"{settings.FILESERVER_URL}/files/{req.file_id}/meta")
        if meta_r.status_code == 404:
            raise HTTPException(404, "File not found in fileserver")
        meta = meta_r.json()

        bytes_r = await client.get(f"{settings.FILESERVER_URL}/files/{req.file_id}/bytes")
        bytes_r.raise_for_status()
        file_bytes = bytes_r.content

    packets, transfer_id, n, k, chunk_size = encode_file(file_bytes, req.redundancy_level)

    # Notify peer so it registers the transfer and prepares to collect UDP packets
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(
                f"{req.target_api_url}/transfer/receive",
                json={
                    "transfer_id": transfer_id,
                    "checksum": meta["sha256"],
                    "file_size": len(file_bytes),
                    "n": n,
                    "k": k,
                    "chunk_size": chunk_size,
                },
            )
            if r.status_code not in (200, 202):
                raise HTTPException(502, f"Peer rejected transfer: {r.text}")
        except httpx.RequestError as exc:
            raise HTTPException(502, f"Cannot reach peer at {req.target_api_url}: {exc}")

    # Send UDP packets (fire and forget — peer is already waiting)
    await udp.send(packets, req.target_udp_host, req.target_udp_port)

    # Poll peer for decode result (35 s window, 0.5 s interval)
    async with httpx.AsyncClient(timeout=5) as client:
        for _ in range(70):
            await asyncio.sleep(0.5)
            try:
                r = await client.get(f"{req.target_api_url}/transfer/{transfer_id}/status")
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") not in ("pending", None):
                        return TransferResult(**data)
            except httpx.RequestError:
                pass

    return TransferResult(
        transfer_id=transfer_id,
        status=TransferStatus.failed,
        reason="timeout_waiting_for_peer_result",
    )


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
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.post(
                    f"{settings.FILESERVER_URL}/files",
                    files={"file": ("received_transfer", result.file_bytes, "application/octet-stream")},
                )
                if r.status_code == 200:
                    file_id = r.json().get("file_id")
            except Exception:
                pass

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
