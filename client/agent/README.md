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

### Transfer and file endpoints

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

### Auth endpoints

| Endpoint | Description |
|---|---|
| `GET /auth/callback?code=&state=` | Keycloak redirect target for the OIDC loopback flow. Stores `{code, state}` in memory for the UI to pick up via `/auth/poll`. Returns an HTML success page that auto-closes after 3 seconds so the system browser tab does not linger. |
| `GET /auth/poll` | Returns `{code, state}` once and immediately clears it from memory. The UI polls this endpoint at 1-second intervals after opening the Keycloak authorization URL. Returns `null` if no code has arrived yet. |
| `POST /auth/token` | Accepts `{"token": "<jwt>"}`. Stores the JWT in `token_store` and immediately re-registers the peer with the server using the JWT as a `Bearer` token. The server in OIDC mode assigns `peer_id = JWT sub` — this may differ from the `PEER_ID` env var. The assigned ID is stored in `token_store.peer_id` and used by the heartbeat loop. |

Interactive docs at `http://127.0.0.1:8000/docs` when running.

## Source layout

```
src/
├── main.py              app factory, lifespan (UDP start, register, heartbeat, RTT probe)
├── config.py            Settings (pydantic-settings, auto-detects local IP)
├── server_client.py     HTTP client: register, heartbeat, peer lookup, metrics report
├── token_store.py       in-memory JWT + peer_id store (set by UI after OIDC login)
│
├── auth/
│   └── router.py        /auth/callback, /auth/poll, /auth/token endpoints
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
| `PEER_ID` | `default-peer` | Fallback peer ID (overridden by server in OIDC mode) |
| `AGENT_API_URL` | auto-detected | Public URL other peers use to reach this agent |
| `AGENT_PORT` | `8000` | Port used when auto-detecting `AGENT_API_URL` |
| `UDP_HOST` | `0.0.0.0` | Listen address for UDP packets |
| `UDP_PORT` | `9001` | UDP listen port |
| `STORAGE_PATH` | `~/.local/share/rockdove` | Directory for stored files. If `$XDG_DATA_HOME` is set, resolves to `$XDG_DATA_HOME/rockdove`. |
| `NETWORK_HINT` | `auto` | `lan` / `wifi` / `cellular` / `satellite` |
| `AGENT_SERVICE_TOKEN` | — | Bearer token for server auth (service account mode) |
| `INVITE_TOKEN` | — | Single-use invite JWT included in the registration body |

`AGENT_API_URL` is auto-resolved on startup: the agent opens a UDP socket toward `8.8.8.8:80` and reads the source IP — no DNS lookup, no network traffic.

## Auth behavior

The agent selects credentials for server calls using the following priority:

1. **`AGENT_SERVICE_TOKEN` env var is set** — used as the `Authorization: Bearer` header for all server calls. This is the service account mode for headless/IoT agents deployed with a long-lived token.
2. **JWT pushed via `POST /auth/token`** — after the user completes OIDC login in the UI, the UI pushes the access token to the agent. `server_client.py` reads it via `token_store.get_token()` when `AGENT_SERVICE_TOKEN` is absent.
3. **`INVITE_TOKEN` env var is set** — included in the registration request body as a single-use invite. Consumed by the server on first registration; not used for subsequent heartbeats.
4. **None of the above** — registration will fail with 401 in OIDC mode. The agent starts but cannot communicate with the server until a token is provided.

## Registration flow

**On startup:** the agent calls `POST /peers/register` using whatever credentials are available at that moment. In interactive OIDC mode this first attempt typically fails (no JWT yet) — the UI completes login and pushes the token afterward.

**On `POST /auth/token`:** the agent re-registers immediately with the fresh JWT. This is the authoritative registration in OIDC mode.

**Server behavior:** in OIDC mode the server ignores the `peer_id` field in the registration body and instead assigns `peer_id = JWT sub`. The assigned ID is returned in the response and stored in `token_store`.

**Heartbeat loop:** uses `token_store.get_peer_id()` as the peer ID, falling back to the `PEER_ID` env var if the token store is empty. This ensures the heartbeat always uses the server-assigned ID, not a locally configured one that may not match.

## token_store module

`src/token_store.py` holds two module-level singletons that allow the JWT and peer ID to be updated at runtime without restarting the process:

| Symbol | Type | Purpose |
|---|---|---|
| `_token` | `str \| None` | The OIDC access token pushed by the UI after login |
| `_peer_id` | `str \| None` | The peer ID assigned by the server after registration |

**Functions:**

```python
get_token() -> str | None      # read by server_client.py for Authorization headers
set_token(token: str) -> None  # called by POST /auth/token handler

get_peer_id() -> str | None    # read by heartbeat loop
set_peer_id(pid: str) -> None  # called after successful registration response
```

`server_client.py` uses `token_store.get_token()` as a fallback when `AGENT_SERVICE_TOKEN` is not set. This means the agent can be started with no env-var credentials and acquire them dynamically once the user logs in.

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
