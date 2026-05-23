from typing import Literal

from pydantic import BaseModel, field_validator

from rs.models import TransferStatus


class HistoryEntry(BaseModel):
    id: str
    ts: str
    direction: str          # "sent" | "received"
    peer_id: str | None = None
    filename: str | None = None
    bytes: int | None = None
    status: str
    redundancy: float | None = None
    recovered_blocks: int = 0
    total_blocks: int = 0
    quality: str | None = None
    profile_name: str | None = None


class SendRequest(BaseModel):
    file_id: str
    target_peer_id: str
    redundancy_level: float | None = None  # None → server recommendation

    @field_validator("redundancy_level")
    @classmethod
    def _check_range(cls, v: float | None) -> float | None:
        if v is not None and not 0.05 <= v <= 0.50:
            raise ValueError("redundancy_level must be between 0.05 and 0.50")
        return v


class ReceiveRequest(BaseModel):
    transfer_id: str
    checksum: str
    file_size: int
    n: int
    k: int
    chunk_size: int
    timeout: float = 30.0


class IncomingConnection(BaseModel):
    transfer_id: str
    peer_id: str
    cert_cn: str
    cert_fingerprint: str
    arrived_at: str
    status: Literal["pending", "accepted", "rejected"]


class TransferResult(BaseModel):
    transfer_id: str
    status: TransferStatus
    recovered_blocks: int = 0
    total_blocks: int = 0
    file_id: str | None = None
    reason: str | None = None
    effective_redundancy: float | None = None
    quality: str | None = None
    profile_name: str | None = None
