"use client";

import { PITCH_GREEN, PitchLines, W, X, Y } from "../../Pitch";
import { BIT, classOf, type Pass } from "../passMath";

/** THE SAME PASSES, LYING DOWN.
 *
 *  Drawn on `Pitch.tsx`, the one pitch every flat map on the site uses, so
 *  the markings, the metre units and the left-wing-on-the-left flip are not
 *  written a second time here.
 *
 *  WHAT THE FLAT VIEW GIVES UP, and it is the one thing the 3D pass map was
 *  built for: HEIGHT. Opta records whether a pass left the ground, and in the
 *  scene a lofted ball arcs above its own shadow so a forty-metre diagonal
 *  over the top and a forty-metre ball along the floor are visibly different
 *  actions. Flat, there is no up. Rather than drop that fact, a lofted pass
 *  is drawn DASHED and a ground pass solid — a weaker encoding than an arc,
 *  and an honest one, because the distinction is still on the picture and
 *  still in the legend.
 *
 *  DIRECTION IS STILL IN THE LINE. The ribbon in the scene widens and
 *  brightens toward where the ball was aimed; here the stroke does the same
 *  with a gradient per class, so a pass map does not collapse into the
 *  undirected cobweb that started this project's pass work over.
 */

/** A season of passes is tens of thousands of line elements, and the DOM is
 *  not a renderer. The 3D view caps at 4,000 ribbons for the same reason; a
 *  phone gets a harder cap, and the caller is told so rather than being
 *  quietly shown a subset. */
export const FLAT_CAP = 1200;

export function FlatPasses({
  passes,
  selected,
  onSelect,
}: {
  passes: Pass[];
  selected: number;
  onSelect: (i: number) => void;
}) {
  const shown = passes.length > FLAT_CAP ? passes.slice(-FLAT_CAP) : passes;
  const offset = passes.length - shown.length;
  const sel = passes[selected];

  /** `sx`/`ex` are Opta x — along the pitch, 0 at their own goal line — and
   *  `sz`/`ez` are Opta y, across it. The names come from the scene's axes,
   *  which is why they read backwards here. `X` takes the across value and
   *  `Y` the along one; getting that pair the wrong way round is the mirror
   *  bug this codebase has already paid for twice. */
  const x1 = (p: Pass) => X(p.sz);
  const y1 = (p: Pass) => Y(p.sx);
  const x2 = (p: Pass) => X(p.ez);
  const y2 = (p: Pass) => Y(p.ex);

  const line = (p: Pass, i: number) => {
    const c = classOf(p.flags);
    const on = i === selected;
    return (
      <g key={i}>
        <line
          x1={x1(p)}
          y1={y1(p)}
          x2={x2(p)}
          y2={y2(p)}
          stroke={c.colour}
          strokeOpacity={on ? 1 : 0.5}
          strokeWidth={on ? 1.1 : 0.42}
          strokeLinecap="round"
          strokeDasharray={p.flags & BIT.air ? "1.6 1.1" : undefined}
        />
        {/* The end, so direction reads without an arrowhead on every one of
            twelve hundred lines. */}
        <circle
          cx={x2(p)}
          cy={y2(p)}
          r={on ? 1.1 : 0.55}
          fill={c.colour}
          fillOpacity={on ? 1 : 0.7}
        />
      </g>
    );
  };

  return (
    <svg
      viewBox={`0 0 ${W} ${Y(0)}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="pass map"
      className="block h-full w-full"
      style={{ background: PITCH_GREEN, touchAction: "manipulation" }}
    >
      <PitchLines />
      {shown.map((p, i) => line(p, i + offset))}

      {/* The selected pass again on top, so picking one out of a carpet
          actually pulls it clear of the carpet. */}
      {sel && line(sel, selected)}

      {/* A transparent grid of hit targets would be the tidy way to make
          hair-thin lines tappable; a line with a fat invisible stroke over it
          is the cheap one, and it is what a finger needs. */}
      {shown.map((p, i) => (
        <line
          key={`hit-${i}`}
          x1={x1(p)}
          y1={y1(p)}
          x2={x2(p)}
          y2={y2(p)}
          stroke="transparent"
          strokeWidth={2.4}
          strokeLinecap="round"
          onClick={() => onSelect(i + offset === selected ? -1 : i + offset)}
          style={{ cursor: "pointer" }}
        />
      ))}
    </svg>
  );
}
