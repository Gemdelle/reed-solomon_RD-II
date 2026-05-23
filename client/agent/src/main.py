import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config import get_settings
from files.router import router as files_router
from metrics.probe import rtt_probe_loop
from peers.router import router as peers_router
from rs.transport import udp
from server_client import server_client
from transfers.router import router as transfers_router

_HEARTBEAT_INTERVAL_S = 15
_auth_store: dict = {}


async def _heartbeat_loop(peer_id: str) -> None:
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
        try:
            await server_client.heartbeat(peer_id)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await udp.start(settings.UDP_HOST, settings.UDP_PORT)
    try:
        await server_client.register(
            peer_id=settings.PEER_ID,
            api_url=settings.AGENT_API_URL,
            udp_host=settings.UDP_HOST,
            udp_port=settings.UDP_PORT,
        )
    except Exception:
        pass
    heartbeat_task = asyncio.create_task(_heartbeat_loop(settings.PEER_ID))
    probe_task = asyncio.create_task(rtt_probe_loop())
    yield
    heartbeat_task.cancel()
    probe_task.cancel()
    udp.stop()


app = FastAPI(title="RS Transfer Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files_router, prefix="/files", tags=["files"])
app.include_router(peers_router, prefix="/peers", tags=["peers"])
app.include_router(transfers_router, prefix="/transfer", tags=["transfer"])


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/auth/callback", tags=["auth"])
async def auth_callback(code: str, state: str):
    """Recibe el código desde el navegador externo."""
    _auth_store["last"] = {"code": code, "state": state}
    return HTMLResponse("""
        <html>
            <body style="font-family:sans-serif;text-align:center;padding-top:50px;background:#0f172a;color:#cbd5e1;">
                <h1 style="color:#10b981;">&#10003; Autenticación Exitosa</h1>
                <p>Ya podés cerrar esta pestaña y volver a RockDove.</p>
                <script>setTimeout(() => window.close(), 3000);</script>
            </body>
        </html>
    """)


@app.get("/auth/poll", tags=["auth"])
async def auth_poll():
    """La UI llama aquí para ver si ya llegó el código."""
    return _auth_store.pop("last", None)
