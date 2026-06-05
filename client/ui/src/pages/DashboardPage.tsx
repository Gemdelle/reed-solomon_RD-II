import { useEffect, useRef, useState } from "react";
import type { AppConfig, FileMetadata, PeerInfo, TransferResult } from "../types";
import { serverApi } from "../api";
import FileList from "../components/FileList";
import PeerList from "../components/PeerList";
import TransferDialog from "../components/TransferDialog";
import TransferHistory from "../components/TransferHistory";
import AdminPanel from "../components/AdminPanel";
import Logo from "../components/Logo";
import OnlineBird from "../components/OnlineBird";


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
  const [showAdmin, setShowAdmin] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Detect admin by probing the scopes endpoint (403 = not admin, 200 = admin)
  useEffect(() => {
    serverApi.getScopes().then(() => setIsAdmin(true)).catch(() => setIsAdmin(false));
  }, [config.serverUrl, config.token]);

  // WebSocket peer discovery
  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = serverApi.watchPeers(config.serverUrl, config.token);
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
  }, [config.serverUrl, config.peerId, config.token]);

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

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bird-header flex items-center gap-3 px-6 py-3 bg-slate-900/85 backdrop-blur-sm">
        <Logo />

        <div className="h-4 w-px bg-slate-700" />

        <span className="text-slate-400 text-sm font-mono">{config.peerId}</span>

        {networkProfile && (
          <span className="text-sm text-slate-500 bg-slate-800 rounded px-2 py-0.5">
            {networkProfile}
          </span>
        )}

        <div className="flex items-center gap-1.5">
          {serverOnline ? (
            <OnlineBird variant={1} size="xs" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse flex-shrink-0" />
          )}
          <span className="text-slate-500 text-sm truncate max-w-48">{config.serverUrl}</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className={`text-slate-500 text-sm flex items-center gap-1.5 ${peers.filter((p) => p.online).length > 0 ? "animate-gentle-pulse" : ""}`}>
            {peers.filter((p) => p.online).length > 0 && <OnlineBird variant={2} size="xs" />}
            {peers.filter((p) => p.online).length} peers online
          </span>
          {isAdmin && (
            <button
              onClick={() => setShowAdmin(true)}
              title="Panel de administración"
              className="text-sm text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 rounded px-2.5 py-1 transition-colors"
            >
              Admin
            </button>
          )}
          <button
            onClick={onDisconnect}
            className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
          >
            Desconectar
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 overflow-auto">
        <div className="lg:col-span-1 animate-fade-in-up">
          <FileList peers={peers} onSend={handleSendFromFile} />
        </div>
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="animate-fade-in-up stagger-1">
            <PeerList peers={peers} currentPeerId={config.peerId} onSend={handleSendFromPeer} />
          </div>
          <div className="animate-fade-in-up stagger-2">
            <TransferHistory transfers={transfers} />
          </div>
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

      {/* Admin panel */}
      {showAdmin && <AdminPanel onClose={() => setShowAdmin(false)} />}
    </div>
  );
}
