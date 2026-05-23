import { useEffect, useState } from "react";
import { serverApi, getServerUrl } from "../api";
import type { DeviceTokenInfo } from "../types";

interface Props {
  onClose: () => void;
}

type Tab = "scopes" | "invites" | "device-tokens";

interface GeneratedInvite {
  token: string;
  deviceId: string;
  expiresAt: string;
}

// ── Scopes tab ────────────────────────────────────────────────────────────────

function ScopesTab() {
  const [scopes, setScopes] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [newGroup, setNewGroup] = useState("");
  const [newVisible, setNewVisible] = useState("");

  useEffect(() => {
    serverApi
      .getScopes()
      .then((cfg) => setScopes(cfg.scopes))
      .catch((e) => setError(`Error cargando scopes: ${(e as Error).message}`))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await serverApi.setScopes({ scopes });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch (e) {
      setError(`Error guardando: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  function addRule() {
    const group = newGroup.trim();
    if (!group) return;
    const visible = newVisible.split(",").map((s) => s.trim()).filter(Boolean);
    setScopes((prev) => ({ ...prev, [group]: visible }));
    setNewGroup("");
    setNewVisible("");
  }

  function removeRule(group: string) {
    setScopes((prev) => {
      const next = { ...prev };
      delete next[group];
      return next;
    });
  }

  function updateVisible(group: string, raw: string) {
    const visible = raw.split(",").map((s) => s.trim()).filter(Boolean);
    setScopes((prev) => ({ ...prev, [group]: visible }));
  }

  if (loading) return <p className="text-xs text-slate-500 py-4">Cargando…</p>;

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Configurá qué grupos puede ver cada grupo dentro de esta org.
        Usá <code className="text-slate-400">__all__</code> para acceso total.
      </p>

      {error && (
        <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {Object.keys(scopes).length === 0 ? (
        <p className="text-xs text-slate-600 italic">
          Sin reglas — cada grupo ve sólo sus propios peers.
        </p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 text-left">
              <th className="pb-2 font-medium w-1/3">Grupo</th>
              <th className="pb-2 font-medium">Puede ver (coma separado)</th>
              <th className="pb-2 w-6" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {Object.entries(scopes).map(([group, visible]) => (
              <tr key={group}>
                <td className="py-2 pr-3 font-mono text-slate-300">{group}</td>
                <td className="py-2 pr-2">
                  <input
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-slate-200 focus:outline-none focus:border-brand-500"
                    value={visible.join(", ")}
                    onChange={(e) => updateVisible(group, e.target.value)}
                  />
                </td>
                <td className="py-2">
                  <button
                    onClick={() => removeRule(group)}
                    className="text-slate-600 hover:text-red-400 transition-colors"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="border-t border-slate-800 pt-3">
        <p className="text-xs text-slate-500 mb-2">Nueva regla</p>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
            placeholder="Grupo"
            value={newGroup}
            onChange={(e) => setNewGroup(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRule()}
          />
          <input
            className="flex-[2] bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
            placeholder="Grupos visibles (ej: hq, field) o __all__"
            value={newVisible}
            onChange={(e) => setNewVisible(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addRule()}
          />
          <button
            onClick={addRule}
            className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg px-3 py-1.5 transition-colors"
          >
            +
          </button>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-2">
        {success && <span className="text-xs text-emerald-400 self-center">Guardado</span>}
        <button
          onClick={save}
          disabled={saving}
          className="text-xs bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-lg px-4 py-1.5 transition-colors"
        >
          {saving ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>
    </div>
  );
}

// ── Invites tab ───────────────────────────────────────────────────────────────

function InvitesTab() {
  const [deviceId, setDeviceId] = useState("");
  const [ttlHours, setTtlHours] = useState(24);
  const [group, setGroup] = useState("field");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generated, setGenerated] = useState<GeneratedInvite | null>(null);

  async function generate() {
    const id = deviceId.trim() || `device-${Math.random().toString(36).slice(2, 8)}`;
    setGenerating(true);
    setError(null);
    try {
      const info = await serverApi.createInvite(ttlHours * 3600);
      setGenerated({ token: info.token, deviceId: id, expiresAt: info.expires_at });
      setDeviceId("");
    } catch (e) {
      setError(`Error generando invite: ${(e as Error).message}`);
    } finally {
      setGenerating(false);
    }
  }

  const serverUrl = getServerUrl();
  const envSnippet = generated
    ? `SERVER_URL=${serverUrl}\nPEER_ID=${generated.deviceId}\nINVITE_TOKEN=${generated.token}\nUDP_HOST=0.0.0.0\nUDP_PORT=9001\n`
    : "";

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        Generá un token de invitación para un agente headless (IoT, edge, CI).
        El token es de un solo uso — el agente lo consume al registrarse.
      </p>

      {error && (
        <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">ID del dispositivo</label>
          <input
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
            placeholder="ej: sensor-planta-1 (auto si vacío)"
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Grupo</label>
          <input
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
            placeholder="field"
            value={group}
            onChange={(e) => setGroup(e.target.value)}
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Expira en (horas)</label>
          <input
            type="number"
            min={1}
            max={720}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
            value={ttlHours}
            onChange={(e) => setTtlHours(Number(e.target.value))}
          />
        </div>
      </div>

      <button
        onClick={generate}
        disabled={generating}
        className="text-xs bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-lg px-4 py-1.5 transition-colors"
      >
        {generating ? "Generando…" : "Generar invite"}
      </button>

      {generated && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400 font-medium">
              Config para <span className="font-mono text-slate-300">{generated.deviceId}</span>
            </p>
            <button
              onClick={() => navigator.clipboard.writeText(envSnippet)}
              className="text-xs text-slate-500 hover:text-slate-300 bg-slate-800 hover:bg-slate-700 rounded px-2 py-0.5 transition-colors"
            >
              Copiar .env
            </button>
          </div>
          <pre className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-300 select-all whitespace-pre overflow-x-auto">
            {envSnippet}
          </pre>
          <p className="text-xs text-slate-600">
            El token expira {new Date(generated.expiresAt).toLocaleString()}.
            Pegá este .env en el agente headless y ejecutalo — el token se consume al primer registro.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Device Tokens tab ─────────────────────────────────────────────────────────

function DeviceTokensTab() {
  const [label, setLabel] = useState("");
  const [peerId, setPeerId] = useState("");
  const [maxDays, setMaxDays] = useState("");   // "" = indefinido
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tokens, setTokens] = useState<DeviceTokenInfo[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [created, setCreated] = useState<DeviceTokenInfo | null>(null);
  const [copied, setCopied] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);

  useEffect(() => { void loadTokens(); }, []);

  async function loadTokens() {
    setLoadingList(true);
    try {
      const list = await serverApi.listDeviceTokens();
      setTokens(list);
    } catch {
      // lista vacía o sin permisos — silencioso
    } finally {
      setLoadingList(false);
    }
  }

  async function create() {
    if (!label.trim()) return;
    setCreating(true);
    setError(null);
    setCreated(null);
    try {
      const days = maxDays.trim() ? parseInt(maxDays, 10) : null;
      const info = await serverApi.createDeviceToken({
        label: label.trim(),
        peer_id: peerId.trim() || null,
        ttl_seconds: days ? days * 86400 : null,
      });
      setCreated(info);
      setLabel("");
      setPeerId("");
      setMaxDays("");
      await loadTokens();
    } catch (e) {
      setError(`Error creando token: ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }

  async function revoke(id: string) {
    setRevoking(id);
    setError(null);
    try {
      await serverApi.revokeDeviceToken(id);
      setTokens((prev) => prev.filter((t) => t.id !== id));
      if (created?.id === id) setCreated(null);
    } catch (e) {
      setError(`Error revocando: ${(e as Error).message}`);
    } finally {
      setRevoking(null);
    }
  }

  function copySnippet() {
    if (!created?.token) return;
    const serverUrl = getServerUrl();
    const pid = created.peer_id || created.label.toLowerCase().replace(/\s+/g, "-");
    const snippet = [
      `PEER_ID=${pid}`,
      `SERVER_URL=${serverUrl}`,
      `AGENT_API_URL=http://<device-ip>:8000`,
      `AGENT_SERVICE_TOKEN=${created.token}`,
    ].join("\n") + "\n";
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function formatExpiry(t: DeviceTokenInfo) {
    if (!t.expires_at) return "∞ indefinido";
    return new Date(t.expires_at).toLocaleDateString("es-AR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  }

  return (
    <div className="space-y-5">
      {/* ── Form ── */}
      <div className="space-y-3">
        <p className="text-xs text-slate-500">
          Cada dispositivo obtiene su propio token autogenerado. El valor completo
          sólo aparece al crearlo — guardalo antes de cerrar.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-slate-500 block mb-1">
              Etiqueta <span className="text-red-500">*</span>
            </label>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
              placeholder="ej: Sensor Planta A"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
            />
          </div>

          <div>
            <label className="text-xs text-slate-500 block mb-1">PEER_ID del dispositivo</label>
            <input
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500"
              placeholder="ej: edge-01 (opcional)"
              value={peerId}
              onChange={(e) => setPeerId(e.target.value)}
            />
          </div>

          <div>
            <label className="text-xs text-slate-500 block mb-1">
              Máximo tiempo (días)
            </label>
            <input
              type="number"
              min={1}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500"
              placeholder="∞  sin vencimiento"
              value={maxDays}
              onChange={(e) => setMaxDays(e.target.value)}
            />
          </div>
        </div>

        {error && (
          <p className="text-xs text-red-400 bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <button
          onClick={create}
          disabled={creating || !label.trim()}
          className="text-xs bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-lg px-4 py-1.5 transition-colors"
        >
          {creating ? "Generando…" : "Crear token"}
        </button>
      </div>

      {/* ── Token recién creado ── */}
      {created?.token && (
        <div className="rounded-xl border border-emerald-800/60 bg-emerald-950/30 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-400">
              Token creado — copialo ahora, no se vuelve a mostrar
            </span>
            <button
              onClick={copySnippet}
              className="text-xs text-slate-400 hover:text-slate-200 bg-slate-800 hover:bg-slate-700 rounded px-2 py-0.5 transition-colors"
            >
              {copied ? "¡Copiado!" : "Copiar .env"}
            </button>
          </div>
          <div className="space-y-1">
            <p className="text-xs text-slate-500">
              <span className="text-slate-400 font-medium">{created.label}</span>
              {created.peer_id && (
                <span className="ml-2 font-mono text-slate-500">{created.peer_id}</span>
              )}
              {created.expires_at ? (
                <span className="ml-2 text-slate-600">
                  · vence {new Date(created.expires_at).toLocaleDateString()}
                </span>
              ) : (
                <span className="ml-2 text-slate-600">· sin vencimiento</span>
              )}
            </p>
            <pre className="bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-emerald-300 select-all whitespace-pre overflow-x-auto break-all">
              {created.token}
            </pre>
          </div>
        </div>
      )}

      {/* ── Lista de tokens activos ── */}
      <div className="space-y-2">
        <p className="text-xs text-slate-500 font-medium">Tokens activos</p>
        {loadingList ? (
          <p className="text-xs text-slate-600">Cargando…</p>
        ) : tokens.length === 0 ? (
          <p className="text-xs text-slate-600 italic">Sin tokens activos.</p>
        ) : (
          <div className="space-y-1.5">
            {tokens.map((t) => (
              <div
                key={t.id}
                className="flex items-center gap-3 bg-slate-800/50 border border-slate-800 rounded-lg px-3 py-2"
              >
                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-200 truncate">
                      {t.label}
                    </span>
                    {t.peer_id && (
                      <span className="text-xs font-mono text-slate-500 bg-slate-700/60 rounded px-1.5 py-0.5 shrink-0">
                        {t.peer_id}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-slate-600 truncate">
                      {t.token_preview}
                    </span>
                    <span className="text-xs text-slate-600 shrink-0">
                      {formatExpiry(t)}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => revoke(t.id)}
                  disabled={revoking === t.id}
                  title="Revocar token"
                  className="text-slate-600 hover:text-red-400 disabled:opacity-40 transition-colors shrink-0 text-sm leading-none"
                >
                  {revoking === t.id ? "…" : "✕"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

const TAB_LABELS: Record<Tab, string> = {
  "scopes": "Visibilidad de grupos",
  "invites": "Invites (un uso)",
  "device-tokens": "Device Tokens",
};

export default function AdminPanel({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>("device-tokens");

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <h2 className="text-sm font-semibold text-slate-200">Panel de administración</h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 text-lg leading-none transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-800 overflow-x-auto">
          {(Object.keys(TAB_LABELS) as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap ${
                tab === t
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-slate-500 hover:text-slate-300"
              }`}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto px-5 py-4">
          {tab === "scopes" && <ScopesTab />}
          {tab === "invites" && <InvitesTab />}
          {tab === "device-tokens" && <DeviceTokensTab />}
        </div>

        {/* Footer */}
        <div className="flex justify-end px-5 py-3 border-t border-slate-800">
          <button
            onClick={onClose}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
