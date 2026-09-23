"use client";

import Link from "next/link";

// TYPES ONLY from lib/data — it opens node:fs at import time, so a value
// import here would pull the filesystem into the browser bundle and fail the
// build. leagueShort therefore comes from lib/league, which is pure.
import type { Crests, Fixture, Outcome, RoundData } from "@/lib/data";
import { leagueShort } from "@/lib/league";
import { setStored, useStored } from "@/lib/useStored";

import { Crest } from "../components/Crest";

/** The round, one league at a time.
 *
 *  FIVE STACKED TABLES WAS A SCROLL, NOT A PAGE. Thirty fixtures in five
 *  sections meant the Ligue 1 reader scrolled past four leagues they did not
 *  ask about, every week, and nobody could see a whole league without the
 *  header leaving the screen. A pill row costs one click and makes every
 *  league the top of the page.
 *
 *  THE CHOICE PERSISTS. Somebody who follows one league follows it next week
 *  too; making them re-pick every visit is the same failure as re-scrolling.
 *  Stored per browser, and a stored league that no longer exists in the
 *  payload falls back rather than rendering nothing.
 */
const KEY = "predictorous:league";

const CALL_STYLE: Record<Outcome, string> = {
  home: "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]",
  draw: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  away: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
};

const OUTCOMES: { key: Outcome; mark: string }[] = [
  { key: "home", mark: "1" },
  { key: "draw", mark: "X" },
  { key: "away", mark: "2" },
];

/** Probability and the price it is worth, as one cell. The number people
 *  act on is the price, so it sits under the percentage rather than in a
 *  separate column they have to re-align themselves. */
function Odds({ f, o }: { f: Fixture; o: Outcome }) {
  const called = f.call === o;
  return (
    <td className={`px-3 py-2.5 text-center ${called ? "bg-[#fafbfc]" : ""}`}>
      <div
        className={`num text-[14px] ${called ? "font-semibold text-ink" : "text-ink-2"}`}
      >
        {Math.round(f.p[o])}%
      </div>
      <div className="num text-[11.5px] text-ink-3">{f.fair[o].toFixed(2)}</div>
    </td>
  );
}

/** EVERY ROW IS A DOOR NOW. A probability with no working shown is the
 *  least trustworthy thing on the site; the fixture page is where the
 *  working is, so the table that states the number links to it. */
function Row({
  f, crests, league,
}: {
  f: Fixture; crests: Crests; league: string;
}) {
  const logos = crests.teams[league] ?? {};
  const href = `/versus?home=${encodeURIComponent(f.home)}&away=${encodeURIComponent(f.away)}`;
  return (
    <tr className="border-t border-line transition-colors hover:bg-[#fafbfc]">
      <td className="whitespace-nowrap py-2.5 pl-4 pr-3 text-[12px] text-ink-3">
        {f.date.slice(5)}
      </td>
      <td className="py-2.5 pr-2 text-right">
        <Link href={href} className="inline-flex items-center gap-2 hover:underline">
          {f.home}
          <Crest src={logos[f.home]} alt="" />
        </Link>
      </td>
      {/* 🐛 THIS COLUMN USED TO SHOW THE PREDICTED SCORELINE UNDER THE
          HEADING "Score". On a Sunday, looking at Saturday's fixtures, that
          reads as the result — the page said 1-1 for a match that finished
          3-0 and quietly buried its own miss. The result is the headline
          once there is one; what we expected moves underneath it. */}
      <td className="px-3 py-2.5 text-center">
        {f.played ? (
          <>
            <div className="num text-[14px] font-semibold text-ink">
              {f.played}
            </div>
            <div className="num text-[10.5px] text-ink-3">said {f.score}</div>
          </>
        ) : (
          <span className="num text-[13px] text-ink-3">{f.score}</span>
        )}
      </td>
      <td className="py-2.5 pl-2">
        <Link href={href} className="inline-flex items-center gap-2 hover:underline">
          <Crest src={logos[f.away]} alt="" />
          {f.away}
        </Link>
      </td>
      <td className="px-4 py-2.5 text-center">
        <span
          className={`inline-block min-w-[22px] rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${CALL_STYLE[f.call]}`}
        >
          {OUTCOMES.find((o) => o.key === f.call)?.mark}
        </span>
        {f.outcome && (
          <div
            className={`mt-0.5 text-[10.5px] font-semibold ${
              f.outcome === f.call ? "text-good" : "text-bad"
            }`}
          >
            {f.outcome === f.call ? "hit" : "miss"}
          </div>
        )}
      </td>
      {OUTCOMES.map((o) => (
        <Odds key={o.key} f={f} o={o.key} />
      ))}
      <td className="num whitespace-nowrap py-2.5 pl-3 pr-4 text-right text-[12px] text-ink-3">
        {f.xg[0].toFixed(2)} – {f.xg[1].toFixed(2)}
      </td>
      <td className="whitespace-nowrap py-2.5 pr-4 text-right">
        <Link href={href} className="text-[12px] text-home hover:underline">
          why &rarr;
        </Link>
      </td>
    </tr>
  );
}

export function RoundTables({ round }: { round: RoundData }) {
  const names = Object.keys(round.leagues);
  const first = names[0] ?? "";

  /** A stored league that is no longer in the payload falls back rather than
   *  rendering an empty page — leagues come and go from the export, and a
   *  stale preference must not be able to blank the front page. */
  const stored = useStored(KEY, first);
  const active = names.includes(stored) ? stored : first;

  const data = round.leagues[active];
  if (!data) return null;

  const played = data.fixtures.filter((f) => f.played).length;

  return (
    <div>
      <div role="tablist" className="flex flex-wrap gap-2">
        {names.map((league) => {
          const on = league === active;
          const lg = round.leagues[league];
          return (
            <button
              key={league}
              role="tab"
              aria-selected={on}
              onClick={() => setStored(KEY, league)}
              className={`flex cursor-pointer items-center gap-2 rounded-full border px-3.5 py-1.5 text-[13px] transition-colors ${
                on
                  ? "border-ink bg-ink text-white"
                  : "border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink"
              }`}
            >
              <Crest src={round.crests.leagues[league]} alt="" size={17} />
              <span className={on ? "font-medium" : undefined}>
                {leagueShort(league)}
              </span>
              <span
                className={`num text-[11px] ${on ? "text-white/60" : "text-ink-3"}`}
              >
                {lg.fixtures.length}
              </span>
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-2.5 text-[12.5px] text-ink-3">
        <span className="num">
          round {data.week} · {data.start.slice(5)} → {data.end.slice(5)}
        </span>
        {played > 0 && (
          <span className="num">
            · {played} of {data.fixtures.length} played
          </span>
        )}
      </div>

      <div className="mt-2 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-3 text-left font-semibold">Date</th>
              <th className="py-2 pr-2 text-right font-semibold">Home</th>
              <th className="px-3 py-2 text-center font-semibold">Score</th>
              <th className="py-2 pl-2 text-left font-semibold">Away</th>
              <th className="px-4 py-2 text-center font-semibold">Call</th>
              {OUTCOMES.map((o) => (
                <th
                  key={o.key}
                  className="px-3 py-2 text-center font-semibold"
                  title={`${o.key} — percentage, and the fair price beneath`}
                >
                  {o.mark}
                </th>
              ))}
              <th className="py-2 pl-3 pr-4 text-right font-semibold">
                Expected xG
              </th>
              <th className="py-2 pr-4 text-right font-semibold" />
            </tr>
          </thead>
          <tbody>
            {data.fixtures.map((f) => (
              <Row
                key={`${f.home}-${f.away}`}
                f={f}
                crests={round.crests}
                league={active}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
