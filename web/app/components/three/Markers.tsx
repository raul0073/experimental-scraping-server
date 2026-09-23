"use client";

import { Html } from "@react-three/drei";

import { toX, toZ } from "./Pitch3D";

/** Labelled pins at known Opta coordinates.
 *
 *  A debugging instrument, and the fastest way to prove the frame is right.
 *  Opta's x runs 0 at your own goal line to 100 at theirs and its y runs 0 at
 *  the RIGHT touchline to 100 at the LEFT, which is the reverse of what
 *  everyone assumes — and a mirrored pitch looks completely plausible until
 *  a winger turns up on the wrong flank in every picture on the site.
 *
 *  Drop a pin at (100, 50) and it should sit in the middle of the attacking
 *  goal. At (0, 0) it should be the corner flag to the RIGHT of your own
 *  goalkeeper as he looks up the pitch.
 */
export type Marker = { x: number; y: number; label: string; colour?: string };

export function Markers({ points }: { points: Marker[] }) {
  return (
    <group>
      {points.map((p) => (
        <group key={p.label} position={[toX(p.y), 0, toZ(p.x)]}>
          <mesh position={[0, 1.6, 0]} castShadow>
            <sphereGeometry args={[0.9, 20, 20]} />
            <meshStandardMaterial
              color={p.colour ?? "#ffd23f"}
              emissive={p.colour ?? "#ffd23f"}
              emissiveIntensity={0.4}
              roughness={0.3}
            />
          </mesh>
          <mesh position={[0, 0.8, 0]}>
            <cylinderGeometry args={[0.07, 0.07, 1.6, 8]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
          <Html center position={[0, 3.6, 0]} distanceFactor={80}>
            <span className="num whitespace-nowrap rounded bg-[#0d1520]/90 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              {p.label}
            </span>
          </Html>
        </group>
      ))}
    </group>
  );
}
