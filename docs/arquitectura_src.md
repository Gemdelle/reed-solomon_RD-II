---
title: "RockDove — Sistema P2P con Reed-Solomon"
subtitle: "Arquitectura, Algoritmo e Infraestructura"
author: "Grupo 1 — Redes de Datos II"
date: "2026"
lang: es
toc: true
toc-depth: 3
numbersections: true
geometry: margin=2.5cm
fontsize: 11pt
---

\newpage

# Descripción del Sistema

## ¿Qué es RockDove?

**RockDove** es una plataforma de transferencia de archivos entre pares (*peer-to-peer*) que aplica
el algoritmo de corrección de errores **Reed-Solomon** sobre **UDP** para garantizar la integridad
de los datos incluso en redes con pérdida de paquetes. La redundancia matemática se calcula de
forma adaptativa según las condiciones de red medidas en tiempo real, sin necesidad de que el
usuario configure parámetros técnicos manualmente.

El sistema está pensado para dos escenarios complementarios:

- **Transferencia entre usuarios de escritorio:** dos o más usuarios de la misma organización se
  envían archivos directamente entre máquinas, con verificación criptográfica de integridad.
- **Ingesta a dispositivos edge / IoT:** un nodo con conectividad degradada (celular, satelital,
  industrial) recibe datos con garantía de reconstrucción aunque se pierdan paquetes, sin
  retransmisión.

## El problema que resuelve

UDP no garantiza entrega ni orden. En redes inestables, una transferencia sin protección resulta en
datos incompletos o corruptos. Las alternativas clásicas son:

| Alternativa | Problema |
|---|---|
| TCP | Retransmisión costosa en links de alta latencia o intermitentes |
| Ignorar la pérdida | Inaceptable para archivos completos |
| Checksum + retry | Requiere round-trips, imposible en links unidireccionales |

RockDove aplica **Forward Error Correction (FEC)** mediante Reed-Solomon: el emisor agrega
redundancia antes de enviar. El receptor reconstruye el original aunque lleguen menos paquetes de
los enviados, **sin contactar al emisor**.

## Casos de uso

| Caso | Escenario típico |
|---|---|
| Transferencia intra-organización | Usuario A envía reporte a colega B |
| Ingesta a nodo edge | Servidor central envía configuración a planta remota |
| Verificación forense | Sistema certifica si el archivo llegó íntegro (`ok`), con recuperación RS (`degraded`) o irrecuperable (`failed`) |
| Dispositivos headless | Sensores o cámaras reciben archivos sin interfaz gráfica, autenticados con token de dispositivo |

\newpage

# Algoritmo Reed-Solomon

## Fundamento matemático

Reed-Solomon es un código corrector de errores que opera sobre **GF(2^8^)** (campo de Galois de
256 elementos). Cada símbolo del código es un byte. El codificador toma **k** bytes originales y
produce **n** bytes totales: los k originales más **n − k** bytes de paridad generados
algebraicamente.

La propiedad fundamental: el receptor puede reconstruir los k bytes originales a partir de
**cualquier combinación de k de los n bytes recibidos**, sin importar cuáles k−n se perdieron.
En el contexto UDP, donde se conoce exactamente qué paquetes llegaron (*erasure model*), esta
capacidad se aprovecha al máximo: cada paquete perdido equivale a una posición de erasure conocida.

## Parámetros RS(n, k)

| Símbolo | Significado |
|---|---|
| `k` | Bytes de datos originales por bloque |
| `n` | Bytes totales tras codificar (k + paridad); máximo 255 en GF(2^8^) |
| `n − k` | Bytes de paridad (capacidad de corrección) |
| `r = (n−k)/n` | Ratio de redundancia — controla cuánta pérdida se tolera |

**Capacidad de corrección en modo erasure:** si `r = 0.30`, el sistema tolera hasta un 30% de
paquetes perdidos por bloque y los reconstruye sin errores.

## Del slider al parámetro RS

El usuario selecciona un nivel de redundancia `r ∈ [0.05, 0.50]`. El sistema determina
automáticamente los parámetros:

```
n = 32   (tamaño de bloque estándar)
k = round(n × (1 − r))
k = clamp(k, mín=4, máx=n−1)
```

| Preset | r | n | k | Paridad | Overhead | Pérdida tolerable |
|---|---|---|---|---|---|---|
| Rápido | 0.10 | 32 | 29 | 3 | 10% | 10% |
| Balanceado | 0.25 | 32 | 24 | 8 | 33% | 25% |
| Resiliente | 0.50 | 32 | 16 | 16 | 100% | 50% |

El valor de `r` puede ser fijado manualmente por el usuario o determinado automáticamente por
el sistema de redundancia adaptativa (ver sección 5).

## Flujo de codificación y decodificación

El archivo se divide en bloques de `k` bytes. Cada bloque se codifica con RS para obtener `n`
bytes (incluida la paridad). Cada bloque codificado se envía como un datagrama UDP. En el
receptor, los bloques que llegan se decodifican con RS; los que faltan se marcan como erasures
y se reconstruyen algebraicamente.

![Flujo del algoritmo Reed-Solomon](img/rs_algorithm.png)

## Verificación de integridad

El emisor calcula el **SHA-256** del archivo original antes de codificarlo y lo envía junto con la
solicitud de transferencia. El receptor verifica el checksum sobre los bytes reconstruidos:

| Resultado | Condición |
|---|---|
| `ok` | Todos los bloques llegaron, SHA-256 coincide |
| `degraded` | Pérdidas recuperadas por RS, SHA-256 coincide — el archivo es íntegro |
| `failed` | Pérdidas superan la capacidad RS, o SHA-256 no coincide |

\newpage

# Arquitectura del Sistema

## Plano de control vs. plano de datos

El diseño central de RockDove separa la coordinación de la transferencia en dos planos
completamente independientes:

**Plano de control — servidor central (una instancia en cloud):**
gestiona identidad, presencia de peers y telemetría de red. **Nunca toca archivos ni interviene
en la transferencia.**

**Plano de datos — agente por máquina:**
cada participante corre un agente local que realiza RS encoding/decoding, maneja el socket UDP
y almacena archivos en el filesystem local.

El dato transferido **nunca pasa por el servidor**. El servidor solo responde a dos preguntas:
*"¿dónde está el peer B?"* y *"¿qué redundancia conviene según la red actual?"*
La transferencia es directa, máquina a máquina, sobre UDP.

```
Una instancia cloud:    Servidor RockDove — coordinación + métricas
Cada máquina de usuario: Agente Python + interfaz Electron
Dispositivos IoT/edge:   Agente Python headless en Docker
```

## Analogía: servidor de coordinación estilo Tailscale

El patrón es idéntico al de herramientas como **Tailscale** o **Syncthing**:

| Componente | Tailscale | RockDove |
|---|---|---|
| Servidor de coordinación | `login.tailscale.com` | Servidor central (cloud) |
| Lo que ve el servidor | Claves públicas, IPs | Peer IDs, IPs UDP, métricas de red |
| Lo que NO ve el servidor | Tráfico de red | Archivos transferidos |
| Comunicación entre peers | WireGuard directo | UDP + Reed-Solomon directo |
| Descubrimiento de peers | DERP / coordination server | `/peers/register` + WebSocket push |

En Tailscale el coordination server permite que dos dispositivos en redes distintas establezcan
un túnel directo. En RockDove, el servidor central permite que dos peers se encuentren y luego
transfieran archivos **directamente por UDP** sin intermediarios.

## Diagrama de infraestructura

![Diagrama de arquitectura del sistema](img/architecture.png)

El diagrama muestra tres tipos de participantes: peers desktop (Electron + agente Python),
nodos edge headless (Docker), y el servidor central con sus servicios internos (Redis, Keycloak).
Las flechas continuas representan comunicación HTTPS con el servidor; la flecha gruesa entre peers
representa la transferencia UDP directa de bloques Reed-Solomon.

\newpage

# Servidor de Rendezvous

El servidor central actúa como **punto de encuentro** (*rendezvous server*): permite que los peers
se encuentren en la red sin conocerse de antemano, y recoge telemetría para alimentar el sistema
de redundancia adaptativa. Está implementado en **Python 3.12 + FastAPI**, expone el puerto 8080,
y persiste todo su estado en **Redis**.

## Registro de peers y presencia

Cuando un agente arranca:

1. Llama a `POST /peers/register` con `{peer_id, udp_host, udp_port, api_url, network_hint}`.
2. El servidor almacena el registro como un **hash en Redis** con TTL = 30 segundos.
3. El servidor transmite inmediatamente el snapshot actualizado a todos los observadores WebSocket.
4. El agente inicia un **heartbeat loop** cada 15 segundos (`POST /peers/{id}/heartbeat`).
5. El heartbeat renueva el TTL del hash. Si el peer deja de latir, Redis expira la clave
   automáticamente y la próxima broadcast lo omite.

Si el servidor se reinicia, Redis recupera todos los peers registrados (el estado persiste).
Si un peer reinicia, detecta el 404 en el próximo heartbeat y se re-registra automáticamente.

## Autodescubrimiento en tiempo real: WebSocket push

La UI React se conecta a `GET /peers/watch` mediante WebSocket permanente. El servidor hace
broadcast de la lista completa cada vez que hay un cambio (registro, heartbeat, expiración).
Esto significa que cuando un colega abre RockDove en otra máquina, aparece en el dashboard en
menos de un segundo, sin polling.

| Evento | Acción del servidor |
|---|---|
| Nuevo peer se registra | broadcast snapshot completo |
| Heartbeat recibido | broadcast (actualiza `last_seen`) |
| Peer expira por timeout | broadcast (el peer desaparece de la lista) |
| UI se conecta por primera vez | envía snapshot inmediato |

## Resolución de dirección para transferencia

Cuando el agente A quiere transferir a B:

1. Consulta **una sola vez** al servidor: `GET /peers/B`
2. El servidor responde con `{udp_host, udp_port}` — la dirección donde B escucha UDP.
3. A partir de ahí, A envía los bloques RS **directamente** al socket UDP de B.
4. El servidor no interviene en el resto.

![Flujo de coordinación y autodescubrimiento](img/peer_discovery.png)

## Persistencia con Redis

Todos los datos del servidor se almacenan en **Redis**:

| Dato | Clave Redis | Estructura | TTL |
|---|---|---|---|
| Peer registrado | `peer:{org}:{id}` | Hash | 30 s (heartbeat) |
| Métricas por peer | `metrics:{peer_id}` | List (últimas 10) | Sin expiración |
| Device token | `device_token:{valor}` | Hash | Según configuración |
| Scopes de grupo | `scope:{org_id}` | String JSON | Sin expiración |

Esta arquitectura garantiza que un reinicio del servidor no pierde datos: los peers re-registran
en el próximo heartbeat; las métricas acumuladas y los device tokens persisten.

\newpage

# Capa de Transporte UDP/QUIC

## Abstracción de transporte

El agente abstrae el protocolo de red detrás de una interfaz común `BaseTransport` con cuatro
operaciones: `start`, `send`, `collect` y `stop`. Las dos implementaciones concretas son
intercambiables mediante la variable de entorno `TRANSPORT_MODE`:

| Modo | Clase | Características |
|---|---|---|
| `udp` (default) | `UDPTransport` | Socket asyncio raw, sin TLS, latencia mínima |
| `quic` | `QUICTransport` | aioquic sobre el mismo puerto UDP, TLS 1.3, DATAGRAM frames RFC 9221 |

El cambio de modo requiere reinicio del agente. El peer anuncia su modo activo en el registro
(`POST /peers/register`), y la UI muestra un badge UDP o QUIC en la lista de peers. Si los modos
no coinciden entre emisor y receptor, la transferencia falla con error descriptivo.

## Modo QUIC: bloques RS sobre DATAGRAM frames

La extensión DATAGRAM de QUIC (RFC 9221) provee frames sin retransmisión dentro de una sesión
QUIC con TLS 1.3. Esto es exactamente la semántica necesaria para Reed-Solomon: los paquetes
individuales pueden perderse (el FEC los recupera), pero la sesión está cifrada y autenticada.

Cada bloque RS se envía como un DATAGRAM frame independiente. El tamaño de cada frame debe
mantenerse por debajo del MTU QUIC (≈ 1164 bytes disponibles), lo que en la práctica limita el
tamaño efectivo de bloque a ≈ 1 KB.

Al arrancar con `TRANSPORT_MODE=quic`, el agente genera automáticamente un certificado TLS
autofirmado (RSA-2048, validez 10 años) con `CN=rockdove-{PEER_ID}` y lo almacena en
`STORAGE_PATH/quic_cert.pem`. Si el `PEER_ID` cambia entre arranques, el certificado anterior
se descarta y se regenera con el nuevo CN.

## Protocolo CERT_HELLO: identidad de peer en QUIC

Antes de enviar los bloques RS, el emisor envía un datagrama especial de 98+ bytes denominado
**CERT_HELLO**, que transporta la identidad criptográfica del emisor:

```
Offset  Tamaño  Campo
──────  ──────  ─────────────────────────────────────────────────
0       4       Magic RDCH  (0x52 0x44 0x43 0x48)
4       1       Versión     (0x01)
5       1       Longitud del peer_id
6       N       peer_id     (UTF-8, N ≤ 63 bytes)
6+N     16      transfer_id (bytes del UUID)
22+N    64      SHA-256 del certificado PEM del emisor (hex ASCII)
```

El receptor identifica el CERT_HELLO por el magic `RDCH` y, antes de procesar cualquier bloque
RS, registra la conexión como **pendiente** con los campos extraídos.

## Flujo de aprobación de conexiones entrantes

```
Emisor A                     Receptor B
────────                     ──────────
send CERT_HELLO ──────────► _on_quic_connect() registra en _pending_conns
send RS blocks  ──────────► wait_for_approval() espera hasta 30 s
                             ▲
                UI B: banner "Conexión QUIC entrante"
                             │ operador hace clic en Aceptar
                             ▼
                          approve_connection() → aprueba
collect(blocks) ◄──────────  continúa con collect() normal
```

Si el operador no interactúa en 30 segundos, la conexión **se aprueba automáticamente** para
no bloquear transferencias en entornos desatendidos. Si el operador rechaza, los bloques RS
recibidos se descartan y la transferencia queda en estado `failed` con razón `rejected_by_operator`.

## API REST de conexiones entrantes

Los siguientes endpoints permiten a la UI consultar y actuar sobre las conexiones pendientes:

| Endpoint | Descripción |
|---|---|
| `GET /transfer/incoming` | Lista conexiones QUIC pendientes con peer_id, cert CN y fingerprint |
| `POST /transfer/incoming/{tid}/accept` | Aprueba la conexión — los bloques RS se procesan |
| `POST /transfer/incoming/{tid}/reject` | Rechaza — el buffer se descarta |

La UI consulta `GET /transfer/incoming` cada 3 segundos y muestra un banner flotante por cada
conexión pendiente, con el peer_id, el Common Name del certificado y el SHA-256 del PEM
(colapsable para ver el fingerprint completo).

\newpage

# Redundancia Adaptativa

## Motivación

Un nivel de redundancia fijo ignora las condiciones reales de la red. Demasiado bajo en un link
degradado produce transferencias fallidas. Demasiado alto en una LAN desperdicia ancho de banda.
El sistema mide condiciones de red continuamente y ajusta el default del slider en cada
transferencia.

## Ciclo de medición y recomendación

Dos fuentes de datos alimentan el sistema:

**Sonda RTT en background:** el agente ejecuta un loop cada 60 segundos que mide la latencia HTTP
hacia cada peer online (5 pings, promedio + jitter). Los resultados se reportan al servidor vía
`POST /metrics/report`.

**Métricas de transferencia:** al finalizar cada envío, el agente calcula la tasa de pérdida real
(`recovered_blocks / total_blocks`) y el tiempo total de transmisión, y los reporta al servidor.

El servidor mantiene las **últimas 10 muestras** por peer en Redis. Al recibir una solicitud de
recomendación, promedia esas muestras y aplica la tabla de calidad:

![Sistema de redundancia adaptativa](img/adaptive_redundancy.png)

## Tabla de calidad de red

| Calidad | Pérdida | RTT | Jitter | Redundancia sugerida |
|---|---|---|---|---|
| Excellent | < 1% | < 50 ms | < 5 ms | 5% |
| Good | < 5% | < 150 ms | < 20 ms | 10% |
| Fair | < 15% | < 500 ms | < 80 ms | 25% |
| Poor | < 30% | < 1000 ms | < 200 ms | 40% |
| Critical | cualquier peor | — | — | 50% |

## Recomendación dual: emisor y receptor

Antes de cada transferencia, el agente emisor consulta la recomendación para **ambos extremos**
del enlace en paralelo:

```
rec_emisor  = GET /metrics/recommendation/{mi_peer_id}
rec_receptor = GET /metrics/recommendation/{target_peer_id}

redundancia_efectiva = max(rec_emisor, rec_receptor)
```

Si cualquiera de los dos extremos tiene condiciones de red degradadas, la redundancia se eleva
para proteger la transferencia. El resultado (nivel efectivo, calidad y perfil de red) se incluye
en la respuesta de la transferencia para que la UI lo muestre al usuario.

## Comportamiento en la UI

Al abrir el diálogo de transferencia, el agente consulta la recomendación y precarga el slider con
el valor sugerido. El usuario puede ajustar manualmente. Si no hay datos de métricas acumulados
aún (primer uso), el sistema usa **0.25 (25%)** como fallback conservador.

\newpage

# Autenticación y Control de Acceso

El sistema soporta tres modalidades de autenticación que pueden coexistir en el mismo despliegue:

## Modo desarrollo (sin OIDC)

Cuando `OIDC_ENABLED=false`, cualquier peer puede registrarse sin credenciales. Todos los peers
quedan en la misma organización (`dev`) y se ven entre sí. Apropiado para desarrollo local y
pruebas de concepto.

## Autenticación OIDC con Keycloak (usuarios humanos)

En producción, el sistema integra con **Keycloak** como proveedor de identidad OpenID Connect.
El flujo utiliza PKCE (*Proof Key for Code Exchange*), que permite autenticación segura desde
una aplicación de escritorio:

1. El usuario hace clic en "Iniciar sesión" en la UI.
2. La app genera la URL de autorización con PKCE y la abre en el **browser del sistema**.
3. El usuario se autentica en Keycloak. El browser redirige a `http://127.0.0.1:8000/auth/callback`.
4. El agente local recibe el código de autorización.
5. La UI completa el intercambio código → JWT via `signinCallback()`.
6. La UI entrega el JWT al agente (`POST /auth/token`). El agente lo usa para re-registrarse.

El **JWT de Keycloak** contiene `sub` (→ peer_id), `iss` (→ org_id derivado del realm), y
`groups` (→ grupos del usuario). La aislación multi-tenant se implementa por realm: peers de
distintas organizaciones no se ven entre sí aunque compartan el mismo servidor central.

## Device tokens para agentes headless

Para dispositivos IoT y nodos edge que no tienen usuario interactivo, el sistema provee
**device tokens**: credenciales autogeneradas por el servidor, únicas por dispositivo,
almacenadas en Redis y revocables en cualquier momento desde el panel de administración.

### Formato del token

```
rd_<43 caracteres Base64URL>   (256 bits de entropía)
```

El valor es generado por el servidor con `secrets.token_urlsafe(32)`. El prefijo `rd_` permite
identificarlo visualmente. El valor completo solo se muestra una vez, en el momento de creación.

### Ciclo de vida

| Estado | Cómo ocurre |
|---|---|
| Activo | Inmediatamente después de la creación |
| Expirado | Automáticamente cuando Redis expira las claves (TTL configurado en días) |
| Revocado | Admin llama `DELETE /device-tokens/{id}` — efecto inmediato |

Los tokens pueden ser **temporales** (con TTL en días) o **indefinidos** (sin expiración). Redis
expira automáticamente los tokens temporales sin necesidad de tareas programadas.

### Flujo de autenticación de un dispositivo headless

![Flujo de autenticación OIDC y device tokens](img/auth_flow.png)

El administrador crea el token desde el panel, lo comunica al operador del dispositivo, y el
operador lo configura como variable de entorno. A partir de ahí, el agente headless se registra
y mantiene su heartbeat usando el token como Bearer en cada request.

## Gestión de grupos y scopes

El sistema implementa aislación a dos niveles dentro de una organización:

**Nivel 1 — org_id:** derivado del realm de Keycloak. Los peers de distintos realms son
completamente invisibles entre sí.

**Nivel 2 — grupos:** dentro de una misma org, el administrador configura qué grupos pueden
verse entre sí. El centinela `__all__` otorga visibilidad sobre toda la org (para usuarios admin).

\newpage

# Flujos de Usuario

## Flujo principal: arranque, carga y transferencia

El siguiente diagrama muestra las tres operaciones centrales: registro del peer al arrancar la
app, subida de un archivo al almacenamiento local del agente, y transferencia P2P con redundancia
adaptativa.

![Flujo de interacción del usuario](img/user_flow.png)

## Historial de transferencias

Cada transferencia (enviada o recibida) queda registrada en una base de datos **SQLite local**
del agente (`transfers.db`). El historial persiste entre reinicios de la aplicación. La UI
consume `GET /transfer/history?limit=50` para mostrar las transferencias pasadas con sus
metadatos: peer destino, archivo, bytes, estado, redundancia efectiva, calidad de red y timestamp.

## Flujo para nodo headless (IoT / edge)

Un nodo edge corre el agente en Docker sin interfaz web. La transferencia puede iniciarse desde
cualquier peer desktop que tenga al nodo edge en su lista. El nodo edge:

1. Se registra con su device token al arrancar el contenedor.
2. Mantiene heartbeat automático cada 15 segundos.
3. Recibe transferencias UDP entrantes y las almacena localmente.
4. Aparece como peer online en el dashboard de los usuarios desktop.

No requiere ninguna interacción manual una vez desplegado.

\newpage

# Componentes del Sistema

## Servidor Central

| Atributo | Valor |
|---|---|
| Runtime | Python 3.12 + FastAPI |
| Puerto | 8080 TCP |
| Persistencia | Redis 7 |
| Auth | Keycloak 24 (OIDC, opcional) |
| Deploy | Docker Compose |

**Módulos principales:**

| Módulo | Responsabilidad |
|---|---|
| `peers/` | Registro, heartbeat, resolución de dirección, WebSocket push |
| `metrics/` | Recolección de telemetría, cálculo de recomendaciones |
| `device_tokens/` | Creación, listado y revocación de tokens por dispositivo |
| `invites/` | Tokens de invitación de un solo uso para incorporación peer-a-peer |
| `auth/` | Validación de JWT via JWKS de Keycloak, extracción de org_id y groups |

## Agente Local

| Atributo | Valor |
|---|---|
| Runtime | Python 3.12 + FastAPI |
| Puerto HTTP | 8000 |
| Puerto UDP | 9001 |
| Almacenamiento | Filesystem local + SQLite |
| Deploy | AppImage (desktop) o Docker (headless) |

**Módulos principales:**

| Módulo | Responsabilidad |
|---|---|
| `rs/encoder.py` | Segmentación en bloques, RS encode, construcción de datagramas UDP |
| `rs/decoder.py` | Colección de bloques recibidos, RS decode con erasure positions, SHA-256 |
| `rs/transport.py` | Capa de transporte — `BaseTransport` (ABC), `UDPTransport` (UDP raw), `QUICTransport` (aioquic + TLS 1.3 + identidad de peer) |
| `storage/store.py` | Almacenamiento local de archivos con checksum SHA-256 |
| `storage/db.py` | Historial de transferencias en SQLite via aiosqlite |
| `metrics/probe.py` | Sonda RTT/jitter en background cada 60 segundos |
| `server_client.py` | Toda la comunicación HTTP con el servidor central |
| `transfers/router.py` | Endpoints `/transfer/*` — envío, recepción, historial |

## Interfaz Electron (Desktop)

El proceso principal de Electron:

1. Inicia el agente Python como proceso hijo y espera a que `/health` responda.
2. Carga la React SPA desde los recursos embebidos del binario.
3. Expone `window.rsAgent.baseUrl` al renderer via `contextBridge` (sin IPC para calls de API).

La UI React (Vite + Tailwind CSS) se comunica exclusivamente con el agente local en
`127.0.0.1:8000`. No hay llamadas directas al servidor central desde el frontend.

\newpage

# Infraestructura y Deployment

## Servidor central (Docker Compose)

```bash
cd server && docker compose up --build
```

El compose incluye tres servicios:

| Servicio | Imagen | Puerto |
|---|---|---|
| `server` | Build local (Python + FastAPI) | 8080 TCP |
| `redis` | redis:7-alpine | 6379 TCP |
| `keycloak` | keycloak:24 | 8081 TCP (opcional) |

## Cliente desktop (AppImage / ejecutable)

El cliente se distribuye como un ejecutable standalone generado con **electron-builder**:

| Plataforma | Artefacto |
|---|---|
| Linux | `.AppImage` (autocontenido) |
| Windows | Instalador NSIS `.exe` |
| macOS | `.dmg` |

El artefacto incluye: shell Electron, React UI compilada, y agente Python congelado con
**PyInstaller**. No requiere Python, Node ni ninguna dependencia preinstalada en el dispositivo
del usuario final.

```bash
cd client
./scripts/build-agent.sh   # PyInstaller → agente congelado
npm run dist:local          # electron-builder → AppImage
```

## Nodo headless (IoT / edge)

Dos opciones de despliegue para dispositivos sin interfaz gráfica:

**Docker Compose (recomendado):**

```bash
# .env del dispositivo (generado por el admin panel)
PEER_ID=sensor-planta-a
SERVER_URL=http://servidor:8080
AGENT_API_URL=http://192.168.1.50:8000
AGENT_SERVICE_TOKEN=rd_xK3mAb9dQpWnLcVt...

docker compose -f docker-compose.headless.yml up -d
```

**Binario AppImage (sin Docker):**

```bash
PEER_ID=sensor-a \
SERVER_URL=http://servidor:8080 \
AGENT_SERVICE_TOKEN=rd_xK3m... \
./rockdove-agent.AppImage
```

El agente headless se registra automáticamente al arrancar, mantiene heartbeat, y si el servidor
se reinicia se vuelve a registrar en el próximo ciclo sin intervención humana.

## Variables de configuración del agente

| Variable | Descripción | Default |
|---|---|---|
| `SERVER_URL` | URL del servidor central | `http://localhost:8080` |
| `PEER_ID` | Identificador único de este peer | `default-peer` |
| `AGENT_API_URL` | URL HTTP pública de este agente (registrada en el servidor) | autodetectada |
| `UDP_PORT` | Puerto UDP/QUIC para recibir bloques RS | `9001` |
| `TRANSPORT_MODE` | Protocolo de transporte: `udp` (raw) o `quic` (TLS 1.3) | `udp` |
| `STORAGE_PATH` | Ruta de almacenamiento local | `~/.local/share/rockdove` |
| `AGENT_SERVICE_TOKEN` | Device token autogenerado por el admin | vacío |
| `NETWORK_HINT` | Perfil de red: `lan`, `wifi`, `cellular`, `satellite`, `auto` | `auto` |

## Consideraciones de red

El puerto **9001 UDP debe ser accesible entre peers** para recibir transferencias. Si hay NAT,
se necesita port forwarding o que ambos peers estén en la misma red (o VPN).

La variable `AGENT_API_URL` debe apuntar a la **IP alcanzable por los otros peers**, no a
`127.0.0.1`. Es la dirección que el servidor entrega a otros peers cuando la consultan.

El servidor central solo requiere **8080 TCP** abierto. No necesita acceso UDP.

\newpage

# Stack Tecnológico

| Capa | Tecnología | Versión | Rol |
|---|---|---|---|
| Servidor central | Python + FastAPI | 3.12 / 0.115 | API REST + WebSocket |
| Persistencia servidor | Redis | 7 | Peers, métricas, device tokens |
| Auth / SSO | Keycloak | 24 | OIDC, multi-tenant, PKCE |
| Agente local | Python + FastAPI | 3.12 / 0.115 | RS engine, UDP, storage |
| FEC | reedsolo | 1.7 | Reed-Solomon GF(2^8^) |
| HTTP client (agente) | httpx | 0.28 | Llamadas async al servidor |
| Historial transferencias | aiosqlite | 0.22 | SQLite async en el agente |
| Shell desktop | Electron | 33 | Empaquetado + spawn del agente |
| UI | React + Vite + Tailwind CSS | 18 / 5 / 3 | SPA cargada por Electron |
| Empaquetado agente | PyInstaller | 6 | Congela Python en binario |
| Empaquetado desktop | electron-builder | 25 | Genera AppImage / exe / dmg |
| Gestión deps Python | uv | latest | Lockfile reproducible |
| Contenedores | Docker + Compose | 27 | Servidor + nodos headless |

## Librerías clave del servidor

| Librería | Uso |
|---|---|
| `fastapi` | Framework HTTP + WebSocket + validación automática via Pydantic |
| `redis[asyncio]` | Cliente Redis async para persistencia de peers y métricas |
| `PyJWT[crypto]` | Validación de JWTs de Keycloak (RS256, JWKS fetch) |
| `pydantic-settings` | Configuración via variables de entorno con tipos |

## Librerías clave del agente

| Librería | Uso |
|---|---|
| `reedsolo` | Implementación de Reed-Solomon en GF(2^8^) |
| `httpx` | Cliente HTTP async para comunicación con el servidor |
| `aiosqlite` | Historial persistente de transferencias en SQLite |
| `pydantic-settings` | Configuración via `.env` o variables de entorno |
| `uvicorn` | Servidor ASGI para la API local del agente |
| `aioquic` | Transporte QUIC (RFC 9000) con DATAGRAM extension (RFC 9221) para bloques RS |
| `cryptography` | Generación de certificados TLS autofirmados para el transporte QUIC |
