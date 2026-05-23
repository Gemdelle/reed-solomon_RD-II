import type {
  AuthConfig,
  DeviceTokenCreate,
  DeviceTokenInfo,
  FileMetadata,
  InviteInfo,
  PeerInfo,
  RecommendationResponse,
  ScopeConfig,
  TransferResult,
} from "./types";

declare global {
  interface Window {
    rsAgent?: {
      baseUrl: string;
      openExternal?: (url: string) => void;
      onOidcCallback?: (callback: (url: string) => void) => void;
    };
  }
}

// ── Config helpers ────────────────────────────────────────────────────────────

export const getAgentUrl = () =>
  window.rsAgent?.baseUrl ?? localStorage.getItem("agentUrl") ?? "http://localhost:8000";

export const getServerUrl = () =>
  localStorage.getItem("serverUrl") ?? "http://localhost:8080";

export const getPeerId = () => localStorage.getItem("peerId") ?? "";

const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Server API (control plane) ────────────────────────────────────────────────

export const serverApi = {
  health: (url: string) =>
    fetch(`${url}/health`).then((r) => json<{ status: string }>(r)),

  authConfig: (url: string) =>
    fetch(`${url}/auth/config`).then((r) => json<AuthConfig>(r)),

  getRecommendation: (peerId: string) =>
    fetch(`${getServerUrl()}/metrics/recommendation/${peerId}`, {
      headers: authHeaders(),
    }).then((r) => json<RecommendationResponse>(r)),

  createInvite: (ttl_seconds = 3600) =>
    fetch(`${getServerUrl()}/invites/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ ttl_seconds }),
    }).then((r) => json<InviteInfo>(r)),

  getScopes: () =>
    fetch(`${getServerUrl()}/peers/scopes`, { headers: authHeaders() }).then(
      (r) => json<ScopeConfig>(r)
    ),

  setScopes: (cfg: ScopeConfig) =>
    fetch(`${getServerUrl()}/peers/scopes`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(cfg),
    }).then((r) => json<ScopeConfig>(r)),

  // Device tokens
  createDeviceToken: (body: DeviceTokenCreate) =>
    fetch(`${getServerUrl()}/device-tokens/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body),
    }).then((r) => json<DeviceTokenInfo>(r)),

  listDeviceTokens: () =>
    fetch(`${getServerUrl()}/device-tokens/`, { headers: authHeaders() }).then(
      (r) => json<DeviceTokenInfo[]>(r)
    ),

  revokeDeviceToken: (id: string) =>
    fetch(`${getServerUrl()}/device-tokens/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    }).then((r) => {
      if (!r.ok && r.status !== 204) throw new Error(`${r.status}`);
    }),

  /** Returns a WebSocket that streams the peer list in real-time. */
  watchPeers: (serverUrl: string, token?: string | null): WebSocket => {
    const base = `${serverUrl.replace(/^http/, "ws")}/peers/watch`;
    const url = token ? `${base}?token=${encodeURIComponent(token)}` : base;
    return new WebSocket(url);
  },
};

// ── Agent API (data plane) ────────────────────────────────────────────────────

export const agentApi = {
  health: () =>
    fetch(`${getAgentUrl()}/health`).then((r) => json<{ status: string }>(r)),

  setToken: (token: string) =>
    fetch(`${getAgentUrl()}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    }).then((r) => json<{ ok: boolean }>(r)),

  // Files
  listFiles: () =>
    fetch(`${getAgentUrl()}/files/`, { headers: authHeaders() }).then((r) =>
      json<FileMetadata[]>(r)
    ),

  uploadFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${getAgentUrl()}/files/`, {
      method: "POST",
      body: fd,
      headers: authHeaders(),
    }).then((r) => json<FileMetadata>(r));
  },

  deleteFile: (fileId: string) =>
    fetch(`${getAgentUrl()}/files/${fileId}`, {
      method: "DELETE",
      headers: authHeaders(),
    }).then((r) => json<{ deleted: string }>(r)),

  // Peers (proxied from server via agent)
  listPeers: () =>
    fetch(`${getAgentUrl()}/peers`, { headers: authHeaders() }).then((r) =>
      json<PeerInfo[]>(r)
    ),

  // Transfers
  sendFile: (fileId: string, targetPeerId: string, redundancyLevel?: number) =>
    fetch(`${getAgentUrl()}/transfer/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        file_id: fileId,
        target_peer_id: targetPeerId,
        redundancy_level: redundancyLevel ?? null,
      }),
    }).then((r) => json<TransferResult>(r)),

  listTransfers: () =>
    fetch(`${getAgentUrl()}/transfer/`, { headers: authHeaders() }).then((r) =>
      json<TransferResult[]>(r)
    ),
};
