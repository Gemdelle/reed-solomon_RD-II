# RockDove UI

React + Vite single-page app served inside the Electron shell (or standalone in a browser for dev). Talks to the local agent over HTTP and to the central server for peer discovery and quality metrics.

## Stack

| Layer | Tech |
|---|---|
| UI | React 18, TypeScript |
| Build | Vite 5 |
| Styles | Tailwind CSS 3 |
| Auth | oidc-client-ts 3 |
| Tests | Vitest 3, happy-dom |

## Quick start

```bash
cd client/ui
npm install
npm run dev      # → http://localhost:5173
```

For production build (consumed by Electron):

```bash
npm run build    # outputs to ui/dist/
```

## Tests

```bash
npm test         # vitest run (single pass)
npm run test:watch
```

16 tests covering URL helpers, all `agentApi` and `serverApi` methods, and error handling.

## Source layout

```
src/
├── main.tsx             React entry point
├── App.tsx              root: config load, OIDC callback detection, page routing
├── api.ts               agentApi + serverApi fetch wrappers
├── types.ts             shared TypeScript interfaces
│
├── auth/
│   └── oidc.ts          oidc-client-ts wrapper (initOidc / startLogin / handleCallback)
│
├── pages/
│   ├── ConnectPage.tsx  server URL entry → OIDC or manual peer ID + invite token
│   └── DashboardPage.tsx main UI: peers, files, transfers, invite creation
│
└── components/
    ├── FileList.tsx       upload + list + delete local files
    ├── PeerList.tsx       online peers with "Send" action
    ├── TransferDialog.tsx send dialog: file selector + adaptive FEC toggle + recommendation chip
    └── TransferHistory.tsx session transfer log
```

## API layers

**`agentApi`** — all data-plane calls go to the local agent (`http://localhost:8000` by default, or `window.rsAgent.baseUrl` injected by Electron's preload):

| Method | Description |
|---|---|
| `agentApi.health()` | liveness check |
| `agentApi.listFiles()` | list stored files |
| `agentApi.uploadFile(file)` | upload a file |
| `agentApi.deleteFile(id)` | delete a file |
| `agentApi.sendFile(fileId, peerId, level?)` | initiate a transfer (`level=undefined` → adaptive) |
| `agentApi.listTransfers()` | session transfer history |

**`serverApi`** — control-plane calls go to the configured server URL:

| Method | Description |
|---|---|
| `serverApi.health(url)` | server liveness check |
| `serverApi.authConfig(url)` | fetch OIDC config |
| `serverApi.getRecommendation(peerId)` | redundancy + quality + profile |
| `serverApi.createInvite()` | generate a single-use invite token |
| `serverApi.watchPeers(url)` | WebSocket for real-time peer list |

## Connect flow

```
Enter server URL
      │
      ▼
GET /health + GET /auth/config
      │
      ├─ oidc_enabled=true ──► "Sign in" → Keycloak redirect
      │                              └─ callback: ?code=… → handleCallback() → auto-proceed
      │
      └─ oidc_enabled=false ─► Peer ID field + optional invite token field
                                     └─ "Join" → DashboardPage
```

On OIDC callback the server URL is re-read from `localStorage` (set before the redirect), the manager is re-initialized, and the `sub` claim becomes the peer ID.

## Adaptive FEC toggle

In `TransferDialog`, the toggle defaults to **ON**:
- **ON** — sends `redundancy_level=null` to the agent; agent resolves via `GET /metrics/recommendation/{peer_id}` on the server
- **OFF** — shows a manual slider (5–50%), with a reset-to-recommended button

The recommendation chip always shows `quality`, `profile_name`, and sample count.

## URL resolution priority

```
Agent URL:  window.rsAgent.baseUrl  →  localStorage["agentUrl"]  →  "http://localhost:8000"
Server URL: localStorage["serverUrl"]                             →  "http://localhost:8080"
```

`window.rsAgent` is injected by the Electron preload script. When running in a plain browser (dev mode without Electron) it falls back to localhost.
