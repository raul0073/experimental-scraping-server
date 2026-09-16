import Link from "next/link";

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
      <rect x={x} y={y} width={w} height={h} rx={6} fill={fill} stroke={stroke} />
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

/** The target pipeline: events locate every action, players own those
 *  actions, zones are the players who occupy them, and the team is what its
 *  zones add up to. */
function Flow() {
  const a = "#8a949e";
  const arrow = {
    stroke: a,
    strokeWidth: 1.5,
    markerEnd: "url(#fa)",
  } as const;
  return (
    <svg
      viewBox="0 0 720 512"
      className="w-full"
      role="img"
      aria-label="Every event is stamped with the match state, becomes a player ranking, which computes the team's zones; that joins team counting stats and a managerial edge ranking to feed the predictor through a validation gate."
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

      <Node x={210} y={12} w={300} h={50} fill="#f3f4f6" stroke="#d5d9dd"
        title="Every event" sub="player · position · outcome · minute" />
      <Node x={170} y={92} w={380} h={52} fill="#f3f4f6" stroke="#d5d9dd"
        title="Stamped with the state at that minute"
        sub="level · behind · ahead · a man down · late" />
      <Node x={190} y={174} w={340} h={54} fill="#e3eef7" stroke="#b9d5e8"
        title="PLAYER RANKING" sub="what he tried · won · controlled, by state" />
      <Node x={150} y={258} w={420} h={58} fill="#d8e8f4" stroke="#4a7ba6"
        title="TEAM ZONES COMPUTE"
        sub="a zone is the players who occupy it" bold />
      <Node x={78} y={348} w={272} h={54} fill="#faf0cd" stroke="#e4d49a"
        title="Team v team stats" sub="what they do, what they concede" />
      <Node x={370} y={348} w={272} h={54} fill="#e8f3ec" stroke="#c2e0cd"
        title="Managerial edge" sub="his own ranking, from his history" />
      <Node x={210} y={438} w={300} h={52} fill="#ffffff" stroke="#d5d9dd"
        title="Predictor" sub="only what passes the gate" />

      <line x1={360} y1={62} x2={360} y2={88} {...arrow} />
      <line x1={360} y1={144} x2={360} y2={170} {...arrow} />
      <line x1={360} y1={228} x2={360} y2={254} {...arrow} />
      <line x1={290} y1={316} x2={214} y2={344} {...arrow} />
      <line x1={430} y1={316} x2={506} y2={344} {...arrow} />
      <line x1={214} y1={402} x2={330} y2={434} {...arrow} />
      <line x1={506} y1={402} x2={390} y2={434} {...arrow} />
    </svg>
  );
}

function Stage({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="num flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-card text-[12.5px] font-semibold text-ink-2">
          {n}
        </div>
        <div className="mt-1 w-px flex-1 bg-line" />
      </div>
      <div className="pb-6">
        <h3 className="text-[15px] font-semibold">{title}</h3>
        <div className="mt-1 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          {children}
        </div>
      </div>
    </div>
  );
}

function Rule({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-card p-4">
      <h3 className="text-[13.5px] font-semibold">{title}</h3>
      <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{children}</p>
    </div>
  );
}

function Tag({ children, tone }: { children: React.ReactNode; tone: "now" | "next" }) {
  const style =
    tone === "now"
      ? "border-[#b9d5e8] bg-[#e3eef7] text-[#1c5b8a]"
      : "border-[#e4d49a] bg-[#faf0cd] text-[#6b5606]";
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider ${style}`}
    >
      {children}
    </span>
  );
}

export default function HowItWorksPage() {
  return (
    <div>
      <h1 className="font-display text-[26px] tracking-[0.01em]">
        How this works
      </h1>
      <p className="mt-2 max-w-3xl text-[13.5px] text-ink-2">
        Two halves: what runs today, and what it is being rebuilt into. The
        difference is marked throughout, because a model that blurs the two is
        selling something.
      </p>

      {/* ---------------------------------------------------------- today */}
      <div className="mt-9 flex items-center gap-3">
        <Tag tone="now">Running today</Tag>
        <h2 className="text-[18px] font-semibold">From shots to a published call</h2>
      </div>

      <div className="mt-5">
        <Stage n={1} title="Read the shots, not the scores">
          Every shot in the big five: where from, what it was worth, who took
          it, which minute, what happened. Results are a poor measure of a team
          — a deflected winner and a hammering both read as three points — so
          chance quality is what gets stored.
        </Stage>
        <Stage n={2} title="Turn shots into team strength">
          Each club gets attack and defence ratings from its last 38 matches,
          weighted toward recent games,{" "}
          <strong className="font-semibold text-ink">opponent-adjusted</strong>{" "}
          so feasting on the bottom three is not mistaken for competing with the
          top three. Promoted clubs start on a measured archetype rather than a
          flattering blank slate.
        </Stage>
        <Stage n={3} title="Map where a team lives on the pitch">
          The same shots, grouped by area, give nine functional zones per club:
          three attacking lanes, three defensive lanes, and midfield split by
          job — progression, press, screen. Defensive zones are built from what
          opponents produced against that side, and lanes are mirrored, so our
          left attack is judged against their right defence.
        </Stage>
        <Stage n={4} title="Price the fixture">
          Ratings become expected goals for this specific match, then a grid of
          scorelines, then three probabilities. The zone matchup nudges those
          expected goals through four fitted channels, and the draw probability
          is owned by a classifier trained on 17,134 matches.
        </Stage>
        <Stage n={5} title="Commit it before kickoff">
          The prediction is written down and never revised, then graded against
          what happened. That record is the product —{" "}
          <Link href="/predictor/history" className="text-home underline underline-offset-2">
            see it
          </Link>
          .
        </Stage>
        <Stage n={6} title="Replay the season ten thousand times">
          Every remaining fixture is priced and the season played out repeatedly.
          Each replay draws its own per-team strength error, because our estimate
          of a club is itself uncertain — without that, projections come out
          about 1.45× too confident, which we measured rather than assumed.
        </Stage>
      </div>

      {/* ----------------------------------------------------------- gate */}
      <section className="mt-2 rounded-xl border border-line bg-card p-5">
        <h2 className="text-[17px] font-semibold">How anything gets in</h2>
        <p className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
          Nothing ships because it sounds clever. An idea is fitted on one
          season, frozen, and judged on a season it has never seen — and only
          ships if it beats what is already there. Most ideas fail, and the
          failures stay on the record.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-lg border border-[#c2e0cd] bg-[#f4faf6] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-good">
              Passed
            </div>
            <div className="mt-1 text-[13.5px] font-semibold">Zone channels</div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
              Squashing all nine zone matchups into one number made them
              redundant with the strength ratings. Kept apart as four channels,
              they beat it on an unseen season by roughly four times the old
              edge.
            </p>
          </div>
          <div className="rounded-lg border border-[#f0c4bf] bg-[#fdf6f5] p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-bad">
              Rejected
            </div>
            <div className="mt-1 text-[13.5px] font-semibold">Availability shock</div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
              Tracking which key players were missing improved the model on one
              season. Across two, the coefficients flipped sign. A real effect
              does not reverse direction, so it was thrown away.
            </p>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------- limits */}
      <section className="mt-8">
        <h2 className="text-[17px] font-semibold">What it does not do</h2>
        <ul className="mt-3 max-w-3xl space-y-1.5 text-[13.5px] leading-relaxed text-ink-2">
          <li>
            <strong className="font-semibold text-ink">Never reads bookmakers&apos; odds.</strong>{" "}
            It states what an outcome is worth and stops. Comparing that with a
            price is the reader&apos;s job; telling anyone what to bet is
            nobody&apos;s.
          </li>
          <li>
            <strong className="font-semibold text-ink">Does not know tonight&apos;s line-up.</strong>{" "}
            No team-news or injury feed, so a late absence is invisible to it.
          </li>
          <li>
            <strong className="font-semibold text-ink">Does not model managers, cups or transfers.</strong>{" "}
            A new manager reaches the ratings only through results, slowly.
          </li>
          <li>
            <strong className="font-semibold text-ink">Player ratings do not feed predictions.</strong>{" "}
            They are a separate, unvalidated experiment — see{" "}
            <Link href="/mental" className="text-home underline underline-offset-2">
              Mental
            </Link>
            .
          </li>
        </ul>
      </section>

      {/* ---------------------------------------------------------- next */}
      <div className="mt-10 flex items-center gap-3">
        <Tag tone="next">Being built</Tag>
        <h2 className="text-[18px] font-semibold">Zones as the unit</h2>
      </div>

      <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        Everything above runs on 25 shots a match — about 1.8% of what happens.
        The next version runs on every event, roughly 1,431 per match, each with
        the player, the position, the outcome and the minute. The organising
        idea:{" "}
        <strong className="font-semibold text-ink">
          a team is as strong as the way it occupies space
        </strong>
        , and a zone cannot be rated without the players who occupy it — so the
        zone rating and the player rating become one measurement read at two
        levels.
      </p>

      <div className="mt-6 rounded-xl border border-line bg-card p-5">
        <Flow />
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <Rule title="Controlled, not touched">
          A touch counts deflections, blocks and miscontrols, which say nothing
          about where a player operates. What matters is where he had the ball
          and did something deliberate with it.
        </Rule>
        <Rule title="State includes the man count">
          A red card changes a match more than most goals do. Every event
          carries the scoreline and the man count at that minute, so how a side
          plays with ten becomes measurable.
        </Rule>
        <Rule title="Intent, reported honestly">
          How often a player <em>tried</em> is the mental signal — but attempts
          alone would crown the wasteful, so attempt rate and success rate are
          published as two numbers, never blended into one that hides which half
          is doing the work.
        </Rule>
        <Rule title="Game state, without the trap">
          Weak teams are behind constantly, so raw &ldquo;performance while
          losing&rdquo; rewards being bad. Everything is measured per minute
          spent in that state and against the player&apos;s own baseline: never
          who was losing, but who changed when it got hard.
        </Rule>
        <Rule title="Zone contributions are fitted, not assumed">
          Today&apos;s zone importance weights were a workaround for not knowing
          which player an action belonged to. With names on every event that
          crutch goes — but a flat sum would be just as much a guess, since the
          fitted channels already came out wildly unequal. The contributions get
          measured.
        </Rule>
        <Rule title="Fitted on the residual, so nothing is redundant">
          Zones and chance quality are computed from the same matches, so they
          overlap by nature. Zones and player ratings are therefore fitted
          against what the chance-quality baseline gets{" "}
          <em>wrong</em> — they can only earn weight for information it does not
          already contain. Redundancy is excluded by arithmetic, not by hope.
        </Rule>
        <Rule title="The manager is ranked, not inferred">
          He gets his own record the way a player does, from his history rather
          than this squad&apos;s zones: what his teams do level, behind and a
          man down, whether leads are held or retrieved, discipline, results
          against chances created — across every club he has managed. Blocked
          until managerial tenures are collected; nothing in our data records
          who was in charge.
        </Rule>
        <Rule title="Opponent-adjusted, with minimum samples">
          A winger who spent a season against the league&apos;s worst full-backs
          would read as elite without correcting for who he faced. And splitting
          by zone, state and game phase fragments the data fast, so every cell
          carries a minimum sample before it is shown.
        </Rule>
      </div>

      <p className="mt-5 max-w-3xl text-[13px] leading-relaxed text-ink-2">
        None of it is published as fact until it passes the same gate as
        everything else — and the prediction baseline stays deliberately blind
        to all of it, because a metric cannot be validated against a model that
        already contains it.
      </p>
    </div>
  );
}
