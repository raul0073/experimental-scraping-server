/** WHAT AN ELEVEN IS, and where the model files live — WITHOUT three.
 *
 *  Lifted out of `Formation3D.tsx` unchanged. `useSquad` derives all of this
 *  from the pass payload and needs the types and the model path; importing
 *  the scene to get them meant that asking "who played" downloaded a WebGL
 *  renderer and a GLTF loader. `Formation3D` re-exports every name here.
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

export type Kit = { shirt: string; shorts: string; socks?: string };

/** The player model. The raw export from the asset library was 1.5 MB;
 *  `scripts/optimise-model.sh` reduces it to 761 KB and 14,959 triangles
 *  with 1024px WebP textures, which is indistinguishable at any distance
 *  this scene actually uses. The source is kept at data/models/ — OUTSIDE
 *  public/, or Next copies all 22 MB of it into the export. */
export const MODEL = "/models/player.glb";

/** Which texel is which garment, baked by scripts/build_kit_regions.py.
 *  R channel: 0 leave, 1 shirt, 2 shorts, 3 socks. */
export const REGIONS = "/models/player-regions.png";
