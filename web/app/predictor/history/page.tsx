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
      </p>

      {/* Four figures side by side need 400px they do not have on a phone,
          so they tile two-up and only become a row from `sm`. */}
      <div className="num mt-5 grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-line bg-card px-4 py-4 sm:flex sm:justify-evenly sm:gap-8 sm:px-5">
        {[
          { label: "Calls graded", value: record.graded },
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
          Grey is what the model claimed, blue is what happened. Landing at or
          slightly above the claim means it is honest and a little
          underconfident — the safe direction to be wrong. Buckets with few
          calls will move a lot; treat small samples as noise.
        </p>
      </section>

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
                  {v.n} calls · open →
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
