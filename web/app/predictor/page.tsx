import {
  getRound,
  leagueShort,
  type Crests,
  type Fixture,
  type Outcome,
} from "@/lib/data";
import { Crest, LeagueHeading } from "../components/Crest";

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
    <td
      className={`px-3 py-2.5 text-center ${called ? "bg-[#fafbfc]" : ""}`}
    >
      <div
        className={`num text-[14px] ${called ? "font-semibold text-ink" : "text-ink-2"}`}
      >
        {Math.round(f.p[o])}%
      </div>
      <div className="num text-[11.5px] text-ink-3">{f.fair[o].toFixed(2)}</div>
    </td>
  );
}

function Row({ f, crests, league }: { f: Fixture; crests: Crests; league: string }) {
  const logos = crests.teams[league] ?? {};
  return (
    <tr className="border-t border-line">
      <td className="whitespace-nowrap py-2.5 pl-4 pr-3 text-[12px] text-ink-3">
        {f.date.slice(5)}
      </td>
      <td className="py-2.5 pr-2 text-right">
        <span className="inline-flex items-center gap-2">
          {f.home}
          <Crest src={logos[f.home]} alt="" />
        </span>
      </td>
      <td className="num px-3 py-2.5 text-center font-semibold">{f.score}</td>
      <td className="py-2.5 pl-2">
        <span className="inline-flex items-center gap-2">
          <Crest src={logos[f.away]} alt="" />
          {f.away}
        </span>
      </td>
      <td className="px-4 py-2.5 text-center">
        <span
          className={`inline-block min-w-[22px] rounded-full border px-2 py-0.5 text-[11.5px] font-semibold ${CALL_STYLE[f.call]}`}
        >
          {OUTCOMES.find((o) => o.key === f.call)?.mark}
        </span>
      </td>
      {OUTCOMES.map((o) => (
        <Odds key={o.key} f={f} o={o.key} />
      ))}
      <td className="num whitespace-nowrap py-2.5 pl-3 pr-4 text-right text-[12px] text-ink-3">
        {f.xg[0].toFixed(2)} – {f.xg[1].toFixed(2)}
      </td>
    </tr>
  );
}

export default function NextRoundPage() {
  const round = getRound();
  if (!round) return <p className="text-ink-2">No round data exported yet.</p>;

  return (
    <div>
      <p className="max-w-3xl text-[13.5px] text-ink-2">
        Every fixture of the next round: the model&apos;s probability for each
        result, the outcome it calls, its most likely scoreline, and the{" "}
        <strong className="font-semibold">fair price</strong> beneath each
        percentage — what that result is worth. Above that price there is value
        in it; below it there is not. We never see your book, so the comparison
        is yours to make.
      </p>

      {Object.entries(round.leagues).map(([league, data]) => (
        <section key={league} className="mt-7">
          <LeagueHeading
            src={round.crests.leagues[league]}
            name={leagueShort(league)}
            meta={`round ${data.week} · ${data.start.slice(5)} → ${data.end.slice(5)}`}
          />
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
                  <th className="py-2 pl-3 pr-4 text-right font-semibold">Expected xG</th>
                </tr>
              </thead>
              <tbody>
                {data.fixtures.map((f) => (
                  <Row
                    key={`${f.home}-${f.away}`}
                    f={f}
                    crests={round.crests}
                    league={league}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <p className="mt-6 text-[12.5px] text-ink-3">
        Percentages are the model&apos;s probability; the smaller number is the
        fair price (1 ÷ probability). The called outcome is shaded. Scorelines
        are the most likely result given that call, not a prediction of the
        exact score.
      </p>
    </div>
  );
}
