"""
Async SQLite persistence for transfer history.

Schema: one row per transfer (sent or received). Written at completion time;
never updated afterwards. The in-memory _transfers dict in router.py remains
the source of truth for active/pending status polling.
"""
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

_CONN: aiosqlite.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transfers (
    id               TEXT PRIMARY KEY,
    ts               TEXT NOT NULL,
    direction        TEXT NOT NULL,
    peer_id          TEXT,
    filename         TEXT,
    bytes            INTEGER,
    status           TEXT NOT NULL,
    redundancy       REAL,
    recovered_blocks INTEGER NOT NULL DEFAULT 0,
    total_blocks     INTEGER NOT NULL DEFAULT 0,
    quality          TEXT,
    profile_name     TEXT
)
"""


async def init_db(storage_path: str) -> None:
    global _CONN
    path = Path(storage_path) / "transfers.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    _CONN = await aiosqlite.connect(str(path))
    _CONN.row_factory = aiosqlite.Row
    await _CONN.execute(_SCHEMA)
    await _CONN.commit()


async def close_db() -> None:
    global _CONN
    if _CONN is not None:
        await _CONN.close()
        _CONN = None


def _db() -> aiosqlite.Connection:
    if _CONN is None:
        raise RuntimeError("DB not initialized")
    return _CONN


async def insert_transfer(
    transfer_id: str,
    direction: str,
    peer_id: str | None,
    filename: str | None,
    bytes_: int | None,
    status: str,
    redundancy: float | None = None,
    recovered_blocks: int = 0,
    total_blocks: int = 0,
    quality: str | None = None,
    profile_name: str | None = None,
) -> None:
    await _db().execute(
        """
        INSERT OR REPLACE INTO transfers
            (id, ts, direction, peer_id, filename, bytes, status,
             redundancy, recovered_blocks, total_blocks, quality, profile_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transfer_id,
            datetime.now(timezone.utc).isoformat(),
            direction,
            peer_id,
            filename,
            bytes_,
            status,
            redundancy,
            recovered_blocks,
            total_blocks,
            quality,
            profile_name,
        ),
    )
    await _db().commit()


async def list_history(limit: int = 50) -> list[dict]:
    async with _db().execute(
        "SELECT * FROM transfers ORDER BY ts DESC LIMIT ?", (limit,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]
