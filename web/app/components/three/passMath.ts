/** What a pass IS, and the arithmetic about it — WITHOUT three.
 *
 *  Lifted out of `PassCloud.tsx` unchanged, for the same reason the shot
 *  maths was: the flat pass map has to know what "led to a shot" is coloured
 *  and whether a pass left the ground, and importing the ribbon renderer to
 *  ask brings the whole WebGL stack with it.
 *
 *  `PassCloud` re-exports all of it, so nothing that imports from there has
 *  to change.
 */

import { PITCH_L, PITCH_W, toX, toZ } from "./dims";

export const BASE_Y = 0.1; // clear of the painted markings

/** How high a lofted pass climbs. Proportional to its length, because a
 *  clipped ball forward and a goalkeeper's punt downfield are not the same
 *  shape, and capped so a 70m clearance does not leave the picture. */
const CLIMB = 0.17;
export const CLIMB_MAX = 8.5;

export type Pass = {
  /** Opta x, ALONG the pitch, 0 at their own goal line. The names read
   *  backwards because they were written for the scene's axes. */
  sx: number;
  /** Opta y, ACROSS the pitch, 0 at the attacking side's right touchline. */
  sz: number;
  ex: number;
  ez: number;
  flags: number;
  player: string;
  /** Who received it — INFERRED from the next event in the stream, since the
   *  feed records no receiver. Empty when the pass was not completed, or
   *  when an opponent got between the two. */
  to: string;
  minute: number;
  opponent: string;
  home: boolean;
};

/** Bit meanings, as the build script writes them. */
export const BIT = {
  ok: 1, air: 2, cross: 4, through: 8, key: 16,
  assist: 32, set: 64, long: 128, big: 256, head: 512,
} as const;

/** The classes a reader actually asks about, in the order that decides
 *  which colour wins when a pass is several of them at once — an assist
 *  that was also a cross is an assist. */
export const CLASSES = [
  { key: "assist", label: "assist", colour: "#22c55e",
    hit: (f: number) => !!(f & BIT.assist) },
  { key: "key", label: "led to a shot", colour: "#f59e0b",
    hit: (f: number) => !!(f & BIT.key) },
  { key: "lost", label: "lost", colour: "#ef4444",
    hit: (f: number) => !(f & BIT.ok) },
  { key: "ok", label: "completed", colour: "#38bdf8",
    hit: () => true },
] as const;

export const classOf = (f: number) => CLASSES.find((c) => c.hit(f))!;

export const lengthOf = (p: Pass) =>
  Math.hypot(((p.ex - p.sx) / 100) * PITCH_W, ((p.ez - p.sz) / 100) * PITCH_L);

/** Scene-space start and end. The Opta conversion lives in `dims` and is
 *  imported, never re-derived — two copies of that arithmetic is how a
 *  pitch ends up mirrored in one view and not the other. */
export function ends(p: Pass) {
  return {
    x0: toX(p.sz), z0: toZ(p.sx),
    x1: toX(p.ez), z1: toZ(p.ex),
  };
}

export function arcOf(p: Pass) {
  const { x0, z0, x1, z1 } = ends(p);
  const L = Math.hypot(x1 - x0, z1 - z0);
  const h = p.flags & BIT.air ? Math.min(CLIMB * L, CLIMB_MAX) : 0;
  return { x0, z0, x1, z1, L, h };
}

/** Point on a pass at 0..1 along it. */
export function at(p: Pass, t: number): [number, number, number] {
  const { x0, z0, x1, z1, h } = arcOf(p);
  return [
    x0 + (x1 - x0) * t,
    BASE_Y + h * 4 * t * (1 - t),
    z0 + (z1 - z0) * t,
  ];
}
