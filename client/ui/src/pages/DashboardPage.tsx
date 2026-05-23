import { useEffect, useRef, useState } from "react";
import type { AppConfig, FileMetadata, PeerInfo, TransferResult } from "../types";
import { serverApi } from "../api";
import FileList from "../components/FileList";
import PeerList from "../components/PeerList";
import TransferDialog from "../components/TransferDialog";
import TransferHistory from "../components/TransferHistory";

interface Props {
  config: AppConfig;
  onDisconnect: () => void;
}

export default function DashboardPage({ config, onDisconnect }: Props) {
  const [peers, setPeers] = useState<PeerInfo[]>([]);
  const [serverOnline, setServerOnline] = useState(true);
  const [transferTarget, setTransferTarget] = useState<{ peer: PeerInfo; file?: FileMetadata } | null>(null);
  const [transfers, setTransfers] = useState<TransferResult[]>([]);
  const [networkProfile, setNetworkProfile] = useState<string>("");
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [inviteLoading, setInviteLoading] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // WebSocket peer discovery
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = serverApi.watchPeers(config.serverUrl);
      wsRef.current = ws;

      ws.onopen = () => setServerOnline(true);

      ws.onmessage = (ev) => {
        try {
          const list: PeerInfo[] = JSON.parse(ev.data);
          setPeers(list.filter((p) => p.peer_id !== config.peerId));
        } catch {}
      };

      ws.onerror = () => setServerOnline(false);

      ws.onclose = () => {
        setServerOnline(false);
        retryTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [config.serverUrl, config.peerId]);

  // Fetch own network profile
  useEffect(() => {
    serverApi
      .getRecommendation(config.peerId)
      .then((rec) => setNetworkProfile(rec.profile_name))
      .catch(() => {});
  }, [config.peerId]);

  const handleSendFromPeer = (peer: PeerInfo) =>
    setTransferTarget({ peer });

  const handleSendFromFile = (file: FileMetadata, peer?: PeerInfo) => {
    if (peer) {
      setTransferTarget({ peer, file });
    } else {
      const online = peers.find((p) => p.online);
      if (online) setTransferTarget({ peer: online, file });
    }
  };

  const handleTransferComplete = (result: TransferResult) => {
    setTransfers((prev) => [result, ...prev]);
    setTransferTarget(null);
  };

  async function handleCreateInvite() {
    setInviteLoading(true);
    try {
      const info = await serverApi.createInvite();
      setInviteToken(info.token);
      setShowInviteModal(true);
    } catch {
      // silently ignore — server may not have invite support or auth may be missing
    } finally {
      setInviteLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-950">
      {/* Header */}
      <header className="flex items-center gap-3 px-6 py-3 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2 text-brand-500">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21 5c-2-2-5-2-7 0l-3 4c-1-1-3-1-5 1l-1 2 3-1c1 2 3 3 5 2l1 3-1 4 3-2-1-4c2-1 4-3 4-6l2-2v-1z"/>
          </svg>
          <span className="font-semibold text-white text-sm">RockDove</span>
        </div>

        <div className="h-4 w-px bg-slate-700" />

        <span className="text-slate-400 text-xs font-mono">{config.peerId}</span>

        {networkProfile && (
          <span className="text-xs text-slate-500 bg-slate-800 rounded px-2 py-0.5">
            {networkProfile}
          </span>
        )}

        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${serverOnline ? "bg-emerald-400" : "bg-red-500"}`} />
          <span className="text-slate-500 text-xs truncate max-w-48">{config.serverUrl}</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="text-slate-500 text-xs">
            {peers.filter((p) => p.online).length} peers online
          </span>
          <button
            onClick={handleCreateInvite}
            disabled={inviteLoading}
            title="Generar token de invitación"
            className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40 bg-slate-800 hover:bg-slate-700 rounded px-2.5 py-1 transition-colors"
          >
            {inviteLoading ? "…" : "+ Invitar"}
          </button>
          <button
            onClick={onDisconnect}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Desconectar
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 overflow-auto">
        <div className="lg:col-span-1">
          <FileList peers={peers} onSend={handleSendFromFile} />
        </div>
        <div className="lg:col-span-2 flex flex-col gap-4">
          <PeerList peers={peers} currentPeerId={config.peerId} onSend={handleSendFromPeer} />
          <TransferHistory transfers={transfers} />
        </div>
      </div>

      {/* Transfer dialog */}
      {transferTarget && (
        <TransferDialog
          peer={transferTarget.peer}
          preselectedFile={transferTarget.file}
          serverUrl={config.serverUrl}
          peerId={config.peerId}
          onComplete={handleTransferComplete}
          onClose={() => setTransferTarget(null)}
        />
      )}

      {/* Invite token modal */}
      {showInviteModal && inviteToken && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h3 className="text-sm font-medium text-slate-200 mb-2">Token de invitación generado</h3>
            <p className="text-xs text-slate-500 mb-4">
              Compartí este token con el nuevo peer. Es de un solo uso y expira en 1 hora.
              El peer debe colocarlo como <code className="text-slate-400">INVITE_TOKEN</code> en su <code className="text-slate-400">.env</code>.
            </p>
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 mb-4 break-all">
              <p className="text-xs font-mono text-slate-300 select-all">{inviteToken}</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => navigator.clipboard.writeText(inviteToken)}
                className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg py-2 text-xs transition-colors"
              >
                Copiar
              </button>
              <button
                onClick={() => { setShowInviteModal(false); setInviteToken(null); }}
                className="flex-1 bg-brand-600 hover:bg-brand-700 text-white rounded-lg py-2 text-xs transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
