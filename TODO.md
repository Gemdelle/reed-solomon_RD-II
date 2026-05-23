# RockDove — Implementation Backlog

## Estado actual

| Componente | Estado |
|---|---|
| Server: peer registry + WS push | ✅ funcional |
| Server: metrics endpoint + recommender | ✅ existe, pero nadie lo alimenta |
| Agent: RS encoder/decoder + UDP | ✅ funcional |
| Agent: heartbeat loop | ✅ funcional |
| Agent: `report_metrics()` | ❌ definida, **nunca llamada** |
| Agent: medición real de RTT/jitter/loss | ❌ no existe |
| Persistencia en servidor | ❌ todo en dicts en memoria |
| OIDC | ❌ stub devuelve `false` |
| Feature flags | ❌ no existe |
| Dynamic FEC | ❌ estático por transferencia |
| Peer invite tokens | ❌ no existe |
| NAT traversal / relay | ❌ no existe |
| Transfer history persistido | ❌ solo en React state |

---

## P0 — Gaps críticos (el sistema no es real sin esto)

### P0.1 · Métricas reales: instrumentar UDP y llamar `report_metrics()`
**Por qué:** el sistema de redundancia adaptativa es el feature estrella del TP pero está ciego — el recommender funciona pero nunca recibe datos.

**Dónde:** `client/agent/src/transfers/router.py` + nuevo `client/agent/src/metrics/probe.py`

**Qué hacer:**
- Al terminar cada transferencia, calcular desde los datos que ya existen: `loss_rate = recovered_blocks / total_blocks`, `elapsed_ms` del envío
- Llamar `await server_client.report_metrics(peer_id, rtt_ms, jitter_ms, loss_rate)` al final de `send_file()`
- Agregar un background task en `main.py` lifespan que cada 60s mide RTT real: abre UDP a cada peer online y envía 5 paquetes de 20 bytes tipo ping, mide round-trip

**Complejidad:** M

---

### P0.2 · Persistencia del servidor con Redis
**Por qué:** si el servidor se reinicia, todos los peers se "olvidan". Inaceptable en producción.

**Dónde:** `server/src/peers/router.py`, `server/src/metrics/collector.py`, `server/docker-compose.yml`

**Qué hacer:**
- Agregar `redis` a `server/pyproject.toml`
- Reemplazar `_peers: dict` → Redis hash con TTL = heartbeat timeout
- Heartbeat = `EXPIRE peer:{id} 30` en lugar de actualizar `last_seen` en memoria
- `_reports` deque → Redis list con `LPUSH` / `LTRIM` (max 10 por peer)

```yaml
# server/docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

**Complejidad:** M

---

### P0.3 · Auto-detección de `AGENT_API_URL`
**Por qué:** ahora el usuario tiene que saber su IP y configurarla a mano. Con Electron, nadie va a hacer eso.

**Dónde:** `client/agent/src/config.py`

```python
def _detect_local_ip() -> str:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]

class Settings(BaseSettings):
    AGENT_API_URL: str = ""

    def model_post_init(self, _):
        if not self.AGENT_API_URL:
            ip = _detect_local_ip()
            self.AGENT_API_URL = f"http://{ip}:{self.AGENT_PORT}"
```

**Complejidad:** S

---

## P1 — Diferenciadores académicos (lo que lo hace interesante)

### P1.1 · Dynamic Adaptive FEC
**Por qué:** esto es el salto de "TP con RS" a "adaptive FEC platform". Es el feature más innovador.

**Concepto:** en lugar de un `redundancy_level` fijo para toda la transferencia, ajustarlo por chunks basado en pérdida observada.

**Dónde:** `client/agent/src/rs/encoder.py`, `client/agent/src/transfers/router.py`

**Protocolo:**
1. Dividir el archivo en chunks de N bloques (configurable, default 200)
2. Enviar chunk 0 con redundancia inicial (la del slider)
3. El receiver reporta al sender: `{chunk_id, received, total}` vía el canal HTTP ya existente
4. El sender calcula `observed_loss = 1 - received/total` y ajusta redundancia para chunk 1
5. Repetir

```python
# transfers/router.py — nuevo campo en TransferResult
class ChunkResult(BaseModel):
    chunk_id: int
    received_blocks: int
    total_blocks: int
    redundancy_used: float

class TransferResult(BaseModel):
    # ... existing fields
    chunks: list[ChunkResult] = []
    redundancy_timeline: list[float] = []  # redundancy per chunk — gráfico en UI
```

**Complejidad:** L
**Dependencia:** P0.1 (necesita métricas para decidir)

---

### P1.2 · Peer Invite Tokens
**Por qué:** agrega un trust graph real. A puede autorizar a B sin que el servidor intermedie la identidad. Crítico para IoT/edge.

**Dónde:** nuevo `server/src/invites/`

**Flujo:**
1. Peer A autenticado llama `POST /invites` → servidor genera JWT firmado:
   ```json
   { "issued_by": "peer-alice", "org_id": "org-123", "exp": 1234567890 }
   ```
2. A le pasa el token a B (out-of-band: QR, email, etc.)
3. B llama `POST /peers/register` incluyendo el token → servidor valida firma, asocia B a la org
4. Sin token, el peer queda en estado `pending` (visible solo para admins)

```python
# server/src/invites/router.py
@router.post("/")
async def create_invite(current_peer: str, org_id: str) -> dict:
    token = jwt.encode({"issued_by": current_peer, "org_id": org_id, "exp": ...}, SECRET_KEY)
    return {"token": token}
```

**Complejidad:** M

---

### P1.3 · Network Profiles
**Por qué:** en lugar de que el usuario ajuste el slider sin contexto, el sistema sugiere un perfil y explica por qué.

**Dónde:** `server/src/metrics/recommender.py` + `client/agent/src/config.py`

**Implementación:**
- Agent declara un `network_hint` en register: `"lan" | "wifi" | "cellular" | "satellite" | "auto"`
- Con `"auto"`: server infiere desde las métricas recibidas
- Server retorna `quality`, `recommended_level`, y `profile_name` en la recomendación

```python
PROFILES = {
    "lan":       {"redundancy": 0.05, "block_size": 64, "pacing_ms": 0},
    "wifi":      {"redundancy": 0.10, "block_size": 32, "pacing_ms": 2},
    "cellular":  {"redundancy": 0.30, "block_size": 32, "pacing_ms": 10},
    "satellite": {"redundancy": 0.50, "block_size": 16, "pacing_ms": 50},
}
```

**Complejidad:** S

---

### P1.4 · OIDC real con Keycloak
**Por qué:** el TP menciona autenticación pero nunca funciona. Con Keycloak en docker-compose es una tarde de trabajo.

**Dónde:** `server/docker-compose.yml`, `server/src/main.py`, `client/ui/src/auth/oidc.ts` (ya implementado del lado UI)

```yaml
# server/docker-compose.yml
keycloak:
  image: quay.io/keycloak/keycloak:24
  environment:
    KCADMIN_USERNAME: admin
    KCADMIN_PASSWORD: admin
  command: start-dev
  ports: ["8081:8080"]
```

Server settings: `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_ENABLED=true` → `/auth/config` ya devuelve esos campos, solo hay que alimentarlos desde env vars.

**Complejidad:** M

---

## P2 — Feature flags y observabilidad

### P2.1 · Feature Flags en servidor
**Por qué:** permite activar/desactivar features por ambiente sin redeploy. Crítico para gradual rollout.

**Dónde:** nuevo `server/src/features/router.py`

```python
# server/src/features/router.py
FEATURES = {
    "dynamic_fec":      os.getenv("FF_DYNAMIC_FEC", "false") == "true",
    "invite_tokens":    os.getenv("FF_INVITE_TOKENS", "false") == "true",
    "relay_fallback":   os.getenv("FF_RELAY_FALLBACK", "false") == "true",
    "quic_transport":   os.getenv("FF_QUIC_TRANSPORT", "false") == "true",
    "oidc_required":    os.getenv("FF_OIDC_REQUIRED", "false") == "true",
}

@router.get("/")
async def get_features() -> dict:
    return FEATURES
```

Agent lo lee al arrancar y guarda en un singleton `features`. Cada codepath que implementa una feature nueva hace `if features.dynamic_fec:`.

**Complejidad:** S

---

### P2.2 · Persistencia de historial de transferencias
**Por qué:** el historial vive solo en React state — si cerrás la app, se pierde.

**Dónde:** `client/agent/src/storage/` — agregar SQLite con `aiosqlite`

```sql
CREATE TABLE transfers (
    id TEXT PRIMARY KEY,
    ts DATETIME,
    target_peer TEXT,
    filename TEXT,
    bytes INTEGER,
    status TEXT,        -- ok / degraded / failed
    redundancy REAL,
    recovered_blocks INTEGER,
    total_blocks INTEGER
);
```

API nueva: `GET /transfers/history?limit=50` — la UI la consume en lugar de mantener estado local.

**Complejidad:** M

---

### P2.3 · PostgreSQL + historial de métricas en servidor
**Por qué:** con Redis se pierde el historial al reiniciar. Con Postgres se puede analizar tendencias, mejorar el recommender.

**Dónde:** `server/src/db/` con SQLAlchemy async

Tablas mínimas:
- `peer_metrics(peer_id, ts, rtt_ms, jitter_ms, loss_rate)`
- `transfers_audit(transfer_id, sender, receiver, bytes, status, ts)`

**Complejidad:** L
**Dependencia:** P0.2 (Redis primero, Postgres como upgrade)

---

## P3 — Roadmap ambicioso

| Feature | Descripción | Complejidad |
|---|---|---|
| **QUIC transport** | Reemplazar raw UDP con `aioquic`. Da encryption, multiplexing, congestion control. RS FEC encima de QUIC stream. | XL |
| **NAT hole punching** | Servidor como signaling relay: coordina intercambio de IPs para que ambos peers se puedan ver detrás de NAT | L |
| **Relay fallback** | Si UDP directo falla N veces, chunks van por el servidor como relay hasta que la conexión directa se establezca | L |
| **Smart routing** | Server puede sugerir `A → relay_peer_C → B` si C tiene mejor conectividad con B que A directamente | XL |
| **Peer capability system** | Agent reporta `{cpu_score, ram_mb, network_type}` en heartbeat. Server puede restar redundancy para nodos lentos | M |
| **ML redundancy** | Reemplazar tabla de umbrales hardcodeada por modelo simple (regresión logística) entrenado sobre historial de transferencias | L |

---

## Secuencia de sprints sugerida

```
Sprint 1 (P0):   auto-IP · Redis en server · métricas desde transfers
Sprint 2 (P1a):  dynamic FEC · network profiles
Sprint 3 (P1b + P2.1): invite tokens · feature flags
Sprint 4 (P2.2 + P1.4): historial SQLite en agent · Keycloak
Sprint 5 (P2.3 + P3):   PostgreSQL · NAT hole punching
```

Lo más importante del Sprint 1 es que el adaptive redundancy funciona de verdad — el sistema mide pérdida real en las transferencias y el recomendador tiene datos para operar. Ese es el feature que le da valor académico al TP y actualmente es un cascarón vacío.
