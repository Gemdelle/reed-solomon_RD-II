import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    from config import get_settings
    get_settings.cache_clear()
    from transfers.router import _transfers, router
    _transfers.clear()
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/transfer")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    get_settings.cache_clear()


_RECEIVE_PAYLOAD = {
    "transfer_id": "test-tid-001",
    "checksum": "a" * 64,
    "file_size": 100,
    "n": 32,
    "k": 24,
    "chunk_size": 8,
    "timeout": 0.05,   # very short so background task completes fast
}


async def test_receive_returns_202_pending(client):
    r = await client.post("/transfer/receive", json=_RECEIVE_PAYLOAD)
    assert r.status_code == 202
    body = r.json()
    assert body["transfer_id"] == "test-tid-001"
    assert body["status"] == "pending"


async def test_status_unknown_transfer_is_404(client):
    r = await client.get("/transfer/ghost-transfer/status")
    assert r.status_code == 404


async def test_list_transfers_empty(client):
    r = await client.get("/transfer/")
    assert r.status_code == 200
    assert r.json() == []


async def test_status_returns_stored_state(client):
    from transfers.router import _transfers
    tid = "manual-tid"
    _transfers[tid] = {
        "transfer_id": tid,
        "status": "degraded",
        "recovered_blocks": 3,
        "total_blocks": 24,
        "file_id": "some-file-id",
        "reason": None,
    }
    r = await client.get(f"/transfer/{tid}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["recovered_blocks"] == 3


async def test_list_returns_all_transfers(client):
    from transfers.router import _transfers
    _transfers["t1"] = {"transfer_id": "t1", "status": "ok", "recovered_blocks": 0,
                        "total_blocks": 24, "file_id": None, "reason": None}
    _transfers["t2"] = {"transfer_id": "t2", "status": "failed", "recovered_blocks": 0,
                        "total_blocks": 24, "file_id": None, "reason": "timeout"}
    r = await client.get("/transfer/")
    assert r.status_code == 200
    ids = {t["transfer_id"] for t in r.json()}
    assert {"t1", "t2"}.issubset(ids)
