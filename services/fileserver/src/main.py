import os

from fastapi import FastAPI, HTTPException, Response, UploadFile, File
from models import FileMetadata
from storage import FileStorage

app = FastAPI(title="File Server")
storage = FileStorage(os.getenv("STORAGE_PATH", "/data"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/files", response_model=FileMetadata)
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    return storage.save(data, file.filename or "")


@app.get("/files", response_model=list[FileMetadata])
async def list_files():
    return storage.list_all()


@app.get("/files/{file_id}/meta", response_model=FileMetadata)
async def get_meta(file_id: str):
    meta = storage.get_meta(file_id)
    if not meta:
        raise HTTPException(404, "File not found")
    return meta


@app.get("/files/{file_id}/bytes")
async def get_bytes(file_id: str):
    data = storage.get_bytes(file_id)
    if data is None:
        raise HTTPException(404, "File not found")
    return Response(content=data, media_type="application/octet-stream")


@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    if not storage.delete(file_id):
        raise HTTPException(404, "File not found")
    return {"deleted": file_id}
