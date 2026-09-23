/** The fifteen cells, and where they are — WITHOUT three.
 *
 *  Lifted out of `ZoneHeat.tsx` unchanged. The flat zone map needs the cell
 *  keys and their labels; importing the tile renderer to get them pulls in
 *  WebGL. `ZoneHeat` re-exports everything here.
 *
 *  Channels are drawn at their REAL widths, not as five equal strips: the
 *  wings take the outer 21% each, the half-spaces about 16, the centre the
 *  middle 26. Seeing the half-spaces as narrower than the centre is half
 *  the reason to draw this rather than tabulate it.
 */

import { PITCH_L, PITCH_W } from "./dims";

/** Channel edges in Opta y. 0 is the attacking side's RIGHT touchline —
 *  see `toX` in Pitch3D, which is the only place that conversion happens. */
export const CHANNELS = [
  { key: "RW", label: "right wing", lo: 0, hi: 21.1 },
  { key: "RH", label: "right half-space", lo: 21.1, hi: 36.8 },
  { key: "C", label: "centre", lo: 36.8, hi: 63.2 },
  { key: "LH", label: "left half-space", lo: 63.2, hi: 78.9 },
  { key: "LW", label: "left wing", lo: 78.9, hi: 100 },
];
export const THIRDS = [
  { key: "D", label: "defensive third", lo: 0, hi: 33.3 },
  { key: "M", label: "middle third", lo: 33.3, hi: 66.7 },
  { key: "A", label: "attacking third", lo: 66.7, hi: 100 },
];

export const CELLS = THIRDS.flatMap((t) => CHANNELS.map((c) => t.key + c.key));

export const cellLabel = (cell: string) => {
  const t = THIRDS.find((x) => cell.startsWith(x.key));
  const c = CHANNELS.find((x) => x.key === cell.slice(1));
  return t && c ? `${c.label}, ${t.label}` : cell;
};

/** Where a point on the grass falls, back in Opta terms. The inverse of
 *  `toX` / `toZ`, and the only other place that conversion is allowed. */
export function cellAt(x: number, z: number): string | null {
  const optaY = ((x + PITCH_W / 2) / PITCH_W) * 100;
  const optaX = ((z + PITCH_L / 2) / PITCH_L) * 100;
  const c = CHANNELS.find((v) => optaY >= v.lo && optaY <= v.hi);
  const t = THIRDS.find((v) => optaX >= v.lo && optaX <= v.hi);
  return c && t ? t.key + c.key : null;
}

export type ZoneValues = Record<string, number | undefined>;
