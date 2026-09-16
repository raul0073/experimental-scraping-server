import Link from "next/link";

function Stage({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="num flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-card text-[12.5px] font-semibold text-ink-2">
          {n}
        </div>
        <div className="mt-1 w-px flex-1 bg-line" />
      </div>
      <div className="pb-7">
        <h3 className="text-[15px] font-semibold">{title}</h3>
        <div className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          {children}
        </div>
      </div>
    </div>
  );
}

export default function HowItWorksPage() {
  return (
    <div>
      <h1 className="font-display text-[26px] tracking-[0.01em]">
        How this works
      </h1>
      <p className="mt-2 max-w-3xl text-[13.5px] text-ink-2">
        The whole pipeline, honestly: what the model reads, what it does with
        it, and what it deliberately refuses to do. Where something is planned
        rather than built, it says so.
      </p>

      <section className="mt-8">
        <h2 className="text-[17px] font-semibold">What happens, in order</h2>
        <div className="mt-4">
          <Stage n={1} title="Read the shots, not the scores">
            Every shot in the big five: where it was taken from, what it was
            worth (xG), who took it, which minute, and what happened. Roughly
            50,000 of them. Results are a terrible measure of a football team —
            a deflected winner and a hammering both read as three points. Chance
            quality is a far better one, so that is what gets stored.
          </Stage>

          <Stage n={2} title="Turn shots into team strength">
            Each club gets an attack and a defence rating from its last 38
            matches, weighted so recent games count more. Two corrections that
            matter: ratings are{" "}
            <strong className="font-semibold text-ink">
              opponent-adjusted
            </strong>{" "}
            — feasting on the bottom three is not the same as competing with the
            top three — and promoted clubs start on a measured archetype of how
            promoted clubs actually perform, rather than on a flattering blank
            slate.
          </Stage>

          <Stage n={3} title="Map where a team lives on the pitch">
            The same shots, grouped by area, give every club nine functional
            zones: three attacking lanes, three defensive lanes, and midfield
            split by <em>job</em> rather than by position — progression, press,
            and screen. This is what produces the battle maps, and it is
            currently built from{" "}
            <strong className="font-semibold text-ink">team-level</strong> data.
            Zones driven by which players occupy which space is the next step,
            not the current one.
          </Stage>

          <Stage n={4} title="Price the fixture">
            Strength ratings become an expected goal count for each side in this
            specific match, which becomes a full grid of scorelines, which
            becomes three probabilities. Two adjustments sit on top: the zone
            matchup nudges those expected goals through four fitted channels
            (the strongest being a side&apos;s progression against the
            opponent&apos;s midfield screen), and the draw probability is owned
            by a classifier trained on 17,134 matches, because draws behave
            differently from wins.
          </Stage>

          <Stage n={5} title="Commit it before kickoff">
            The prediction is written down and never revised. After the match it
            is graded against what happened. That record — not the model, not
            the maths — is the product:{" "}
            <Link
              href="/predictor/history"
              className="text-home underline underline-offset-2"
            >
              see the track record
            </Link>
            .
          </Stage>

          <Stage n={6} title="Replay the season ten thousand times">
            Every remaining fixture is priced, then the season is played out
            repeatedly to produce title, European and relegation odds. Each
            replay also draws its own per-team strength error, because our
            estimate of a club is itself uncertain — without that, the
            projections come out about 1.45× too confident, which we measured
            rather than assumed.
          </Stage>
        </div>
      </section>

      <section className="mt-2 rounded-xl border border-line bg-card p-5">
        <h2 className="text-[17px] font-semibold">
          How anything gets into the model
        </h2>
        <p className="mt-2 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          Nothing ships because it sounds clever. An idea is fitted on one
          season, frozen, and then judged on a season it has never seen — and it
          only ships if it beats what is already there. Most ideas fail, and the
          failures are kept on the record:
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-[#c2e0cd] bg-[#f4faf6] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-good">
              Passed
            </div>
            <div className="mt-1 text-[13.5px] font-semibold">
              Zone channels
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
              The old version squashed all nine zone matchups into a single
              number, which turned out to be redundant with the strength
              ratings. Kept apart as four separate channels, they beat it on an
              unseen season by roughly four times the old edge — so they
              shipped.
            </p>
          </div>
          <div className="rounded-lg border border-[#f0c4bf] bg-[#fdf6f5] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-bad">
              Rejected
            </div>
            <div className="mt-1 text-[13.5px] font-semibold">
              Availability shock
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
              Tracking which key players had been missing looked promising — it
              improved the model on one season. Tested across two, the
              coefficients flipped sign. A real effect does not reverse
              direction, so it was thrown away. The likely reason is that the
              rolling window already absorbs absence.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-[17px] font-semibold">What it does not do</h2>
        <ul className="mt-3 max-w-3xl space-y-2 text-[13.5px] leading-relaxed text-ink-2">
          <li>
            <strong className="font-semibold text-ink">
              It never reads bookmakers&apos; odds.
            </strong>{" "}
            It states what an outcome is worth and stops there. Comparing that
            with a price is the reader&apos;s job, and telling anyone what to
            bet is nobody&apos;s.
          </li>
          <li>
            <strong className="font-semibold text-ink">
              It does not know tonight&apos;s line-up.
            </strong>{" "}
            No team-news or injury feed is used, so a late absence is invisible
            to it. Anything claiming otherwise would be guessing.
          </li>
          <li>
            <strong className="font-semibold text-ink">
              It does not model managers, cup runs or transfers.
            </strong>{" "}
            A January signing or a new manager only reaches the ratings through
            results, slowly.
          </li>
          <li>
            <strong className="font-semibold text-ink">
              The player ratings do not feed the predictions.
            </strong>{" "}
            They are a separate, unvalidated experiment — see{" "}
            <Link
              href="/mental"
              className="text-home underline underline-offset-2"
            >
              Mental
            </Link>
            .
          </li>
        </ul>
      </section>

      <section className="mt-8 rounded-xl border border-[#e4d49a] bg-[#fdfaf0] p-5">
        <h2 className="text-[17px] font-semibold">What is being built next</h2>
        <p className="mt-2 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          Everything above runs on shot data. The next version runs on{" "}
          <strong className="font-semibold text-ink">every event</strong> — each
          pass, duel, tackle, carry and error, with its position, its outcome
          and its minute. Because the minute can be matched to the scoreline at
          that moment, it becomes possible to ask the question this project
          exists for:{" "}
          <em>
            not how often a player beats his man, but how often he still tries
            when his team is losing.
          </em>{" "}
          Intent, measured under pressure.
        </p>
        <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          That unlocks three things in order: player ratings built from actions
          rather than involvement, zones built from who actually occupies the
          space, and a team rating that can be compared against the sum of its
          players — the difference being what the collective adds or destroys.
          None of it is published until it passes the same gate as everything
          else.
        </p>
      </section>
    </div>
  );
}
