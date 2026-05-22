# File Server

FastAPI service de almacenamiento interno. Guarda archivos en disco y calcula SHA-256 al momento del upload.

**No está expuesto al exterior** — solo el API Gateway puede accederlo (red interna Docker).

## Responsabilidades

- Almacenar archivos con UUID como identificador
- Calcular y persistir SHA-256 al subir (nunca se recalcula)
- Servir bytes crudos y metadata por separado
- Borrar archivos

El file server no conoce usuarios, orgs ni transfers. Toda la lógica de scoping vive en el API Gateway.

## Endpoints

```
GET  /health

POST /files                    # upload multipart → {file_id, sha256, size, ...}
GET  /files                    # listar todos los archivos
GET  /files/{id}/meta          # metadata JSON
GET  /files/{id}/bytes         # bytes crudos (application/octet-stream)
DEL  /files/{id}
```

## Almacenamiento

```
/data/
├── files/   # bytes crudos, nombre = UUID del archivo
└── meta/    # {uuid}.json con metadata
```

Estructura de metadata:

```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "documento.pdf",
  "sha256": "a3f1...",
  "size": 204800,
  "created_at": "2026-05-22T14:30:00+00:00"
}
```

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `STORAGE_PATH` | `/data` | Directorio base de almacenamiento |

En Docker el path `/data` es un volumen nombrado (`fileserver_data`).

## Local dev

```bash
uv sync

STORAGE_PATH=/tmp/rs-fileserver uv run uvicorn main:app --reload --port 9000

uv run pytest
```

## Docker

```bash
uv export --frozen --no-dev -o requirements.txt
docker build -t rs-fileserver .
```
