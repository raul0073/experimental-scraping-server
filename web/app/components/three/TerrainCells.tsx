"use client";

import { Html, RoundedBox } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useRef, useState } from "react";
import * as THREE from "three";

import { toX, toZ } from "./Pitch3D";

/** Territory as paired columns standing ON the pitch.
 *
 *  TWO COLUMNS PER CELL, SIDE BY SIDE, BOTH RISING. The first version put
 *  the home side's above the grass and the away side's below it, which reads
 *  beautifully in a sketch and is useless in practice: from any camera
 *  angle a reader would actually choose, the entire away team is hidden
 *  under the pitch. Half the fixture was invisible and the picture was a
 *  wall of green.
 *
 *  Splitting each cell across its width solves it without inventing space —
 *  a cell is 14 to 18 metres wide and the two columns sit in it comfortably,
 *  close enough that the comparison is immediate and the taller one obvious.
 *
 *  COLOUR CARRIES THE VALUE TOO. Side is green or blue; how dark it is says
 *  how big. Height alone was a field of identical green blocks where only
 *  the silhouette meant anything, and the silhouette is the first thing a
 *  perspective view distorts.
 *
 *  And every column prints its number. "No data at all" was the complaint
 *  about a chart whose figures only appeared one at a time on hover.
 */

const CHANNELS = [
  { key: "RW", lo: 0, hi: 21.1 },
  { key: "RH", lo: 21.1, hi: 36.8 },
  { key: "C", lo: 36.8, hi: 63.2 },
  { key: "LH", lo: 63.2, hi: 78.9 },
  { key: "LW", lo: 78.9, hi: 100 },
];
const THIRDS = [
  { key: "D", lo: 0, hi: 33.3 },
  { key: "M", lo: 33.3, hi: 66.7 },
  { key: "A", lo: 66.7, hi: 100 },
];

/** Tall enough to compare, short enough that the goals and the markings are
 *  still what a reader recognises first. */
const MAX_H = 11;

export type Cell = { cell: string; value: number };

/** Pale at nothing, saturated at the top of the range — so a short column
 *  and a tall one differ in two channels at once. */
function shade(base: string, t: number) {
  const c = new THREE.Color(base);
  const pale = new THREE.Color("#dfe9e3");
  return pale.lerp(c, 0.25 + 0.75 * Math.max(0, Math.min(1, t)));
}

function Column({
  cell, value, scale, colour, side, onHover, label,
}: {
  cell: string; value: number; scale: number; colour: string;
  side: -1 | 1;
  label: string; onHover: (v: string | null) => void;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const [hot, setHot] = useState(false);
  // EVERY HOOK BEFORE THE FIRST RETURN. `useFrame` used to sit below the
  // guard, so an unrecognised cell key changed the number of hooks this
  // component ran and React tore the tree down — the column view appearing
  // for a second and then dying.
  useFrame((_s, dt) => {
    if (!ref.current) return;
    const want = hot ? 1.08 : 1;
    ref.current.scale.x += (want - ref.current.scale.x) * Math.min(1, dt * 14);
    ref.current.scale.z = ref.current.scale.x;
  });

  const third = THIRDS.find((t) => cell.startsWith(t.key));
  const chan = CHANNELS.find((c) => cell.slice(1) === c.key);
  if (!third || !chan) return null;

  const x0 = toX(chan.hi);
  const x1 = toX(chan.lo);
  const z0 = toZ(third.lo);
  const z1 = toZ(third.hi);
  const cellW = Math.abs(x1 - x0);
  const cellD = Math.abs(z1 - z0);
  // each side takes half the cell's width, with a gap down the middle
  const w = cellW / 2 - 1.4;
  const d = Math.min(cellD - 3, 13);
  const h = Math.max(0.25, (value / scale) * MAX_H);
  const cx = (x0 + x1) / 2 + side * (cellW / 4);
  const cz = (z0 + z1) / 2;
  const col = shade(colour, value / scale);

  return (
    <group position={[cx, 0, cz]}>
      <RoundedBox
        ref={ref}
        position={[0, h / 2, 0]}
        args={[w, h, d]}
        radius={Math.min(0.45, h / 2.5, w / 6)}
        smoothness={3}
        castShadow
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHot(true);
          onHover(label);
        }}
        onPointerOut={() => {
          setHot(false);
          onHover(null);
        }}
      >
        <meshStandardMaterial
          color={col}
          roughness={0.42}
          metalness={0.02}
        />
      </RoundedBox>
      {/* The number, always on, facing the camera wherever it is.
          HTML rather than drei's <Text>: that one renders through
          troika-three-text, which fetches a font file before it can draw
          anything. Fetching means suspending, and a component that suspends
          inside a Canvas with no boundary above it takes the whole scene
          down — which is exactly what happened here, a pitch that drew once
          and vanished. This uses the page's own font and cannot fail.
          `distanceFactor` keeps it scaling like something in the scene
          instead of staying a fixed size on screen as the camera pulls out. */}
      <Html center position={[0, h + 2.4, 0]} distanceFactor={90} zIndexRange={[10, 0]}>
        <span
          className="num select-none whitespace-nowrap rounded px-1 text-[13px] font-bold"
          style={{
            color: hot ? "#ffffff" : "#eaf2ee",
            textShadow: "0 1px 3px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9)",
          }}
        >
          {value.toFixed(2)}
        </span>
      </Html>
    </group>
  );
}

export function TerrainCells({
  home, away, homeColour = "#2fa85f", awayColour = "#2f7fd0", onHover,
}: {
  /** both already in the HOME side's frame */
  home: Cell[];
  away: Cell[];
  homeColour?: string;
  awayColour?: string;
  onHover: (v: string | null) => void;
}) {
  const scale = Math.max(
    0.15, ...home.map((c) => c.value), ...away.map((c) => c.value),
  );
  return (
    <group>
      {home.map((c) => (
        <Column
          key={`h-${c.cell}`}
          cell={c.cell}
          value={c.value}
          scale={scale}
          colour={homeColour}
          side={-1}
          label={`home|${c.cell}`}
          onHover={onHover}
        />
      ))}
      {away.map((c) => (
        <Column
          key={`a-${c.cell}`}
          cell={c.cell}
          value={c.value}
          scale={scale}
          colour={awayColour}
          side={1}
          label={`away|${c.cell}`}
          onHover={onHover}
        />
      ))}
    </group>
  );
}
