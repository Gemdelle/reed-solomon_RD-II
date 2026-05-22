"""
Reed-Solomon decoder for UDP file transfer.

Receives a list of raw UDP packets (may be incomplete due to packet loss),
reconstructs the original file using columnar erasure decoding, and verifies
integrity via SHA-256.
"""
import struct
from hashlib import sha256

from reedsolo import RSCodec, ReedSolomonError

from .encoder import HEADER_FMT, HEADER_SIZE
from .models import DecodeResult, TransferStatus


def decode_transfer(
    received_packets: list[bytes],
    expected_checksum: str,
) -> DecodeResult:
    if not received_packets:
        return DecodeResult(transfer_id="", status=TransferStatus.failed, reason="no_packets")

    hdr = struct.unpack(HEADER_FMT, received_packets[0][:HEADER_SIZE])
    tid_bytes, _, _, n, k, _, _, file_size = hdr
    transfer_id = tid_bytes.hex()
    nsym = n - k
    rs = RSCodec(nsym)

    block_map: dict[int, bytes] = {}
    for pkt in received_packets:
        h = struct.unpack(HEADER_FMT, pkt[:HEADER_SIZE])
        block_map[h[1]] = pkt[HEADER_SIZE:]

    if len(block_map) < k:
        return DecodeResult(
            transfer_id=transfer_id,
            status=TransferStatus.failed,
            reason=f"insufficient_packets: received {len(block_map)}/{n}, need {k}",
        )

    chunk_size = len(next(iter(block_map.values())))
    missing = [i for i in range(n) if i not in block_map]
    recovered = sum(1 for i in missing if i < k)  # lost data chunks that RS rebuilt

    data_chunks = [bytearray(chunk_size) for _ in range(k)]

    for j in range(chunk_size):
        # Build the full n-byte codeword for column j (0 where packet is missing)
        codeword = bytearray(n)
        for i, payload in block_map.items():
            codeword[i] = payload[j]

        try:
            decoded, _, _ = rs.decode(codeword, erase_pos=missing)
            for i in range(k):
                data_chunks[i][j] = decoded[i]
        except (ReedSolomonError, Exception):
            return DecodeResult(
                transfer_id=transfer_id,
                status=TransferStatus.failed,
                reason="unrecoverable_loss",
            )

    file_bytes = b"".join(bytes(c) for c in data_chunks)[:file_size]

    if sha256(file_bytes).hexdigest() != expected_checksum:
        return DecodeResult(
            transfer_id=transfer_id,
            status=TransferStatus.failed,
            reason="checksum_mismatch",
        )

    return DecodeResult(
        transfer_id=transfer_id,
        status=TransferStatus.degraded if recovered > 0 else TransferStatus.ok,
        file_bytes=file_bytes,
        recovered_blocks=recovered,
        total_blocks=k,
    )
