---
title: "RockDove — Sistema P2P con Reed-Solomon"
subtitle: "Especificación Técnica y Arquitectura"
author: "Redes de Datos II"
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

## ¿Qué es?

**RockDove** es una plataforma de transferencia de archivos entre pares (*peer-to-peer*) que utiliza el algoritmo de corrección de errores **Reed-Solomon** sobre **UDP** para garantizar la integridad de los datos incluso en redes con pérdida de paquetes.

El sistema está pensado para dos escenarios principales:

- **Transferencia entre usuarios:** dos o más usuarios pueden enviarse archivos directamente entre sus máquinas, con garantía de integridad aunque se pierdan paquetes en el camino.
- **Ingesta a dispositivos edge:** envío de datos desde una máquina remota hacia un nodo con conectividad degradada (celular, satelital, IoT), donde la retransmisión es costosa o imposible.

## ¿Qué problema resuelve?

UDP no garantiza entrega ni orden de paquetes. En redes inestables, una transferencia sin protección resulta en datos corruptos o incompletos. Las alternativas clásicas son:

- **TCP:** garantiza entrega pero requiere retransmisión, costosa en links de alta latencia o intermitentes.
- **Ignorar la pérdida:** simple pero inaceptable para archivos.

Este sistema aplica **corrección de errores hacia adelante** (*Forward Error Correction*, FEC) mediante Reed-Solomon: el emisor agrega redundancia matemática al dato antes de enviarlo. El receptor puede reconstruir el original aunque lleguen menos paquetes de los enviados, **sin necesidad de retransmisión**.

## Casos de uso

| Caso | Descripción |
|------|-------------|
| Transferencia intra-org | Usuario A envía un archivo a Usuario B dentro de la misma organización |
| Transferencia a edge | Operador envía configuración a un nodo remoto con link degradado |
| Verificación de integridad | Sistema reporta si el archivo llegó íntegro (`ok`), con errores recuperados (`degraded`) o irrecuperable (`failed`) |

\newpage

# Algoritmo Reed-Solomon

## ¿Qué hace?

Reed-Solomon opera sobre bloques de datos. Dado un bloque de **k** símbolos originales, el codificador produce **n** símbolos totales (k originales + n−k de paridad). El receptor puede reconstruir los k originales a partir de **cualquier combinación de k de los n símbolos**, aunque los n−k restantes se hayan perdido.

Cada símbolo es un byte. El campo matemático utilizado es **GF(2^8^)** (campo de Galois de 256 elementos), estándar para RS en sistemas digitales.

## Parámetros RS(n, k)

| Símbolo | Significado |
|---------|-------------|
| `k` | Bytes originales por bloque |
| `n` | Bytes totales después de codificar (k + paridad) |
| `n − k` | Bytes de paridad (redundancia) |
| `r = (n−k)/n` | Ratio de redundancia |

**Capacidad de recuperación:** en UDP se sabe exactamente qué paquetes llegaron (erasures). RS puede recuperar hasta `n − k` pérdidas por bloque, equivalente a tolerar un `r × 100%` de pérdida de paquetes.

## Relación entre el slider y los parámetros RS

El usuario configura la redundancia mediante un valor `r ∈ [0.05, 0.50]`. El sistema deriva los parámetros automáticamente:

```
n = 32  (tamaño de bloque fijo)
k = round(n × (1 − r))
k = clamp(k, 4, n−1)
```

| Preset | r | n | k | Paridad | Overhead | Tolera pérdida |
|--------|---|---|---|---------|----------|----------------|
| Rápido | 0.10 | 32 | 29 | 3 | 10% | 10% |
| Balanceado | 0.25 | 32 | 24 | 8 | 33% | 25% |
| Resiliente | 0.50 | 32 | 16 | 16 | 100% | 50% |

## Flujo del algoritmo

El siguiente diagrama ilustra el ciclo completo: codificación en el emisor, transmisión UDP con posible pérdida, decodificación en el receptor y verificación de integridad.

![Flujo del algoritmo Reed-Solomon](img/rs_algorithm.png)

\newpage

# Arquitectura del Sistema

## Modelo de deployment: plano de control vs. plano de datos

**Este es el punto central del diseño.**

El sistema se divide en dos planos completamente independientes:

**Plano de control — servidor central (una sola instancia en cloud):**
gestiona identidad, registro de peers y telemetría. **Nunca toca datos de archivos ni está en el camino de las transferencias.**

**Plano de datos — agente por máquina:**
cada participante corre un agente local que realiza el RS encoding/decoding, maneja el socket UDP y almacena archivos en el filesystem local.

```
Cloud (una instancia):   servidor RockDove — coordinación + métricas
Cada máquina:            agente Python + UI Electron (o Docker headless)
```

El dato transferido **nunca pasa por el servidor**. El servidor solo responde: *"¿dónde está el peer B?"* y *"¿qué redundancia te conviene según la red actual?"*. La transferencia es directa, máquina a máquina, sobre UDP.

![Diagrama de arquitectura del sistema](img/architecture.png)

## Analogía: servidor de coordinación estilo Tailscale

El patrón arquitectónico es idéntico al que usan herramientas como **Tailscale** o **Syncthing**:

| Componente | Tailscale | RockDove |
|------------|-----------|----------|
| Servidor de coordinación | `login.tailscale.com` | Servidor central (cloud) |
| Dato que ve el servidor | Claves públicas, IPs | Peer IDs, IPs UDP, métricas |
| Dato que NO ve el servidor | Tráfico de red | Archivos transferidos |
| Comunicación entre peers | WireGuard directo | UDP + Reed-Solomon directo |
| Descubrimiento | DERP / coord server | `/peers/register` + WS push |

En Tailscale, el coordination server permite que dos dispositivos en redes distintas se encuentren y establezcan un túnel directo. En RockDove, el servidor central permite que dos peers se encuentren y luego se transfieran archivos **directamente por UDP** sin intermediarios.

\newpage

# Coordinación P2P y Autodescubrimiento

## El problema del descubrimiento en P2P

En una red P2P pura, cada peer necesita saber la dirección IP y puerto de los demás antes de poder comunicarse. Sin un punto de encuentro, esto requiere flooding, multicast o configuración manual — todos con limitaciones en redes reales (NAT, firewalls, redes distintas).

RockDove resuelve esto con un **servidor de rendezvous** (punto de encuentro) centralizado: cada peer anuncia su presencia y dirección UDP al servidor, y puede consultar la dirección de cualquier otro peer registrado.

## Registro y presencia

Cuando un agente arranca:

1. Llama a `POST /peers/register` con su `{peer_id, udp_host, udp_port, api_url}`.
2. El servidor almacena el registro y lo marca como **online**.
3. El servidor **transmite inmediatamente** la lista actualizada a todos los observadores WebSocket.
4. El agente inicia un **loop de heartbeat** cada 15 segundos (`POST /peers/{id}/heartbeat`).
5. Un peer sin heartbeat por más de 30 segundos se marca **offline** automáticamente.

## Autodescubrimiento en tiempo real: WebSocket push

La UI React se conecta al endpoint `GET /peers/watch` del servidor mediante WebSocket. Esto permite que el dashboard refleje el estado de la red **sin polling**:

| Evento | Lo que hace el servidor |
|--------|------------------------|
| Nuevo peer se registra | broadcast lista completa a todos los watchers |
| Heartbeat recibido | broadcast (actualiza `last_seen`) |
| Peer desaparece (timeout) | broadcast (marca offline) |
| UI se conecta por primera vez | envía snapshot inmediato del estado actual |

Esto significa que cuando un colega abre RockDove en otra máquina, aparece automáticamente en tu dashboard en menos de un segundo, sin que tengas que hacer nada.

![Flujo de coordinación y autodescubrimiento](img/peer_discovery.png)

## Resolución de dirección para transferencia

Cuando el agente A quiere enviar un archivo al peer B:

1. Consulta **una sola vez** al servidor: `GET /peers/B`
2. El servidor responde con `{udp_host, udp_port}` — la dirección donde B escucha UDP.
3. A partir de ese momento, A envía los bloques RS **directamente** al socket UDP de B.
4. El servidor no interviene en el resto de la transferencia.

```
A ──► GET /peers/B ──► Servidor
      {udp_host, udp_port} ◄──

A ════════════════════════════► B   (UDP directo, sin pasar por servidor)
     bloques Reed-Solomon
```

## Consideraciones de NAT y red

Para que el descubrimiento funcione en redes reales:

- El **puerto UDP 9001 debe ser accesible** desde el exterior (o desde los otros peers). Si hay NAT, se necesita port forwarding o que ambos peers estén en la misma red.
- La variable `AGENT_API_URL` debe contener la **IP pública o accesible** del host, no `127.0.0.1`. Es la dirección que se registra en el servidor y que otros peers usarán para contactar.
- El servidor central solo necesita el **puerto 8080 TCP** abierto. No necesita acceso UDP.

> **Trabajo futuro:** implementar NAT traversal mediante UDP hole punching (técnica usada por WebRTC). El servidor actuaría como signaling server para coordinar el hole punching y permitir comunicación P2P incluso detrás de NAT estricto.

\newpage

# Flujo de Interacción del Usuario

El siguiente diagrama de secuencia muestra las tres operaciones principales: arranque con registro, subida de archivo al almacenamiento local, y transferencia P2P con redundancia adaptativa.

![Flujo de interacción del usuario](img/user_flow.png)

## Estados de resultado de una transferencia

| Estado | Condición |
|--------|-----------|
| `ok` | Todos los bloques llegaron, SHA-256 coincide |
| `degraded` | Pérdidas recuperadas por RS, SHA-256 coincide |
| `failed` | Pérdidas superan capacidad RS, o SHA-256 no coincide |

\newpage

# Componentes del Sistema

## Servidor Central (`server/`)

| Atributo | Valor |
|----------|-------|
| Tecnología | Python 3.12 + FastAPI |
| Puerto | 8080 TCP |
| Deploy | Docker Compose, instancia única compartida |

El servidor expone tres responsabilidades:

**Registro de peers (`/peers`):** almacena `{peer_id, udp_host, udp_port, last_seen}`. Provee el endpoint WebSocket `/peers/watch` para push en tiempo real.

**Métricas y recomendador (`/metrics`):** recibe reportes de RTT, jitter y pérdida. Promedia las últimas 10 muestras y calcula un `redundancy_level` recomendado.

**Configuración de autenticación (`/auth/config`):** informa a la UI si OIDC está habilitado. Permite futura integración con Keycloak sin cambios en el cliente.

## Agente (`client/agent/`)

| Atributo | Valor |
|----------|-------|
| Tecnología | Python 3.12 + FastAPI |
| Puerto HTTP | 8000 |
| Puerto UDP | 9001 |
| Deploy | Electron (desktop) o Docker headless (IoT/edge) |

El agente es el peer UDP real. Mantiene el socket UDP abierto, codifica y decodifica bloques RS, y envía/recibe datagramas directamente.

| Módulo | Responsabilidad |
|--------|----------------|
| `rs/encoder.py` | RS encode, segmentación columnar, construcción de paquetes UDP |
| `rs/decoder.py` | RS decode con erasure positions, verificación SHA-256 |
| `rs/transport.py` | Socket UDP, envío/recepción de datagramas |
| `storage/store.py` | Almacenamiento local de archivos con checksum |
| `server_client.py` | Toda la comunicación HTTP con el servidor central |
| `transfers/router.py` | Endpoints `/transfers/*` |

## Shell Electron (`client/electron/`)

El proceso principal de Electron:

1. Spawna el agente Python como proceso hijo (`127.0.0.1:8000`), o en producción ejecuta el binario congelado con PyInstaller.
2. Espera a que `/health` responda antes de abrir la ventana (polling, máximo 20 segundos).
3. Carga la UI React desde los recursos embebidos (`extraResources` de electron-builder).
4. Expone `window.rsAgent.baseUrl` al renderer via `contextBridge`.

## Nodo Edge / IoT

Para dispositivos con recursos limitados (Raspberry Pi, nodos industriales). El agente corre en Docker sin interfaz web, configurado puramente por variables de entorno.

```bash
docker run \
  -e PEER_ID=edge-01 \
  -e SERVER_URL=http://servidor:8080 \
  -e AGENT_API_URL=http://192.168.1.50:8000 \
  -p 8000:8000 -p 9001:9001/udp \
  rs-agent
```

\newpage

# Redundancia Adaptativa

## Motivación

Un nivel de redundancia demasiado bajo en una red inestable produce transferencias fallidas. Un nivel demasiado alto en una red estable desperdicia ancho de banda. El sistema mide condiciones de red en tiempo real y ajusta el valor por defecto del slider automáticamente.

## Flujo de recomendación

![Sistema de redundancia adaptativa](img/adaptive_redundancy.png)

## Tabla de calidad → redundancia

| Calidad | Pérdida | RTT | Jitter | Redundancia sugerida |
|---------|---------|-----|--------|----------------------|
| Excellent | < 1% | < 50 ms | < 5 ms | 5% |
| Good | < 5% | < 150 ms | < 20 ms | 10% |
| Fair | < 15% | < 500 ms | < 80 ms | 25% |
| Poor | < 30% | < 1000 ms | < 200 ms | 40% |
| Critical | cualquier peor | — | — | 50% |

## Comportamiento en la UI

Al abrir el diálogo de transferencia, el agente consulta `GET /metrics/recommendation/{peer_id}` y precarga el slider con el valor recomendado. El usuario puede sobreescribir el valor manualmente y restablecer la recomendación con un botón. Si el servidor no está disponible, el agente usa **25%** como fallback conservador.

\newpage

# Infraestructura y Deployment

## Servidor central

```bash
cd server && docker compose up --build
# accesible en :8080
```

El servidor no tiene estado persistente en la implementación actual (registro y métricas en memoria). En producción se reemplazaría con Redis para heartbeats y PostgreSQL para historial de métricas.

## Cliente desktop (RockDove)

El cliente se distribuye como un ejecutable standalone generado con **electron-builder**:

| Plataforma | Artefacto |
|------------|-----------|
| Linux | `.AppImage` |
| Windows | instalador NSIS `.exe` |
| macOS | `.dmg` |

El binario incluye: shell Electron + UI React compilada + agente Python congelado con PyInstaller. **No requiere Python, Node ni ninguna dependencia instalada.**

Para generar localmente:

```bash
cd client
./scripts/build-agent.sh      # congela el agente Python con PyInstaller
npm run dist:local             # empaqueta todo con electron-builder
# → dist/app/RockDove-0.1.0.AppImage
```

Los releases en GitHub se generan automáticamente con GitHub Actions al pushear un tag `v*`.

## Variables de configuración del agente

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SERVER_URL` | URL del servidor central | `http://localhost:8080` |
| `PEER_ID` | Identificador único de este peer | `default-peer` |
| `AGENT_API_URL` | URL HTTP pública de este agente | `http://localhost:8000` |
| `UDP_HOST` | Bind address del socket UDP | `0.0.0.0` |
| `UDP_PORT` | Puerto UDP | `9001` |
| `STORAGE_PATH` | Ruta de almacenamiento local | `./data` |

## Estructura del repositorio

```
.
├── server/
│   ├── src/
│   │   ├── peers/         ← registro de peers + WebSocket push
│   │   └── metrics/       ← telemetría + recomendador RS
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── client/
│   ├── agent/
│   │   └── src/
│   │       ├── rs/        ← encoder, decoder, transport UDP
│   │       ├── storage/   ← almacenamiento local
│   │       ├── transfers/ ← rutas /transfers/*
│   │       └── server_client.py
│   ├── electron/          ← shell Electron
│   ├── ui/                ← React SPA (Vite + Tailwind)
│   ├── build-resources/   ← ícono de la app
│   └── scripts/           ← build-agent.sh (PyInstaller)
│
└── docs/
    ├── diagrams/          ← fuentes Mermaid (versionadas)
    └── informes/          ← output generado (gitignored)
```

## Consideraciones de red

- El puerto **9001 UDP debe ser accesible** entre peers para recibir transferencias.
- `AGENT_API_URL` debe apuntar a la **IP accesible por los otros peers** (no `127.0.0.1`). Si hay NAT, debe ser la IP pública o la IP dentro de la red compartida.
- El servidor solo necesita **8080 TCP** abierto. No necesita acceso UDP.
- Para redes con NAT estricto, se requiere port forwarding o VPN (por ejemplo Tailscale) para que los peers puedan alcanzarse directamente. El soporte de UDP hole punching es trabajo futuro.
