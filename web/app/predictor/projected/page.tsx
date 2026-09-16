import { getRound, leagueShort, type ZoneKey } from "@/lib/data";
import { Crest, LeagueHeading } from "../../components/Crest";
import { Fighting, ZoneBar, ZoneLegend } from "../../components/ZoneBar";

const EUROPE: ZoneKey[] = ["ucl", "uclq", "uel", "uecl"];

function Pct({ v, bold }: { v: number; bold?: boolean }) {
  if (!v || v < 0.1) return <span className="text-ink-3">—</span>;
  return <span className={bold && v >= 20 ? "font-semibold" : ""}>{v}%</span>;
}

export default function ProjectedPage() {
  const round = getRound();
  if (!round) return <p className="text-ink-2">No projection exported yet.</p>;

  return (
    <div>
      <p className="max-w-3xl text-[13.5px] text-ink-2">
        Every remaining fixture priced by the model, then the season replayed
        ten thousand times. Points already banked are kept; the rest is
        simulated. Each league is scored against{" "}
        <strong className="font-semibold">its own</strong> European places and
        relegation shape — the two 18-team leagues have a play-off place that a
        simple &ldquo;bottom three&rdquo; would miss.
      </p>
      <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
        Ratings are frozen as of {round.as_of}, so a match in May is priced with
        today&apos;s strengths: no transfers or injuries are modelled, which
        makes title odds far more trustworthy than the exact gap between 14th
        and 15th. Cup winners&apos; European routes and UEFA coefficient bonus
        places are not modelled either.
      </p>

      {Object.entries(round.leagues).map(([league, data]) => (
        <section key={league} className="mt-8">
          <LeagueHeading
            src={round.crests.leagues[league]}
            name={leagueShort(league)}
            meta="projected final table"
          />
          <div className="mt-2">
            <ZoneLegend zones={data.zones} />
          </div>
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
                  <th className="px-3 py-2 text-right font-semibold">Europe</th>
                  <th className="px-3 py-2 text-right font-semibold">Danger</th>
                  <th className="px-4 py-2 text-left font-semibold">
                    Season outlook
                  </th>
                  <th className="py-2 pl-2 pr-4 text-left font-semibold">
                    Playing for
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.projection.map((r, i) => {
                  const europe = EUROPE.reduce(
                    (a, k) => a + (r.zone[k] ?? 0),
                    0,
                  );
                  const danger = (r.zone.rel ?? 0) + (r.zone.playoff ?? 0);
                  return (
                    <tr key={r.team} className="border-t border-line">
                      <td className="num py-2 pl-4 pr-2 text-ink-3">{i + 1}</td>
                      <td className="whitespace-nowrap py-2 pr-3">
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
                        <Pct v={r.title} bold />
                      </td>
                      <td className="num px-3 py-2 text-right">
                        <Pct v={Math.round(europe * 10) / 10} />
                      </td>
                      <td className="num px-3 py-2 text-right">
                        <span className={danger >= 30 ? "font-semibold" : ""}>
                          <Pct v={Math.round(danger * 10) / 10} />
                        </span>
                      </td>
                      <td className="px-4 py-2">
                        <ZoneBar zone={r.zone} zones={data.zones} />
                      </td>
                      <td className="py-2 pl-2 pr-4">
                        <Fighting zone={r.zone} zones={data.zones} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
