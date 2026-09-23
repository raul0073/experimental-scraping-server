/** What a shot IS, and the arithmetic about it — WITHOUT three.
 *
 *  All of this was in `ShotCloud.tsx`. None of it is 3D: it is a record type,
 *  two colour tables and some trigonometry. It moved because the shot view
 *  now has a flat SVG rendering that has to draw the same shots in the same
 *  colours, and a flat rendering that imports `ShotCloud` to learn what green
 *  means downloads the whole WebGL stack to find out.
 *
 *  `ShotCloud` re-exports every name here, so existing imports are unchanged
 *  and there is still one definition of each.
 *
 *  Understat's frame: x and y both 0-1 over 105 by 68, x = 1 at the goal
 *  being attacked. Penalties sit at exactly (0.885, 0.500), which confirms
 *  both axes. Low y is the attacking side's RIGHT, the same as Opta — see
 *  the note on `toX` in Pitch3D.
 */

import { PITCH_L, PITCH_W } from "./dims";

export const GOAL_W = 7.32;
export const GOAL_H = 2.44;
const POST = GOAL_W / 2;
const GOAL_Z = PITCH_L / 2;

export const shotX = (uy: number) => (uy - 0.5) * PITCH_W;
export const shotZ = (ux: number) => (ux - 0.5) * PITCH_L;

export type Shot = {
  x: number; y: number; xg: number;
  result: string; situation: string; foot: string;
  minute: number; player: string; assist: string;
  opponent: string; home: boolean;
  /** where the ball crossed the line, in the goal's own frame: metres
   *  across from the centre, and metres off the ground. Null for the one
   *  shot in twenty the two feeds could not be matched on. */
  gx: number | null; gz: number | null;
};

/** Which corner of the goal, in words — because "top left" is what anyone
 *  actually says, and a coordinate pair is not. */
export function corner(gx: number, gz: number): string {
  const side = gx < -0.9 ? "left" : gx > 0.9 ? "right" : "middle";
  const tier = gz > 1.5 ? "top" : gz > 0.7 ? "mid" : "bottom";
  if (side === "middle") return tier === "mid" ? "straight down the middle"
    : `${tier}, down the middle`;
  return `${tier} ${side}`;
}

export const RESULT_COLOUR: Record<string, string> = {
  Goal: "#22c55e",
  SavedShot: "#eab308",
  ShotOnPost: "#f97316",
  MissedShots: "#94a3b8",
  BlockedShot: "#ef4444",
  OwnGoal: "#a855f7",
};

export const RESULT_LABEL: Record<string, string> = {
  Goal: "goal",
  SavedShot: "saved",
  ShotOnPost: "hit the post",
  MissedShots: "off target",
  BlockedShot: "blocked",
  OwnGoal: "own goal",
};

/** WHICH GOAL THIS SHOT WAS GOING INTO.
 *
 *  Everything used to assume the far one, which is right for an attempt and
 *  wrong for the one case where the ball ended up in the other net. Understat
 *  files an own goal in the CONCEDING side's own shot list, at their own goal
 *  line — Piero Hincapié under Arsenal against Chelsea at x = 0.025 — so the
 *  wedge, the distance and the angle were all measured to a goal 100 metres
 *  from the one the ball crossed.
 */
export const goalEndOf = (shot: Shot): 1 | -1 =>
  shot.result === "OwnGoal" ? -1 : 1;
export const goalZOf = (shot: Shot) => goalEndOf(shot) * GOAL_Z;

/** The angle of goal available from a point, and the distance — the geometry
 *  an xG model is mostly built on, so the panel can state it. */
export function geometry(sx: number, sz: number, gz: number = GOAL_Z) {
  const a1 = Math.atan2(gz - sz, -POST - sx);
  const a2 = Math.atan2(gz - sz, POST - sx);
  let ang = Math.abs(a1 - a2);
  if (ang > Math.PI) ang = Math.PI * 2 - ang;
  return { deg: (ang * 180) / Math.PI, dist: Math.hypot(sx, gz - sz) };
}

/** Where to stand to see what he saw.
 *
 *  OVER HIS SHOULDER, NOT AT HIS EYE. Head height sounds right and is wrong:
 *  from 1.75m the ball itself — which is over a metre across for a big
 *  chance — sits directly between the camera and the goal and hides the
 *  whole route. The view has to clear it.
 *
 *  Both the drop back and the lift scale with how far out he was, because a
 *  tap-in and a thirty-yarder need very different framing: close in, a few
 *  metres back is plenty and the angle is wide; from distance you need to be
 *  much further back to get the goal and the ball in the same shot. */
export function eyeOf(shot: Shot) {
  const sx = shotX(shot.y);
  const sz = shotZ(shot.x);
  const gz = goalZOf(shot);
  const dx = 0 - sx;
  const dz = gz - sz;
  const dist = Math.hypot(dx, dz) || 1;
  const back = Math.max(9, dist * 0.55);
  const lift = Math.max(4.5, dist * 0.30);
  return {
    pos: [sx - (dx / dist) * back, lift, sz - (dz / dist) * back] as
      [number, number, number],
    // aimed a little above the ground so the goal sits in the frame rather
    // than at its very bottom edge
    target: [sx * 0.25, GOAL_H * 0.6, gz - (dz / dist) * dist * 0.12] as
      [number, number, number],
  };
}

/** THE RADIUS THAT CARRIES xG, shared by the ball in the 3D scene and the
 *  disc on the flat map so the two encode the chance identically.
 *
 *  `p` is 1/3 for a sphere whose VOLUME is the quantity and 1/2 for a disc
 *  whose AREA is. Letting radius go as xG directly makes a 0.40 chance
 *  sixteen times the area of a 0.10 one: every tap-in shouts and nothing
 *  else is legible. The floor keeps the smallest attempt clickable. */
export const xgRadius = (xg: number, unit: number, p: number, floor: number) =>
  Math.max(floor, unit * Math.pow(Math.max(xg, 0.001), p));

export { PITCH_L, PITCH_W };
