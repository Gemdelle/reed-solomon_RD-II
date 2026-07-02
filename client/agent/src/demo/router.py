"""
Modo Demo — visualización didáctica de Reed-Solomon sobre una imagen.

Este router NO usa la red: hace todo el pipeline en memoria para poder mostrar,
lado a lado, qué pasa con una imagen cuando se pierden paquetes:

  1. Original          — la imagen tal cual.
  2. Sin Reed-Solomon  — solo con los bloques de datos que "llegaron" (UDP crudo).
  3. Con Reed-Solomon  — reconstrucción usando los bloques de paridad (FEC).

Permite variar el nivel de redundancia y el porcentaje de pérdida simulada,
ilustrando los tres resultados posibles: ok / degraded / failed.
"""
import base64
import io
import random
from hashlib import sha256

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from rs.encoder import HEADER_SIZE, encode_file
from rs.decoder import decode_transfer

router = APIRouter()

# Lado máximo de la imagen procesada. Mantiene la demo ágil en vivo.
_MAX_SIDE = 420
# Gris neutro para los bloques de datos que no llegaron (se ven como bandas).
_GRAY = 0x80


def _to_png_b64(raw_rgb: bytes, size: tuple[int, int]) -> str:
    img = Image.frombytes("RGB", size, raw_rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _block_index(packet: bytes) -> int:
    # header: !16sIIBBBBQ  → block_index es el segundo campo (bytes 16..20)
    return int.from_bytes(packet[16:20], "big")


@router.post("/simulate")
async def simulate(
    file: UploadFile = File(...),
    redundancy_level: float = Form(0.25),
    loss_rate: float = Form(0.0),
) -> dict:
    redundancy_level = max(0.05, min(0.50, redundancy_level))
    loss_rate = max(0.0, min(0.95, loss_rate))

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Archivo vacío")

    # Decodificar a píxeles crudos para que la corrupción sea siempre visible.
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "No se pudo leer la imagen (usá PNG/JPG)")

    img.thumbnail((_MAX_SIDE, _MAX_SIDE))
    size = img.size
    raw_rgb = img.tobytes()
    file_size = len(raw_rgb)
    checksum = sha256(raw_rgb).hexdigest()

    # 1) Codificar en n bloques (k datos + paridad).
    packets, _tid, n, k, chunk_size = encode_file(raw_rgb, redundancy_level)
    parity = n - k

    # 2) Simular pérdida: descartar exactamente round(n * loss_rate) bloques al azar.
    drop_count = min(n, round(n * loss_rate))
    dropped = set(random.sample(range(n), drop_count)) if drop_count else set()
    arrived = [p for p in packets if _block_index(p) not in dropped]

    data_lost = sum(1 for i in dropped if i < k)
    parity_lost = drop_count - data_lost

    # 3) Reconstrucción SIN Reed-Solomon: solo los bloques de datos que llegaron.
    arrived_data: dict[int, bytes] = {}
    for p in arrived:
        idx = _block_index(p)
        if idx < k:
            arrived_data[idx] = p[HEADER_SIZE:]
    naive = bytearray([_GRAY]) * (chunk_size * k)
    for i in range(k):
        if i in arrived_data:
            naive[i * chunk_size : (i + 1) * chunk_size] = arrived_data[i]
    naive_rgb = bytes(naive)[:file_size]

    # 4) Reconstrucción CON Reed-Solomon (usa la paridad para rellenar huecos).
    result = decode_transfer(arrived, checksum)

    rs_png = None
    if result.file_bytes is not None and len(result.file_bytes) == file_size:
        rs_png = _to_png_b64(result.file_bytes, size)

    return {
        "status": result.status.value,
        "reason": result.reason,
        "width": size[0],
        "height": size[1],
        "n": n,
        "k": k,
        "parity": parity,
        "redundancy_level": redundancy_level,
        "loss_rate": loss_rate,
        "blocks_total": n,
        "blocks_dropped": drop_count,
        "blocks_arrived": n - drop_count,
        "data_lost": data_lost,
        "parity_lost": parity_lost,
        "recovered_blocks": result.recovered_blocks,
        "needed_blocks": k,
        "max_recoverable": parity,
        "original_png": _to_png_b64(raw_rgb, size),
        "naive_png": _to_png_b64(naive_rgb, size),
        "rs_png": rs_png,
    }
