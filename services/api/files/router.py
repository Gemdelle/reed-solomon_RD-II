import httpx
from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from ..config import get_settings

router = APIRouter()


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    settings = get_settings()
    data = await file.read()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{settings.FILESERVER_URL}/files",
            files={"file": (file.filename, data, file.content_type or "application/octet-stream")},
        )
        r.raise_for_status()
    return r.json()


@router.get("/")
async def list_files():
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{settings.FILESERVER_URL}/files")
        r.raise_for_status()
    return r.json()


@router.get("/{file_id}/meta")
async def get_meta(file_id: str):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{settings.FILESERVER_URL}/files/{file_id}/meta")
        if r.status_code == 404:
            raise HTTPException(404, "File not found")
        r.raise_for_status()
    return r.json()


@router.get("/{file_id}")
async def download_file(file_id: str):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{settings.FILESERVER_URL}/files/{file_id}/bytes")
        if r.status_code == 404:
            raise HTTPException(404, "File not found")
        r.raise_for_status()
    return Response(
        content=r.content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_id}"'},
    )


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(f"{settings.FILESERVER_URL}/files/{file_id}")
        if r.status_code == 404:
            raise HTTPException(404, "File not found")
        r.raise_for_status()
    return r.json()
