"use client";

import { useMemo, useState } from "react";

import { H, PITCH_GREEN, PitchLines, W, X, Y } from "./Pitch";

/** Every shot, where it was hit from.
 *
 *  The attacking end only, from the halfway line up. A full pitch spends half
 *  its height on a region that holds about four shots a season, and shrinks
 *  the part anyone is reading to nothing. Shots from deeper than halfway are
 *  counted in the caption rather than drawn, because moving one onto the edge
 *  to keep it visible would be drawing something that did not happen.
 *
 *  PENALTIES ARE LEFT OUT, the same as everywhere else on the site. Twenty of
 *  them stacked on the spot is the loudest thing on the picture and says only
 *  that penalties are taken from the penalty spot.
 *
 *  Three states, because that is what the data honestly separates: scored,
 *  on target, off target. Big chances get a ring — Opta's judgement that the
 *  chance should have been scored, which is a different claim from where the
 *  ball was struck.
 */

export type Shot = {
  x: number;
  y: number;
  goal: boolean;
  target: boolean;
  big: boolean;
  setPiece: boolean;
  head: boolean;
  who: string;
};

/** The band drawn, in Opta x. A full pitch spends half its height on a region
 *  that holds about four shots a season and shrinks the part anyone is
 *  reading to nothing. */
const BAND = 50;

const GOAL = "#1a7f37";
const TARGET = "#e8b23a";
const OFF = "rgba(255,255,255,0.72)";

export function ShotMap({
  shots,
  title,
  subtitle,
  width = 250,
  faced = false,
}: {
  shots: Shot[];
  title?: string;
  subtitle?: string;
  /** The width it wants, not the width it takes: the map draws this big
   *  where there is room and shrinks to its column where there is not, so a
   *  phone gets the whole picture rather than the page sliding sideways. */
  width?: number;
  /** a map of shots FACED: no shooter to name, and green is bad news */
  faced?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);

  /** A shot FACED arrives already mirrored into this side's own frame, so it
   *  sits at LOW x — close to their own goal line — while a shot taken sits
   *  at high x. Drawn with one mapping, every faced map on the site came out
   *  empty: the dots were all in the half the picture cuts off.
   *
   *  So the defensive map is flipped. The goal being shot at is at the top in
   *  both pictures, which is also the only way the two are comparable: the
   *  right of one is the right of the other, and a side that shoots from the
   *  left and is got at down its own left shows that at a glance. */
  const toY = (x: number) => (faced ? Y(100 - x) : Y(x));
  const inBand = (x: number) => (faced ? x <= 100 - BAND : x >= BAND);

  // Ordered ONCE, misses first and goals last, so the index a dot carries is
  // the index the tooltip reads. Sorting at draw time and looking the shot
  // back up by identity would be a linear scan per dot, two thousand times.
  const { drawn, deep, goals } = useMemo(() => {
    const near = shots.filter((s) => inBand(s.x));
    const drawn = [...near].sort((a, b) => Number(a.goal) - Number(b.goal));
    return {
      drawn,
      deep: shots.length - near.length,
      goals: shots.filter((s) => s.goal).length,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shots, faced]);

  // the visible band of the pitch, in viewBox units
  const top = 0;
  const bot = Y(BAND);
  const h = Math.round((width * bot) / W);

  return (
    <figure className="m-0 min-w-0">
      {title && (
        <figcaption className="mb-1.5 text-[13px] font-medium text-ink">
          {title}
          {subtitle && (
            <span className="ml-1.5 font-normal text-ink-3">{subtitle}</span>
          )}
        </figcaption>
      )}
      <div className="relative w-full" style={{ maxWidth: width }}>
        <svg
          width={width}
          height={h}
          viewBox={`0 ${top} ${W} ${bot}`}
          role="img"
          aria-label={title ?? "shot map"}
          style={{
            background: PITCH_GREEN,
            borderRadius: 8,
            display: "block",
            width: "100%",
            height: "auto",
          }}
        >
          <PitchLines from={BAND} />
          {/* misses underneath, goals last: the picture should read
              goals-first rather than hide them under a cloud of misses */}
          {drawn.map((s, i) => (
            <g key={i}>
              {s.big && (
                <circle
                  cx={X(s.y)}
                  cy={toY(s.x)}
                  r={2.5}
                  fill="none"
                  stroke="rgba(255,255,255,0.85)"
                  strokeWidth={0.4}
                />
              )}
              <circle
                cx={X(s.y)}
                cy={toY(s.x)}
                r={s.goal ? 1.6 : 1.1}
                fill={s.goal ? GOAL : s.target ? TARGET : "none"}
                stroke={s.goal ? "rgba(255,255,255,0.9)" : s.target ? "none" : OFF}
                strokeWidth={s.goal ? 0.4 : 0.35}
                opacity={s.goal ? 1 : 0.85}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover((k) => (k === i ? null : k))}
                style={{ cursor: "help" }}
              />
            </g>
          ))}
        </svg>

        {hover !== null && drawn[hover] && (() => {
          const s = drawn[hover];
          // Per cent of the box, not pixels: the map scales to its column, so
          // a pixel offset computed from the width we ASKED for lands beside
          // the dot on any screen that gave us less.
          const cx = (X(s.y) / W) * 100;
          const cy = ((toY(s.x) - top) / bot) * 100;
          const above = cy > 50;
          const what = s.goal ? "Goal" : s.target ? "Saved" : "Off target";
          const how = [
            s.head ? "header" : null,
            s.setPiece ? "from a set piece" : null,
            s.big ? "big chance" : null,
          ]
            .filter(Boolean)
            .join(", ");
          return (
            <span
              role="tooltip"
              className="pointer-events-none absolute z-30 w-44 rounded-lg border border-line bg-card p-2 text-left text-[11.5px] leading-relaxed text-ink-2 shadow-lg"
              style={{
                left: `clamp(4px, calc(${cx}% - 88px), calc(100% - 180px))`,
                top: above ? undefined : `calc(${cy}% + 12px)`,
                bottom: above ? `calc(${100 - cy}% + 12px)` : undefined,
              }}
            >
              <b className="block text-ink">
                {s.who || (faced ? "Shot faced" : "Shot")}
              </b>
              {what}
              {how && ` · ${how}`}
            </span>
          );
        })()}
      </div>

      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">
        <span className="num">{drawn.length}</span> shots,{" "}
        <span className="num">{goals}</span> scored
        {deep > 0 && (
          <>
            {" "}
            · <span className="num">{deep}</span> from outside this half, not
            drawn
          </>
        )}
        . Penalties excluded.
      </p>
    </figure>
  );
}

export function ShotLegend() {
  const dot = (fill: string, stroke: string) => (
    <svg width="11" height="11" viewBox="0 0 11 11" aria-hidden>
      <circle cx="5.5" cy="5.5" r="3.4" fill={fill} stroke={stroke} strokeWidth="1" />
    </svg>
  );
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-3">
      <span className="flex items-center gap-1">
        {dot(GOAL, "rgba(0,0,0,0.25)")} goal
      </span>
      <span className="flex items-center gap-1">
        {dot(TARGET, "rgba(0,0,0,0.15)")} on target
      </span>
      <span className="flex items-center gap-1">
        {dot("none", "#9aa3ab")} off target
      </span>
      <span className="flex items-center gap-1">
        <svg width="13" height="13" viewBox="0 0 13 13" aria-hidden>
          <circle cx="6.5" cy="6.5" r="5.4" fill="none" stroke="#9aa3ab" strokeWidth="1" />
          <circle cx="6.5" cy="6.5" r="2.4" fill="#9aa3ab" />
        </svg>
        big chance
      </span>
    </div>
  );
}
