from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, field_validator


class TransferStatus(str, Enum):
    ok = "ok"
    degraded = "degraded"
    failed = "failed"
    pending = "pending"


class SendRequest(BaseModel):
    file_id: str
    target_api_url: str       # http://192.168.1.10:8000
    target_udp_host: str
    target_udp_port: int = 9001
    redundancy_level: float = 0.25

    @field_validator("redundancy_level")
    @classmethod
    def _check_range(cls, v: float) -> float:
        if not 0.05 <= v <= 0.50:
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


class TransferResult(BaseModel):
    transfer_id: str
    status: TransferStatus
    recovered_blocks: int = 0
    total_blocks: int = 0
    file_id: str | None = None
    reason: str | None = None


@dataclass
class DecodeResult:
    transfer_id: str
    status: TransferStatus
    file_bytes: bytes | None = None
    recovered_blocks: int = 0
    total_blocks: int = 0
    reason: str | None = None
