# AI Agent Guidelines

Read this before writing any code. Full architecture in [ARCHITECTURE.md](./ARCHITECTURE.md). Rules in [RULES.md](./RULES.md).

---

## Project Context

P2P file transfer system for a university data networks course. Core algorithm: **Reed-Solomon FEC over UDP**. The system is split into:

- **`server/`** — control plane (cloud): peer registry, network metrics, adaptive redundancy recommendation
- **`client/agent/`** — data plane (per peer): RS encode/decode, UDP transport, local storage, transfer orchestration
- **`client/electron/`** — desktop shell (spawns agent, loads UI)
- **`client/ui/`** — React SPA

**The server never touches file data.** Transfers are always direct machine-to-machine over UDP.

---

## Service Ownership Map

| Area | Location |
|------|----------|
| RS encode | `client/agent/src/rs/encoder.py` |
| RS decode | `client/agent/src/rs/decoder.py` |
| UDP transport | `client/agent/src/rs/transport.py` |
| RS + API models | `client/agent/src/rs/models.py`, `client/agent/src/transfers/models.py` |
| Transfer routes | `client/agent/src/transfers/router.py` |
| File routes | `client/agent/src/files/router.py` |
| Local storage | `client/agent/src/storage/store.py` |
| Server HTTP client | `client/agent/src/server_client.py` |
| Peer registry | `server/src/peers/router.py` |
| Metrics + recommendation | `server/src/metrics/` |
| Electron shell | `client/electron/main.ts` |
| Frontend | `client/ui/src/` |

---

## Key Invariants

1. **UDP sockets only in `rs/transport.py`** — never open sockets elsewhere.
2. **RS params derived from `redundancy_level` float** — never accept raw `n`/`k` from clients.
3. **Checksum always verified** — `rs/decoder.py` must verify SHA-256 before returning any result.
4. **File data never touches the server** — the server only stores `{peer_id, api_url, udp_host, udp_port}`.
5. **`server_client.py` is the only place the agent calls the server** — don't add server HTTP calls anywhere else.
6. **Storage is embedded** — no separate fileserver service. `storage/store.py` writes to `STORAGE_PATH`.

---

## RS Parameter Derivation

```python
N_FIXED = 32

def derive_rs_params(redundancy_level: float) -> tuple[int, int]:
    n = N_FIXED
    k = round(n * (1 - redundancy_level))
    return n, max(4, min(k, n - 1))
```

---

## Transfer Status Logic

```
RS decode raises exception → status = "failed", reason = "unrecoverable_loss"
RS decode ok, checksum mismatch → status = "failed", reason = "checksum_mismatch"
RS decode ok, some blocks reconstructed, checksum ok → status = "degraded"
RS decode ok, no reconstruction needed, checksum ok → status = "ok"
```

---

## SendRequest — adaptive redundancy

`redundancy_level` in `SendRequest` is optional (`float | None`). When `None`, the agent fetches the recommended level from `server_client.get_recommendation(peer_id)`. The server's recommendation is based on averaged RTT/jitter/loss from recent metric reports.

---

## Agent Startup Sequence

1. UDP listener starts on `UDP_HOST:UDP_PORT`
2. Agent registers with server: `POST /peers/register`
3. Heartbeat task starts (every 15s): `POST /peers/{peer_id}/heartbeat`
4. If server is unreachable at startup, agent starts anyway — deferred re-registration happens on next heartbeat.

---

## API Endpoint Patterns

```
# Agent
GET    /files              → list local files
POST   /files              → upload file to local storage
GET    /files/{id}/meta    → file metadata
GET    /files/{id}         → download file
DELETE /files/{id}         → delete file

POST   /transfer/send      → initiate outgoing transfer (resolves peer addr from server)
POST   /transfer/receive   → called by sender to prepare incoming transfer
GET    /transfer/{id}/status → get transfer status
GET    /transfer           → list transfer history

# Server
POST   /peers/register
POST   /peers/{id}/heartbeat
GET    /peers
GET    /peers/{id}
POST   /metrics/report
GET    /metrics/recommendation/{peer_id}
```

---

## What You Must Not Do

- Do not open UDP sockets outside `rs/transport.py`
- Do not compute checksums at decode time — use the stored value from storage
- Do not accept `n` or `k` from HTTP request bodies — derive from `redundancy_level`
- Do not add HTTP calls to the server outside `server_client.py`
- Do not commit `.env` files
- Do not mock `RSCodec` in transfer integration tests
