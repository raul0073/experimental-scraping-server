"use client";

import { Html } from "@react-three/drei";
import { type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

import { useLabelScale } from "./labelScale";

import { PITCH_L, PITCH_W, toX, toZ } from "./Pitch3D";

/** Passes as ribbons on and over the pitch.
 *
 *  WHAT THE THIRD DIMENSION IS FOR HERE, and it is not decoration: Opta
 *  flags whether a pass LEFT THE GROUND — Chipped, Longball, Cross,
 *  HeadPass. A forty-metre ball along the floor and a forty-metre diagonal
 *  over the top are completely different actions, and a flat map draws them
 *  as the same line. Height is the one thing it cannot say, so height is
 *  what this spends it on: aerial passes arc, ground passes stay down.
 *
 *  RIBBONS, NOT LINES. `LineBasicMaterial` is one pixel wide on every
 *  platform that matters — `linewidth` is silently ignored — so a pass map
 *  built from lines is a cobweb that disappears at any angle except
 *  straight down. A ribbon is real geometry with real width, takes the
 *  light, and survives a low camera.
 *
 *  ONE GEOMETRY, ONE DRAW CALL. A club plays about 18,000 passes a season.
 *  Even filtered to one player that is over a thousand objects, and a
 *  thousand meshes is a thousand draw calls. Every visible pass goes into a
 *  single buffer instead, rebuilt only when the filter changes.
 *
 *  Every pass gets the SAME number of segments whether it arcs or not, so
 *  that a ray hit's `faceIndex` divides straight back to which pass it hit.
 *  The alternative — packing flat passes as one quad and arcs as six — saves
 *  a few thousand triangles nobody was short of and makes picking a lookup
 *  table that has to be kept in step with the geometry.
 */

const SEGS = 6;                       // per pass, arcing or not
const FACES = SEGS * 2;               // triangles per pass
const VERTS = (SEGS + 1) * 2;         // ribbon cross-sections, two each
const WIDTH = 0.36;                   // ribbon half-width at the far end

/** THE PASS ITSELF — the type, the flag bits, the classes and the flight
 *  geometry (including BASE_Y and the climb) — now lives in `passMath.ts`,
 *  which imports no three, so the flat fallback can colour the same passes
 *  without the WebGL stack behind it. Re-exported here so every existing
 *  import of them is unchanged. */
export {
  BIT, CLASSES, arcOf, at, classOf, ends, lengthOf, type Pass,
} from "./passMath";
import {
  BASE_Y, BIT, CLASSES, CLIMB_MAX, arcOf, at, classOf, lengthOf, type Pass,
} from "./passMath";

const SHADOW_Y = 0.07;      // just under the ribbons, clear of the markings

/** THE SHADOW IS WHAT MAKES THE HEIGHT LEGIBLE.
 *
 *  An arc drawn over a pitch from an elevated camera is ambiguous: a ball
 *  ten metres up and a ball on the floor ten metres further on project to
 *  nearly the same place. A dark track on the grass beneath it resolves
 *  that instantly, because the GAP between the two is the height.
 *
 *  Straight down, not along the sun. A true shadow from this scene's light
 *  would sit four metres to one side at the top of a lofted ball, which
 *  reads as a second, unrelated stroke rather than as the same pass. Every
 *  flight tracker and every minimap drops it vertically for the same reason.
 *
 *  It still behaves like a shadow in the two ways that matter: it SPREADS
 *  and FADES as the ball climbs. Those are doing real work — a flat delivery
 *  keeps a tight dark track the whole way, a steepling one almost loses its
 *  shadow at the peak, and you can read the flight from the ground alone.
 *
 *  Ground passes get none. That absence is the signal.
 */
function build(passes: Pass[], solo: boolean, shadow = false) {
  const n = passes.length;
  const pos = new Float32Array(n * VERTS * 3);
  const col = new Float32Array(n * VERTS * 4);
  const idx = new Uint32Array(n * FACES * 3);
  const c = new THREE.Color();

  for (let i = 0; i < n; i++) {
    const p = passes[i];
    const { x0, z0, x1, z1, L, h } = arcOf(p);
    const ux = (x1 - x0) / (L || 1);
    const uz = (z1 - z0) / (L || 1);
    // horizontal perpendicular: the ribbon lies flat, so its face points up
    // and it stays readable from every camera that is above the grass —
    // which, since orbit is blocked below it, is all of them
    const px = -uz;
    const pz = ux;
    c.set(shadow ? "#06120c" : classOf(p.flags).colour);

    for (let k = 0; k <= SEGS; k++) {
      const t = k / SEGS;
      const cx = x0 + (x1 - x0) * t;
      const cz = z0 + (z1 - z0) * t;
      const lift = 4 * t * (1 - t);              // 0 at the ends, 1 at the peak
      const cy = shadow ? SHADOW_Y : BASE_Y + h * lift;
      // widens toward the target, which is what says which way it went
      // without an arrowhead on every one of two thousand passes
      let w = WIDTH * (solo ? 2.2 : 1) * (0.4 + 0.6 * t);
      // and fades in from the passer, so a dense map reads as flow
      let a = solo ? 0.95 : 0.1 + 0.42 * t;
      if (shadow) {
        // spreads and fades with the ball's height, so the flight can be
        // read off the ground track alone
        const climb = h ? (h * lift) / CLIMB_MAX : 0;
        w *= 1 + 1.1 * climb;
        a = (solo ? 0.55 : 0.28) * (1 - 0.6 * climb);
      }

      for (const s of [-1, 1]) {
        const v = (i * VERTS + k * 2 + (s < 0 ? 0 : 1)) * 3;
        pos[v] = cx + px * w * s;
        pos[v + 1] = cy;
        pos[v + 2] = cz + pz * w * s;
        const q = (i * VERTS + k * 2 + (s < 0 ? 0 : 1)) * 4;
        col[q] = c.r;
        col[q + 1] = c.g;
        col[q + 2] = c.b;
        col[q + 3] = a;
      }
    }

    for (let k = 0; k < SEGS; k++) {
      const base = i * VERTS + k * 2;
      const f = (i * FACES + k * 2) * 3;
      idx[f] = base;
      idx[f + 1] = base + 1;
      idx[f + 2] = base + 3;
      idx[f + 3] = base;
      idx[f + 4] = base + 3;
      idx[f + 5] = base + 2;
    }
  }

  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.BufferAttribute(col, 4));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  return g;
}

/** The two ends of the selected pass, so it reads as going somewhere. */
function Ends({ pass }: { pass: Pass }) {
  const { x0, z0, x1, z1 } = arcOf(pass);
  const colour = classOf(pass.flags).colour;
  return (
    <group>
      <mesh position={[x0, BASE_Y, z0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.75, 1.0, 28]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.9}
                           side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[x1, BASE_Y + 0.02, z1]} castShadow>
        <sphereGeometry args={[0.62, 18, 12]} />
        <meshStandardMaterial color={colour} emissive={colour}
                              emissiveIntensity={0.5} roughness={0.35} />
      </mesh>
    </group>
  );
}

export function PassCloud({
  passes, selected, onSelect,
}: {
  passes: Pass[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  const ls = useLabelScale();
  const sel = passes[selected];

  // HIDE THE REST, do not fade them. Two thousand ribbons at low opacity are
  // still two thousand ribbons catching the eye and swallowing clicks, and
  // the one that was chosen ends up buried in the clutter choosing it was
  // meant to clear.
  //
  // The choice happens INSIDE the memo. Built outside it, `sel ? [sel] : …`
  // is a fresh array on every render, so the dependency never matched and
  // four thousand ribbons were rebuilt from scratch every time anything on
  // the page changed.
  const geo = useMemo(
    () => build(sel ? [sel] : passes, !!sel),
    [passes, sel],
  );
  /** Only the lofted ones, in their own buffer. Kept separate so the main
   *  geometry keeps exactly `FACES` triangles per pass and a ray hit still
   *  divides back to an index — and so this mesh can be taken out of
   *  raycasting entirely, since a shadow should never be the thing you
   *  clicked. */
  const shade = useMemo(() => {
    const air = (sel ? [sel] : passes).filter((p) => p.flags & BIT.air);
    return air.length ? build(air, !!sel, true) : null;
  }, [passes, sel]);

  // and a geometry replaced is a geometry still on the GPU until it is told
  // otherwise — useMemo returning a cleanup does not run one
  useEffect(() => () => geo.dispose(), [geo]);
  useEffect(() => () => shade?.dispose(), [shade]);

  const pick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    if (sel) {
      onSelect(-1);
      return;
    }
    const f = e.faceIndex;
    if (f === undefined || f === null) return;
    const i = Math.floor(f / FACES);
    if (i >= 0 && i < passes.length) onSelect(i);
  };

  return (
    <group>
      {shade && (
        <mesh geometry={shade} raycast={() => null}>
          <meshBasicMaterial vertexColors transparent depthWrite={false}
                             side={THREE.DoubleSide} />
        </mesh>
      )}
      <mesh geometry={geo} onClick={pick}>
        <meshBasicMaterial vertexColors transparent depthWrite={false}
                           side={THREE.DoubleSide} />
      </mesh>

      {sel && (
        <>
          <Ends pass={sel} />
          {/* Above the highest point of the pass, which for a lofted ball is
              well clear of the pitch and for a ground pass is just over it.
              A plate rather than shadowed text: these hang in front of
              ribbons painted in their own colour. */}
          <Html
            center
            position={[
              at(sel, 0.5)[0],
              at(sel, 0.5)[1] + 2.6,
              at(sel, 0.5)[2],
            ]}
            distanceFactor={18 * ls}
            zIndexRange={[30, 0]}
          >
            <div
              className="select-none whitespace-nowrap rounded-md px-2 py-1 text-center leading-tight"
              style={{
                background: "rgba(7,17,25,0.88)",
                borderBottom: `2px solid ${classOf(sel.flags).colour}`,
                boxShadow: "0 2px 10px rgba(0,0,0,.6)",
              }}
            >
              <div className="text-[11px] font-semibold text-white">
                {sel.player}
                {sel.to && (
                  <>
                    <span className="mx-1 opacity-60">→</span>
                    {sel.to}
                  </>
                )}
              </div>
              <div className="num text-[12px] font-bold"
                   style={{ color: classOf(sel.flags).colour }}>
                {lengthOf(sel).toFixed(0)} m
                {sel.flags & BIT.air ? " · in the air" : ""}
              </div>
            </div>
          </Html>
        </>
      )}
    </group>
  );
}
