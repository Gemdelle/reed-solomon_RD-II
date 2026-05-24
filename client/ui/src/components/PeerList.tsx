import type { PeerInfo } from "../types";

interface Props {
  peers: PeerInfo[];
  currentPeerId: string;
  onSend: (peer: PeerInfo) => void;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffS = Math.floor(diffMs / 1000);
  if (diffS < 60) return `${diffS}s`;
  return `${Math.floor(diffS / 60)}m`;
}

const TRANSPORT_BADGE: Record<string, string> = {
  quic: "text-violet-400 bg-violet-950/50 border-violet-800",
  udp:  "text-slate-500 bg-slate-800/50 border-slate-700",
};

export default function PeerList({ peers, currentPeerId, onSend }: Props) {
  const online = peers.filter((p) => p.online);
  const offline = peers.filter((p) => !p.online);

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-medium text-slate-200">Peers de la red</h2>
        {peers.length > 0 ? (
          <span className="text-xs text-slate-500">
            {online.length} online · {offline.length} offline
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
          {[...online, ...offline].map((peer) => {
            const transport = peer.transport ?? "udp";
            const badgeCls = TRANSPORT_BADGE[transport] ?? TRANSPORT_BADGE.udp;

            return (
              <li
                key={peer.peer_id}
                className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/40 transition-colors"
              >
                {/* Status dot */}
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    peer.online ? "bg-emerald-400" : "bg-slate-600"
                  }`}
                />

                {/* Identity */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono text-slate-200 truncate">
                      {peer.peer_id}
                    </span>
                    {peer.peer_id === currentPeerId && (
                      <span className="text-xs bg-brand-900 text-brand-400 rounded px-1.5 py-0.5">
                        yo
                      </span>
                    )}
                    {/* Transport badge */}
                    <span
                      className={`text-xs font-mono border rounded px-1.5 py-0.5 ${badgeCls}`}
                    >
                      {transport.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-slate-500 truncate">
                      {peer.udp_host}:{peer.udp_port}
                    </span>
                    {peer.online && (
                      <span className="text-xs text-slate-600">
                        · hace {timeAgo(peer.last_seen)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Send button */}
                {peer.online && peer.peer_id !== currentPeerId && (
                  <button
                    onClick={() => onSend(peer)}
                    className="flex-shrink-0 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 rounded-lg px-3 py-1.5 transition-colors"
                  >
                    Enviar
                  </button>
                )}

                {!peer.online && (
                  <span className="flex-shrink-0 text-xs text-slate-600">
                    offline
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
