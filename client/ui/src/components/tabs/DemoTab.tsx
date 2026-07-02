import { useRef, useState } from "react";
import type { DemoResult } from "../../types";
import { agentApi } from "../../api";

const STATUS_STYLE: Record<string, { label: string; cls: string; emoji: string }> = {
  ok: { label: "OK — llegó perfecto", cls: "text-emerald-400", emoji: "✅" },
  degraded: { label: "DEGRADED — Reed-Solomon lo reconstruyó", cls: "text-amber-400", emoji: "🛠️" },
  failed: { label: "FAILED — pérdida mayor a la capacidad", cls: "text-red-400", emoji: "❌" },
  pending: { label: "pending", cls: "text-slate-400", emoji: "…" },
  relayed: { label: "relayed", cls: "text-violet-400", emoji: "🔀" },
};

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

function ImageCard({
  title,
  subtitle,
  src,
  tone,
  placeholder,
}: {
  title: string;
  subtitle: string;
  src: string | null;
  tone: "neutral" | "bad" | "good";
  placeholder?: string;
}) {
  const ring =
    tone === "bad"
      ? "border-red-800/60"
      : tone === "good"
      ? "border-emerald-800/60"
      : "border-slate-700";
  return (
    <div className={`flex-1 min-w-0 rounded-xl border ${ring} bg-slate-900/60 overflow-hidden`}>
      <div className="px-3 py-2 border-b border-slate-800">
        <p className="text-sm font-medium text-slate-200">{title}</p>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
      <div className="aspect-square flex items-center justify-center bg-slate-950/60">
        {src ? (
          <img src={src} alt={title} className="max-h-full max-w-full object-contain" />
        ) : (
          <div className="text-center px-4">
            <div className="text-4xl mb-2">🚫</div>
            <p className="text-xs text-slate-500">{placeholder ?? "Sin imagen"}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DemoTab() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [redundancy, setRedundancy] = useState(0.25);
  const [loss, setLoss] = useState(0.2);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile(f: File | undefined) {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
    setPreview(URL.createObjectURL(f));
  }

  async function run() {
    if (!file) {
      setError("Elegí una imagen primero.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await agentApi.simulateDemo(file, redundancy, loss);
      setResult(r);
    } catch (e) {
      setError(`Error: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  const st = result ? STATUS_STYLE[result.status] ?? STATUS_STYLE.pending : null;

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto space-y-4">
        {/* Intro */}
        <div className="bird-panel rounded-xl p-4">
          <h2 className="font-medium text-slate-100">Demo Reed-Solomon</h2>
          <p className="text-sm text-slate-400 mt-1">
            Enviamos una imagen partida en bloques por un canal con pérdida. Mirá la diferencia entre
            recibirla <span className="text-red-400">sin corrección</span> (UDP crudo) y
            <span className="text-emerald-400"> con Reed-Solomon</span> (FEC).
          </p>
        </div>

        {/* Controls */}
        <div className="bird-panel rounded-xl p-4 space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={() => inputRef.current?.click()}
              className="bird-btn text-sm bg-brand-600 hover:bg-brand-700 text-white rounded-lg px-4 py-2 transition-colors"
            >
              {file ? "Cambiar imagen" : "Elegir imagen"}
            </button>
            {file && <span className="text-xs text-slate-400 font-mono truncate">{file.name}</span>}
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Redundancy */}
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-sm text-slate-300">Redundancia (respaldo)</label>
                <span className="text-sm font-mono text-brand-400">{pct(redundancy)}</span>
              </div>
              <input
                type="range"
                min={0.05}
                max={0.5}
                step={0.05}
                value={redundancy}
                onChange={(e) => setRedundancy(Number(e.target.value))}
                className="w-full accent-brand-500"
              />
              <p className="text-xs text-slate-500 mt-1">Más redundancia = tolera más pérdida (más lento).</p>
            </div>

            {/* Loss */}
            <div>
              <div className="flex justify-between mb-1">
                <label className="text-sm text-slate-300">Pérdida de paquetes (canal)</label>
                <span className="text-sm font-mono text-red-400">{pct(loss)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={0.6}
                step={0.05}
                value={loss}
                onChange={(e) => setLoss(Number(e.target.value))}
                className="w-full accent-red-500"
              />
              <p className="text-xs text-slate-500 mt-1">Cuánto se pierde en la red simulada.</p>
            </div>
          </div>

          <button
            onClick={run}
            disabled={loading || !file}
            className="bird-btn w-full sm:w-auto bg-brand-600 hover:bg-brand-700 disabled:opacity-40 text-white rounded-lg px-6 py-2.5 text-sm font-medium transition-colors"
          >
            {loading ? "Simulando…" : "▶ Simular transferencia"}
          </button>

          {error && (
            <p className="text-red-400 text-sm bg-red-950/40 border border-red-900 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {/* Result */}
        {result && st && (
          <div className="space-y-4">
            {/* Status banner */}
            <div className="bird-panel rounded-xl p-4">
              <p className={`text-lg font-semibold ${st.cls}`}>
                {st.emoji} {st.label}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-sm">
                <Stat label="Bloques enviados" value={`${result.blocks_total}`} />
                <Stat label="Bloques perdidos" value={`${result.blocks_dropped}`} tone="bad" />
                <Stat label="Paridad disponible" value={`${result.max_recoverable}`} />
                <Stat
                  label="Recuperados por RS"
                  value={`${result.recovered_blocks}`}
                  tone="good"
                />
              </div>
              <p className="text-xs text-slate-500 mt-3">
                n={result.n} · k={result.k} (datos) · paridad={result.parity} · necesita al menos {result.needed_blocks} bloques ·
                redundancia {pct(result.redundancy_level)} · pérdida {pct(result.loss_rate)}
                {result.reason ? ` · motivo: ${result.reason}` : ""}
              </p>
            </div>

            {/* Images */}
            <div className="flex flex-col md:flex-row gap-4">
              <ImageCard
                title="Original"
                subtitle="Lo que se quiso enviar"
                src={result.original_png}
                tone="neutral"
              />
              <ImageCard
                title="Sin Reed-Solomon"
                subtitle="Solo lo que llegó (UDP crudo)"
                src={result.naive_png}
                tone="bad"
              />
              <ImageCard
                title="Con Reed-Solomon"
                subtitle={
                  result.status === "failed"
                    ? "No alcanzó la paridad para reconstruir"
                    : "Reconstruida con FEC"
                }
                src={result.rs_png}
                tone="good"
                placeholder="Se perdieron más bloques que la paridad disponible. Subí la redundancia o bajá la pérdida."
              />
            </div>
          </div>
        )}

        {/* Preview before running */}
        {!result && preview && (
          <div className="bird-panel rounded-xl p-4">
            <p className="text-sm text-slate-400 mb-2">Imagen elegida:</p>
            <img src={preview} alt="preview" className="max-h-64 rounded-lg object-contain" />
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const cls = tone === "good" ? "text-emerald-400" : tone === "bad" ? "text-red-400" : "text-slate-200";
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-lg font-mono ${cls}`}>{value}</p>
    </div>
  );
}
