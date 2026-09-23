"use client";

import { H, PITCH_GREEN, PitchLines, W, X, Y } from "../../Pitch";
import { GOAL_W, RESULT_COLOUR, xgRadius, type Shot } from "../shotMath";

/** THE SAME SHOTS, LYING DOWN.
 *
 *  Not a second shot map. `app/components/ShotMap.tsx` already draws one, and
 *  this reuses the pitch it is drawn on — `Pitch.tsx`, the single definition
 *  of the markings, the metre units and the flip that keeps the left wing on
 *  the left. What it does NOT reuse is that component's own dot layer, and
 *  that is deliberate: it takes Opta rows, drops penalties, drops anything
 *  from beyond the halfway line, and collapses five outcomes into three. Good
 *  choices for the team page it was built for, and the wrong ones here —
 *  a phone would then be shown a different set of shots, encoded differently,
 *  from the one a laptop is shown on the same page. So the marks are drawn
 *  from the same Understat rows, in the same colours, as the 3D cloud.
 *
 *  WHAT THE FLAT VIEW GIVES UP, honestly: the balls have no height, so there
 *  is no shadow and no sense of an object in space, and the shooter's-eye
 *  flight is not available. What it gives back at 340 pixels is that every
 *  attempt is the same size at the same xG wherever it sits on the grass,
 *  which foreshortening takes away, and that the whole attacking half is on
 *  screen at once.
 *
 *  AREA IS xG, so the radius goes as the SQUARE root here where the sphere in
 *  the 3D scene uses the cube root — a disc's area and a ball's volume are
 *  different quantities and the same number has to mean the same thing in
 *  both. A 0.40 chance covers four times the ground of a 0.10 one, which is
 *  exactly what the caption on the page claims.
 */

/** viewBox units are metres, so these are metres. */
const UNIT = 3.2;
const FLOOR = 0.75; // keeps a 0.02 chance big enough to tap

export function FlatShots({
  shots,
  selected,
  onSelect,
  /** how much of the pitch the 3D view is drawing, so the flat one frames
   *  the same grass rather than quietly showing more or less of it */
  portion = 0.75,
}: {
  shots: Shot[];
  selected: number;
  onSelect: (i: number) => void;
  portion?: number;
}) {
  /** WHERE THE PICTURE STARTS. The 3D scene draws `portion` of the pitch back
   *  from the attacking goal and anything behind that falls off the grass, so
   *  the flat map cuts at the same place. But a shot outside it is NOT
   *  dropped: the band opens up to hold it instead, because moving a mark to
   *  keep it visible, or leaving it out and printing a footnote, are both
   *  ways of not drawing something that happened. */
  const wanted = (1 - portion) * 100;
  const deepest = shots.reduce((lo, s) => Math.min(lo, s.x * 100), 100);
  const from = Math.max(0, Math.min(wanted, Math.floor(deepest) - 2));

  const top = Y(100);
  const bot = Y(from);

  /** Opta y is Understat y on the same footing — low is the attacking side's
   *  RIGHT in both feeds, see the note on `toX` in Pitch3D — so the one flip
   *  that keeps the left wing on the left is `X` and nothing else. */
  const cx = (s: Shot) => X(s.y * 100);
  const cy = (s: Shot) => Y(s.x * 100);

  /** Misses first and goals last, so the picture reads goals-first instead of
   *  burying them under a cloud of misses. The index each mark carries is its
   *  index in the ORIGINAL list, because that is the index the caller's
   *  selection, caption and side panel are all keyed by. */
  const order = shots
    .map((s, i) => i)
    .sort((a, b) =>
      Number(shots[a].result === "Goal") - Number(shots[b].result === "Goal"),
    );

  const sel = shots[selected];

  return (
    <svg
      viewBox={`0 ${top} ${W} ${bot - top}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="shot map"
      className="block h-full w-full"
      style={{ background: PITCH_GREEN, touchAction: "manipulation" }}
    >
      <PitchLines from={from} />

      {/* The goal itself, so "the angle he had" has something to open onto. */}
      <rect
        x={(W - GOAL_W) / 2}
        y={-0.5}
        width={GOAL_W}
        height={0.9}
        fill="rgba(255,255,255,0.9)"
      />

      {/* THE ANGLE OF GOAL, which is most of what an xG model reads and the
          one thing the 3D view exists to show. Flat, it is a plain triangle
          to both posts — which is the true planar angle, not an impression
          of it, and it survives being 340 pixels wide. */}
      {sel && (
        <polygon
          points={[
            `${cx(sel)},${cy(sel)}`,
            `${(W - GOAL_W) / 2},0`,
            `${(W + GOAL_W) / 2},0`,
          ].join(" ")}
          fill={RESULT_COLOUR[sel.result] ?? "#ffd23f"}
          fillOpacity={0.22}
          stroke={RESULT_COLOUR[sel.result] ?? "#ffd23f"}
          strokeOpacity={0.5}
          strokeWidth={0.25}
          pointerEvents="none"
        />
      )}

      {order.map((i) => {
        const s = shots[i];
        const r = xgRadius(s.xg, UNIT, 0.5, FLOOR);
        const on = i === selected;
        return (
          <circle
            key={i}
            cx={cx(s)}
            cy={cy(s)}
            r={r}
            fill={RESULT_COLOUR[s.result] ?? "#94a3b8"}
            fillOpacity={on ? 0.95 : 0.72}
            stroke={on ? "#ffffff" : "rgba(255,255,255,0.55)"}
            strokeWidth={on ? 0.7 : 0.22}
            onClick={() => onSelect(on ? -1 : i)}
            style={{ cursor: "pointer" }}
          >
            {/* The native tooltip, because there is no room for a floating
                card and no hover on a phone at all. The caption under the
                map is what a tap is actually for. */}
            <title>
              {s.player} · {s.minute}&apos; · {s.xg.toFixed(2)} xG
            </title>
          </circle>
        );
      })}
    </svg>
  );
}
