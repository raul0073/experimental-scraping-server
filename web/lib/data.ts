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
  score: string;
  xg: [number, number];
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

export type RecordData = {
  generated: string;
  graded: number;
  hit_rate: number | null;
  said_avg: number | null;
  exact_score: number | null;
  by_league: Record<string, { n: number; hit_rate: number }>;
  calibration: { bucket: string; n: number; said: number; landed: number }[];
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
};

export type HistoryLeague = {
  name: string;
  crest?: string;
  rows: HistoryRow[];
  graded: number;
  hits: number;
  exact: number;
  teams: Record<string, string>;
};

export type HistoryData = {
  generated: string;
  leagues: Record<string, HistoryLeague>;
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

export const slugify = (league: string) =>
  league.toLowerCase().replace(/[ _]/g, "-");

export const leagueShort = (league: string) => league.split("-")[1] ?? league;

export const outcomeLabel: Record<Outcome, string> = {
  home: "1",
  draw: "X",
  away: "2",
};
