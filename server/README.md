# RS Transfer Server

Central control plane for the RockDove P2P network. Manages peer registration, real-time discovery, network quality metrics, invite tokens, and (optionally) Keycloak OIDC.

## Stack

| Layer | Tech |
|---|---|
| Runtime | Python 3.12, FastAPI, uvicorn |
| Persistence | Redis 7 (hashes + lists + TTL) |
| Auth | PyJWT (HS256 invites, RS256 Keycloak JWTs) |
| Container | Docker Compose (server + Redis + Keycloak) |

## Quick start

```bash
# 1. Copy and fill the env file (root of repo)
cp .env.example .env

# 2. Start all services
cd server
docker compose up --build

# Server  → http://localhost:8080
# Keycloak → http://localhost:8081  (admin/admin)
# Redis    → localhost:6379
```

Dev without Docker:

```bash
uv sync
REDIS_URL=redis://localhost:6379/0 uv run uvicorn main:app --reload --app-dir src
```

## API surface

```
GET  /health                            liveness probe
GET  /auth/config                       OIDC config for the UI

POST /peers/register                    register or re-register a peer
POST /peers/{peer_id}/heartbeat         refresh TTL (keep-alive)
GET  /peers/                            list all online peers
GET  /peers/{peer_id}                   get a single peer
WS   /peers/watch                       real-time peer list stream

POST /metrics/report                    ingest a MetricReport from an agent
GET  /metrics/recommendation/{peer_id} compute redundancy recommendation

POST /invites/                          create a single-use invite token
```

Interactive docs at `/docs` when running.

## Source layout

```
src/
├── main.py              app factory, CORS, router mounting, /health, /auth/config
├── config.py            Settings (pydantic-settings, all env vars)
├── redis_client.py      shared async Redis connection pool
│
├── auth/
│   ├── deps.py          extract_auth() FastAPI dependency
│   └── verifier.py      PyJWKClient JWKS cache + verify_token()
│
├── peers/
│   └── router.py        registration, heartbeat, list, WebSocket watch
│
├── metrics/
│   ├── models.py        MetricReport, RecommendationResponse
│   ├── collector.py     Redis LPUSH/LTRIM sliding window (10 samples/peer)
│   ├── recommender.py   quality bands + network profile floors → redundancy level
│   └── router.py        /report and /recommendation/{peer_id} endpoints
│
└── invites/
    ├── models.py        InviteCreate, InviteInfo
    └── router.py        JWT creation, Redis state machine, validate_invite()
```

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `HEARTBEAT_TTL_S` | `30` | Seconds before an unresponsive peer is evicted |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `OIDC_ENABLED` | `false` | Set to `true` to require auth |
| `OIDC_ISSUER` | `` | Internal issuer URL for JWT validation |
| `OIDC_ISSUER_PUBLIC` | `` | Public issuer URL sent to the UI (proxy override) |
| `OIDC_CLIENT_ID` | `` | Keycloak client ID |
| `INVITE_SECRET` | `change-me-in-production` | HS256 key for invite JWTs |
| `AGENT_SERVICE_TOKEN` | `` | Static Bearer token for headless agents |

## Auth modes

**Dev mode (`OIDC_ENABLED=false`)** — no auth; peer ID comes from the request body.

**OIDC mode (`OIDC_ENABLED=true`)** — every `/peers/register` call needs one of:
- `Authorization: Bearer <keycloak_jwt>` — sub claim becomes the peer_id
- `Authorization: Bearer <AGENT_SERVICE_TOKEN>` — body peer_id trusted
- `invite_token` field in registration body — single-use JWT, consumed atomically

## Peer registration data model (Redis hash `peer:{peer_id}`)

| Field | Example |
|---|---|
| `peer_id` | `peer-alice` |
| `api_url` | `http://192.168.1.10:8000` |
| `udp_host` | `192.168.1.10` |
| `udp_port` | `9001` |
| `last_seen` | ISO-8601 UTC |
| `network_hint` | `wifi` / `lan` / `cellular` / `satellite` / `auto` |

Key expires after `HEARTBEAT_TTL_S` seconds — expiry = peer offline.

## Network profiles

The recommender maps averaged RTT/jitter/loss to a quality band, then enforces a minimum redundancy floor per network type:

| Profile (`network_hint`) | Min redundancy |
|---|---|
| `lan` | 5% |
| `wifi` | 10% |
| `cellular` | 20% |
| `satellite` | 35% |
| `auto` | no floor (quality band only) |

## Keycloak setup

The pre-configured realm is imported automatically on first start:
- Realm: `rockdove`
- Client: `rockdove-client` (public, PKCE S256)
- Test user: `dev-user` / `password123`
- Redirect URIs: `http://localhost:5173/*`, `http://localhost:5174/*`

To enable OIDC in the server set:
```
OIDC_ENABLED=true
OIDC_ISSUER=http://localhost:8081/realms/rockdove
OIDC_CLIENT_ID=rockdove-client
```
