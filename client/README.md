# RockDove — Electron Shell

Packages the React UI and the Python agent into a single cross-platform desktop app. The Electron main process spawns the agent as a child process and waits for it to be healthy before opening the browser window.

## Stack

| Layer | Tech |
|---|---|
| Shell | Electron 32, TypeScript |
| UI | React (served from `ui/dist/` in production, Vite dev server in dev) |
| Agent | Python binary (`rs-agent`) bundled as an `extraResource` |
| Build | electron-builder 25 |

## Sub-packages

```
client/
├── electron/         Electron main + preload (TypeScript)
├── ui/               React + Vite SPA  →  see ui/README.md
├── agent/            Python FastAPI agent  →  see agent/README.md
├── resources/agent/  compiled rs-agent binary (run scripts/build-agent.sh first)
└── scripts/          build-agent.sh / build-agent.bat
```

## Dev setup

```bash
# 1. Install Electron dependencies
npm install

# 2. Build the agent binary once (requires uv + Python 3.12)
./scripts/build-agent.sh          # Linux / macOS
scripts\build-agent.bat           # Windows

# 3. Start in dev mode (UI on Vite dev server, agent via uv)
npm run dev
```

`npm run dev` runs concurrently:
- `vite` → `http://localhost:5173`
- `tsc -p electron/tsconfig.json && electron .` → opens the window

The Electron main process spawns the agent with `uv run uvicorn main:app …` in dev and the compiled binary in production.

## Build & release

```bash
# Local distribution package (no publish)
npm run dist:local     # → dist/app/

# GitHub release (needs GH_TOKEN env var)
npm run release
```

Targets: Linux AppImage, Windows NSIS, macOS DMG (x64 + arm64).

## Electron source

### `electron/main.ts`

| Responsibility | Detail |
|---|---|
| Agent lifecycle | `startAgent()` / `stopAgent()` — spawns the binary or `uv run uvicorn` in dev |
| Health gate | `waitForAgent()` — polls `GET /health` with 500 ms intervals, up to 40 attempts, before opening the window |
| Window | `createWindow()` — loads `ui/dist/index.html` (packaged) or `http://localhost:5173` (dev) |
| External links | `shell.openExternal` for any `window.open` calls from the renderer |

### `electron/preload.ts`

Runs in an isolated context before the renderer loads. Exposes one object via `contextBridge`:

```ts
window.rsAgent = { baseUrl: "http://127.0.0.1:8000" }
```

The UI reads `window.rsAgent.baseUrl` for all agent API calls. No Electron IPC is needed — everything goes through HTTP.

## Tests

```bash
npm test    # tsc --noEmit (type-check) + vitest run
```

Two tests cover the preload contract: that `exposeInMainWorld` is called with key `"rsAgent"` and that `baseUrl` defaults to `http://127.0.0.1:8000`.

## Agent binary build

The build scripts run PyInstaller inside the `client/agent/` directory and copy the output to `client/resources/agent/rs-agent`. The binary is bundled as an `extraResource` so it lands at `process.resourcesPath/agent/rs-agent` inside the packaged app.

```bash
# Rebuild after changing Python source:
./scripts/build-agent.sh
```

The agent reads its `.env` from the working directory. In the packaged app this is `process.resourcesPath/agent/`.

## Folder structure (production bundle)

```
resources/
├── agent/
│   └── rs-agent          (or rs-agent.exe on Windows)
└── ui/
    └── dist/
        └── index.html
```
