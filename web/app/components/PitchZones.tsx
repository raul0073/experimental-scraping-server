"use client";

import { useState } from "react";

/** The fifteen cells, drawn on a football pitch. VERTICALLY.
 *
 *  Attacking upwards: own goal at the bottom, the opponent's at the top,
 *  which is how every analyst draws a pitch and how anyone reading one
 *  expects to find it. The thirds therefore stack up the image and the five
 *  channels run across it.
 *
 *  The channels are drawn at their real widths rather than as five equal
 *  strips: the wings take the outer 21% each, the half-spaces about 16, the
 *  centre the middle 26. Seeing the half-spaces as narrower than the centre
 *  is half the reason to draw this rather than tabulate it.
 *
 *  Opta's y runs 0 at the RIGHT touchline to 100 at the LEFT, so the left
 *  wing lands on the left of the image only after a flip. Skip it and the
 *  map is mirrored, which nobody notices until a winger is on the wrong
 *  side of every picture on the site.
 *
 *  COLOUR IS A MEASURE, NOT VOLUME. Shading raw activity put the cell in
 *  front of the goalkeeper top of every against-map — true, and useless.
 *  What arrives here is already a measure: share of the ball against a
 *  typical side there, or shots conceded from there.
 *
 *  Green through yellow to red is the convention a football reader knows.
 *  It is a poor ramp for colour blindness, which is survivable only because
 *  every cell prints its number — the colour is a second reading of
 *  something already legible.
 */

const PITCH = "#3f8f4f";
const LINE = "rgba(255,255,255,0.75)";

/** Channel edges in Opta y (0 = right touchline). Listed left-to-right as
 *  the reader sees them, which is descending y. */
const CHANNELS = [
  { key: "LW", label: "Left wing", lo: 78.9, hi: 100 },
  { key: "LH", label: "Left half-space", lo: 63.2, hi: 78.9 },
  { key: "C", label: "Centre", lo: 36.8, hi: 63.2 },
  { key: "RH", label: "Right half-space", lo: 21.1, hi: 36.8 },
  { key: "RW", label: "Right wing", lo: 0, hi: 21.1 },
];
/** Thirds up the pitch, bottom to top. */
const THIRDS = [
  { key: "D", label: "Own third", lo: 0, hi: 33.3 },
  { key: "M", label: "Middle third", lo: 33.3, hi: 66.7 },
  { key: "A", label: "Attacking third", lo: 66.7, hi: 100 },
];

const RAMP: [number, number, number, number][] = [
  [0, 46, 125, 68],
  [0.3, 90, 180, 70],
  [0.5, 225, 215, 60],
  [0.72, 240, 150, 45],
  [1, 214, 45, 35],
];

function shade(v: number | undefined, lo: number, hi: number): string {
  if (v === undefined || Number.isNaN(v)) return "rgba(255,255,255,0.06)";
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
  for (let i = 1; i < RAMP.length; i++) {
    const [s1, r1, g1, b1] = RAMP[i];
    if (t <= s1) {
      const [s0, r0, g0, b0] = RAMP[i - 1];
      const k = s1 === s0 ? 0 : (t - s0) / (s1 - s0);
      return `rgba(${Math.round(r0 + (r1 - r0) * k)}, ${Math.round(
        g0 + (g1 - g0) * k,
      )}, ${Math.round(b0 + (b1 - b0) * k)}, 0.82)`;
    }
  }
  return "rgba(214,45,35,0.82)";
}

/** Pitch is 68 wide by 105 long in metres, and drawn that way round. */
const W = 68;
const H = 105;

export function PitchZones({
  values,
  title,
  subtitle,
  width = 250,
  lo = 0,
  hi = 100,
  decimals = 0,
  explain,
}: {
  /** what a cell's number MEANS, given its value and where it sits */
  explain?: (cell: string, v: number | undefined, where: string) => string;
  /** cell key ("ARW", "MC", …) -> value */
  values: Record<string, number | undefined>;
  title?: string;
  subtitle?: string;
  width?: number;
  lo?: number;
  hi?: number;
  decimals?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const height = Math.round((width * H) / W);
  const px = width / W;   // viewBox units to pixels
  // left wing on the left: Opta y descends across the image
  const X = (y: number) => ((100 - y) / 100) * W;
  // attacking upwards: own goal at the bottom of the image
  const Y = (x: number) => ((100 - x) / 100) * H;

  return (
    <figure className="m-0">
      {title && (
        <figcaption className="mb-1.5 text-[13px] font-medium text-ink">
          {title}
          {subtitle && (
            <span className="ml-1.5 font-normal text-ink-3">{subtitle}</span>
          )}
        </figcaption>
      )}
      <div className="relative" style={{ width }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={title ?? "zone map"}
        style={{ background: PITCH, borderRadius: 8, display: "block" }}
      >
        {THIRDS.map((t) =>
          CHANNELS.map((c) => {
            const key = `${t.key}${c.key}`;
            const v = values[key];
            const x = X(c.hi);
            const y = Y(t.hi);
            const w = X(c.lo) - X(c.hi);
            const h = Y(t.lo) - Y(t.hi);
            const where = `${t.label.toLowerCase()}, ${c.label.toLowerCase()}`;
            return (
              <g
                key={key}
                onMouseEnter={() => setHover(key)}
                onMouseLeave={() => setHover((k) => (k === key ? null : k))}
                style={{ cursor: explain ? "help" : "default" }}
              >
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill={shade(v, lo, hi)}
                  stroke={hover === key ? "#ffffff" : "none"}
                  strokeWidth={hover === key ? 0.6 : 0}
                />

                <text
                  x={x + w / 2}
                  y={y + h / 2}
                  textAnchor="middle"
                  dominantBaseline="central"
                  className="num"
                  fontSize="3.6"
                  fontWeight="700"
                  fill="#ffffff"
                  stroke="rgba(0,0,0,0.35)"
                  strokeWidth="0.6"
                  paintOrder="stroke"
                >
                  {v === undefined || Number.isNaN(v) ? "—" : v.toFixed(decimals)}
                </text>
              </g>
            );
          }),
        )}

        {/* the grid, so the channels are visible as channels */}
        <g
          stroke="rgba(255,255,255,0.35)"
          strokeWidth="0.25"
          strokeDasharray="1.4 1.4"
        >
          {CHANNELS.slice(1).map((c) => (
            <line key={c.key} x1={X(c.hi)} y1={0} x2={X(c.hi)} y2={H} />
          ))}
          {THIRDS.slice(1).map((t) => (
            <line key={t.key} x1={0} y1={Y(t.lo)} x2={W} y2={Y(t.lo)} />
          ))}
        </g>

        {/* the pitch itself, drawn the long way up */}
        <g fill="none" stroke={LINE} strokeWidth="0.4">
          <rect x="0.4" y="0.4" width={W - 0.8} height={H - 0.8} />
          <line x1="0.4" y1={H / 2} x2={W - 0.4} y2={H / 2} />
          <circle cx={W / 2} cy={H / 2} r="9.15" />
          {/* penalty areas */}
          <rect x={(W - 40.3) / 2} y={H - 16.5} width="40.3" height="16.1" />
          <rect x={(W - 40.3) / 2} y="0.4" width="40.3" height="16.1" />
          {/* six-yard boxes */}
          <rect x={(W - 18.3) / 2} y={H - 5.5} width="18.3" height="5.1" />
          <rect x={(W - 18.3) / 2} y="0.4" width="18.3" height="5.1" />
          {/* the D at each end */}
          <path d={`M ${W / 2 - 7.3} ${H - 16.5} A 9.15 9.15 0 0 1 ${W / 2 + 7.3} ${H - 16.5}`} />
          <path d={`M ${W / 2 - 7.3} 16.5 A 9.15 9.15 0 0 0 ${W / 2 + 7.3} 16.5`} />
        </g>
      </svg>
      {/* Hover, not click, and styled like every other explanation on the
          site: a small card rather than a block of text shoved under the
          picture. Positioned over the cell it belongs to and pointer-events
          off, so it never eats the next hover. */}
      {explain && hover && (() => {
        const t = THIRDS.find((z) => hover.startsWith(z.key));
        const c = CHANNELS.find((z) => hover.slice(1) === z.key);
        if (!t || !c) return null;
        const cx = ((100 - (c.lo + c.hi) / 2) / 100) * W * px;
        const cy = ((100 - (t.lo + t.hi) / 2) / 100) * H * px;
        const left = Math.max(4, Math.min(width - 224, cx - 110));
        const above = cy > height / 2;
        return (
          <span
            role="tooltip"
            className="pointer-events-none absolute z-30 w-56 rounded-lg border border-line bg-card p-2.5 text-left text-[11.5px] font-normal leading-relaxed text-ink-2 shadow-lg"
            style={{
              left,
              top: above ? undefined : cy + 14,
              bottom: above ? height - cy + 14 : undefined,
            }}
          >
            <b className="block text-ink">
              {t.label}, {c.label.toLowerCase()}
            </b>
            {explain(hover, values[hover], `${t.label.toLowerCase()}, ${c.label.toLowerCase()}`)}
          </span>
        );
      })()}
      </div>
      <div className="mt-1 flex justify-center text-[10px] uppercase tracking-wider text-ink-3">
        <span aria-hidden>attacking ↑</span>
      </div>
    </figure>
  );
}

export function ZoneLegend({ label }: { label: string }) {
  const stops = [0, 0.25, 0.5, 0.75, 1].map((t) => shade(t * 100, 0, 100));
  return (
    <div className="flex items-center gap-2 text-[11px] text-ink-3">
      <span>less</span>
      <span
        className="h-2.5 w-28 rounded-full"
        style={{ background: `linear-gradient(to right, ${stops.join(", ")})` }}
      />
      <span>more</span>
      <span className="ml-1">{label}</span>
    </div>
  );
}
