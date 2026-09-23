"use client";

import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

/** THE GROUND AROUND THE PITCH — everything that is not the playing surface.
 *
 *  WHY THIS EXISTS. A correctly drawn pitch on an empty plane still reads as
 *  a diagram, because nothing in the picture has a known height. The goal is
 *  2.44m tall but the eye has nothing to check that against, so the scene
 *  flattens: it could be a model on a table or a real ground from a
 *  helicopter and there is no way to tell. Every object here exists to give
 *  the eye something it already knows the size of.
 *
 *    corner flag   1.5m  — the smallest, sets the near scale
 *    hoardings     1.0m  — a continuous horizon line at a fixed distance,
 *                          which is what actually conveys depth: parallel
 *                          lines converging is the strongest cue there is
 *    dugout        2.1m  — human scale, and the one thing in a stadium
 *                          picture that is obviously built for people
 *    floodlight    22m   — nine goals tall, and it settles the question of
 *                          whether you are looking at something big
 *
 *  It is also what makes the thing feel inhabited rather than plotted, which
 *  is the whole point of moving off a flat chart.
 *
 *  DIMENSIONS ARE REAL, same as the pitch itself. Hoardings sit 5.5m off the
 *  line, which is roughly what a ground with a running lane has; dugouts
 *  straddle the halfway line where they belong rather than wherever looked
 *  balanced.
 *
 *  Everything is positioned against the DRAWN region, not the full pitch, so
 *  a part-pitch view gets a coherent little arena closed off behind the play
 *  instead of furniture floating past the edge of the grass.
 */

const BOARD_H = 1.0;
const BOARD_OFF = 5.5;      // hoarding line, from touchline and goal line
const BOARD_TILT = 0.13;    // they lean back, and the lean catches the light
const PANEL_M = 9;          // metres of board per repeat of the ad canvas

const PYLON_H = 22;
const PYLON_OUT = 20;       // beyond the corner, in both x and z

const FLAG_H = 1.5;

/** Shared singletons. Thirty-two lamp boxes do not need thirty-two materials,
 *  and a material per pylon is a material to keep in sync. */
const STEEL = new THREE.MeshStandardMaterial({
  color: "#2c3c47", roughness: 0.55, metalness: 0.45,
});
const CONCRETE = new THREE.MeshStandardMaterial({
  color: "#4e565c", roughness: 0.95,
});
/** `toneMapped: false` is what makes a lamp look switched on. Without it the
 *  renderer's tone curve pulls the brightest white back to the same value as
 *  the painted lines, and the bank reads as eight grey rectangles. */
const LAMP = new THREE.MeshStandardMaterial({
  color: "#fff7e2", emissive: "#ffeec2", emissiveIntensity: 1.5,
  roughness: 0.3, toneMapped: false,
});
const GLOW = new THREE.MeshBasicMaterial({
  color: "#ffeec9", transparent: true, opacity: 0.15,
  blending: THREE.AdditiveBlending, depthWrite: false,
  toneMapped: false, side: THREE.DoubleSide,
});

/* ------------------------------------------------------------------ boards */

/** The advertising canvas, drawn once and shared by all four runs.
 *
 *  Drawn rather than loaded: a 2D canvas needs no network fetch, so it cannot
 *  suspend and cannot take the scene down with it the way a font or an image
 *  can. The text is ours — a ground ringed with other people's brands would
 *  be a different kind of claim entirely.
 */
let AD_CANVAS: HTMLCanvasElement | null | undefined;

function adCanvas(): HTMLCanvasElement | null {
  if (AD_CANVAS !== undefined) return AD_CANVAS;
  if (typeof document === "undefined") return null;   // never cache the SSR miss

  const PW = 512;
  const PH = 128;
  const panels = [
    { bg: "#0c1f2e", fg: "#8ec8ee", text: "PREDICTOROUS", weight: 700 },
    { bg: "#143349", fg: "#dceaf4", text: "experiMental", weight: 600 },
    { bg: "#1c5b8a", fg: "#eef6fc", text: "PROBABILITIES · NOT TIPS", weight: 600 },
  ];

  const c = document.createElement("canvas");
  c.width = PW * panels.length;
  c.height = PH;
  const g = c.getContext("2d");
  if (!g) return null;

  const face = '"Segoe UI", system-ui, -apple-system, sans-serif';
  panels.forEach((p, i) => {
    const x0 = i * PW;
    g.fillStyle = p.bg;
    g.fillRect(x0, 0, PW, PH);
    g.fillStyle = "rgba(255,255,255,0.16)";      // top rail, catches the sun
    g.fillRect(x0, 0, PW, 7);
    g.fillStyle = "rgba(0,0,0,0.45)";            // seam to the next panel
    g.fillRect(x0, 0, 5, PH);

    // shrink to fit rather than trusting one size for every string
    let size = 48;
    g.font = `${p.weight} ${size}px ${face}`;
    while (g.measureText(p.text).width > PW - 70 && size > 14) {
      size -= 2;
      g.font = `${p.weight} ${size}px ${face}`;
    }
    g.fillStyle = p.fg;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(p.text, x0 + PW / 2, PH / 2 + 4);
  });

  AD_CANVAS = c;
  return c;
}

/** One straight run of hoardings. `rotY` turns the lettered face toward the
 *  pitch; the box gives it real thickness so it still reads as an object
 *  when the camera swings behind it. */
function BoardRun({
  len, x, z, rotY, aniso,
}: { len: number; x: number; z: number; rotY: number; aniso: number }) {
  const tex = useMemo(() => {
    const c = adCanvas();
    if (!c) return null;
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.wrapS = THREE.RepeatWrapping;
    t.repeat.set(Math.max(1, Math.round(len / PANEL_M)), 1);
    // ANISOTROPY MATTERS MORE HERE THAN ANYWHERE. A board run is seen almost
    // edge-on from every camera on this site, which is the exact case
    // trilinear filtering handles worst — without it the far half of the run
    // turns to grey mush by about thirty metres.
    t.anisotropy = aniso;
    return t;
  }, [len, aniso]);

  const mats = useMemo(() => {
    const back = new THREE.MeshStandardMaterial({ color: "#0a1620", roughness: 0.9 });
    const rail = new THREE.MeshStandardMaterial({ color: "#223d4f", roughness: 0.55 });
    const ad = new THREE.MeshStandardMaterial({
      map: tex, color: tex ? "#ffffff" : "#12293a", roughness: 0.5,
    });
    // box face order: +x, −x, +y, −y, +z, −z — the ad is the +z face
    return [back, back, rail, back, ad, back];
  }, [tex]);

  useEffect(
    () => () => {
      tex?.dispose();
      mats.forEach((m) => m.dispose());
    },
    [tex, mats],
  );

  // Yaw on the group, lean on the mesh. Combining them into one Euler means
  // depending on which order three applies today, and a board that leans
  // sideways is a hard thing to debug from a screenshot.
  return (
    <group position={[x, 0, z]} rotation={[0, rotY, 0]}>
      {/* No cast shadow. A metre-tall board throws a metre-long shadow that
          lands nowhere useful and reads as a thin dark line running the whole
          length of the ground — it cost more than it bought. */}
      <mesh
        position={[0, BOARD_H / 2, 0]}
        rotation={[-BOARD_TILT, 0, 0]}
        material={mats}
        receiveShadow
      >
        <boxGeometry args={[len, BOARD_H, 0.16]} />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------- flags */

/** A corner flag, and it moves. Everything else in the scene is still; one
 *  thing with a slow idle is the difference between a render and a place.
 *  Kept in `useFrame` on a ref — a `setState` here would re-render the React
 *  tree sixty times a second to turn a 45cm rectangle. */
function CornerFlag({ x, z, face, phase }: {
  x: number; z: number; face: number; phase: number;
}) {
  const wave = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (!wave.current) return;
    wave.current.rotation.y = Math.sin(t * 1.5 + phase) * 0.18;
    wave.current.rotation.z = Math.sin(t * 2.4 + phase) * 0.06;
  });

  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, FLAG_H / 2, 0]} castShadow>
        <cylinderGeometry args={[0.035, 0.035, FLAG_H, 8]} />
        <meshStandardMaterial color="#f3f6f4" roughness={0.6} />
      </mesh>
      <group position={[0, FLAG_H - 0.18, 0]} rotation={[0, face, 0]}>
        <group ref={wave}>
          <mesh position={[0.23, 0, 0]} castShadow>
            <planeGeometry args={[0.46, 0.32]} />
            <meshStandardMaterial
              color="#efb42a"
              emissive="#c47d06"
              emissiveIntensity={0.25}
              roughness={0.8}
              side={THREE.DoubleSide}
            />
          </mesh>
        </group>
      </group>
    </group>
  );
}

/* ----------------------------------------------------------------- dugouts */

/** A strip of chalk on the run-off, for the technical area. Lower than the
 *  pitch markings because the run-off itself sits below the turf. */
function Chalk({ x, z, w, d }: { x: number; z: number; w: number; d: number }) {
  return (
    <mesh position={[x, 0.01, z]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[w, d]} />
      {/* same decal problem as the pitch markings — see Pitch3D's PAINT_Y */}
      <meshStandardMaterial
        color="#cfe0d6"
        roughness={0.95}
        polygonOffset
        polygonOffsetFactor={-2}
        polygonOffsetUnits={-4}
      />
    </mesh>
  );
}

/** A dugout, open toward the pitch.
 *
 *  The shell is a single box with `side: BackSide`, which renders only the
 *  faces pointing away from the camera — so from the pitch you look straight
 *  through the near wall and see the inside of the far one. One mesh, a
 *  genuine open front, and no seams to line up. The roof is a separate slab
 *  on top because BackSide would cull it from above and leave the thing
 *  looking like an open crate from the overhead camera.
 */
function Dugout({ x, z }: { x: number; z: number }) {
  const L = 6.4;   // along the touchline
  const D = 2.4;   // back to front
  const H = 2.0;
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, H / 2, 0]}>
        <boxGeometry args={[D, H, L]} />
        <meshStandardMaterial color="#1a2b36" roughness={0.85} side={THREE.BackSide} />
      </mesh>
      <mesh position={[0, H + 0.06, 0]} castShadow>
        <boxGeometry args={[D + 0.5, 0.12, L + 0.4]} />
        <meshStandardMaterial color="#26404f" roughness={0.6} metalness={0.2} />
      </mesh>
      {/* bench: a slab and a back, enough to read as seating at this size */}
      <mesh position={[0.15, 0.48, 0]}>
        <boxGeometry args={[0.9, 0.1, L - 0.7]} />
        <meshStandardMaterial color="#c9d6dd" roughness={0.7} />
      </mesh>
      <mesh position={[-0.35, 0.78, 0]}>
        <boxGeometry args={[0.1, 0.55, L - 0.7]} />
        <meshStandardMaterial color="#9fb2bd" roughness={0.7} />
      </mesh>
    </group>
  );
}

/* --------------------------------------------------------------- pylons */

/** A floodlight. `aim` is the yaw that points the lamp bank at the middle of
 *  whatever is being drawn; the downward tilt is a separate nested rotation
 *  because Euler order on a single group makes "yaw then tilt" ambiguous and
 *  it is not worth working out which convention three is using today. */
function Pylon({ x, z, aim }: { x: number; z: number; aim: number }) {
  const lamps = useMemo(() => {
    const out: [number, number][] = [];
    for (let r = 0; r < 2; r++) {
      for (let c = 0; c < 4; c++) out.push([(c - 1.5) * 1.32, (0.5 - r) * 0.98]);
    }
    return out;
  }, []);

  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.25, 0]} material={CONCRETE}>
        <boxGeometry args={[1.9, 0.5, 1.9]} />
      </mesh>
      {/* tapered: a parallel-sided pole this tall reads as a pipe */}
      <mesh position={[0, PYLON_H / 2, 0]} material={STEEL}>
        <cylinderGeometry args={[0.3, 0.72, PYLON_H, 10]} />
      </mesh>
      <group position={[0, PYLON_H, 0]} rotation={[0, aim, 0]}>
        <group rotation={[0.46, 0, 0]}>
          <mesh material={STEEL}>
            <boxGeometry args={[5.8, 2.4, 0.4]} />
          </mesh>
          {lamps.map(([lx, ly], i) => (
            <mesh key={i} position={[lx, ly, 0.24]} material={LAMP}>
              <boxGeometry args={[1.18, 0.86, 0.1]} />
            </mesh>
          ))}
          <mesh position={[0, 0, 0.42]} material={GLOW}>
            <planeGeometry args={[7.2, 3.4]} />
          </mesh>
        </group>
        {/* the truss that hangs the bank off the pole */}
        <mesh position={[0, -1.5, 0.3]} material={STEEL}>
          <boxGeometry args={[3.6, 0.2, 0.9]} />
        </mesh>
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------- arena */

export function Arena({
  width, zFrom, length, ownEnd,
}: {
  width: number; zFrom: number; length: number;
  /** whether the reader's own goal line is on screen — if it is not, the
   *  near edge of the grass is a cut, not a corner */
  ownEnd: boolean;
}) {
  // `getMaxAnisotropy` is a renderer capability, so it can only be read from
  // inside the Canvas — which is the whole reason this is a component and
  // not a set of constants.
  const aniso = useThree((s) => s.gl.capabilities.getMaxAnisotropy());

  const hx = width / 2;
  const zEnd = zFrom + length;
  const midZ = zFrom + length / 2;
  const sideLen = length + BOARD_OFF * 2;

  const bx = hx + BOARD_OFF;
  const px = hx + PYLON_OUT;
  const pzFar = zEnd + PYLON_OUT;
  const pzNear = zFrom - PYLON_OUT;

  const dugX = -(hx + 7.6);   // behind the near hoarding, rising well above it
  const tech = hx + 1.0;      // technical area starts 1m off the touchline

  return (
    <group>
      {/* Hoardings, closing the ground on all four sides. The side runs
          overhang each end by the same 5.5m the ends are set back, so the
          rectangle meets itself at the corners without overlapping. */}
      <BoardRun len={sideLen} x={-bx} z={midZ} rotY={Math.PI / 2} aniso={aniso} />
      <BoardRun len={sideLen} x={bx} z={midZ} rotY={-Math.PI / 2} aniso={aniso} />
      <BoardRun len={width} x={0} z={zEnd + BOARD_OFF} rotY={Math.PI} aniso={aniso} />
      <BoardRun len={width} x={0} z={zFrom - BOARD_OFF} rotY={0} aniso={aniso} />

      {/* Corner flags go at REAL corners only. When the pitch is cut short
          the near edge of the grass is just a cut, and a flag there would be
          quietly telling the reader something false about where they are. */}
      <CornerFlag x={-hx} z={zEnd} face={-0.9} phase={0} />
      <CornerFlag x={hx} z={zEnd} face={0.9} phase={1.7} />
      {ownEnd && (
        <>
          <CornerFlag x={-hx} z={zFrom} face={-2.2} phase={3.1} />
          <CornerFlag x={hx} z={zFrom} face={2.2} phase={4.6} />
        </>
      )}

      {/* Dugouts straddle the halfway line — z = 0 in the pitch's own frame,
          wherever the grass happens to be cut. If that falls behind the
          drawn region they sit on the run-off, which is where they are at a
          real ground anyway. */}
      <Dugout x={dugX} z={-5.4} />
      <Dugout x={dugX} z={5.4} />
      {[-1, 1].map((s) => (
        <group key={s}>
          <Chalk x={-(tech + 2)} z={s * 11.2} w={4.0} d={0.1} />
          <Chalk x={-(tech + 4)} z={s * 6.1} w={0.1} d={10.2} />
        </group>
      ))}

      {/* Floodlights. Four is what a training ground has, and four corners
          is also what gives the eye a height reference wherever it looks. */}
      {([[-px, pzFar], [px, pzFar], [-px, pzNear], [px, pzNear]] as const).map(
        ([lx, lz]) => (
          <Pylon
            key={`${lx},${lz}`}
            x={lx}
            z={lz}
            aim={Math.atan2(-lx, midZ - lz)}
          />
        ),
      )}
    </group>
  );
}
