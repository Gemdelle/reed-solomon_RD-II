import type { PeerInfo } from "../types";
import OnlineBird from "./OnlineBird";
import bird2 from "../assets/bird-2.png";

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

export default function PeerList({ peers, currentPeerId, onSend }: Props) {
  const online = peers.filter((p) => p.online);
  const offline = peers.filter((p) => !p.online);

  return (
    <div className="bird-panel rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <h2 className="font-medium text-slate-200">Peers de la red</h2>
        <span className="text-xs text-slate-500">
          {online.length} online · {offline.length} offline
        </span>
      </div>

      {peers.length === 0 ? (
        <div className="px-4 py-10 text-center text-slate-600 text-sm">
          <img
            src={bird2}
            alt=""
            className="h-10 w-10 mx-auto mb-3 object-contain animate-bird-bob opacity-60"
          />
          <p className="animate-gentle-pulse">Esperando peers…</p>
          <p className="text-xs text-slate-700 mt-1">El agente se registra automáticamente al arrancar.</p>
        </div>
      ) : (
        <ul className="divide-y divide-slate-800/50">
          {[...online, ...offline].map((peer, i) => (
            <li key={peer.peer_id} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/40 transition-colors">
              <OnlineBird variant={i} size="sm" offline={!peer.online} />

              {/* Identity */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-base font-mono text-slate-200 truncate">{peer.peer_id}</span>
                  {peer.peer_id === currentPeerId && (
                    <span className="text-xs bg-brand-900 text-brand-400 rounded px-1.5 py-0.5">yo</span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-slate-500 truncate">{peer.udp_host}:{peer.udp_port}</span>
                  {peer.online && (
                    <span className="text-xs text-slate-600">· hace {timeAgo(peer.last_seen)}</span>
                  )}
                </div>
              </div>

              {/* Send button */}
              {peer.online && peer.peer_id !== currentPeerId && (
                <button
                  onClick={() => onSend(peer)}
                  className="bird-btn-outline flex-shrink-0 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg px-3 py-1.5 transition-colors"
                >
                  Enviar
                </button>
              )}

              {!peer.online && (
                <span className="flex-shrink-0 text-xs text-slate-600">offline</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
