import asyncio
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import get_settings
from files.router import router as files_router
from metrics.probe import rtt_probe_loop
from peers.router import router as peers_router
from rs.transport import udp
from server_client import server_client
import storage.db as db
import token_store
from transfers.router import router as transfers_router

_HEARTBEAT_INTERVAL_S = 15
_auth_store: dict = {}


async def _heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
        settings = get_settings()
        pid = token_store.get_peer_id() or settings.PEER_ID
        try:
            await server_client.heartbeat(pid)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Peer TTL expired (e.g. server restart) — re-register silently.
                try:
                    result = await server_client.register(
                        peer_id=settings.PEER_ID,
                        api_url=settings.AGENT_API_URL,
                        udp_host=settings.UDP_HOST,
                        udp_port=settings.UDP_PORT,
                    )
                    token_store.set_peer_id(result.get("peer_id", settings.PEER_ID))
                except Exception:
                    pass
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await db.init_db(settings.STORAGE_PATH)
    await udp.start(settings.UDP_HOST, settings.UDP_PORT)
    try:
        result = await server_client.register(
            peer_id=settings.PEER_ID,
            api_url=settings.AGENT_API_URL,
            udp_host=settings.UDP_HOST,
            udp_port=settings.UDP_PORT,
        )
        token_store.set_peer_id(result.get("peer_id", settings.PEER_ID))
    except Exception:
        pass
    heartbeat_task = asyncio.create_task(_heartbeat_loop())
    probe_task = asyncio.create_task(rtt_probe_loop())
    yield
    heartbeat_task.cancel()
    probe_task.cancel()
    udp.stop()
    await db.close_db()


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


class TokenPayload(BaseModel):
    token: str


@app.post("/auth/token", tags=["auth"])
async def push_token(body: TokenPayload):
    """
    UI pushes the OIDC access token here after login.
    Agent stores it and re-registers with the central server.
    """
    token_store.set_token(body.token)
    settings = get_settings()
    try:
        result = await server_client.register(
            peer_id=settings.PEER_ID,
            api_url=settings.AGENT_API_URL,
            udp_host=settings.UDP_HOST,
            udp_port=settings.UDP_PORT,
        )
        token_store.set_peer_id(result.get("peer_id", settings.PEER_ID))
    except Exception:
        pass
    return {"ok": True}
