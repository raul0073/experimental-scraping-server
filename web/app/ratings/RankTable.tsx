"use client";

/** THE RANKING — one row per manager spell.
 *
 *  Two renderings of one list, chosen by width. A table of fourteen columns
 *  is the right shape on a laptop and an unusable shape on a phone, so below
 *  the `sm` breakpoint the same rows come out as cards with an explicit sort
 *  control. Nothing is hidden on the small version except the grid lines.
 *
 *  THE SHORT SPELL IS THE THING THIS COMPONENT HAS TO GET RIGHT. A caretaker
 *  is not excluded — he is shrunk toward 50 on how many matches he had — and
 *  a reader who sees a caretaker at 52 must be able to see instantly that it
 *  is 52 because there is very little evidence, not because he was ordinary.
 *  So the score cell carries BOTH numbers: the raw weighted percentile and
 *  what survived, with the arrow between them, and the row carries a badge.
 */

import Link from "next/link";

import { Crest } from "../components/Crest";
import { Info } from "../components/Info";
import { SPREAD_TEAM, ScoreRing, tint } from "./scoreUi";
import {
  type ManagerRow,
  type Metric,
  type Scored,
  type Slot,
  PICK_COLOR,
  fmtRaw,
  keptOf,
  orient,
  rowId,
  shortLabel,
  slugify,
} from "./contract";

export type Row = ManagerRow & { s: Scored | null };
export type Sort = { key: string; dir: 1 | -1 };

export const SORT_LABELS: Record<string, string> = {
  score: "Score",
  manager: "Manager",
  team: "Club",
  matches: "Matches",
  kept: "Evidence kept",
};

/** A sortable header that also carries its explanation. The info icon stops
 *  the click, so reaching for the popover never re-sorts the table under the
 *  reader's hand. */
function Th({
  k,
  sort,
  setSort,
  children,
  info,
  align = "center",
  className = "",
}: {
  k: string;
  sort: Sort;
  setSort: (s: Sort) => void;
  children: React.ReactNode;
  info?: React.ReactNode;
  align?: "left" | "center" | "right";
  className?: string;
}) {
  const active = sort.key === k;
  return (
    <th
      onClick={() =>
        setSort({
          key: k,
          // A fresh column opens best-first, which is what anyone reading a
          // ranking wants; the two name columns open A-Z instead.
          dir: active
            ? ((sort.dir * -1) as 1 | -1)
            : k === "manager" || k === "team"
              ? 1
              : -1,
        })
      }
      className={`cursor-pointer select-none whitespace-nowrap px-2.5 py-2 font-semibold transition-colors hover:text-ink ${
        align === "left" ? "text-left" : align === "right" ? "text-right" : "text-center"
      } ${active ? "text-ink" : ""} ${className}`}
    >
      <span className="inline-flex items-center">
        {children}
        <span className={active ? "" : "opacity-0"}> {sort.dir === -1 ? "▾" : "▴"}</span>
        {info && (
          <span onClick={(e) => e.stopPropagation()}>
            <Info>{info}</Info>
          </span>
        )}
      </span>
    </th>
  );
}

/** How much of the distance from average survived the evidence test, as a
 *  bar. A number on its own reads as a quality; the bar reads as a fraction,
 *  which is what it is. */
function KeptBar({ kept, matches }: { kept: number; matches: number }) {
  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={`${matches} matches keeps ${(kept * 100).toFixed(0)}% of the distance from average. Everything not kept is pulled back to 50, because a short spell is thin evidence and the score says so rather than hiding it.`}
    >
      <span className="relative block h-1.5 w-8 overflow-hidden rounded-full bg-[#eef0f2]">
        <span
          className="absolute left-0 top-0 h-full rounded-full bg-[#8a949e]"
          style={{ width: `${Math.max(0, Math.min(1, kept)) * 100}%` }}
        />
      </span>
      <span className="num text-[11.5px] text-ink-3">
        {(kept * 100).toFixed(0)}%
      </span>
    </span>
  );
}

/** The ring is the score after shrinkage. The ghost beside it is where it
 *  came from, shown only when the two differ enough to be worth a reader's
 *  attention — on a full season they are within a point or two and a second
 *  number would be noise. */
function ScoreCell({ s, row }: { s: Scored | null; row: ManagerRow }) {
  if (!s) {
    return (
      <span
        className="text-[12px] text-ink-3"
        title="No weight is on any metric this spell has data for. Give something weight in the panel above, or the spell has none of the metrics you chose."
      >
        —
      </span>
    );
  }
  const moved = Math.abs(s.raw - s.final) >= 2.5;
  const thin = s.covered < 0.999;
  // A GRID, NOT A FLEX ROW. The ghost and the thin-coverage mark appear on
  // some rows and not others, and in a flex row that moved the ring itself —
  // so the one number every reader scans down the column was never in the
  // same place twice. Fixed tracks keep the ring on one axis and let the
  // annotations vary beside it.
  return (
    <span className="inline-grid grid-cols-[auto_2.5rem] items-center gap-1">
      <ScoreRing score={s.final} spread={SPREAD_TEAM} decimals={1} />
      <span className="flex items-center gap-0.5 text-left">
      {moved && (
        <span
          className="num text-[11px] text-ink-3"
          title={`Raw ${s.raw.toFixed(1)} on your weights, pulled to ${s.final.toFixed(1)} because ${row.matches} matches is ${(100 - 100 * keptOf(row)).toFixed(0)}% short of the evidence a full spell carries.${typeof row.score === "number" ? ` As published, on the pipeline's own weights: ${row.score.toFixed(1)}.` : ""}`}
        >
          {s.raw.toFixed(0)}→
        </span>
      )}
      {thin && (
        <span
          className="text-[10px] text-[#9a7400]"
          title={`Only ${(s.covered * 100).toFixed(0)}% of the weight you spent has data on this spell. The rest was dropped and what remained renormalised — never filled in at average.`}
        >
          ◐
        </span>
      )}
      </span>
    </span>
  );
}

function ShortBadge() {
  return (
    <span
      className="ml-1.5 shrink-0 whitespace-nowrap rounded border border-[#e2cc8f] bg-[#fdf8ea] px-1 py-px text-[10px] font-normal text-[#8a6d1f]"
      title="A short spell. It is not excluded — it is shrunk hard toward 50, because a handful of matches cannot tell a good manager from a lucky fortnight. The evidence column says how hard."
    >
      short
    </span>
  );
}

function PickButtons({
  id,
  pick,
  onPick,
}: {
  id: string;
  pick: Record<Slot, string | null>;
  onPick: (slot: Slot, id: string) => void;
}) {
  return (
    <span className="inline-flex gap-1">
      {(["a", "b"] as const).map((slot) => {
        const on = pick[slot] === id;
        return (
          <button
            key={slot}
            onClick={() => onPick(slot, id)}
            aria-pressed={on}
            title={
              on
                ? `Showing as ${slot.toUpperCase()} in the fingerprint — click to clear`
                : `Show this spell as ${slot.toUpperCase()} in the fingerprint below`
            }
            className="h-5 w-5 rounded border text-[10px] font-semibold leading-none transition-colors"
            style={
              on
                ? {
                    borderColor: PICK_COLOR[slot],
                    background: PICK_COLOR[slot],
                    color: "#fff",
                  }
                : { borderColor: "var(--color-line)", color: "var(--color-ink-3)" }
            }
          >
            {slot.toUpperCase()}
          </button>
        );
      })}
    </span>
  );
}

function MetricCell({ row, m }: { row: ManagerRow; m: Metric }) {
  const raw = row.raw?.[m.key];
  const p = orient(row.pct?.[m.key], m);
  return (
    <td
      className="num px-2.5 py-2 text-right text-[12.5px] tabular-nums"
      style={{ background: tint(p) }}
      title={
        p === undefined
          ? `${m.label}: not computable for this spell`
          : `${m.label}: ${fmtRaw(raw, m.unit)}${m.unit ? " " + m.unit : ""} — ${p.toFixed(0)} of 100 in this league${m.invert ? ", counting down, because lower is better" : ""}`
      }
    >
      {fmtRaw(raw, m.unit)}
    </td>
  );
}

export function RankTable({
  rows,
  directional,
  sort,
  setSort,
  pick,
  onPick,
  crests,
  rankOf,
}: {
  rows: Row[];
  directional: Metric[];
  sort: Sort;
  setSort: (s: Sort) => void;
  pick: Record<Slot, string | null>;
  onPick: (slot: Slot, id: string) => void;
  crests: Record<string, string>;
  /** Position in the UNFILTERED table. The # column was the loop index, so
   *  filtering to three clubs numbered them 1, 2, 3 and a manager lying
   *  fortieth read as second. A rank is a fact about the league, not about
   *  what happens to be on screen. */
  rankOf?: Map<Row, number>;
}) {
  const rank = (r: Row, i: number) => rankOf?.get(r) ?? i + 1;
  if (!rows.length) {
    return (
      <p className="mt-6 rounded-xl border border-line bg-card p-4 text-[13.5px] text-ink-2">
        No spell in this league has enough behind it to rank.
      </p>
    );
  }

  const clubLink = (r: ManagerRow) => (
    <Link
      href={`/team/${slugify(r.team)}`}
      className="inline-flex items-center gap-1.5 hover:text-home hover:underline"
    >
      <Crest src={crests[r.team]} alt="" size={16} />
      {r.team}
    </Link>
  );

  return (
    <>
      {/* ================================================= phone: cards */}
      <div className="sm:hidden">
        <label className="mt-4 flex items-center gap-2 text-[12.5px] text-ink-2">
          sort by
          <select
            value={sort.key}
            onChange={(e) =>
              setSort({
                key: e.target.value,
                dir: e.target.value === "manager" || e.target.value === "team" ? 1 : -1,
              })
            }
            className="min-w-0 flex-1 rounded-md border border-line bg-card px-2 py-1"
          >
            {Object.entries(SORT_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
            {directional.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => setSort({ ...sort, dir: (sort.dir * -1) as 1 | -1 })}
            aria-label="reverse the order"
            className="shrink-0 rounded-md border border-line bg-card px-2 py-1 text-[12px]"
          >
            {sort.dir === -1 ? "▾" : "▴"}
          </button>
        </label>

        <ul className="mt-3 space-y-2.5">
          {rows.map((r, i) => {
            const id = rowId(r);
            return (
              <li
                key={id}
                className="rounded-xl border border-line bg-card p-3"
                style={
                  pick.a === id || pick.b === id
                    ? {
                        borderColor: PICK_COLOR[pick.a === id ? "a" : "b"],
                      }
                    : undefined
                }
              >
                <div className="flex items-start gap-2.5">
                  <span className="num pt-1 text-[12px] text-ink-3">{rank(r, i)}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-baseline text-[14px] font-medium">
                      <span className="truncate">{r.manager}</span>
                      {r.short && <ShortBadge />}
                    </div>
                    <div className="mt-0.5 truncate text-[12.5px] text-ink-2">
                      {clubLink(r)}
                    </div>
                    <div className="num mt-0.5 text-[11.5px] text-ink-3">
                      {r.matches} matches · {r.start?.slice(0, 7)} →{" "}
                      {r.end?.slice(0, 7)}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5">
                    <ScoreCell s={r.s} row={r} />
                    <PickButtons id={id} pick={pick} onPick={onPick} />
                  </div>
                </div>

                <div className="mt-2 flex items-center gap-2 border-t border-line pt-2 text-[11.5px] text-ink-3">
                  <span>evidence kept</span>
                  <KeptBar kept={keptOf(r)} matches={r.matches} />
                </div>

                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                  {directional.map((m) => {
                    const p = orient(r.pct?.[m.key], m);
                    return (
                      <div
                        key={m.key}
                        className="flex min-w-0 items-baseline justify-between gap-2 rounded px-1.5 py-0.5"
                        style={{ background: tint(p) }}
                      >
                        <dt className="min-w-0 truncate text-[11.5px] text-ink-2">
                          {shortLabel(m)}
                          {m.invert ? " ↓" : ""}
                        </dt>
                        <dd className="num shrink-0 text-[12px]">
                          {fmtRaw(r.raw?.[m.key], m.unit)}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </li>
            );
          })}
        </ul>
      </div>

      {/* ================================================= laptop: table */}
      <div className="mt-4 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-3 pr-1 text-left font-semibold">#</th>
              <Th k="manager" sort={sort} setSort={setSort} align="left" className="pr-2">
                Manager
              </Th>
              <Th k="team" sort={sort} setSort={setSort} align="left" className="pr-2">
                Club
              </Th>
              <Th
                k="score"
                sort={sort}
                setSort={setSort}
                info={
                  <>
                    <b className="text-ink">Your weights, not ours.</b> The
                    weighted mean of this spell&apos;s percentiles within this
                    league, then pulled toward 50 by how many matches it rests
                    on. Where the shrinkage moved it, the cell shows both
                    numbers. Percentiles are computed inside one league only —
                    the event feed is the same across Europe but the football
                    is not.
                  </>
                }
              >
                Score
              </Th>
              <Th
                k="kept"
                sort={sort}
                setSort={setSort}
                info={
                  <>
                    <b className="text-ink">How much evidence survived.</b> A
                    38-match spell keeps 83% of its distance from average, a
                    four-match caretaker 33%. Nobody is excluded for being
                    brief; a brief spell simply cannot move far from the middle,
                    and this column is why.
                  </>
                }
              >
                Kept
              </Th>
              <Th k="matches" sort={sort} setSort={setSort}>
                Mt
              </Th>
              {directional.map((m) => (
                <Th
                  key={m.key}
                  k={m.key}
                  sort={sort}
                  setSort={setSort}
                  align="right"
                  info={
                    <>
                      <b className="text-ink">{m.label}</b>
                      {m.unit ? ` (${m.unit})` : ""}. {m.help}
                      {m.invert && (
                        <>
                          {" "}
                          <b className="text-ink">Lower is better</b>, so
                          sorting this column still puts the best at the top and
                          the wash of colour still runs blue where the spell
                          leads its league.
                        </>
                      )}
                    </>
                  }
                >
                  {shortLabel(m)}
                  {m.invert ? " ↓" : ""}
                </Th>
              ))}
              <th className="py-2 pl-1 pr-3 text-center font-semibold">Cf</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const id = rowId(r);
              const on = pick.a === id ? "a" : pick.b === id ? "b" : null;
              return (
                <tr
                  key={id}
                  className="border-t border-line hover:bg-[#fafbfc]"
                  style={on ? { background: `${PICK_COLOR[on]}12` } : undefined}
                >
                  <td className="num py-2 pl-3 pr-1 text-ink-3">{rank(r, i)}</td>
                  <td className="whitespace-nowrap py-2 pr-2 font-medium">
                    {r.manager}
                    {r.short && <ShortBadge />}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-2">{clubLink(r)}</td>
                  <td className="px-2.5 py-1.5 text-ink">
                    <div className="flex justify-center">
                      <ScoreCell s={r.s} row={r} />
                    </div>
                  </td>
                  <td className="px-2.5 py-2 text-center">
                    <KeptBar kept={keptOf(r)} matches={r.matches} />
                  </td>
                  <td
                    className="num px-2 py-2 text-center text-[12px] text-ink-3"
                    title={`${r.start} → ${r.end}${r.seasons?.length ? ` (${r.seasons.join(", ")})` : ""}`}
                  >
                    {r.matches}
                  </td>
                  {directional.map((m) => (
                    <MetricCell key={m.key} row={r} m={m} />
                  ))}
                  <td className="py-2 pl-1 pr-3 text-center">
                    <PickButtons id={id} pick={pick} onPick={onPick} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
        A cell&apos;s wash of colour is where the spell sits in{" "}
        <em>this league</em>, blue where it leads and warm where it trails, and
        it reads the same way on a metric where lower is better. The number
        beside it is always the plain value: the colour is a second encoding of
        something already legible, never the reading itself.
      </p>
    </>
  );
}
