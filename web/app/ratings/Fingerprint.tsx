"use client";

/** THE FINGERPRINT — the half of this page that is not a ranking.
 *
 *  Press height, pass length, when he goes to the bench, how many shapes he
 *  uses: none of these has a good end. A side that sits off is not worse than
 *  one that presses — Atletico and Liverpool have both won leagues — and a
 *  late first substitution is not worse than an early one. So NOTHING here is
 *  coloured as if high were better. The track is grey, the centre line is the
 *  league median, and the only colour on the page is the two managers' own
 *  identity hues, which are the site's home and away and mean "this one" and
 *  "that one". The good/bad red and green never appear.
 *
 *  There is deliberately NO TOTAL. Summing style metrics would produce a
 *  number that ranks ways of playing football, which is an opinion wearing a
 *  decimal point.
 *
 *  TWO SHAPES OF THE SAME NUMBERS. The radar is what makes two managers
 *  comparable at a glance — the difference between a compact profile and a
 *  lopsided one is a shape, not a list. The strip underneath carries the
 *  actual values, because a radar cannot be read to two decimal places and
 *  pretending otherwise is how a picture becomes a claim.
 */

import { useState } from "react";

import { HintBox, HintIcon } from "./Hint";
import {
  type Metric,
  type Slot,
  PICK_COLOR,
  fmtRaw,
  rowId,
  shortLabel,
} from "./contract";
import type { Row } from "./RankTable";

// BIGGER, AND THE PLOT PULLED IN FROM THE EDGE. Sixteen spokes at the old
// 380 with a 112 radius left 78px for a label that is drawn from the rim
// outward, so the long ones ran off the viewBox and the short ones sat on top
// of the web. Widening the canvas while KEEPING the plot radius is what buys
// the room: the shape stays the same size and the labels get somewhere to go.
const SIZE = 460;
const R = 118;
const LABEL_R = R + 20;

/** THE SAME PLOT WITH THE LABEL RING CUT AWAY, for a phone.
 *
 *  The labelled canvas is 460 units wide carrying a 118-unit plot, so two
 *  thirds of it is the room the rim labels need. Scaled into the ~300px a
 *  375px screen has to offer, an 8.5-unit label renders at about five and a
 *  half pixels — present, unreadable, and stealing the width the shape
 *  itself needs. Sixteen of them around a 300px circle would not fit legibly
 *  at any size.
 *
 *  So below `sm` the rim is dropped and the plot fills the box instead. The
 *  radar was never where the values were read — it is the one thing on the
 *  page that shows two managers as SHAPES, compact against lopsided, and
 *  that survives at 300px. Every axis name and every number is in the strip
 *  directly below it, which is where a phone reader gets them. */
const SIZE_BARE = 2 * (R + 10);

function polar(i: number, n: number, radius: number, c: number): [number, number] {
  const ang = (i / n) * 2 * Math.PI - Math.PI / 2;
  return [c + radius * Math.cos(ang), c + radius * Math.sin(ang)];
}

function Radar({
  axes,
  series,
  hover,
  setHover,
  bare = false,
}: {
  axes: Metric[];
  series: Array<{ slot: Slot; label: string; pct: number[] }>;
  /** index of the spoke under the pointer, or null */
  hover: number | null;
  setHover: (i: number | null) => void;
  /** drop the rim labels and the hover arms — see SIZE_BARE */
  bare?: boolean;
}) {
  const n = axes.length;
  const rings = [25, 50, 75, 100];
  const size = bare ? SIZE_BARE : SIZE;
  const C = size / 2;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className={`mx-auto block h-auto w-full ${bare ? "max-w-[300px]" : "max-w-[460px]"}`}
      role="img"
      aria-label={`Style profile across ${n} axes for ${series.map((s) => s.label).join(" and ")}. Each axis is a percentile within this league; no axis has a good end.${bare ? " The axis names and values are listed below the chart." : ""}`}
    >
      {rings.map((v) => (
        <polygon
          key={v}
          points={axes
            .map((_, i) => polar(i, n, (v / 100) * R, C).join(","))
            .join(" ")}
          fill="none"
          stroke={v === 50 ? "#c9d0d6" : "#eef0f2"}
          strokeWidth={v === 50 ? 1 : 1}
          strokeDasharray={v === 50 ? "3 3" : undefined}
        />
      ))}
      {axes.map((_, i) => {
        const [x, y] = polar(i, n, R, C);
        return (
          <line key={i} x1={C} y1={C} x2={x} y2={y} stroke="#eef0f2" strokeWidth={1} />
        );
      })}

      {series.map((s) => {
        const pts = s.pct.map((v, i) =>
          polar(i, n, (Math.max(0, Math.min(100, v)) / 100) * R, C),
        );
        return (
          <g key={s.slot}>
            <polygon
              points={pts.map((p) => p.join(",")).join(" ")}
              fill={PICK_COLOR[s.slot]}
              fillOpacity={0.1}
              stroke={PICK_COLOR[s.slot]}
              strokeWidth={1.75}
              strokeLinejoin="round"
            />
            {pts.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r={2.4} fill={PICK_COLOR[s.slot]} />
            ))}
          </g>
        );
      })}

      {/* The hovered spoke, drawn over the web so it reads as picked out
          rather than as another grid line. */}
      {hover !== null && !bare && (
        <line
          x1={C}
          y1={C}
          x2={polar(hover, n, R, C)[0]}
          y2={polar(hover, n, R, C)[1]}
          stroke="#1f2429"
          strokeWidth="1"
          opacity="0.35"
        />
      )}

      {!bare && axes.map((m, i) => {
        const [x, y] = polar(i, n, LABEL_R, C);
        const dx = x - C;
        const anchor = Math.abs(dx) < 12 ? "middle" : dx > 0 ? "start" : "end";
        const on = hover === i;
        return (
          <g
            key={m.key}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            style={{ cursor: "default" }}
          >
            {/* An invisible wedge so the whole arm is hoverable, not just the
                eight-pixel text. A target you have to hit exactly is a target
                nobody discovers. */}
            <line
              x1={C}
              y1={C}
              x2={polar(i, n, LABEL_R + 14, C)[0]}
              y2={polar(i, n, LABEL_R + 14, C)[1]}
              stroke="transparent"
              strokeWidth="22"
            />
            <text
              x={x}
              y={y}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize={on ? "9.5" : "8.5"}
              fontWeight={on ? 600 : 400}
              fill={on ? "#1f2429" : "#55606b"}
            >
              {shortLabel(m)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** One metric as OPPOSED BARS growing out of a shared centre — the shape a
 *  football broadcast uses for possession or shots, because it is the one
 *  people read without being taught.
 *
 *  WHY NOT A SPLIT 100% BAR, which is what that graphic usually is. A split
 *  bar says the two numbers are shares of one thing, and here they are not:
 *  press height, pass length and PPDA do not sum to anything, and drawing
 *  A/(A+B) would invent a total that does not exist. Each side's bar is its
 *  OWN percentile in its OWN league instead, so a full bar means "top of the
 *  league at this", not "more of it than the other man". Two long bars are
 *  therefore possible and mean both are extreme — which a share bar could
 *  never show.
 *
 *  The raw values sit at the outer ends, where the eye lands after the bar.
 */
function StripRow({
  m,
  a,
  b,
}: {
  m: Metric;
  a: { label: string; pct?: number; raw?: number | null } | null;
  b: { label: string; pct?: number; raw?: number | null } | null;
}) {
  const pctOf = (e: { pct?: number } | null) =>
    e && typeof e.pct === "number" ? Math.max(0, Math.min(100, e.pct)) : null;
  const pa = pctOf(a);
  const pb = pctOf(b);

  const tip = (
    e: { label: string; pct?: number; raw?: number | null } | null,
    p: number | null,
  ) =>
    e && p !== null
      ? `${e.label}: ${fmtRaw(e.raw, m.unit)}${m.unit ? " " + m.unit : ""} — ${p.toFixed(0)} of 100 in his own league`
      : undefined;

  return (
    <div className="group/hint relative border-t border-line py-2">
      {/* ================================== phone: one bar per manager, stacked
          FOUR TRACKS DO NOT FIT ON A PHONE. The opposed layout below spends
          about 100px on the two value columns and 144px on the label, which
          on a 375px screen leaves the two bars roughly thirteen pixels each —
          a graphic that no longer encodes anything. Stacked, each bar gets
          the full width and still runs 0-100 from a fixed left edge, so a
          long bar still means "extreme for this league".
          What is lost is the mirror: the two managers are read one above the
          other rather than out from a shared centre. Both values, both
          percentiles and both colours survive, which is everything the row
          was carrying. */}
      <div className="sm:hidden">
        <div className="flex items-baseline gap-1 text-[12.5px] text-ink-2">
          <span className="truncate">{m.label}</span>
          {m.unit && (
            <span className="shrink-0 text-[10px] text-ink-3">{m.unit}</span>
          )}
          <HintIcon />
        </div>
        {([["a", a, pa], ["b", b, pb]] as const).map(([slot, e, p]) =>
          e ? (
            <div
              key={slot}
              className="mt-1.5 grid grid-cols-[1.1rem_1fr_3.2rem] items-center gap-2"
              title={tip(e, p)}
            >
              <span
                aria-hidden
                className="inline-flex h-4 w-4 items-center justify-center rounded text-[9px] font-semibold text-white"
                style={{ background: PICK_COLOR[slot] }}
              >
                {slot.toUpperCase()}
              </span>
              <span className="relative block h-3 overflow-hidden rounded-full bg-[#f0f2f4]">
                {p !== null && (
                  <span
                    className="absolute left-0 top-0 h-full rounded-full"
                    style={{ width: `${p}%`, background: PICK_COLOR[slot] }}
                  />
                )}
              </span>
              <span
                className="num truncate text-right text-[12px] font-medium"
                style={{ color: PICK_COLOR[slot] }}
              >
                {fmtRaw(e.raw, m.unit)}
              </span>
            </div>
          ) : null,
        )}
      </div>

      {/* ============================= laptop: opposed bars from one centre */}
      <div className="hidden grid-cols-[minmax(0,11rem)_1fr] items-center gap-3 sm:grid">
        <div className="flex min-w-0 items-baseline gap-1 text-[12.5px] text-ink-2">
          <span className="truncate">{m.label}</span>
          <HintIcon />
        </div>

        {/* THE UNIT MOVED OUT OF A COLUMN AND UNDER THE BARS. As a fifth
            track it had about 2.6rem to live in, which truncated the ones
            that actually needed explaining — "x (0-1…", "passe…", "chan…" —
            so the column was widest where it said least and useless where it
            mattered. Under the bars it has the whole width and costs a row
            of muted 10px type. */}
        <div className="grid grid-cols-[3.2rem_1fr_1fr_3.2rem] items-center gap-1.5">
          <span
            className="num truncate text-right text-[12px] font-medium"
            style={{ color: PICK_COLOR.a }}
            title={tip(a, pa)}
          >
            {a ? fmtRaw(a.raw, m.unit) : ""}
          </span>

          {/* A grows leftward out of the centre line */}
          <span
            className="relative block h-3 overflow-hidden rounded-l-full bg-[#f0f2f4]"
            title={tip(a, pa)}
          >
            {pa !== null && (
              <span
                className="absolute right-0 top-0 h-full rounded-l-full"
                style={{ width: `${pa}%`, background: PICK_COLOR.a }}
              />
            )}
          </span>

          {/* B grows rightward */}
          <span
            className="relative block h-3 overflow-hidden rounded-r-full bg-[#f0f2f4]"
            title={tip(b, pb)}
          >
            {pb !== null && (
              <span
                className="absolute left-0 top-0 h-full rounded-r-full"
                style={{ width: `${pb}%`, background: PICK_COLOR.b }}
              />
            )}
          </span>

          <span
            className="num truncate text-[12px] font-medium"
            style={{ color: PICK_COLOR.b }}
            title={tip(b, pb)}
          >
            {b ? fmtRaw(b.raw, m.unit) : ""}
          </span>
        </div>
      </div>

      {m.unit && (
        <div className="hidden grid-cols-[minmax(0,11rem)_1fr] gap-3 sm:grid">
          <span />
          <span className="block text-center text-[10px] leading-none text-ink-3">
            {m.unit}
          </span>
        </div>
      )}

      <HintBox>
        {m.help || m.label}
        {m.unit ? ` Measured in ${m.unit}.` : ""}{" "}
        <b className="text-ink">Neither end is better.</b> This is what he
        does, not how well he does it, and it is never scored. Each bar is that
        manager&apos;s percentile in his own league, so a long bar means
        &ldquo;extreme for this league&rdquo; — not &ldquo;more than the other
        man&rdquo;.
      </HintBox>
    </div>
  );
}

function Picker({
  slot,
  rows,
  value,
  onPick,
  allowNone,
}: {
  slot: Slot;
  rows: Row[];
  value: string | null;
  onPick: (slot: Slot, id: string) => void;
  allowNone?: boolean;
}) {
  return (
    <label className="flex min-w-0 flex-1 items-center gap-2 text-[12.5px] text-ink-2">
      <span
        aria-hidden
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] font-semibold text-white"
        style={{ background: PICK_COLOR[slot] }}
      >
        {slot.toUpperCase()}
      </span>
      <select
        value={value ?? ""}
        aria-label={`manager ${slot.toUpperCase()}`}
        onChange={(e) => onPick(slot, e.target.value)}
        className="h-11 min-w-0 flex-1 rounded-md border border-line bg-card px-2 sm:h-8"
      >
        {allowNone && <option value="">— nobody —</option>}
        {rows.map((r) => {
          const id = rowId(r);
          return (
            <option key={id} value={id}>
              {r.manager} — {r.team}
              {r.short ? " (short)" : ""}
            </option>
          );
        })}
      </select>
    </label>
  );
}

export function Fingerprint({
  fingerprint,
  rows,
  pick,
  onPick,
  open,
  setOpen,
}: {
  fingerprint: Metric[];
  rows: Row[];
  pick: Record<Slot, string | null>;
  onPick: (slot: Slot, id: string) => void;
  /** OPEN BY DEFAULT, unlike the weight panel. This sits above the table now
   *  because the comparison is the reason to come here; opening collapsed
   *  would make that position pointless. It folds for a reader who wants the
   *  ranking back at the top of the screen, which is a different visit. */
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  /** Which spoke the pointer is on. Lives here rather than in Radar because
   *  the readout under the chart needs it too — the point of the hover is to
   *  turn a shape back into numbers, and a shape that can only say "this one"
   *  has not been made interactive, only twitchy. */
  const [hover, setHover] = useState<number | null>(null);

  const find = (id: string | null) =>
    id ? rows.find((r) => rowId(r) === id) ?? null : null;
  const A = find(pick.a);
  const B = find(pick.b);

  if (!fingerprint.length) {
    return (
      <p className="mt-4 text-[13px] text-ink-2">
        This payload carries no fingerprint metrics.
      </p>
    );
  }

  const entry = (r: Row | null, m: Metric) =>
    r
      ? {
          label: `${r.manager} (${r.team})`,
          pct: typeof r.pct?.[m.key] === "number" ? (r.pct[m.key] as number) : undefined,
          raw: r.raw?.[m.key],
        }
      : null;

  // A radar can only be drawn over axes BOTH selected spells have. An axis
  // one of them is missing would have to be guessed at, and a guessed vertex
  // changes the shape — which is the entire thing the radar is for. Missing
  // axes are dropped from the picture and named underneath; the strip below
  // still lists them, as a dash.
  const radarAxes = fingerprint.filter((m) => {
    const ok = (r: Row | null) => !r || typeof r.pct?.[m.key] === "number";
    return ok(A) && ok(B);
  });
  const dropped = fingerprint.filter((m) => !radarAxes.includes(m));
  const series: Array<{ slot: Slot; label: string; pct: number[] }> = [];
  for (const [slot, r] of [["a", A], ["b", B]] as Array<[Slot, Row | null]>) {
    if (!r) continue;
    series.push({
      slot,
      label: `${r.manager} (${r.team})`,
      pct: radarAxes.map((m) => (r.pct[m.key] as number) ?? 50),
    });
  }

  const names = [A, B].filter(Boolean).map((r) => r!.manager).join(" vs ");

  return (
    <section className="mt-6 rounded-xl border border-line bg-card">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-line px-3 py-3 sm:px-4">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="flex items-baseline gap-1.5 text-left text-[14px] font-semibold hover:text-home"
        >
          <span className="text-ink-3">{open ? "▾" : "▸"}</span>
          The fingerprint — how he plays, not how well
        </button>
        {/* Collapsed, the header still has to say what is inside it, or the
            row is a mystery box the reader has no reason to open. */}
        <span className="num min-w-0 flex-1 truncate text-[12.5px] text-ink-3">
          {names || "pick two managers"}
        </span>
      </div>

      {!open ? null : (
      <div className="px-3 pb-4 pt-3 sm:px-4">
      <p className="max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        How he plays, which is a different question from how well it goes.{" "}
        <strong className="font-semibold">
          None of these has a good end
        </strong>
        , so none of them is scored, coloured as if high were better, or added
        to anything. The two colours are the two managers, not two verdicts.
      </p>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <Picker slot="a" rows={rows} value={pick.a} onPick={onPick} />
        <Picker slot="b" rows={rows} value={pick.b} onPick={onPick} allowNone />
      </div>

      {!A && !B ? (
        <p className="mt-4 rounded-xl border border-line bg-card p-4 text-[13px] text-ink-2">
          Pick a manager above, or press <b>A</b> on any row in the table.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 rounded-xl border border-line bg-card p-3 sm:p-4 lg:grid-cols-[380px_1fr] lg:gap-6">
          <div>
            {radarAxes.length >= 3 ? (
              <>
                {/* Two canvases, one shape. The phone gets the plot without
                    the rim — see SIZE_BARE — and nothing to hover, because
                    a touch screen has no pointer to hover with. */}
                <div className="sm:hidden">
                  <Radar
                    axes={radarAxes}
                    series={series}
                    hover={null}
                    setHover={() => {}}
                    bare
                  />
                </div>
                <div className="hidden sm:block">
                  <Radar
                    axes={radarAxes}
                    series={series}
                    hover={hover}
                    setHover={setHover}
                  />
                </div>
              </>
            ) : (
              <p className="text-[12.5px] text-ink-2">
                Too few shared axes to draw a shape — the strip beside it
                carries what there is.
              </p>
            )}
            {/* The readout. Fixed height, so hovering does not shove the
                legend and the strip below it down the page. Pointer-only:
                a phone reads the same numbers off the strip below, which is
                why the bare radar can afford to drop its labels. */}
            <div className="mt-1 hidden min-h-[2.4rem] items-center justify-center px-2 text-center sm:flex">
              {hover !== null && radarAxes[hover] ? (
                <span className="text-[12px] leading-tight">
                  <b className="text-ink">{radarAxes[hover].label}</b>
                  {radarAxes[hover].unit ? (
                    <span className="text-ink-3"> ({radarAxes[hover].unit})</span>
                  ) : null}
                  <br />
                  {series.map((sr, si) => (
                    <span key={sr.slot} className="num">
                      {si > 0 && <span className="text-ink-3"> · </span>}
                      <span style={{ color: PICK_COLOR[sr.slot] }}>
                        {fmtRaw(
                          (sr.slot === "a" ? A : B)?.raw?.[
                            radarAxes[hover].key
                          ],
                          radarAxes[hover].unit,
                        )}
                      </span>
                      <span className="text-ink-3">
                        {" "}
                        ({sr.pct[hover]?.toFixed(0) ?? "—"})
                      </span>
                    </span>
                  ))}
                </span>
              ) : (
                <span className="text-[11.5px] text-ink-3">
                  Each spoke is a percentile in this league; the dashed ring is
                  the median. Hover a spoke for its numbers.
                </span>
              )}
            </div>
            {/* What the phone's radar says for itself, since it carries no
                names on its rim and no hover to ask with. */}
            <p className="mt-1.5 px-2 text-center text-[11.5px] leading-snug text-ink-3 sm:hidden">
              Each spoke is a percentile in this league and the dashed ring is
              the median. The shape is the comparison; every axis is named with
              its numbers in the list below.
            </p>
            <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[12px]">
              {series.map((s) => (
                <span key={s.slot} className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ background: PICK_COLOR[s.slot] }}
                  />
                  {s.label}
                </span>
              ))}
            </div>
            {dropped.length > 0 && (
              <p className="mt-2 text-center text-[11.5px] text-ink-3">
                Left off the shape for want of a value on one side:{" "}
                {dropped.map((m) => m.label).join(", ")}.
              </p>
            )}
          </div>

          <div className="min-w-0">
            {fingerprint.map((m) => (
              <StripRow key={m.key} m={m} a={entry(A, m)} b={entry(B, m)} />
            ))}
          </div>
        </div>
      )}
      </div>
      )}
    </section>
  );
}
