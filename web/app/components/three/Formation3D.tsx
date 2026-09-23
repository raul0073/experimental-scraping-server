"use client";

import dynamic from "next/dynamic";

import type { Edge, Field, Kit, Spot } from "./formation";

/** THE ELEVEN ON THE PITCH — the door, not the room.
 *
 *  The scene itself is in `Formation3DMesh.tsx`. This file exists so that
 *  importing `Formation3D` does not import three.
 *
 *  That distinction is the whole reason the versus page can open on a phone
 *  without fetching a renderer. `SideXI` and `ZoneView` both name this module
 *  at the top of their files, and a static import is a static import: the
 *  bundler puts three in the page's first chunk whether or not the scene is
 *  ever rendered. Creating the ELEMENT `<Formation3D … />` costs nothing —
 *  it is an object — and `PitchScene` only ever renders it inside the canvas,
 *  so on a small screen showing the flat map the mesh is never asked for and
 *  never fetched.
 *
 *  Suspending here is safe and is handled: `PitchCanvas` wraps the pitch and
 *  its children in a Suspense boundary, and the loading placeholder stays up
 *  until the first frame actually draws — which is now the first frame after
 *  this chunk lands, rather than before it.
 *
 *  THE PROPS AND THE TYPES ARE UNCHANGED. Every export this module had, it
 *  still has.
 */

export {
  MODEL, REGIONS, type Edge, type Field, type Kit, type Spot,
} from "./formation";

const Mesh = dynamic(() => import("./Formation3DMesh"), {
  ssr: false,
  // A DOM node here would be invalid inside a Canvas; nothing is the right
  // fallback, and the scene's own placeholder is what the reader sees.
  loading: () => null,
});

export function Formation3D(props: {
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
  return <Mesh {...props} />;
}
