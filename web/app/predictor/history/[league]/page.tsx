import { notFound } from "next/navigation";
import {
  getHistory,
  leagueShort,
  outcomeLabel,
  type HistoryLeague,
  type HistoryRow,
} from "@/lib/data";
import { Crest } from "../../../components/Crest";
import { Crumbs } from "../../../components/Crumbs";

// output: "export" needs every dynamic path known at build time.
export function generateStaticParams() {
  const history = getHistory();
  return Object.keys(history?.leagues ?? {}).map((league) => ({ league }));
}

function Verdict({ r }: { r: HistoryRow }) {
  if (r.status !== "graded")
    return <span className="text-[12.5px] text-ink-3">pending</span>;
  if (r.score_hit)
    return (
      <span className="rounded-full border border-[#c2e0cd] bg-[#e8f3ec] px-2 py-0.5 text-[11.5px] font-semibold text-good">
        exact score
      </span>
    );
  return r.outcome_hit ? (
    <span className="text-[13px] font-semibold text-good">✓ called it</span>
  ) : (
    <span className="text-[13px] text-bad">✗ missed</span>
  );
}

/** One graded call on a phone. Ten columns is a sideways scroll at 375px,
 *  and the first thing it scrolls off is the two team names — so the same
 *  ten facts stack instead. Nothing is dropped: probabilities, our call, the
 *  result, both xG pairs and the verdict are all here. */
function Card({ r, league }: { r: HistoryRow; league: HistoryLeague }) {
  const side = (team: string) => (
    <span className="flex min-w-0 items-center gap-2 text-[14px]">
      <Crest src={league.teams[team]} alt="" size={16} />
      <span className="truncate">{team}</span>
    </span>
  );
  return (
    <li className="rounded-xl border border-line bg-card p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="num text-[11.5px] text-ink-3">{r.kickoff}</span>
        <Verdict r={r} />
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-3">
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          {side(r.home)}
          {side(r.away)}
        </span>
        <span className="shrink-0 text-right">
          <span className="num block text-[16px] font-semibold">
            {r.score ?? <span className="font-normal text-ink-3">—</span>}
          </span>
          <span className="num block text-[10.5px] text-ink-3">
            said {r.our_score} ({outcomeLabel[r.call]})
          </span>
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-line pt-2 text-[11.5px] text-ink-3">
        <span className="num">
          <span className="mr-1">H/D/A</span>
          {(["home", "draw", "away"] as const).map((o, i) => (
            <span key={o}>
              {i > 0 ? <span className="text-ink-3"> / </span> : null}
              <span
                className={r.call === o ? "font-semibold text-ink" : undefined}
              >
                {Math.round(r.p[o])}
              </span>
            </span>
          ))}
        </span>
        {r.our_xg && (
          <span className="num">
            our xG {r.our_xg[0].toFixed(2)}–{r.our_xg[1].toFixed(2)}
          </span>
        )}
        {r.real_xg && (
          <span className="num">
            real {r.real_xg[0].toFixed(2)}–{r.real_xg[1].toFixed(2)}
          </span>
        )}
      </div>
    </li>
  );
}

function Row({ r, league }: { r: HistoryRow; league: HistoryLeague }) {
  const called = (o: "home" | "draw" | "away") => r.call === o;
  return (
    <tr className="border-t border-line">
      <td className="whitespace-nowrap py-2.5 pl-4 pr-3 text-[12px] text-ink-3">
        {r.kickoff}
      </td>
      <td className="py-2.5 pr-2 text-right">
        <span className="inline-flex items-center gap-2">
          {r.home}
          <Crest src={league.teams[r.home]} alt="" size={16} />
        </span>
      </td>
      <td className="px-2 py-2.5 text-center text-[12px] text-ink-3">v</td>
      <td className="py-2.5 pl-2">
        <span className="inline-flex items-center gap-2">
          <Crest src={league.teams[r.away]} alt="" size={16} />
          {r.away}
        </span>
      </td>
      <td className="num px-3 py-2.5 text-center text-[12.5px]">
        {(["home", "draw", "away"] as const).map((o, i) => (
          <span key={o}>
            {i > 0 ? <span className="text-ink-3"> / </span> : null}
            <span className={called(o) ? "font-semibold text-ink" : "text-ink-3"}>
              {Math.round(r.p[o])}
            </span>
          </span>
        ))}
      </td>
      <td className="num px-3 py-2.5 text-center">
        {r.our_score}
        <span className="ml-1.5 text-[11px] text-ink-3">
          {outcomeLabel[r.call]}
        </span>
      </td>
      <td className="num px-3 py-2.5 text-center font-semibold">
        {r.score ?? <span className="font-normal text-ink-3">—</span>}
      </td>
      <td className="num px-3 py-2.5 text-center text-[12px] text-ink-3">
        {r.our_xg ? `${r.our_xg[0].toFixed(2)}–${r.our_xg[1].toFixed(2)}` : "—"}
      </td>
      <td className="num px-3 py-2.5 text-center text-[12px] text-ink-3">
        {r.real_xg
          ? `${r.real_xg[0].toFixed(2)}–${r.real_xg[1].toFixed(2)}`
          : "—"}
      </td>
      <td className="py-2.5 pl-3 pr-4">
        <Verdict r={r} />
      </td>
    </tr>
  );
}

export default async function LeagueHistoryPage({
  params,
}: {
  params: Promise<{ league: string }>;
}) {
  const { league: slug } = await params;
  const history = getHistory();
  const league = history?.leagues[slug];
  if (!league) notFound();

  const pending = league.rows.filter((r) => r.status !== "graded").length;
  const rate = league.graded
    ? Math.round((league.hits / league.graded) * 1000) / 10
    : null;

  return (
    <div>
      <Crumbs
        trail={[
          { href: "/predictor", label: "Predictor" },
          { href: "/predictor/history", label: "History" },
          { label: leagueShort(league.name) },
        ]}
      />

      <div className="mt-3 flex flex-wrap items-center gap-4">
        <Crest src={league.crest} alt="" size={32} />
        <h2 className="text-[19px] font-semibold">
          {leagueShort(league.name)}
        </h2>
        <div className="num flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-2 sm:gap-6">
          <span>
            <strong className="text-[15px] font-semibold text-ink">
              {rate ?? "—"}%
            </strong>{" "}
            called
          </span>
          <span>
            {league.hits}/{league.graded} graded
          </span>
          <span>{league.exact} exact scores</span>
          {pending ? <span>{pending} pending</span> : null}
        </div>
      </div>

      <ul className="mt-4 space-y-2 sm:hidden">
        {league.rows.map((r) => (
          <Card key={`${r.kickoff}-${r.home}`} r={r} league={league} />
        ))}
      </ul>

      <div className="mt-4 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-3 text-left font-semibold">Kickoff</th>
              <th className="py-2 pr-2 text-right font-semibold">Home</th>
              <th />
              <th className="py-2 pl-2 text-left font-semibold">Away</th>
              <th className="px-3 py-2 text-center font-semibold">H / D / A</th>
              <th className="px-3 py-2 text-center font-semibold">Our call</th>
              <th className="px-3 py-2 text-center font-semibold">Result</th>
              <th className="px-3 py-2 text-center font-semibold">Our xG</th>
              <th className="px-3 py-2 text-center font-semibold">Real xG</th>
              <th className="py-2 pl-3 pr-4 text-left font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {league.rows.map((r) => (
              <Row key={`${r.kickoff}-${r.home}`} r={r} league={league} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[12.5px] text-ink-3">
        The bold number in H / D / A is the outcome the model called, recorded
        before kickoff. A draw caps at roughly 32–35%, so the call is only a
        draw when it reaches that ceiling — which is why most calls are for a
        side even in matches the model considers close.
      </p>
    </div>
  );
}
