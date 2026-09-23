/** The visual grammar both ratings boards share.
 *
 *  WHY THIS EXISTS. The player board and the team board were each carrying
 *  their own copy of the score colour ramp and the score ring — the same
 *  algorithm, the same 38px SVG, the same midpoint — differing only in a
 *  constant. Two copies of a thing is two places to change it and one place
 *  to forget, and the team copy had already drifted: it inlined the palette
 *  as three anonymous arrays and lost the paragraph explaining why the scale
 *  is built the way it is. That paragraph is the part worth keeping.
 */

/** THE SCORE IS AN AVERAGE OF PERCENTILES, so 50 is the average player or
 *  side BY CONSTRUCTION. That makes this a DIVERGING scale with a real
 *  midpoint, not a sequential one, so it runs pole — neutral grey — pole and
 *  never puts a hue in the middle.
 *
 *  Red to green is the convention a reader expects, and it is also the worst
 *  possible pair for colour blindness. That is only survivable here because
 *  the number is ALWAYS printed beside the mark in ordinary ink: the colour
 *  is a second encoding of something already legible, never the value
 *  itself. Do not remove the number. */
const SCORE_BAD = [179, 38, 30];       // --color-bad
const SCORE_MID = [154, 163, 171];     // neutral grey, no hue at the midpoint
const SCORE_GOOD = [26, 127, 55];      // --color-good

/** How many points either side of average saturate the ramp.
 *
 *  Players spread wider than sides do — there are only twenty clubs in a
 *  league and far more players, so the tails are thinner for teams. Beyond
 *  the spread the ramp saturates rather than washing everything out. */
export const SPREAD_PLAYER = 25;
export const SPREAD_TEAM = 30;

export function scoreColor(score: number, spread = SPREAD_PLAYER): string {
  const t = Math.max(-1, Math.min(1, (score - 50) / spread));
  const to = t < 0 ? SCORE_BAD : SCORE_GOOD;
  const k = Math.abs(t);
  const mix = SCORE_MID.map((c, i) => Math.round(c + (to[i] - c) * k));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

/** A ring with the number inside it, in ordinary ink.
 *
 *  The arc is the encoding and the digits are the value, which is what keeps
 *  this readable for a colour-blind reader. Rounded cap on the arc, a
 *  recessive track behind it, and the text in the cell's OWN colour rather
 *  than the score's — a coloured mark beside a number carries identity; a
 *  coloured number just makes the number harder to read. */
export function ScoreRing({
  score, spread = SPREAD_PLAYER, decimals = 0,
}: {
  score: number;
  spread?: number;
  /** precision in the accessible label only; the face always reads whole */
  decimals?: number;
}) {
  const pct = Math.max(0, Math.min(100, score));
  const R = 15;
  const C = 2 * Math.PI * R;
  return (
    <svg
      width="38"
      height="38"
      viewBox="0 0 38 38"
      role="img"
      aria-label={`${score.toFixed(decimals)} out of 100`}
    >
      <circle cx="19" cy="19" r={R} fill="none" stroke="#eef0f2" strokeWidth="3.5" />
      <circle
        cx="19"
        cy="19"
        r={R}
        fill="none"
        stroke={scoreColor(score, spread)}
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeDasharray={`${(C * pct) / 100} ${C}`}
        transform="rotate(-90 19 19)"
      />
      <text
        x="19"
        y="19"
        textAnchor="middle"
        dominantBaseline="central"
        className="num"
        fontSize="10.5"
        fontWeight="600"
        fill="currentColor"
      >
        {score.toFixed(0)}
      </text>
    </svg>
  );
}

/** Percentile as a wash of colour behind a cell: blue where the subject
 *  leads its group, warm where it trails, and NOTHING in the middle — where
 *  the number is unremarkable, ink would only add noise. */
export function tint(pct?: number): string | undefined {
  if (pct === undefined || Number.isNaN(pct)) return undefined;
  if (pct >= 60) return `rgba(74, 123, 166, ${((pct - 60) / 40) * 0.22})`;
  if (pct <= 40) return `rgba(224, 120, 74, ${((40 - pct) / 40) * 0.18})`;
  return undefined;
}

/** THE RELIABILITY GATE, in one place because both boards enforce it.
 *
 *  A metric that cannot reproduce itself from one season to the next is
 *  measuring luck, not capability. These are the thresholds the colour dots
 *  and the "ignore metrics that don't hold up" switch both read. */
export const RELIABLE = 0.6;
export const MARGINAL = 0.4;
/** Below this many pairs a correlation is a rumour, not a result. */
export const THIN_N = 25;

/** Every config spends exactly this and no more, so a weighting is a set of
 *  TRADE-OFFS rather than a wish list. */
export const BUDGET = 100;
