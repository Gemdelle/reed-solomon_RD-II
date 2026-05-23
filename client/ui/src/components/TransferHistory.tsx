import type { TransferResult } from "../types";

interface Props {
  transfers: TransferResult[];
}

const STATUS_CONFIG = {
  ok: { icon: "✅", label: "ok", color: "text-emerald-400", bg: "bg-emerald-950/30 border-emerald-900" },
  degraded: { icon: "⚠️", label: "degraded", color: "text-yellow-400", bg: "bg-yellow-950/30 border-yellow-900" },
  failed: { icon: "❌", label: "failed", color: "text-red-400", bg: "bg-red-950/30 border-red-900" },
  pending: { icon: "⏳", label: "pending", color: "text-slate-400", bg: "bg-slate-800/30 border-slate-700" },
};

export default function TransferHistory({ transfers }: Props) {
  if (transfers.length === 0) {
    return (
      <div className="bg-slate-900 rounded-xl border border-slate-800 px-4 py-6 text-center text-slate-600 text-sm">
        <div className="text-2xl mb-1">📋</div>
        Historial de transferencias
      </div>
    );
  }

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-800">
        <h2 className="text-sm font-medium text-slate-200">Historial</h2>
      </div>
      <ul className="divide-y divide-slate-800/50 max-h-48 overflow-auto">
        {transfers.map((t) => {
          const cfg = STATUS_CONFIG[t.status] ?? STATUS_CONFIG.pending;
          return (
            <li key={t.transfer_id} className={`flex items-center gap-3 px-4 py-2.5 border-l-2 ${cfg.bg}`}>
              <span className="text-base leading-none">{cfg.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium font-mono ${cfg.color}`}>{cfg.label}</span>
                  {t.status === "degraded" && (
                    <span className="text-xs text-slate-500">
                      RS recuperó {t.recovered_blocks}/{t.total_blocks} bloques
                    </span>
                  )}
                  {t.reason && (
                    <span className="text-xs text-slate-500">{t.reason}</span>
                  )}
                </div>
                <p className="text-xs text-slate-600 font-mono truncate mt-0.5">{t.transfer_id}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
