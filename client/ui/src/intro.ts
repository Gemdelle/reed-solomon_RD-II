export function markIntroForPlayback() {
  sessionStorage.setItem("rockdove-play-intro", "1");
}

export function shouldPlayIntro() {
  return sessionStorage.getItem("rockdove-play-intro") === "1";
}

export function clearIntroFlag() {
  sessionStorage.removeItem("rockdove-play-intro");
}
