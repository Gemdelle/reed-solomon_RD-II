import logo from "../assets/logo.png";

interface Props {
  size?: "sm" | "lg";
}

export default function Logo({ size = "sm" }: Props) {
  const imgClass = size === "lg" ? "h-12 w-12" : "h-6 w-6";
  const textClass = size === "lg" ? "text-3xl" : "text-lg";

  return (
    <div className="inline-flex items-center gap-2 text-brand-500">
      <img src={logo} alt="" className={`${imgClass} object-contain ${size === "sm" ? "animate-logo-float" : ""}`} />
      <span className={`font-display text-white tracking-widest uppercase ${textClass}`}>RockDove</span>
    </div>
  );
}
