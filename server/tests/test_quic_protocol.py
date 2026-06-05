import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from quic_server import QuicServerProtocol
from auth.deps import CallerInfo

@pytest.mark.asyncio
async def test_quic_ping():
    # We patch QuicConnectionProtocol so it doesn't do real initialization
    with patch("aioquic.asyncio.QuicConnectionProtocol.__init__", return_value=None):
        mock_quic = MagicMock()
        mock_quic.transmit = MagicMock()
        
        protocol = QuicServerProtocol()
        protocol._quic = mock_quic 
        protocol._buffers = {}
        protocol.transmit = mock_quic.transmit
        
        # Simulate a ping request
        stream_id = 4
        payload = json.dumps({
            "method": "ping",
            "params": {}
        }).encode()
        
        with patch("auth.deps.authenticate", new_callable=AsyncMock) as mock_auth:
            mock_auth.return_value = CallerInfo(peer_id="test-peer", org_id="dev")
            
            await protocol._handle_request(stream_id, payload)
            
            # Verify that send_stream_data was called with a pong
            mock_quic.send_stream_data.assert_called()
            args, kwargs = mock_quic.send_stream_data.call_args
            assert args[0] == stream_id
            resp = json.loads(args[1].decode())
            assert resp["status"] == "pong"

@pytest.mark.asyncio
async def test_quic_register_dispatch():
    with patch("aioquic.asyncio.QuicConnectionProtocol.__init__", return_value=None):
        mock_quic = MagicMock()
        mock_quic.transmit = MagicMock()
        
        protocol = QuicServerProtocol()
        protocol._quic = mock_quic
        protocol._buffers = {}
        protocol.transmit = mock_quic.transmit
        
        stream_id = 8
        params = {
            "peer_id": "peer-1",
            "api_url": "http://1.2.3.4:8000",
            "udp_host": "1.2.3.4",
            "udp_port": 9001
        }
        payload = json.dumps({
            "method": "peers.register",
            "params": params,
            "auth": "fake-token"
        }).encode()
        
        with patch("auth.deps.authenticate", new_callable=AsyncMock) as mock_auth, \
             patch("peers.router.register", new_callable=AsyncMock) as mock_register:
            
            mock_auth.return_value = CallerInfo(peer_id="peer-1", org_id="dev")
            mock_register.return_value = MagicMock(model_dump=lambda: {"status": "registered"})
            
            await protocol._handle_request(stream_id, payload)
            
            mock_register.assert_called_once()
            args, kwargs = mock_quic.send_stream_data.call_args
            resp = json.loads(args[1].decode())
            assert resp == {"status": "registered"}
