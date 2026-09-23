"use client";

import { Html, useGLTF, useTexture } from "@react-three/drei";
import { type ThreeEvent } from "@react-three/fiber";
import { Suspense, useEffect, useMemo } from "react";
import * as THREE from "three";

import { PITCH_L, PITCH_W, toX, toZ } from "./Pitch3D";

/** Average positions, the passes between them, and WHERE THEY ACTUALLY WERE.
 *
 *  THE PROBLEM THIS EXISTS TO FIX. An average position is a mean, and a mean
 *  of a wide cloud is a place nobody stood. Measured on Arsenal 25/26, the
 *  share of a player's actions that happen within twelve metres of his own
 *  average position:
 *
 *      Raya (GK)   63%      Saliba      28%
 *      Gabriel     29%      Ødegaard    19%
 *      Zubimendi   16%      RICE        13%
 *
 *  Rice's dot is a place he is thirteen per cent of the time. Only the
 *  keeper is well described by a point. So the flat chart is not wrong so
 *  much as it is answering a question nobody asked, and drawing the same
 *  dots again in perspective would be worse than the flat one — a 3D scatter
 *  plot with extra steps.
 *
 *  WHAT THE HEIGHT IS FOR, then: the selected player's TERRITORY, as a
 *  density surface. Put it under the nodes and you can see whether a man's
 *  average position sits on a peak or in the valley between two of them.
 *  For a midfielder who shuttles it is a valley, and that is the whole story
 *  the dot was hiding.
 *
 *  One player's territory at a time. Eleven translucent mounds over each
 *  other is mud, and the same isolate-on-click the shot and pass maps use
 *  already works here.
 */

export type Spot = {
  name: string;
  /** mean position, Opta terms, so the conversion stays in one place */
  x: number; y: number;
  passes: number;
  apps: number;
};
export type Edge = { a: string; b: string; n: number };

/** A density field over the pitch, row-major, `gw` across by `gz` along. */
export type Field = { g: Float32Array; gw: number; gz: number; max: number };

const PEAK = 4.6;            // metres at the busiest cell — twice a goal
const NODE_Y = 0.16;

/* ---------------------------------------------------------------- terrain */

function sample(f: Field, u: number, v: number) {
  // bilinear, clamped — a nearest-neighbour lookup gives a staircase and the
  // whole point of a surface is that it is smooth
  const x = Math.min(f.gw - 1.001, Math.max(0, u * f.gw - 0.5));
  const z = Math.min(f.gz - 1.001, Math.max(0, v * f.gz - 0.5));
  const x0 = Math.floor(x);
  const z0 = Math.floor(z);
  const fx = x - x0;
  const fz = z - z0;
  const at = (i: number, j: number) => f.g[j * f.gw + i];
  const a = at(x0, z0) + (at(x0 + 1, z0) - at(x0, z0)) * fx;
  const b = at(x0, z0 + 1) + (at(x0 + 1, z0 + 1) - at(x0, z0 + 1)) * fx;
  return a + (b - a) * fz;
}

function Territory({ field, colour }: { field: Field; colour: string }) {
  const geo = useMemo(() => {
    const NX = 44;
    const NZ = 68;
    const g = new THREE.PlaneGeometry(PITCH_W, PITCH_L, NX, NZ);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position as THREE.BufferAttribute;
    const col = new Float32Array(pos.count * 4);
    const c = new THREE.Color(colour);
    for (let i = 0; i < pos.count; i++) {
      // plane coordinates back to 0..1 across and along the pitch
      const u = pos.getX(i) / PITCH_W + 0.5;
      const v = pos.getZ(i) / PITCH_L + 0.5;
      const d = field.max ? sample(field, u, v) / field.max : 0;
      // a square root, because density falls off fast and a linear surface
      // is a spike at the busiest cell and a flat plain everywhere else
      const h = Math.sqrt(Math.max(0, d));
      pos.setY(i, 0.12 + h * PEAK);
      col[i * 4] = c.r;
      col[i * 4 + 1] = c.g;
      col[i * 4 + 2] = c.b;
      // fades to nothing at the fringe, so the surface ends where the player
      // did rather than at the edge of a rectangle
      col[i * 4 + 3] = Math.min(0.72, h * 1.25);
    }
    pos.needsUpdate = true;
    g.setAttribute("color", new THREE.BufferAttribute(col, 4));
    g.computeVertexNormals();
    return g;
  }, [field, colour]);

  useEffect(() => () => geo.dispose(), [geo]);

  return (
    <mesh geometry={geo} raycast={() => null}>
      <meshStandardMaterial
        vertexColors
        transparent
        depthWrite={false}
        roughness={0.55}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ------------------------------------------------------------------ links */

/** A directed pass count, as its own lane.
 *
 *  THE FLAT VERSION THROWS THIS AWAY. `{a, b, n}` has always been directed
 *  in the payload, and one line per pair loses it: Gabriel and Saliba at
 *  330 and 327 is a pivot, 300 and 80 is a dead end, and undirected draws
 *  them identically. Each direction gets its own lane, pushed to one side
 *  of the pair's axis, so the asymmetry is the picture.
 */
function Lane({
  from, to, n, max, dim,
}: {
  from: Spot; to: Spot; n: number; max: number; dim: boolean;
}) {
  const geo = useMemo(() => {
    const x0 = toX(from.y);
    const z0 = toZ(from.x);
    const x1 = toX(to.y);
    const z1 = toZ(to.x);
    const L = Math.hypot(x1 - x0, z1 - z0) || 1;
    const ux = (x1 - x0) / L;
    const uz = (z1 - z0) / L;
    const px = -uz;
    const pz = ux;
    const w = 0.18 + 1.25 * (n / max);
    const lane = 0.85 + w;               // clear of the opposite direction
    const SEG = 10;
    const v: number[] = [];
    const idx: number[] = [];
    for (let k = 0; k <= SEG; k++) {
      const t = k / SEG;
      // pulled in from both nodes so the lane does not disappear under them
      const tt = 0.10 + 0.80 * t;
      const cx = x0 + (x1 - x0) * tt + px * lane;
      const cz = z0 + (z1 - z0) * tt + pz * lane;
      const cy = 0.34 + 1.5 * 4 * t * (1 - t);
      const hw = w * (0.45 + 0.55 * t);
      v.push(cx - px * hw, cy, cz - pz * hw, cx + px * hw, cy, cz + pz * hw);
      if (k < SEG) {
        const b = k * 2;
        idx.push(b, b + 1, b + 3, b, b + 3, b + 2);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
    g.setIndex(idx);
    return g;
  }, [from, to, n, max]);

  useEffect(() => () => geo.dispose(), [geo]);

  return (
    <mesh geometry={geo} raycast={() => null}>
      <meshBasicMaterial
        color="#dff1ff"
        transparent
        opacity={dim ? 0.07 : 0.14 + 0.5 * (n / max)}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ----------------------------------------------------------------- player */

/** A player, at the height a player is.
 *
 *  THE FIGURE NEVER SCALES. It is tempting to size it by involvement, and
 *  it would wreck the one thing the arena was built for: the flags, the
 *  hoardings and the pylons are there so the eye has objects of known size
 *  to measure the scene against, and a 2.6m Rice beside a 1.4m Gyökeres
 *  quietly destroys all of it. Volume goes on the PLINTH underneath, which
 *  is a footprint on the pitch plane and stays comparable from every seat.
 *
 *  Primitives rather than a model, for now. They cost no fetch — and a
 *  fetch inside a Canvas is the thing that took this scene down once
 *  already. A real .glb drops in here and nothing else in the file changes:
 *  the plinth, the label, the click target and the selection all live on
 *  the group around it.
 */
/** The OPTIMISED model, not the download.
 *
 *  What came off Sketchfab was 22.8 MB: 195,928 triangles and four PNG
 *  textures totalling 16 MB. It renders — `clone()` shares geometry and
 *  material, so eleven of them are eleven draw calls over one upload, not
 *  eleven uploads — but it is 2.15 million triangles a frame for figures
 *  that are thirty pixels tall from most seats, on a site whose entire
 *  build was 1.5 MB.
 *
 *  `scripts/optimise-model.sh` reduces it to 761 KB and 14,959 triangles
 *  with 1024px WebP textures, which is indistinguishable at any distance
 *  this scene actually uses. The source is kept at data/models/ — OUTSIDE
 *  public/, or Next copies all 22 MB of it into the export. */
export const MODEL = "/models/player.glb";
const FIGURE_H = 1.82;

function Figure({ colour }: { colour: string }) {
  return (
    <group>
      <mesh position={[0, 0.45, 0]} castShadow>
        <cylinderGeometry args={[0.17, 0.25, 0.9, 14]} />
        <meshStandardMaterial color={colour} roughness={0.6} />
      </mesh>
      <mesh position={[0, 1.13, 0]} castShadow>
        <capsuleGeometry args={[0.235, 0.4, 6, 14]} />
        <meshStandardMaterial color={colour} roughness={0.6} />
      </mesh>
      <mesh position={[0, 1.64, 0]} castShadow>
        <sphereGeometry args={[0.16, 18, 12]} />
        <meshStandardMaterial color={colour} roughness={0.7} />
      </mesh>
    </group>
  );
}

/** The real thing, when there is one.
 *
 *  NORMALISED BY MEASUREMENT, NOT BY A CONSTANT. Models are authored in
 *  whatever unit the artist felt like — centimetres, inches, "1.0 = a
 *  person" — so a hard-coded scale is a coin flip between a toy and a
 *  skyscraper on a pitch built in real metres. Measure the bounding box,
 *  scale its height to 1.82m and sit its feet on the grass, and any model
 *  drops in correctly.
 *
 *  `clone()` copies the transform tree and SHARES geometry and materials,
 *  so eleven of these are eleven draw calls over one mesh on the GPU — not
 *  eleven uploads. It also means the material is shared, which is why
 *  selection is shown on the plinth and the label rather than by tinting a
 *  figure: recolouring one would recolour the side.
 */
export type Kit = { shirt: string; shorts: string; socks?: string };

/** Which texel is which garment, baked by scripts/build_kit_regions.py.
 *  R channel: 0 leave, 1 shirt, 2 shorts, 3 socks. */
export const REGIONS = "/models/player-regions.png";
const R_SHIRT = 1;
const R_SHORTS = 2;
const R_SOCKS = 3;

const rgb = (s: string): [number, number, number] => [
  parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16),
  parseInt(s.slice(5, 7), 16),
];

/** Repaint the kit in a club colours, using the baked region map.
 *
 *  WHY A REGION MAP AND NOT COLOUR KEYS. Keying on colour gets the yellow
 *  right and is helpless on the whites, which is the part that has to change
 *  for a shirt to be PLAIN: the same white appears as stripes across the
 *  chest and as the socks, and the atlas is hundreds of small islands butted
 *  together with no gutters, so neighbouring texels are as likely to be an
 *  elbow and a knee as two parts of one garment.
 *
 *  So the garment is decided by HEIGHT UP THE BODY, worked out offline by
 *  rasterising every triangle into UV space, and shipped as a 22 KB PNG.
 *  The measurement is the argument: on this model white texels sit at height
 *  0.08-0.27 AND at 0.79, dark ones at 0.01-0.06 AND at 0.49. Both colours
 *  are two different garments, and only geometry separates them.
 *
 *  SHADING SURVIVES because the target is MULTIPLIED by the source texel own
 *  brightness rather than replacing it, so folds and baked occlusion come
 *  through. Using the max channel for that is also what makes the shirt come
 *  out plain: a white stripe and the yellow around it both peak at 1.0, so
 *  both land on the same colour and the stripe disappears. The shorts need
 *  their own curve, because near-black has no range to scale and multiplying
 *  any colour by 0.1 gives black.
 */
function repaint(
  src: THREE.Texture,
  regions: THREE.Texture,
  kit: Kit,
): THREE.Texture | null {
  const img = src.image as CanvasImageSource & { width: number; height: number };
  const reg = regions.image as CanvasImageSource & { width: number };
  if (!img?.width || !reg || typeof document === "undefined") return null;

  const c = document.createElement("canvas");
  c.width = img.width;
  c.height = img.height;
  const g = c.getContext("2d");
  if (!g) return null;
  g.drawImage(img, 0, 0);

  // the map is half the texture resolution; the browser scales it as it
  // draws, and a garment border a texel out is not a border anyone can see
  const rc = document.createElement("canvas");
  rc.width = c.width;
  rc.height = c.height;
  const rg = rc.getContext("2d");
  if (!rg) return null;
  rg.imageSmoothingEnabled = false;
  rg.drawImage(reg, 0, 0, c.width, c.height);

  let d: ImageData;
  let m: ImageData;
  try {
    d = g.getImageData(0, 0, c.width, c.height);
    m = rg.getImageData(0, 0, c.width, c.height);
  } catch {
    return null;                     // tainted canvas; keep the stock kit
  }

  const p = d.data;
  const q = m.data;
  const SHIRT = rgb(kit.shirt);
  const SHORTS = rgb(kit.shorts);
  const SOCKS = rgb(kit.socks ?? kit.shorts);

  for (let i = 0; i < p.length; i += 4) {
    const region = q[i];
    // named rather than "anything non-zero", so a map written by a later
    // version with a region this build does not know is left alone instead
    // of quietly coming out as socks
    if (region !== R_SHIRT && region !== R_SHORTS && region !== R_SOCKS) continue;
    const mx = Math.max(p[i], p[i + 1], p[i + 2]) / 255;
    let t: [number, number, number];
    let f: number;
    if (region === R_SHORTS) {
      t = SHORTS;
      f = Math.max(0.45, Math.min(1.05, 0.55 + mx * 2.8));
    } else {
      t = region === R_SHIRT ? SHIRT : SOCKS;
      f = Math.max(0.35, Math.min(1.05, mx / 0.95));
    }
    p[i] = t[0] * f;
    p[i + 1] = t[1] * f;
    p[i + 2] = t[2] * f;
  }
  g.putImageData(d, 0, 0);

  const t = new THREE.CanvasTexture(c);
  // a glTF atlas is authored with flipY off and in sRGB; a CanvasTexture
  // defaults to neither, and getting it wrong shows as a player wearing his
  // kit upside down in the wrong gamma
  t.flipY = src.flipY;
  t.colorSpace = src.colorSpace;
  t.wrapS = src.wrapS;
  t.wrapT = src.wrapT;
  t.anisotropy = src.anisotropy;
  return t;
}

function Rigged({ kit }: { kit: Kit | null }) {
  const { scene } = useGLTF(MODEL);
  const regions = useTexture(REGIONS);

  /** ONE repaint for the whole side, not one per player. The clones share
   *  a material, so this builds a single recoloured copy and every figure
   *  points at it — eleven draw calls, one texture. */
  const painted = useMemo(() => {
    if (!kit) return null;
    let made: { map: THREE.Texture; mat: THREE.Material } | null = null;
    scene.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial;
      if (made || !m?.map) return;
      const map = repaint(m.map, regions, kit);
      if (!map) return;
      const mat = m.clone();
      mat.map = map;
      made = { map, mat };
    });
    return made as { map: THREE.Texture; mat: THREE.Material } | null;
  }, [scene, regions, kit]);

  useEffect(
    () => () => {
      painted?.map.dispose();
      painted?.mat.dispose();
    },
    [painted],
  );

  const inst = useMemo(() => {
    const c = scene.clone(true);
    if (painted) {
      c.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) mesh.material = painted.mat;
      });
    }
    const box = new THREE.Box3().setFromObject(c);
    const h = box.max.y - box.min.y || 1;
    const s = FIGURE_H / h;
    c.scale.setScalar(s);
    c.position.y = -box.min.y * s;
    c.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) o.castShadow = true;
    });
    return c;
  }, [scene, painted]);
  return <primitive object={inst} />;
}

/** A model that may not be there yet. The primitive stands in while the
 *  file loads AND when there is no file — the view is never blocked on an
 *  asset, and a missing one degrades instead of blanking the scene. */
function Player({ colour, model, kit }: {
  colour: string; model: boolean; kit: Kit | null;
}) {
  if (!model) return <Figure colour={colour} />;
  return (
    <Suspense fallback={<Figure colour={colour} />}>
      <Rigged kit={kit} />
    </Suspense>
  );
}

/** What the player stands on, now that he is a player and not a disc.
 *
 *  THE SOLID PUCK HAD TO GO. It worked when it WAS the player — a disc on
 *  the grass sized by volume is a fine abstract marker. Under a figure it
 *  reads as a game-character selection ring: the eye goes to the bright
 *  slab, not the man on it, and the thing we are drawing is the man.
 *
 *  It still has both jobs to do, so neither is dropped — it is the volume
 *  reading (radius) AND the click target, because a 1.8m figure is a very
 *  small thing to hit on a 105m pitch. What changes is that it now looks
 *  like ground under someone: a soft contact shadow that fades out, with a
 *  thin ring at the radius so the size stays measurable.
 *
 *  A RING GEOMETRY, NOT A CIRCLE. A circle has one centre vertex and a rim,
 *  so a vertex-alpha gradient across it is a straight cone — every value
 *  between is linear interpolation over one enormous triangle fan. Radial
 *  segments give the falloff somewhere to curve.
 */
function Base({
  r, colour, selected, dim, onClick,
}: {
  r: number; colour: string; selected: boolean; dim: boolean;
  onClick: (e: ThreeEvent<MouseEvent>) => void;
}) {
  const shadow = useMemo(() => {
    const g = new THREE.RingGeometry(0, r, 44, 6);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position as THREE.BufferAttribute;
    const col = new Float32Array(p.count * 4);
    for (let i = 0; i < p.count; i++) {
      const d = Math.hypot(p.getX(i), p.getZ(i)) / r;
      col[i * 4] = 0.02;
      col[i * 4 + 1] = 0.07;
      col[i * 4 + 2] = 0.04;
      col[i * 4 + 3] = 0.5 * Math.pow(1 - Math.min(1, d), 1.6);
    }
    g.setAttribute("color", new THREE.BufferAttribute(col, 4));
    return g;
  }, [r]);

  useEffect(() => () => shadow.dispose(), [shadow]);

  return (
    <group position={[0, NODE_Y * 0.5, 0]}>
      <mesh geometry={shadow} onClick={onClick}>
        <meshBasicMaterial vertexColors transparent depthWrite={false} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}
            raycast={() => null}>
        <ringGeometry args={[r - 0.13, r + 0.13, 44]} />
        <meshBasicMaterial
          color={colour}
          transparent
          opacity={selected ? 0.95 : dim ? 0.18 : 0.5}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function Marker({
  spot, max, selected, dim, colour, model, kit, onSelect,
}: {
  spot: Spot; max: number; selected: boolean; dim: boolean;
  colour: string; model: boolean; kit: Kit | null;
  onSelect: (n: string) => void;
}) {
  const x = toX(spot.y);
  const z = toZ(spot.x);
  const r = 1.5 + 2.4 * Math.sqrt(spot.passes / max);

  return (
    <group position={[x, 0, z]}>
      <Base
        r={r}
        colour={colour}
        selected={selected}
        dim={dim}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          onSelect(selected ? "" : spot.name);
        }}
      />
      <Player
        model={model}
        kit={kit}
        colour={selected ? "#dff3ff" : dim ? "#4a6478" : "#eef4f8"}
      />
      <Html
        center
        position={[0, 2.7, 0]}
        distanceFactor={32}
        zIndexRange={[20, 0]}
      >
        <div
          className="select-none whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold text-white"
          style={{
            background: "rgba(7,17,25,0.86)",
            borderBottom: `2px solid ${colour}`,
            opacity: dim ? 0.45 : 1,
          }}
        >
          {spot.name.split(" ").slice(-1)[0]}
        </div>
      </Html>
    </group>
  );
}

/* ------------------------------------------------------------------ scene */

export function Formation3D({
  spots, edges, field, selected, model = false, kit = null, onSelect,
}: {
  spots: Spot[];
  edges: Edge[];
  /** the selected player's territory, or null when nobody is chosen */
  field: Field | null;
  selected: string;
  /** whether public/models/player.glb is actually there — checked once by
   *  the view, so a missing asset never reaches the loader */
  model?: boolean;
  /** the club colours to repaint the kit in, or null for the stock one */
  kit?: Kit | null;
  onSelect: (name: string) => void;
}) {
  const byName = useMemo(
    () => new Map(spots.map((s) => [s.name, s])),
    [spots],
  );
  const maxPass = Math.max(1, ...spots.map((s) => s.passes));
  const maxEdge = Math.max(1, ...edges.map((e) => e.n));

  return (
    <group>
      {field && <Territory field={field} colour="#5cc8ff" />}

      {edges.map((e) => {
        const a = byName.get(e.a);
        const b = byName.get(e.b);
        if (!a || !b) return null;
        const mine = !selected || e.a === selected || e.b === selected;
        return (
          <Lane
            key={`${e.a}>${e.b}`}
            from={a}
            to={b}
            n={e.n}
            max={maxEdge}
            dim={!mine}
          />
        );
      })}

      {spots.map((s) => (
        <Marker
          key={s.name}
          spot={s}
          max={maxPass}
          selected={s.name === selected}
          dim={!!selected && s.name !== selected}
          colour={s.name === selected ? "#5cc8ff" : "#9fd3ee"}
          model={model}
          kit={kit}
          onSelect={onSelect}
        />
      ))}
    </group>
  );
}
