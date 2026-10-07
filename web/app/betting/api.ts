/** THE CONTRACT for the betting section: every payload, and the only way in.
 *
 *  WHY A LIVE FETCH AND NOT A BUILT PAYLOAD. Everything under
 *  web/public/data is copied wholesale into the static export and published,
 *  so a betting payload written there would ship with the site — which is
 *  exactly what this section must never do. These three endpoints are read
 *  from the local API at render time instead, the same way the admin panel
 *  reads its own. In a production build the route is not emitted at all
 *  (see layout.tsx), so nothing here can ever run against a public visitor.
 *
 *  NO ODDS. NOWHERE. No price on this page comes from a bookmaker, and none
 *  is fetched, stored or compared against. Every `breakeven` below is the
 *  FAIR price the model's own probability implies — 1/p, the price at which
 *  the bet is a coin flip with no edge in either direction. What a book
 *  actually offers is the reader's business, done with his own eyes.
 *
 *  THE TYPES ARE TRANSCRIBED FROM LIVE PAYLOADS, not from a schema. Where a
 *  field is `| null` or optional below it is because the Python genuinely
 *  produces that, and the four that bite are worth knowing before you render:
 *
 *    weekly.window and weekly.strategy  are null when the season has no
 *        unplayed fixtures left, or fewer than three draw picks to advise on.
 *    fixture.probabilities_elo          is null until a league has an Elo
 *        arm; `probabilities` is always the official triplet.
 *    monkey.roi, entry.hit_rate, …      are null, not 0, before anything has
 *        been graded. A nothing is not a zero and must not print as one.
 *    leg.team and leg.side              exist on a favorite or banker leg
 *        and not on a draw leg, because a draw has no side.
 *
 *  ERRORS ARE THROWN, WITH SOMETHING A HUMAN CAN ACT ON. The API only exists
 *  while main.py is running, and a blank panel is the worst possible way to
 *  say so. Every getter rejects with an Error whose message is already fit to
 *  print; `message(e)` below unwraps anything else into one.
 */

export const API = "http://127.0.0.1:8080/api/v2/predictions";

/* ------------------------------------------------------------------ shared */

export type Side = "home" | "draw" | "away";
export type PickType = "draw" | "home" | "away";

/** The outcome triplet. Sums to 1. */
export type Probs = Record<Side, number>;

/** A reason the draw classifier moved, with its sign and its weight:
 *  `t` the phrase, `s` +1 toward the draw or -1 away from it, `w` how much. */
export type Driver = { t: string; s: number; w: number };

/** ["1-1", 0.1276] — a scoreline and its probability. */
export type Scoreline = [string, number];

/* ----------------------------------------------- GET /upcoming  (Weekly) */

/** One fixture, as the model sees it. The same row appears inside
 *  `all_predictions` and, with the pick fields added, inside every pick list. */
export type Fixture = {
  /** gold ≥55% on the favourite, silver ≥45%, flip below that. */
  tier: "gold" | "silver" | "flip";
  /** Full key, e.g. "ITA-Serie A". */
  league: string;
  season: string;
  week: number;
  /** Kickoff DATE, "YYYY-MM-DD" — not a timestamp. */
  kickoff: string;
  home: string;
  away: string;
  /** Expected goals, keyed by team name — not by home/away. */
  xg: Record<string, number>;
  /** The official triplet, and the only one to show as "the probability". */
  probabilities: Probs;
  /** The two arms behind it, kept so a call can be audited afterwards. */
  probabilities_ship: Probs;
  probabilities_elo: Probs | null;
  probabilities_poisson: Probs;
  /** The draw classifier on its own, null where it could not be computed. */
  p_draw_classifier: number | null;
  draw_drivers: Driver[];
  top_scorelines: Scoreline[];
  /** The likeliest score for each outcome, keyed home/draw/away. */
  modal_scores: Record<Side, Scoreline>;
  /** The model's stated call — a draw once P(draw) reaches the ceiling zone,
   *  otherwise the argmax. It is NOT always the largest probability. */
  call: Side;
  /** "low" means the xG rests on league-average priors: shown, never picked. */
  confidence: "normal" | "low";
  /** Zone-by-zone plain English, e.g. { attCentral: "PSG advantage (0.95)" }.
   *  Can be empty for a fixture with nothing to say. */
  why: Record<string, string>;
  in_window: boolean;
};

/** A fixture carrying the probability it was chosen on. The watchlist stops
 *  here: it is low-confidence, so it is never ranked and never committed. */
export type Watch = Fixture & { pick_prob: number };

/** A ranked, committable pick. */
export type Pick = Watch & { rank: number; pick_type: PickType };

/** P(exactly k of the four draw picks land), assuming independent legs. */
export type Trixy = { p_ge2: number; p_ge3: number; p_4of4: number };

/** A leg of a recommended form. `mark` is the Winner-form mark: 1 home,
 *  X draw, 2 away. `breakeven` is 1/prob — fair, not offered. */
export type Leg = {
  /** "draw", or "banker"/"fav" for a favourite leg. */
  role: string;
  mark: "1" | "X" | "2";
  /** "Torino v Udinese" */
  fixture: string;
  home: string;
  away: string;
  /** Full key, e.g. "ITA-Serie A". */
  league_full: string;
  /** Short name, e.g. "Serie A". */
  league: string;
  /** Only on a leg that backs a team — a draw leg has no side. */
  team?: string;
  side?: "home" | "away";
  prob: number;
  breakeven: number;
  kickoff: string;
  /** Added by grading, "2-2". */
  score?: string;
  hit?: boolean;
};

/** P(exactly `hits` legs land), and what that pays on this structure. */
export type Scenario = {
  hits: number;
  p: number;
  lines_won: number;
  total_lines: number;
  /** Gross return as a multiple of the whole stake. */
  ret_frac: number;
  profit: boolean;
};

/** A structure the advisor could have chosen instead, for a price comparison. */
export type Alternative = {
  title_he: string;
  title_en: string;
  lines: number;
  p_return: number;
  p_profit: number;
};

/** The recommended form: exact games, exact marks, enumerated outcomes. */
export type StrategySlip = {
  /** Hebrew is the primary name — it is the form the user actually plays. */
  title_he: string;
  title_en: string;
  /** k-of-n: every k-subset of the legs is one line. */
  k: number;
  lines: number;
  legs: Leg[];
  scenarios: Scenario[];
  /** P(any line returns) and P(the slip profits), at fair prices. */
  p_return: number;
  p_profit: number;
  /** Why this shape, in plain words. */
  how: string;
  mandate?: string;
  alternatives?: Alternative[];
};

/** The strongest certified favourite not already used as a draw leg. A PRICE
 *  tool, never a default — see `Strategy.text`. */
export type Banker = {
  fixture: string;
  league: string;
  home: string;
  away: string;
  team: string;
  side: "home" | "away";
  prob: number;
  tier: string;
  kickoff: string;
};

export type Option = {
  name: string;
  lines: number;
  p_return: number;
  /** P(the tail: 3 or more legs). */
  p_big: number;
  note: string;
};

export type Strategy = {
  /** How good the draw board is this round: top-4 average against a ~32% ceiling. */
  board: "strong" | "normal" | "thin";
  board_avg: number;
  banker: Banker | null;
  slip: StrategySlip;
  options: Option[];
  /** The recommendation in prose, including the mandate. Worth printing whole. */
  text: string;
};

export type Weekly = {
  season: string;
  /** Absent on the degenerate payload below. */
  generated_at?: string;
  /** Null when no fixtures are left to play this season. */
  window: { start: string; end: string } | null;
  /** Which round each league has in this window: { "ITA-Serie A": [6] }. */
  weeks: Record<string, number[]>;
  /** The four committed draws, and 5-8 as priced alternates. */
  draw_picks: Pick[];
  draw_candidates: Pick[];
  /** Low-confidence fixtures with ticket-grade draw numbers. Never committed,
   *  and absent entirely from the degenerate payload. */
  draw_watchlist?: Watch[];
  home_win_picks: Pick[];
  away_win_picks?: Pick[];
  trixy: Trixy | null;
  /** Every in-window fixture, keyed by full league name. */
  all_predictions: Record<string, Fixture[]>;
  /** Null with fewer than three draw picks to build a form from. */
  strategy: Strategy | null;
};

/* ------------------------------------------------- GET /ledger  (Ledger) */

/** One committed pick. Append-only: written BEFORE kickoff and never
 *  rewritten afterwards except to fill the result in. */
export type Entry = {
  committed_at: string;
  season: string;
  /** The window start date. Absent on the oldest entries. */
  window?: string | null;
  week: number;
  pick_type: PickType;
  rank: number;
  league: string;
  home: string;
  away: string;
  kickoff: string;
  pick_prob: number;
  probabilities: Probs;
  xg: Record<string, number>;
  status: "pending" | "graded";
  /* everything below exists only once graded */
  graded_at?: string;
  score?: string;
  outcome?: Side;
  hit?: boolean;
  /** Says so when the fixture was matched by a fallback — fbref flipped the
   *  venue, or renamed a club, after the pick was committed. */
  note?: string;
};

export type TypeRecord = {
  committed: number;
  graded: number;
  hits: number;
  /** Null before anything of this type has been graded. */
  hit_rate: number | null;
  /** What the model said on average, to read the hit rate against. */
  avg_pick_prob: number | null;
};

export type LedgerSummary = {
  total_picks: number;
  by_type: Record<PickType, TypeRecord>;
};

export type Ledger = { summary: LedgerSummary; entries: Entry[] };

/* ------------------------------------------------- GET /monkey  (Monkey) */

/** One window's committed slip and how it finished. */
export type Slip = {
  committed_at: string;
  season: string;
  /** The window START date. This is the row's identity. */
  window: string;
  title_he: string;
  title_en: string;
  k: number;
  lines: number;
  /** Per line, in ₪. */
  unit: number;
  /** lines x unit. */
  stake: number;
  p_profit: number;
  legs: Leg[];
  status: "pending" | "graded";
  /** "draws" is on-mandate; anything else was an experiment, real money kept
   *  in the pot but scored separately. Absent on pre-mandate rows. */
  mandate?: string;
  /** The bankroll after this row settled — computed, not stored. */
  pot_after: number;
  /* everything below exists only once graded */
  graded_at?: string;
  hits?: number;
  lines_won?: number;
  gross_return?: number;
  net?: number;
};

/** P&L for one mandate bucket. The pot balance stays whole; this splits only
 *  the score, so the draw system's record is not flattered or dragged by an
 *  experiment that shared the same bankroll. */
export type Block = {
  slips: number;
  graded: number;
  staked: number;
  returned: number;
  net: number;
  /** Null before anything in this bucket has been graded. */
  roi: number | null;
  profit_weeks: number;
  in_play: number;
};

/** THE MONKEY'S BOOK — the honest bankroll test, and the reason this section
 *  exists. Every window, the advisor's recommended slip is placed at unit per
 *  line and graded line-by-line once all its legs resolve, at the breakeven
 *  prices frozen on commit. From a 1000 start. Nothing is retrofitted: a slip
 *  that was recommended and lost stays in the book and in the pot. */
export type Monkey = {
  start_pot: number;
  /** Where the bankroll stands now. */
  pot: number;
  staked: number;
  returned: number;
  /** Staked on slips whose legs have not all resolved. */
  in_play: number;
  net: number;
  /** On graded stake only. Null before the first slip settles. */
  roi: number | null;
  weeks_played: number;
  weeks_graded: number;
  profit_weeks: number;
  peak: number;
  /** What this pot is mandated to bet, in words. */
  mandate: string;
  on_mandate: Block;
  off_mandate: Block;
  /** Newest window first. */
  weeks: Slip[];
};

/** One GOLD single, at its own frozen fair price. */
export type GoldBet = {
  league_full: string;
  league: string;
  home: string;
  away: string;
  fixture: string;
  team: string;
  side: "home" | "away";
  prob: number;
  breakeven: number;
  kickoff: string;
  score?: string;
  hit?: boolean;
};

export type GoldWeek = {
  committed_at: string;
  season: string;
  window: string;
  unit: number;
  stake: number;
  bets: GoldBet[];
  status: "pending" | "graded";
  pot_after: number;
  graded_at?: string;
  hits?: number;
  gross_return?: number;
  net?: number;
};

/** THE GOLD POT — the same question asked of singles rather than systems.
 *  Every certified GOLD favourite is backed at 1/p, so ROI is positive
 *  exactly when realized accuracy beats the probability the model stated.
 *  `realized` against `expected` is therefore the whole reading: it is a
 *  calibration test wearing a bankroll. */
export type Gold = {
  start_pot: number;
  pot: number;
  staked: number;
  returned: number;
  in_play: number;
  net: number;
  roi: number | null;
  bets_graded: number;
  hits: number;
  /** Hits over bets, and the average probability claimed. Null before any. */
  realized: number | null;
  expected: number | null;
  /** The live view: every leg whose result is known, including legs inside a
   *  window still waiting on a late kickoff. Bigger n than `bets_graded`. */
  settled: {
    n: number;
    hits: number;
    pending_legs: number;
    realized: number | null;
    expected: number | null;
  };
  /** The investor-plan bar: n >= 150 at >= 62%. */
  gate_a: { target_n: number; target_acc: number; on_track: boolean | null };
  /** Newest window first. */
  weeks: GoldWeek[];
};

/** What GET /monkey returns. Two pots, one call. */
export type MonkeyBook = { monkey: Monkey; gold: Gold };

/* ------------------------------------------------------------- the getters */

const DOWN = "API not reachable on :8080 — is main.py running?";

async function get<T>(path: string, what: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${API}${path}`, { cache: "no-store" });
  } catch {
    // A refused connection and a CORS rejection are indistinguishable here,
    // and both have the same cause nine times in ten: nothing is listening.
    throw new Error(DOWN);
  }
  if (!r.ok) {
    // FastAPI puts the readable half in `detail`; prefer it over the status.
    const body = (await r.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(
      body?.detail ? `${what}: ${body.detail}` : `${what}: HTTP ${r.status}`,
    );
  }
  try {
    return (await r.json()) as T;
  } catch {
    throw new Error(`${what}: the API answered with something that is not JSON`);
  }
}

/** This window's picks, probabilities and recommended form. Nothing is
 *  recorded by reading it. `start` overrides which window is built. */
export function getWeekly(start?: string): Promise<Weekly> {
  const q = start ? `?start=${encodeURIComponent(start)}` : "";
  return get<Weekly>(`/upcoming${q}`, "picks");
}

/** Every committed pick and the per-type record. `season` filters, e.g. "2627". */
export function getLedger(season?: string): Promise<Ledger> {
  const q = season ? `?season=${encodeURIComponent(season)}` : "";
  return get<Ledger>(`/ledger${q}`, "track record");
}

/** Both paper pots: the slip book and the GOLD singles beside it. */
export function getMonkey(): Promise<MonkeyBook> {
  return get<MonkeyBook>("/monkey", "monkey");
}

/** One printable sentence out of whatever was thrown. Use it in every catch,
 *  so all three tabs fail the same legible way instead of rendering nothing. */
export function message(e: unknown): string {
  if (e instanceof Error && e.message) return e.message;
  if (typeof e === "string" && e) return e;
  return DOWN;
}
