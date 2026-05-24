export interface PeerInfo {
  peer_id: string;
  api_url: string;
  udp_host: string;
  udp_port: number;
  last_seen: string;
  online: boolean;
  transport?: "udp" | "quic";
}

export interface FileMetadata {
  file_id: string;
  filename: string;
  sha256: string;
  size: number;
  created_at: string;
}

export interface TransferResult {
  transfer_id: string;
  status: "ok" | "degraded" | "failed" | "pending";
  recovered_blocks: number;
  total_blocks: number;
  file_id: string | null;
  reason: string | null;
}

export interface RecommendationResponse {
  peer_id: string;
  redundancy_level: number;
  quality: "excellent" | "good" | "fair" | "poor" | "critical" | "unknown";
  based_on_samples: number;
  profile_name: string;
}

export interface AuthConfig {
  oidc_enabled: boolean;
  issuer: string | null;
  client_id: string | null;
}

export interface InviteInfo {
  token: string;
  issued_by: string;
  org_id: string;
  expires_at: string;
}

export interface IncomingConnection {
  transfer_id: string;
  peer_id: string;
  cert_cn: string;
  cert_fingerprint: string;
  arrived_at: string;
  status: "pending" | "accepted" | "rejected";
}

export interface AppConfig {
  serverUrl: string;
  agentUrl: string;
  peerId: string;
  token: string | null;
  inviteToken?: string | null;
}

export interface ScopeConfig {
  scopes: Record<string, string[]>;
}

export interface DeviceTokenCreate {
  label: string;
  peer_id?: string | null;
  ttl_seconds?: number | null;
}

export interface DeviceTokenInfo {
  id: string;
  label: string;
  peer_id: string | null;
  org_id: string;
  created_by: string;
  created_at: string;
  expires_at: string | null;
  token_preview: string;
  token?: string | null; // solo presente en la respuesta de creación
}

export interface AgentConfig {
  server_url: string;
  peer_id: string;
  agent_api_url: string;
  udp_host: string;
  udp_port: number;
  udp_advertise_host: string;
  transport_mode: "udp" | "quic";
  storage_path: string;
  invite_token: string;
  network_hint: string;
}

export interface ConfigUpdateResponse {
  ok: boolean;
  requires_restart: boolean;
  transport_mode: string;
}

export interface TransportRequest {
  request_id: string;
  sender_peer_id: string;
  requested_transport: "udp" | "quic";
  status: "pending" | "accepted" | "rejected";
  arrived_at: string;
}
