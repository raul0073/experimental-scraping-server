"use client";

import { useState } from "react";

import { H, PITCH_GREEN, PitchLines, W, X, Y } from "./Pitch";
import { posLabel, posShort } from "../lib/positions";
import type { XI } from "../lib/bestXI";

/** The best eleven, drawn as a team sheet.
 *
 *  A list of eleven names sorted by rating is a leaderboard; put on a pitch
 *  it is a side, and the shape is the point — it was chosen by which formation
 *  the squad scores highest in, not assumed.
 *
 *  Each badge carries the rating, coloured on the same diverging scale the
 *  rest of the site uses: 50 is the middle of the league by construction, so
 *  grey is genuinely average and there is never a hue for "no data".
 */

function shade(v: number): string {
  const t = Math.max(-1, Math.min(1, (v - 50) / 30));
  const mid = [154, 163, 171];
  const to = t < 0 ? [179, 38, 30] : [26, 127, 55];
  const c = mid.map((m, i) => Math.round(m + (to[i] - m) * Math.abs(t)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

const short = (name: string) => {
  const parts = name.trim().split(/\s+/);
  return parts.length === 1 ? parts[0] : parts[parts.length - 1];
};

export function BestXI({ xi, width = 320 }: { xi: XI; width?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const px = width / W;
  const h = Math.round((width * H) / W);

  return (
    <figure className="m-0">
      <div className="relative" style={{ width }}>
        <svg
          width={width}
          height={h}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`best eleven, ${xi.formation}`}
          style={{ background: PITCH_GREEN, borderRadius: 8, display: "block" }}
        >
          <PitchLines />
          {xi.picked.map((e, i) => (
            <g
              key={e.player.n}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((k) => (k === i ? null : k))}
              style={{ cursor: "help" }}
            >
              <circle
                cx={X(e.slot.y)}
                cy={Y(e.slot.x)}
                r={4.2}
                fill={shade(e.v)}
                stroke="rgba(255,255,255,0.92)"
                strokeWidth="0.7"
              />
              <text
                x={X(e.slot.y)}
                y={Y(e.slot.x)}
                textAnchor="middle"
                dominantBaseline="central"
                className="num"
                fontSize="3.4"
                fontWeight="700"
                fill="#ffffff"
              >
                {e.v.toFixed(0)}
              </text>
              <text
                x={X(e.slot.y)}
                y={Y(e.slot.x) + 7.2}
                textAnchor="middle"
                fontSize="2.7"
                fontWeight="600"
                fill="#ffffff"
                stroke="rgba(0,0,0,0.45)"
                strokeWidth="0.6"
                paintOrder="stroke"
              >
                {short(e.player.n)}
              </text>
            </g>
          ))}
        </svg>

        {hover !== null && xi.picked[hover] && (() => {
          const e = xi.picked[hover];
          const cx = X(e.slot.y) * px;
          const cy = Y(e.slot.x) * px;
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
              <b className="block text-ink">{e.player.n}</b>
              {posLabel(e.player.p)} ·{" "}
              <span className="num">{e.player.m.toLocaleString()}</span> minutes
              <span className="mt-1 block">
                <span className="num font-semibold text-ink">
                  {e.v.toFixed(0)}
                </span>{" "}
                of 100 against every {posShort(e.player.p)} in the league, on
                your weights.
              </span>
            </span>
          );
        })()}
      </div>
    </figure>
  );
}
