import Link from "next/link";
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
        <div className="num flex gap-6 text-[13px] text-ink-2">
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

      <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-card">
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
