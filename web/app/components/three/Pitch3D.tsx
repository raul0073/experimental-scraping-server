"use client";

import { useMemo } from "react";
import * as THREE from "three";

import { Arena } from "./Arena";
import { TurfMesh } from "./turf";

/** A football pitch in three dimensions. The STAGE, not the show.
 *
 *  Everything spatial on this site stands on the same ground: formations,
 *  shot maps, heat maps, territory. So the pitch is built once, to real
 *  dimensions, and whatever is being shown is passed in as children. Nothing
 *  else should ever draw its own grass.
 *
 *  THE FIRST ATTEMPT FAILED because it drew a green rectangle with hairlines
 *  on it and called that a pitch. From behind the goal it read as a lawn
 *  with boxes on it and had, in the user's words, zero connection to
 *  football. What makes a pitch legible is not the outline — it is the
 *  MOWING STRIPES, the GOALS, and lines with real width that catch the
 *  light. Those three do more than any amount of geometric accuracy.
 *
 *  Metres throughout, FIFA dimensions. 105 long by 68 wide, goals 7.32 by
 *  2.44, penalty area 40.32 by 16.5, six-yard box 18.32 by 5.5, penalty spot
 *  at 11, centre circle and the D both 9.15, corner arcs 1. Getting these
 *  right costs nothing and means a shot drawn just outside the box really
 *  was just outside the box.
 *
 *  OPTA'S FRAME IS NOT THE SCENE'S. Opta gives x 0 at your own goal line to
 *  100 at theirs, and y 0 at the RIGHT touchline to 100 at the LEFT. The
 *  helpers below are the only place that conversion should ever happen.
 */

export const PITCH_L = 105;   // along the pitch, scene z
export const PITCH_W = 68;    // across the pitch, scene x
const LINE = 0.12;            // real line width
const GOAL_W = 7.32;
const GOAL_H = 2.44;
const PEN_W = 40.32;
const PEN_D = 16.5;
const SIX_W = 18.32;
const SIX_D = 5.5;
const SPOT = 11;
const CIRCLE = 9.15;

/** Opta y (0 = the attacking team's RIGHT touchline) -> scene x.
 *
 *  🐛 THIS WAS MIRRORED, AND IT SURVIVED FOR WEEKS. Every shot map, pass map
 *  and zone column drawn with it had the flanks swapped — Saka on the left
 *  wing, Gabriel at right centre-back — and none of it looked broken,
 *  because a mirrored pitch never does. It took the whole eleven on screen
 *  at once for anyone to see it.
 *
 *  Settled two ways rather than by convention:
 *
 *  WHICH SIDE IS LOW y — from the data, using players whose side is not in
 *  doubt. Opta means for Arsenal 25/26: Saka 18.9, Timber 18.5, Saliba 32.0
 *  against Trossard 77.8, Martinelli 69.6, Magalhães 67.2. Low y is the
 *  attacking team's RIGHT. (Understat agrees: Saka 0.382, Trossard 0.563.)
 *
 *  WHICH WAY THAT IS IN THE SCENE — from the geometry, not from taste. For
 *  any observer `right = forward × up`. A player attacking +z is
 *  (0,0,1) × (0,1,0) = (-1,0,0), so his right hand points at world -x.
 *  Cross-check against three's own lookAt, which puts world +x on screen
 *  right for the canonical camera at +z looking back at the origin: there
 *  forward is (0,0,-1) and (0,0,-1) × (0,1,0) = (1,0,0). Same rule, and it
 *  is the rule three uses.
 *
 *  So the right touchline, y = 0, is world -x. The old form sent it to +34.
 *
 *  `shotX` in ShotCloud was never wrong — Understat's low y is also the
 *  right, and (uy - 0.5) * PITCH_W already sent it to -x. That is exactly
 *  why the shot map looked fine while everything built on toX did not.
 */
export const toX = (optaY: number) => (optaY / 100) * PITCH_W - PITCH_W / 2;
/** Opta x (0 = own goal line) -> scene z, attacking toward +z. */
export const toZ = (optaX: number) => (optaX / 100) * PITCH_L - PITCH_L / 2;

/** Pitched brighter than they look on the page, because the turf texture
 *  multiplies them and an 8-bit map can only ever darken — its mean is about
 *  0.79, so these land roughly where the old flat greens did.
 *
 *  The two bands are also far closer together than they were. Most of the
 *  stripe now comes from the grass being laid the other way, measured at
 *  about 14%; the remaining 3% of colour is only a floor, so the stripes
 *  never vanish entirely at an unlucky sun angle. */
const TURF_A = "#3c9e50";
const TURF_B = "#399a4d";
const RUNOFF = "#2a5638";
const GROUND = "#1a3122";
const PAINT = "#f2f6f3";

/** Where each corner's quarter-circle starts, keyed "ex,ez" for the corner
 *  at (ex * halfWidth, ez * halfLength). A ring lies in its own XY plane and
 *  is then rotated flat, so local +X is world +X but local +Y is world −Z —
 *  and the arc has to bulge INTO the pitch, away from both touchlines. */
const CORNER_FROM: Record<string, number> = {
  "1,1": Math.PI / 2,      // near right: sweeps from −Z round to −X
  "1,-1": Math.PI,         // far right
  "-1,1": 0,               // near left
  "-1,-1": -Math.PI / 2,   // far left
};

/** LINES SIT ON THE GRASS, WHICH IS THE HARDEST THING TO DRAW.
 *
 *  Paint at 1.2cm above the turf broke up into dots and dashes down the far
 *  end — the classic look of a depth buffer running out of precision. With
 *  `near` at 0.1 and `far` at 900 the ratio is 9000:1, and at sixty metres
 *  the smallest distance the buffer can tell apart is larger than the gap
 *  between the paint and the grass, so which one wins is decided per pixel
 *  by rounding.
 *
 *  Three things together, because any one alone leaves a case:
 *    · `near` raised to 0.5 on the camera — five times the precision, free
 *    · this 3cm lift, still far too small to see as a step
 *    · `polygonOffset`, which biases the paint toward the camera in depth
 *      only, the standard way to lay a decal on a surface
 */
const PAINT_Y = 0.03;

function Paint({
  x = 0, z = 0, w, d, rot = 0,
}: { x?: number; z?: number; w: number; d: number; rot?: number }) {
  return (
    <mesh position={[x, PAINT_Y, z]} rotation={[-Math.PI / 2, 0, rot]} receiveShadow>
      <planeGeometry args={[w, d]} />
      <meshStandardMaterial
        color={PAINT}
        roughness={0.82}
        polygonOffset
        polygonOffsetFactor={-2}
        polygonOffsetUnits={-4}
      />
    </mesh>
  );
}

/** An arc of paint: the centre circle, the D, the corner quadrants. */
function Arc({
  x = 0, z = 0, r, from, to,
}: { x?: number; z?: number; r: number; from: number; to: number }) {
  return (
    <mesh position={[x, PAINT_Y, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[r - LINE / 2, r + LINE / 2, 128, 1, from, to - from]} />
      <meshStandardMaterial
        color={PAINT}
        roughness={0.82}
        side={THREE.DoubleSide}
        polygonOffset
        polygonOffsetFactor={-2}
        polygonOffsetUnits={-4}
      />
    </mesh>
  );
}

/** The penalty and centre spots. */
function Spot({ z }: { z: number }) {
  return (
    <mesh position={[0, PAINT_Y + 0.001, z]} rotation={[-Math.PI / 2, 0, 0]}>
      <circleGeometry args={[0.16, 20]} />
      <meshStandardMaterial
        color={PAINT}
        roughness={0.82}
        polygonOffset
        polygonOffsetFactor={-2}
        polygonOffsetUnits={-4}
      />
    </mesh>
  );
}

/** A goal, with a net. The single biggest thing that makes a rectangle of
 *  grass read as a football pitch — without these it is a lawn. */
function Goal({ end }: { end: 1 | -1 }) {
  const z = (end * PITCH_L) / 2;
  const post = 0.12;
  const depth = 1.8;
  // A wireframe plane reads as graph paper, not netting — the squares are
  // far too coarse and the lines too even. A fine grid at low opacity, with
  // the geometry subdivided enough that the mesh is dense, is what makes it
  // catch light the way a net does.
  const net = useMemo(
    () => new THREE.MeshStandardMaterial({
      color: "#dfe9ee", transparent: true, opacity: 0.16,
      roughness: 1, side: THREE.DoubleSide, wireframe: true,
      depthWrite: false,
    }),
    [],
  );
  return (
    <group position={[0, 0, z]}>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[(s * GOAL_W) / 2, GOAL_H / 2, 0]} castShadow>
          <cylinderGeometry args={[post, post, GOAL_H, 12]} />
          <meshStandardMaterial color="#ffffff" roughness={0.5} />
        </mesh>
      ))}
      <mesh position={[0, GOAL_H, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[post, post, GOAL_W + post * 2, 12]} />
        <meshStandardMaterial color="#ffffff" roughness={0.5} />
      </mesh>
      {/* the net: back, roof and two sides, as a light wireframe */}
      <mesh position={[0, GOAL_H / 2, (end * depth)]}>
        <planeGeometry args={[GOAL_W, GOAL_H, 30, 12]} />
        <primitive object={net} attach="material" />
      </mesh>
      <mesh
        position={[0, GOAL_H, (end * depth) / 2]}
        rotation={[Math.PI / 2, 0, 0]}
      >
        <planeGeometry args={[GOAL_W, depth, 30, 7]} />
        <primitive object={net} attach="material" />
      </mesh>
      {[-1, 1].map((s) => (
        <mesh
          key={s}
          position={[(s * GOAL_W) / 2, GOAL_H / 2, (end * depth) / 2]}
          rotation={[0, Math.PI / 2, 0]}
        >
          <planeGeometry args={[depth, GOAL_H, 7, 12]} />
          <primitive object={net} attach="material" />
        </mesh>
      ))}
    </group>
  );
}

/** One end's markings — penalty area, six-yard box, spot and the D. */
function End({ end }: { end: 1 | -1 }) {
  const gl = (end * PITCH_L) / 2;                 // goal line
  const penEdge = gl - end * PEN_D;
  const sixEdge = gl - end * SIX_D;
  const spotZ = gl - end * SPOT;
  // THE D: only the part of the 9.15m circle around the penalty spot that
  // sits OUTSIDE the penalty area. The edge of the box is 16.5 - 11 = 5.5m
  // from the spot, so the arc runs acos(5.5 / 9.15) = 53 degrees either side
  // of straight-ahead — a 106 degree sweep.
  //
  // This was `Math.min(1, PEN_D - SPOT) / CIRCLE`, which clamps 5.5 to 1 and
  // gives acos(1/9.15) = 84 degrees either side. A 167 degree sweep wraps
  // most of the way round the spot, so the D was drawn curling back INSIDE
  // the penalty area — which is the one place it never goes.
  const half = Math.acos(Math.min(1, (PEN_D - SPOT) / CIRCLE));
  const base = end === 1 ? Math.PI / 2 : -Math.PI / 2;
  return (
    <group>
      <Paint z={penEdge} w={PEN_W} d={LINE} />
      <Paint x={-PEN_W / 2} z={gl - (end * PEN_D) / 2} w={LINE} d={PEN_D} />
      <Paint x={PEN_W / 2} z={gl - (end * PEN_D) / 2} w={LINE} d={PEN_D} />
      <Paint z={sixEdge} w={SIX_W} d={LINE} />
      <Paint x={-SIX_W / 2} z={gl - (end * SIX_D) / 2} w={LINE} d={SIX_D} />
      <Paint x={SIX_W / 2} z={gl - (end * SIX_D) / 2} w={LINE} d={SIX_D} />
      <Spot z={spotZ} />
      <Arc z={spotZ} r={CIRCLE} from={base - half} to={base + half} />
    </group>
  );
}

export function Pitch3D({
  portion = 1,
  goals = true,
  arena = true,
  children,
}: {
  /** How much of the pitch to draw, measured back from the ATTACKING goal
   *  line. 1 is all of it; 0.75 is what a shot map wants.
   *
   *  It was a half at first, on the reasoning that almost nothing happens in
   *  the other one and drawing it wastes the picture. True of the average,
   *  false at the edges: shots from just inside the own half are rare but
   *  they are exactly the ones worth looking at, and they were being drawn
   *  past the end of the grass. Three quarters covers every genuine attempt
   *  in the data and still gives the box most of the frame.
   *
   *  (The handful that fall outside even that are all recorded as OwnGoal.
   *  Understat puts an own goal at the SCORING side's own goal line, so they
   *  sit at the wrong end by construction and no amount of pitch would
   *  place them sensibly.) */
  portion?: number;
  goals?: boolean;
  /** the ground around the grass — hoardings, flags, dugouts, floodlights.
   *  On by default: without something of known height in the picture the
   *  whole scene flattens and could be a model on a table. See Arena.tsx. */
  arena?: boolean;
  children?: React.ReactNode;
}) {
  const length = PITCH_L * portion;
  const zFrom = PITCH_L / 2 - length;
  const midZ = zFrom + length / 2;

  /** Whether the reader's own end is in shot at all. Everything down there —
   *  the goal line, the penalty area, the goal, the two corner arcs and
   *  their flags — is drawn as a set or not at all, because half a penalty
   *  area running off the edge of the grass looks like a mistake. */
  const ownEnd = portion > 0.999;
  /** The centre circle is 9.15m either side of halfway, so it survives whole
   *  as soon as the drawn region reaches that far back. */
  const wholeCircle = zFrom <= -CIRCLE;

  /** Mowing stripes. The detail that does the most work: a plain green
   *  rectangle reads as a lawn, and eight alternating bands read as a pitch
   *  before a single line is drawn.
   *
   *  The count follows the LENGTH DRAWN rather than being fixed, so a band
   *  stays about 10.5m whatever portion is on screen — otherwise stripes
   *  would be a different width on the shot map than on the team page, and
   *  the two pictures would not look like the same ground. */
  const bands = useMemo(() => {
    const n = Math.max(1, Math.round(length / (PITCH_L / 10)));
    const w = length / n;
    return Array.from({ length: n }, (_, i) => ({
      z: zFrom + w / 2 + i * w,
      w,
      colour: i % 2 === 0 ? TURF_A : TURF_B,
      // the grass itself laid the other way, which is the whole mechanism
      flip: i % 2 === 1,
    }));
  }, [length, zFrom]);

  return (
    <group>
      {/* THE SURROUND, AND WHY IT IS BIG. A tight dark rectangle round the
          grass drew a hard black frame a few metres out — the pitch looked
          cut out and pasted onto a void, which was most of what made the
          scene feel wrong. Running it far past the camera's reach and
          keeping it close to the turf in tone removes the edge entirely:
          there is no line to notice, the grass simply gives way to darker
          ground and then to the sky behind. */}
      <TurfMesh
        y={-0.05}
        z={midZ}
        w={PITCH_W + 260}
        d={length + 260}
        colour={GROUND}
        // a coarser tile out here: the pitch's own pattern stretched across
        // 300 metres would repeat thirty times and the grid would be the
        // first thing anyone saw
        tile={22}
        // this plane runs far outside the shadow camera, where the lookup
        // clamps to the border texel and draws long dark streaks
        shadow={false}
      />
      {/* a band of darker turf just off the pitch, the way a real ground has
          run-off before the stands start */}
      <TurfMesh
        y={-0.02}
        z={midZ}
        w={PITCH_W + 26}
        d={length + 26}
        colour={RUNOFF}
        tile={11}
      />

      {bands.map((b, i) => (
        <TurfMesh
          key={i}
          z={b.z}
          w={PITCH_W}
          d={b.w}
          colour={b.colour}
          flip={b.flip}
        />
      ))}

      {/* touchlines and goal lines */}
      <Paint x={-PITCH_W / 2} z={midZ} w={LINE} d={length} />
      <Paint x={PITCH_W / 2} z={midZ} w={LINE} d={length} />
      <Paint z={PITCH_L / 2} w={PITCH_W} d={LINE} />
      {ownEnd && <Paint z={-PITCH_L / 2} w={PITCH_W} d={LINE} />}

      {/* halfway line and centre circle */}
      <Paint z={0} w={PITCH_W} d={LINE} />
      {wholeCircle ? (
        <>
          <Arc r={CIRCLE} from={0} to={Math.PI * 2} />
          <Spot z={0} />
        </>
      ) : (
        // THE HALF THAT SURVIVES IS THE +Z ONE, and the ring's angles do not
        // say so: it is built in its own XY plane and laid flat, which maps
        // local +Y to world −Z. So 0 → π is the half BEHIND halfway, which
        // is the half that is not there. −π → 0 is the one on the grass.
        <Arc r={CIRCLE} from={-Math.PI} to={0} />
      )}

      <End end={1} />
      {ownEnd && <End end={-1} />}

      {/* Corner arcs. A LOOKUP, not a formula: the ring is drawn in its own
          XY plane and then laid flat, so local +Y becomes world -Z and the
          mapping from "which corner" to "which quarter of the circle" has
          a sign flip in it that is easy to write and impossible to read. A
          nested ternary got two of the four wrong. */}
      {(ownEnd ? [1, -1] : [1]).map((ez) =>
        [1, -1].map((ex) => {
          const from = CORNER_FROM[`${ex},${ez}`];
          return (
            <Arc
              key={`${ez}${ex}`}
              x={(ex * PITCH_W) / 2}
              z={(ez * PITCH_L) / 2}
              r={1}
              from={from}
              to={from + Math.PI / 2}
            />
          );
        }),
      )}

      {goals && <Goal end={1} />}
      {goals && ownEnd && <Goal end={-1} />}

      {arena && (
        <Arena width={PITCH_W} zFrom={zFrom} length={length} ownEnd={ownEnd} />
      )}

      {children}
    </group>
  );
}

/** The lighting a pitch wants: a low sun, a soft sky, and enough fill that
 *  nothing on the far side goes black. Shared so every scene matches. */
export function PitchLights() {
  return (
    <>
      <hemisphereLight args={["#b9d7ff", "#20361f", 0.8]} />
      <directionalLight
        position={[38, 70, 30]}
        intensity={2.0}
        castShadow
        // A 4k map over a 140m frustum is about 3.5cm per texel. At 2k it
        // was 7cm and every shadow edge on the pitch was visibly stepped.
        shadow-mapSize={[4096, 4096]}
        shadow-camera-left={-80}
        shadow-camera-right={80}
        shadow-camera-top={80}
        shadow-camera-bottom={-80}
        shadow-camera-far={240}
        shadow-bias={-0.0006}
        shadow-normalBias={0.02}
      />
      <directionalLight position={[-40, 30, -30]} intensity={0.35} />
    </>
  );
}
