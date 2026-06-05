import bird1 from "../assets/bird-1.png";
import bird2 from "../assets/bird-2.png";
import bird3 from "../assets/bird-3.png";
import logo from "../assets/logo.png";

const BIRDS = [
  { src: bird1, delay: "0s", top: "34%" },
  { src: bird2, delay: "0.5s", top: "46%" },
  { src: bird3, delay: "1s", top: "58%" },
];

export default function IntroSplash() {
  return (
    <div className="intro-splash fixed inset-0 z-[100] flex items-center justify-center overflow-hidden bg-slate-950/90 backdrop-blur-md">
      <div className="absolute inset-0 pointer-events-none">
        {BIRDS.map((bird, i) => (
          <img
            key={i}
            src={bird.src}
            alt=""
            className="intro-bird absolute h-24 w-24 object-contain drop-shadow-[0_0_12px_rgba(34,211,238,0.4)]"
            style={{ animationDelay: bird.delay, top: bird.top }}
          />
        ))}
      </div>

      <div className="intro-title relative z-10 flex flex-col items-center gap-4">
        <img src={logo} alt="" className="h-24 w-24 object-contain intro-title-logo" />
        <h1 className="text-6xl font-display tracking-[0.2em] uppercase intro-title-text flex items-baseline gap-1">
          <span className="text-white intro-title-rock">Rock</span>
          <span className="intro-title-dove">Dove</span>
        </h1>
        <p className="text-base text-slate-400 intro-title-tagline font-display tracking-widest uppercase">P2P · Reed-Solomon · Adaptive</p>
      </div>

      <div className="intro-burst absolute rounded-full border-2" />
    </div>
  );
}
