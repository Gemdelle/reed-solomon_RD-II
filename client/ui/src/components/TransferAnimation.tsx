import { useEffect, useState } from "react";
import computerLogo from "../assets/computer-logo.png";
import bird1 from "../assets/bird-1.png";
import bird2 from "../assets/bird-2.png";
import bird3 from "../assets/bird-3.png";

const BIRDS = [bird1, bird2, bird3];
const DOT_COLORS = ["bg-bird-magenta", "bg-bird-cyan", "bg-bird-violet"];
const DOT_GLOW = [
  "shadow-[0_0_8px_rgba(232,121,249,0.9)]",
  "shadow-[0_0_8px_rgba(34,211,238,0.9)]",
  "shadow-[0_0_8px_rgba(167,139,250,0.9)]",
];

const BIRD_CYCLE: boolean[][] = [
  [true, false, false],
  [true, true, false],
  [false, true, false],
  [false, true, true],
  [false, false, true],
  [true, false, true],
];

interface Props {
  targetPeer: string;
}

export default function TransferAnimation({ targetPeer }: Props) {
  const [birdSlots, setBirdSlots] = useState<boolean[]>([false, false, false]);

  useEffect(() => {
    let step = 0;
    const id = setInterval(() => {
      setBirdSlots(BIRD_CYCLE[step]);
      step = (step + 1) % BIRD_CYCLE.length;
    }, 750);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="py-4 px-1 overflow-visible">
      <p className="text-center text-xs text-slate-400 mb-8">
        Transfiriendo a <span className="font-mono text-slate-300">{targetPeer}</span>…
      </p>

      <div className="relative flex items-center justify-between gap-4 min-h-[200px] overflow-visible">
        <div className="flex flex-col items-center gap-2 flex-shrink-0 z-10 w-36">
          <div className="w-36 h-36 flex items-center justify-center overflow-visible">
            <img src={computerLogo} alt="" className="max-h-full max-w-full object-contain transfer-computer-pulse" />
          </div>
          <span className="text-xs text-slate-500">Vos</span>
        </div>

        <div className="relative flex-1 mx-1 h-24 overflow-visible">
          <div className="absolute top-1/2 left-0 right-0 h-px -translate-y-1/2 bg-gradient-to-r from-brand-600/20 via-brand-500/60 to-brand-600/20" />
          <div className="absolute top-1/2 left-0 right-0 transfer-line-flow" />

          {BIRDS.map((bird, i) => {
            const isBird = birdSlots[i];
            return (
              <div
                key={i}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
                style={{ left: `${25 + i * 25}%` }}
              >
                <div className="relative w-14 h-14 flex items-center justify-center">
                  <div
                    className={`absolute w-3 h-3 rounded-full transition-all duration-500 ${DOT_COLORS[i]} ${DOT_GLOW[i]} ${
                      isBird ? "opacity-0 scale-0" : "opacity-100 scale-100"
                    }`}
                  />
                  <img
                    src={bird}
                    alt=""
                    className={`absolute h-11 w-11 object-contain transition-all duration-500 ${
                      isBird ? "opacity-100 scale-100 transfer-bird-pop" : "opacity-0 scale-75"
                    }`}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-col items-center gap-2 flex-shrink-0 z-10 w-36">
          <div className="w-36 h-36 flex items-center justify-center overflow-visible">
            <img src={computerLogo} alt="" className="max-h-full max-w-full object-contain transfer-computer-pulse-right" />
          </div>
          <span className="text-xs text-slate-500 truncate max-w-full text-center">{targetPeer}</span>
        </div>
      </div>

      <p className="text-center text-[10px] text-slate-600 mt-6 animate-pulse">
        Palomas en camino…
      </p>
    </div>
  );
}
