"use client";

import { useThree } from "@react-three/fiber";
import { useMemo } from "react";
import * as THREE from "three";

/** REAL GRASS, GENERATED RATHER THAN DOWNLOADED.
 *
 *  A flat colour has no surface. Lit by a directional sun it returns the
 *  same value at every point, so the turf reads as paper and the shadows
 *  falling on it look pasted on rather than cast. The fix is not a prettier
 *  green — it is giving the material something for the light to catch.
 *
 *  Two fields, built once and shared:
 *
 *    patch  — low frequency. Mower wander, wear, where the water lands.
 *    blade  — short strokes lying mostly one way, with a faded tip each, so
 *             the high-frequency detail reads as grass rather than as noise.
 *
 *  From those come a colour map (brightness only, so the band's own colour
 *  still decides the hue) and a normal map (the one that does the work).
 *
 *  WHY NOT AN IMAGE FILE. A texture is a fetch, a fetch suspends, and a
 *  component that suspends inside a Canvas with no boundary above it takes
 *  the whole scene down — which is exactly how drei's <Text> turned this
 *  view into a black rectangle. A canvas drawn in memory cannot fail that
 *  way, adds nothing to a statically exported site, and tiles seamlessly
 *  because the blades are written with wrapped indices instead of hoping
 *  someone's photograph happens to.
 *
 *  ── THE STRIPES, AND TWO THINGS THAT LOOK RIGHT BUT DO NOTHING ──
 *
 *  Mowing stripes are not two shades of grass. They are the SAME grass bent
 *  in opposite directions, so one band returns the sun toward you and the
 *  next away. Reproducing that took two corrections, both measured rather
 *  than assumed (`scratchpad/turfcheck.mjs` renders the fields outside the
 *  browser and prints the brightness difference):
 *
 *  1. A ZERO-MEAN NORMAL MAP CANNOT MAKE A STRIPE. Rotating ordinary bump
 *     noise by 180° measured a 0.0% difference, because diffuse lighting is
 *     near-linear in the normal and the average of a symmetric perturbation
 *     is the same either way. The grass has to actually LEAN: `LIE` below is
 *     a constant tilt added to every normal, along the mower's direction of
 *     travel. With it the two bands measure ~14% apart.
 *  2. `texture.rotation` DOES NOT ROTATE THE NORMAL. It changes where the
 *     shader samples, not what the sampled vector means, so the lean would
 *     have pointed the same way in every band. Negating `normalScale` is
 *     what mirrors the perturbation, and the two together are a genuine
 *     180° turn of the surface.
 *
 *  The difference is diffuse, so it is fixed by where the sun is rather than
 *  where you are standing — same as a photograph of a real pitch.
 */

/** THE TILE HAS TO BE BIG, AND THE COLOUR MAP HAS TO BE BORING.
 *
 *  The first version was 512 pixels over 5 metres, which is fourteen repeats
 *  across the width of a pitch — and it carried the low-frequency patchiness
 *  in the COLOUR map, where every repeat showed as the same blotch in the
 *  same place. From any height it read as a grid, which is worse than the
 *  flat green it replaced.
 *
 *  Two changes fix it. A 9m tile at 1024 keeps roughly a centimetre per
 *  texel while cutting the repeat to seven, and the patchiness comes almost
 *  entirely out of the colour. What is left is fine blade grain, which has
 *  no feature large enough for the eye to match up between tiles.
 *
 *  Real grass over eighteen metres IS nearly uniform in colour. The texture
 *  people see in a photograph of a pitch is light on blades, not pigment —
 *  so it belongs in the normal map, and the colour map's job is only to stop
 *  the surface being mathematically flat.
 */
const RES = 1024;         // 1024 over a 9m tile is just under 1cm per texel
const TILE = 9;           // metres covered by one repeat
const BLADE_DENSITY = 2080;                          // per square metre
const BLADES = Math.round(BLADE_DENSITY * TILE * TILE);
const SLOPE = 2.4;        // how hard the blade detail bends the normal
const LIE = 0.24;         // the constant lean that makes a stripe possible

/** Negating x and y mirrors the normal perturbation — the flip that a
 *  texture rotation alone does not perform. */
const LIE_WITH = new THREE.Vector2(1, 1);
const LIE_AGAINST = new THREE.Vector2(-1, -1);

/* ------------------------------------------------------------ the pattern */

/** A small wrapped lattice of random values, bilinearly smoothed. Wrapped
 *  indices are what make the result tile with no seam. */
function lattice(n: number): Float32Array {
  const a = new Float32Array(n * n);
  for (let i = 0; i < a.length; i++) a[i] = Math.random();
  return a;
}

function sampleWrapped(a: Float32Array, n: number, u: number, v: number) {
  const x = u * n;
  const y = v * n;
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const at = (xx: number, yy: number) =>
    a[(((yy % n) + n) % n) * n + (((xx % n) + n) % n)];
  const s = (t: number) => t * t * (3 - 2 * t);
  const sx = s(x - x0);
  const sy = s(y - y0);
  const a0 = at(x0, y0) + (at(x0 + 1, y0) - at(x0, y0)) * sx;
  const a1 = at(x0, y0 + 1) + (at(x0 + 1, y0 + 1) - at(x0, y0 + 1)) * sx;
  return a0 + (a1 - a0) * sy;
}

function fields() {
  const patch = new Float32Array(RES * RES);
  const blade = new Float32Array(RES * RES);

  const coarse = lattice(4);
  const mid = lattice(9);
  const fine = lattice(24);
  for (let y = 0; y < RES; y++) {
    for (let x = 0; x < RES; x++) {
      const u = x / RES;
      const v = y / RES;
      patch[y * RES + x] =
        0.55 * sampleWrapped(coarse, 4, u, v) +
        0.30 * sampleWrapped(mid, 9, u, v) +
        0.15 * sampleWrapped(fine, 24, u, v);
    }
  }

  // Blades lie along texture +u, which is the pitch's WIDTH — the direction
  // a mower travels to leave bands stacked down the length. Written with
  // wrapped indices so a blade running off one edge continues on the other.
  for (let i = 0; i < BLADES; i++) {
    const bx = Math.random() * RES;
    const by = Math.random() * RES;
    const len = 2.5 + Math.random() * 5.0;
    const ang = (Math.random() - 0.5) * 1.5;
    const dx = Math.cos(ang);
    const dy = Math.sin(ang);
    const lift = 0.35 + Math.random() * 0.65;
    for (let s = 0; s < len; s++) {
      const px = (((Math.round(bx + dx * s) % RES) + RES) % RES);
      const py = (((Math.round(by + dy * s) % RES) + RES) % RES);
      // fading along the blade gives each one a tip, which is what reads as
      // grass rather than as static
      blade[py * RES + px] += lift * (1 - s / len);
    }
  }

  // Scale the blades by a high PERCENTILE, not by the maximum. A handful of
  // pixels where several blades crossed would otherwise set the scale and
  // press everything else flat — which is precisely what made the first
  // attempt look like billiard cloth.
  const sample = Array.from(
    { length: 20000 },
    () => blade[(Math.random() * blade.length) | 0],
  ).sort((a, b) => a - b);
  const p = sample[(sample.length * 0.97) | 0] || 1;
  for (let i = 0; i < blade.length; i++) blade[i] = Math.min(1, blade[i] / p);

  let lo = Infinity;
  let hi = -Infinity;
  for (let i = 0; i < patch.length; i++) {
    if (patch[i] < lo) lo = patch[i];
    if (patch[i] > hi) hi = patch[i];
  }
  const span = hi - lo || 1;
  for (let i = 0; i < patch.length; i++) patch[i] = (patch[i] - lo) / span;

  return { patch, blade };
}

/* ------------------------------------------------------------- the source */

type Turf = { map: THREE.Texture; normal: THREE.Texture };
let SOURCE: Turf | undefined;

function source(): Turf | null {
  if (SOURCE) return SOURCE;
  if (typeof document === "undefined") return null;   // never cache an SSR miss

  const { patch, blade } = fields();

  // Colour: brightness only, mean around 0.79. An 8-bit map can ONLY darken
  // what it multiplies, which is why the band colours in Pitch3D are pitched
  // brighter than the flat greens they replaced.
  const cm = document.createElement("canvas");
  cm.width = cm.height = RES;
  const gm = cm.getContext("2d");
  if (!gm) return null;
  const colour = gm.createImageData(RES, RES);
  for (let i = 0; i < RES * RES; i++) {
    // patch is all but absent here — it is the only thing coarse enough to
    // give the tiling away, and it does its real work on the normals
    const v = 0.62 + patch[i] * 0.05 + blade[i] * 0.30;
    colour.data[i * 4] = Math.min(255, v * 243);
    colour.data[i * 4 + 1] = Math.min(255, v * 255);
    colour.data[i * 4 + 2] = Math.min(255, v * 234);
    colour.data[i * 4 + 3] = 255;
  }
  gm.putImageData(colour, 0, 0);

  // Normal: central differences on blade detail over a little of the patch
  // noise, wrapped so the normals tile as cleanly as the colour does, plus
  // the constant lean along +u that the stripe depends on.
  const cn = document.createElement("canvas");
  cn.width = cn.height = RES;
  const gn = cn.getContext("2d");
  if (!gn) return null;
  const h = new Float32Array(RES * RES);
  for (let i = 0; i < h.length; i++) h[i] = blade[i] + patch[i] * 0.10;
  const at = (x: number, y: number) =>
    h[(((y % RES) + RES) % RES) * RES + (((x % RES) + RES) % RES)];
  const norm = gn.createImageData(RES, RES);
  for (let y = 0; y < RES; y++) {
    for (let x = 0; x < RES; x++) {
      const nx = -(at(x + 1, y) - at(x - 1, y)) * SLOPE - LIE;
      const ny = -(at(x, y + 1) - at(x, y - 1)) * SLOPE;
      const len = Math.hypot(nx, ny, 1);
      const i = (y * RES + x) * 4;
      norm.data[i] = ((nx / len) * 0.5 + 0.5) * 255;
      norm.data[i + 1] = ((ny / len) * 0.5 + 0.5) * 255;
      norm.data[i + 2] = ((1 / len) * 0.5 + 0.5) * 255;
      norm.data[i + 3] = 255;
    }
  }
  gn.putImageData(norm, 0, 0);

  const map = new THREE.CanvasTexture(cm);
  map.colorSpace = THREE.SRGBColorSpace;
  map.wrapS = map.wrapT = THREE.RepeatWrapping;

  // A normal map is data, not colour — leaving it in sRGB would bend every
  // normal toward vertical and quietly flatten the surface again.
  const normal = new THREE.CanvasTexture(cn);
  normal.wrapS = normal.wrapT = THREE.RepeatWrapping;

  SOURCE = { map, normal };
  return SOURCE;
}

/** Per-mesh view of the shared turf: same pixels, its own offset so the
 *  pattern runs continuously from one band into the next rather than
 *  restarting at every stripe.
 *
 *  Clones share the underlying `Source`, so twenty of these are twenty small
 *  objects and ONE texture on the GPU. For the same reason they are never
 *  disposed — the source belongs to the module, not to any one mesh.
 */
function tiled(
  src: THREE.Texture,
  x: number, z: number, w: number, d: number,
  tile: number, flip: boolean, aniso: number,
) {
  const t = src.clone();
  t.repeat.set(w / tile, d / tile);
  t.offset.set((x - w / 2) / tile, (z - d / 2) / tile);
  if (flip) {
    t.center.set(0.5, 0.5);
    t.rotation = Math.PI;
  }
  // grass is only ever seen at a grazing angle, which is the case trilinear
  // filtering handles worst
  t.anisotropy = aniso;
  return t;
}

/* ------------------------------------------------------------------- mesh */

/** A flat piece of turf. Everything green in the scene is one of these: the
 *  mowing bands, the run-off round the pitch, the ground beyond it. */
export function TurfMesh({
  x = 0, y = 0, z = 0, w, d, colour, flip = false, tile = TILE,
  shadow = true,
}: {
  x?: number; y?: number; z?: number;
  w: number; d: number;
  colour: string;
  /** the next stripe over: the same grass turned 180°, which takes both a
   *  rotated lookup and a mirrored normal */
  flip?: boolean;
  tile?: number;
  /** receive shadows. Off for ground that extends well beyond the shadow
   *  camera's frustum: past its edge the lookup clamps to the border texel
   *  and paints long dark streaks across the distance. */
  shadow?: boolean;
}) {
  const aniso = useThree((s) => s.gl.capabilities.getMaxAnisotropy());
  const maps = useMemo(() => {
    const src = source();
    if (!src) return null;
    return {
      map: tiled(src.map, x, z, w, d, tile, flip, aniso),
      normal: tiled(src.normal, x, z, w, d, tile, flip, aniso),
    };
  }, [x, z, w, d, tile, flip, aniso]);

  return (
    <mesh position={[x, y, z]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow={shadow}>
      <planeGeometry args={[w, d]} />
      <meshStandardMaterial
        color={colour}
        map={maps?.map ?? null}
        normalMap={maps?.normal ?? null}
        normalScale={flip ? LIE_AGAINST : LIE_WITH}
        // enough sheen that the sun sits on the grass rather than soaking
        // straight into it, without turning the pitch plastic
        roughness={0.86}
      />
    </mesh>
  );
}
