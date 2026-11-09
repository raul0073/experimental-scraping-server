import fs from "node:fs";
import path from "node:path";

// The site is static: the Python pipeline writes these artifacts weekly and
// the client reads them at BUILD time. Nothing here runs per request, which
// is why the public site needs no server.
const DATA_DIR = path.join(process.cwd(), "..", "data", "web");

export type Outcome = "home" | "draw" | "away";

export type Fixture = {
  date: string;
  home: string;
  away: string;
  p: Record<Outcome, number>;
  /** What each outcome is worth. Above this price it is value, below it is not. */
  fair: Record<Outcome, number>;
  call: Outcome;
  /** the modal scoreline the model expected — NOT the result */
  score: string;
  xg: [number, number];
  /** what actually happened, once it has. Absent while unplayed, so the
   *  client can tell a 0-0 from a match that has not kicked off. */
  played?: string;
  outcome?: Outcome;
};

export type ZoneKey =
  | "ucl"
  | "uclq"
  | "uel"
  | "uecl"
  | "mid"
  | "playoff"
  | "rel";

export type Zone = { key: ZoneKey; label: string; from: number; to: number };

export type LeagueRound = {
  week: number;
  start: string;
  end: string;
  fixtures: Fixture[];
  /** Finishing zones for THIS league — European places and the relegation
   *  shape differ per competition (18-team leagues have a play-off). */
  zones: Zone[];
  projection: {
    team: string;
    played_pts: number;
    exp_pts: number;
    title: number;
    med_pos: number;
    zone: Partial<Record<ZoneKey, number>>;
  }[];
};

export type Crests = {
  teams: Record<string, Record<string, string>>;
  leagues: Record<string, string>;
};

export type RoundData = {
  generated: string;
  season: string;
  as_of: string;
  crests: Crests;
  zones_note?: string;
  leagues: Record<string, LeagueRound>;
};

export const ZONE_STYLE: Record<
  ZoneKey,
  { fill: string; text: string; chip: string; short: string }
> = {
  ucl: {
    fill: "#2f6fae",
    text: "#1c5b8a",
    chip: "bg-[#e3eef7] border-[#b9d5e8]",
    short: "UCL",
  },
  uclq: {
    fill: "#6fa3ca",
    text: "#1c5b8a",
    chip: "bg-[#eef5fb] border-[#cfe1ef]",
    short: "UCL Q",
  },
  uel: {
    fill: "#e0784a",
    text: "#a34a22",
    chip: "bg-[#fae5d9] border-[#eec4ab]",
    short: "UEL",
  },
  uecl: {
    fill: "#4a9e6b",
    text: "#1a7f37",
    chip: "bg-[#e8f3ec] border-[#c2e0cd]",
    short: "UECL",
  },
  mid: {
    fill: "#e4e7ea",
    text: "#55606b",
    chip: "bg-[#f3f4f6] border-line",
    short: "mid-table",
  },
  playoff: {
    fill: "#d9a300",
    text: "#6b5606",
    chip: "bg-[#faf0cd] border-[#e4d49a]",
    short: "play-off",
  },
  rel: {
    fill: "#c0392b",
    text: "#b3261e",
    chip: "bg-[#fbe9e7] border-[#f0c4bf]",
    short: "relegation",
  },
};

/** Order segments the way a table reads: Europe at the top, danger at the
 *  bottom, so the bar's shape alone tells you what a club is fighting for. */
export const ZONE_ORDER: ZoneKey[] = [
  "ucl",
  "uclq",
  "uel",
  "uecl",
  "mid",
  "playoff",
  "rel",
];

export type Scores = { logloss: number; brier: number };

export type CalibrationBucket = {
  bucket: string;
  n: number;
  said: number;
  landed: number;
};

/** The track record. HEADLINE FIGURES ARE LIVE ROWS ONLY — calls committed
 *  before kickoff. `reconstructed` holds the rounds that were rebuilt
 *  walk-forward after the fact (the first three or four of each league, on
 *  2026-09-10), apart, so the reader can see both and never has to take the
 *  word "before" on trust. `all` is the two together. */
export type RecordData = {
  generated: string;
  graded: number;
  hit_rate: number | null;
  said_avg: number | null;
  exact_score: number | null;
  by_league: Record<
    string,
    {
      n: number;
      hit_rate: number | null;
      logloss: number | null;
      n_reconstructed: number;
      reconstructed_rounds: [number, number] | null;
    }
  >;
  calibration: CalibrationBucket[];
  /** per outcome, mean stated probability v share that happened, all rows */
  levels: {
    outcome: Outcome;
    n: number;
    said: number;
    landed: number;
    gap: number;
    se: number;
  }[];
  scoring: {
    model: Scores;
    base_rate: Scores;
    uniform: Scores;
    base_rates: Record<Outcome, number>;
  } | null;
  live_since: string | null;
  /** mean expected goals a match the model priced v mean goals scored */
  goals: { expected: number; actual: number } | null;
  reconstructed: {
    n: number;
    hit_rate: number | null;
    said_avg: number | null;
    exact_score: number | null;
    scores: Scores | null;
    recorded_on: string | null;
    kickoffs: [string, string] | null;
    calibration: CalibrationBucket[];
  };
  all: {
    n: number;
    hit_rate: number | null;
    said_avg: number | null;
    exact_score: number | null;
    scores: Scores | null;
  };
};

export type HistoryRow = {
  kickoff: string;
  home: string;
  away: string;
  p: Record<Outcome, number>;
  call: Outcome;
  our_score: string;
  our_xg: [number, number] | null;
  status: "graded" | "pending";
  score: string | null;
  real_xg: [number, number] | null;
  outcome_hit: boolean | null;
  score_hit: boolean | null;
  /** rebuilt walk-forward after the result was known; kept out of headlines */
  retro: boolean;
  /** the date the row was written to the ledger */
  recorded: string;
};

export type HistoryLeague = {
  name: string;
  crest?: string;
  rows: HistoryRow[];
  /** live (pre-committed) graded rows only */
  graded: number;
  hits: number;
  exact: number;
  reconstructed: number;
  teams: Record<string, string>;
};

export type HistoryData = {
  generated: string;
  leagues: Record<string, HistoryLeague>;
};

/** One scorer's three figures; log loss and Brier are "lower is better". */
export type MarketScore = {
  log_loss: number;
  brier: number;
  accuracy: number;
};

/** Model vs market vs the two baselines on one set of joined rows. `gap`
 *  is model minus market log loss in nats: negative means the model was
 *  closer to what happened. `n: 0` blocks carry nothing else. */
export type MarketSplit = {
  n: number;
  model?: MarketScore;
  market?: MarketScore;
  uniform?: MarketScore;
  base_rate?: MarketScore;
  gap?: number;
};

export type MarketDisagreementRow = {
  league: string;
  kickoff: string;
  home: string;
  away: string;
  retro: boolean;
  model: Record<Outcome, number>;
  market: Record<Outcome, number>;
  /** the model's fair price, 1/p — what the round page published */
  fair: Record<Outcome, number>;
  /** the bookmaker's closing odds as published, margin still in them */
  odds: Record<Outcome, number>;
  /** which column of the sheet the odds came from */
  odds_column: string;
  max_diff: number;
  result: Outcome;
  better: "model" | "market";
};

export type MarketSeason = {
  season: string;
  n: number;
  blend_log_loss: number;
  layer_log_loss: number;
  market_log_loss: number;
  blend_gap: number;
  layer_gap: number;
};

/** data/web/market.json — the model measured against bookmaker closing
 *  odds. Odds appear only for fixtures already played; the builder never
 *  emits a price for one that has not. Schema documented in
 *  scripts/build_market.py. */
export type MarketData = {
  generated: string;
  as_of: string;
  source: string;
  margin_method: "normalise" | "shin";
  margin_methods: {
    n: number;
    normalise_log_loss?: number;
    shin_log_loss?: number;
    reason: string;
  };
  odds_column_used: Record<
    "live" | "historical" | "all",
    Record<"pinnacle_closing" | "pinnacle" | "average", number>
  >;
  live: {
    join: {
      graded: number;
      joined: number;
      rate: number | null;
      unjoined: { league: string; kickoff: string; home: string; away: string; retro: boolean }[];
    };
    splits: Record<"live" | "reconstructed" | "all", MarketSplit>;
    by_league: Record<string, { n: number; model: MarketScore; market: MarketScore; gap: number }>;
    disagreement: {
      threshold: number;
      buckets: {
        bucket: string;
        n: number;
        model_log_loss: number | null;
        market_log_loss: number | null;
        better: "model" | "market" | "tie" | null;
      }[];
      rows: MarketDisagreementRow[];
    };
    histogram: {
      bins: { from: number; to: number; label: string }[];
    } & Record<Outcome, number[]>;
  };
  historical: {
    leagues: string[];
    join: {
      rows: number;
      joined: number;
      rate: number | null;
      unjoined: { season: string; league: string; date: string; home: string; away: string }[];
    };
    seasons: MarketSeason[];
    pooled: Omit<MarketSeason, "season"> | null;
    note: string | null;
  };
  information_test: {
    arm: string;
    n: number;
    verdict: string;
    seasons?: string[];
    weight_model?: number;
    weight_market?: number;
    ci95?: [number, number];
    resamples?: number;
    per_season?: { season: string; n: number; market_only: number; stacked: number }[];
    pooled?: { market_only: number; stacked: number };
    adds_information?: boolean;
  };
};

function read<T>(name: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), "utf-8")) as T;
  } catch {
    // A missing artifact must degrade the page, never break the build.
    return null;
  }
}

export const getRound = () => read<RoundData>("round.json");
export const getRecord = () => read<RecordData>("record.json");
export const getHistory = () => read<HistoryData>("history.json");
export const getMarket = () => read<MarketData>("market.json");

// Re-exported from lib/league.ts, which has no node:fs, so client components
// can import them without pulling this module into the browser bundle.
export { leagueShort, slugify } from "./league";

export const outcomeLabel: Record<Outcome, string> = {
  home: "1",
  draw: "X",
  away: "2",
};
