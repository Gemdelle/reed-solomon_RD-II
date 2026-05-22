# Architecture

## Overview

P2P file transfer system with Reed-Solomon forward error correction over UDP. Designed for reliable transfer over unreliable connections, with organization-based isolation and configurable redundancy.

**Primary use cases:**
- Org members transferring files peer-to-peer through the backend
- Edge device ingestion: sending sensitive files to a remote node with unstable connectivity (cellular, satellite)

---

## Deployment Model

**This is the most important thing to understand about this architecture.**

Each participant runs their own full instance of the stack on their own machine. The API Gateway on each machine is the UDP peer — it owns the UDP socket and handles RS encoding/decoding directly. The browser cannot open raw UDP sockets, so the local backend acts as the user's network agent.

```
What's LOCAL per user (runs on each machine):
  api  ·  fileserver  ·  web

What's SHARED (one instance, e.g. a cloud VM):
  Keycloak — only used for auth tokens and peer registry (IP lookup)
```

The actual file data never touches the shared server. Keycloak only answers "who is User B and what is their IP:PORT?" The transfer goes machine-to-machine directly over UDP.

**Analogy:** Think of a torrent client. The app running on your machine IS the peer. The tracker (Keycloak here) only helps peers find each other — it doesn't relay data.

### Why this matters for the edge use case

An edge device (Raspberry Pi, industrial PC) runs `docker-compose.edge.yml` — only `api` + `fileserver`, no web UI, no auth. It listens on UDP port 9001. A remote operator sends a file directly to the edge device's IP over UDP with RS encoding. The unreliable link (cellular, satellite) drops packets; RS reconstructs the file anyway. No central server is in the data path.

### P2P Transfer Flow (two machines)

```
Machine A (User A)                           Machine B (User B)
─────────────────                            ─────────────────
browser → POST /transfer/send
           { file_id, target: "userB",
             redundancy: 0.30 }
              │
              ▼
api queries Keycloak ──── HTTPS ────▶ "userB is at 203.0.113.42:9001"
              │
              ▼
api fetches file from own fileserver
api RS-encodes → UDP packets
              │
              └──────────── UDP ────────────▶ api :9001 receives packets
                                              RS-decode, verify SHA-256
                                              store in own fileserver
              ◀────────── HTTPS ─────────── POST /transfer/{id}/result
browser receives status: ok / degraded / failed
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser / Web UI                          │
│                    React SPA  ·  port 3000                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / REST
┌───────────────────────────▼─────────────────────────────────────┐
│                      API Gateway                                  │
│                  FastAPI  ·  port 8000                            │
│                                                                   │
│   ┌────────────────┐   ┌─────────────────────────────────────┐   │
│   │  /auth/*        │   │  /transfer/*  (redundancy module)   │   │
│   │  /files/*       │   │  APIRouter  — RS encode/decode      │   │
│   │  /peers/*       │   │  UDP socket manager                 │   │
│   └────────┬───────┘   └──────────────────┬──────────────────┘   │
└────────────┼──────────────────────────────┼────────────────────── ┘
             │ HTTP (internal)              │ UDP
             ▼                             ▼
┌────────────────────────┐      ┌──────────────────────────────────┐
│     File Server         │      │  Peer Node                        │
│  FastAPI  ·  port 9000  │      │  (another stack instance)         │
│                         │      │  API Gateway  ·  port 8000        │
│  - store / retrieve     │      │  redundancy module listening UDP  │
│  - SHA-256 checksum     │      └──────────────────────────────────┘
│  - file metadata        │
│  - internal only        │
└────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    Keycloak  ·  port 8080                         │
│   realm per org  ·  OIDC/JWT  ·  org_id + user_id in claims       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Services

### `api` — API Gateway
- **Runtime**: Python 3.12, FastAPI
- **Port**: 8000
- **Responsibilities**:
  - Validate JWTs (Keycloak JWKS endpoint)
  - Proxy file operations to `fileserver`
  - Mount `redundancy` module as an `APIRouter` at `/transfer`
  - Expose `/peers` endpoint (queries Keycloak for org members + heartbeat state)
- **Does NOT**: store files, do raw UDP directly (delegated to redundancy module)

### `api/redundancy/` — Redundancy Module
- **Type**: FastAPI `APIRouter`, lives inside `api` service
- **Mounted at**: `/transfer`
- **Responsibilities**:
  - Accept transfer requests (file_id, target_peer, redundancy_level)
  - Fetch file bytes from `fileserver`
  - RS-encode data into UDP packets
  - Send packets to target peer's UDP listener
  - On receive: RS-decode, verify SHA-256 checksum, store in own `fileserver`
  - Report transfer status: `ok` / `degraded` / `failed`
- **Owns**: UDP socket lifecycle, RS parameter calculation

### `fileserver` — File Server
- **Runtime**: Python 3.12, FastAPI
- **Port**: 9000 (internal network only, not exposed)
- **Responsibilities**:
  - `POST /files` — store file, compute and persist SHA-256
  - `GET /files/{file_id}` — retrieve raw bytes
  - `GET /files/{file_id}/checksum` — retrieve stored checksum
  - `DELETE /files/{file_id}`
- **Storage**: local volume (`/data`), replaceable with S3-compatible backend

### `auth` — Identity Provider
- **Runtime**: Keycloak (official image)
- **Port**: 8080
- **Model**:
  - One Keycloak realm per organization
  - Users belong to groups within their realm
  - JWT claims include `org_id`, `user_id`, `realm_access`
- **API Gateway integration**: validates tokens via JWKS (`/realms/{realm}/protocol/openid-connect/certs`)

### `web` — Frontend
- **Runtime**: Node / React (Vite)
- **Port**: 3000
- **Responsibilities**:
  - Org/user management UI
  - File list and upload
  - Peer list (org members online)
  - Transfer dialog: target peer selector + redundancy slider
  - Transfer history with status badges (`ok` / `degraded` / `failed`)
- **Communicates only with**: `api` (never directly with `fileserver` or Keycloak)

---

## Data Flows

### Upload
```
User → POST /files (multipart) → API Gateway
     → POST /internal/files     → File Server
     ← file_id + checksum       ←
     ← file_id                  ←
```

### Transfer (P2P)
```
Initiator                    API Gateway (initiator)         API Gateway (target)
─────────                    ───────────────────────         ────────────────────
POST /transfer/send
  file_id
  target_peer_id
  redundancy_level (0.0–0.5)
                    → fetch file bytes from fileserver
                    → RS-encode into blocks
                    → UDP packets → → → → → → → → → → receive UDP packets
                                                        RS-decode blocks
                                                        reconstruct bytes
                                                        verify SHA-256
                                                        store in own fileserver
                    ← transfer_result {status, stats} ←
← status response ←
```

### Peer Discovery
```
GET /peers  →  API Gateway
           →  Keycloak: list users in same realm/org
           →  filter by heartbeat (last_seen < 30s)
           ←  [{user_id, username, address, last_seen}]
```

Peers register their transfer endpoint (IP:UDP_PORT) on login and maintain a heartbeat via `POST /peers/heartbeat`.

---

## Organization Model

- Each organization maps to a Keycloak realm
- Users can only see and transfer to peers in their own org
- Files are scoped per user (org isolation enforced at API layer)
- Cross-org transfer is not supported in MVP

---

## Redundancy Configuration

The redundancy level is expressed as a ratio `r = (n - k) / n` where:
- `k` = number of original data symbols per block
- `n` = total symbols after encoding (data + parity)
- `r` controls what percentage of UDP packets can be lost and still recover

| Preset | r | RS params | Overhead | Tolerates |
|--------|---|-----------|----------|-----------|
| Fast | 0.10 | n=10, k=9 | ~11% | 10% loss |
| Balanced | 0.25 | n=8, k=6 | ~33% | 25% loss |
| Resilient | 0.50 | n=10, k=5 | 100% | 50% loss |
| Custom | 0.05–0.50 | derived | variable | variable |

See [REED_SOLOMON.md](./REED_SOLOMON.md) for encoding/decoding spec and parameter derivation.

---

## Transfer Status

| Status | Meaning |
|--------|---------|
| `ok` | All packets received, checksum matches |
| `degraded` | Packet loss occurred, RS recovered data, checksum matches |
| `failed` | Unrecoverable loss (exceeded RS capacity) or checksum mismatch |

---

## Deployment Profiles

### `full` (default)
All services: `web`, `api`, `fileserver`, `auth` (Keycloak).

### `edge`
Minimal profile for resource-constrained nodes. No `web`, no `auth`. Only `api` (redundancy module as receiver) + `fileserver`. Receives transfers from a full-profile instance.

```yaml
# docker-compose.edge.yml — see compose files for full spec
services: [api, fileserver]
```

---

## Port Reference

| Service | Port | Exposure |
|---------|------|----------|
| web | 3000 | public |
| api | 8000 | public |
| api UDP | 9001 | public (UDP) |
| fileserver | 9000 | internal only |
| auth (Keycloak) | 8080 | public (admin) |
