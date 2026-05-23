"""
RS encoder/decoder tests.

Mandatory per RULES.md: roundtrip, erasure recovery, checksum mismatch.
"""
import hashlib
import random

import pytest

from rs.decoder import decode_transfer
from rs.encoder import derive_rs_params, encode_file
from rs.models import TransferStatus


def drop_packets(packets: list, loss_rate: float) -> list:
    return [p for p in packets if random.random() > loss_rate]


# ── derive_rs_params ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("level,expected_k", [
    (0.05, 30),   # round(32 * 0.95) = 30
    (0.25, 24),   # round(32 * 0.75) = 24
    (0.50, 16),   # round(32 * 0.50) = 16
])
def test_derive_rs_params(level, expected_k):
    n, k = derive_rs_params(level)
    assert n == 32
    assert k == expected_k
    assert 4 <= k < n


def test_derive_rs_params_high_redundancy_clamps_k():
    n, k = derive_rs_params(0.99)
    assert k >= 4


# ── Clean roundtrip (no loss) ─────────────────────────────────────────────────

def test_roundtrip_no_loss():
    data = b"hello rockdove " * 100
    checksum = hashlib.sha256(data).hexdigest()
    packets, tid, n, k, _ = encode_file(data, 0.25)

    result = decode_transfer(packets, checksum)
    assert result.status == TransferStatus.ok
    assert result.file_bytes == data
    assert result.recovered_blocks == 0
    assert result.total_blocks == k


def test_single_byte_file():
    data = b"\xff"
    checksum = hashlib.sha256(data).hexdigest()
    packets, _, _, _, _ = encode_file(data, 0.25)
    result = decode_transfer(packets, checksum)
    assert result.file_bytes == data


def test_large_file():
    data = bytes(range(256)) * 400   # ~100 KB
    checksum = hashlib.sha256(data).hexdigest()
    packets, _, n, k, _ = encode_file(data, 0.10)
    result = decode_transfer(packets, checksum)
    assert result.status == TransferStatus.ok
    assert result.file_bytes == data


# ── Erasure recovery (within RS capacity) ────────────────────────────────────
# n=32, k=24, nsym=8 for redundancy_level=0.25

def test_roundtrip_with_erasures():
    data = b"erasure recovery test " * 200
    checksum = hashlib.sha256(data).hexdigest()
    packets, _, n, k, _ = encode_file(data, 0.25)
    # Drop last 2 data blocks (indices 22,23); keep all 8 parity blocks.
    # block_map = {0..21, 24..31} → 30 entries ≥ k=24
    # missing data indices = [22, 23] → recovered = 2
    survived = packets[:22] + packets[24:]
    result = decode_transfer(survived, checksum)
    assert result.status == TransferStatus.degraded
    assert result.file_bytes == data
    assert result.recovered_blocks == 2


def test_roundtrip_recovers_lost_data_blocks():
    data = b"block recovery " * 300
    checksum = hashlib.sha256(data).hexdigest()
    packets, _, n, k, _ = encode_file(data, 0.25)
    # Drop first 3 data blocks (indices 0,1,2); keep data[3:24] + all parity.
    # block_map = {3..23, 24..31} → 29 entries ≥ k=24
    # missing data indices = [0, 1, 2] → recovered = 3
    survived = packets[3:24] + packets[24:]
    result = decode_transfer(survived, checksum)
    assert result.status == TransferStatus.degraded
    assert result.file_bytes == data
    assert result.recovered_blocks == 3


# ── Unrecoverable loss ────────────────────────────────────────────────────────

def test_roundtrip_unrecoverable_loss():
    data = b"too much loss " * 100
    checksum = hashlib.sha256(data).hexdigest()
    packets, _, n, k, _ = encode_file(data, 0.25)
    # k-1 = 23 < k=24 → decoder returns insufficient_packets
    survived = packets[: k - 1]
    result = decode_transfer(survived, checksum)
    assert result.status == TransferStatus.failed


# ── Checksum mismatch ─────────────────────────────────────────────────────────

def test_checksum_mismatch():
    data = b"original content"
    packets, _, _, _, _ = encode_file(data, 0.25)
    result = decode_transfer(packets, "a" * 64)
    assert result.status == TransferStatus.failed
    assert result.reason == "checksum_mismatch"


def test_no_packets():
    result = decode_transfer([], "abc")
    assert result.status == TransferStatus.failed


# ── drop_packets helper ───────────────────────────────────────────────────────

def test_drop_packets_zero_loss():
    pkts = list(range(100))
    assert drop_packets(pkts, 0.0) == pkts


def test_drop_packets_total_loss():
    pkts = list(range(100))
    assert drop_packets(pkts, 1.0) == []


def test_drop_packets_partial():
    random.seed(42)
    pkts = list(range(1000))
    survived = drop_packets(pkts, 0.3)
    assert 600 < len(survived) < 900
    assert all(p in pkts for p in survived)
