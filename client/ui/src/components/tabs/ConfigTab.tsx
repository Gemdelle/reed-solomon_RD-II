import { useCallback, useEffect, useState } from "react";
import { agentApi, serverApi } from "../../api";

interface Props {
  peerId: string;
  agentUrl: string;
  serverUrl: string;
}

const TRANSPORT_BADGE: Record<string, string> = {
  quic: "text-violet-400 bg-violet-950/50 border-violet-800",
  udp: "text-slate-500 bg-slate-800/50 border-slate-700",
};

interface HealthInfo {
  status: string;
  transport?: string;
  udp_host?: string;
  udp_port?: number;
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between text-sm gap-4">
      <span className="text-slate-400 flex-shrink-0">{label}</span>
      <span className="text-slate-200 font-mono text-right truncate">{children}</span>
    </div>
  );
}

export default function ConfigTab({ peerId, agentUrl, serverUrl }: Props) {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [pinging, setPinging] = useState(false);
  const [pingMs, setPingMs] = useState<number | null>(null);
  const [pingError, setPingError] = useState<string | null>(null);

  const appVersion = (import.meta as unknown as { env: Record<string, string> }).env.VITE_APP_VERSION ?? "1.1.0-beta.3";

  const loadHealth = useCallback(async () => {
    try {
      const h = await agentApi.health();
      setHealth(h as HealthInfo);
      setHealthError(null);
    } catch (e) {
      setHealthError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  async function handlePing() {
    setPinging(true);
    setPingMs(null);
    setPingError(null);
    const t0 = performance.now();
    try {
      await serverApi.health(serverUrl);
      setPingMs(Math.round(performance.now() - t0));
    } catch (e) {
      setPingError((e as Error).message);
    } finally {
      setPinging(false);
    }
  }

  const transport = (health as any)?.transport as string | undefined;
  const transportBadge = transport
    ? TRANSPORT_BADGE[transport.toLowerCase()] ?? TRANSPORT_BADGE.udp
    : null;

  return (
    <div className="space-y-4 overflow-auto h-full">
      {/* Peer info */}
      <section>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Peer
        </h3>
        <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 p-4 space-y-2">
          <InfoRow label="Peer ID">{peerId}</InfoRow>
          <InfoRow label="Agent URL">{agentUrl}</InfoRow>
          <InfoRow label="Server URL">{serverUrl}</InfoRow>
          <InfoRow label="Version">{appVersion}</InfoRow>
        </div>
      </section>

      {/* Transport + network */}
      <section>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Agente
        </h3>
        <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 p-4 space-y-2">
          {healthError && (
            <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
              {healthError}
            </p>
          )}

          <div className="flex justify-between text-sm gap-4">
            <span className="text-slate-400 flex-shrink-0">Transport</span>
            <span>
              {transportBadge && transport ? (
                <span className={`text-xs font-mono border rounded px-1.5 py-0.5 ${transportBadge}`}>
                  {transport.toUpperCase()}
                </span>
              ) : (
                <span className="text-slate-500 font-mono text-sm">—</span>
              )}
            </span>
          </div>

          <InfoRow label="UDP Host">
            {(health as any)?.udp_host ?? "—"}
          </InfoRow>
          <InfoRow label="UDP Port">
            {(health as any)?.udp_port != null ? String((health as any).udp_port) : "—"}
          </InfoRow>
        </div>
      </section>

      {/* Server connection */}
      <section>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Servidor
        </h3>
        <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 p-4 space-y-3">
          <InfoRow label="URL">{serverUrl}</InfoRow>

          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-slate-400">Latencia</span>
            <div className="flex items-center gap-3">
              {pingMs !== null && (
                <span className="text-sm font-mono text-emerald-400">{pingMs} ms</span>
              )}
              {pingError && (
                <span className="text-xs text-red-400 font-mono">{pingError}</span>
              )}
              <button
                onClick={handlePing}
                disabled={pinging}
                className="text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-40 text-slate-300 rounded-lg px-3 py-1.5 transition-colors"
              >
                {pinging ? "Midiendo…" : "Ping"}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
