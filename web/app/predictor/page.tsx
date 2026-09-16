import {
  getRecord,
  getRound,
  leagueShort,
  outcomeLabel,
  type Fixture,
  type Outcome,
} from "@/lib/data";

const CALL_STYLE: Record<Outcome, string> = {
  home: "bg-[#e3eef7] text-[#1c5b8a] border-[#b9d5e8]",
  draw: "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  away: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
};

function Bar({ p }: { p: Record<Outcome, number> }) {
  return (
    <div className="flex h-1.5 w-28 overflow-hidden rounded-full">
      <div style={{ width: `${p.home}%` }} className="bg-home" />
      <div style={{ width: `${p.draw}%` }} className="bg-draw" />
      <div style={{ width: `${p.away}%` }} className="bg-away" />
    </div>
  );
}

function Row({ f }: { f: Fixture }) {
  return (
    <tr className="border-t border-line align-middle">
      <td className="py-2 pr-3 text-[12px] text-ink-3">{f.date.slice(5)}</td>
      <td className="py-2 pr-2 text-right">{f.home}</td>
      <td className="num px-2 text-center font-semibold">{f.score}</td>
      <td className="py-2 pl-2">{f.away}</td>
      <td className="px-3">
        <span
          className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${CALL_STYLE[f.call]}`}
        >
          {outcomeLabel[f.call]}
        </span>
      </td>
      <td className="px-2">
        <Bar p={f.p} />
      </td>
      <td className="num px-2 text-[12px] text-ink-3">
        {Math.round(f.p.home)}·{Math.round(f.p.draw)}·{Math.round(f.p.away)}
      </td>
      <td className="num px-2 text-[12.5px]">
        <span className="text-ink-3">fair </span>
        {f.fair.home} / {f.fair.draw} / {f.fair.away}
      </td>
    </tr>
  );
}

export default function PredictorPage() {
  const round = getRound();
  const record = getRecord();
  if (!round) return <p className="text-ink-2">No round data exported yet.</p>;

  const leagues = Object.entries(round.leagues);

  return (
    <div>
      <h1 className="font-display text-[24px] tracking-[0.01em]">Predictor</h1>
      <p className="mt-2 max-w-3xl text-[13.5px] text-ink-2">
        Every fixture of the next round, with the model&apos;s probability, the
        outcome it calls, its most likely scoreline, and the{" "}
        <strong className="font-semibold">fair price</strong> of each result —
        what the outcome is worth. Above that price there is value in it; below
        it there is not. We never see your book, so that comparison is yours to
        make.
      </p>

      {record ? (
        <div className="num mt-5 flex flex-wrap gap-6 rounded-xl border border-line bg-card px-5 py-4 text-[13px]">
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-ink-3">
              Calls graded
            </div>
            <div className="text-[20px] font-semibold">{record.graded}</div>
          </div>
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-ink-3">
              Landed
            </div>
            <div className="text-[20px] font-semibold">{record.hit_rate}%</div>
          </div>
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-ink-3">
              It claimed
            </div>
            <div className="text-[20px] font-semibold">{record.said_avg}%</div>
          </div>
          <div>
            <div className="text-[11.5px] uppercase tracking-wider text-ink-3">
              Exact score
            </div>
            <div className="text-[20px] font-semibold">
              {record.exact_score}%
            </div>
          </div>
          <p className="max-w-sm self-center text-[12.5px] text-ink-2">
            Landing above what it claimed means the model is honest, not that it
            is beating the game — most fixtures are genuinely close.
          </p>
        </div>
      ) : null}

      {leagues.map(([league, data]) => (
        <section key={league} className="mt-8">
          <h2 className="text-[16px] font-semibold">
            {leagueShort(league)}
            <span className="ml-3 text-[12.5px] font-normal text-ink-3">
              round {data.week} · {data.start.slice(5)} → {data.end.slice(5)}
            </span>
          </h2>
          <div className="mt-2 overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-[13.5px]">
              <tbody>
                {data.fixtures.map((f) => (
                  <Row key={`${f.home}-${f.away}`} f={f} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
