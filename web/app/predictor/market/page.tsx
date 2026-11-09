import {
  getMarket,
  leagueShort,
  outcomeLabel,
  type MarketDisagreementRow,
  type MarketSplit,
  type Outcome,
} from "@/lib/data";
import { Crumbs } from "../../components/Crumbs";

export const metadata = {
  title: "Versus the market",
  description:
    "The model's published probabilities measured against bookmaker closing odds — a statistical benchmark, never betting advice.",
};

const OUTCOMES: Outcome[] = ["home", "draw", "away"];

/** "1819" -> "2018/19". The builder keeps the pipeline's season codes. */
const seasonLabel = (s: string) => `20${s.slice(0, 2)}/${s.slice(2)}`;

const f4 = (v: number | null | undefined) =>
  v == null ? "—" : v.toFixed(4);
const signed = (v: number | null | undefined) =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(4)}`;
const pct = (v: number) => `${Math.round(v * 100)}%`;

/** Negative gap is the model's win; it is the whole page in one colour. */
function Gap({ v }: { v: number | null | undefined }) {
  if (v == null) return <span className="text-ink-3">—</span>;
  const cls = v < 0 ? "text-good" : v > 0 ? "text-bad" : "text-ink-2";
  return <span className={`num font-semibold ${cls}`}>{signed(v)}</span>;
}

function Better({ v }: { v: string | null | undefined }) {
  if (!v || v === "tie") return <span className="text-ink-3">{v ?? "—"}</span>;
  return (
    <span className={v === "model" ? "font-semibold text-good" : "text-ink-2"}>
      {v}
    </span>
  );
}

function Triplet({ p, bold }: { p: Record<Outcome, number>; bold: Outcome }) {
  return (
    <span className="num whitespace-nowrap">
      {OUTCOMES.map((k, i) => (
        <span key={k}>
          {i > 0 && <span className="text-ink-3"> / </span>}
          <span className={k === bold ? "font-semibold" : "text-ink-2"}>
            {pct(p[k])}
          </span>
        </span>
      ))}
    </span>
  );
}

const TH = "px-3 py-2 text-right font-semibold";
const TH_L = "py-2 pl-4 pr-3 text-left font-semibold";
const TD = "num px-3 py-2 text-right";

/** Decimal prices, the way the round page and a betting sheet both spell
 *  them. The model's is 1/p, the market's is the closing price as published,
 *  margin and all — so the two columns are not quite like for like, and the
 *  caption under the table says so. */
function Prices({ p, bold }: { p: Record<Outcome, number>; bold: Outcome }) {
  return (
    <span className="num whitespace-nowrap text-[12px]">
      {OUTCOMES.map((k, i) => (
        <span key={k}>
          {i > 0 && <span className="text-ink-3"> / </span>}
          <span className={k === bold ? "font-semibold text-ink" : "text-ink-3"}>
            {p[k].toFixed(2)}
          </span>
        </span>
      ))}
    </span>
  );
}

function DisagreementTable({ rows }: { rows: MarketDisagreementRow[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-card">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
            <th className={TH_L}>Fixture</th>
            <th className="px-3 py-2 text-left font-semibold">
              Model 1 / X / 2
              <span className="block normal-case tracking-normal text-ink-3">probability · fair price</span>
            </th>
            <th className="px-3 py-2 text-left font-semibold">
              Market 1 / X / 2
              <span className="block normal-case tracking-normal text-ink-3">implied · closing odds</span>
            </th>
            <th className={TH}>Max diff</th>
            <th className={TH}>Result</th>
            <th className="py-2 pl-3 pr-4 text-left font-semibold">Closer</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`${r.league}${r.kickoff}${r.home}${r.away}`}
              className="border-t border-line"
            >
              <td className="py-2 pl-4 pr-3">
                <div className="whitespace-nowrap">
                  {r.home} <span className="text-ink-3">v</span> {r.away}
                  {r.retro && (
                    <span
                      className="ml-1.5 rounded-full border border-dashed border-line px-1.5 py-px text-[10px] uppercase tracking-wider text-ink-3"
                      title="Reconstructed walk-forward, priced after the result was known."
                    >
                      rebuilt
                    </span>
                  )}
                </div>
                <div className="num text-[11px] text-ink-3">
                  {leagueShort(r.league)} · {r.kickoff}
                </div>
              </td>
              <td className="px-3 py-2">
                <Triplet p={r.model} bold={r.result} />
                {r.fair && (
                  <div>
                    <Prices p={r.fair} bold={r.result} />
                  </div>
                )}
              </td>
              <td className="px-3 py-2">
                <Triplet p={r.market} bold={r.result} />
                {r.odds && (
                  <div title={`closing odds as published (${r.odds_column}), bookmaker margin included`}>
                    <Prices p={r.odds} bold={r.result} />
                  </div>
                )}
              </td>
              <td className={TD}>{r.max_diff.toFixed(2)}</td>
              <td className={`${TD} font-semibold`}>{outcomeLabel[r.result]}</td>
              <td className="py-2 pl-3 pr-4">
                <Better v={r.better} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function MarketPage() {
  const m = getMarket();
  if (!m)
    return (
      <div>
        <Crumbs
          trail={[
            { href: "/predictor", label: "Predictor" },
            { label: "Versus the market" },
          ]}
        />
        <p className="max-w-3xl text-[13.5px] text-ink-2">
          The market benchmark has not been built yet. Once the daily run has
          downloaded closing odds for the fixtures the model has already
          priced, this page will show how far its probabilities sit from the
          bookmakers&apos; — a statistical comparison, never betting advice.
        </p>
      </div>
    );

  const live: MarketSplit =
    m.live.splits.live.n > 0 ? m.live.splits.live : m.live.splits.all;
  const liveLabel = m.live.splits.live.n > 0 ? "live" : "all graded";
  const hist = m.live.histogram;
  const histMax = Math.max(1, ...OUTCOMES.flatMap((k) => hist[k]));
  const rows = m.live.disagreement.rows;
  const SHOW = 30;
  const info = m.information_test;
  const share = (c: Record<string, number>) => {
    const total = Object.values(c).reduce((a, b) => a + b, 0) || 1;
    return Math.round((c.pinnacle_closing / total) * 100);
  };
  const pinLive = share(m.odds_column_used.live);
  const pinHist = share(m.odds_column_used.historical);

  return (
    <div>
      <Crumbs
        trail={[
          { href: "/predictor", label: "Predictor" },
          { label: "Versus the market" },
        ]}
      />
      <p className="max-w-3xl text-[13.5px] text-ink-2">
        The closing price at a sharp bookmaker is the best public forecast of a
        football match: by kickoff it has absorbed every model and every
        professional&apos;s money, and very little beats it over a season. So
        this is the yardstick I hold my own probabilities to. Every fixture
        below has already been played; I take the market&apos;s closing odds,
        strip the bookmaker&apos;s margin, and score both of us against what
        happened. This page measures the model against the market — not your
        bets, and not anyone&apos;s.
      </p>
      <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
        Lower log loss is better; the gap is model minus market in nats, so a
        negative number means I was closer. Odds from {m.source}, margin
        removed by{" "}
        {m.margin_method === "shin" ? "Shin's method" : "proportional normalisation"}
        . The frozen seasons are scored against Pinnacle&apos;s closing price
        ({pinHist}% of those rows); the sheet has carried no Pinnacle price
        since January 2026, so this season&apos;s calls ({pinLive}% Pinnacle)
        are scored against the closing average across books, a softer line.
      </p>

      {/* Four figures: phone tiles two-up, a row from `sm`, like the track
          record's card so the two pages read as one. */}
      <div className="num mt-5 grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-line bg-card px-4 py-4 sm:flex sm:justify-evenly sm:gap-8 sm:px-5">
        {[
          { label: `${liveLabel} calls joined`, value: String(live.n) },
          { label: "Model log loss", value: f4(live.model?.log_loss) },
          { label: "Market log loss", value: f4(live.market?.log_loss) },
          { label: "Gap (nats)", value: <Gap v={live.gap} /> },
        ].map((s) => (
          <div key={s.label}>
            <div className="text-[11px] uppercase tracking-wider text-ink-3">
              {s.label}
            </div>
            <div className="text-[22px] font-semibold">{s.value}</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[12.5px] text-ink-3">
        {m.live.join.joined} of {m.live.join.graded} graded calls matched a
        priced fixture
        {m.live.join.unjoined.length > 0 &&
          ` (${m.live.join.unjoined.length} unmatched: postponed and replayed on another date)`}
        . For scale, guessing a third each way scores{" "}
        <span className="num">{f4(live.uniform?.log_loss)}</span> and the
        outcome base rate of these rows{" "}
        <span className="num">{f4(live.base_rate?.log_loss)}</span>.
        {m.live.splits.reconstructed.n > 0 && (
          <>
            {" "}
            Reconstructed rounds ({m.live.splits.reconstructed.n} calls, priced
            after the fact): model{" "}
            <span className="num">{f4(m.live.splits.reconstructed.model?.log_loss)}</span>
            , market{" "}
            <span className="num">{f4(m.live.splits.reconstructed.market?.log_loss)}</span>
            .
          </>
        )}
      </p>

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">When we disagree</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          Each graded fixture is bucketed by the largest difference between my
          probability and the market&apos;s across the three outcomes. If the
          model knew something, the rows where it strays furthest are where it
          would show; if it is only noise, those are where it loses most.
        </p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                <th className={TH_L}>Max difference</th>
                <th className={TH}>Calls</th>
                <th className={TH}>Model log loss</th>
                <th className={TH}>Market log loss</th>
                <th className="py-2 pl-3 pr-4 text-left font-semibold">Closer</th>
              </tr>
            </thead>
            <tbody>
              {m.live.disagreement.buckets.map((b) => (
                <tr key={b.bucket} className="border-t border-line">
                  <td className="num py-2.5 pl-4 pr-3">{b.bucket}</td>
                  <td className={`${TD} text-ink-3`}>{b.n}</td>
                  <td className={TD}>{f4(b.model_log_loss)}</td>
                  <td className={TD}>{f4(b.market_log_loss)}</td>
                  <td className="py-2.5 pl-3 pr-4">
                    <Better v={b.better} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Eight frozen seasons</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          This season is a few hundred calls; the statistics live here. For
          each season from 2018/19 I rebuilt the model as it would have stood
          the summer before, priced every fixture, and scored it against that
          season&apos;s closing odds. &ldquo;Blend&rdquo; is the recipe the
          site publishes; &ldquo;layer&rdquo; is the alternative it replaced.
        </p>
        {m.historical.seasons.length === 0 ? (
          <p className="mt-3 text-[13px] text-ink-3">
            Not available yet{m.historical.note ? `: ${m.historical.note}` : "."}
          </p>
        ) : (
          <>
            <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-[13.5px]">
                <thead>
                  <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                    <th className={TH_L}>Season</th>
                    <th className={TH}>Fixtures</th>
                    <th className={TH}>Blend</th>
                    <th className={TH}>Market</th>
                    <th className={TH}>Gap</th>
                    <th className={TH}>Layer</th>
                    <th className="py-2 pl-3 pr-4 text-right font-semibold">Layer gap</th>
                  </tr>
                </thead>
                <tbody>
                  {m.historical.seasons.map((s) => (
                    <tr key={s.season} className="border-t border-line">
                      <td className="num py-2.5 pl-4 pr-3">{seasonLabel(s.season)}</td>
                      <td className={`${TD} text-ink-3`}>{s.n.toLocaleString("en-GB")}</td>
                      <td className={TD}>{f4(s.blend_log_loss)}</td>
                      <td className={TD}>{f4(s.market_log_loss)}</td>
                      <td className={TD}>
                        <Gap v={s.blend_gap} />
                      </td>
                      <td className={`${TD} text-ink-2`}>{f4(s.layer_log_loss)}</td>
                      <td className="num py-2.5 pl-3 pr-4 text-right">
                        <Gap v={s.layer_gap} />
                      </td>
                    </tr>
                  ))}
                  {m.historical.pooled && (
                    <tr className="border-t-2 border-line bg-[#fafbfb] font-medium">
                      <td className="py-2.5 pl-4 pr-3">All</td>
                      <td className={`${TD} text-ink-3`}>
                        {m.historical.pooled.n.toLocaleString("en-GB")}
                      </td>
                      <td className={TD}>{f4(m.historical.pooled.blend_log_loss)}</td>
                      <td className={TD}>{f4(m.historical.pooled.market_log_loss)}</td>
                      <td className={TD}>
                        <Gap v={m.historical.pooled.blend_gap} />
                      </td>
                      <td className={`${TD} text-ink-2`}>
                        {f4(m.historical.pooled.layer_log_loss)}
                      </td>
                      <td className="num py-2.5 pl-3 pr-4 text-right">
                        <Gap v={m.historical.pooled.layer_gap} />
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[12.5px] text-ink-3">
              {m.historical.leagues.map(leagueShort).join(", ")};{" "}
              {m.historical.join.joined.toLocaleString("en-GB")} of{" "}
              {m.historical.join.rows.toLocaleString("en-GB")} walk-forward
              fixtures matched a closing price.
            </p>
          </>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Does it know anything the market does not?</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          Losing to the market on log loss is expected; the sharper question
          is whether adding my probabilities to the market&apos;s improves the
          forecast at all. I fit a multinomial regression of the result on the
          market&apos;s log-probabilities alone and then on market plus model,
          leaving one season out at a time, and bootstrap the model&apos;s
          weight over fixtures.
        </p>
        <p className="mt-2 max-w-3xl rounded-xl border border-line bg-card px-4 py-3 text-[13.5px]">
          {info.per_season ? info.verdict : `Not available yet: ${info.verdict}.`}
          {info.per_season && info.pooled && (
            <span className="text-ink-3">
              {" "}
              (n = {info.n.toLocaleString("en-GB")}; pooled out-of-sample log
              loss <span className="num">{f4(info.pooled.market_only)}</span>{" "}
              market-only, <span className="num">{f4(info.pooled.stacked)}</span>{" "}
              stacked; {info.resamples} resamples.)
            </span>
          )}
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Where the probabilities differ</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          Model minus market, per outcome, over every joined graded call. A
          pile to the right of zero means I rate that outcome higher than the
          market does; a wide spread means I disagree with it often.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {OUTCOMES.map((k) => (
            <div key={k} className="rounded-xl border border-line bg-card p-3">
              <div className="mb-2 text-[11px] uppercase tracking-wider text-ink-3">
                {k} ({outcomeLabel[k]})
              </div>
              <ul className="space-y-1">
                {hist.bins.map((b, i) => {
                  const n = hist[k][i];
                  return (
                    <li key={b.label} className="flex items-center gap-2">
                      <span className="num w-[44px] shrink-0 text-right text-[10.5px] text-ink-3">
                        {b.label}
                      </span>
                      <span className="h-2 flex-1 overflow-hidden rounded-full bg-[#eceff1]">
                        <span
                          className={`block h-full rounded-full ${
                            b.from < 0 ? "bg-ink-3" : "bg-home"
                          }`}
                          style={{ width: `${(n / histMax) * 100}%` }}
                        />
                      </span>
                      <span className="num w-[30px] shrink-0 text-right text-[11px] text-ink-2">
                        {n || ""}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[12.5px] text-ink-3">
          Each bin starts at the value shown and runs 0.05 wide; grey is below
          the market, blue above it.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">The biggest disagreements, graded</h2>
        <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">
          Every played fixture where my probability and the market&apos;s
          differed by more than {m.live.disagreement.threshold} on some
          outcome, largest first. The result&apos;s column is in bold;
          &ldquo;closer&rdquo; is whoever gave it the higher probability.
          Nothing here is unplayed, and nothing here is a price to take.
        </p>
        {rows.length === 0 ? (
          <p className="mt-3 text-[13px] text-ink-3">No graded disagreements yet.</p>
        ) : (
          <div className="mt-3">
            <DisagreementTable rows={rows.slice(0, SHOW)} />
            {rows.length > SHOW && (
              <details className="mt-2">
                <summary className="cursor-pointer text-[12.5px] text-ink-2 hover:text-ink">
                  Show the other {rows.length - SHOW} rows
                </summary>
                <div className="mt-2">
                  <DisagreementTable rows={rows.slice(SHOW)} />
                </div>
              </details>
            )}
          </div>
        )}
      </section>

      <p className="mt-10 border-t border-line pt-4 text-[12.5px] text-ink-3">
        Probabilities and fair prices only — never betting advice.
      </p>
    </div>
  );
}
