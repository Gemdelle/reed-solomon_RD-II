# AI Agent Guidelines

This document tells AI coding agents how to work on this codebase. Read it before writing any code.

---

## Project Context

This is a **P2P file transfer system** for a university data networks course. The core algorithm is **Reed-Solomon forward error correction** applied to UDP transfers. The architecture is described in [ARCHITECTURE.md](./ARCHITECTURE.md). Development rules are in [RULES.md](./RULES.md).

The project is built by students with mixed profiles (DevOps, backend, frontend). The code must be readable, modular, and well-structured — not just working.

### Critical: How P2P actually works

**Each participant runs their own full instance of the stack on their own machine.** The `api` service on each machine is the UDP peer — it owns the UDP socket, encodes/decodes RS blocks, and sends/receives datagrams directly to/from other machines.

The browser cannot open raw UDP sockets. The local `api` service acts as a network agent on behalf of the user. When a user clicks "send", their local API fetches the file, RS-encodes it, and fires UDP packets to the target machine's `api` port.

**What's local per user:** `api`, `fileserver`, `web`  
**What's shared (one cloud instance):** `auth` (Keycloak) — only for identity and peer IP lookup, never in the data path.

If you find yourself designing code where the shared server relays file data, stop — that's wrong. The transfer is always direct, machine-to-machine over UDP.

---

## Service Ownership Map

When working on a task, identify which service owns it first.

| Area | Location | Notes |
|------|----------|-------|
| RS encode/decode | `services/api/redundancy/` | Core algorithm — treat with care |
| UDP transport | `services/api/redundancy/transport.py` | Single file owns all sockets |
| Transfer routes | `services/api/redundancy/router.py` | Thin — no logic here |
| File storage | `services/fileserver/` | Separate service, internal only |
| Auth / JWT | `services/api/auth/` | Keycloak integration |
| Peer discovery | `services/api/peers/` | Heartbeat + org member list |
| Frontend | `services/web/src/` | React, communicates only with `api` |
| Compose config | root `docker-compose*.yml` | DevOps concern |

---

## What You Can Change Freely

- Adding new Pydantic models in `models.py` files
- Adding new routes to existing routers
- Adding tests under `tests/`
- Frontend components under `services/web/src/components/`
- Improving error messages and response bodies

---

## What Requires Caution

**`services/api/redundancy/encoder.py` and `decoder.py`**  
These implement the RS algorithm. Any change must:
1. Not break the encode→decode roundtrip
2. Not change the UDP packet format (see [REED_SOLOMON.md](./REED_SOLOMON.md)) without updating the spec
3. Pass existing tests before the PR is opened

**`services/api/redundancy/transport.py`**  
Owns the UDP socket. Changes here can silently break transfers. Test with actual UDP sends, not mocks.

**`docker-compose.yml`**  
Do not add `ports` mappings for `fileserver`. Do not remove health checks. Coordinate with the DevOps owner before structural changes.

**`services/api/auth/`**  
JWT validation logic. Do not add workarounds that skip token verification. If Keycloak is unavailable in dev, use a dev-mode flag — don't disable auth wholesale.

---

## What You Must Not Do

- Do not open UDP sockets outside `transport.py`
- Do not compute checksums outside `fileserver` storage layer — use the stored value
- Do not accept `n` or `k` directly from HTTP request bodies — always derive from `redundancy_level`
- Do not store files outside the `fileserver` service
- Do not add `org_id` as a request body field and trust it — extract from JWT only
- Do not commit `.env` files
- Do not mock `RSCodec` in transfer integration tests

---

## RS Parameter Derivation

When the API receives `redundancy_level: float`, derive parameters like this:

```python
N_FIXED = 32

def derive_rs_params(redundancy_level: float) -> tuple[int, int]:
    n = N_FIXED
    k = round(n * (1 - redundancy_level))
    k = max(4, min(k, n - 1))
    return n, k
```

Never let the client send `n` or `k` directly.

---

## Transfer Status Logic

The transfer result must be one of three values. The decision tree:

```
RS decode raises exception (unrecoverable loss)
    → status = "failed", reason = "unrecoverable_loss"

RS decode succeeds, checksum mismatch
    → status = "failed", reason = "checksum_mismatch"

RS decode succeeds, some blocks were reconstructed (recovered_blocks > 0), checksum matches
    → status = "degraded"

RS decode succeeds, no reconstruction needed, checksum matches
    → status = "ok"
```

---

## Adding a New Feature

1. Identify which service owns it (use the table above)
2. Add Pydantic models first
3. Add the route to the appropriate router
4. Implement logic in a separate module (not in `router.py`)
5. Write at least one test
6. Update the relevant doc if the feature changes public behavior

---

## API Endpoint Patterns

```
GET    /files              → list user's files
POST   /files              → upload file
GET    /files/{id}         → download file
DELETE /files/{id}         → delete file

GET    /peers              → list online peers in same org
POST   /peers/heartbeat    → register/refresh peer presence

POST   /transfer/send      → initiate outgoing transfer
GET    /transfer/{id}      → get transfer status
GET    /transfer           → list transfer history
```

New endpoints should follow this REST pattern. No RPC-style routes (`/transfer/doSend`).

---

## Dev Environment

All services start with:
```bash
docker compose up --build
```

For local development without Docker, each service has a `pyproject.toml` (or `requirements.txt`). Run individual services with:
```bash
uvicorn main:app --reload --port 8000
```

The `fileserver` must be running before `api` can start (health check dependency in compose).

---

## Questions to Ask Before Implementing

Before writing code, confirm:
- Which service owns this functionality?
- Does this change the UDP packet format? (If yes: update REED_SOLOMON.md)
- Does this touch auth? (If yes: verify JWT is still required)
- Does this require a new environment variable? (If yes: add to `.env.example` and RULES.md)
- Is there an existing model or utility I can extend instead of creating new?
