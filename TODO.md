# RockDove — Implementation Backlog

## Estado actual

| Componente | Estado |
|---|---|
| Server: peer registry + WS push | ✅ funcional |
| Server: metrics endpoint + recommender | ✅ funcional — colecta latencia y sube redundancia |
| Server: org/realm isolation (OIDC multi-realm) | ✅ funcional |
| Server: group scopes (admin configurable) | ✅ funcional |
| Server: invite tokens para agentes headless | ✅ funcional |
| Agent: RS encoder/decoder + UDP | ✅ funcional |
| Agent: heartbeat loop + auto re-registro | ✅ re-registra si TTL vence (server restart) |
| Headless agent Docker deploy | ✅ Dockerfile (uv) + docker-compose.headless.yml |
| Device tokens per-dispositivo | ✅ autogenerados, revocables, temporales o indefinidos |
| Agent: AppImage / distribución Electron | ✅ funcional (arreglado) |
| Agent: storage path XDG-compliant | ✅ `~/.local/share/rockdove` |
| Agent: JWT push desde UI después de login | ✅ funcional |
| Agent: token_store (JWT dinámico en runtime) | ✅ funcional |
| Admin panel (UI) | ✅ visibilidad de grupos + invites IoT |
| OIDC / SSO en Electron | ✅ loopback flow con browser externo |
| Peer invite tokens | ✅ funcional |
| Agent: `report_metrics()` | ✅ llamada post-transfer (loss_rate) y en background RTT probe |
| Agent: medición real de RTT/jitter/loss | ✅ `metrics/probe.py` — HTTP RTT a peers cada 60s |
| Persistencia en servidor | ✅ Redis — peers con TTL, métricas con LPUSH/LTRIM |
| Feature flags | ❌ no existe |
| Dynamic FEC | ❌ estático por transferencia |
| NAT traversal / relay | ❌ no existe |
| Transfer history persistido | ✅ SQLite en agente (`storage/db.py`) + `GET /transfer/history` |

---

## Fixes aplicados en esta sesión

### ✅ AppImage: agente no arrancaba (`ModuleNotFoundError: No module named 'main'`)
- `src/main.py` tenía `\"\"\"` (backslashes literales antes de triple-quotes) → syntax error → PyInstaller marcaba `main` como `invalid module` y no lo bundleaba
- `src/__init__.py` convertía `src/` en un paquete Python, rompiendo la resolución de imports de PyInstaller con `pathex=["src"]`
- `run.py` manipulaba `sys.path` innecesariamente en modo frozen (PyInstaller ya provee `FrozenImporter` en `sys.meta_path`)

### ✅ AppImage: storage path read-only (`OSError: [Errno 30] Read-only file system: 'data'`)
- `STORAGE_PATH` defaulteaba a `"./data"` (path relativo al CWD del AppImage montado)
- Ahora resuelve a `$XDG_DATA_HOME/rockdove` o `~/.local/share/rockdove`

### ✅ OIDC: SSO abría Keycloak dentro de Electron en lugar del browser del sistema
- `startLogin()` usaba monkey-patching de `window.open` + `signinPopup()` — muy frágil
- Ahora usa `_manager._client.createSigninRequest()` para generar la URL con PKCE, la abre via `shell.openExternal()`, y el loopback flow (`/auth/callback` → `/auth/poll`) completa el intercambio

### ✅ UI: 307 redirects en cada request al agente
- `agentApi` usaba `/files` y `/transfer` sin trailing slash → FastAPI redirigía a `/files/` y `/transfer/` en cada call
- Arreglado en `api.ts`

### ✅ UI: React StrictMode en build de producción
- `StrictMode` en React 18 double-invoca effects en dev para detectar side effects → `useEffect` de `FileList` se ejecutaba 2 veces al montar, generando ráfagas de requests
- Sacado de `main.tsx` para el AppImage

---

## Fixes aplicados — sesión 2

### ✅ JWKS URL roto dentro de Docker
El servidor intentaba fetch a `localhost:8081` desde dentro del container para obtener las claves públicas de Keycloak. Ese hostname no existe dentro de la red Docker — el request fallaba silenciosamente y todos los JWTs eran rechazados.

Fix: `OIDC_KEYCLOAK_URL=http://keycloak:8080` en `docker-compose.yml` (hostname interno del servicio). `_jwks_url()` en `verifier.py` usa este hostname interno para el fetch de claves, pero valida el claim `iss` del JWT contra la URL pública (la que el usuario ve en el browser), evitando errores de validación de issuer.

### ✅ Agente no se registraba en modo OIDC
El agente arranca antes de que el usuario haga login. En el primer intento de registro no tenía JWT, la request fallaba con 401, y el agente nunca se recuperaba.

Fix: flujo JWT push desde la UI después del login OIDC. Cuando el usuario completa el login, la UI llama `POST /auth/token` con el access token. El agente lo almacena en `token_store` y lanza inmediatamente un nuevo intento de registro con el JWT en el header `Authorization: Bearer`.

### ✅ Service token `org_id` hardcodeado
`deps.py` ponía `org_id="dev"` para los service tokens aunque hubiera un `OIDC_ISSUER` configurado. Agentes desplegados con `AGENT_SERVICE_TOKEN` en realms distintos al de desarrollo quedaban en la org incorrecta.

Fix: cuando `OIDC_ISSUER` está disponible, se deriva el `org_id` a partir del realm del issuer en lugar de usar el literal `"dev"`.

### ✅ Invite `org_id` ignoraba el realm del caller
El endpoint de creación de invites siempre usaba `body.org_id` para el campo `org_id` del token generado, sin verificar a qué realm pertenecía el peer que hacía la llamada. Un peer autenticado en el realm A podía generar invites válidos para el realm B.

Fix: en modo OIDC, el endpoint ahora usa `caller.org_id` (extraído del JWT del caller) en lugar de `body.org_id`.

### ✅ Mapper de grupos no activo en Keycloak
El realm JSON (`rockdove-realm.json`) sólo se importa en el primer arranque de Keycloak. Las instancias existentes que ya tenían el realm importado sin el mapper de grupos no emitían el claim `groups` en el JWT.

Fix: el mapper se añade vía la API de administración de Keycloak en runtime (script de inicialización), independientemente del estado del realm existente.

### ✅ Panel admin no aparecía en la UI
La detección de admin dependía de que el claim `groups` estuviera presente en el JWT del usuario. Los tokens emitidos antes del fix anterior no incluían ese claim, por lo que ningún usuario era reconocido como admin.

Fix: detección server-side. La UI ahora sondea `GET /peers/scopes`: respuesta 200 significa que el peer tiene permisos de admin; respuesta 403 significa que no. Esto elimina la dependencia del claim `groups` en el cliente.

---

## ✅ P0.1 · Métricas reales — COMPLETADO

- `metrics/probe.py`: loop cada 60s, HTTP RTT (5 pings) a cada peer online, reporta a servidor
- `transfers/router.py`: al terminar cada send, reporta `loss_rate = recovered_blocks / total_blocks` y `elapsed_ms`
- `server_client.get_full_recommendation()`: fetch en paralelo para sender **y** target; usa `max` → si cualquier extremo tiene alta latencia, sube redundancia
- `TransferResult` ahora incluye `effective_redundancy`, `quality`, `profile_name` para que la UI los muestre

---

## ✅ P0.2 · Persistencia del servidor — COMPLETADO

- Peers en Redis hash `peer:{org_id}:{peer_id}` con TTL = `HEARTBEAT_TTL_S`
- Heartbeat = `EXPIRE` del key, el peer desaparece solo si deja de latir
- Métricas en Redis list `metrics:{peer_id}` con `LPUSH` + `LTRIM` (max 10 muestras)
- Redis en `docker-compose.yml` como servicio propio

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

**Estado:** ✅ implementado para el flujo headless/IoT (admin panel genera snippets `.env`). Pendiente: flujo peer-a-peer sin panel admin.

**Flujo pendiente:**
1. Peer A autenticado llama `POST /invites` → servidor genera JWT firmado:
   ```json
   { "issued_by": "peer-alice", "org_id": "org-123", "exp": 1234567890 }
   ```
2. A le pasa el token a B (out-of-band: QR, email, etc.)
3. B llama `POST /peers/register` incluyendo el token → servidor valida firma, asocia B a la org
4. Sin token, el peer queda en estado `pending` (visible solo para admins)

**Complejidad restante:** S

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

### ✅ P1.4 · OIDC real con Keycloak — completado (client + server)

El flujo SSO está operativo end-to-end:

**Client side:**
- `startLogin()` genera la URL de autorización con PKCE y la abre en el browser del sistema
- Keycloak redirige a `http://127.0.0.1:8000/auth/callback` (agente local)
- El agente almacena el code; la UI hace polling y completa el token exchange con `signinCallback()`
- La UI empuja el JWT al agente vía `POST /auth/token`; el agente re-registra con el servidor

**Server side:**
- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_ENABLED=true` configurados en el servidor
- JWT verification con JWKS fetch desde el hostname interno de Keycloak
- `peer_id` asignado como `JWT sub` en modo OIDC
- `org_id` derivado del realm del issuer para service tokens
- Invite `org_id` usa el realm del caller en modo OIDC

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

## ✅ P2.2 · Historial de transferencias SQLite — COMPLETADO

- `storage/db.py` — init, insert, list con `aiosqlite`
- Persiste sent (con `peer_id`, `filename`, `redundancy`, `quality`) y received (con `file_size`, `recovered_blocks`)
- `GET /transfer/history?limit=50` — `HistoryEntry` model
- Inicializado en el lifespan de `main.py`; se cierra ordenadamente al apagar el agente

---

## ✅ Headless Agent Deployment — COMPLETADO

### Qué hay

**`client/agent/Dockerfile`** — imagen funcional construida con `uv export` desde el lockfile para deps reproducibles.

**`client/agent/docker-compose.headless.yml`** — compose listo para copiar al dispositivo. Lee variables desde `.env`.

**Heartbeat auto-recovery** — si el peer TTL vence en Redis (server se reinicia), el siguiente heartbeat devuelve 404 y el agente se vuelve a registrar automáticamente sin intervención humana.

### Device tokens — sistema de autenticación por dispositivo ✅

Módulo `server/src/device_tokens/`. Reemplaza el token compartido por tokens únicos, autogenerados y revocables.

**Formato:** `rd_<43-char base64url>` — 256 bits de entropía, imposible de adivinar.

**API (admin only):**

| Endpoint | Acción |
|---|---|
| `POST /device-tokens/` | Crea token. Retorna el valor completo **solo en esta respuesta** |
| `GET /device-tokens/` | Lista tokens del org con `token_preview` (primeros 12 chars + `...`) |
| `DELETE /device-tokens/{id}` | Revoca inmediatamente — el token falla en el próximo request |

**Creación — campos:**
```json
{
  "label": "Sensor Planta A",
  "peer_id": "sensor-a1",
  "ttl_seconds": 2592000
}
```
`ttl_seconds: null` → indefinido. El token se borra de Redis al vencer (sin cron).

**Storage Redis:**
- `device_token:{value}` → hash con metadata (lookup de auth)
- `device_token_rev:{org}:{id}` → value (para revocar por ID)
- `device_tokens_idx:{org}` → set de IDs (para listar)

**Auth flow en `deps.py`:**
1. `AGENT_SERVICE_TOKEN` estático (legado, solo si está configurado)
2. Redis lookup `device_token:{bearer}` → `CallerInfo(is_service=True, peer_id=<peer_id del token>)`
3. OIDC JWT (usuarios humanos)

### Flujo completo para un dispositivo headless

**Paso 1 — Admin genera un device token**

```http
POST /device-tokens/
Authorization: Bearer <admin-jwt>

{ "label": "Sensor Planta A", "peer_id": "sensor-a1", "ttl_seconds": null }
```
Respuesta (el campo `token` solo aparece aquí):
```json
{
  "id": "550e8400-...",
  "label": "Sensor Planta A",
  "token": "rd_dW6awd00XpaS1PqJzK8mBnLcVt9...",
  "token_preview": "rd_dW6awd00Xp...",
  "expires_at": null
}
```

**Paso 2 — Operador configura el dispositivo**

`.env` en el dispositivo:
```
PEER_ID=sensor-a1
SERVER_URL=http://my-server:8080
AGENT_API_URL=http://<device-ip>:8000
AGENT_SERVICE_TOKEN=rd_dW6awd00XpaS1PqJzK8mBnLcVt9...
```
```bash
docker compose -f docker-compose.headless.yml up -d
```

**Paso 3 — El agente se auto-mantiene**

- Se registra en el server al arrancar usando el device token como Bearer
- Heartbeat cada 15s renueva el TTL Redis del peer
- Si el server se reinicia → siguiente heartbeat (404) dispara re-registro automático
- Si el token vence → heartbeat empieza a fallar 401 → admin genera uno nuevo

### Binario alternativo (sin Docker)

```bash
chmod +x rockdove-agent.AppImage
PEER_ID=sensor-a1 SERVER_URL=http://server:8080 \
AGENT_API_URL=http://$(hostname -I | awk '{print $1}'):8000 \
AGENT_SERVICE_TOKEN=rd_dW6awd00XpaS1... \
./rockdove-agent.AppImage
```

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
Sprint 1 (P0):   Redis en server · métricas desde transfers
Sprint 2 (P1a):  dynamic FEC · network profiles
Sprint 3 (P1b + P2.1): peer-to-peer invite tokens · feature flags
Sprint 4 (P2.2 + P2.3): historial SQLite en agent · PostgreSQL en server
Sprint 5 (P3):   NAT hole punching · relay fallback
```

Lo más importante del Sprint 1 es que el adaptive redundancy funciona de verdad — el sistema mide pérdida real en las transferencias y el recomendador tiene datos para operar. Ese es el feature que le da valor académico al TP y actualmente es un cascarón vacío.
