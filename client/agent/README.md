# RS Transfer Agent

Per-peer background process that handles local file storage, UDP packet I/O, and Reed-Solomon FEC encoding/decoding. Exposes a local HTTP API consumed by the Electron shell and the React UI.

## Stack

| Layer | Tech |
|---|---|
| Runtime | Python 3.12, FastAPI, uvicorn |
| FEC | reedsolo 1.7 |
| Transport | asyncio UDP (custom transport) |
| HTTP client | httpx (server registration + peer lookup) |
| Packaging | PyInstaller (`rs-agent` binary for distribution) |

## Quick start

```bash
cd client/agent

# Copy and fill the env
cp ../../.env.example .env   # edit PEER_ID, SERVER_URL, etc.

uv sync
uv run uvicorn main:app --reload --app-dir src --host 127.0.0.1 --port 8000
```

The agent registers itself with the server on startup and begins sending heartbeats every 15 s.

## API surface

```
GET  /health                  liveness probe
GET  /files/                  list stored files
POST /files/                  upload a file (multipart/form-data, field "file")
DELETE /files/{file_id}       delete a stored file

GET  /peers/                  peer list (proxy from server)

POST /transfer/send           encode + send a file to a peer via UDP
POST /transfer/receive        called by the sending peer to prepare reception
GET  /transfer/{id}/status    poll transfer result
GET  /transfer/               list all transfers this session
```

Interactive docs at `http://127.0.0.1:8000/docs` when running.

## Source layout

```
src/
├── main.py              app factory, lifespan (UDP start, register, heartbeat, RTT probe)
├── config.py            Settings (pydantic-settings, auto-detects local IP)
├── server_client.py     HTTP client: register, heartbeat, peer lookup, metrics report
│
├── files/
│   └── router.py        upload / list / delete endpoints
│
├── peers/
│   └── router.py        proxy list from server (GET /peers)
│
├── rs/
│   ├── encoder.py       encode_file() → packets list (n=32 blocks, k=data, n-k=parity)
│   ├── decoder.py       decode_transfer() → file bytes + TransferStatus
│   ├── models.py        TransferStatus enum, DecodeResult
│   └── transport.py     UDPTransport singleton (listener + per-transfer buffers)
│
├── storage/
│   ├── store.py         FileStorage: save / get_bytes / get_meta / list / delete
│   └── models.py        FileMetadata
│
├── transfers/
│   ├── router.py        /send, /receive, /status, /list
│   └── models.py        SendRequest, ReceiveRequest, TransferResult
│
└── metrics/
    └── probe.py         background RTT probe loop (HTTP /health pings every 60 s)
```

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `SERVER_URL` | `http://localhost:8080` | Central server address |
| `PEER_ID` | `default-peer` | Unique name for this peer |
| `AGENT_API_URL` | auto-detected | Public URL other peers use to reach this agent |
| `AGENT_PORT` | `8000` | Port used when auto-detecting `AGENT_API_URL` |
| `UDP_HOST` | `0.0.0.0` | Listen address for UDP packets |
| `UDP_PORT` | `9001` | UDP listen port |
| `STORAGE_PATH` | `./data` | Directory for stored files |
| `NETWORK_HINT` | `auto` | `lan` / `wifi` / `cellular` / `satellite` |
| `AGENT_SERVICE_TOKEN` | `` | Bearer token for server auth (service account mode) |
| `INVITE_TOKEN` | `` | Single-use invite JWT for first registration |

`AGENT_API_URL` is auto-resolved on startup: the agent opens a UDP socket toward `8.8.8.8:80` and reads the source IP — no DNS lookup, no network traffic.

## FEC parameters

```python
n = 32           # total blocks per transfer
k = max(4, min(round(32 * (1 - redundancy_level)), 31))  # data blocks
nsym = n - k     # parity blocks = erasures correctable
```

Example: `redundancy_level=0.25` → `k=24`, `nsym=8` → tolerates up to 8 lost blocks out of 32.

When `redundancy_level=None` is sent by the UI (adaptive mode), the agent calls `GET /metrics/recommendation/{peer_id}` on the server to resolve it before encoding.

## Transfer flow

```
Sender                           Receiver
  │                                  │
  ├─ encode_file() → n packets       │
  ├─ POST /transfer/receive ────────►│  (signals receiver to open buffer)
  ├─ UDP send (n packets) ──────────►│
  │                                  ├─ collect packets (asyncio wait)
  │                                  ├─ decode_transfer() → file bytes
  ├─ poll GET /transfer/{id}/status ─┤
  ◄─ {status: ok|degraded|failed} ───┤
  │                                  │
  └─ report_metrics() → server       │
```

## Tests

```bash
uv run pytest -v
```

39 tests covering RS codec (encode/decode/erasure/unrecoverable), file storage, and HTTP endpoints.
