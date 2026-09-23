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

/* ------------------------------------------------------------------ filters
 *
 *  Both boards carry a row of selects above the table, and both had grown the
 *  same shape by hand: bare labels in 12.5px ink-2 beside px-2 py-1 selects,
 *  strung together with gap-2. It read as a sentence rather than as controls,
 *  the hit targets were below what a pointer wants, and there was no way to
 *  see at a glance which filters were ON — which matters, because every
 *  active filter is a reason the table is shorter than the reader expects.
 *
 *  One definition here, imported by both, so they cannot drift again — which
 *  is the same reason the score ramp above lives in this file. */

/** One class for every select on a ratings board.
 *
 *  WIDTH-CAPPED BELOW `sm`, AND THAT IS NOT COSMETIC. A native <select> sizes
 *  itself to its WIDEST OPTION, so a club picker in a league containing
 *  "Borussia Mönchengladbach" is over 200px wide before its padding. Two of
 *  those in a filter bar and it is the PAGE that scrolls sideways on a 375px
 *  screen, not the control. Pinned to its field the browser truncates the
 *  closed control and still opens the list at full width, which is where the
 *  long name actually has to be readable.
 *
 *  `h-11` below `sm` is the 44px touch target; the laptop keeps its 36px. */
export const SELECT =
  "h-11 w-full min-w-0 max-w-full cursor-pointer rounded-lg border border-line "
  + "bg-card px-2.5 text-[13px] "
  + "text-ink transition-colors hover:border-ink-3 focus:border-home "
  + "focus:outline-none focus:ring-2 focus:ring-[#e9f1f8] sm:h-9 sm:w-auto";

export const FIELD_LABEL =
  "text-[10.5px] font-semibold uppercase tracking-[0.07em] text-ink-3";

/** The bar the fields sit in. */
export const FILTER_BAR =
  "flex flex-wrap items-end gap-x-3 gap-y-3 rounded-xl border border-line "
  + "bg-card px-3 py-3 sm:gap-x-5 sm:px-4";

/** A checkbox styled as a control rather than as stray text. */
export const CHECK_BOX =
  "flex h-11 max-w-full cursor-pointer items-center gap-2 rounded-lg border "
  + "border-line px-3 text-[12.5px] text-ink-2 transition-colors "
  + "hover:border-ink-3 sm:h-9";

/** A range input with a thumb a finger can actually find.
 *
 *  The default control is about 16px tall, which is a third of the 44px a
 *  touch target is supposed to be — on a phone you aim at a slider you cannot
 *  hit and end up scrolling the page instead. The element's whole box is the
 *  hit area, so making it 44px tall below `sm` is the entire fix; the track
 *  and thumb stay centred in it and the laptop keeps the compact control. */
export const SLIDER =
  "h-11 w-full cursor-pointer touch-manipulation accent-[#4a7ba6] sm:h-5";

export function Field({
  label,
  title,
  children,
}: {
  label: string;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    // TWO TO A ROW ON A PHONE, content-sized on a laptop. `basis-[8.5rem]`
    // with `flex-1` means two fields share a 375px row and a third wraps
    // rather than squeezing; `min-w-0` is what lets the select inside be
    // narrower than its own longest option.
    <label
      className="flex min-w-0 flex-1 basis-[8.5rem] flex-col gap-1 sm:flex-none sm:basis-auto"
      title={title}
    >
      <span className={FIELD_LABEL}>{label}</span>
      {children}
    </label>
  );
}

/** THE SORT CONTROL THAT COMES WITH A CARD LIST.
 *
 *  A table sorts by clicking a column header. Cards have no headers, so the
 *  sort has to be said out loud or the phone reader simply loses it — which
 *  is the one thing that would make the small layout a lesser page rather
 *  than a different shape of the same one. `RankTable` wrote the original
 *  inline; this is the same control, lifted so the player and team boards
 *  cannot drift from it. */
export function SortControl({
  options,
  value,
  dir,
  onChange,
}: {
  /** [key, label] in the order the table's columns run */
  options: [string, string][];
  value: string;
  dir: 1 | -1;
  /** the board decides which way a fresh key opens — a name opens A-Z, a
   *  number opens best-first */
  onChange: (key: string, dir: 1 | -1) => void;
}) {
  return (
    <label className="mt-4 flex items-center gap-2 text-[12.5px] text-ink-2 sm:hidden">
      sort by
      <select
        value={value}
        onChange={(e) => onChange(e.target.value, dir)}
        className="h-11 min-w-0 flex-1 rounded-md border border-line bg-card px-2"
      >
        {options.map(([k, label]) => (
          <option key={k} value={k}>
            {label}
          </option>
        ))}
      </select>
      <button
        onClick={() => onChange(value, (dir * -1) as 1 | -1)}
        aria-label="reverse the order"
        className="h-11 w-11 shrink-0 rounded-md border border-line bg-card text-[12px]"
      >
        {dir === -1 ? "▾" : "▴"}
      </button>
    </label>
  );
}

/** A filter that is ON, shown so it can be seen and undone in one click.
 *  A filter you cannot see is a filter you forget you set. */
export function ActiveChip({
  label,
  onClear,
}: {
  label: string;
  onClear: () => void;
}) {
  return (
    <button
      onClick={onClear}
      title="Remove this filter"
      className="group inline-flex items-center gap-1.5 rounded-full border border-home
                 bg-[#e9f1f8] py-1 pl-3 pr-2 text-[12px] font-medium text-[#1c5b8a]
                 transition-colors hover:bg-[#dbe9f4]"
    >
      {label}
      <span className="text-[13px] leading-none text-[#5b8cb5] group-hover:text-[#1c5b8a]">
        ×
      </span>
    </button>
  );
}

/** The row of active chips, with a clear-all once there is more than one. */
export function ActiveFilters({
  active,
}: {
  active: { label: string; clear: () => void }[];
}) {
  if (!active.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <span className={FIELD_LABEL}>filtering</span>
      {/* KEYED ON THE INDEX AS WELL AS THE LABEL. `key={a.label}` alone looks
          safe and is not: a caller that hands over an undefined label — a
          season key with no entry in its label map, say — produces
          key={undefined}, which React treats as NO key and warns about. The
          index is always defined and the list is small and re-derived every
          render, so there is nothing for a stable identity to preserve. */}
      {active.map((a, i) => (
        <ActiveChip
          key={`${i}:${a.label ?? ""}`}
          label={a.label}
          onClear={a.clear}
        />
      ))}
      {active.length > 1 && (
        <button
          onClick={() => active.forEach((a) => a.clear())}
          className="text-[12px] text-ink-3 underline underline-offset-2 hover:text-ink"
        >
          clear all
        </button>
      )}
    </div>
  );
}
