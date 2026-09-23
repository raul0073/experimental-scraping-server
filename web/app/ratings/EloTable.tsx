"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { Crest } from "../components/Crest";
import { HintBox, HintIcon } from "./Hint";

/** The process Elo, as a table.
 *
 *  This is the predictor's rating spine and it had been shipping as a JSON
 *  file nothing on the site looked at — built, fitted, used by the versus
 *  projection, and invisible. A rating nobody can read is a rating nobody
 *  can argue with.
 *
 *  The numbers are LOG-MULTIPLIERS ON CHANCES, which is the honest unit but
 *  not a readable one, so each is also shown as what it means: a side with
 *  attack +0.20 against the league creates exp(0.20) = 1.22 times what an
 *  average side would. The table sorts on attack + defence.
 */

const DATA = "/data/team/eng-premier-league";

type Row = {
  team: string; attack: number; defence: number; rating: number;
  current?: boolean;
};
type Elo = {
  params: { k: number; home_adv: number; conv: number; rho: number };
  table: Row[];
};

function slugify(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** Diverging on the league's own spread, not on an absolute scale: these
 *  are log units and a tenth of one is a real difference. */
function shade(v: number, lo: number, hi: number) {
  const t = Math.max(-1, Math.min(1, ((v - (lo + hi) / 2) / ((hi - lo) / 2 || 1))));
  const mid = [154, 163, 171];
  const to = t < 0 ? [179, 38, 30] : [26, 127, 55];
  const c = mid.map((m, i) => Math.round(m + (to[i] - m) * Math.abs(t)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function EloTable() {
  const [elo, setElo] = useState<Elo | null>(null);
  const [crests, setCrests] = useState<Record<string, string>>({});
  const [all, setAll] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch(`${DATA}/elo.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${DATA}/meta.json`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([e, m]) => {
        setElo(e);
        setCrests(m?.crests ?? {});
      })
      .catch(() => setElo(null));
  }, []);

  const rows = useMemo(() => {
    if (!elo) return [];
    const list = all ? elo.table : elo.table.filter((r) => r.current !== false);
    return [...list].sort((a, b) => b.rating - a.rating);
  }, [elo, all]);

  if (!elo) return null;
  const aLo = Math.min(...rows.map((r) => r.attack));
  const aHi = Math.max(...rows.map((r) => r.attack));
  const dLo = Math.min(...rows.map((r) => r.defence));
  const dHi = Math.max(...rows.map((r) => r.defence));

  return (
    <section className="mt-8">
      {/* THE POPOVER IS ANCHORED TO A BLOCK, NOT TO ITS ICON, which is what
          `Hint` exists for. The shared `Info` is a fixed 288px box hung off a
          14px circle: sitting after a heading it starts about 130px in, so on
          a 375px screen it either runs off the right edge — which scrolls the
          whole PAGE sideways — or, anchored right, off the left one, where
          half the sentence cannot be read.
          The anchor is this span rather than the row, because the row is the
          full page width and `inset-x-0` on a 1392px row is a 1392px tooltip.
          Full width on a phone, a readable column on anything wider. */}
      <div className="flex flex-wrap items-baseline gap-3">
        <div className="group/hint relative w-full sm:w-auto sm:min-w-[24rem]">
          <h2 className="inline-flex items-baseline text-[16px] font-semibold">
            Process Elo
            <HintIcon />
          </h2>
          <HintBox>
            <b className="text-ink">The predictor&apos;s rating spine.</b> An
            online rating updated after every match on what a side CREATED,
            not on the result — a half-season of points predicts the next half
            at 0.59, the process metrics at 0.78. It carries across seasons,
            needs no seed, and is opponent-aware by construction, because the
            update is a surprise against a specific opponent. Fitted K=
            {elo.params.k}, home advantage {elo.params.home_adv}.
          </HintBox>
        </div>
        <button
          onClick={() => setAll((v) => !v)}
          className="ml-auto rounded-full border border-line bg-card px-3 py-1 text-[12px] text-ink-2 hover:border-ink-3"
        >
          {all ? "current league only" : "include relegated clubs"}
        </button>
      </div>
      <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
        Log-multipliers on chances. An attack of{" "}
        <span className="num">+0.20</span> means a side creates{" "}
        <span className="num">1.22×</span> what an average one would; a
        defence of <span className="num">+0.20</span> means it concedes that
        much less. Scored against 25/26 the pair runs at{" "}
        <span className="num">1.039</span> log-loss against a base rate of{" "}
        <span className="num">1.085</span>.
      </p>

      <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="w-10 py-2 pl-4 text-right font-semibold">#</th>
              <th className="py-2 pl-3 pr-3 text-left font-semibold">Club</th>
              <th className="px-3 py-2 text-center font-semibold">Attack</th>
              <th className="px-3 py-2 text-center font-semibold">Defence</th>
              <th className="px-3 py-2 text-center font-semibold">Overall</th>
              <th className="px-3 py-2 text-center font-semibold">
                Chances a match
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.team} className="border-t border-line">
                <td className="num py-2 pl-4 text-right text-[12px] text-ink-3">
                  {i + 1}
                </td>
                <td className="whitespace-nowrap py-2 pl-3 pr-3">
                  <Link
                    href={`/team/${slugify(r.team)}`}
                    className="flex items-center gap-2 font-medium hover:underline"
                  >
                    <Crest src={crests[r.team] ?? ""} alt="" size={18} />
                    {r.team}
                    {r.current === false && (
                      <span className="text-[10.5px] font-normal text-ink-3">
                        not in the league
                      </span>
                    )}
                  </Link>
                </td>
                {([[r.attack, aLo, aHi], [r.defence, dLo, dHi]] as const).map(
                  ([v, lo, hi], j) => (
                    <td key={j} className="px-3 py-2 text-center">
                      <span
                        className="num inline-block w-[52px] rounded-md py-0.5 text-[12px] font-semibold text-white"
                        style={{ background: shade(v, lo, hi) }}
                      >
                        {v >= 0 ? "+" : ""}{v.toFixed(2)}
                      </span>
                    </td>
                  ),
                )}
                <td className="num px-3 py-2 text-center font-semibold">
                  {r.rating >= 0 ? "+" : ""}{r.rating.toFixed(2)}
                </td>
                <td className="num px-3 py-2 text-center text-ink-2">
                  {(Math.exp(r.attack) * elo.params.conv).toFixed(2)}
                  <span className="mx-1 text-ink-3">–</span>
                  {(Math.exp(-r.defence) * elo.params.conv).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 max-w-4xl text-[11.5px] leading-relaxed text-ink-3">
        The last column is what the rating expects against a league-average
        opponent, converted to goals — scored and conceded. It is a fair
        expectation and not a price.
      </p>
    </section>
  );
}
