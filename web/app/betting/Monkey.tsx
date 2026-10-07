"use client";

import { useEffect, useState } from "react";

import { leagueShort } from "@/lib/league";

import { getMonkey, message } from "./api";
import type {
  Block,
  Gold,
  GoldWeek,
  Leg,
  Monkey as Book,
  MonkeyBook,
  Slip,
} from "./api";

/** The monkey's book — what following the advice would actually have done.
 *
 *  THE NAME IS NOT A JOKE. Every window, the slip the advisor recommended is
 *  placed at one unit per line and graded line by line once all its legs
 *  resolve, from a fixed 1,000 start. Nobody picks the good weeks afterwards,
 *  nothing is skipped because it looked thin, and a losing slip stays in the
 *  book and in the pot. That is the whole point: the pot is the one number in
 *  this section that cannot be improved by telling the story differently.
 *
 *  AND THE ROI IS NOT A TRACK RECORD. Returns are computed at each leg's
 *  BREAKEVEN price frozen at commit — 1/p, the model's own fair value, which
 *  is the only price this project will touch. A real book pays less than fair
 *  on every leg, and a system slip multiplies its legs together, so the
 *  shortfall compounds with each one: these figures are an upper bound no
 *  actual slip would have returned. That sentence sits beside the ROI rather
 *  than in a footnote, because an ROI that looks like a track record and is
 *  not one is the easiest way for this page to mislead the one person reading
 *  it. slip_ledger.py says the same thing in its own docstring; that should
 *  not be the only place it is said.
 *
 *  THE MANDATE SPLIT EXISTS BECAUSE THE POT DOES NOT CARE. From the user's
 *  sign-off on 2026-09-15 this pot bets ONE instrument — the draw system, one
 *  slip per round. Slips without that stamp are pre-mandate or off-mandate
 *  experiments. They were real money and they stay in the pot balance, so the
 *  curve keeps telling the truth; but they are scored apart, because a
 *  strategy's P&L that quietly includes the experiments you ran instead of it
 *  is not that strategy's P&L.
 *
 *  THE GOLD POT IS HERE BECAUSE IT ARRIVES IN THE SAME CALL AND ANSWERS THE
 *  SAME QUESTION OF SINGLES. Backing every certified gold favourite at 1/p
 *  makes its ROI positive exactly when realized accuracy beats the stated
 *  probability — a calibration test wearing a bankroll — so it is shown
 *  realized-against-expected first and as money second.
 *
 *  NO ODDS. Not fetched, not displayed, not compared against.
 *
 *  DEVELOPMENT ONLY. The real guard is layout.tsx, which stops this route
 *  being emitted at all; the check below is the second one.
 */
const DEV = process.env.NODE_ENV === "development";

const MARK_STYLE: Record<string, string> = {
  "1": "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]",
  X: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  "2": "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
};

const money = (v: number) =>
  `₪${v.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const signed = (v: number) =>
  `${v >= 0 ? "+" : "−"}₪${Math.abs(v).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

const tone = (v: number | null | undefined) =>
  v == null
    ? "text-ink-2"
    : v > 0
      ? "text-good"
      : v < 0
        ? "text-bad"
        : "text-ink-2";

/** Oldest first. The service hands both books back newest-first for the
 *  list, and a curve plotted in that order runs backwards — a winning pot
 *  then reads as a collapse. */
function chronological<T extends { window: string }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => a.window.localeCompare(b.window));
}

function Stat({
  label,
  value,
  sub,
  colour,
  big,
}: {
  label: string;
  value: string;
  sub?: string;
  colour?: string;
  big?: boolean;
}) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-wider text-ink-3">
        {label}
      </div>
      <div
        className={`num ${big ? "text-[22px]" : "text-[15px]"} font-semibold ${
          colour ?? "text-ink"
        }`}
      >
        {value}
      </div>
      {sub && <div className="num text-[10.5px] text-ink-3">{sub}</div>}
    </div>
  );
}

/** Two bars on one 0–100 track. Used for the gold pot's claim against its
 *  result, which is the same shape of statement the record tab makes. */
function Bar({
  tone: t,
  label,
  value,
}: {
  tone: "said" | "landed";
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[62px] shrink-0 text-right text-[10.5px] text-ink-3">
        {label}
      </span>
      <div className="h-[7px] flex-1 overflow-hidden rounded-full bg-[#eef0f2]">
        <div
          className={`h-full rounded-full ${
            t === "said" ? "bg-[#b9d5e8]" : "bg-[#1c5b8a]"
          }`}
          style={{ width: `${Math.max(1, Math.min(100, value * 100))}%` }}
        />
      </div>
      <span
        className={`num w-[48px] shrink-0 text-right text-[11.5px] ${
          t === "landed" ? "font-semibold text-ink" : "text-ink-3"
        }`}
      >
        {pct(value)}
      </span>
    </div>
  );
}

type Point = { label: string; pot: number; pending: boolean };

/** The pot, slip by slip. Hand-drawn SVG on purpose — a chart library for one
 *  polyline is three hundred kilobytes to say the same thing.
 *
 *  THE START IS A POINT, NOT JUST A BASELINE. With two or three graded weeks
 *  a line drawn between the pot values alone has no origin, so the first
 *  movement is invisible; beginning at the start pot makes the first week a
 *  climb or a dip rather than a dot. The dashed rule stays at the start pot
 *  too, because "above the line" is the only thing this picture has to say. */
function PotCurve({ points, start }: { points: Point[]; start: number }) {
  const W = 640;
  const H = 170;
  const padL = 56;
  const padR = 56;
  const padT = 16;
  const padB = 26;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const pots = points.map((p) => p.pot);
  let lo = Math.min(start, ...pots);
  let hi = Math.max(start, ...pots);
  // A flat book would otherwise divide by zero and draw nothing at all.
  if (hi - lo < 1) {
    lo -= 50;
    hi += 50;
  }
  const span = hi - lo;
  lo -= span * 0.1;
  hi += span * 0.1;

  const x = (i: number) =>
    points.length > 1
      ? padL + (i * innerW) / (points.length - 1)
      : padL + innerW / 2;
  const y = (v: number) => padT + innerH - ((v - lo) / (hi - lo)) * innerH;

  const path = points
    .map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.pot).toFixed(1)}`)
    .join(" ");

  const last = points[points.length - 1];
  const baseY = y(start);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="block h-auto w-full"
      role="img"
      aria-label={`Pot from ${money(start)} to ${money(last.pot)} over ${
        points.length - 1
      } slips`}
    >
      <line
        x1={padL}
        x2={padL + innerW}
        y1={baseY}
        y2={baseY}
        stroke="#c9ced4"
        strokeWidth="1"
        strokeDasharray="4 4"
      />
      <text
        x={padL - 8}
        y={baseY + 3.5}
        textAnchor="end"
        className="num"
        fontSize="10"
        fill="#8a949e"
      >
        {start.toFixed(0)}
      </text>

      <path d={path} fill="none" stroke="#4a7ba6" strokeWidth="1.8" />

      {points.map((p, i) => (
        <g key={`${p.label}-${i}`}>
          <circle
            cx={x(i)}
            cy={y(p.pot)}
            r="3.4"
            fill={p.pending ? "#ffffff" : p.pot >= start ? "#1a7f37" : "#b3261e"}
            stroke={p.pending ? "#8a949e" : "none"}
            strokeWidth="1.4"
          />
          {/* Beyond a dozen slips these labels collide into a grey smear;
              the week is in the list underneath either way. */}
          {points.length <= 12 && (
            <text
              x={x(i)}
              y={H - 8}
              textAnchor="middle"
              className="num"
              fontSize="9.5"
              fill="#8a949e"
            >
              {p.label}
            </text>
          )}
        </g>
      ))}

      <text
        x={padL + innerW + 8}
        y={y(last.pot) + 3.5}
        className="num"
        fontSize="10.5"
        fontWeight="600"
        fill={last.pot >= start ? "#1a7f37" : "#b3261e"}
      >
        {last.pot.toFixed(0)}
      </text>
    </svg>
  );
}

function MandateCard({
  title,
  note,
  block,
}: {
  title: string;
  note: string;
  block: Block;
}) {
  return (
    <div className="rounded-xl border border-line bg-card px-4 py-3.5">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <h4 className="text-[12.5px] font-semibold text-ink">{title}</h4>
        <span className="num text-[11px] text-ink-3">
          {block.graded}/{block.slips} graded · {block.profit_weeks} in profit
        </span>
      </div>
      <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-3">{note}</p>
      <div className="num mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[12px]">
        <span className="text-ink-2">staked {money(block.staked)}</span>
        <span className="text-ink-2">back {money(block.returned)}</span>
        <span className={`font-semibold ${tone(block.net)}`}>
          {signed(block.net)}
        </span>
        {/* Null is not zero: nothing graded means no return on stake, not a
            flat one. */}
        <span className={`font-semibold ${tone(block.roi)}`}>
          {block.roi != null ? pct(block.roi) : "—"}
        </span>
        {!!block.in_play && (
          <span className="text-ink-3">{money(block.in_play)} in play</span>
        )}
      </div>
    </div>
  );
}

function Hit({ hit }: { hit?: boolean }) {
  if (hit == null) {
    return (
      <span className="text-[10.5px] uppercase tracking-wider text-ink-3">
        open
      </span>
    );
  }
  return hit ? (
    <span className="font-semibold text-good">✓</span>
  ) : (
    <span className="font-semibold text-bad">✗</span>
  );
}

function LegRow({ l }: { l: Leg }) {
  return (
    <tr className="border-t border-line align-top">
      <td className="py-2 pl-3 pr-2 text-center">
        <span
          className={`inline-block min-w-[22px] rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${
            MARK_STYLE[l.mark] ?? "border-line bg-card text-ink-2"
          }`}
        >
          {l.mark}
        </span>
      </td>
      <td className="py-2 pr-3">
        <div className="text-[12.5px]">{l.fixture}</div>
        <div className="num text-[10.5px] text-ink-3">
          {leagueShort(l.league)} · {l.kickoff}
          {/* A favourite leg names the team it needs; a draw leg has no side,
              and inventing one for it would be a lie. */}
          {l.team && <> · needs {l.team}</>}
        </div>
      </td>
      <td className="num px-2 py-2 text-center text-[12.5px] text-ink-2">
        {pct(l.prob)}
      </td>
      <td className="num px-2 py-2 text-center text-[12.5px] text-ink-2">
        {l.breakeven.toFixed(2)}
      </td>
      <td className="num px-2 py-2 text-center text-[12.5px]">
        {l.score ?? <span className="text-ink-3">—</span>}
      </td>
      <td className="py-2 pl-2 pr-3 text-center text-[13px]">
        <Hit hit={l.hit} />
      </td>
    </tr>
  );
}

function SlipRow({
  w,
  open,
  onToggle,
}: {
  w: Slip;
  open: boolean;
  onToggle: () => void;
}) {
  const graded = w.status === "graded";
  const onMandate = w.mandate == null || w.mandate === "draws";

  return (
    <li className="border-t border-line first:border-t-0">
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 text-left"
      >
        <span className="num text-[11.5px] text-ink-3">{w.window}</span>

        {/* Hebrew is the name the form actually has, so it leads. dir="rtl"
            also isolates the run, which is what keeps "2/4" inside it the
            right way round instead of reordered by the surrounding text. */}
        <span dir="rtl" className="text-[13.5px] font-semibold text-ink">
          {w.title_he}
        </span>
        <span className="text-[12px] text-ink-2">{w.title_en}</span>

        {!onMandate && (
          <span
            className="rounded-full border border-line bg-[#fafbfc] px-2 py-0.5 text-[10px] uppercase tracking-wider text-ink-3"
            title={`${w.mandate} — not the mandated draw system. Real money, kept in the pot, scored apart.`}
          >
            off-mandate
          </span>
        )}

        <span className="num ml-auto flex flex-wrap items-baseline gap-x-2.5 text-[12px]">
          <span className="text-ink-3">
            {w.k}/{w.legs.length} · {w.lines}×{money(w.unit)} ={" "}
            {money(w.stake)}
          </span>
          {graded && w.net != null ? (
            <b className={`font-semibold ${tone(w.net)}`}>{signed(w.net)}</b>
          ) : (
            <span className="text-ink-3">in play</span>
          )}
          <span className="text-ink-2">pot {money(w.pot_after)}</span>
          <span className="text-[11px] text-ink-3">{open ? "▴" : "▾"}</span>
        </span>
      </button>

      {open && (
        <div className="border-t border-line bg-[#fcfcfb] px-4 pb-4 pt-3">
          <div className="num flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[11.5px] text-ink-2">
            <span>
              system{" "}
              <b className="font-semibold text-ink">
                {w.k}/{w.legs.length}
              </b>{" "}
              — every combination of {w.k} of the {w.legs.length} legs
            </span>
            <span>
              <b className="font-semibold text-ink">{w.lines}</b> lines at{" "}
              {money(w.unit)}
            </span>
            <span>
              chance of profit{" "}
              <b className="font-semibold text-ink">{pct(w.p_profit)}</b>
            </span>
            {graded && (
              <>
                {w.hits != null && (
                  <span>
                    <b className="font-semibold text-ink">{w.hits}</b>/
                    {w.legs.length} legs landed
                  </span>
                )}
                {w.lines_won != null && (
                  <span>
                    <b className="font-semibold text-ink">{w.lines_won}</b>/
                    {w.lines} lines won
                  </span>
                )}
                {w.gross_return != null && (
                  <span>back {money(w.gross_return)}</span>
                )}
              </>
            )}
          </div>

          <div className="mt-2.5 overflow-x-auto rounded-lg border border-line bg-card">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[10.5px] uppercase tracking-wider text-ink-3">
                  <th className="py-1.5 pl-3 pr-2 text-center font-semibold">
                    Mark
                  </th>
                  <th className="py-1.5 pr-3 text-left font-semibold">Leg</th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Said
                  </th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Fair
                  </th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Score
                  </th>
                  <th className="py-1.5 pl-2 pr-3 text-center font-semibold">
                    Hit
                  </th>
                </tr>
              </thead>
              <tbody>
                {w.legs.map((l, i) => (
                  <LegRow key={`${l.fixture}-${l.mark}-${i}`} l={l} />
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
            Each winning line paid {money(w.unit)} multiplied by the fair price
            of its {w.k} legs, frozen when the slip was committed. No
            bookmaker price is involved.
          </p>
        </div>
      )}
    </li>
  );
}

function GoldRow({
  w,
  open,
  onToggle,
}: {
  w: GoldWeek;
  open: boolean;
  onToggle: () => void;
}) {
  const graded = w.status === "graded";
  return (
    <li className="border-t border-line first:border-t-0">
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full cursor-pointer flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-left"
      >
        <span className="num text-[11.5px] text-ink-3">{w.window}</span>
        <span className="num text-[12.5px] text-ink">
          {w.bets.length} singles at {money(w.unit)}
        </span>
        <span className="num ml-auto flex flex-wrap items-baseline gap-x-2.5 text-[12px]">
          {graded && w.hits != null && (
            <span className="text-ink-2">
              {w.hits}/{w.bets.length} landed
            </span>
          )}
          {graded && w.net != null ? (
            <b className={`font-semibold ${tone(w.net)}`}>{signed(w.net)}</b>
          ) : (
            <span className="text-ink-3">in play</span>
          )}
          <span className="text-ink-2">pot {money(w.pot_after)}</span>
          <span className="text-[11px] text-ink-3">{open ? "▴" : "▾"}</span>
        </span>
      </button>

      {open && (
        <div className="border-t border-line bg-[#fcfcfb] px-4 pb-4 pt-3">
          <div className="overflow-x-auto rounded-lg border border-line bg-card">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[10.5px] uppercase tracking-wider text-ink-3">
                  <th className="py-1.5 pl-3 pr-3 text-left font-semibold">
                    Fixture
                  </th>
                  <th className="py-1.5 pr-3 text-left font-semibold">
                    Backed
                  </th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Said
                  </th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Fair
                  </th>
                  <th className="px-2 py-1.5 text-center font-semibold">
                    Score
                  </th>
                  <th className="py-1.5 pl-2 pr-3 text-center font-semibold">
                    Hit
                  </th>
                </tr>
              </thead>
              <tbody>
                {w.bets.map((b, i) => (
                  <tr
                    key={`${b.fixture}-${i}`}
                    className="border-t border-line align-top"
                  >
                    <td className="py-2 pl-3 pr-3">
                      <div className="text-[12.5px]">{b.fixture}</div>
                      <div className="num text-[10.5px] text-ink-3">
                        {leagueShort(b.league)} · {b.kickoff}
                      </div>
                    </td>
                    <td className="py-2 pr-3 text-[12.5px]">
                      {b.team}
                      <span className="text-ink-3"> ({b.side})</span>
                    </td>
                    <td className="num px-2 py-2 text-center text-[12.5px] text-ink-2">
                      {pct(b.prob)}
                    </td>
                    <td className="num px-2 py-2 text-center text-[12.5px] text-ink-2">
                      {b.breakeven.toFixed(2)}
                    </td>
                    <td className="num px-2 py-2 text-center text-[12.5px]">
                      {b.score ?? <span className="text-ink-3">—</span>}
                    </td>
                    <td className="py-2 pl-2 pr-3 text-center text-[13px]">
                      <Hit hit={b.hit} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </li>
  );
}

/** The gold pot, led by the comparison that makes it mean something. Backing
 *  every gold favourite at its own fair price means the pot grows if and only
 *  if realized accuracy beat the stated probability — so realized against
 *  expected is the reading, and the money is the consequence. */
function GoldPot({ g }: { g: Gold }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const ordered = chronological(g.weeks);
  const points: Point[] = [
    { label: "start", pot: g.start_pot, pending: false },
    ...ordered.map((w) => ({
      label: w.window.slice(5, 10),
      pot: w.pot_after,
      pending: w.status !== "graded",
    })),
  ];
  const s = g.settled;
  const progress = Math.min(1, s.n / g.gate_a.target_n);

  return (
    <section className="mt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-display text-[18px] tracking-[0.01em]">
          The gold pot
        </h3>
        <span className="text-[12px] text-ink-3">
          the same question asked of singles
        </span>
      </div>

      <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-ink-2">
        Every certified gold favourite is backed on its own at its own fair
        price. Because the price is exactly 1/p, this pot grows if and only if
        the favourites landed more often than the model claimed they would —
        it is the calibration test from the record tab, wearing a bankroll.
      </p>

      <div className="mt-3 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
        {s.realized !== null && s.expected !== null ? (
          <div className="space-y-1">
            <Bar tone="said" label="expected" value={s.expected} />
            <Bar tone="landed" label="realized" value={s.realized} />
          </div>
        ) : (
          <p className="text-[12px] text-ink-3">nothing settled yet</p>
        )}

        <div className="num mt-1.5 text-[11px] text-ink-3">
          over {s.n} settled singles
          {s.pending_legs > 0 && <> · {s.pending_legs} still to play</>}
          {s.n !== g.bets_graded && (
            <>
              {" "}
              · {g.bets_graded} inside fully graded windows
            </>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-x-8 gap-y-4 border-t border-line pt-4">
          <Stat
            label="pot"
            value={money(g.pot)}
            sub={`from ${money(g.start_pot)}`}
            colour={g.pot >= g.start_pot ? "text-good" : "text-bad"}
          />
          <Stat
            label="net"
            value={signed(g.net)}
            colour={tone(g.net)}
            sub={`${g.hits}/${g.bets_graded} landed`}
          />
          <Stat
            label="return on stake"
            value={g.roi != null ? pct(g.roi) : "—"}
            colour={tone(g.roi)}
            sub="at frozen fair prices"
          />
          <Stat
            label="staked / back"
            value={`${money(g.staked)} / ${money(g.returned)}`}
            sub={
              g.in_play ? `${money(g.in_play)} still in play` : "nothing in play"
            }
          />
        </div>

        {/* GATE A — the investor plan's own bar, and the only forward-looking
            claim in this section. Printed as distance travelled, because
            "on track" at n=24 toward a target of 150 is a hope, not a pass. */}
        <div className="mt-4 border-t border-line pt-3.5">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
              Gate A
            </span>
            <span className="num text-[11.5px] text-ink-2">
              {g.gate_a.target_n} singles at {pct(g.gate_a.target_acc)} or
              better
            </span>
            <span
              className={`num ml-auto text-[11.5px] font-semibold ${
                g.gate_a.on_track == null
                  ? "text-ink-3"
                  : g.gate_a.on_track
                    ? "text-good"
                    : "text-bad"
              }`}
            >
              {g.gate_a.on_track == null
                ? "nothing to judge yet"
                : g.gate_a.on_track
                  ? "on track"
                  : "off track"}
            </span>
          </div>
          <div className="mt-1.5 h-[7px] overflow-hidden rounded-full bg-[#eef0f2]">
            <div
              className="h-full rounded-full bg-[#4a7ba6]"
              style={{ width: `${Math.max(1, progress * 100)}%` }}
            />
          </div>
          <div className="num mt-1 text-[10.5px] text-ink-3">
            {s.n} of {g.gate_a.target_n} singles — {(progress * 100).toFixed(0)}%
            of the way to a sample worth judging
          </div>
        </div>
      </div>

      {points.length > 1 && (
        <div className="mt-3 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
          <PotCurve points={points} start={g.start_pot} />
        </div>
      )}

      <div className="mt-3 overflow-hidden rounded-xl border border-line bg-card">
        <ul>
          {g.weeks.map((w, i) => {
            const key = `gold|${w.window}|${i}`;
            return (
              <GoldRow
                key={key}
                w={w}
                open={open[key] ?? i === 0}
                onToggle={() =>
                  setOpen((o) => ({ ...o, [key]: !(o[key] ?? i === 0) }))
                }
              />
            );
          })}
          {!g.weeks.length && (
            <li className="px-4 py-4 text-[12.5px] text-ink-3">
              no gold windows committed yet
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

/** The slip book: the headline, what the headline actually is, the curve, the
 *  mandate split, and then every slip. */
function SlipBook({ m }: { m: Book }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const ordered = chronological(m.weeks);
  /** The stake per line is the book's own, not a constant retyped here. */
  const unit = ordered[0]?.unit ?? 10;
  const points: Point[] = [
    { label: "start", pot: m.start_pot, pending: false },
    ...ordered.map((w) => ({
      label: w.window.slice(5, 10),
      pot: w.pot_after,
      pending: w.status !== "graded",
    })),
  ];

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[21px] tracking-[0.01em]">
          The monkey&apos;s book
        </h2>
        <span className="text-[12px] text-ink-3">
          mandate: <span className="text-ink-2">{m.mandate}</span>
        </span>
      </div>

      <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-ink-2">
        Every window, the slip the advisor recommended is placed at{" "}
        {money(unit)} a line from a {money(m.start_pot)} start and graded leg
        by leg once its matches resolve. Nothing is skipped and no week is
        chosen afterwards — this is what following the advice would have done,
        not what it could have done.
      </p>

      {/* THE HEADLINE, AND IMMEDIATELY UNDER IT WHAT THE HEADLINE IS. */}
      <div className="mt-4 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
          <Stat
            label="pot"
            value={money(m.pot)}
            sub={`from ${money(m.start_pot)}`}
            big
            colour={m.pot >= m.start_pot ? "text-good" : "text-bad"}
          />
          <Stat
            label="net"
            value={signed(m.net)}
            sub={`peak ${money(m.peak)}`}
            big
            colour={tone(m.net)}
          />
          <Stat
            label="return on stake"
            value={m.roi != null ? pct(m.roi) : "—"}
            sub="at frozen fair prices"
            big
            colour={tone(m.roi)}
          />
          <Stat
            label="staked / back"
            value={`${money(m.staked)} / ${money(m.returned)}`}
            sub={
              m.in_play ? `${money(m.in_play)} still in play` : "nothing in play"
            }
          />
          <Stat
            label="slips"
            value={`${m.weeks_graded}/${m.weeks_played} graded`}
            sub={`${m.profit_weeks} in profit`}
          />
        </div>

        <p className="mt-4 rounded-lg border border-[#e4d49a] bg-[#faf0cd] px-3 py-2.5 text-[12px] leading-relaxed text-[#6b5606]">
          <b className="font-semibold">
            This return is not a track record, and it is not what a book would
            have paid.
          </b>{" "}
          Every line is settled at the breakeven price frozen when the slip was
          committed — 1 divided by the model&apos;s own probability, with no
          margin in it at all. A real bookmaker pays less than fair on every
          leg, and a system slip multiplies its legs together, so the shortfall
          compounds with each one. What this figure measures is whether the
          probabilities were good enough to beat their own fair price. Whether
          the shape clears a real market is a different question, and this page
          does not answer it.
        </p>
      </div>

      {points.length > 1 && (
        <div className="mt-4 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
            The pot, slip by slip
          </h3>
          <div className="mt-1">
            <PotCurve points={points} start={m.start_pot} />
          </div>
          <p className="text-[11px] leading-relaxed text-ink-3">
            Dashed line is the {money(m.start_pot)} start. A hollow point is a
            slip still in play — its stake has left the pot and nothing has
            come back yet, so that dip is an open position and not a loss.
          </p>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MandateCard
          title="On mandate"
          note="The instrument this pot is supposed to bet: the draw system, one slip per round."
          block={m.on_mandate}
        />
        <MandateCard
          title="Off mandate"
          note="Pre-mandate slips and experiments. Real money, still inside the pot above, scored apart so the strategy's own number stays its own."
          block={m.off_mandate}
        />
      </div>

      <div className="mt-4 overflow-hidden rounded-xl border border-line bg-card">
        <ul>
          {m.weeks.map((w, i) => {
            const key = `slip|${w.window}|${i}`;
            return (
              <SlipRow
                key={key}
                w={w}
                /* Newest slip open by default — it is the one whose legs may
                   not have resolved yet. */
                open={open[key] ?? i === 0}
                onToggle={() =>
                  setOpen((o) => ({ ...o, [key]: !(o[key] ?? i === 0) }))
                }
              />
            );
          })}
          {!m.weeks.length && (
            <li className="px-4 py-4 text-[12.5px] text-ink-3">
              no slips committed yet
            </li>
          )}
        </ul>
      </div>
    </section>
  );
}

export function Monkey() {
  const [book, setBook] = useState<MonkeyBook | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!DEV) return;
    let alive = true;
    getMonkey()
      .then((r) => {
        if (alive) setBook(r);
      })
      .catch((e: unknown) => {
        if (alive) setErr(message(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  if (!DEV) {
    return (
      <p className="text-[13.5px] text-ink-2">
        The betting workbench runs in development only.
      </p>
    );
  }

  if (err) {
    return (
      <div>
        <h2 className="font-display text-[21px] tracking-[0.01em]">
          The monkey&apos;s book
        </h2>
        <p className="mt-3 rounded-lg border border-[#eec4ab] bg-[#fae5d9] px-3 py-2 text-[12px] text-[#a34a22]">
          {err}
        </p>
      </div>
    );
  }

  if (!book) {
    return (
      <div>
        <h2 className="font-display text-[21px] tracking-[0.01em]">
          The monkey&apos;s book
        </h2>
        <p className="mt-2 text-[12.5px] text-ink-3">opening the book…</p>
      </div>
    );
  }

  return (
    <div>
      <SlipBook m={book.monkey} />
      <GoldPot g={book.gold} />

      <p className="mt-3 max-w-3xl text-[11.5px] leading-relaxed text-ink-3">
        Both pots settle at the model&apos;s own fair prices and nothing else:
        no bookmaker odds are fetched, shown or compared against anywhere in
        this section. None of this is betting advice.
      </p>
    </div>
  );
}

export default Monkey;
