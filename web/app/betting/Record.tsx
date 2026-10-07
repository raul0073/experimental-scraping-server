"use client";

import { useEffect, useMemo, useState } from "react";

import { leagueShort } from "@/lib/league";
import { setStored, useStored } from "@/lib/useStored";

import { getLedger, message } from "./api";
import type { Entry, Ledger, PickType, Side } from "./api";

/** What was called, and what happened — the append-only pick ledger, rendered.
 *
 *  WHY THIS IS A CALIBRATION PAGE AND NOT A SCOREBOARD. Every pick here was
 *  committed before the match existed as a result, and the ledger never
 *  rewrites a committed row. That makes one comparison available that a
 *  tipping page can never make: what the model SAID against what actually
 *  LANDED. A hit rate on its own is meaningless for this model — the draw
 *  board states about a third, so a 28% strike is a good month and a 50%
 *  strike means the probabilities are wrong in the other direction. A page
 *  that printed "28%" in large type would be reporting a success as a
 *  failure. So nothing here shows a landed figure without its stated figure
 *  beside it, on the same track, at the same size.
 *
 *  THE NOISE BAND IS PART OF THE NUMBER. Twenty-four graded picks is not a
 *  track record, it is a start: at n=12, one standard error on a 32% claim is
 *  about thirteen points — wider than any gap this table can currently show.
 *  Printing the gap without that band would dress sampling noise up as
 *  evidence, which is the exact failure this page exists to avoid. Every
 *  bucket carries its own ±, and buckets thinner than ten observations are
 *  dimmed and say so.
 *
 *  PENDING PICKS STAY ON SCREEN. Filtering to graded rows would quietly turn
 *  the ledger into a list of settled bets, and the oldest way to flatter a
 *  record is to let the open positions fall off the bottom. They are shown as
 *  pending, counted as committed, and excluded only from the landed
 *  arithmetic, where they genuinely have no place yet.
 *
 *  THE SUMMARY BLOCK IS NOT READ, AND THAT IS DELIBERATE. The API returns
 *  per-type counts alongside the rows, and they agree with the rows today.
 *  Counting the rows here means "said" and "landed" are always two readings
 *  of one set of entries — a page built on the summary would print a
 *  disagreement between them as fact, and this page shows the entries it is
 *  also tabulating underneath.
 *
 *  NO ODDS, ANYWHERE. The one price on this page is the breakeven — 1/p, the
 *  model's own fair value. Nothing is fetched from, or compared against, a
 *  bookmaker.
 *
 *  DEVELOPMENT ONLY. The real guard is layout.tsx, which stops this route
 *  being emitted at all; the check below is the second one, as on the admin
 *  panel.
 */
const DEV = process.env.NODE_ENV === "development";
const KEY = "predictorous:betting-record-type";

/** Below this, a percentage is noise wearing a decimal point. */
const THIN = 10;

/** Spelled as mapped types rather than with the `Record` utility, which this
 *  component's own name sits uncomfortably close to — the same reason
 *  page.tsx spells its labels out. */
const MARK: { [K in PickType]: string } = { home: "1", draw: "X", away: "2" };

const MARK_STYLE: { [K in PickType]: string } = {
  home: "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]",
  draw: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  away: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
};

const TYPE_LABEL: { [K in PickType]: string } = {
  draw: "draw board",
  home: "home wins",
  away: "away wins",
};

const TYPES = Object.keys(TYPE_LABEL) as PickType[];
const SIDES: Side[] = ["home", "draw", "away"];

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const pts = (v: number) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)}`;

/** What actually happened. The graded row carries `outcome`, but the oldest
 *  rows predate it, so the scoreline is the fallback — and reading it back off
 *  the score the cell beside it prints keeps the two from ever disagreeing. */
function outcomeOf(e: Entry): Side | null {
  if (e.outcome) return e.outcome;
  const m = /^\s*(\d+)\s*-\s*(\d+)\s*$/.exec(e.score ?? "");
  if (!m) return null;
  const h = Number(m[1]);
  const a = Number(m[2]);
  return h > a ? "home" : a > h ? "away" : "draw";
}

type Stats = {
  committed: number;
  graded: number;
  pending: number;
  hits: number;
  said: number | null;
  landed: number | null;
  /** One standard error on the stated probability at this sample size — the
   *  width of the band inside which said and landed agreeing, or disagreeing,
   *  means nothing at all. */
  se: number | null;
};

function statsFor(rows: Entry[]): Stats {
  const graded = rows.filter((r) => r.status === "graded");
  const hits = graded.filter((r) => r.hit === true).length;
  const n = graded.length;
  const said = n ? graded.reduce((s, r) => s + r.pick_prob, 0) / n : null;
  return {
    committed: rows.length,
    graded: n,
    pending: rows.length - n,
    hits,
    said,
    landed: n ? hits / n : null,
    se: said !== null && n ? Math.sqrt((said * (1 - said)) / n) : null,
  };
}

/** Said against landed, two bars on one 0–100 track. The comparison IS the
 *  claim, so neither bar is allowed to become the caption of the other. */
function Bar({
  tone,
  label,
  value,
}: {
  tone: "said" | "landed";
  label: string;
  value: number;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-[46px] shrink-0 text-right text-[10.5px] text-ink-3">
        {label}
      </span>
      <div className="h-[7px] flex-1 overflow-hidden rounded-full bg-[#eef0f2]">
        <div
          className={`h-full rounded-full ${
            tone === "said" ? "bg-[#b9d5e8]" : "bg-[#1c5b8a]"
          }`}
          style={{ width: `${Math.max(1, Math.min(100, value * 100))}%` }}
        />
      </div>
      <span
        className={`num w-[48px] shrink-0 text-right text-[11.5px] ${
          tone === "landed" ? "font-semibold text-ink" : "text-ink-3"
        }`}
      >
        {pct(value)}
      </span>
    </div>
  );
}

function Pill({ type, rank }: { type: PickType; rank?: number }) {
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span
        className={`inline-block min-w-[22px] rounded-full border px-2 py-0.5 text-center text-[11.5px] font-semibold ${MARK_STYLE[type]}`}
      >
        {MARK[type]}
      </span>
      {rank != null && (
        <span className="num text-[10.5px] text-ink-3">#{rank}</span>
      )}
    </span>
  );
}

function Verdict({ e }: { e: Entry }) {
  if (e.status !== "graded") {
    return (
      <span className="rounded-full border border-line bg-[#fafbfc] px-2 py-0.5 text-[10.5px] uppercase tracking-wider text-ink-3">
        pending
      </span>
    );
  }
  return e.hit === true ? (
    <span className="font-semibold text-good">✓</span>
  ) : (
    <span className="font-semibold text-bad">✗</span>
  );
}

/** A row graded through the fallback match: fbref flipped the venue or
 *  renamed the club after the pick was committed. Small, but it has to be
 *  visible — it is the one case where the fixture on screen is not quite the
 *  fixture that was played. */
function Note({ note }: { note?: string }) {
  if (!note) return null;
  return (
    <span
      className="ml-1 cursor-help text-[10.5px] text-[#6b5606]"
      title={note}
    >
      ⚑
    </span>
  );
}

/** One ledger row, as a card. Below `sm` the nine-column table becomes a
 *  horizontal scroll with the fixture pushed off the left edge — the one
 *  column you need in order to read the rest is the first to leave. Nothing
 *  is dropped: every figure in the table is in here. */
function Card({ e }: { e: Entry }) {
  const got = outcomeOf(e);
  const xh = e.xg[e.home];
  const xa = e.xg[e.away];
  return (
    <li className="border-t border-line px-4 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="num text-[11.5px] text-ink-3">
          {e.kickoff} · {leagueShort(e.league)} · wk {e.week}
        </span>
        <Verdict e={e} />
      </div>

      <div className="mt-1 flex items-baseline justify-between gap-2">
        <span className="text-[13.5px]">
          {e.home} <span className="text-ink-3">v</span> {e.away}
          <Note note={e.note} />
        </span>
        <Pill type={e.pick_type} rank={e.rank} />
      </div>

      {xh != null && xa != null && (
        <div className="num mt-0.5 text-[10.5px] text-ink-3">
          xG {xh.toFixed(2)}–{xa.toFixed(2)}
        </div>
      )}

      <div className="num mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[12px]">
        <span>
          said <b className="font-semibold text-ink">{pct(e.pick_prob)}</b>
          <span className="text-ink-3">
            {" "}
            · fair {(1 / e.pick_prob).toFixed(2)}
          </span>
        </span>
        <span className="text-ink-2">
          {SIDES.map((s) => (
            <span key={s}>
              {s !== "home" && <span className="text-ink-3"> / </span>}
              <span className={got === s ? "font-semibold text-ink" : ""}>
                {Math.round(e.probabilities[s] * 100)}
              </span>
            </span>
          ))}
          <span className="text-ink-3"> (1/X/2)</span>
        </span>
        <span className="ml-auto">
          {e.score ? (
            <b className="font-semibold text-ink">{e.score}</b>
          ) : (
            <span className="text-ink-3">not played</span>
          )}
        </span>
      </div>

      <div className="num mt-1 text-[10.5px] text-ink-3">
        committed {e.committed_at.slice(0, 10)}
      </div>
    </li>
  );
}

function Row({ e }: { e: Entry }) {
  const got = outcomeOf(e);
  const xh = e.xg[e.home];
  const xa = e.xg[e.away];
  return (
    <tr className="border-t border-line align-top">
      <td className="whitespace-nowrap py-2.5 pl-4 pr-3">
        <div className="num text-[12px] text-ink-2">{e.kickoff}</div>
        <div
          className="num text-[10.5px] text-ink-3"
          title={`committed ${e.committed_at}`}
        >
          wk {e.week} · said {e.committed_at.slice(5, 10)}
        </div>
      </td>

      <td className="py-2.5 pr-3">
        <div className="text-[13px]">
          {e.home} <span className="text-ink-3">v</span> {e.away}
          <Note note={e.note} />
        </div>
        <div className="num text-[10.5px] text-ink-3">
          {leagueShort(e.league)}
          {xh != null && xa != null && (
            <>
              {" "}
              · xG {xh.toFixed(2)}–{xa.toFixed(2)}
            </>
          )}
        </div>
      </td>

      <td className="whitespace-nowrap px-3 py-2.5 text-center">
        <Pill type={e.pick_type} rank={e.rank} />
      </td>

      <td className="px-3 py-2.5 text-center">
        <div className="num text-[13.5px] font-semibold text-ink">
          {pct(e.pick_prob)}
        </div>
        <div className="num text-[10.5px] text-ink-3">
          fair {(1 / e.pick_prob).toFixed(2)}
        </div>
      </td>

      {/* The triplet as committed, with the outcome that happened picked out
          — the row is then readable as a calibration observation rather than
          as a win or a loss. */}
      {SIDES.map((s) => (
        <td
          key={s}
          className={`num px-2 py-2.5 text-center text-[12.5px] ${
            got === s
              ? "bg-[#fafbfc] font-semibold text-ink"
              : "text-ink-3"
          }`}
          title={got === s ? "this is what happened" : undefined}
        >
          {Math.round(e.probabilities[s] * 100)}
        </td>
      ))}

      <td className="num whitespace-nowrap px-3 py-2.5 text-center text-[13px]">
        {e.score ?? <span className="text-ink-3">—</span>}
      </td>

      <td className="py-2.5 pl-2 pr-4 text-center text-[13px]">
        <Verdict e={e} />
      </td>
    </tr>
  );
}

export function Record() {
  const [d, setD] = useState<Ledger | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!DEV) return;
    let alive = true;
    getLedger()
      .then((r) => {
        if (alive) setD(r);
      })
      .catch((e: unknown) => {
        if (alive) setErr(message(e));
      });
    return () => {
      alive = false;
    };
  }, []);

  /** The chosen pick type survives the visit: somebody reading the draw board
   *  this week is reading it next week too. */
  const filter = useStored(KEY, "all");

  const entries: Entry[] = d?.entries ?? [];

  const sorted = useMemo(
    () =>
      [...entries].sort(
        (a, b) =>
          b.committed_at.localeCompare(a.committed_at) ||
          a.kickoff.localeCompare(b.kickoff) ||
          a.rank - b.rank,
      ),
    [entries],
  );

  const groups = useMemo(() => {
    const all = { key: "all", label: "every pick", rows: entries };
    const byType = TYPES.map((t) => ({
      key: t as string,
      label: TYPE_LABEL[t],
      rows: entries.filter((e) => e.pick_type === t),
    }));
    return [all, ...byType]
      .filter((g) => g.rows.length)
      .map((g) => ({ ...g, s: statsFor(g.rows) }));
  }, [entries]);

  if (!DEV) {
    return (
      <p className="text-[13.5px] text-ink-2">
        The betting workbench runs in development only.
      </p>
    );
  }

  const shown =
    filter === "all" ? sorted : sorted.filter((e) => e.pick_type === filter);
  const overall = groups.find((g) => g.key === "all")?.s;

  return (
    <section>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-[21px] tracking-[0.01em]">
          The record
        </h2>
        {overall && (
          <span className="num flex flex-wrap items-center gap-x-2.5 text-[12px] text-ink-2">
            <span>
              <b className="font-semibold text-ink">{overall.committed}</b>{" "}
              committed
            </span>
            <span className="text-ink-3">·</span>
            <span>
              <b className="font-semibold text-ink">{overall.graded}</b> graded
            </span>
            {overall.pending > 0 && (
              <>
                <span className="text-ink-3">·</span>
                <span>
                  <b className="font-semibold text-ink">{overall.pending}</b>{" "}
                  pending
                </span>
              </>
            )}
            {overall.said !== null && overall.landed !== null && (
              <>
                <span className="text-ink-3">·</span>
                <span>
                  said{" "}
                  <b className="font-semibold text-ink">
                    {pct(overall.said)}
                  </b>
                  , landed{" "}
                  <b className="font-semibold text-ink">
                    {pct(overall.landed)}
                  </b>
                </span>
              </>
            )}
          </span>
        )}
      </div>

      <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-ink-2">
        Every row was committed before the match was played and has not been
        touched since. The question is not how many landed — the draw board
        states about a third and is supposed to miss two in three. The question
        is whether the stated probability was honest, so each bucket below
        prints what was said next to what happened, at the same size.
      </p>

      {err && (
        <p className="mt-3 rounded-lg border border-[#eec4ab] bg-[#fae5d9] px-3 py-2 text-[12px] text-[#a34a22]">
          {err}
        </p>
      )}

      {!d && !err && (
        <p className="mt-3 text-[12.5px] text-ink-3">reading the ledger…</p>
      )}

      {/* SAID AGAINST LANDED, per instrument. */}
      {groups.length > 0 && (
        <div className="mt-4 space-y-4 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
          {groups.map((g) => {
            const thin = g.s.graded < THIN;
            const gap =
              g.s.said !== null && g.s.landed !== null
                ? g.s.landed - g.s.said
                : null;
            return (
              <div
                key={g.key}
                className={thin ? "opacity-50" : undefined}
                title={
                  thin
                    ? `${g.s.graded} graded — too few to read anything into`
                    : undefined
                }
              >
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-[12.5px] font-semibold text-ink">
                    {g.label}
                  </span>
                  <span className="num text-[11px] text-ink-3">
                    {g.s.hits}/{g.s.graded} graded
                    {g.s.pending > 0 && <> · {g.s.pending} pending</>}
                  </span>
                  {gap !== null && g.s.se !== null && (
                    <span className="num text-[11px] text-ink-3">
                      gap {pts(gap)} pts · ±{(g.s.se * 100).toFixed(1)} (1 s.e.)
                    </span>
                  )}
                  {thin && (
                    <span className="text-[10.5px] uppercase tracking-wider text-ink-3">
                      too thin to read
                    </span>
                  )}
                </div>
                {g.s.said !== null && g.s.landed !== null ? (
                  <div className="space-y-1">
                    <Bar tone="said" label="said" value={g.s.said} />
                    <Bar tone="landed" label="landed" value={g.s.landed} />
                  </div>
                ) : (
                  <p className="text-[11.5px] text-ink-3">
                    nothing graded yet — {g.s.pending} in play
                  </p>
                )}
              </div>
            );
          })}

          <p className="border-t border-line pt-3 text-[11.5px] leading-relaxed text-ink-3">
            The ± is one standard error on the stated probability at this
            sample size. A gap smaller than it is noise — not skill, and not
            failure. At these counts almost every gap on this page is smaller
            than it, which is the honest reading of two months of picks.
          </p>
        </div>
      )}

      {/* THE ROWS. */}
      {entries.length > 0 && (
        <>
          <div className="mt-5 flex flex-wrap items-center gap-1.5">
            {groups.map((g) => (
              <button
                key={g.key}
                onClick={() => setStored(KEY, g.key)}
                aria-pressed={filter === g.key}
                className={`cursor-pointer rounded-full border px-2.5 py-0.5 text-[11.5px] transition-colors ${
                  filter === g.key
                    ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                    : "border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink"
                }`}
              >
                {g.label}
                <span className="num text-ink-3"> {g.rows.length}</span>
              </button>
            ))}
          </div>

          <div className="mt-2.5 overflow-hidden rounded-xl border border-line bg-card">
            {/* Laptop: the full nine columns. */}
            <table className="hidden w-full text-[13px] sm:table">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-3 text-left font-semibold">
                    Kickoff
                  </th>
                  <th className="py-2 pr-3 text-left font-semibold">Fixture</th>
                  <th className="px-3 py-2 text-center font-semibold">Pick</th>
                  <th className="px-3 py-2 text-center font-semibold">Said</th>
                  <th className="px-2 py-2 text-center font-semibold">1</th>
                  <th className="px-2 py-2 text-center font-semibold">X</th>
                  <th className="px-2 py-2 text-center font-semibold">2</th>
                  <th className="px-3 py-2 text-center font-semibold">
                    Result
                  </th>
                  <th className="py-2 pl-2 pr-4 text-center font-semibold">
                    Hit
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((e, i) => (
                  <Row
                    key={`${e.committed_at}|${e.pick_type}|${e.rank}|${i}`}
                    e={e}
                  />
                ))}
              </tbody>
            </table>

            {/* Phone: the same rows as cards. */}
            <ul className="sm:hidden">
              {shown.map((e, i) => (
                <Card
                  key={`${e.committed_at}|${e.pick_type}|${e.rank}|${i}`}
                  e={e}
                />
              ))}
            </ul>
          </div>
        </>
      )}

      <p className="mt-3 max-w-3xl text-[11.5px] leading-relaxed text-ink-3">
        <b className="font-semibold text-ink-2">Fair</b> is the breakeven price
        — 1 divided by the stated probability. It is the model&apos;s own
        number and nothing else: no bookmaker price is fetched, displayed or
        compared against anywhere in this section. None of this is betting
        advice.
      </p>
    </section>
  );
}

export default Record;
