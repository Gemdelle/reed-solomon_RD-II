import bird1 from "../assets/bird-1.png";
import bird2 from "../assets/bird-2.png";
import bird3 from "../assets/bird-3.png";

const BIRDS = [bird1, bird2, bird3];

interface Props {
  /** Which bird sprite to show (0–2). */
  variant?: number;
  size?: "xs" | "sm";
  offline?: boolean;
}

export default function OnlineBird({ variant = 0, size = "sm", offline = false }: Props) {
  const dim = size === "xs" ? "h-4 w-4" : "h-5 w-5";

  if (offline) {
    return <div className={`${dim} rounded-full bg-slate-600 flex-shrink-0 opacity-50`} />;
  }

  return (
    <img
      src={BIRDS[variant % BIRDS.length]}
      alt=""
      className={`${dim} object-contain flex-shrink-0 animate-bird-bob`}
      style={{ animationDelay: `${(variant % 3) * 0.35}s` }}
    />
  );
}
