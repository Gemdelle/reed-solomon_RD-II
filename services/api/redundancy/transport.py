"""
UDP transport layer.

One UDPTransport instance runs per API service process (singleton via module-level `udp`).
It owns a single listening socket and routes incoming datagrams to per-transfer buffers.

Sending uses a separate ephemeral endpoint to avoid blocking the listener.
"""
import asyncio
import struct
import time

from .encoder import HEADER_FMT, HEADER_SIZE


class _TransferBuffer:
    def __init__(self, total: int):
        self.total = total
        self.packets: dict[int, bytes] = {}
        self._done = asyncio.Event()

    def add(self, index: int, raw: bytes) -> None:
        self.packets[index] = raw
        if len(self.packets) >= self.total:
            self._done.set()

    async def wait(self, timeout: float) -> None:
        try:
            await asyncio.wait_for(self._done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass


class _ListenerProtocol(asyncio.DatagramProtocol):
    def __init__(self, buffers: dict[str, _TransferBuffer]):
        self._buffers = buffers

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if len(data) <= HEADER_SIZE:
            return
        hdr = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])
        tid = hdr[0].hex()
        block_index = hdr[1]
        total_blocks = hdr[2]

        if tid not in self._buffers:
            self._buffers[tid] = _TransferBuffer(total_blocks)
        self._buffers[tid].add(block_index, data)

    def error_received(self, exc: Exception) -> None:
        pass


class UDPTransport:
    def __init__(self) -> None:
        self._buffers: dict[str, _TransferBuffer] = {}
        self._listener: asyncio.BaseTransport | None = None

    async def start(self, host: str, port: int) -> None:
        loop = asyncio.get_running_loop()
        self._listener, _ = await loop.create_datagram_endpoint(
            lambda: _ListenerProtocol(self._buffers),
            local_addr=(host, port),
        )

    async def send(self, packets: list[bytes], host: str, port: int) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=(host, port),
        )
        try:
            for pkt in packets:
                transport.sendto(pkt)
                await asyncio.sleep(0)  # yield between packets
        finally:
            transport.close()

    async def collect(self, transfer_id: str, timeout: float = 30.0) -> list[bytes]:
        """Wait for all packets of a transfer and return them in arrival order."""
        deadline = time.monotonic() + timeout

        # Wait for first packet to arrive
        while transfer_id not in self._buffers:
            if time.monotonic() > deadline:
                return []
            await asyncio.sleep(0.05)

        remaining = deadline - time.monotonic()
        await self._buffers[transfer_id].wait(timeout=max(0.0, remaining))

        buf = self._buffers.pop(transfer_id, None)
        return list(buf.packets.values()) if buf else []

    def stop(self) -> None:
        if self._listener:
            self._listener.close()


udp = UDPTransport()
