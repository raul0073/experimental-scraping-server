import Link from "next/link";
import { getRecord, getRound, leagueShort, slugify } from "@/lib/data";
import { Crest } from "../../components/Crest";
import { Crumbs } from "../../components/Crumbs";

export const metadata = {
  title: "Track record",
  description:
    "Every call this model made before kickoff, graded afterwards. The misses are here too, because a record with the losses removed is not a record.",
};

export default function HistoryPage() {
  const record = getRecord();
  const round = getRound();
  if (!record) return <p className="text-ink-2">No record exported yet.</p>;

  const maxBucket = Math.max(
    ...record.calibration.flatMap((b) => [b.said, b.landed]),
    1,
  );

  return (
    <div>
      <Crumbs
        trail={[
          { href: "/predictor", label: "Predictor" },
          { label: "History" },
        ]}
      />
      <p className="max-w-3xl text-[13.5px] text-ink-2">
        Every prediction is written down before kickoff and graded afterwards.
        The first prediction stands — nothing is revised once a result is known.
        The figures on this page count only calls committed before kickoff
        {record.live_since ? ` (the full-round record runs from ${record.live_since})` : ""}
        {record.reconstructed?.n ? (
          <>
            ; the opening rounds, rebuilt after the fact, are{" "}
            <a href="#reconstructed" className="text-home underline underline-offset-2">
              reported apart
            </a>
          </>
        ) : null}
        .
      </p>

      {/* Four figures side by side need 400px they do not have on a phone,
          so they tile two-up and only become a row from `sm`. */}
      <div className="num mt-5 grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-line bg-card px-4 py-4 sm:flex sm:justify-evenly sm:gap-8 sm:px-5">
        {[
          { label: "Live calls graded", value: record.graded },
          { label: "Landed", value: `${record.hit_rate}%` },
          { label: "It claimed", value: `${record.said_avg}%` },
          { label: "Exact score", value: `${record.exact_score}%` },
        ].map((s) => (
          <div key={s.label}>
            <div className="text-[11px] uppercase tracking-wider text-ink-3">
              {s.label}
            </div>
            <div className="text-[22px] font-semibold">{s.value}</div>
          </div>
        ))}
      </div>

      {record.scoring && (
        <section className="mt-8">
          <h2 className="text-[16px] font-semibold">Scored properly</h2>
          <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
            A hit rate rewards calling the favourite and says nothing about
            whether 46% meant 46%. Log loss and Brier score punish a confident
            miss more than a hesitant one, which is what a published
            probability has to answer for. Lower is better. Two baselines say
            what the numbers mean: a third each is knowing nothing; the base
            rate is knowing only how often home sides win this season (
            {record.scoring.base_rates.home}% home, {record.scoring.base_rates.draw}%
            draw, {record.scoring.base_rates.away}% away, over these same matches,
            which flatters the baseline).
          </p>
          <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-3 text-left font-semibold">Forecast</th>
                  <th className="px-3 py-2 text-right font-semibold">Log loss</th>
                  <th className="py-2 pl-3 pr-4 text-right font-semibold">Brier</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    { label: "This model", s: record.scoring.model, strong: true },
                    { label: "Base rate", s: record.scoring.base_rate, strong: false },
                    { label: "A third each", s: record.scoring.uniform, strong: false },
                  ] as const
                ).map((r) => (
                  <tr key={r.label} className="border-t border-line">
                    <td className={`py-2.5 pl-4 pr-3 ${r.strong ? "font-semibold" : "text-ink-2"}`}>
                      {r.label}
                    </td>
                    <td className={`num px-3 py-2.5 text-right ${r.strong ? "font-semibold" : ""}`}>
                      {r.s.logloss.toFixed(4)}
                    </td>
                    <td className={`num py-2.5 pl-3 pr-4 text-right ${r.strong ? "font-semibold" : ""}`}>
                      {r.s.brier.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[12.5px] text-ink-3">
            On the frozen seasons the same model scores 0.984 log loss over
            11,311 fixtures against a base rate of 1.073. How it compares with
            the bookmakers&apos; closing prices is on{" "}
            <Link href="/predictor/market" className="text-home underline underline-offset-2">
              Versus the market
            </Link>
            .
          </p>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Is it honest?</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          Accuracy can be gamed by only predicting easy matches. Calibration
          cannot: to be calibrated the model has to be right about its own
          uncertainty, so its 35% calls must fail about 65% of the time. Each
          row groups predictions by how confident the model was, and compares
          what it claimed against what happened.
        </p>
        {/* phone: one block per bucket. The bars are the comparison, so they
            get the full width instead of a 176px cell inside a table that
            would have to be scrolled sideways to reach them. */}
        <ul className="mt-3 space-y-2 sm:hidden">
          {record.calibration.map((b) => (
            <li key={b.bucket} className="rounded-xl border border-line bg-card p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[13px] font-medium">{b.bucket}</span>
                <span className="num text-[11.5px] text-ink-3">
                  {b.n} call{b.n === 1 ? "" : "s"}
                </span>
              </div>
              <div className="mt-2 space-y-1.5">
                {(
                  [
                    { label: "said", v: b.said, fill: "bg-ink-3" },
                    { label: "landed", v: b.landed, fill: "bg-home" },
                  ] as const
                ).map((r) => (
                  <div key={r.label} className="flex items-center gap-2">
                    <span className="w-[42px] shrink-0 text-[10.5px] text-ink-3">
                      {r.label}
                    </span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#eceff1]">
                      <span
                        className={`block h-full rounded-full ${r.fill}`}
                        style={{ width: `${(r.v / maxBucket) * 100}%` }}
                      />
                    </span>
                    <span
                      className={`num w-[44px] shrink-0 text-right text-[12px] ${
                        r.label === "landed" ? "font-semibold" : "text-ink-2"
                      }`}
                    >
                      {r.v}%
                    </span>
                  </div>
                ))}
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-3 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                <th className="py-2 pl-4 pr-3 text-left font-semibold">
                  Confidence
                </th>
                <th className="px-3 py-2 text-right font-semibold">Calls</th>
                <th className="px-3 py-2 text-right font-semibold">It said</th>
                <th className="px-3 py-2 text-right font-semibold">Landed</th>
                <th className="py-2 pl-3 pr-4 text-left font-semibold">
                  Said v landed
                </th>
              </tr>
            </thead>
            <tbody>
              {record.calibration.map((b) => (
                <tr key={b.bucket} className="border-t border-line">
                  <td className="py-2.5 pl-4 pr-3">{b.bucket}</td>
                  <td className="num px-3 py-2.5 text-right text-ink-3">
                    {b.n}
                  </td>
                  <td className="num px-3 py-2.5 text-right">{b.said}%</td>
                  <td className="num px-3 py-2.5 text-right font-semibold">
                    {b.landed}%
                  </td>
                  <td className="py-2.5 pl-3 pr-4">
                    <div className="flex w-44 flex-col gap-1">
                      <div className="h-1.5 rounded-full bg-[#eceff1]">
                        <div
                          className="h-full rounded-full bg-ink-3"
                          style={{ width: `${(b.said / maxBucket) * 100}%` }}
                        />
                      </div>
                      <div className="h-1.5 rounded-full bg-[#eceff1]">
                        <div
                          className="h-full rounded-full bg-home"
                          style={{ width: `${(b.landed / maxBucket) * 100}%` }}
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[12.5px] text-ink-3">
          Grey is what the model claimed, blue is what happened. Bars that
          match are the point. Landing above the claim is not a virtue: it
          means the probability was too low, and every fair price built on it
          was too high. Buckets with few calls will move a lot; treat small
          samples as noise.
        </p>
      </section>

      {record.levels?.length ? (
        <section className="mt-8" id="levels">
          <h2 className="text-[16px] font-semibold">Where the probability sits</h2>
          <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
            The buckets above group calls, so a bias in one outcome&apos;s level
            can hide inside them. This table takes every live fixture, not only
            the calls, and compares the mean probability the model gave each
            outcome with how often that outcome happened. A gap beyond two
            standard errors is a bias, not noise.
          </p>
          <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-3 text-left font-semibold">Outcome</th>
                  <th className="px-3 py-2 text-right font-semibold">It said</th>
                  <th className="px-3 py-2 text-right font-semibold">Happened</th>
                  <th className="px-3 py-2 text-right font-semibold">Gap</th>
                  <th className="py-2 pl-3 pr-4 text-right font-semibold">± 1 s.e.</th>
                </tr>
              </thead>
              <tbody>
                {record.levels.map((l) => {
                  const bias = Math.abs(l.gap) >= 2 * l.se;
                  return (
                    <tr key={l.outcome} className="border-t border-line">
                      <td className="py-2.5 pl-4 pr-3 capitalize">{l.outcome}</td>
                      <td className="num px-3 py-2.5 text-right">{l.said}%</td>
                      <td className="num px-3 py-2.5 text-right font-semibold">{l.landed}%</td>
                      <td className={`num px-3 py-2.5 text-right ${bias ? "font-semibold text-bad" : "text-ink-2"}`}>
                        {l.gap > 0 ? "+" : ""}
                        {l.gap}
                      </td>
                      <td className="num py-2.5 pl-3 pr-4 text-right text-ink-3">{l.se}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {record.goals && (
            <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-3">
              Where a draw gap comes from: the model has priced these matches at{" "}
              <span className="num">{record.goals.expected}</span> goals a game and{" "}
              <span className="num">{record.goals.actual}</span> have been scored.
              A scoreline grid turns every goal it fails to expect straight
              into draw probability. On the eight frozen seasons the same
              model says 25.0% draw against 25.4% drawn, and a draw correction
              fitted season by season comes out between 1.00 and 1.02 — so no
              correction is applied, and the gap is reported here instead.
            </p>
          )}
        </section>
      ) : null}

      {record.reconstructed?.n ? (
        <section
          className="mt-8 rounded-xl border border-dashed border-line bg-[#fbfcfd] p-5"
          id="reconstructed"
        >
          <h2 className="text-[16px] font-semibold">The reconstructed rounds</h2>
          <p className="mt-1 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
            The full-round record started on {record.reconstructed.recorded_on}.
            The {record.reconstructed.n} fixtures played before that
            {record.reconstructed.kickoffs
              ? ` (${record.reconstructed.kickoffs[0]} to ${record.reconstructed.kickoffs[1]})`
              : ""}{" "}
            were rebuilt on that date, walk-forward: each priced only from
            data available before its kickoff, by the model as it stood then.
            The method is the same, but the rows were written after the
            results were known, and a reader cannot verify the difference —
            so they are kept out of every headline figure and shown here on
            their own. The weekly picks ledger, a separate record, was
            committed before kickoff from the first round.
          </p>
          <div className="num mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:flex sm:gap-10">
            {[
              { label: "Fixtures", value: record.reconstructed.n },
              { label: "Landed", value: `${record.reconstructed.hit_rate}%` },
              { label: "It claimed", value: `${record.reconstructed.said_avg}%` },
              {
                label: "Log loss",
                value: record.reconstructed.scores
                  ? record.reconstructed.scores.logloss.toFixed(4)
                  : "—",
              },
            ].map((s) => (
              <div key={s.label}>
                <div className="text-[11px] uppercase tracking-wider text-ink-3">{s.label}</div>
                <div className="text-[18px] font-semibold">{s.value}</div>
              </div>
            ))}
          </div>
          {record.all?.scores && (
            <p className="mt-3 text-[12.5px] text-ink-3">
              Both sets together: {record.all.n} fixtures, {record.all.hit_rate}% landed,{" "}
              {record.all.scores.logloss.toFixed(4)} log loss.
            </p>
          )}
        </section>
      ) : null}

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">By competition</h2>
        <p className="mt-1 text-[13px] text-ink-2">
          Open a competition for every prediction it has made, graded
          match by match.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(record.by_league).map(([league, v]) => (
            <Link
              key={league}
              href={`/predictor/history/${slugify(league)}`}
              className="group flex items-center gap-3 rounded-xl border border-line bg-card px-4 py-3 transition-colors hover:border-ink-3"
            >
              <Crest src={round?.crests.leagues[league]} alt="" size={24} />
              <div className="flex-1">
                <div className="text-[13.5px]">{leagueShort(league)}</div>
                <div className="text-[11.5px] text-ink-3">
                  {v.n} live calls
                  {v.logloss !== null ? ` · ${v.logloss.toFixed(3)} log loss` : ""}
                  {v.n_reconstructed
                    ? ` · +${v.n_reconstructed} rebuilt`
                    : ""}{" "}
                  · open →
                </div>
              </div>
              <div className="num text-[19px] font-semibold">
                {v.hit_rate}%
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
