/** SAMPLE_PAYLOAD — INVENTED NUMBERS, FOR LOOKING AT THE LAYOUT.
 *
 *  Nothing in this file was measured. The managers and the clubs do not
 *  exist; the values are made up to span the range each metric plausibly
 *  occupies, so the table, the radar and the sliders can be seen working
 *  before the pipeline has written a real payload.
 *
 *  It is reachable ONLY from the empty state, behind a button that says what
 *  it is, and everything rendered from it carries a banner saying so. It is
 *  never a fallback for a payload that failed to load — a page quietly
 *  showing invented football would be the single worst failure mode this
 *  feature has.
 *
 *  Percentiles are computed from the raw values at load time rather than
 *  written out by hand, so the sample exercises the same code path as the
 *  real payload instead of a shortcut through it.
 */

import {
  type ManagerRow,
  type Metric,
  type Payload,
  K_MATCHES,
  percentileMap,
} from "./contract";

const METRICS: Metric[] = [
  // ------------------------------------------------------ directional
  {
    key: "set_piece_balance", label: "Set-piece balance", dimension: "set pieces",
    directional: true, invert: false, unit: "xG/match",
    help: "Set-piece xG for minus set-piece xG against, per match.",
  },
  {
    key: "sendings_off", label: "Sendings off", dimension: "discipline",
    directional: true, invert: true, unit: "/match",
    help: "Reds and second yellows per match. Rare enough that one season is close to noise.",
  },
  {
    key: "lead_protection", label: "Lead protection", dimension: "game management",
    directional: true, invert: true, unit: "xG/min",
    help: "Opponent xG per minute while his side is ahead. Compared only with other sides while ahead.",
  },
  {
    key: "deficit_response", label: "Deficit response", dimension: "game management",
    directional: true, invert: false, unit: "xG/min",
    help: "His side's own xG per minute while behind.",
  },
  {
    key: "half_time_correction", label: "Half-time correction", dimension: "game management",
    directional: true, invert: false, unit: "xG",
    help: "Second-half xG difference minus first-half xG difference.",
  },
  {
    key: "sub_impact", label: "Substitution impact", dimension: "bench",
    directional: true, invert: false, unit: "xG/min",
    help: "Own minus opponent xG per minute in the fifteen minutes after the first change, less the fifteen before, controlled for game state.",
  },
  {
    key: "self_inflicted", label: "Self-inflicted", dimension: "discipline",
    directional: true, invert: true, unit: "/match",
    help: "Errors leading to a shot or a goal, per match.",
  },
  {
    key: "card_rate", label: "Card rate", dimension: "discipline",
    directional: true, invert: true, unit: "/100 passes",
    help: "Cards per hundred opponent passes.",
  },
  // ------------------------------------------------------ fingerprint
  {
    key: "press_height", label: "Press height", dimension: "pressing",
    directional: false, invert: false, unit: "x",
    help: "Mean x of tackles, interceptions, challenges, recoveries and fouls, in the attacking direction.",
  },
  {
    key: "ppda", label: "PPDA", dimension: "pressing",
    directional: false, invert: false, unit: "passes",
    help: "Opponent passes per own defensive action in the opponent's 60% of the pitch.",
  },
  {
    key: "pass_length", label: "Pass length", dimension: "possession",
    directional: false, invert: false, unit: "m",
    help: "Median of the Length qualifier on pass events.",
  },
  {
    key: "directness", label: "Directness", dimension: "possession",
    directional: false, invert: false, unit: "%",
    help: "Share of passes ending more than fifteen units further up the pitch than they started.",
  },
  {
    key: "territory", label: "Territory", dimension: "possession",
    directional: false, invert: false, unit: "%",
    help: "Share of own touches taken in the final third.",
  },
  {
    key: "fast_break", label: "Fast break", dimension: "transition",
    directional: false, invert: false, unit: "%",
    help: "Share of own shots carrying Opta's FastBreak qualifier.",
  },
  {
    key: "minutes_concentration", label: "Minutes concentration", dimension: "selection",
    directional: false, invert: false, unit: "HHI",
    help: "Herfindahl index of minutes across the squad. High is a settled eleven, low is a rotation.",
  },
  {
    key: "xi_churn", label: "XI churn", dimension: "selection",
    directional: false, invert: false, unit: "/match",
    help: "Mean number of starting-XI changes between consecutive matches.",
  },
  {
    key: "first_sub_minute", label: "First substitution", dimension: "bench",
    directional: false, invert: false, unit: "min",
    help: "Median minute of the first change.",
  },
  {
    key: "sub_intent", label: "Substitution intent", dimension: "bench",
    directional: false, invert: false, unit: "%",
    help: "Share of changes where the man coming on plays a different position from the man going off.",
  },
  {
    key: "shape_repertoire", label: "Shape repertoire", dimension: "shape",
    directional: false, invert: false, unit: "shapes",
    help: "Count of distinct starting formations across the spell.",
  },
  {
    key: "shape_changes", label: "In-game shape changes", dimension: "shape",
    directional: false, invert: false, unit: "/match",
    help: "Formation changes per match.",
  },
  {
    key: "corner_profile", label: "Short corners", dimension: "set pieces",
    directional: false, invert: false, unit: "%",
    help: "Share of own corners played short.",
  },
  {
    key: "tactical_foul_x", label: "Foul height", dimension: "discipline",
    directional: false, invert: false, unit: "x",
    help: "Mean x of fouls committed carrying the Defensive qualifier.",
  },
];

/** manager, club, matches, short, start, end, seasons, then one raw value per
 *  metric in the order METRICS declares them. Invented, all of it. */
const SEED: Array<{
  manager: string;
  team: string;
  matches: number;
  short: boolean;
  start: string;
  end: string;
  seasons: string[];
  raw: number[];
}> = [
  {
    manager: "R. Vance", team: "Northgate", matches: 76, short: false,
    start: "2023-08-12", end: "2025-05-25", seasons: ["2324", "2425"],
    raw: [0.31, 0.03, 0.0121, 0.0288, 0.22, 0.0041, 0.21, 0.42,
          38.4, 9.1, 15.2, 21.8, 29.4, 11.2, 612, 2.1, 68, 41, 4, 0.31, 18.2, 51.1],
  },
  {
    manager: "M. Osei", team: "Ashfield United", matches: 58, short: false,
    start: "2023-08-12", end: "2025-02-02", seasons: ["2324", "2425"],
    raw: [0.12, 0.05, 0.0174, 0.0231, -0.08, -0.0012, 0.34, 0.61,
          33.1, 13.4, 19.8, 30.2, 24.1, 16.8, 744, 1.4, 74, 22, 2, 0.11, 8.4, 46.9],
  },
  {
    manager: "J. Kowalczyk", team: "Brookmere", matches: 38, short: false,
    start: "2024-06-30", end: "2025-05-25", seasons: ["2425"],
    raw: [0.04, 0.08, 0.0198, 0.0205, -0.19, 0.0008, 0.44, 0.73,
          31.6, 15.9, 21.4, 34.6, 21.8, 19.4, 801, 1.1, 79, 18, 2, 0.06, 5.2, 44.1],
  },
  {
    manager: "A. Bergqvist", team: "Ashfield United", matches: 21, short: false,
    start: "2025-02-09", end: "2025-05-25", seasons: ["2425"],
    raw: [0.24, 0.0, 0.0139, 0.0312, 0.34, 0.0062, 0.18, 0.38,
          37.2, 10.4, 16.1, 23.9, 27.8, 13.6, 548, 2.8, 62, 55, 5, 0.42, 22.6, 49.8],
  },
  {
    manager: "T. Iwuchukwu", team: "Calderfield", matches: 38, short: false,
    start: "2024-06-30", end: "2025-05-25", seasons: ["2425"],
    raw: [0.18, 0.02, 0.0156, 0.0264, 0.05, 0.0019, 0.28, 0.52,
          35.0, 12.0, 17.6, 26.4, 25.6, 14.9, 668, 1.8, 71, 34, 3, 0.19, 12.8, 48.2],
  },
  {
    manager: "P. Marchetti", team: "Calderfield", matches: 6, short: true,
    start: "2024-04-06", end: "2024-05-19", seasons: ["2324"],
    raw: [0.02, 0.17, 0.0211, 0.0349, 0.41, 0.0074, 0.5, 0.68,
          36.1, 11.3, 18.9, 28.1, 26.2, 17.7, 702, 3.4, 58, 61, 2, 0.5, 14.1, 52.7],
  },
  {
    manager: "D. Halvorsen", team: "Northgate", matches: 11, short: true,
    start: "2025-08-16", end: "2025-11-02", seasons: ["2526"],
    raw: [0.09, 0.0, 0.0182, 0.0219, -0.26, -0.0031, 0.36, 0.57,
          34.2, 12.8, 20.1, 31.5, 23.4, 15.2, 585, 2.4, 66, 29, 3, 0.27, 9.6, 47.4],
  },
];

export function samplePayload(): Payload {
  // PRE-ORIENTED, exactly as the real payload is. ranking.py writes each
  // column already pointing the right way (100 is good, whatever direction
  // the raw value runs), so the sample has to do the same or it is not a
  // sample of the thing it stands in for.
  //
  // 🐛 IT DID NOT, AND THAT IS WHY A REAL BUG SURVIVED EVERY RENDER TEST.
  // The sample used unflipped percentiles while the payload used oriented
  // ones, so contract.orient's extra flip cancelled out here and only here.
  // The layout looked right on sample data and the live table was upside
  // down on four metrics. A fixture that disagrees with production about a
  // convention does not just fail to catch bugs — it hides them.
  const pctCols = METRICS.map((m, mi) => {
    const col = percentileMap(SEED.map((s) => s.raw[mi]));
    if (!(m.directional && m.invert)) return col;
    return col.map((p) => (p === null ? null : 100 - p));
  });

  const managers: ManagerRow[] = SEED.map((s, ri) => {
    const raw: Record<string, number | null> = {};
    const pct: Record<string, number | null> = {};
    METRICS.forEach((m, mi) => {
      raw[m.key] = s.raw[mi] ?? null;
      pct[m.key] = pctCols[mi][ri];
    });
    const kept = s.matches / (s.matches + K_MATCHES);
    // The builder's own default weights, reproduced here only so the sample
    // carries a `score` field of the right shape.
    const dir = METRICS.filter((m) => m.directional);
    let acc = 0;
    let used = 0;
    for (const m of dir) {
      const p = pct[m.key];
      if (typeof p !== "number") continue;
      const w = 100 / dir.length;
      acc += (m.invert ? 100 - p : p) * w;
      used += w;
    }
    const scoreRaw = used ? acc / used : 50;
    return {
      manager: s.manager,
      team: s.team,
      matches: s.matches,
      short: s.short,
      start: s.start,
      end: s.end,
      seasons: s.seasons,
      raw,
      pct,
      score: 50 + (scoreRaw - 50) * kept,
      score_raw: scoreRaw,
      kept,
    };
  });

  return {
    league: "SAMPLE — not a league",
    generated: "0000-00-00",
    metrics: METRICS,
    managers,
  };
}
