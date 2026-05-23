"""
PyInstaller entry point for the frozen agent binary.
Pins loop and http implementations explicitly so uvicorn does not probe for
uvloop / httptools at runtime (both cause hangs inside a frozen bundle).
"""
import os
import uvicorn
from main import app  # import object directly — frozen sys.path can't resolve "main:app" string

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("AGENT_PORT", "8000")),
        loop="asyncio",
        http="h11",
        log_level="info",
    )
