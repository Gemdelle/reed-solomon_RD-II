from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .files.router import router as files_router
from .peers.router import router as peers_router
from .redundancy.router import router as redundancy_router
from .redundancy.transport import udp


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await udp.start(settings.UDP_HOST, settings.UDP_PORT)
    yield
    udp.stop()


app = FastAPI(title="RS Transfer API", version="0.1.0", lifespan=lifespan)

app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(peers_router, prefix="/peers", tags=["peers"])
app.include_router(redundancy_router, prefix="/transfer", tags=["transfer"])


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
