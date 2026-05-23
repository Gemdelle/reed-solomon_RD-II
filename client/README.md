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

In dev mode the agent runs via `uv run uvicorn main:app …` — no compiled binary is needed. The binary is only required for packaged distribution.

## Build & release

```bash
# Local distribution package (no publish)
npm run dist:local     # → dist/app/

# GitHub release (needs GH_TOKEN env var)
npm run release
```

**Important:** run `./scripts/build-agent.sh` before `npm run dist:local`. The script compiles the Python agent with PyInstaller and copies the output to `resources/agent/rs-agent`. If the binary is missing or stale, the packaged app will fail to start the agent.

Targets: Linux AppImage, Windows NSIS, macOS DMG (x64 + arm64).

## OIDC login flow

Electron cannot complete a standard OAuth redirect internally — the Keycloak redirect URI would land inside a webview with no way for the renderer to access the authorization code. Instead, RockDove uses a loopback flow: the system browser handles the Keycloak interaction and the agent (running on `127.0.0.1:8000`) acts as the redirect URI target.

The full sequence is:

1. User clicks "Login with SSO" in the UI.
2. `startLogin()` calls `_manager._client.createSigninRequest()` to build the authorization URL with PKCE. The PKCE verifier and state are stored in `sessionStorage`.
3. The URL is opened in the system browser via `window.rsAgent.openExternal(url)` → Electron `shell.openExternal()`.
4. The user authenticates in Keycloak. Keycloak redirects to `http://127.0.0.1:8000/auth/callback?code=...&state=...`.
5. The agent stores `{code, state}` in an in-memory `_auth_store` and returns an HTML page that auto-closes after 3 seconds.
6. The UI polls `GET /auth/poll` every 1 second.
7. When the code arrives, the UI calls `_manager.signinCallback(url)` with the reconstructed callback URL to complete the PKCE token exchange with Keycloak directly from the renderer.
8. The UI stores `access_token` in `localStorage` and immediately calls `agentApi.setToken(accessToken)`.
9. The agent stores the JWT in `token_store` and re-registers with the server. The server assigns `peer_id = JWT sub` and returns it; the agent stores it in `token_store` for the heartbeat loop.

**Why the push in step 8 is required:** the agent starts before the user logs in and has no JWT at that point. Without the explicit push via `POST /auth/token`, the agent would have no credentials to authenticate its registration request to the server in OIDC mode, and all subsequent server calls would fail with 401.

## JWT push to agent

After a successful OIDC login the UI calls:

```ts
await agentApi.setToken(accessToken);
```

This posts `{"token": "<jwt>"}` to `POST /auth/token` on the agent. The agent:
1. Stores the token in `token_store` (used for all subsequent server HTTP calls).
2. Immediately re-registers with the server using the JWT as the `Authorization: Bearer` header.
3. Stores the server-assigned `peer_id` (which equals the JWT `sub` claim in OIDC mode).

The heartbeat loop then reads `token_store.get_peer_id()` for its requests rather than the `PEER_ID` environment variable, because in OIDC mode the server controls peer ID assignment.

## Preload API

`electron/preload.ts` runs in an isolated context before the renderer loads and exposes one object via `contextBridge`:

```ts
window.rsAgent = {
  baseUrl: string,                               // always "http://127.0.0.1:8000"
  openExternal?: (url: string) => void,          // opens url in the system browser
  onOidcCallback?: (cb: (url: string) => void) => void,  // legacy, unused
}
```

The UI reads `window.rsAgent.baseUrl` for all agent API calls. No Electron IPC is needed — everything goes through HTTP. `openExternal` is used exclusively during the OIDC login flow to open the Keycloak authorization URL in the system browser.

## Electron source

### `electron/main.ts`

| Responsibility | Detail |
|---|---|
| Agent lifecycle | `startAgent()` / `stopAgent()` — spawns `uv run uvicorn` in dev or `process.resourcesPath/agent/rs-agent` in packaged mode |
| Health gate | `waitForAgent()` — polls `GET /health` with 500 ms intervals, up to 40 attempts, before opening the window |
| Window | `createWindow()` — loads `ui/dist/index.html` (packaged) or `http://localhost:5173` (dev) |
| External links | `shell.openExternal` for any navigation that leaves the app origin, including OIDC auth URLs |

### `electron/preload.ts`

Exposes `window.rsAgent` via `contextBridge`. See [Preload API](#preload-api) above.

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
