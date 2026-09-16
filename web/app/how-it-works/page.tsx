import Link from "next/link";

const BOX = { r: 6 };

function Node({
  x,
  y,
  w,
  h,
  fill,
  stroke,
  title,
  sub,
  bold,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  fill: string;
  stroke: string;
  title: string;
  sub?: string;
  bold?: boolean;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={BOX.r} fill={fill} stroke={stroke} />
      <text
        x={x + w / 2}
        y={sub ? y + h / 2 - 8 : y + h / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={bold ? 14.5 : 13.5}
        fontWeight={bold ? 700 : 600}
        fill="#1f2429"
      >
        {title}
      </text>
      {sub ? (
        <text
          x={x + w / 2}
          y={y + h / 2 + 11}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={11.5}
          fill="#55606b"
        >
          {sub}
        </text>
      ) : null}
    </g>
  );
}

/** The target pipeline, with zones as the organising unit rather than a
 *  by-product: events locate every action, players own those actions, zones
 *  are the players who occupy them, and the team is the sum of its zones. */
function Flow() {
  const a = "#8a949e";
  return (
    <svg
      viewBox="0 0 720 512"
      className="mt-5 w-full"
      role="img"
      aria-label="Pipeline: every event is stamped with the match state, becomes a player ranking, which computes the team's zones; that joins team counting stats and a managerial edge ranking to feed the predictor through a validation gate."
    >
      <defs>
        <marker
          id="fa"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="6"
          markerHeight="6"
          orient="auto-start-reverse"
        >
          <path
            d="M2 1L8 5L2 9"
            fill="none"
            stroke={a}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </marker>
      </defs>

      <Node
        x={210}
        y={12}
        w={300}
        h={50}
        fill="#f3f4f6"
        stroke="#d5d9dd"
        title="Every event"
        sub="player · position · outcome · minute"
      />
      <Node
        x={170}
        y={92}
        w={380}
        h={52}
        fill="#f3f4f6"
        stroke="#d5d9dd"
        title="Stamped with the state at that minute"
        sub="level · behind · ahead · a man down · late"
      />
      <Node
        x={190}
        y={174}
        w={340}
        h={54}
        fill="#e3eef7"
        stroke="#b9d5e8"
        title="PLAYER RANKING"
        sub="what he tried · won · controlled, by state"
      />
      <Node
        x={150}
        y={258}
        w={420}
        h={58}
        fill="#d8e8f4"
        stroke="#4a7ba6"
        title="TEAM ZONES COMPUTE"
        sub="a zone is the players who occupy it, weighted"
        bold
      />
      <Node
        x={78}
        y={348}
        w={272}
        h={54}
        fill="#faf0cd"
        stroke="#e4d49a"
        title="Team v team stats"
        sub="fbref counting stats"
      />
      <Node
        x={370}
        y={348}
        w={272}
        h={54}
        fill="#e8f3ec"
        stroke="#c2e0cd"
        title="Managerial edge"
        sub="his own ranking, from his history"
      />
      <Node
        x={210}
        y={438}
        w={300}
        h={52}
        fill="#ffffff"
        stroke="#d5d9dd"
        title="Predictor"
        sub="only what passes the gate"
      />

      <line x1={360} y1={62} x2={360} y2={88} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={360} y1={144} x2={360} y2={170} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={360} y1={228} x2={360} y2={254} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={290} y1={316} x2={214} y2={344} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={430} y1={316} x2={506} y2={344} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={214} y1={402} x2={330} y2={434} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
      <line x1={506} y1={402} x2={390} y2={434} stroke={a} strokeWidth="1.5" markerEnd="url(#fa)" />
    </svg>
  );
}

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
        <h2 className="text-[17px] font-semibold">
          What is being built next: zones as the unit
        </h2>
        <p className="mt-2 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          Everything above runs on 25 shots a match — about 1.8% of what
          actually happens. The next version runs on{" "}
          <strong className="font-semibold text-ink">every event</strong>:
          roughly 1,431 per match, each with the player, where on the pitch it
          happened, whether it came off, and the minute. The minute is the key
          that unlocks the rest, because it can be matched to the scoreline at
          that moment.
        </p>
        <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          The organising idea:{" "}
          <strong className="font-semibold text-ink">
            a team is as strong as the way it occupies space
          </strong>
          . Not how good its players are in the abstract — how often the left
          attacker actually runs at his man, how often the midfield tries the
          switch, what share of its duels a side wins in each area, where its
          attackers get their touches, and where it keeps losing the ball. A
          zone cannot be rated without the players who occupy it, so the zone
          and the player rating are the same measurement read at two levels.
        </p>
        <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          Two distinctions do a lot of work here.{" "}
          <strong className="font-semibold text-ink">
            Controlled, not touched
          </strong>{" "}
          — a touch counts deflections, blocks and miscontrols, which says
          nothing about where a player operates; what matters is where he had
          the ball and did something deliberate with it. And the state stamped
          on each event is not only the scoreline but{" "}
          <strong className="font-semibold text-ink">the man count</strong>: a
          red card changes a match more than a goal does, and how a side plays
          with ten is one of the most revealing things about it.
        </p>

        <Flow />

        <p className="mt-4 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          The manager is{" "}
          <strong className="font-semibold text-ink">ranked, not inferred</strong>
          . He gets his own record the same way a player does, built from his
          history rather than from this squad&apos;s zones: what his teams do
          when level, behind and a man down, how often they hold a lead or
          retrieve a lost one, their discipline, and how results compare with
          the chances created — across every club he has managed, which is what
          separates a manager from the team he inherited. It is the one layer we
          cannot start yet: nothing in our data records who was in charge, so
          managerial tenures have to be collected before any of it can be
          computed.
        </p>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <div>
            <h3 className="text-[13.5px] font-semibold">
              Intent, reported honestly
            </h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
              What matters is how often a player <em>tried</em>, not only how
              often it worked. But attempts alone would crown the wasteful, so
              attempt rate and success rate are published as two numbers, never
              blended into one that hides which half is doing the work.
            </p>
          </div>
          <div>
            <h3 className="text-[13.5px] font-semibold">
              Game state, without the trap
            </h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
              Weak teams are behind constantly, so raw &ldquo;performance while
              losing&rdquo; quietly rewards being bad. Everything is measured
              per minute spent in that state and against the player&apos;s{" "}
              <em>own</em> baseline — the question is never who was losing, but
              who changed when it got hard.
            </p>
          </div>
          <div>
            <h3 className="text-[13.5px] font-semibold">
              Opponent-adjusted, thresholded
            </h3>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
              A winger who spends a season against the league&apos;s worst
              full-backs will look elite unless the ratings correct for who he
              faced. And splitting by zone, state and game phase fragments the
              data fast, so every cell carries a minimum sample before it is
              shown.
            </p>
          </div>
        </div>

        <p className="mt-5 max-w-3xl text-[13px] leading-relaxed text-ink-2">
          None of this is published as fact until it passes the same gate as
          everything else: fitted on one season, frozen, judged on a season it
          has never seen. And the prediction baseline stays deliberately blind
          to all of it — a metric cannot be validated against a model that
          already contains it.
        </p>
      </section>
    </div>
  );
}
