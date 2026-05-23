# Architecture

## Overview

P2P file transfer system with Reed-Solomon forward error correction over UDP. Designed for reliable transfer over unreliable connections, with organization-based isolation and adaptive redundancy driven by real-time network telemetry.

**Primary use cases:**
- Org members transferring files peer-to-peer directly between machines
- Edge device ingestion over unstable links (cellular, satellite)
- IoT headless receivers that bootstrap via a known peer token

---

## Deployment Model

The system is split into two independent planes:

```
CONTROL PLANE (one instance, cloud/VM)           DATA PLANE (one per peer machine)
─────────────────────────────────────            ──────────────────────────────────
server/                                          client/agent/
  ├── Peer registry                                ├── RS encoder / decoder
  ├── Network metrics collector                    ├── UDP transport  (TRANSPORT_MODE=udp)
  └── Redundancy recommendation engine             └── QUIC transport (TRANSPORT_MODE=quic)
                                                   ├── Local file storage
                                                   └── Transfer orchestration
```

**The server never sees file data.** It only answers:
- "Who is peer B and what is their address?"
- "What redundancy level should I use given my recent network conditions?"

**The transfer is always machine-to-machine over UDP.** The server is not in the data path.

**Analogy:** Like Tailscale or Syncthing — a coordination server helps peers find each other, but the actual data flows directly.

---

## Component Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                           SERVER  (cloud)                           │
│                                                                     │
│  POST /peers/register   POST /peers/{id}/heartbeat                  │
│  GET  /peers            GET  /peers/{id}                            │
│  POST /metrics/report   GET  /metrics/recommendation/{peer_id}      │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────────────────────────┐   │
│  │  Peer Registry    │   │  Metrics / Recommender               │   │
│  │  (→ Keycloak)     │   │  quality score → redundancy level    │   │
│  └──────────────────┘   └──────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                │  HTTPS (control only)            ▲ metrics reports
                ▼                                  │
┌────────────────────────────────────────────────────────────────────┐
│                     AGENT  (per peer machine)                       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Electron Shell  (desktop)  OR  headless Docker  (IoT/edge)  │   │
│  └───────────────────────────────┬─────────────────────────────┘   │
│                                  │ spawns / embeds                  │
│  ┌───────────────────────────────▼─────────────────────────────┐   │
│  │  Python Agent  ·  port 8000                                   │   │
│  │                                                               │   │
│  │  /files   →  storage/store.py  (local filesystem)            │   │
│  │  /transfer → rs/ (encode, decode, UDP transport)             │   │
│  └───────────────────────────────────────────────────────────── ┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  React UI  (Vite)  — loaded by Electron, or served locally   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                           │ UDP  (data path — direct, machine-to-machine)
                           ▼
                   [other peer's Agent]
```

---

## Services

### `server` — Control Plane

- **Runtime**: Python 3.12, FastAPI
- **Port**: 8080
- **Deploy**: single cloud instance shared by all org peers

#### `server/peers/` — Peer Registry

Stores `{peer_id → api_url, udp_host, udp_port, last_seen}`. Peers register on startup and send a heartbeat every 15s. Peers not seen within `HEARTBEAT_TTL_S` (default 30s) are considered offline.

#### `server/metrics/` — Telemetry + Adaptive Redundancy

Peers periodically report network metrics (RTT, jitter, packet loss). The server averages the last 10 samples and maps them to a recommended `redundancy_level`:

| Quality | Loss | RTT | Jitter | Recommended r |
|---------|------|-----|--------|---------------|
| Excellent | < 1% | < 50ms | < 5ms | 0.05 |
| Good | < 5% | < 150ms | < 20ms | 0.10 |
| Fair | < 15% | < 500ms | < 80ms | 0.25 |
| Poor | < 30% | < 1000ms | < 200ms | 0.40 |
| Critical | any worse | — | — | 0.50 |

The client displays this as a default in the redundancy slider. The user can override.

---

### `client/agent` — Data Plane Agent

- **Runtime**: Python 3.12, FastAPI
- **Port**: 8000 (HTTP) + 9001 (UDP)
- **Deploy**: one instance per peer machine (desktop via Electron, or headless Docker)

#### `rs/` — Reed-Solomon Engine

Unchanged from original design. See [REED_SOLOMON.md](./REED_SOLOMON.md).

#### `rs/transport.py` — Transport Abstraction

`rs/transport.py` exposes three public symbols: `BaseTransport` (abstract interface), `UDPTransport`, and `QUICTransport`. The active instance is managed via a module-level `get_transport()` / `set_transport()` pair; `main.py` selects the implementation at startup via `TRANSPORT_MODE`.

`UDPTransport` — raw `asyncio.DatagramProtocol`, no TLS, port `UDP_PORT`.

`QUICTransport` — aioquic over the same UDP port, TLS 1.3 via the QUIC DATAGRAM extension (RFC 9221). RS blocks are sent as unreliable QUIC datagrams so that erasure recovery still works. TLS certificates are auto-generated (RSA-2048, self-signed) with `CN = rockdove-{PEER_ID}` and stored at `STORAGE_PATH/quic_{cert,key}.pem`. The cert is regenerated automatically if `PEER_ID` changes.

#### `storage/` — Local File Storage

Embedded in the agent process. No separate fileserver service. Files stored to `STORAGE_PATH` with SHA-256 checksums.

#### `server_client.py` — Server Communication

Single module responsible for all HTTP calls to the server: registration, heartbeat, peer discovery, metric reporting, and redundancy recommendation fetch.

---

### `client/electron` — Desktop Shell

Electron main process that:
1. Spawns the Python agent as a child process
2. Loads the React UI (`client/ui/`)
3. Exposes `window.rsAgent.baseUrl` (`http://127.0.0.1:8000`) via `contextBridge`

The UI makes all API calls to the local agent over HTTP — no direct Electron IPC needed.

### `client/ui` — React Frontend (SPA)

Same responsibilities as the original `web` service. Communicates exclusively with the local agent at `window.rsAgent.baseUrl`.

---

## P2P Transfer Flow

```
User (Electron UI)                Agent A                    Agent B
──────────────────                ───────                    ───────
POST /transfer/send
  file_id, target_peer_id
  (redundancy_level optional)
                      → GET recommendation from server
                      → GET peer B address from server
                      → encode_file(bytes, redundancy_level)
                      → POST /transfer/receive to Agent B
                                                 ← 202 accepted
                      → UDP packets → → → → → → → receive
                                                   RS decode
                                                   verify SHA-256
                                                   store locally
                      ← poll GET /transfer/{id}/status
                      ← {status: ok/degraded/failed}
← result ←
```

---

### QUIC Transport Variant

When `TRANSPORT_MODE=quic`, the sender additionally emits a **CERT_HELLO datagram** immediately before the RS blocks:

```
CERT_HELLO format (98 bytes typical):
  RDCH magic  (4 B)
  version     (1 B) = 0x01
  peer_id_len (1 B)
  peer_id     (UTF-8)
  transfer_id (16 B, raw UUID bytes)
  fingerprint (64 B, SHA-256 hex of sender cert)
```

The receiver surfaces this as a **pending incoming connection** visible at `GET /transfer/incoming`. The operator can approve or reject before the RS blocks are decoded. Auto-approves after 30 s if no action is taken. Rejection discards the buffer and marks the transfer `failed: rejected_by_operator`.

---

## Redundancy Configuration

See [REED_SOLOMON.md](./REED_SOLOMON.md) for the full RS parameter spec.

`redundancy_level` in `SendRequest` is optional. If omitted, the agent fetches a recommendation from `GET /metrics/recommendation/{peer_id}` on the server, based on recent network telemetry. The slider in the UI shows this value as the default and lets the user override.

---

## Transfer Status

| Status | Meaning |
|--------|---------|
| `ok` | All packets received, checksum matches |
| `degraded` | Packet loss occurred, RS recovered data, checksum matches |
| `failed` | Unrecoverable loss (exceeded RS capacity) or checksum mismatch |

---

## Deployment Profiles

### Desktop (Electron)
Full experience. Electron spawns the Python agent and loads the React UI. No Docker required on the end user's machine.

### Headless / Edge (Docker)
```bash
docker run -e PEER_ID=edge-01 -e SERVER_URL=http://myserver:8080 \
           -p 9001:9001/udp rs-agent
```
No web UI. Agent listens for incoming UDP transfers and stores received files locally. Used for IoT / industrial edge nodes.

### Server
```bash
cd server && docker compose up --build
```

---

## Port Reference

| Component | Port | Protocol |
|-----------|------|----------|
| Server | 8080 | TCP (HTTP) |
| Agent HTTP | 8000 | TCP (HTTP) |
| Agent UDP / QUIC | 9001 | UDP (raw RS blocks in UDP mode; QUIC datagrams in QUIC mode) |

---

## Environment Variables

### Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `TRANSPORT_MODE` | `udp` | `udp` for raw socket, `quic` for aioquic with TLS 1.3 |
