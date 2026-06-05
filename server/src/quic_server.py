import asyncio
import json
import logging
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import StreamDataReceived, QuicEvent

from config import get_settings
from quic_utils import generate_self_signed_cert

logger = logging.getLogger(__name__)

class QuicServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffers: Dict[int, bytes] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            data = self._buffers.get(event.stream_id, b"") + event.data
            self._buffers[event.stream_id] = data
            
            if event.end_stream:
                payload = self._buffers.pop(event.stream_id)
                asyncio.create_task(self._handle_request(event.stream_id, payload))

    async def _handle_request(self, stream_id: int, payload: bytes) -> None:
        try:
            req = json.loads(payload.decode())
            method = req.get("method")
            params = req.get("params", {})
            auth_token = req.get("auth") # Agent will send JWT here
            
            logger.info(f"QUIC Request: {method}")
            
            # Dispatch to handlers (to be implemented)
            response = await self._dispatch(method, params, auth_token)
            
            response_data = json.dumps(response).encode()
            self._quic.send_stream_data(stream_id, response_data, end_stream=True)
            self.transmit()
        except Exception as e:
            logger.error(f"Error handling QUIC request: {e}")
            error_resp = {"error": str(e)}
            self._quic.send_stream_data(stream_id, json.dumps(error_resp).encode(), end_stream=True)
            self.transmit()

    async def _dispatch(self, method: str, params: dict, auth_token: Optional[str]) -> dict:
        try:
            from auth.deps import authenticate
            caller = await authenticate(auth_token or "")
            
            if method == "peers.register":
                from peers.router import register, PeerRegistration
                reg = PeerRegistration(**params)
                result = await register(reg, caller)
                return result.model_dump()
            
            elif method == "peers.heartbeat":
                from peers.router import heartbeat
                result = await heartbeat(params["peer_id"], caller)
                return result
            
            elif method == "peers.list":
                from peers.router import list_peers
                result = await list_peers(caller)
                return [p.model_dump() for p in result]
            
            elif method == "metrics.report":
                from metrics.router import report_metrics, MetricReport
                report = MetricReport(**params)
                result = await report_metrics(report)
                return result
            
            elif method == "metrics.recommendation":
                from metrics.router import get_recommendation
                result = await get_recommendation(params["peer_id"])
                return result.model_dump()
            
            elif method == "peers.get":
                from peers.router import get_peer
                result = await get_peer(params["peer_id"], caller)
                return result.model_dump()
            
            elif method == "peers.relay":
                from peers.router import get_relay_peer
                result = await get_relay_peer(params["target"], caller)
                return result.model_dump()
            
            elif method == "peers.incoming_policy":
                from peers.router import get_incoming_policy
                result = await get_incoming_policy(params["peer_id"], caller)
                return result

            elif method == "peers.route":
                from peers.routing import get_route
                result = await get_route(params["target_id"], params.get("source_id"), caller)
                return result.model_dump()
            
            elif method == "ping":
                return {"status": "pong"}
            
            return {"error": f"Method {method} not found"}
        except Exception as e:
            logger.error(f"QUIC Dispatch Error: {e}")
            return {"error": str(e)}

async def start_quic_server():
    settings = get_settings()
    if not settings.QUIC_ENABLED:
        return

    generate_self_signed_cert(settings.QUIC_CERT_PATH, settings.QUIC_KEY_PATH)

    configuration = QuicConfiguration(is_client=False)
    configuration.load_cert_chain(settings.QUIC_CERT_PATH, settings.QUIC_KEY_PATH)

    logger.info(f"Starting QUIC server on {settings.QUIC_HOST}:{settings.QUIC_PORT}")
    await serve(
        settings.QUIC_HOST,
        settings.QUIC_PORT,
        configuration=configuration,
        create_protocol=QuicServerProtocol,
    )
