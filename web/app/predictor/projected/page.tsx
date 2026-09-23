import { getRound, leagueShort, type ZoneKey } from "@/lib/data";
import { Crest, LeagueHeading } from "../../components/Crest";
import { Crumbs } from "../../components/Crumbs";
import { Fighting, ZoneBar, ZoneLegend } from "../../components/ZoneBar";

export const metadata = {
  title: "Projected tables",
  description:
    "Where each league finishes if the rest of the season is played out at the model's own prices, simulated from today's ratings.",
};

const EUROPE: ZoneKey[] = ["ucl", "uclq", "uel", "uecl"];

type Zones = Partial<Record<ZoneKey, number>>;

/** Rounded to a tenth, the way the table has always printed them. Shared so
 *  the card layout and the table cannot drift apart on what a number says. */
const europeOf = (zone: Zones) =>
  Math.round(EUROPE.reduce((a, k) => a + (zone[k] ?? 0), 0) * 10) / 10;
const dangerOf = (zone: Zones) =>
  Math.round(((zone.rel ?? 0) + (zone.playoff ?? 0)) * 10) / 10;

function Pct({ v, bold }: { v: number; bold?: boolean }) {
  if (!v || v < 0.1) return <span className="text-ink-3">—</span>;
  return <span className={bold && v >= 20 ? "font-semibold" : ""}>{v}%</span>;
}

export default function ProjectedPage() {
  const round = getRound();
  if (!round) return <p className="text-ink-2">No projection exported yet.</p>;

  return (
    <div>
      <Crumbs
        trail={[
          { href: "/predictor", label: "Predictor" },
          { label: "Projected" },
        ]}
      />
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
          {/* phone: one card per club. A nine-column table at 375px hides
              the club name behind a sideways scroll, and the season-outlook
              bar — the whole point of the page — sits in the column furthest
              from the edge you start at. Here the bar gets the full width. */}
          <ul className="mt-2 space-y-2 sm:hidden">
            {data.projection.map((r, i) => (
              <li
                key={r.team}
                className="rounded-xl border border-line bg-card p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="num w-5 shrink-0 text-[12px] text-ink-3">
                    {i + 1}
                  </span>
                  <Crest src={round.crests.teams[league]?.[r.team]} alt="" />
                  <span className="min-w-0 flex-1 truncate text-[14px]">
                    {r.team}
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="num block text-[15px] font-semibold">
                      {r.exp_pts}
                    </span>
                    <span className="block text-[10px] uppercase tracking-wider text-ink-3">
                      exp. pts
                    </span>
                  </span>
                </div>

                <div className="mt-2.5">
                  <ZoneBar zone={r.zone} zones={data.zones} />
                </div>

                <div className="num mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11.5px] text-ink-3">
                  <span>now {r.played_pts}</span>
                  <span>
                    title <Pct v={r.title} bold />
                  </span>
                  <span>
                    Europe <Pct v={europeOf(r.zone)} />
                  </span>
                  <span>
                    danger <Pct v={dangerOf(r.zone)} />
                  </span>
                  <Fighting zone={r.zone} zones={data.zones} />
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-2 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
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
                  const europe = europeOf(r.zone);
                  const danger = dangerOf(r.zone);
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
                        <Pct v={europe} />
                      </td>
                      <td className="num px-3 py-2 text-right">
                        <span className={danger >= 30 ? "font-semibold" : ""}>
                          <Pct v={danger} />
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
