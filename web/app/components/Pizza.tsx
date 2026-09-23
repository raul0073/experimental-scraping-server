"use client";

import { useState } from "react";

/** The pizza chart: one wedge per metric, length is the percentile.
 *
 *  Every wedge is the SAME WIDTH and every one is a percentile, because the
 *  chart's whole job is that a reader can compare two slices by eye. Sizing a
 *  wedge by its weight in the score as well would put two variables into one
 *  shape, and nobody can read area and radius apart.
 *
 *  HIGHER IS ALWAYS BETTER, which for shots conceded means the value was
 *  flipped upstream. A chart where long is good in one wedge and bad in the
 *  next is a chart that has to be read wedge by wedge, which is a table.
 *
 *  Colour is the phase — with the ball, against it, set pieces — so the
 *  picture separates a side that creates from one that stops you creating
 *  before any number is read.
 *
 *  THE NUMBER IS ON EVERY WEDGE, not only the hovered one. A chart you have
 *  to interrogate a slice at a time to read has failed at being a chart.
 */

export type Slice = {
  key: string;
  label: string;
  phase: string;
  v: number;
  /** what this metric carries of the hundred points in the score */
  weight?: number;
  desc?: string;
};

const PHASE: Record<string, { fill: string; label: string }> = {
  with: { fill: "#2f6f4f", label: "With the ball" },
  against: { fill: "#1c5b8a", label: "Against the ball" },
  set: { fill: "#8a6d1c", label: "Set pieces" },
};
const FALLBACK = { fill: "#6b7280", label: "Other" };

const TAU = Math.PI * 2;

// Geometry in viewBox units. The ring is 100 across; everything else is the
// room the LABELS need, which is most of the picture.
//
// The padding is EQUAL in both directions and MEASURED from the longest
// label, not guessed. A label is rotated to point outward from its wedge, so
// the one at twelve o'clock runs straight up and needs its whole length as
// VERTICAL room. Padding the sides generously and the top by half as much
// looked right for the labels at 3 and 9 and cut "Set-piece shots" and
// "Reaches the box" in half at the top of the box. A wedge can sit at any
// angle, so the room it needs is the same in every direction.
const R = 100;
const R0 = 24;
const LABEL_R = R + 17;       // where a label starts, measured from centre
const CHAR_W = 5.6;           // ≈ advance width at fontSize 10, weight 600
const LINE = 11;              // label line height

/** Wrap to at most two lines of roughly this many characters. Long metric
 *  names are the norm here — "Set-piece chances conceded" is four words and
 *  no amount of margin makes it fit on one line at a readable size. */
function wrap(text: string, max = 15): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    if (!cur) cur = w;
    else if (cur.length + 1 + w.length <= max) cur += ` ${w}`;
    else {
      lines.push(cur);
      cur = w;
    }
  }
  if (cur) lines.push(cur);
  if (lines.length <= 2) return lines;
  return [lines[0], lines.slice(1).join(" ")];
}

export function Pizza({
  slices,
  size = 560,
  label,
}: {
  slices: Slice[];
  size?: number;
  label?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = slices.length;
  if (!n) return null;

  const wrapped = slices.map((s) => wrap(s.label));
  const longest = Math.max(...wrapped.map((ls) => Math.max(...ls.map((l) => l.length))));
  const PAD = Math.ceil(LABEL_R - R + longest * CHAR_W + 6);
  const VB = (R + PAD) * 2;
  const CX = VB / 2;
  const CY = VB / 2;

  const point = (a: number, rr: number): [number, number] => [
    CX + Math.cos(a) * rr,
    CY + Math.sin(a) * rr,
  ];
  // start at twelve o'clock and run clockwise, with a hairline gap
  const a0 = (i: number) => (i / n) * TAU - Math.PI / 2 + 0.012;
  const a1 = (i: number) => ((i + 1) / n) * TAU - Math.PI / 2 - 0.012;
  const mid = (i: number) => (i / n) * TAU + TAU / (2 * n) - Math.PI / 2;
  const radius = (v: number) =>
    R0 + ((R - R0) * Math.max(0, Math.min(100, v))) / 100;

  const arc = (i: number, r: number) => {
    const [x0, y0] = point(a0(i), R0);
    const [x1, y1] = point(a1(i), R0);
    const [x2, y2] = point(a1(i), r);
    const [x3, y3] = point(a0(i), r);
    const big = a1(i) - a0(i) > Math.PI ? 1 : 0;
    return `M ${x0} ${y0} A ${R0} ${R0} 0 ${big} 1 ${x1} ${y1} L ${x2} ${y2} A ${r} ${r} 0 ${big} 0 ${x3} ${y3} Z`;
  };

  return (
    <figure className="m-0">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${VB} ${VB}`}
        role="img"
        aria-label={label ?? "metric percentiles"}
        style={{ display: "block", maxWidth: "100%" }}
      >
        {/* the 25 / 50 / 75 rings, so a wedge reads without counting */}
        {[25, 50, 75, 100].map((t) => (
          <circle
            key={t}
            cx={CX}
            cy={CY}
            r={R0 + ((R - R0) * t) / 100}
            fill="none"
            stroke={t === 50 ? "#cfd5da" : "#e8ebee"}
            strokeWidth={t === 50 ? 1.1 : 0.9}
            strokeDasharray={t === 50 ? undefined : "3 3"}
          />
        ))}

        {slices.map((s, i) => {
          const ph = PHASE[s.phase] ?? FALLBACK;
          return (
            <path
              key={s.key}
              d={arc(i, radius(s.v))}
              fill={ph.fill}
              opacity={hover === null || hover === i ? 0.9 : 0.28}
              stroke="#ffffff"
              strokeWidth="0.9"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((k) => (k === i ? null : k))}
              style={{ cursor: "help" }}
            />
          );
        })}

        {/* the value, at the end of its own wedge */}
        {slices.map((s, i) => {
          const ph = PHASE[s.phase] ?? FALLBACK;
          const [x, y] = point(mid(i), radius(s.v));
          const on = hover === null || hover === i;
          return (
            <g key={`v-${s.key}`} pointerEvents="none" opacity={on ? 1 : 0.3}>
              <circle
                cx={x}
                cy={y}
                r={8.4}
                fill={ph.fill}
                stroke="#ffffff"
                strokeWidth="1.4"
              />
              <text
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="central"
                className="num"
                fontSize="8.2"
                fontWeight="700"
                fill="#ffffff"
              >
                {s.v.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* labels outside the ring, rotated to stay upright on the left */}
        {slices.map((s, i) => {
          const a = mid(i);
          const [x, y] = point(a, LABEL_R);
          const deg = (a * 180) / Math.PI;
          const flip = deg > 90 || deg < -90;
          const lines = wrapped[i];
          const dy0 = -((lines.length - 1) * LINE) / 2;
          return (
            <text
              key={s.key}
              x={x}
              y={y}
              textAnchor={flip ? "end" : "start"}
              fontSize="10"
              fontWeight={hover === i ? 700 : 600}
              fill={hover === i ? "#1f2937" : "#5c656e"}
              transform={`rotate(${flip ? deg + 180 : deg} ${x} ${y})`}
              pointerEvents="none"
            >
              {lines.map((ln, j) => (
                <tspan
                  key={j}
                  x={x}
                  dy={j === 0 ? dy0 : LINE}
                  dominantBaseline="central"
                >
                  {ln}
                </tspan>
              ))}
            </text>
          );
        })}
      </svg>

      {/* Fixed height, so hovering does not shove the page down two lines
          every time the pointer crosses a wedge. */}
      <p
        className="mt-1 text-[12.5px] leading-relaxed text-ink-2"
        style={{ minHeight: "3.2em", maxWidth: size }}
      >
        {hover !== null ? (
          <>
            <b className="text-ink">{slices[hover].label}</b>{" "}
            <span className="num text-ink-3">
              {slices[hover].v.toFixed(0)} of 100
              {slices[hover].weight !== undefined && (
                <> · worth {slices[hover].weight} of the score</>
              )}
            </span>
            {slices[hover].desc && <> — {slices[hover].desc}</>}
          </>
        ) : (
          <span className="text-ink-3">Hover a wedge for what it measures.</span>
        )}
      </p>
    </figure>
  );
}

export function PizzaLegend({ phases }: { phases: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-ink-3">
      {phases.map((p) => {
        const ph = PHASE[p] ?? FALLBACK;
        return (
          <span key={p} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: ph.fill }}
            />
            {ph.label}
          </span>
        );
      })}
      <span className="ml-1">longer is better · 50 is the league median</span>
    </div>
  );
}
