"use client";

/** The data and the weights that BOTH boards read.
 *
 *  Team mental is the squad's player ratings aggregated, so it has to react
 *  to the weights the reader sets on the players board rather than to the
 *  presets. That needs one owner for the config and the player rows, sitting
 *  above both tabs instead of inside the players one.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Metric = {
  key: string;
  label: string;
  unit: string;
  group: string;
  invert: boolean;
  desc: string;
};
export type Player = {
  n: string;
  t: string;
  /** the position bucket this row is about */
  p: string;
  /** which side of the pitch he played it on: R, L, C, or RL for both */
  s: string;
  /** the club he plays for NOW, when it differs from the one this row is
   *  about — a 23/24 row describes the club he was at then */
  tn?: string;
  /** which league this row is from — only set in the pooled view, where a
   *  name on its own does not say. */
  lg?: string;
  /** set when he has NOT appeared in the season in progress. The pooled
   *  view spans four seasons, so without this a "best in the league" table
   *  is topped by players who have left it. */
  gone?: boolean;
  /** share of his minutes spent in this role, 0-100 */
  sh: number;
  /** minutes IN THIS ROLE, not in the season */
  m: number;
  /** those minutes as a share of his club's available ones, 0-100 */
  rs: number;
  /** raw per-90 values and their percentile within the bucket */
  v: Record<string, number>;
  q: Record<string, number>;
  /** the same, adjusted for how much of the ball the player's team had */
  va: Record<string, number>;
  qa: Record<string, number>;
};
export type Rel = { rho: number; n: number };
export type Data = {
  league: string;
  seasons: string[];
  min_share: number;
  period_minutes: Record<string, number>;
  views: { key: string; label: string }[];
  buckets: { key: string; label: string; desc: string }[];
  sides: Record<string, string>;
  metric_groups: { key: string; label: string }[];
  metrics: Metric[];
  reliability: Record<string, Record<string, Rel>>;
  self_reliability: Record<string, Record<string, Rel>>;
  metric_keys: string[];
  leagues: { key: string; label: string }[];
};

/** A view arrives down the columns — one array per field, plus one array of
 *  64 values per player for each block, lined up against `metric_keys`. */
export type ColumnarView = {
  n: string[];
  t: string[];
  tn: (string | null)[];
  gone?: (number | null)[];
  p: string[];
  s: string[];
  m: number[];
  sh: number[];
  rs: number[];
  v: (number | null)[][];
  q: (number | null)[][];
  va: (number | null)[][];
  qa: (number | null)[][];
};

export function inflate(c: ColumnarView, keys: string[]): Player[] {
  const blocks = ["v", "q", "va", "qa"] as const;
  return c.n.map((name, i) => {
    const row: Player = {
      n: name, t: c.t[i], p: c.p[i], s: c.s[i], m: c.m[i], sh: c.sh[i],
      rs: c.rs[i] ?? 0,
      v: {}, q: {}, va: {}, qa: {},
    };
    if (c.tn[i]) row.tn = c.tn[i] as string;
    if (c.gone?.[i]) row.gone = true;
    for (const b of blocks) {
      const vals = c[b][i];
      for (let k = 0; k < keys.length; k++) {
        const val = vals[k];
        if (val !== null && val !== undefined) row[b][keys[k]] = val;
      }
    }
    return row;
  });
}

/** Starting points only — every weight is yours to change. Nothing here is
 *  a claim about what "mental" means; that is the question the page exists
 *  to let you answer.
 *
 *  What these do NOT contain is any metric the gate calls noise for that
 *  bucket. Tackle SUCCESS rate was in three of these presets and repeats at
 *  -0.12 for a centre-back, 0.11 for a full-back, 0.07 for a midfielder —
 *  so the volume of tackles stands in its place, which repeats at 0.42-0.74.
 *  Attacking-header win rate survives in exactly one preset, the striker's,
 *  because that is the only bucket where it can be measured (0.83). */
export const PRESETS: Record<string, Record<string, number>> = {
  // Nothing here is a claim about what "mental" means — that is the question
  // the page exists to let you answer, and every weight is yours to change.
  //
  // But nothing here is guessed either. Every metric below REPEATS for its
  // own bucket at 0.45 or better across three seasons, so the gate chose what
  // was eligible and football chose from it. Each bucket spends exactly 100.
  //
  // ROUGHLY A THIRD OF EVERY BUDGET GOES ON MISTAKES AND DISCIPLINE. The
  // first version of these defaults spent nothing at all on them in three
  // buckets, because they were built by walking down the gate's rho list and
  // that list is topped by volume — passes, aerials, duels — which is what
  // repeats hardest. Mistakes sit mid-table and kept falling off the end.
  // That optimised for the most stable number rather than for the thing being
  // measured: in a ranking about dependability, not giving it away is half
  // the definition, and giveaways repeat at 0.49-0.77 anyway.
  //
  // Opta's own `error_90` flag stays out everywhere, and that one IS a
  // measurement failure rather than a choice: it fires 1.7 times a match
  // across both teams, so a player collects one or two a season, and it
  // repeats at 0.01 to 0.35. `giveaway_90` is the same instinct measured on
  // a base twenty times larger — dispossessed, miscontrolled, or an outright
  // error — which is why it works and the flag does not.

  // The keeper is the weak spot: almost no goalkeeping MISTAKE survives the
  // gate. Giveaways 0.15, miscontrols -0.27, errors 0.32. Only cards (0.58)
  // and goals conceded (0.53) carry any cost for him, so that is all there is
  // to spend, and it is less than the other buckets get.
  GK: { claim_90: 16, conceded_90: 14, catch_pct: 14, pass_pct: 12,
        prog_pass_90: 12, sweeper_90: 12, card_90: 8, final_third_90: 12 },

  FB: { giveaway_90: 14, ground_duel_90: 12, takeon_90: 11, cross_90: 10,
        recovery_90: 9, miscontrol_90: 8, interception_90: 8, touch_box_90: 8,
        dispossessed_90: 7, pass_pct: 7, foul_90: 6 },

  CB: { aerial_90: 13, ground_duel_90: 12, giveaway_90: 12, aerial_def_pct: 11,
        clearance_90: 10, dribbled_past_90: 10, tackle_90: 10, foul_90: 8,
        press_height: 7, availability_pct: 7 },

  // The only bucket with no cross-season test: the gate needs the same man in
  // the same role at 900+ minutes in two consecutive seasons, and there are
  // not fifteen of those. Gated on the split-half check instead — which is a
  // better substitute than it sounds. Across the 406 metric/bucket pairs that
  // have BOTH tests, split-half correlates 0.73 with cross-season, and a
  // metric clearing 0.45 on it goes on to repeat 91% of the time. Every
  // weight below scores 0.51 to 0.84. The real caveats are smaller than that
  // one: n=23 behind each of those numbers, and 36 players in the pool, so
  // the percentiles are noisier than elsewhere — noisier, not biased.
  WB: { takeon_90: 14, cross_90: 13, ground_duel_90: 12, dispossessed_90: 12,
        touch_box_90: 11, foul_90: 10, availability_pct: 10, prog_pass_90: 9,
        pass_pct: 9 },

  // A holding midfielder's TACKLES and INTERCEPTIONS do not repeat (0.39 and
  // 0.39) — but his defensive aerials do, at 0.82. Counter-intuitive, and the
  // reason this one is not built out of ground defending.
  DM: { aerial_def_90: 13, giveaway_90: 12, prog_pass_90: 12, pass_pct: 11,
        recovery_90: 11, takeon_90: 10, miscontrol_90: 9, dispossessed_90: 6,
        foul_90: 6, clearance_90: 6, final_third_90: 4 },

  CM: { decisive_90: 12, giveaway_90: 12, ground_duel_90: 11, prog_pass_90: 11,
        tackle_90: 10, aerial_def_90: 9, dribbled_past_90: 9, takeon_90: 8,
        foul_90: 7, dispossessed_90: 6, keypass_90: 5 },

  AM: { decisive_90: 12, takeon_90: 11, dribbled_past_90: 11, keypass_90: 10,
        prog_pass_90: 10, ground_duel_90: 9, foul_90: 9, miscontrol_90: 8,
        giveaway_90: 7, goal_90: 7, shot_box_pct: 6 },

  WIDE: { takeon_90: 14, touch_box_90: 12, dispossessed_90: 12,
          giveaway_90: 11, ground_duel_90: 10, bigchance_shot_90: 9,
          fouled_90: 8, cross_90: 7, foul_90: 6, miscontrol_90: 6,
          final_third_90: 5 },

  // His shooting HABITS, not his finishing. Getting on the end of big chances
  // repeats at 0.60; converting them at 0.16 and non-penalty conversion at
  // 0.09, so neither is here. Attacking headers are the standout striker
  // trait in the whole bank — volume 0.91, win rate 0.69.
  ST: { aerial_att_90: 13, decisive_90: 11, bigchance_shot_90: 11,
        miscontrol_90: 11, giveaway_90: 10, ground_duel_90: 10,
        aerial_att_pct: 9, card_90: 7, touch_box_90: 7, foul_90: 6,
        fouled_90: 5 },
};

/** Where the split payload lives. */
export const DATA = "/data/mental";

export type LeagueRef = { key: string; label: string };

/** The pooled pseudo-league.
 *
 *  WHAT IT HONESTLY ANSWERS, and what it does not. Every score on this page
 *  is a percentile WITHIN a league, and the opponent adjustment behind it is
 *  computed within a league too — by construction, neither can cross one.
 *  So pooling cannot say "best in Europe": that would require assuming the
 *  five leagues are equally strong, which is false and is the entire reason
 *  league coefficients exist.
 *
 *  What it CAN say is "most outstanding relative to his own league", which
 *  is a real question and the one this table already measures. The label on
 *  screen says exactly that, because the number would otherwise be read as
 *  the claim it is not. */
export const ALL_LEAGUES = "__all__";

type Ctx = {
  meta: Data | null;
  /** Every league that has been built, and which one is on show. */
  index: LeagueRef[];
  league: string;
  setLeague: (k: string) => void;
  /** Rows per view, fetched on demand and kept. */
  players: Record<string, Player[]>;
  /** Ask for a view; it arrives when it arrives. */
  want: (view: string) => void;
  loading: boolean;
  allWeights: Record<string, Record<string, number>>;
  setAllWeights: React.Dispatch<
    React.SetStateAction<Record<string, Record<string, number>>>
  >;
};

const RatingsCtx = createContext<Ctx | null>(null);

export function useRatings(): Ctx {
  const c = useContext(RatingsCtx);
  if (!c) throw new Error("useRatings used outside RatingsData");
  return c;
}

export function RatingsData({ children }: { children: React.ReactNode }) {
  const [meta, setMeta] = useState<Data | null>(null);
  const [players, setPlayers] = useState<Record<string, Player[]>>({});
  const [wanted, setWanted] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [allWeights, setAllWeights] =
    useState<Record<string, Record<string, number>>>(() => ({ ...PRESETS }));

  /** WHICH LEAGUE. The index used to be read once and leagues[0] taken
   *  forever, so the players board could only ever show one league however
   *  many were built. The index is now the list of what exists and `league`
   *  is the choice within it; changing it refetches meta and clears the
   *  cached player views, because rows from two leagues must never mix in
   *  one percentile. */
  const [index, setIndex] = useState<LeagueRef[]>([]);
  const [league, setLeague] = useState<string>("");

  useEffect(() => {
    fetch(`${DATA}/index.json`)
      .then((r) => r.json())
      .then((idx: { leagues: LeagueRef[] }) => {
        setIndex(idx.leagues ?? []);
        setLeague((cur) => cur || idx.leagues?.[0]?.key || "");
      })
      .catch(() => setIndex([]));
  }, []);

  useEffect(() => {
    if (!league) return;
    let alive = true;
    setMeta(null);
    setPlayers({});          // percentiles are WITHIN a league — never mix
    // The pooled view borrows the first league's META — metric list,
    // buckets, weights, the reliability gate. Those are the same shape
    // everywhere; only the ROWS differ, and those are what get pooled.
    const from = league === ALL_LEAGUES ? index[0]?.key : league;
    if (!from) return;
    fetch(`${DATA}/${from}/meta.json`)
      .then((r) => r.json())
      .then((d: Data) => alive && setMeta(d))
      .catch(() => alive && setMeta(null));
    return () => {
      alive = false;
    };
  }, [league, index]);

  const want = useCallback((view: string) => {
    setWanted((prev) => (prev.includes(view) ? prev : [...prev, view]));
  }, []);

  /** What was asked for, then every other view — the floor and swing columns
   *  need each season separately, so they all arrive eventually, just not
   *  before the first paint. */
  useEffect(() => {
    if (!meta || !wanted.length) return;
    const all = meta.views.map((v) => v.key);
    const missing = [...wanted, ...all].filter(
      (k, i, a) => a.indexOf(k) === i && !players[k],
    );
    if (!missing.length) return;
    let alive = true;
    setLoading(missing.some((k) => wanted.includes(k)));
    const from = league === ALL_LEAGUES
      ? index.map((l) => l.key)
      : [league];
    const short = (k: string) =>
      index.find((l) => l.key === k)?.label.split("-").slice(1).join("-") ?? k;
    Promise.all(
      missing.map((k) =>
        Promise.all(
          from.map((lk) =>
            fetch(`${DATA}/${lk}/${k}.json`)
              .then((r) => r.json())
              // Tag the league on every row. In the pooled view a surname
              // alone does not say whose league a score is a percentile of,
              // and that is the one thing a reader must not have to guess.
              .then((c: ColumnarView) =>
                inflate(c, meta.metric_keys).map((row) =>
                  from.length > 1 ? { ...row, lg: short(lk) } : row))
              .catch(() => [] as Player[]),
          ),
        ).then((lists) => [k, lists.flat()] as const),
      ),
    ).then((got) => {
      if (!alive) return;
      setPlayers((prev) => ({ ...prev, ...Object.fromEntries(got) }));
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, [meta, league, wanted, players]);

  const value = useMemo(
    () => ({ meta, index, league, setLeague, players, want, loading,
             allWeights, setAllWeights }),
    [meta, index, league, players, want, loading, allWeights],
  );
  return <RatingsCtx.Provider value={value}>{children}</RatingsCtx.Provider>;
}
