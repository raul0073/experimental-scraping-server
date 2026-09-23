import Link from "next/link";

import { Crumbs } from "../components/Crumbs";

/** WHAT WE TRIED AND THREW AWAY.
 *
 *  Every project publishes what worked. This one has an unusual amount of
 *  evidence about what did NOT, because each idea was tested against the
 *  shipping model on held-out fixtures and most of them lost — and that
 *  record is the most honest thing the site can show. A model you can only
 *  see the successes of is a model you have no reason to trust.
 *
 *  The rule throughout: a paired bootstrap on the fixtures an idea actually
 *  touches, and nothing ships on a story. P(better) is the share of
 *  resamples in which the new version beat the old one. Around 0.5 is a coin
 *  flip. None of these got near enough to 0.95 to ship.
 */
export const metadata = {
  title: "What we rejected — Predictorous",
  description:
    "Ideas that were tested against the shipping model and lost, with the numbers.",
};

type Entry = {
  idea: string;
  hope: string;
  result: string;
  verdict: "rejected" | "not proven" | "reversed";
  stat?: string;
};

const ENTRIES: Entry[] = [
  {
    idea: "A team-quality layer inside the predictor",
    hope: "Twenty-eight opponent-adjusted team metrics ought to know something about Saturday that goal-based ratings do not.",
    result:
      "It moved the log loss by +0.0001. Not a small win — no win. The information was already in the chance rates the model reads.",
    verdict: "rejected",
    stat: "+0.0001 log loss",
  },
  {
    idea: "The manager as a separate effect",
    hope: "A new manager changes a side, so a manager term should carry signal the club's own history does not.",
    result:
      "Tested four independent ways and rejected each time. What survives is SELECTION — who he picks — and that is already visible in the squad. Scoping the whole history to the current spell made it actively worse.",
    verdict: "rejected",
    stat: "−0.0132 log loss when fully spell-scoped",
  },
  {
    idea: "Availability corrections to a club's history",
    hope: "A side missing three regulars is not the side its record describes, so the history should be discounted.",
    result:
      "The right shape — it has the property that a full-strength side gets no correction at all — but the effect could not be separated from noise on 232 fixtures.",
    verdict: "not proven",
    stat: "P(better) = 0.633",
  },
  {
    idea: "Blending the process-Elo arm into the shipped model",
    hope: "Two independent models usually beat one.",
    result:
      "Better on the sample, nowhere near significantly. It has not shipped and will not until a bigger sample says so.",
    verdict: "not proven",
    stat: "P(better) = 0.790",
  },
  {
    idea: "Seeding the model with a manager's record",
    hope: "Same idea as above, from the other end.",
    result: "Closer, still short. Same answer: wait for the data.",
    verdict: "not proven",
    stat: "P(better) = 0.840",
  },
  {
    idea: "Context features for the draw model",
    hope: "Points-per-game gap, how far into the season it is, whether both sides are comfortable — a drawish match ought to be predictable from its situation.",
    result:
      "The model assigned them coefficients of ±0.001 to 0.04 and out-of-sample performance did not move. Consistent with the separate finding that drawish weeks are random clumping: overdispersion measured 1.0 across ten league-seasons.",
    verdict: "rejected",
    stat: "28.9% vs 29.6%, inside noise",
  },
  {
    idea: "Zones built from individual players",
    hope: "If a side's zone profile is the sum of who plays in it, building it from players should beat building it from team totals.",
    result: "It did not beat the shipping model. The team totals already had it.",
    verdict: "rejected",
  },
  {
    idea: "“Volume beats weighting” — my own claim",
    hope: "I argued that how much a side creates matters more than how the chances are weighted, and had a result to show for it.",
    result:
      "The result came from a conversion constant I had fitted by log loss instead of solving. Projections came out at 3.77 goals a game against an actual 2.75. Solving it properly INVERTED the ranking and falsified the claim.",
    verdict: "reversed",
    stat: "3.77 projected vs 2.75 actual",
  },
];

const STYLE: Record<Entry["verdict"], string> = {
  rejected: "bg-[#fae5d9] text-[#a34a22] border-[#eec4ab]",
  "not proven": "bg-[#faf0cd] text-[#6b5606] border-[#e4d49a]",
  reversed: "bg-[#efe3f7] text-[#6b3a8a] border-[#dcc7ea]",
};

export default function RejectedPage() {
  return (
    <div>
      <Crumbs trail={[{ label: "What we rejected" }]} />
      <h1 className="font-display text-[24px] tracking-[0.01em]">
        What we rejected
      </h1>
      <p className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        Every idea below was built, tested against the shipping model on
        fixtures it had not seen, and lost. They are here because a model you
        can only see the successes of is a model you have no reason to trust —
        and because several of these are the ideas anyone would try next.
      </p>
      <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-3">
        The test is a paired bootstrap on the fixtures an idea actually
        touches. <span className="num">P(better)</span> is the share of
        resamples in which the new version beat the old one — about{" "}
        <span className="num">0.5</span> is a coin flip. Nothing here got near
        enough to <span className="num">0.95</span> to ship, so nothing here
        shipped.
      </p>

      <div className="mt-6 space-y-3">
        {ENTRIES.map((e) => (
          <article
            key={e.idea}
            className="rounded-xl border border-line bg-card p-4"
          >
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-[15px] font-semibold text-ink">{e.idea}</h2>
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STYLE[e.verdict]}`}
              >
                {e.verdict}
              </span>
              {e.stat && (
                <span className="num ml-auto text-[12.5px] text-ink-3">
                  {e.stat}
                </span>
              )}
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              <span className="text-ink-3">The hope. </span>
              {e.hope}
            </p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">
              <span className="text-ink-3">What happened. </span>
              {e.result}
            </p>
          </article>
        ))}
      </div>

      <section className="mt-8 max-w-3xl rounded-xl border border-line bg-[#fbfcfd] p-5">
        <h2 className="text-[11px] uppercase tracking-[0.14em] text-ink-3">
          What this leaves
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
          A shipping model that beats picking the home side by{" "}
          <span className="num">9.6</span> points of accuracy, is{" "}
          <span className="num">6.9%</span> better than league base rates on
          log loss, and is calibrated where the mass is — matches it calls at
          25–35% happen 29% of the time. Everything above was an attempt to
          improve on that and did not.
        </p>
        <p className="mt-2 text-[12.5px] leading-relaxed text-ink-3">
          The honest constraint is sample size. Most of these were tested on a
          few hundred fixtures, which cannot separate ideas that differ by a
          few thousandths of log loss. They are not dead — they are unproven,
          and the difference matters. Four more leagues are being collected
          for exactly this reason.
        </p>
        <p className="mt-3 text-[12.5px] text-ink-3">
          <Link href="/predictor/history" className="text-home underline underline-offset-2">
            The track record
          </Link>{" "}
          is what the model that survived all this has actually done.
        </p>
      </section>
    </div>
  );
}
