/** The seats, and where they are remembered — WITHOUT three.
 *
 *  Every line of this was in `PitchScene.tsx`. None of it ever needed WebGL:
 *  it is three arrays of numbers, some localStorage and a string formatter.
 *  It moved because the toolbar that reads it now has to render on a phone
 *  BEFORE anyone has asked for a 3D scene, and a toolbar that imports three
 *  is a 600KB toolbar.
 *
 *  `PitchScene` re-exports the lot, so existing imports are unchanged.
 */

import { PITCH_L } from "./dims";

/** A camera's name. NOT a fixed union: the list of seats belongs to whoever
 *  is looking at the scene, so a name is whatever they called it. */
export type ViewName = string;

export type Vec3 = [number, number, number];
export type Seat = { pos: Vec3; target: Vec3 };
export type Cam = Seat & { name: string };

export type Focus = {
  pos: Vec3;
  target: Vec3;
};

/** Where each seat is AND what it looks at, and both depend on WHAT IS BEING
 *  FRAMED.
 *
 *  One set of positions was used for every mode, sized for the full 105
 *  metres — so on a part pitch the camera sat eighty metres from a
 *  fifty-metre subject and everything was a postage stamp in the middle of
 *  a lot of dark blue.
 *
 *  The part-pitch seats also aim well up the pitch rather than at the middle
 *  of what is drawn: shots cluster between the penalty spot and the edge of
 *  the box, and framing the centre wastes a third of the picture on grass
 *  nobody shoots from.
 *
 *  FROM HALFWAY is the one seat with a direction in it. Every other view
 *  frames the subject and the reader works out which way is which; this one
 *  is the attacking view — stood behind the play, looking at the goal being
 *  shot at — which only means anything if the camera is actually pointed
 *  down the pitch rather than at the middle of what is drawn.
 *
 *  THESE ARE DEFAULTS, NOT THE LAST WORD. The tuner lets whoever is looking
 *  at the scene fly the camera where they want it and capture the seat;
 *  captured seats win over everything here.
 */
/** OVERHEAD SITS ON THE −z SIDE OF ITS TARGET, and the 0.1 is not noise.
 *
 *  Looking straight down is the one degenerate case for `lookAt`: the up
 *  vector is parallel to the view and which way the image lands is decided
 *  by whatever tiny offset happens to exist. With the camera on the +z side
 *  the resolved up comes out as world −z, so the attacking goal is at the
 *  BOTTOM of the picture — upside down against every football diagram ever
 *  drawn, which reads to anyone looking at it as "the sides are swapped".
 *  Nudging the camera to the far side of the target instead puts the attack
 *  up the screen, where it belongs.
 */
const FULL: Cam[] = [
  { name: "overhead", pos: [0, 96, -0.1], target: [0, 0, 0] },
  { name: "touchline", pos: [74, 26, 0], target: [0, 0, 0] },
  { name: "behind the goal", pos: [0, 18, PITCH_L / 2 + 38], target: [0, 0, 0] },
  { name: "from halfway", pos: [0, 13, -18], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [50, 34, 60], target: [0, 0, 0] },
];
/** Three quarters — what the shot map stands on. Aimed at z = 32 rather than
 *  the region's own middle of 13, because the extra quarter exists to stop
 *  rare long-range attempts falling off the grass, not to be looked at. */
const THREE_Q: Cam[] = [
  { name: "overhead", pos: [0, 66, 31.9], target: [0, 0, 32] },
  { name: "touchline", pos: [56, 19, 34], target: [0, 0, 34] },
  { name: "behind the goal", pos: [0, 13, PITCH_L / 2 + 34], target: [0, 0, 32] },
  { name: "from halfway", pos: [0, 12, -30], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [40, 24, 76], target: [0, 0, 32] },
];
const HALF: Cam[] = [
  { name: "overhead", pos: [0, 50, 37.9], target: [0, 0, 38] },
  { name: "touchline", pos: [46, 15, 38], target: [0, 0, 38] },
  { name: "behind the goal", pos: [0, 11, PITCH_L / 2 + 30], target: [0, 0, 38] },
  { name: "from halfway", pos: [0, 11, -14], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [33, 19, 74], target: [0, 0, 38] },
];

export type Mode = "full" | "three" | "half";
export const MODES: Mode[] = ["full", "three", "half"];
export const TABLES: Record<Mode, Cam[]> = { full: FULL, three: THREE_Q, half: HALF };
export const modeOf = (portion: number): Mode =>
  portion > 0.999 ? "full" : portion > 0.6 ? "three" : "half";
export const portionOf = (m: Mode) => (m === "full" ? 1 : m === "three" ? 0.75 : 0.5);

/* ------------------------------------------------------------ saved seats */

/** Captured seats live in the browser, per mode and per view.
 *
 *  They are read on EVERY scene, not only where the tuner is shown, so a
 *  seat tuned in the lab is immediately the seat the team page and the
 *  versus page use. "Copy code" then turns the lot into the literal above,
 *  which is how a captured seat stops being one person's browser setting and
 *  becomes the default everyone gets.
 */
const STORE = "predictorous.cameras.v3";
export type Saved = Partial<Record<Mode, Cam[]>>;

export function readSaved(): Saved {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(STORE) || "{}") as Saved;
  } catch {
    return {};
  }
}

/** WHICH CAMERA A VIEW OPENS ON, per view rather than per mode.
 *
 *  The seat a shot map should land on is not the seat a zone map should,
 *  even though both are looking at the same pitch — one wants to be behind
 *  the goal and the other wants to be above it. That choice was hard-coded
 *  in every view as a string nobody could change without editing the file,
 *  which is the same mistake the camera list itself used to be.
 *
 *  Keyed by a scene name so a view keeps its own answer, and read with a
 *  fallback so a scene that has never been set still opens somewhere
 *  sensible.
 */
const OPENS = "predictorous.cameraDefaults.v1";

export function defaultCam(scene: string, fallback: ViewName): ViewName {
  if (typeof window === "undefined" || !scene) return fallback;
  try {
    const d = JSON.parse(window.localStorage.getItem(OPENS) || "{}");
    return typeof d[scene] === "string" ? (d[scene] as ViewName) : fallback;
  } catch {
    return fallback;
  }
}

export function setOpensOn(scene: string, name: string) {
  try {
    const d = JSON.parse(window.localStorage.getItem(OPENS) || "{}");
    d[scene] = name;
    window.localStorage.setItem(OPENS, JSON.stringify(d));
  } catch {
    /* blocked storage — the choice still applies for this session */
  }
}

export function camsFor(saved: Saved, mode: Mode): Cam[] {
  const own = saved[mode];
  return own && own.length ? own : TABLES[mode];
}

export function writeSaved(s: Saved) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(s));
  } catch {
    /* private mode, blocked storage — the seat still applies this session */
  }
}

const n1 = (v: number) => Math.round(v * 10) / 10;
export const round1 = n1;

/** Emits the seat tables exactly as they appear in this file, with captured
 *  seats substituted in — so tuning ends in a paste, not a transcription. */
export function asCode(saved: Saved) {
  const row = (c: Cam) =>
    `  { name: ${JSON.stringify(c.name)}, pos: [${c.pos.join(", ")}], ` +
    `target: [${c.target.join(", ")}] },`;
  const table = (name: string, mode: Mode) =>
    `const ${name}: Cam[] = [\n` +
    camsFor(saved, mode).map(row).join("\n") +
    `\n];`;
  return [
    table("FULL", "full"),
    table("THREE_Q", "three"),
    table("HALF", "half"),
  ].join("\n");
}
