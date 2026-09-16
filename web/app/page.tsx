import Link from "next/link";
import { getRecord } from "@/lib/data";

const TOOLS = [
  {
    href: "/predictor",
    name: "Predictor",
    tagline: "What every match is worth",
    body: "A probability and a fair price for all 380 fixtures in each of the big five. Every call is recorded before kickoff and graded afterwards — including the wrong ones.",
    status: "live",
  },
  {
    href: "/mental",
    name: "Mental",
    tagline: "Who holds up under pressure",
    body: "A dependability ranking for players and teams, built from actions measured by game state. Not who is best — who is reliable when it is level, behind, or protecting a lead.",
    status: "in validation",
  },
  {
    href: "/viz",
    name: "Visualiser",
    tagline: "Every event, in three dimensions",
    body: "Shots, passes and duels rendered on a real pitch: click a shot to swing the camera behind it and see the angle, the chance quality and where it finished.",
    status: "in build",
  },
];

const STATUS_STYLE: Record<string, string> = {
  live: "bg-[#e8f3ec] text-good border-[#c2e0cd]",
  "in validation": "bg-[#fbf3da] text-[#6b5606] border-[#e4d49a]",
  "in build": "bg-[#f0f1f2] text-ink-2 border-line",
};

export default function Home() {
  const record = getRecord();

  return (
    <div>
      <section className="max-w-3xl">
        <h1 className="font-display text-[30px] leading-[1.25] tracking-[0.01em]">
          A football model that shows its work.
        </h1>
        <p className="mt-3 text-ink-2">
          Three tools on one data platform: a calibrated match predictor, a
          dependability benchmark for players and teams, and a 3D explorer for
          the raw events underneath both. Updated every round.
        </p>
      </section>

      {record?.calibration?.length ? (
        <section className="mt-8 rounded-xl border border-line bg-card p-5">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-ink-3">
            The only claim that matters
          </h2>
          <p className="mt-2 max-w-3xl text-[13.5px] text-ink-2">
            Anyone can publish predictions. The test is whether the stated
            probabilities are honest: when this model says 45%, does it happen
            about 45% of the time? Across {record.graded} graded predictions:
          </p>
          <div className="num mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {record.calibration.map((b) => (
              <div key={b.bucket} className="rounded-lg border border-line p-3">
                <div className="text-[11.5px] text-ink-3">
                  said {b.said}% · n={b.n}
                </div>
                <div className="mt-0.5 text-[22px] font-semibold">
                  {b.landed}%
                </div>
                <div className="text-[11.5px] text-ink-3">actually landed</div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {TOOLS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="group flex flex-col rounded-xl border border-line bg-card p-5 transition-colors hover:border-ink-3"
          >
            <div className="flex items-center justify-between">
              <h2 className="font-display text-[18px] tracking-[0.01em]">
                {t.name}
              </h2>
              <span
                className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider ${STATUS_STYLE[t.status]}`}
              >
                {t.status}
              </span>
            </div>
            <div className="mt-0.5 text-[13.5px] text-ink-2">{t.tagline}</div>
            <p className="mt-3 flex-1 text-[13px] leading-relaxed text-ink-2">
              {t.body}
            </p>
            <div className="mt-4 text-[13px] font-medium text-home">
              Open {t.name} →
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
