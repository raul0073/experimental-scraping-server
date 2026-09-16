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

export type LeagueRound = {
  week: number;
  start: string;
  end: string;
  fixtures: Fixture[];
  projection: {
    team: string;
    played_pts: number;
    exp_pts: number;
    title: number;
    top4: number;
    rel: number;
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
  leagues: Record<string, LeagueRound>;
};

export type RecordData = {
  generated: string;
  graded: number;
  hit_rate: number | null;
  said_avg: number | null;
  exact_score: number | null;
  by_league: Record<string, { n: number; hit_rate: number }>;
  calibration: { bucket: string; n: number; said: number; landed: number }[];
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

export const leagueShort = (league: string) => league.split("-")[1] ?? league;

export const outcomeLabel: Record<Outcome, string> = {
  home: "1",
  draw: "X",
  away: "2",
};
