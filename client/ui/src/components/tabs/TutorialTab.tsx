import { useState } from "react";
import type { ReactNode } from "react";
import logo from "../../assets/logo.png";
import bird from "../../assets/bird-1.png";
import computer from "../../assets/computer-logo.png";

/* ── Pixel-art: un paisajito que "enviamos" y reconstruimos ───── */

const SCENE_W = 16;
const SCENE_H = 12;

// Color de cada píxel del paisaje (cielo, sol, montañas con nieve).
function sceneColor(x: number, y: number): string {
  const dx = x - 12;
  const dy = y - 3;
  if (dx * dx + dy * dy <= 4) return "#fbbf24"; // sol

  const spread = y - 5; // montaña principal, pico en x=5
  if (y >= 5 && x >= 5 - spread && x <= 5 + spread) {
    return y <= 6 ? "#e2e8f0" : "#22c55e"; // nieve arriba, verde abajo
  }

  const spread2 = y - 7; // montaña secundaria, pico en x=11
  if (y >= 7 && x >= 11 - spread2 && x <= 11 + spread2) return "#16a34a";

  return "#38bdf8"; // cielo
}

type SceneMode = "clean" | "bands" | "broken";

function PixelScene({ px = 10, mode = "clean" }: { px?: number; mode?: SceneMode }) {
  const rows: ReactNode[] = [];
  for (let y = 0; y < SCENE_H; y++) {
    const cols: ReactNode[] = [];
    for (let x = 0; x < SCENE_W; x++) {
      let c = sceneColor(x, y);
      if (mode === "bands" && (y === 3 || y === 4 || y === 8 || y === 9)) c = "#475569";
      if (mode === "broken" && (x * 7 + y * 13) % 10 < 5) c = "#334155";
      cols.push(<div key={x} style={{ width: px, height: px, background: c }} />);
    }
    rows.push(
      <div key={y} style={{ display: "flex" }}>
        {cols}
      </div>
    );
  }
  return (
    <div
      className="overflow-hidden rounded-md ring-1 ring-slate-700"
      style={{ width: SCENE_W * px, imageRendering: "pixelated" }}
    >
      {rows}
    </div>
  );
}

/* ── Circulitos: bloques de datos y paridad ──────────────────── */

function DotGrid({
  data,
  parity,
  lost = [],
}: {
  data: number;
  parity: number;
  lost?: number[];
}) {
  const total = data + parity;
  return (
    <div className="grid w-max grid-cols-8 gap-2">
      {Array.from({ length: total }, (_, i) => {
        const isParity = i >= data;
        const isLost = lost.includes(i);
        let cls = isParity
          ? "bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.55)]"
          : "bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.55)]";
        if (isLost) cls = "border-2 border-dashed border-slate-600 bg-transparent shadow-none";
        return (
          <span
            key={i}
            style={{ animationDelay: `${i * 0.02}s` }}
            className={`animate-pixel-pop h-6 w-6 rounded-full ${cls}`}
          />
        );
      })}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <span className={`h-4 w-4 rounded-full ${color}`} />
      {label}
    </div>
  );
}

/* ── Flujo: dos peers con puntos que viajan ──────────────────── */

function PeerFlow() {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <div className="flex flex-col items-center gap-0.5">
          <img src={computer} alt="Peer A" className="h-12 w-12 object-contain" />
          <span className="text-xs text-slate-400">Peer A</span>
        </div>

        <div className="relative h-8 w-36">
          <div className="transfer-line-flow absolute top-1/2 w-full -translate-y-1/2" />
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              style={{ animationDelay: `${i * 0.45}s` }}
              className="dot-travel absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-brand-400 shadow-[0_0_10px_rgba(129,140,248,0.7)]"
            />
          ))}
          <span className="absolute -top-1 left-1/2 -translate-x-1/2 text-sm text-brand-400">
            directo
          </span>
        </div>

        <div className="flex flex-col items-center gap-0.5">
          <img src={computer} alt="Peer B" className="h-12 w-12 object-contain" />
          <span className="text-xs text-slate-400">Peer B</span>
        </div>
      </div>

      <div className="w-max rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400">
        Servidor: <span className="text-slate-500">coordina, no transporta</span>
      </div>
    </div>
  );
}

function TransportCard({
  name,
  color,
  dot,
  points,
}: {
  name: string;
  color: string;
  dot: string;
  points: string[];
}) {
  return (
    <div className={`flex-1 rounded-xl border ${color} bg-slate-900/60 p-3`}>
      <div className="mb-1.5 flex items-center gap-2">
        <span className={`h-2.5 w-2.5 animate-gentle-pulse rounded-full ${dot}`} />
        <span className="font-display text-lg">{name}</span>
      </div>
      <ul className="space-y-1 text-xs text-slate-400">
        {points.map((p) => (
          <li key={p} className="flex gap-2">
            <span className="text-slate-600">›</span>
            {p}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Donut de redundancia: ámbar = paridad, cyan = datos.
function RedundancyDonut() {
  return (
    <div className="flex items-center gap-4">
      <div
        className="relative flex h-24 w-24 flex-shrink-0 items-center justify-center rounded-full"
        style={{ background: "conic-gradient(#f59e0b 0 25%, #22d3ee 25% 100%)" }}
      >
        <div className="flex h-16 w-16 flex-col items-center justify-center rounded-full bg-slate-900">
          <span className="font-display text-2xl text-brand-400">25%</span>
          <span className="text-[10px] text-slate-500">redundancia</span>
        </div>
      </div>
      <div className="space-y-1.5">
        <Legend color="bg-cyan-400" label="24 datos" />
        <Legend color="bg-amber-400" label="8 paridad" />
        <div className="mt-1 flex flex-wrap gap-1.5">
          {["pérdida", "latencia", "jitter"].map((m) => (
            <span
              key={m}
              className="rounded-full border border-slate-700 px-2.5 py-0.5 text-xs text-slate-400"
            >
              {m}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function StateChip({
  label,
  desc,
  tone,
  mode,
}: {
  label: string;
  desc: string;
  tone: "ok" | "degraded" | "failed";
  mode: SceneMode;
}) {
  const styles = {
    ok: "border-emerald-500/40 text-emerald-400",
    degraded: "border-amber-500/40 text-amber-400",
    failed: "border-rose-500/40 text-rose-400",
  }[tone];
  return (
    <div className={`flex-1 rounded-xl border ${styles} bg-slate-900/60 p-2 text-center`}>
      <div className="mx-auto mb-1 w-max">
        <PixelScene px={5} mode={mode} />
      </div>
      <div className="font-display text-sm uppercase tracking-wide">{label}</div>
      <div className="mt-0.5 text-xs leading-snug text-slate-400">{desc}</div>
    </div>
  );
}

// Nido para la esquina superior derecha de cada cuadrante.
function Nest() {
  return (
    <svg width="60" height="40" viewBox="0 0 70 46" aria-hidden>
      <ellipse cx="35" cy="32" rx="31" ry="13" fill="#6b4423" />
      <ellipse cx="35" cy="27" rx="22" ry="8" fill="#4a2f18" />
      <ellipse cx="29" cy="24" rx="4.5" ry="5.5" fill="#eef2fb" />
      <ellipse cx="38" cy="25" rx="4.5" ry="5.5" fill="#eef2fb" />
      <path d="M6 30 Q22 20 38 30" stroke="#8a5a2b" strokeWidth="2" fill="none" />
      <path d="M32 34 Q46 24 62 32" stroke="#7c4f26" strokeWidth="2" fill="none" />
      <path d="M10 36 Q30 30 58 36" stroke="#8a5a2b" strokeWidth="1.5" fill="none" />
    </svg>
  );
}

/* ── Pasos ───────────────────────────────────────────────────── */

interface Step {
  title: string;
  points: string[];
  visual?: ReactNode;
}

const STEPS: Step[] = [
  {
    title: "BASE DE ROCKDOVE",
    points: [
      "reconstruir imagen con Reed-Solomon",
      "flujo teórico y práctico",
    ],
    visual: (
      <div className="flex items-center gap-4">
        <PixelScene px={10} />
        <img src={logo} alt="RockDove" className="animate-logo-float h-16 w-16 object-contain" />
      </div>
    ),
  },
  {
    title: "ARCHIVO",
    points: [
      "se parte en 32 bloques",
    ],
    visual: <DotGrid data={32} parity={0} />,
  },
  {
    title: "DATOS Y PARIDAD",
    points: [
      "bloques de datos",
      "bloques de paridad: respaldo calculados matemáticamente para reconstruir",
    ],
    visual: (
      <div className="space-y-2">
        <DotGrid data={24} parity={8} />
        <div className="flex gap-4">
          <Legend color="bg-cyan-400" label="24 datos" />
          <Legend color="bg-amber-400" label="8 paridad" />
        </div>
      </div>
    ),
  },
  {
    title: "PROPIEDAD CLAVE",
    points: [
      "no importa cuáles",
      "importa cuántos",
    ],
    visual: (
      <div className="flex items-center gap-3">
        <div className="text-center">
          <PixelScene px={7} mode="bands" />
          <span className="mt-0.5 block text-xs text-slate-500">llegan con huecos</span>
        </div>
        <span className="font-display text-2xl text-brand-400">→</span>
        <div className="text-center">
          <PixelScene px={7} mode="clean" />
          <span className="mt-0.5 block text-xs text-emerald-400">✔ reconstruida</span>
        </div>
      </div>
    ),
  },
  {
    title: "FLUJO",
    points: [
      "Peer destino",
      "Archivo o imagen",
      "Transporte por el que van a viajar los bloques",
      "Política de aceptación",
      "Bloques viajan entre peers",
      "Servidor coordina, NO transporta",
    ],
    visual: <PeerFlow />,
  },
  {
    title: "CANAL",
    points: [
      "UDP: rápido sin garantizar orden, NO reenvía automáticamente",
      "Reed-Solomon recupera",
      "QUIC: sobre UDP con ventajas modernas",
      "Coordinación por streams",
      "Datagrams para datos, NO reenvía",
    ],
    visual: (
      <div className="flex gap-3">
        <TransportCard
          name="UDP"
          color="border-slate-700"
          dot="bg-slate-400"
          points={["Rápido y simple.", "No reenvía lo perdido → ideal para Reed-Solomon."]}
        />
        <TransportCard
          name="QUIC"
          color="border-brand-800"
          dot="bg-brand-400"
          points={[
            "Sobre UDP, cifrado y autenticación.",
            "streams: control confiable.",
            "datagrams: datos, no reenvían.",
          ]}
        />
      </div>
    ),
  },
  {
    title: "REDUNDANCIA",
    points: [
      "Redundancia: % de respaldo agregado al archivo",
      "Paridad: bloques generados a partir de % de redundancia",
      "Ejemplo: R 25% → 32 (24D + 8P)",
      "Tolera hasta 8 pérdidas",
      "R adaptativa: según condiciones de red (pérdida, latencia, jitter)",
      "Cantidad de redundancia",
    ],
    visual: <RedundancyDonut />,
  },
  {
    title: "LOS 3 ESTADOS",
    points: [
      "OK: sin reconstrucción",
      "DEGRADED: hubo pérdida y reconstrucción",
      "FAILED: se perdió más de lo que la paridad cubría",
    ],
    visual: (
      <div className="flex gap-3">
        <StateChip label="OK" tone="ok" desc="llega bien" mode="clean" />
        <StateChip label="Degraded" tone="degraded" desc="se recupera" mode="bands" />
        <StateChip label="Failed" tone="failed" desc="no se puede" mode="broken" />
      </div>
    ),
  },
  {
    title: "¿POR QUÉ A VECES RECUPERA MENOS?",
    points: [
      "Pérdida: 6",
      "Recuperados: 3",
      "Tipos de bloques",
      "Reconstrucción necesaria",
      "Menos bloques que el mínimo",
    ],
    visual: (
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <span
              key={i}
              style={{ animationDelay: `${i * 0.05}s` }}
              className={`animate-pixel-pop h-6 w-6 rounded-full ${
                i < 3 ? "bg-cyan-400" : "border-2 border-dashed border-amber-500/60"
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-slate-500">3 datos recuperados · 3 paridad no hacían falta</span>
      </div>
    ),
  },
  {
    title: "DEMO",
    points: ["Pasamos a verlo funcionando con dos peers reales."],
    visual: (
      <div className="flex items-center gap-3">
        <img src={bird} alt="" className="animate-bird-bob h-12 w-12 object-contain" />
        <span className="font-display text-2xl text-brand-400">→</span>
      </div>
    ),
  },
];

const PAGE_SIZE = 4;
const PAGE_COUNT = Math.ceil(STEPS.length / PAGE_SIZE);

/* ── Cuadrante ───────────────────────────────────────────────── */

function Quadrant({
  step,
  n,
  active,
  birdKey,
}: {
  step: Step;
  n: number;
  active: boolean;
  birdKey: string;
}) {
  return (
    <div
      className={`animate-fade-in-up relative flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border bg-slate-900/50 p-3 transition-colors ${
        active ? "border-brand-600 ring-2 ring-brand-600/50" : "border-slate-800"
      }`}
    >
      {/* Nido + pájaro en la esquina superior derecha */}
      <div className="pointer-events-none absolute right-3 top-2 h-12 w-16">
        <div className="absolute bottom-0 right-0 scale-90">
          <Nest />
        </div>
        {active ? (
          <img
            key={birdKey}
            src={bird}
            alt=""
            className="animate-tutorial-bird-in absolute -top-0.5 right-3 h-10 w-10 object-contain"
          />
        ) : null}
      </div>

      <div className="flex flex-shrink-0 flex-col items-center gap-2 px-2 pt-1 text-center">
        <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-900 font-display text-lg text-brand-400">
          {n}
        </span>
        <h2 className="text-xl leading-snug">{step.title}</h2>
      </div>

      <ul className="mt-3 flex-shrink-0 space-y-2 px-1 text-left text-lg leading-relaxed text-slate-200">
        {step.points.map((p) => (
          <li key={p} className="flex items-start gap-2.5">
            <span className="mt-2 h-2.5 w-2.5 flex-shrink-0 bg-brand-400 shadow-[0_0_6px_rgba(129,140,248,0.7)]" />
            <span>{p}</span>
          </li>
        ))}
      </ul>

      {step.visual ? (
        <div className="mt-auto flex min-h-0 flex-1 items-center justify-center overflow-hidden pt-2">
          {step.visual}
        </div>
      ) : null}
    </div>
  );
}

/* ── Componente principal ────────────────────────────────────── */

export default function TutorialTab() {
  const [page, setPage] = useState(0);
  const [revealed, setRevealed] = useState(1);

  const pageSteps = STEPS.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  const activeInPage = revealed - 1;
  const isLastPage = page === PAGE_COUNT - 1;
  const pageComplete = revealed >= pageSteps.length;
  const allDone = isLastPage && pageComplete;
  const globalStep = page * PAGE_SIZE + revealed;

  function next() {
    if (!pageComplete) setRevealed((r) => r + 1);
    else if (!isLastPage) {
      setPage((p) => p + 1);
      setRevealed(1);
    }
  }

  function back() {
    if (revealed > 1) setRevealed((r) => r - 1);
    else if (page > 0) {
      const prevLen = Math.min(PAGE_SIZE, STEPS.length - (page - 1) * PAGE_SIZE);
      setPage((p) => p - 1);
      setRevealed(prevLen);
    }
  }

  function reset() {
    setPage(0);
    setRevealed(1);
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden px-[5%] pb-[5%] pt-[3%]">
      {/* Encabezado */}
      <div className="mb-3 flex flex-shrink-0 items-center gap-4">
        <img src={logo} alt="RockDove" className="animate-logo-float h-11 w-11 object-contain" />
        <div>
          <h1 className="text-2xl">Cómo funciona RockDove</h1>
          <p className="mt-0.5 text-sm text-slate-400">
            Pantalla {page + 1} de {PAGE_COUNT} · paso {globalStep} de {STEPS.length}
          </p>
        </div>
      </div>

      {/* Cartas verticales apiladas hacia la derecha */}
      <div key={page} className="flex min-h-0 flex-1 flex-row gap-4 overflow-hidden">
        {Array.from({ length: PAGE_SIZE }, (_, i) => {
          const step = pageSteps[i];
          const n = page * PAGE_SIZE + i + 1;
          if (!step || i >= revealed) return null;
          return (
            <div
              key={i}
              className="h-full flex-shrink-0 overflow-hidden"
              style={{ width: "calc((100% - 3 * 1rem) / 4)" }}
            >
              <Quadrant
                step={step}
                n={n}
                active={i === activeInPage}
                birdKey={`${page}-${i}`}
              />
            </div>
          );
        })}
      </div>

      {/* Controles */}
      <div className="mt-3 flex flex-shrink-0 items-center justify-between gap-3">
        <button
          onClick={back}
          disabled={page === 0 && revealed <= 1}
          className="rounded-lg border border-slate-700 px-5 py-2.5 text-base text-slate-400 transition-colors hover:text-slate-200 disabled:opacity-30"
        >
          ← Atrás
        </button>

        {allDone ? (
          <button
            onClick={reset}
            className="rounded-lg border border-slate-700 px-5 py-2.5 text-base text-slate-400 transition-colors hover:text-slate-200"
          >
            ↺ Reiniciar
          </button>
        ) : (
          <button
            onClick={next}
            className="bird-btn rounded-lg bg-brand-600 px-8 py-2.5 text-base font-medium text-white transition-colors hover:bg-brand-500"
          >
            {pageComplete ? "Siguiente pantalla →" : "OK, seguir →"}
          </button>
        )}
      </div>
    </div>
  );
}
