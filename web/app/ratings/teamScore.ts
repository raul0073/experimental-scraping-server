/** Scoring a team, in ONE place.
 *
 *  The board computed this inline and the team page read `club.score`, which
 *  does not exist in the file — the score is derived from the weights, not
 *  stored — so every club on its own page showed a flat 50. Two copies of a
 *  calculation is one copy too many; both now call this.
 */

export type TeamMetric = {
  key: string;
  label: string;
  phase: string;
  kind: string;
  unit: string;
  invert: boolean;
  desc: string;
};
export type TeamRel = { rho?: number; predicts?: number };
export type TeamRow = { team: string; matches: number } & Record<
  string,
  number | string | string[] | undefined
>;

export const BUDGET = 100;
export const RELIABLE = 0.6;
export const MARGINAL = 0.4;

/** Built from both gates, not from taste: every weight agrees with itself
 *  across half a season AND predicts points in the half it was not measured
 *  on. Nothing style-conditional — "do their long balls stick" only means
 *  anything if they play long, so it measures a choice, not a quality. */
export const PRESET: Record<string, number> = {
  // With the ball (50)
  box_entry_op_90: 14,
  shot_op_90: 12,
  bigchance_op_90: 10,
  prog_pass_90: 8,
  f3_entry_90: 6,
  // Against the ball (40)
  box_entry_con_op_90: 15,
  shot_con_op_90: 13,
  bigchance_con_op_90: 12,
  // Set pieces (10). Small on purpose: DEFENDING them repeats (0.53) while
  // creating from them barely does (0.22) — a side gets about eleven
  // set-piece big chances in half a season, too few to measure. Arsenal's
  // three-season lead on set-piece output is real; the per-season number is
  // not yet trustworthy enough to carry weight.
  sp_shot_con_90: 6,
  sp_shot_90: 4,
};

/** A metric fails if it cannot reproduce itself across half a season, or if
 *  it does not move with points. The second gate is the one that matters for
 *  a predictor input and the one that caught the trap: tackles,
 *  interceptions and recoveries all repeat beautifully and all predict FEWER
 *  points, because a side making a lot of them is a side without the ball. */
export function gateFails(r?: TeamRel): boolean {
  if (!r) return false;
  return (
    (r.rho !== undefined && r.rho < MARGINAL) ||
    (r.predicts !== undefined && Math.abs(r.predicts) < 0.25)
  );
}

export type TeamScore = {
  score: number;
  withBall: number;
  against: number;
};

/** Every metric percentiled across the rows given, higher always better.
 *
 *  Split out of the scorer because the pizza chart on a team page needs the
 *  per-metric percentile rather than the total, and a second implementation
 *  of "rank this column" would be a second place for the inversion rule to be
 *  got wrong. An inverted quality metric — shots conceded, say — is flipped
 *  here once, so 90 always means good.
 */
export function percentiles(
  rows: TeamRow[],
  metrics: TeamMetric[],
): Record<string, Map<TeamRow, number>> {
  const pct: Record<string, Map<TeamRow, number>> = {};
  if (!rows.length) return pct;
  for (const m of metrics) {
    const col = `${m.key}_adj` in rows[0] ? `${m.key}_adj` : m.key;
    const vals = rows
      .map((r) => ({ r, v: r[col] }))
      .filter((e) => typeof e.v === "number") as { r: TeamRow; v: number }[];
    vals.sort((a, b) => a.v - b.v);
    const map = new Map<TeamRow, number>();
    vals.forEach((e, i) => {
      const p = vals.length > 1 ? (i / (vals.length - 1)) * 100 : 50;
      map.set(e.r, m.kind === "quality" && m.invert ? 100 - p : p);
    });
    pct[m.key] = map;
  }
  return pct;
}

/** Percentile every quality metric across the rows given, then weight.
 *  Adjusted columns are used wherever they exist, so the score is about the
 *  side rather than about who it happened to play. */
export function scoreTeams(
  rows: TeamRow[],
  metrics: TeamMetric[],
  reliability: Record<string, TeamRel>,
  weights: Record<string, number> = PRESET,
  blockUnreliable = true,
): Map<TeamRow, TeamScore> {
  const out = new Map<TeamRow, TeamScore>();
  if (!rows.length) return out;

  const pct = percentiles(rows, metrics);

  const active = Object.entries(weights).filter(([k, w]) => {
    if (w <= 0) return false;
    return !(blockUnreliable && gateFails(reliability[k]));
  });
  const phaseOf = Object.fromEntries(metrics.map((m) => [m.key, m.phase]));

  const sum = (r: TeamRow, only?: string) => {
    let acc = 0;
    let used = 0;
    for (const [k, w] of active) {
      if (only && phaseOf[k] !== only) continue;
      acc += (pct[k]?.get(r) ?? 50) * w;
      used += w;
    }
    return used ? acc / used : 50;
  };

  for (const r of rows) {
    out.set(r, {
      score: sum(r),
      withBall: sum(r, "with"),
      against: sum(r, "against"),
    });
  }
  return out;
}
