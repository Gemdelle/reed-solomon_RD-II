import type { PeerInfo } from "../types";

interface Props {
  peers: PeerInfo[];
  currentPeerId: string;
  onSend: (peer: PeerInfo) => void;
}

type PeerStatus = "online" | "unknown" | "offline";

const UNKNOWN_THRESHOLD_S = 300; // 5 min — recently lost heartbeat

function getPeerStatus(peer: PeerInfo): PeerStatus {
  if (peer.online) return "online";
  try {
    const ageSec = (Date.now() - new Date(peer.last_seen).getTime()) / 1000;
    return ageSec < UNKNOWN_THRESHOLD_S ? "unknown" : "offline";
  } catch {
    return "offline";
  }
}

function timeAgo(iso: string): string {
  const diffS = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diffS < 60) return `${diffS}s`;
  if (diffS < 3600) return `${Math.floor(diffS / 60)}m`;
  return `${Math.floor(diffS / 3600)}h`;
}

const STATUS_DOT: Record<PeerStatus, string> = {
  online:  "bg-emerald-400",
  unknown: "bg-amber-400 animate-pulse",
  offline: "bg-slate-600",
};

const STATUS_LABEL: Record<PeerStatus, string> = {
  online:  "online",
  unknown: "desconocido",
  offline: "offline",
};

const STATUS_TEXT: Record<PeerStatus, string> = {
  online:  "text-slate-600",
  unknown: "text-amber-600",
  offline: "text-slate-600",
};

const TRANSPORT_BADGE: Record<string, string> = {
  quic: "text-violet-400 bg-violet-950/50 border-violet-800",
  udp:  "text-slate-500 bg-slate-800/50 border-slate-700",
};

export default function PeerList({ peers, currentPeerId, onSend }: Props) {
  const online  = peers.filter((p) => p.online);
  const notOnline = peers.filter((p) => !p.online);

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-medium text-slate-200">Peers de la red</h2>
        {peers.length > 0 ? (
          <span className="text-xs text-slate-500">
            {online.length} online
            {notOnline.length > 0 ? ` · ${notOnline.length} inactivos` : ""}
          </span>
        ) : null}
      </div>

      {peers.length === 0 ? (
        <div className="px-4 py-10 text-center text-slate-600 text-sm">
          <div className="text-3xl mb-2">📡</div>
          Esperando peers… el agente se registra automáticamente al arrancar.
        </div>
      ) : (
        <ul className="divide-y divide-slate-800/50">
          {[...online, ...notOnline].map((peer) => {
            const status = getPeerStatus(peer);
            const transport = peer.transport ?? "udp";
            const badgeCls = TRANSPORT_BADGE[transport] ?? TRANSPORT_BADGE.udp;

            return (
              <li
                key={peer.peer_id}
                className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/40 transition-colors"
              >
                {/* Status dot */}
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[status]}`} />

                {/* Identity */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-slate-200 truncate">
                      {peer.peer_id}
                    </span>
                    {peer.peer_id === currentPeerId ? (
                      <span className="text-xs bg-brand-900 text-brand-400 rounded px-1.5 py-0.5">
                        yo
                      </span>
                    ) : null}
                    {/* Transport badge */}
                    <span className={`text-xs font-mono border rounded px-1.5 py-0.5 ${badgeCls}`}>
                      {transport.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-slate-500 truncate">
                      {peer.udp_host}:{peer.udp_port}
                    </span>
                    <span className={`text-xs ${STATUS_TEXT[status]}`}>
                      · {status === "online"
                          ? `hace ${timeAgo(peer.last_seen)}`
                          : STATUS_LABEL[status]}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                {status === "online" && peer.peer_id !== currentPeerId ? (
                  <button
                    onClick={() => onSend(peer)}
                    className="flex-shrink-0 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg px-3 py-1.5 transition-colors"
                  >
                    Enviar
                  </button>
                ) : status !== "online" ? (
                  <span className={`flex-shrink-0 text-xs ${STATUS_TEXT[status]}`}>
                    {STATUS_LABEL[status]}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
