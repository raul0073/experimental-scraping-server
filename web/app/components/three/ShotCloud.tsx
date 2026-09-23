"use client";

import { Billboard, Html } from "@react-three/drei";
import { type ThreeEvent } from "@react-three/fiber";
import { useMemo, useState } from "react";
import * as THREE from "three";

import { PITCH_L, PITCH_W } from "./Pitch3D";

/** Shots on a pitch, and what the shooter could actually see.
 *
 *  A flat shot map is a scatter plot — position and outcome, with xG
 *  smuggled in as a dot size nobody can compare by eye. What it cannot show
 *  is the GEOMETRY, which is most of what xG is: how wide the goal was from
 *  where he stood, and how far away.
 *
 *  BALLS, NOT DISCS. The first version drew flat circles lying on the grass,
 *  which from any angle except straight down are ellipses on a green plane —
 *  a 2D chart that happens to be rendered by a 3D engine, with none of the
 *  depth that was the entire reason to be here. A sphere sitting on the turf
 *  reads as an object in space from every angle, casts a shadow, and grows
 *  toward the camera as you approach it.
 *
 *  AREA, NOT RADIUS, carries xG — so the ball's radius goes as the cube root
 *  of xG rather than xG itself. A 0.40 chance that was sixteen times the
 *  size of a 0.10 one would make every tap-in shout and nothing else legible.
 *
 *  Understat's frame: x and y both 0-1 over 105 by 68, x = 1 at the goal
 *  being attacked. Penalties sit at exactly (0.885, 0.500), which confirms
 *  both axes; which touchline y = 0 means is not settled by the data.
 */

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
 *
 *  Making the target a property of the shot rather than a constant is also
 *  what a shots-faced panel beside a shots-taken one will need, since faced
 *  shots are attempts on the goal at the other end.
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

/** Geometry with a per-vertex RGBA, which is what lets the wedge FADE.
 *
 *  A single flat opacity cannot work here, because the wedge is a solid seen
 *  from inside: at the shooter all three surfaces meet, so whatever value
 *  looks right across the middle stacks into a slab of neat colour at the
 *  apex — and the apex is exactly where the camera sits on a click. Grading
 *  the alpha along the shot fixes the density where it is worst and reads as
 *  a beam thrown at the goal rather than a coloured region.
 *
 *  Alpha per vertex needs a FOUR-component colour attribute; three switches
 *  on `USE_COLOR_ALPHA` from the attribute's itemSize, so a three-component
 *  one silently gives a uniform wedge back.
 */
function shaded(verts: number[], alphas: number[], colour: THREE.Color) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
  const c = new Float32Array(alphas.length * 4);
  alphas.forEach((a, i) => {
    c[i * 4] = colour.r;
    c[i * 4 + 1] = colour.g;
    c[i * 4 + 2] = colour.b;
    c[i * 4 + 3] = a;
  });
  g.setAttribute("color", new THREE.Float32BufferAttribute(c, 4));
  return g;
}

const APEX = 0.04;    // at the ball, where every surface overlaps
const MOUTH = 0.22;   // at the goal line, where it is a single sheet

function Wedge({ shot }: { shot: Shot }) {
  const sx = shotX(shot.y);
  const sz = shotZ(shot.x);
  const gz = goalZOf(shot);
  const end = goalEndOf(shot);
  const colour = RESULT_COLOUR[shot.result] ?? "#ffd23f";
  const rgb = useMemo(() => new THREE.Color(colour), [colour]);

  /** Sideways from the shot, in the ground plane. The angle text hugs the
   *  ball on one side of the line, so the distance goes to the other. */
  const perp = useMemo<[number, number]>(() => {
    const dx = 0 - sx;
    const dz = gz - sz;
    const L = Math.hypot(dx, dz) || 1;
    return [dz / L, -dx / L];
  }, [sx, sz, gz]);

  const floor = useMemo(
    () => shaded(
      [sx, 0.07, sz, -POST, 0.07, gz, POST, 0.07, gz],
      [APEX, MOUTH, MOUTH],
      rgb,
    ),
    [sx, sz, gz, rgb],
  );

  /** The two vertical sheets from the shooter to each post, which is what
   *  turns a flat wedge into something you can stand inside. */
  const walls = useMemo(() => {
    const make = (px: number) =>
      shaded(
        [
          sx, 0, sz, px, 0, gz, px, GOAL_H, gz,
          sx, 0, sz, px, GOAL_H, gz, sx, 1.75, sz,
        ],
        [APEX, MOUTH * 0.65, MOUTH * 0.65, APEX, MOUTH * 0.65, APEX],
        rgb,
      );
    return [make(-POST), make(POST)];
  }, [sx, sz, gz, rgb]);

  return (
    <group>
      <mesh geometry={floor}>
        <meshBasicMaterial vertexColors transparent
                           side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      {walls.map((g, i) => (
        <mesh key={i} geometry={g}>
          <meshBasicMaterial vertexColors transparent
                             side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      ))}
      {/* the mouth he was aiming at, lit between the posts */}
      <mesh position={[0, GOAL_H / 2, gz]}>
        <planeGeometry args={[GOAL_W, GOAL_H]} />
        <meshBasicMaterial color={colour} transparent opacity={0.26}
                           side={THREE.DoubleSide} depthWrite={false} />
      </mesh>

      {/* WHERE IT ACTUALLY CROSSED THE LINE. WhoScored records the goal-mouth
          point on every shot and Understat records the xG on every shot, and
          neither has the other's — so this is joined on surname and minute
          inside the fixture, which lands 95% of them. A ball sitting in the
          top corner of a real net is the single thing that makes a 3D goal
          worth drawing at all. */}
      {shot.gx !== null && shot.gz !== null && (
        // `gx` is metres across the goal's own mouth, measured in the frame
        // of the goal being attacked — so at the other end it mirrors, the
        // same flip that catches every two-team drawing on one pitch.
        <group position={[end * shot.gx, shot.gz, gz + end * 0.35]}>
          <mesh castShadow>
            <sphereGeometry args={[0.36, 20, 14]} />
            <meshStandardMaterial
              color="#ffffff"
              emissive={colour}
              emissiveIntensity={0.55}
              roughness={0.3}
            />
          </mesh>
          {/* THIS ONE STAYS A BILLBOARD. Everything on the grass is painted
              flat because it is a diagram drawn on the ground, but the spot
              in the goal is a point in the AIR — a ring fixed to the goal
              plane goes edge-on and vanishes the moment the camera moves off
              the centre line, which is most of the time. Turning to face the
              viewer is the only way a marker at head height stays a marker. */}
          <Billboard>
            <mesh>
              <ringGeometry args={[0.52, 0.7, 28]} />
              <meshBasicMaterial color={colour} transparent opacity={0.95}
                                 side={THREE.DoubleSide} depthTest={false} />
            </mesh>
          </Billboard>
        </group>
      )}
      {/* the strike point */}
      <mesh position={[sx, 0.12, sz]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.9, 1.15, 32]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.9}
                           side={THREE.DoubleSide} />
      </mesh>

      {/* THE ANGLE, MARKED THE WAY AN ANGLE IS MARKED — a small arc struck
          across the corner it belongs to, with the degrees beside it. It was
          a floating number next to the ball, which is a caption, not a
          measurement of anything. */}
      <AngleArc sx={sx} sz={sz} gz={gz} />

      {/* The distance, facing the reader, halfway down the line it measures —
          and pushed SIDEWAYS off that line.

          Dead centre it sat on the shot's own axis, which is also where the
          ball's name chip hangs and where the reader stands in both default
          cameras. All three then project onto the same column of screen and
          the distance ends up behind the name. Same overlap the angle text
          had; same cure, which is to stop putting things on the line the
          reader is looking down. */}
      <Html
        center
        position={[sx * 0.5 + perp[0] * 5, 1.3, sz + (gz - sz) * 0.5 + perp[1] * 5]}
        distanceFactor={26}
        zIndexRange={[30, 0]}
      >
        <div className="num select-none whitespace-nowrap text-[15px] font-bold text-white"
             style={{ textShadow: "0 2px 6px #000, 0 0 4px #000" }}>
          {geometry(sx, sz, gz).dist.toFixed(1)} m
        </div>
      </Html>

      {/* What became of it, over the bar — and big, because it is the answer
          to the question the whole picture is asking. */}
      <Html
        center
        position={[0, GOAL_H + 2.4, gz]}
        distanceFactor={42}
        zIndexRange={[30, 0]}
      >
        <span
          className="select-none whitespace-nowrap rounded-md px-2.5 py-1 text-[15px] font-bold uppercase tracking-wide text-white"
          style={{ background: colour, boxShadow: "0 2px 10px rgba(0,0,0,.7)" }}
        >
          {RESULT_LABEL[shot.result] ?? shot.result}
        </span>
      </Html>
    </group>
  );
}

/** The arc across the corner between the two sight lines, plus the degrees.
 *
 *  A ring is built in its own XY plane and then laid flat, so a world
 *  direction (dx, dz) is a local angle of atan2(-dz, dx) — the same sign
 *  flip that got the corner arcs wrong twice. */
function AngleArc({ sx, sz, gz }: { sx: number; sz: number; gz: number }) {
  const { deg } = geometry(sx, sz, gz);
  const dz = gz - sz;
  const a1 = Math.atan2(-dz, -POST - sx);
  const a2 = Math.atan2(-dz, POST - sx);
  const from = Math.min(a1, a2);
  const span = Math.abs(a1 - a2);
  const quarter = from + span * 0.25;
  const r = 3.2;
  return (
    <group>
      <mesh position={[sx, 0.14, sz]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[r - 0.09, r + 0.09, 64, 1, from, span]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.95}
                           side={THREE.DoubleSide} />
      </mesh>
      {/* The degrees sit beside the arc a QUARTER of the way round, not at
          its midpoint. The midpoint points straight at the goal — which from
          behind the shooter is exactly where the ball's own name label
          hangs, so the two printed over each other. */}
      <Html
        center
        position={[sx + Math.cos(quarter) * (r + 1.3), 0.9,
                   sz - Math.sin(quarter) * (r + 1.3)]}
        distanceFactor={19}
        zIndexRange={[30, 0]}
      >
        <div className="num select-none whitespace-nowrap text-[14px] font-bold text-white"
             style={{ textShadow: "0 2px 6px #000, 0 0 4px #000" }}>
          {deg.toFixed(0)}°
        </div>
      </Html>
    </group>
  );
}

function Ball({
  shot, i, selected, onSelect,
}: {
  shot: Shot; i: number; selected: boolean;
  onSelect: (i: number) => void;
}) {
  const [hot, setHot] = useState(false);
  const sx = shotX(shot.y);
  const sz = shotZ(shot.x);
  // area, not radius: the cube root keeps a 0.40 chance about one and a half
  // times the ball of a 0.10 one rather than four times
  const r = 0.34 + 1.05 * Math.cbrt(Math.min(shot.xg, 0.9));
  const colour = RESULT_COLOUR[shot.result] ?? "#94a3b8";

  return (
    <group position={[sx, r, sz]}>
      <mesh
        castShadow
        scale={hot || selected ? 1.35 : 1}
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHot(true);
        }}
        onPointerOut={() => setHot(false)}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          onSelect(selected ? -1 : i);
        }}
      >
        <sphereGeometry args={[r, 22, 16]} />
        <meshStandardMaterial
          color={colour}
          roughness={0.35}
          metalness={0.05}
          emissive={colour}
          emissiveIntensity={hot || selected ? 0.5 : 0.12}
        />
      </mesh>
      {/* Name and xG above the ball, and NOTHING ELSE here.
          `distanceFactor` scales an HTML label UP as the camera closes in,
          so it has to be judged at the CLOSEST seat rather than whichever
          one is on screen: the nearest this scene ever gets is the shooter's
          eye, nine metres back. At 44 the name filled a third of the frame
          from there and buried the goal behind it. */}
      {/* A CHIP, NOT SHADOWED TEXT. White type with a black shadow works over
          grass and fails over the wedge: the wedge is painted in the outcome
          colour, the name hangs directly in front of it, and a soft dark
          shadow on a saturated field is no contrast at all — the name came
          out as dark smudge on red. A solid dark plate with the outcome
          colour as its edge reads over anything, and the edge says which
          shot the label belongs to. */}
      {(hot || selected) && (
        <Html center position={[0, r + 3.1, 0]} distanceFactor={16}
              zIndexRange={[30, 0]}>
          <div
            className="select-none whitespace-nowrap rounded-md px-2 py-1 text-center leading-tight"
            style={{
              background: "rgba(7,17,25,0.88)",
              borderBottom: `2px solid ${colour}`,
              boxShadow: "0 2px 10px rgba(0,0,0,.6)",
            }}
          >
            <div className="text-[11px] font-semibold tracking-wide text-white">
              {shot.player}
            </div>
            <div className="num text-[12px] font-bold" style={{ color: colour }}>
              {shot.xg.toFixed(2)} xG
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

export function ShotCloud({
  shots, selected, onSelect,
}: {
  shots: Shot[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  const sel = shots[selected];
  // ONE SHOT AT A TIME, and the rest genuinely GONE. Fading them to 12% left
  // five hundred balls still lit, still glowing, still catching the eye and
  // still swallowing clicks — the wedge was buried in exactly the clutter
  // that choosing a shot was meant to clear.
  const visible = sel ? [{ s: sel, i: selected }]
                      : shots.map((s, i) => ({ s, i }));
  return (
    <group>
      {visible.map(({ s, i }) => (
        <Ball
          key={i}
          shot={s}
          i={i}
          selected={selected === i}
          onSelect={onSelect}
        />
      ))}
      {sel && <Wedge shot={sel} />}
    </group>
  );
}
