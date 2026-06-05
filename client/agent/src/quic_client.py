import asyncio
import json
import logging
import time
from typing import Optional, Dict

import token_store
from aioquic.asyncio import QuicConnectionProtocol, connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, QuicEvent

logger = logging.getLogger(__name__)

class QuicClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._futures: Dict[int, asyncio.Future] = {}
        self._buffers: Dict[int, bytes] = {}

    async def call(self, method: str, params: dict, auth_token: Optional[str]) -> dict:
        stream_id = self._quic.get_next_available_stream_id()
        payload = json.dumps({
            "method": method,
            "params": params,
            "auth": auth_token
        }).encode()
        
        future = asyncio.Future()
        self._futures[stream_id] = future
        
        self._quic.send_stream_data(stream_id, payload, end_stream=True)
        self.transmit()
        
        return await future

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            self._buffers[event.stream_id] = self._buffers.get(event.stream_id, b"") + event.data
            if event.end_stream:
                payload = self._buffers.pop(event.stream_id)
                future = self._futures.pop(event.stream_id, None)
                if future:
                    try:
                        future.set_result(json.loads(payload.decode()))
                    except Exception as e:
                        future.set_exception(e)

_TOKEN_POLL_INTERVAL = 0.5
_TOKEN_TIMEOUT = 30.0


class ServerQuicClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.configuration = QuicConfiguration(is_client=True)
        self.configuration.verify_mode = 0  # Disable cert verification for self-signed
        self._protocol: Optional[QuicClientProtocol] = None
        self._connect_context = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        """Eagerly establish the QUIC connection at agent startup."""
        async with self._lock:
            if self._started:
                return
            self._started = True
            logger.info("Connecting QUIC to %s:%s", self.host, self.port)
            self._connect_context = connect(
                self.host,
                self.port,
                configuration=self.configuration,
                create_protocol=QuicClientProtocol,
            )
            self._protocol = await self._connect_context.__aenter__()
            logger.info("QUIC connection established")

    async def _ensure_connected(self):
        async with self._lock:
            if self._protocol is not None:
                return
            if not self._started:
                self._started = True
            self._connect_context = connect(
                self.host,
                self.port,
                configuration=self.configuration,
                create_protocol=QuicClientProtocol,
            )
            self._protocol = await self._connect_context.__aenter__()

    async def _wait_for_token(self, timeout: float = _TOKEN_TIMEOUT) -> str:
        """Poll token_store until a non-empty token appears or timeout elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            token = token_store.get_token()
            if token:
                return token
            await asyncio.sleep(_TOKEN_POLL_INTERVAL)
        raise TimeoutError("Timed out waiting for auth token")

    async def call(self, method: str, params: dict, auth_token: Optional[str]) -> dict:
        try:
            # If no token was passed, wait/poll for one from the store.
            if not auth_token:
                auth_token = await self._wait_for_token()

            await self._ensure_connected()
            return await self._protocol.call(method, params, auth_token)
        except Exception:
            logger.exception("QUIC Call Error")
            if self._connect_context is not None:
                try:
                    await self._connect_context.__aexit__(None, None, None)
                except Exception:
                    pass
                self._connect_context = None
            self._protocol = None
            raise

