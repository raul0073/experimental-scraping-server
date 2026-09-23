"use client";

import { useMemo, useState } from "react";

import { H, PITCH_GREEN, PitchLines, W, X, Y } from "./Pitch";

/** Average positions, with the passes between them.
 *
 *  These are one picture, not two. A chart of average positions and a passing
 *  map are the same nodes; the second just draws the lines. Splitting them
 *  into two tabs would ask the reader to hold one in their head while looking
 *  at the other.
 *
 *  A NODE is where a player had the ball, averaged over every controlled
 *  action — a pass, a take-on, a shot, a touch. Not every event he appears
 *  in: a centre-back who makes four tackles on the edge of his own box and
 *  ninety passes from the halfway line belongs at the halfway line, and
 *  averaging the tackles in drags him twenty metres the wrong way.
 *
 *  A LINK is a completed pass from one to the other, and the receiver is
 *  INFERRED — Opta records who played the pass and never who got it, so the
 *  receiver is taken as the next event by the same side. For a completed
 *  pass that is nearly always right and the page prints how often it
 *  resolved, but it is an inference and the caption says so. A line here is
 *  a good guess drawn thick, not a fact.
 *
 *  Averaged over a whole period, not one match, so this is a habit rather
 *  than an afternoon — and a player who changed position mid-season sits
 *  between the two jobs he did, which is honest but worth knowing.
 */

/** n: name, x/y: mean position in Opta terms, t: actions on the ball,
 *  a: matches he appeared in. */
export type Node = { n: string; x: number; y: number; t: number; a?: number };
export type Link = { a: string; b: string; n: number };

/** "Bukayo Saka" -> "Saka", "Gabriel Dos Santos Magalhaes" -> "Magalhaes".
 *  Nothing else fits inside a node on a pitch drawn 300 pixels wide. */
function short(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length === 1 ? parts[0] : parts[parts.length - 1];
}

export function PassNetwork({
  nodes,
  links,
  resolved,
  title,
  subtitle,
  width = 300,
}: {
  nodes: Node[];
  links: Link[];
  /** share of completed passes whose receiver could be inferred, 0-1 */
  resolved?: number;
  title?: string;
  subtitle?: string;
  width?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const px = width / W;
  const h = Math.round((width * H) / W);

  const at = useMemo(
    () => new Map(nodes.map((d) => [d.n, d])),
    [nodes],
  );
  const maxT = Math.max(1, ...nodes.map((d) => d.t));
  const maxN = Math.max(1, ...links.map((l) => l.n));
  const drawn = links.filter((l) => at.has(l.a) && at.has(l.b));

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
          height={h}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={title ?? "average positions and passing links"}
          style={{ background: PITCH_GREEN, borderRadius: 8, display: "block" }}
        >
          <PitchLines />

          <g>
            {drawn.map((l, i) => {
              const a = at.get(l.a)!;
              const b = at.get(l.b)!;
              const on = hover === l.a || hover === l.b;
              return (
                <line
                  key={i}
                  x1={X(a.y)}
                  y1={Y(a.x)}
                  x2={X(b.y)}
                  y2={Y(b.x)}
                  stroke={on ? "#ffffff" : "rgba(255,255,255,0.55)"}
                  strokeWidth={0.35 + (l.n / maxN) * 1.5}
                  strokeLinecap="round"
                  opacity={hover && !on ? 0.12 : 0.75}
                />
              );
            })}
          </g>

          <g>
            {nodes.map((d) => {
              const r = 1.9 + (d.t / maxT) * 2.2;
              const dim = hover !== null && hover !== d.n;
              return (
                <g
                  key={d.n}
                  onMouseEnter={() => setHover(d.n)}
                  onMouseLeave={() => setHover((k) => (k === d.n ? null : k))}
                  style={{ cursor: "help" }}
                  opacity={dim ? 0.35 : 1}
                >
                  <circle
                    cx={X(d.y)}
                    cy={Y(d.x)}
                    r={r}
                    fill="#1f2937"
                    stroke="rgba(255,255,255,0.9)"
                    strokeWidth="0.45"
                  />
                  <text
                    x={X(d.y)}
                    y={Y(d.x) + r + 2.6}
                    textAnchor="middle"
                    fontSize="2.5"
                    fontWeight="600"
                    fill="#ffffff"
                    stroke="rgba(0,0,0,0.45)"
                    strokeWidth="0.55"
                    paintOrder="stroke"
                  >
                    {short(d.n)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {hover !== null && at.has(hover) && (() => {
          const d = at.get(hover)!;
          const mine = drawn
            .filter((l) => l.a === hover)
            .sort((a, b) => b.n - a.n)
            .slice(0, 3);
          const cx = X(d.y) * px;
          const cy = Y(d.x) * px;
          const above = cy > h / 2;
          return (
            <span
              role="tooltip"
              className="pointer-events-none absolute z-30 w-52 rounded-lg border border-line bg-card p-2.5 text-left text-[11.5px] leading-relaxed text-ink-2 shadow-lg"
              style={{
                left: Math.max(4, Math.min(width - 210, cx - 104)),
                top: above ? undefined : cy + 14,
                bottom: above ? h - cy + 14 : undefined,
              }}
            >
              <b className="block text-ink">{d.n}</b>
              <span className="num">{d.t.toLocaleString()}</span> actions on the
              ball
              {d.a !== undefined && (
                <>
                  {" "}
                  in <span className="num">{d.a}</span> matches
                </>
              )}
              {mine.length > 0 && (
                <>
                  <span className="mt-1 block text-ink-3">passes most to</span>
                  {mine.map((l) => (
                    <span key={l.b} className="block">
                      {short(l.b)}{" "}
                      <span className="num text-ink-3">{l.n}</span>
                    </span>
                  ))}
                </>
              )}
            </span>
          );
        })()}
      </div>

      <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">
        The eleven who appeared most, so this is the side they usually put
        out. Node size is time on the ball, line thickness is passes between
        the two. The receiver is inferred as the next touch by the same side
        {resolved !== undefined && (
          <>
            {" "}
            — it resolves for{" "}
            <span className="num">{(resolved * 100).toFixed(1)}%</span> of
            completed passes
          </>
        )}
        , so read a line as a strong guess rather than a count.
      </p>
    </figure>
  );
}
