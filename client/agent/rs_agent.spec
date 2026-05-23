# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the RS Transfer agent — onedir mode.
# Run from client/agent/: pyinstaller rs_agent.spec --distpath dist --noconfirm
# Output: dist/rs-agent/   (directory, not single file)
a = Analysis(
    ["src/run.py"],          # explicit entry point — forces asyncio loop / h11
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        # uvicorn internals (h11 path only; uvloop/httptools excluded on purpose)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "anyio",
        "anyio._backends._asyncio",
        # our subpackages
        "config",
        "server_client",
        "peers",
        "peers.router",
        "rs",
        "rs.encoder",
        "rs.decoder",
        "rs.transport",
        "rs.models",
        "files",
        "files.router",
        "transfers",
        "transfers.router",
        "transfers.models",
        "storage",
        "storage.store",
        "storage.models",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest", "uvloop", "httptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: binaries collected separately
    name="rs-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="rs-agent",         # output dir: dist/rs-agent/
)
