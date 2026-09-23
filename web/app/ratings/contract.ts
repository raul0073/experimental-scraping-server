/** THE MANAGER PAYLOAD, AND THE ARITHMETIC THE BROWSER IS ALLOWED TO DO.
 *
 *  Python computes the expensive, league-wide half — a percentile per metric
 *  per manager spell, WITHIN the league, after the opponent adjustment has
 *  been fitted across the whole league-season. The browser only ever takes a
 *  weighted mean of numbers that are already comparable, then shrinks it.
 *  It never re-derives a percentile from a raw value and it never touches an
 *  event. That is what makes moving a weight free: a few dozen rows and a
 *  sort, single-digit milliseconds, no network.
 *
 *  ⚠️ ONE CONTRACT DETAIL THE BUILDER AND THIS FILE MUST AGREE ON.
 *  `pct` ARRIVES ALREADY ORIENTED: 100 is the good end, whichever way the
 *  raw value runs. ranking.py sorts each column with `reverse=invert` before
 *  writing it, so the flip has happened by the time the JSON is on disk.
 *  `orient` therefore clamps and returns it untouched.
 *
 *  This paragraph used to say the opposite, and the page flipped a second
 *  time on the strength of it — every inverted metric, and about half the
 *  score's weight, was upside down. `invert` stays in the payload because the
 *  header's "lower is better" marker and the tooltips still need to know
 *  which way the RAW number runs; it is not an instruction to this file.
 */

export type Metric = {
  key: string;
  label: string;
  /** which family the metric belongs to; groups the sliders and nothing more */
  dimension: string;
  /** directional metrics feed the score; fingerprint metrics never can */
  directional: boolean;
  /** lower is better — applied by `orient`, never by the payload */
  invert: boolean;
  unit: string;
  help: string;
  /** OPTIONAL and only ever a DEFAULT. If the builder ships the config's own
   *  weight the page opens on it; absent, DEFAULT_WEIGHTS below is used.
   *  Either way the reader's weights win the moment they touch a slider. */
  weight?: number;
};

export type ManagerRow = {
  manager: string;
  team: string;
  matches: number;
  /** a spell too short to measure cleanly. Not excluded — shrunk, and said. */
  short: boolean;
  start: string;
  end: string;
  seasons: string[];
  /** Set only in the pooled All-leagues list, where a club name on its own
   *  does not say which competition the row's percentiles were computed in. */
  league?: string;
  raw: Record<string, number | null>;
  pct: Record<string, number | null>;
  /** what the builder's own weights produced; shown as a reference, never
   *  used, because the score on screen is the READER's weights */
  score: number | null;
  score_raw: number;
  /** the shrinkage factor, 0-1, and the whole reason a caretaker sits near 50 */
  kept: number;
};

export type Payload = {
  league: string;
  generated: string;
  metrics: Metric[];
  managers: ManagerRow[];
};

export type LeagueRef = { key: string; label: string };

/** Written by the pipeline; merged into, never overwritten. */
export const DATA = "/data/managers";

/** Evidence shrinkage on MATCHES, the same construction as
 *  services/mental/dependability.py with the unit changed from 90s to
 *  matches: a 38-match spell keeps 83% of its distance from average, a
 *  four-match caretaker 33%. Only a fallback here — the payload ships its
 *  own `kept`, which may have been computed on a metric's own denominator. */
export const K_MATCHES = 8;

/** STARTING POINTS, AND ONLY THAT. Nothing here is a finding; it is where the
 *  sliders sit before a reader has an opinion, and the page exists so they
 *  can have one. Every weight is theirs to move.
 *
 *  The shape of it: game management takes the largest share because it is the
 *  part of a match a manager's hand is actually on — what the opponent does
 *  once his side is in front, what his side does once it is behind, and what
 *  changed over the interval. Discipline is next, and set pieces and
 *  substitutions smallest, because both are thin evidence per match. */
export const DEFAULT_WEIGHTS: Record<string, number> = {
  // game management (42)
  lead_protection: 16,
  deficit_response: 14,
  half_time_correction: 12,
  // discipline (32)
  card_rate: 14,
  self_inflicted: 10,
  sendings_off: 8,
  // set pieces (14) and the bench (12)
  set_piece_balance: 14,
  sub_impact: 12,
};

/** Column headers have about eight characters before a table starts to
 *  shove. Anything not named here falls back to the payload's own label. */
export const SHORT: Record<string, string> = {
  // directional
  set_piece_balance: "Set pc",
  sendings_off: "Reds",
  lead_protection: "Lead",
  deficit_response: "Chasing",
  half_time_correction: "Interval",
  sub_impact: "Bench",
  self_inflicted: "Errors",
  card_rate: "Cards",
  // fingerprint
  press_height: "Press ht",
  ppda: "PPDA",
  regain_time: "Regain",
  regain_5s: "Regain 5s",
  squad_used: "Players",
  pass_length: "Pass len",
  directness: "Direct",
  territory: "Territory",
  fast_break: "Fast break",
  minutes_concentration: "Mins conc",
  xi_churn: "XI churn",
  first_sub_minute: "1st sub",
  sub_intent: "Sub intent",
  shape_repertoire: "Shapes",
  shape_changes: "Shape chg",
  corner_profile: "Short crn",
  tactical_foul_x: "Foul ht",
};

export function shortLabel(m: Metric): string {
  return SHORT[m.key] ?? m.label;
}

export function dimensionLabel(d: string): string {
  const s = d.replace(/[-_]+/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : "Other";
}

/** Raw values run from thousandths of an xG per minute to a foul height in
 *  the fifties, so precision follows magnitude rather than a per-metric
 *  table nobody would keep current. */
export function fmtRaw(v: number | null | undefined, unit = ""): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  if (unit === "%") return v.toFixed(1);
  const a = Math.abs(v);
  const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  return v.toFixed(d);
}

/** THE ONE PLACE DIRECTION IS APPLIED. 100 always means good afterwards —
 *  and it is only ever called on a directional metric, because a fingerprint
 *  has no good end to point at. */
export function orient(
  pct: number | null | undefined,
  m: Metric,
): number | undefined {
  if (typeof pct !== "number" || !Number.isFinite(pct)) return undefined;
  // 🐛 THIS USED TO FLIP AGAIN, AND THE WHOLE TABLE WAS BACKWARDS.
  //
  // The payload's percentiles are ALREADY oriented — ranking.py sorts each
  // column with `reverse=invert`, so 100 is always the good end by the time
  // it is written. Verified on the shipped England payload: the lowest
  // card_rate carries pct 100.0 and the highest carries 0.0. Flipping here
  // as well turned "fewest cards" into "most cards" on the four inverted
  // metrics, which between them hold about half the score's weight — and
  // nothing on the page contradicted it, because the page never shows the
  // payload's own `score`. Maresca and Arteta were riding the league's WORST
  // discipline to the top three.
  //
  // It survived every render test because sample.ts built its percentiles
  // unflipped, so the sample used the opposite convention from the real
  // payload and the double negative came out right there.
  //
  // `invert` stays in the payload: the "↓ lower is better" marker on the
  // header and the tooltips still need to know which way the raw value runs.
  return Math.max(0, Math.min(100, pct));
}

export function keptOf(row: ManagerRow): number {
  if (typeof row.kept === "number" && Number.isFinite(row.kept))
    return Math.max(0, Math.min(1, row.kept));
  const m = row.matches ?? 0;
  return m / (m + K_MATCHES);
}

export type Scored = {
  /** the weighted mean of oriented percentiles, before any shrinkage */
  raw: number;
  /** the same after shrinking toward 50 on evidence — what the ring shows */
  final: number;
  /** how much of the weight the reader spent this row actually has data for.
   *  Below 1 the score is a renormalised average of what was there, and the
   *  reader is told so rather than handed a silent 50 in the gap. */
  covered: number;
};

/** Missing metrics are DROPPED and the rest renormalised, not imputed at 50.
 *  An imputed 50 is an invented measurement wearing the pool's average; a
 *  renormalised mean is honest about having measured less. `covered` carries
 *  the difference to the surface. */
export function scoreRow(
  row: ManagerRow,
  directional: Metric[],
  weights: Record<string, number>,
): Scored | null {
  let acc = 0;
  let used = 0;
  let asked = 0;
  for (const m of directional) {
    const w = weights[m.key] ?? 0;
    if (w <= 0) continue;
    asked += w;
    const p = orient(row.pct?.[m.key], m);
    if (p === undefined) continue;
    acc += p * w;
    used += w;
  }
  if (!used) return null;
  const raw = acc / used;
  return {
    raw,
    final: 50 + (raw - 50) * keptOf(row),
    covered: asked ? used / asked : 0,
  };
}

/** The payload's own weights if it ships them, this file's defaults if not,
 *  and an equal split if the metric bank has moved on from both — so a new
 *  metric key can never leave the page scoring nothing at all. */
export function defaultsFor(directional: Metric[]): Record<string, number> {
  const out: Record<string, number> = {};
  let total = 0;
  for (const m of directional) {
    const w = typeof m.weight === "number" ? m.weight : DEFAULT_WEIGHTS[m.key];
    const v = typeof w === "number" && Number.isFinite(w) ? Math.max(0, w) : 0;
    out[m.key] = v;
    total += v;
  }
  if (total > 0 || !directional.length) return out;
  const each = Math.floor(100 / directional.length);
  directional.forEach((m, i) => {
    out[m.key] = i === directional.length - 1 ? 100 - each * i : each;
  });
  return out;
}

/** THE TWO COMPARISON COLOURS ARE IDENTITY, NOT VALUE.
 *
 *  They are the site's home and away hues, which already mean "this side" and
 *  "that side" and mean nothing about better. The good/bad pair — the red and
 *  the green in --color-bad and --color-good — is deliberately NOT used
 *  anywhere in the fingerprint: style has no good end, and colouring a press
 *  height green would be the page quietly asserting that pressing is correct.
 */
export const PICK_COLOR = { a: "#4a7ba6", b: "#e0784a" } as const;
export type Slot = "a" | "b";

/** A spell is a manager at a club from a date — the same man at the same
 *  club twice is two rows, and they must not collapse into one another. */
export function rowId(r: ManagerRow): string {
  return `${r.manager}|${r.team}|${r.start}`;
}

/** Must match the slugs the team pages are generated under. */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Percentile within a list, used only by the sample payload — the real one
 *  arrives with its percentiles already computed, within its own league. */
export function percentileMap(
  values: Array<number | null | undefined>,
): Array<number | null> {
  const known = values
    .map((v, i) => ({ i, v }))
    .filter((e) => typeof e.v === "number") as { i: number; v: number }[];
  known.sort((a, b) => a.v - b.v);
  const out: Array<number | null> = values.map(() => null);
  known.forEach((e, r) => {
    out[e.i] = known.length > 1 ? (r / (known.length - 1)) * 100 : 50;
  });
  return out;
}
