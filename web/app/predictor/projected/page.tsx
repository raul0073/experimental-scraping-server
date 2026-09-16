import { getRound, leagueShort } from "@/lib/data";
import { Crest, LeagueHeading } from "../../components/Crest";

function Pct({ v, strong }: { v: number; strong?: boolean }) {
  if (v < 0.1) return <span className="text-ink-3">—</span>;
  return (
    <span className={strong && v >= 20 ? "font-semibold" : undefined}>
      {v}%
    </span>
  );
}

export default function ProjectedPage() {
  const round = getRound();
  if (!round) return <p className="text-ink-2">No projection exported yet.</p>;

  return (
    <div>
      <p className="max-w-3xl text-[13.5px] text-ink-2">
        Every remaining fixture priced by the model, then the season replayed
        ten thousand times. Points already banked are kept; the rest is
        simulated. Ratings are frozen as of {round.as_of}, so a match in May is
        priced with today&apos;s strengths — no transfers or injuries are
        modelled, which makes title odds far more trustworthy than the exact
        gap between 14th and 15th.
      </p>

      {Object.entries(round.leagues).map(([league, data]) => (
        <section key={league} className="mt-7">
          <LeagueHeading
            src={round.crests.leagues[league]}
            name={leagueShort(league)}
            meta="projected final table"
          />
          <div className="mt-2 overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-2 text-left font-semibold">#</th>
                  <th className="py-2 pr-3 text-left font-semibold">Team</th>
                  <th className="px-3 py-2 text-right font-semibold">Now</th>
                  <th className="px-3 py-2 text-right font-semibold">
                    Exp. pts
                  </th>
                  <th className="px-3 py-2 text-right font-semibold">Title</th>
                  <th className="px-3 py-2 text-right font-semibold">Top 4</th>
                  <th className="py-2 pl-3 pr-4 text-right font-semibold">
                    Relegation
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.projection.map((r, i) => (
                  <tr key={r.team} className="border-t border-line">
                    <td className="num py-2 pl-4 pr-2 text-ink-3">{i + 1}</td>
                    <td className="py-2 pr-3">
                      <span className="inline-flex items-center gap-2">
                        <Crest
                          src={round.crests.teams[league]?.[r.team]}
                          alt=""
                        />
                        {r.team}
                      </span>
                    </td>
                    <td className="num px-3 py-2 text-right text-ink-3">
                      {r.played_pts}
                    </td>
                    <td className="num px-3 py-2 text-right font-semibold">
                      {r.exp_pts}
                    </td>
                    <td className="num px-3 py-2 text-right">
                      <Pct v={r.title} strong />
                    </td>
                    <td className="num px-3 py-2 text-right">
                      <Pct v={r.top4} />
                    </td>
                    <td className="num py-2 pl-3 pr-4 text-right">
                      <span className={r.rel >= 30 ? "text-bad font-semibold" : ""}>
                        <Pct v={r.rel} />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
