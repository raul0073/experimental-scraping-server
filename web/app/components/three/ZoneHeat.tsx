"use client";

import dynamic from "next/dynamic";

import type { ZoneValues } from "./zones";

/** THE FIFTEEN ZONES AS HEAT ON THE GRASS — the door, not the room.
 *
 *  The tiles are in `ZoneHeatMesh.tsx`. This file exists so that importing
 *  `ZoneHeat` does not import three.
 *
 *  `ZonePitch` on the versus page names this module at the top of its file,
 *  and a static import puts three in that page's first chunk whether or not
 *  a scene is ever drawn. Here, creating the element costs nothing and
 *  `PitchScene` only renders it inside the canvas — so a phone that opens on
 *  the flat zone map never fetches the renderer at all.
 *
 *  The flat map, for the record, is `app/components/PitchZones.tsx`: same
 *  cells, same real channel widths, same colour ramp, same number printed on
 *  every tile. These tiles were built to match it, which is why there is a
 *  2D fallback here that nobody had to invent.
 *
 *  EVERY EXPORT THIS MODULE HAD, IT STILL HAS.
 */

export {
  CELLS, CHANNELS, THIRDS, cellAt, cellLabel, type ZoneValues,
} from "./zones";

const Mesh = dynamic(() => import("./ZoneHeatMesh"), {
  ssr: false,
  // A DOM node here would be invalid inside a Canvas; nothing is the right
  // fallback, and the scene's own placeholder covers the gap.
  loading: () => null,
});

export function ZoneHeat(props: {
  values: ZoneValues;
  lo: number;
  hi: number;
  curve?: "linear" | "sqrt";
  decimals?: number;
  selected: string;
  onSelect: (cell: string) => void;
}) {
  return <Mesh {...props} />;
}
