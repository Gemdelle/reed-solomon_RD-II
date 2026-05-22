# API Gateway

FastAPI service that acts as the main entry point for clients. Owns the UDP socket and the Reed-Solomon redundancy module.

## Responsabilidades

- Proxy de operaciones de archivo hacia `fileserver`
- Registro y discovery de peers (in-memory, TODO: Keycloak)
- Módulo `redundancy`: codifica archivos con RS, los envía por UDP, decodifica los entrantes y verifica integridad SHA-256

## Módulos internos

| Módulo | Prefijo | Descripción |
|--------|---------|-------------|
| `files/` | `/files` | Proxy hacia fileserver |
| `peers/` | `/peers` | Registro y heartbeat de peers |
| `redundancy/` | `/transfer` | RS encode/decode + transporte UDP |

### `redundancy/` en detalle

```
redundancy/
├── encoder.py    # divide archivo en k chunks, genera n-k chunks de paridad, construye datagramas UDP
├── decoder.py    # decodifica por columnas RS con erasure positions, verifica SHA-256
├── transport.py  # socket UDP asyncio: listener único + envío por endpoint efímero
├── router.py     # rutas HTTP /transfer/*; orquesta encoder, decoder y transport
└── models.py     # SendRequest, ReceiveRequest, TransferResult, DecodeResult
```

## Endpoints

```
GET  /health

POST /files                    # upload (proxy a fileserver)
GET  /files                    # listar archivos
GET  /files/{id}/meta          # metadata + checksum
GET  /files/{id}               # download
DEL  /files/{id}

POST /peers/register           # registrar peer con IP:UDP_PORT
POST /peers/{id}/heartbeat     # mantener presencia
GET  /peers                    # listar peers online (TTL 30s)
GET  /peers/{id}

POST /transfer/send            # iniciar transferencia P2P
POST /transfer/receive         # receptor: registrar transfer entrante
GET  /transfer/{id}/status     # estado de una transferencia
GET  /transfer                 # historial
```

### Flujo de transferencia

```
POST /transfer/send  {file_id, target_api_url, target_udp_host, redundancy_level}
  → fetch file bytes del fileserver local
  → RS encode → n UDP packets (k data + n-k paridad)
  → HTTP notify al peer  POST target/transfer/receive
  → enviar UDP packets
  → polling GET target/transfer/{id}/status
  → retornar ok / degraded / failed
```

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `FILESERVER_URL` | `http://fileserver:9000` | URL interna del fileserver |
| `UDP_HOST` | `0.0.0.0` | Interfaz para el socket UDP listener |
| `UDP_PORT` | `9001` | Puerto UDP (debe estar abierto en firewall) |

Copiar `.env.example` en la raíz del repo a `.env` antes de correr.

## Local dev

```bash
uv sync                                      # instalar deps + dev group

uv run uvicorn main:app --reload --port 8000 # levantar con hot-reload

uv run pytest                                # correr tests
```

## Docker

El `Dockerfile` usa multistage con pip. El `requirements.txt` es generado por uv y **no se edita a mano**:

```bash
uv export --frozen --no-dev -o requirements.txt
docker build -t rs-api .
```

## Parámetros Reed-Solomon

`redundancy_level` es un float entre `0.05` y `0.50` que controla el ratio de redundancia `r = (n-k)/n`:

| Preset | r | Tolerancia de pérdida |
|--------|---|----------------------|
| Rápido | 0.10 | 10% |
| Balanceado | 0.25 | 25% |
| Resiliente | 0.50 | 50% |

Con `n=32` fijo: `k = round(32 * (1 - r))`, clampeado a `[4, 31]`.
