"use client";

import { Html } from "@react-three/drei";
import { type ThreeEvent } from "@react-three/fiber";
import { useMemo } from "react";
import * as THREE from "three";

import { PITCH_L, PITCH_W, toX, toZ } from "./Pitch3D";

/** The fifteen zones, as heat on the grass.
 *
 *  NO HEIGHT, AND THAT IS THE POINT. The honest question before building
 *  anything in 3D is whether the third dimension carries information. Here
 *  it does not: a zone value is one number per place on the plane, and
 *  colour on the plane is what that wants. The column version was built
 *  first and was rejected on sight — it turned a pitch into a bar chart in
 *  perspective, which is strictly worse than a bar chart, and you could not
 *  see the pitch through it.
 *
 *  What the 3D stage earns instead is CONTEXT and CONTINUITY. The goals,
 *  the box and the arena are right there, so "where they get got at" is
 *  read against the goal rather than against a cell in a grid; and it is
 *  the same pitch, the same cameras and the same click-to-inspect as the
 *  shot and pass maps. That is a real reason to be here. Height is not.
 *
 *  🐛 AND IT WAS A WASH BEFORE THIS. The first version interpolated the
 *  fifteen values into one smooth surface covering the whole pitch. It was
 *  reported as "not intuitive at all, not like the rest of the visuals",
 *  and the reason is exact: every other view on this site puts OBJECTS on a
 *  pitch — balls, ribbons, figures — while that one REPLACED the pitch with
 *  a stain. The stripes, the markings and the boxes all went under it, and
 *  with them every cue that made the rest read as football. It also had
 *  nothing to look at: no edges, no focus, and no number.
 *
 *  Fifteen inset tiles with the figure printed on each fixes all of it. The
 *  grass shows between them, the cells are unmistakable, clicking one is
 *  obvious, and it stops claiming a resolution the data never had — smooth
 *  colour from fifteen numbers implies detail between them that does not
 *  exist.
 *
 *  Channels are drawn at their REAL widths, not as five equal strips: the
 *  wings take the outer 21% each, the half-spaces about 16, the centre the
 *  middle 26. Seeing the half-spaces as narrower than the centre is half
 *  the reason to draw this rather than tabulate it.
 */

import { CHANNELS, THIRDS, cellAt, type ZoneValues } from "./zones";

/** How much grass shows between tiles. Enough that the stripes and the
 *  markings read through the grid, not so much that the cells stop
 *  looking like a map of the pitch. */
const GAP = 1.6;

/** Green through yellow to red, the same ramp as the flat map on the team
 *  page — a reader moving between the two should not have to relearn the
 *  colours. Its weakness for colour blindness is survivable only because
 *  every value is also printed. */
const RAMP: [number, [number, number, number]][] = [
  [0.0, [38, 150, 92]],
  [0.5, [246, 206, 36]],
  [1.0, [226, 42, 32]],
];

function ramp(t: number): [number, number, number] {
  const u = Math.max(0, Math.min(1, t));
  for (let i = 1; i < RAMP.length; i++) {
    const [t1, c1] = RAMP[i];
    if (u <= t1 || i === RAMP.length - 1) {
      const [t0, c0] = RAMP[i - 1];
      const k = t1 === t0 ? 0 : (u - t0) / (t1 - t0);
      return [
        c0[0] + (c1[0] - c0[0]) * k,
        c0[1] + (c1[1] - c0[1]) * k,
        c0[2] + (c1[2] - c0[2]) * k,
      ];
    }
  }
  return RAMP[0][1];
}


function Paint({
  x, z, w, d, colour = "#ffffff", opacity = 0.5, y = 0.135,
}: {
  x: number; z: number; w: number; d: number;
  colour?: string; opacity?: number; y?: number;
}) {
  return (
    <mesh position={[x, y, z]} rotation={[-Math.PI / 2, 0, 0]} raycast={() => null}>
      <planeGeometry args={[w, d]} />
      <meshBasicMaterial color={colour} transparent opacity={opacity}
                         depthWrite={false} side={THREE.DoubleSide} />
    </mesh>
  );
}

export default function ZoneHeatMesh({
  values, lo, hi, curve = "linear", decimals = 0, selected, onSelect,
}: {
  values: ZoneValues;
  lo: number;
  hi: number;
  curve?: "linear" | "sqrt";
  decimals?: number;
  selected: string;
  onSelect: (cell: string) => void;
}) {
  const span = hi - lo || 1;

  const tiles = useMemo(
    () =>
      THIRDS.flatMap((t) =>
        CHANNELS.map((c) => {
          const cell = t.key + c.key;
          const x0 = toX(c.lo);
          const x1 = toX(c.hi);
          const z0 = toZ(t.lo);
          const z1 = toZ(t.hi);
          const v = values[cell];
          const raw = typeof v === "number"
            ? Math.max(0, Math.min(1, (v - lo) / span))
            : null;
          const k = raw === null ? null : curve === "sqrt" ? Math.sqrt(raw) : raw;
          return {
            cell,
            v,
            k,
            x: (x0 + x1) / 2,
            z: (z0 + z1) / 2,
            // INSET, so the grass shows between them. A wall-to-wall wash
            // covered the stripes, the markings and the boxes — every cue
            // that made the other views read as football — and left a stain
            // with nothing to look at. Tiles sitting ON a pitch is the same
            // idea as balls on a pitch and ribbons on a pitch.
            w: Math.abs(x1 - x0) - GAP,
            d: Math.abs(z1 - z0) - GAP,
          };
        }),
      ),
    [values, lo, span, curve],
  );

  return (
    <group>
      {tiles.map((t) => {
        const on = t.cell === selected;
        const c = t.k === null ? [90, 100, 110] : ramp(t.k);
        return (
          <group key={t.cell} position={[t.x, 0, t.z]}>
            <mesh
              position={[0, 0.12, 0]}
              rotation={[-Math.PI / 2, 0, 0]}
              onClick={(e: ThreeEvent<MouseEvent>) => {
                e.stopPropagation();
                onSelect(on ? "" : t.cell);
              }}
            >
              <planeGeometry args={[t.w, t.d]} />
              <meshBasicMaterial
                color={`rgb(${c.map(Math.round).join(",")})`}
                transparent
                opacity={t.k === null ? 0.18 : (on ? 0.92 : 0.5 + 0.34 * t.k)}
                depthWrite={false}
                side={THREE.DoubleSide}
              />
            </mesh>

            {/* THE NUMBER ON THE TILE. Colour carries the shape and the
                figure carries the precision — nobody should be estimating a
                value by eye off a ramp when the number can simply be
                printed where they are already looking. */}
            {typeof t.v === "number" && (
              <Html center position={[0, 0.5, 0]} zIndexRange={[18, 0]}>
                <div
                  className="num select-none whitespace-nowrap text-[13px] font-bold leading-none"
                  style={{
                    color: "#ffffff",
                    textShadow: "0 1px 4px rgba(0,0,0,.85), 0 0 3px rgba(0,0,0,.9)",
                  }}
                >
                  {t.v.toFixed(decimals)}
                </div>
              </Html>
            )}

            {on && (
              <group>
                <Paint x={0} z={-t.d / 2} w={t.w} d={0.45} opacity={0.95} />
                <Paint x={0} z={t.d / 2} w={t.w} d={0.45} opacity={0.95} />
                <Paint x={-t.w / 2} z={0} w={0.45} d={t.d} opacity={0.95} />
                <Paint x={t.w / 2} z={0} w={0.45} d={t.d} opacity={0.95} />
              </group>
            )}
          </group>
        );
      })}

      {/* WHICH END IS WHICH. From overhead a pitch is symmetrical and there
          is nothing in the picture to say which way this side is playing —
          the goals are identical and the markings are mirrored. Naming the
          thirds settles it in one glance, off the grass so they never cover
          the measure they are labelling. */}
      {THIRDS.map((t) => (
        <Html
          key={t.key}
          center
          position={[-(PITCH_W / 2 + 7), 0.4, toZ((t.lo + t.hi) / 2)]}
          zIndexRange={[15, 0]}
        >
          <div className="select-none whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white/80"
               style={{ background: "rgba(7,17,25,0.72)" }}>
            {t.key === "A" ? "attacking third ↑" : t.label}
          </div>
        </Html>
      ))}
    </group>
  );
}
