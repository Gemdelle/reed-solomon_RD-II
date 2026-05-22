---
title: "Sistema de Transferencia P2P con Reed-Solomon"
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

Este sistema es una plataforma de transferencia de archivos entre pares (*peer-to-peer*) que utiliza el algoritmo de corrección de errores **Reed-Solomon** sobre el protocolo **UDP** para garantizar la integridad de los datos transferidos incluso en redes con pérdida de paquetes.

El sistema está pensado para dos escenarios principales:

- **Transferencia entre usuarios de una organización:** dos o más usuarios dentro de la misma organización pueden enviarse archivos directamente entre sus máquinas, con garantía de que el archivo llega íntegro aunque se pierdan paquetes en el camino.
- **Ingesta a dispositivos edge:** envío de información sensible desde una máquina remota hacia un dispositivo con conectividad degradada (celular, satelital), donde la pérdida de paquetes es frecuente y la retransmisión es costosa o imposible.

## ¿Qué problema resuelve?

UDP no garantiza entrega ni orden de paquetes. En redes inestables, una transferencia de archivos sobre UDP sin protección resultará en datos corruptos o incompletos. Las alternativas clásicas son:

- **Usar TCP:** garantiza entrega pero requiere retransmisión, lo que es costoso en links de alta latencia o intermitentes.
- **Ignorar la pérdida:** simple pero inaceptable para archivos.

Este sistema aplica **corrección de errores hacia adelante** (*Forward Error Correction*, FEC) mediante Reed-Solomon: el emisor agrega redundancia matemática al dato antes de enviarlo. El receptor puede reconstruir el dato original aunque lleguen menos paquetes que los enviados, **sin necesidad de retransmisión**.

## Casos de uso

| Caso | Descripción |
|------|-------------|
| Transferencia intra-org | Usuario A envía un archivo a Usuario B dentro de la misma organización |
| Transferencia a edge | Operador central envía configuración o datos a un nodo remoto con link degradado |
| Verificación de integridad | Sistema reporta si el archivo llegó íntegro (`ok`), con errores recuperados (`degraded`) o irrecuperable (`failed`) |

\newpage

# Algoritmo Reed-Solomon

## ¿Qué hace?

Reed-Solomon es un código de corrección de errores que opera sobre bloques de datos. Dado un bloque de **k** símbolos originales, el codificador produce **n** símbolos totales (k originales + n−k de paridad). El receptor puede reconstruir los k símbolos originales a partir de **cualquier combinación de k símbolos del total de n**, aunque los n−k restantes se hayan perdido.

En este sistema, cada símbolo es un byte y el campo matemático utilizado es **GF(2^8^)** (campo de Galois de 256 elementos), que es el estándar para RS en sistemas digitales.

## Parámetros RS(n, k)

| Símbolo | Significado |
|---------|-------------|
| `k` | Bytes originales por bloque |
| `n` | Bytes totales después de codificar (k + paridad) |
| `n − k` | Bytes de paridad (redundancia) |
| `r = (n−k)/n` | Ratio de redundancia |

**Capacidad de recuperación:** si los paquetes perdidos son en posiciones conocidas (erasures, como en UDP donde se sabe qué paquetes llegaron), RS puede recuperar hasta `n − k` pérdidas por bloque. Esto equivale a tolerar un `r × 100%` de pérdida de paquetes.

## Relación entre el slider y los parámetros RS

El usuario configura la redundancia mediante un valor `r ∈ [0.05, 0.50]`. El sistema deriva los parámetros RS automáticamente:

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

El siguiente diagrama ilustra el ciclo completo: codificación en el emisor, transmisión por UDP con posible pérdida, decodificación en el receptor y verificación de integridad.

![Flujo del algoritmo Reed-Solomon](img/rs_algorithm.png)

\newpage

# Diagrama a Nivel de Aplicación

## Flujo de interacción del usuario

El siguiente diagrama de secuencia muestra las tres operaciones principales desde la perspectiva del usuario: autenticación, subida de archivo y transferencia P2P.

![Flujo de interacción del usuario](img/user_flow.png)

## Estados de resultado de una transferencia

| Estado | Condición |
|--------|-----------|
| `ok` | Todos los bloques llegaron, SHA-256 coincide |
| `degraded` | Pérdidas recuperadas por RS, SHA-256 coincide |
| `failed` | Pérdidas superan capacidad RS, o SHA-256 no coincide |

\newpage

# Arquitectura del Sistema

## Modelo de deployment

**Este es el punto más importante de la arquitectura.**

Cada participante corre su propia instancia completa del stack en su propia máquina. El API Gateway de cada máquina es el peer UDP real: mantiene el socket UDP abierto, codifica y decodifica bloques RS, y envía/recibe datagramas directamente a/desde otras máquinas.

El browser no puede abrir sockets UDP. El servicio local `api` actúa como agente de red del usuario.

**Lo que corre local por usuario:** `web`, `api`, `fileserver`

**Lo que es compartido (una sola instancia en cloud):** `Keycloak` — solo para autenticación y lookup de IP de peers, **nunca está en el camino de los datos**.

![Diagrama de arquitectura del sistema](img/architecture.png)

## Servicios

### API Gateway (`api`)

| Atributo | Valor |
|----------|-------|
| Tecnología | Python 3.12 + FastAPI |
| Puerto HTTP | 8000 |
| Puerto UDP | 9001 |
| Exposición | Pública (HTTP + UDP) |

Responsabilidades:

- Validar tokens JWT (Keycloak JWKS)
- Proxy de operaciones de archivo hacia `fileserver`
- Montar el módulo `redundancy` como `APIRouter` en `/transfer`
- Exponer `/peers` (lista miembros de la org con heartbeat activo)

### Módulo Redundancy (`api/redundancy/`)

Submódulo del API Gateway. No es un servicio separado.

| Archivo | Responsabilidad |
|---------|----------------|
| `router.py` | Rutas HTTP `/transfer/*`, sin lógica |
| `encoder.py` | RS encode, segmentación, construcción de paquetes UDP |
| `decoder.py` | RS decode, verificación SHA-256, determinación de estado |
| `transport.py` | Socket UDP, envío/recepción de datagramas |
| `models.py` | Modelos Pydantic: `TransferRequest`, `TransferResponse`, `TransferStatus` |

### File Server (`fileserver`)

| Atributo | Valor |
|----------|-------|
| Tecnología | Python 3.12 + FastAPI |
| Puerto | 9000 |
| Exposición | **Interna únicamente** |

Responsabilidades:

- `POST /files` — almacenar archivo, calcular y persistir SHA-256
- `GET /files/{id}` — recuperar bytes crudos
- `GET /files/{id}/checksum` — recuperar checksum almacenado
- `DELETE /files/{id}` — eliminar archivo

### Keycloak (`auth`)

| Atributo | Valor |
|----------|-------|
| Imagen | `quay.io/keycloak/keycloak:latest` |
| Puerto | 8080 |
| Exposición | Pública (instancia compartida en cloud) |

Modelo de identidad: un **realm** de Keycloak por organización. Los JWT incluyen `org_id` y `user_id`. El API Gateway valida tokens via el endpoint JWKS: `/realms/{realm}/protocol/openid-connect/certs`.

### Frontend (`web`)

| Atributo | Valor |
|----------|-------|
| Tecnología | React 18 + Vite |
| Puerto | 3000 |
| Exposición | Pública |

Se comunica **únicamente** con el API Gateway. Nunca habla directamente con el file server ni con Keycloak.

\newpage

# Infraestructura

## Docker Compose

El proyecto utiliza Docker y Docker Compose para orquestar todos los servicios. Cada servicio tiene su propio `Dockerfile` con build multistage y corre con usuario no-root.

### Perfil `full` (por defecto)

```bash
docker compose up --build
```

| Servicio | Puerto | Visibilidad |
|----------|--------|-------------|
| web | 3000 TCP | Pública |
| api | 8000 TCP | Pública |
| api UDP listener | 9001 UDP | Pública |
| fileserver | 9000 TCP | Interna |
| Keycloak | 8080 TCP | Pública (cloud) |

### Perfil `edge`

Para dispositivos con recursos limitados. Sin interfaz web, sin autenticación local. Solo recibe transferencias UDP.

```bash
docker compose -f docker-compose.edge.yml up
```

El nodo edge escucha pasivamente en UDP y reconstruye los archivos que recibe. No necesita iniciar sesión ni conocer a otros peers.

## Estructura del repositorio

```
.
├── services/
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── redundancy/
│   │       ├── router.py
│   │       ├── encoder.py
│   │       ├── decoder.py
│   │       ├── transport.py
│   │       └── models.py
│   ├── fileserver/
│   │   └── Dockerfile
│   └── web/
│       └── Dockerfile
├── docs/
│   ├── diagrams/         ← fuentes Mermaid (tracked)
│   ├── build.sh          ← regenera diagramas + docs
│   └── informes/         ← output generado (gitignored)
├── docker-compose.yml
├── docker-compose.edge.yml
└── .env.example
```

## Variables de entorno principales

| Variable | Servicio | Descripción |
|----------|---------|-------------|
| `KEYCLOAK_URL` | api | URL base de la instancia Keycloak compartida |
| `KEYCLOAK_REALM` | api | Realm de la organización |
| `KEYCLOAK_CLIENT_ID` | api | Client ID OIDC |
| `KEYCLOAK_CLIENT_SECRET` | api | Client secret OIDC |
| `FILESERVER_URL` | api | URL interna del fileserver |
| `UDP_HOST` | api | Host para el socket UDP (default: `0.0.0.0`) |
| `UDP_PORT` | api | Puerto UDP (default: `9001`) |
| `STORAGE_PATH` | fileserver | Ruta de almacenamiento en el contenedor |

## Consideraciones de red

- El puerto **9001 UDP debe estar abierto** en el firewall del host para recibir transferencias de otros peers.
- El puerto **9000 (fileserver) no debe estar expuesto** fuera de la red Docker interna.
- En deployment detrás de NAT, la IP pública del nodo debe registrarse en Keycloak al hacer login (heartbeat con IP reportada).
