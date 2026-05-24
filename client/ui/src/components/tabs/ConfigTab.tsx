import { useCallback, useEffect, useState } from "react";
import type { AgentConfig } from "../../types";
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

  // Transport switcher state
  const [agentConfig, setAgentConfig] = useState<AgentConfig | null>(null);
  const [selectedMode, setSelectedMode] = useState<"udp" | "quic">("udp");
  const [applyingTransport, setApplyingTransport] = useState(false);
  const [transportSuccess, setTransportSuccess] = useState<string | null>(null);
  const [transportError, setTransportError] = useState<string | null>(null);

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

  useEffect(() => {
    agentApi.getConfig().then((cfg) => {
      setAgentConfig(cfg);
      setSelectedMode(cfg.transport_mode);
    }).catch(() => {});
  }, []);

  async function handleApplyTransport() {
    setApplyingTransport(true);
    setTransportSuccess(null);
    setTransportError(null);
    try {
      const res = await agentApi.setTransport(selectedMode);
      setTransportSuccess(`Transport actualizado a ${res.transport_mode.toUpperCase()}`);
      setAgentConfig((prev) => prev ? { ...prev, transport_mode: selectedMode } : prev);
      await loadHealth();
    } catch (e) {
      setTransportError((e as Error).message);
    } finally {
      setApplyingTransport(false);
    }
  }

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

          <div className="flex justify-between text-sm gap-4 items-center">
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

          {/* QUIC hint when running in UDP mode */}
          {transport === "udp" ? (
            <div className="mt-2 flex items-start gap-2 bg-slate-800/40 border border-slate-700/50 rounded-lg px-3 py-2.5 text-xs text-slate-500">
              <svg className="w-3.5 h-3.5 flex-shrink-0 mt-px text-slate-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>
                Para habilitar QUIC/TLS, reiniciá el agente con{" "}
                <code className="text-slate-400 bg-slate-800 rounded px-1">TRANSPORT_MODE=quic</code>
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {/* Transport switcher */}
      <section>
        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Transport
        </h3>
        <div className="bg-slate-800/40 rounded-lg border border-slate-700/50 p-4 space-y-3">
          {/* Current mode badge */}
          <div className="flex items-center justify-between text-sm gap-4">
            <span className="text-slate-400 flex-shrink-0">Modo actual</span>
            {agentConfig ? (
              <span className={`text-xs font-mono border rounded px-1.5 py-0.5 ${
                agentConfig.transport_mode === "quic"
                  ? TRANSPORT_BADGE.quic
                  : TRANSPORT_BADGE.udp
              }`}>
                {agentConfig.transport_mode.toUpperCase()}
              </span>
            ) : (
              <span className="text-slate-500 font-mono text-sm">—</span>
            )}
          </div>

          {/* Toggle buttons */}
          <div className="flex gap-2">
            {(["udp", "quic"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => {
                  setSelectedMode(mode);
                  setTransportSuccess(null);
                  setTransportError(null);
                }}
                className={`flex-1 py-2 text-xs font-mono rounded-lg border transition-colors ${
                  selectedMode === mode
                    ? mode === "quic"
                      ? "bg-violet-900/60 border-violet-700 text-violet-300"
                      : "bg-slate-700 border-slate-600 text-slate-200"
                    : "bg-slate-800/40 border-slate-700/50 text-slate-500 hover:text-slate-300 hover:border-slate-600"
                }`}
              >
                {mode.toUpperCase()}
              </button>
            ))}
          </div>

          {/* QUIC warning when switching from UDP */}
          {selectedMode === "quic" && agentConfig?.transport_mode === "udp" ? (
            <div className="flex items-start gap-2 bg-amber-950/30 border border-amber-800/50 rounded-lg px-3 py-2.5 text-xs text-amber-400">
              <svg className="w-3.5 h-3.5 flex-shrink-0 mt-px" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <span>QUIC requiere certificados TLS. Asegurate de que el agente esté configurado con los certs correspondientes.</span>
            </div>
          ) : null}

          {/* Apply button */}
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleApplyTransport}
              disabled={applyingTransport || selectedMode === agentConfig?.transport_mode}
              className="text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 rounded-lg px-4 py-1.5 transition-colors flex items-center gap-2"
            >
              {applyingTransport ? (
                <>
                  <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                  </svg>
                  Aplicando…
                </>
              ) : "Aplicar"}
            </button>
          </div>

          {/* Success message */}
          {transportSuccess ? (
            <p className="text-xs text-emerald-400 bg-emerald-950/40 border border-emerald-900 rounded-lg px-3 py-2">
              {transportSuccess}
            </p>
          ) : null}

          {/* Error message */}
          {transportError ? (
            <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
              Error: {transportError}
            </p>
          ) : null}
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
