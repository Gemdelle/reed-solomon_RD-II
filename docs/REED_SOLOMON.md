# Reed-Solomon Implementation Spec

## Purpose

Reed-Solomon (RS) codes are used as Forward Error Correction (FEC) for UDP file transfers. Because UDP does not guarantee delivery or ordering, RS allows the receiver to reconstruct the original data even when a fraction of packets is lost, without retransmission.

---

## Algorithm Parameters

RS operates over GF(2^8) (Galois Field, 256 elements). Each symbol is one byte.

| Symbol | Meaning |
|--------|---------|
| `k` | Number of original data symbols per block |
| `n` | Total symbols after encoding (data + parity) |
| `n - k` | Parity symbols (redundancy) |
| `r` | Redundancy ratio: `(n - k) / n` |

**Error correction capacity (erasures model):**
- UDP loss = erasure (position known). RS can recover up to `n - k` erasures per block.
- This means: if `r = 0.30`, up to 30% of packets per block can be lost and the block is still recoverable.

**Recommended parameter bounds:**
- Minimum `k`: 4 (blocks too small lose efficiency)
- Maximum `n`: 255 (GF(2^8) limit)
- Recommended `n`: 16–64 (balance overhead vs latency)

---

## Redundancy Slider → RS Parameters

The user selects a redundancy ratio `r ∈ [0.05, 0.50]`.

Given a target `r` and a fixed `n` (default: 32):

```python
n = 32  # fixed block size
k = round(n * (1 - r))
k = max(4, min(k, n - 1))  # clamp
```

| r | n | k | parity | overhead |
|---|---|---|--------|----------|
| 0.05 | 32 | 30 | 2 | 6.7% |
| 0.10 | 32 | 29 | 3 | 10.3% |
| 0.25 | 32 | 24 | 8 | 33.3% |
| 0.50 | 32 | 16 | 16 | 100% |

The API accepts `redundancy_level: float` in range `[0.05, 0.50]`. The redundancy module derives `n, k` from this value before encoding.

---

## File Segmentation

Before encoding, the file is split into chunks. Each chunk becomes one RS block.

```
file bytes
    │
    ▼
┌──────────┬──────────┬──────────┬──────┐
│ chunk_0  │ chunk_1  │ chunk_2  │ ...  │   ← k bytes each
└──────────┴──────────┴──────────┴──────┘
    │
    ▼  RS encode (per chunk)
┌──────────────────────────────────┐
│ chunk_i (k bytes) + parity (n-k) │   ← n bytes total per block
└──────────────────────────────────┘
```

**Chunk size**: `CHUNK_SIZE = k` bytes (fills exactly one RS codeword).

**Padding**: The last chunk is zero-padded to `k` bytes. The original file size is included in the transfer header so the receiver can strip padding.

---

## UDP Packet Structure

Each RS block is sent as one UDP datagram.

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
├───────────────────────────────────────────────────────────────────┤
│                        transfer_id (16 bytes UUID)                 │
├───────────────────────────────────────────────────────────────────┤
│              block_index (4 bytes)  │  total_blocks (4 bytes)      │
├───────────────────────────────────────────────────────────────────┤
│        n (1 byte)  │  k (1 byte)  │  flags (1 byte)  │  pad (1)   │
├───────────────────────────────────────────────────────────────────┤
│                  file_size_bytes (8 bytes, in block_index=0)       │
├───────────────────────────────────────────────────────────────────┤
│                      RS block payload (n bytes)                    │
└───────────────────────────────────────────────────────────────────┘
```

**Flags byte:**
- bit 0: `IS_LAST` — set on the final block
- bit 1: `HAS_PADDING` — set if last chunk was zero-padded
- bits 2–7: reserved

**Header size**: 30 bytes  
**Max payload**: 65507 − 30 = 65477 bytes (UDP MTU limit)  
**Recommended payload** (`n`): 32–256 bytes to avoid fragmentation on standard links

---

## Encoding Flow

```python
def encode_file(file_bytes: bytes, r: float) -> list[bytes]:
    n, k = derive_params(r)
    rs = ReedSolomonCodec(n, k)

    chunks = chunk_file(file_bytes, k)          # split into k-byte chunks
    transfer_id = uuid4().bytes
    packets = []

    for i, chunk in enumerate(chunks):
        encoded_block = rs.encode(chunk)        # k → n bytes
        packet = build_packet(
            transfer_id, block_index=i,
            total_blocks=len(chunks),
            n=n, k=k, payload=encoded_block,
            file_size=len(file_bytes) if i == 0 else None
        )
        packets.append(packet)

    return packets
```

---

## Decoding Flow

```python
def decode_transfer(received_packets: list[bytes], checksum: str) -> DecodeResult:
    meta = parse_header(received_packets[0])
    n, k, total_blocks, file_size = meta.n, meta.k, meta.total_blocks, meta.file_size
    rs = ReedSolomonCodec(n, k)

    blocks = {p.block_index: p.payload for p in received_packets}
    recovered_errors = 0

    chunks = []
    for i in range(total_blocks):
        if i in blocks:
            chunk = rs.decode(blocks[i])        # may raise if unrecoverable
            if blocks[i] was incomplete:
                recovered_errors += 1
        else:
            chunk = rs.decode_with_erasure(available_blocks, i)  # erasure decode
            recovered_errors += 1
        chunks.append(chunk)

    file_bytes = b"".join(chunks)[:file_size]  # strip padding

    actual_checksum = sha256(file_bytes).hexdigest()
    if actual_checksum != checksum:
        return DecodeResult(status="failed", reason="checksum_mismatch")

    status = "degraded" if recovered_errors > 0 else "ok"
    return DecodeResult(status=status, file_bytes=file_bytes, recovered_blocks=recovered_errors)
```

---

## Python Library

Use [`reedsolo`](https://github.com/tomerfiliba/reedsolomon) (pure Python, well-maintained):

```
pip install reedsolo
```

```python
from reedsolo import RSCodec

rs = RSCodec(nsym=n - k)          # nsym = number of parity symbols
encoded = rs.encode(bytearray(data))
decoded, _, _ = rs.decode(bytearray(received))
```

For erasure decoding (known lost positions), use `rs.decode(..., erase_pos=[...])`.

---

## Checksum

SHA-256 of the **original** file bytes (before encoding, after padding removal).

- Stored in `fileserver` alongside the file at upload time
- Included in the transfer initiation response (not in UDP packets — fetched separately by receiver from its own API after transfer completes)
- Used to determine `ok` vs `degraded` vs `failed`

---

## Error States

| Condition | Status |
|-----------|--------|
| All blocks received, checksum matches | `ok` |
| Some blocks lost, RS recovered all, checksum matches | `degraded` |
| Lost blocks exceed RS capacity (`> n-k` per block) | `failed` — unrecoverable |
| RS recovered but checksum mismatch | `failed` — data corruption |
| Timeout: not all blocks arrived within window | `failed` — timeout |

---

## Transfer Timeout

The receiver waits up to `TRANSFER_TIMEOUT_S = 30` seconds for all blocks. If the timeout expires, blocks received up to that point are used for a best-effort decode. If reconstruction fails, status is `failed`.

The sender must complete transmission within `SEND_TIMEOUT_S = 25` seconds (gives receiver 5s buffer).
