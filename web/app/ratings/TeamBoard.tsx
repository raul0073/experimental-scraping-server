"use client";

import { useEffect, useMemo, useState } from "react";

import { Crest } from "../components/Crest";
import { Info } from "../components/Info";
import Link from "next/link";

import { posLabel, posShort } from "../lib/positions";
import { type Player, useRatings } from "./RatingsData";

type Metric = {
  key: string;
  label: string;
  phase: "with" | "against";
  kind: "style" | "quality";
  unit: string;
  invert: boolean;
  desc: string;
};
type Rel = {
  metric: string;
  kind: string;
  n?: number;
  rho?: number;
  /** How well it predicts POINTS in the half of the season it was NOT
   *  measured on. The gate that matters for a predictor input. */
  predicts?: number;
};
type Meta = {
  league: string;
  /** club name -> badge path; absent clubs simply get none */
  crests?: Record<string, string>;
  leagues: { key: string; label: string }[];
  seasons: string[];
  season_labels: Record<string, string>;
  min_matches: number;
  grid: { cells: string[] };
  current_season: string;
  current_teams: string[];
  metrics: Metric[];
  reliability: Record<string, Rel>;
};
type Row = {
  team: string;
  season?: string;
  spell?: string;
  manager?: string;
  matches: number;
  /** Style words, derived at render rather than stored. */
  tags?: string[];
} & Record<string, number | string | string[] | undefined>;

/** Spreading a Row loses its index signature, so the scored rows say so
 *  explicitly — the style columns still look metrics up by key. */
/** Spreading a Row loses its index signature, so the scored rows say so
 *  explicitly — the manager panel still looks metrics up by key. */
type Scored = Row & {
  score: number;
  withBall: number;
  against: number;
  /** Style said in words, split by phase — the same division the score uses,
   *  so a reader is never comparing how a side attacks with how it defends. */
  withTags: string[];
  againstTags: string[];
  /** Where their RESULTS put them, as a percentile of points per match in
   *  the same pool. Kept entirely outside the score. */
  result: number;
  /** TEAM MENTAL: the squad's player ratings aggregated, and its softest
   *  fielded position. A different question from the stats layer, and the
   *  gap between the two is the manager's. */
  squad: number;
  weakest: number;
  weakAt: string;
};

import {
  ActiveFilters, BUDGET, FILTER_BAR, Field, MARGINAL, RELIABLE, SELECT,
  SPREAD_TEAM, ScoreRing,
} from "./scoreUi";

const DATA = "/data/team";

/** The pooled pseudo-league.
 *
 *  Quality here is OPPONENT-ADJUSTED WITHIN A LEAGUE — conceding four shots
 *  to Manchester City and four to Sheffield United stop counting the same,
 *  but only against opponents in the same competition. That adjustment
 *  cannot reach across leagues, so a pooled table cannot say a 70 in one
 *  beats a 68 in another. What it CAN say is who stands out most against
 *  the sides they actually play, which is the question the table already
 *  answers — one league at a time. */
const ALL_LEAGUES = "__all__";

/** Must match the slugs the team pages are generated under. */
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Starting points, and only that. Every weight here clears 0.40 on the
 *  split-half test for a manager spell, so nothing in the defaults is a
 *  number the data cannot hold up.
 *
 *  Style metrics are deliberately absent and cannot be weighted at all. A
 *  side that goes long is not worse than one that plays out — ranking
 *  directness would be the table quietly asserting that a way of playing is
 *  correct, which is not a finding. Style is shown, never scored. */
const PRESET: Record<string, number> = {
  // Built from both gates, not from taste. Every weight below agrees with
  // itself across half a season AND predicts points in the half it was not
  // measured on. Nothing style-conditional is here: "do their long balls
  // stick" only means something if they play long, so it measures a choice.
  //
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
  // creating from them barely does (0.22), because a side gets about eleven
  // set-piece big chances in half a season and that is too few to measure.
  // Arsenal's three-season lead on set-piece output is real; the per-season
  // number is not yet trustworthy enough to carry weight.
  sp_shot_con_90: 6,
  sp_shot_90: 4,
};

function fmt(v: unknown, unit: string) {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return unit === "%" ? v.toFixed(1) : v.toFixed(unit === "/match" ? 2 : 1);
}

/** A dot, never coloured text. Two questions sit behind it and both are in
 *  the tooltip: does the metric agree with itself across half a season, and
 *  does it predict POINTS in the half it was not measured on.
 *
 *  The second is the one that matters for a predictor input, and it is the
 *  one that caught the trap: tackles, interceptions and recoveries all repeat
 *  beautifully and all predict FEWER points, because a side doing a lot of
 *  them is a side without the ball. */
function relTone(r?: Rel) {
  const holds = r?.rho;
  const pred = r?.predicts;
  const bits = [
    holds === undefined
      ? "agreement with itself: not computed"
      : `agrees with itself ${holds.toFixed(2)}${r?.n ? ` (n=${r.n})` : ""}`,
    pred === undefined
      ? "predicts points: not computed"
      : `predicts next-half points ${pred >= 0 ? "+" : ""}${pred.toFixed(2)}`,
  ];
  const bad =
    (holds !== undefined && holds < MARGINAL) ||
    (pred !== undefined && Math.abs(pred) < 0.25);
  const dot = bad
    ? "bg-bad"
    : holds !== undefined && holds >= RELIABLE
      ? "bg-good"
      : "bg-[#c99a1e]";
  return { dot, bad, tip: bits.join("\n") };
}

/** A style value against the league, as a bar that fills from the middle.
 *  No colour meaning — high is not good, it is just high. */
function StyleBar({ pct }: { pct: number }) {
  const p = Math.max(0, Math.min(100, pct));
  return (
    <span className="relative block h-1.5 w-full overflow-hidden rounded-full bg-[#eef0f2]">
      <span className="absolute left-1/2 top-0 h-full w-px bg-line" />
      <span
        className="absolute top-0 h-full rounded-full bg-[#8a949e]"
        style={
          p >= 50
            ? { left: "50%", width: `${(p - 50) * 0.94}%` }
            : { right: "50%", width: `${(50 - p) * 0.94}%` }
        }
      />
    </span>
  );
}

/** THE STYLE BANK. Six numbers describing how a side plays are six numbers
 *  nobody reads; the same thing said in words is read instantly. Each style
 *  metric carries a name for each end of it, and a team is described by the
 *  two or three dimensions on which it is furthest from ordinary.
 *
 *  Nothing here is a judgement and none of it touches the score. "Sits off"
 *  is not worse than "high press" — Atletico and Liverpool have both won
 *  leagues — it is just what the side does. */
const STYLE_WORDS: Record<string, { high: string; low: string }> = {
  // with the ball
  poss_share: { high: "possession", low: "cedes the ball" },
  directness: { high: "direct", low: "plays short" },
  // NOT "patient": tempo is passes per minute of possession, and a direct
  // side records few because the ball is in the air.
  tempo: { high: "quick tempo", low: "slow tempo" },
  width: { high: "uses the width", low: "goes through the middle" },
  // A low build-up share is a side rarely IN its own third, not one that
  // bypasses it — Arsenal came out as "skips the build-up", backwards.
  buildup_share: { high: "builds from the back", low: "lives up the pitch" },
  cross_share: { high: "crosses", low: "works it in" },
  // against the ball
  press_height: { high: "high line", low: "deep block" },
  ppda: { high: "sits off", low: "high press" },
  recovery_high_pct: { high: "wins it back high", low: "wins it back deep" },
};
const STYLE_EDGE = 20;   // percentile points from the middle before it is worth saying

function styleTags(
  pct: Record<string, number>,
  keys: string[],
): string[] {
  return keys
    .filter((k) => STYLE_WORDS[k])
    .map((k) => ({ p: pct[k], w: STYLE_WORDS[k] }))
    .filter((e) => typeof e.p === "number" && Math.abs(e.p - 50) >= STYLE_EDGE)
    .sort((a, b) => Math.abs(b.p - 50) - Math.abs(a.p - 50))
    .slice(0, 3)
    .map((e) => (e.p >= 50 ? e.w.high : e.w.low));
}

/** TEAM MENTAL — the squad's player ratings, aggregated.
 *
 *  A club's mentality is the collection of players it has, so this is built
 *  from the player board and moves when its weights move. It is NOT the
 *  stats layer beside it, which measures what the collective actually
 *  produces from team events. The two are different questions and the gap
 *  between them is the manager's.
 *
 *  Two numbers, because one hides the thing worth knowing:
 *
 *    SQUAD    every qualifying player's percentile within his own bucket,
 *             weighted by the minutes he played in that role
 *    WEAKEST  the softest position the club ACTUALLY FIELDS
 *
 *  Only positions the club fields count toward the weakest link. Liverpool
 *  have no wing-backs and Newcastle no attacking midfielder — that is a
 *  shape, not a hole, and scoring a club for a position it never picks would
 *  punish it for its formation.
 */
function teamMental(
  rows: Player[],
  score: (p: Player) => number,
): Map<string, { squad: number; weakest: number; weakAt: string }> {
  // A percentile inside each bucket first, so a keeper is compared with
  // keepers before anything is averaged across positions.
  const pctOf = new Map<Player, number>();
  const byBucket: Record<string, Player[]> = {};
  for (const p of rows) (byBucket[p.p] ??= []).push(p);
  for (const list of Object.values(byBucket)) {
    const scored = list
      .map((p) => ({ p, v: score(p) }))
      .sort((a, b) => a.v - b.v);
    scored.forEach((e, i) =>
      pctOf.set(e.p, scored.length > 1 ? (i / (scored.length - 1)) * 100 : 50),
    );
  }

  const perClub = new Map<
    string,
    { num: number; den: number; buckets: Record<string, { num: number; den: number }> }
  >();
  for (const p of rows) {
    const club = String(p.t);
    const e =
      perClub.get(club) ?? { num: 0, den: 0, buckets: {} };
    const v = pctOf.get(p) ?? 50;
    e.num += v * p.m;
    e.den += p.m;
    const b = (e.buckets[p.p] ??= { num: 0, den: 0 });
    b.num += v * p.m;
    b.den += p.m;
    perClub.set(club, e);
  }

  const out = new Map<string, { squad: number; weakest: number; weakAt: string }>();
  for (const [club, e] of perClub) {
    if (!e.den) continue;
    // A position needs real minutes before it can be called this club's weak
    // spot — one cameo at wing-back is not where a season is lost.
    const fielded = Object.entries(e.buckets).filter(
      ([, b]) => b.den >= e.den * 0.04,
    );
    let weakest = 50;
    let weakAt = "";
    if (fielded.length) {
      const sorted = fielded
        .map(([k, b]) => ({ k, v: b.num / b.den }))
        .sort((a, b) => a.v - b.v);
      weakest = sorted[0].v;
      weakAt = sorted[0].k;
    }
    out.set(club, { squad: e.num / e.den, weakest, weakAt });
  }
  return out;
}

type Sort = { key: string; dir: 1 | -1 };

/** A sortable header that also carries its explanation. The info icon stops
 *  the click, so reaching for the popover never re-sorts the table under the
 *  reader's hand. */
function Th({
  k,
  sort,
  setSort,
  children,
  info,
  align = "center",
  className = "",
}: {
  k: string;
  sort: Sort;
  setSort: (s: Sort) => void;
  children: React.ReactNode;
  info?: React.ReactNode;
  align?: "left" | "center";
  className?: string;
}) {
  const active = sort.key === k;
  return (
    <th
      onClick={() =>
        setSort({
          key: k,
          // a fresh column opens biggest-first, which is what anyone reading
          // a ranking wants; "club" is the exception and opens A-Z
          dir: active ? ((sort.dir * -1) as 1 | -1) : k === "team" ? 1 : -1,
        })
      }
      className={`cursor-pointer select-none px-3 py-2 font-semibold transition-colors hover:text-ink ${
        align === "left" ? "text-left" : "text-center"
      } ${active ? "text-ink" : ""} ${className}`}
    >
      <span className="inline-flex items-center">
        {children}
        <span className={active ? "" : "opacity-0"}>
          {" "}
          {sort.dir === -1 ? "▾" : "▴"}
        </span>
        {info && (
          <span onClick={(e) => e.stopPropagation()}>
            <Info>{info}</Info>
          </span>
        )}
      </span>
    </th>
  );
}

export function TeamBoard() {
  // The player board's data and config. Team mental is the squad's ratings,
  // so it has to move when those weights move.
  const {
    meta: pMeta,
    players,
    want,
    allWeights,
  } = useRatings();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [cuts, setCuts] = useState<Record<string, Row[]>>({});
  const [weights, setWeights] = useState<Record<string, number>>({ ...PRESET });
  const [blockUnreliable, setBlockUnreliable] = useState(true);
  const [season, setSeason] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const [sort, setSort] = useState<Sort>({ key: "score", dir: -1 });
  /** Clubs to show. Empty means all of them.
   *
   *  A SET RATHER THAN ONE CHOICE, because filtering a table OF clubs down to
   *  a single club leaves one row and answers nothing. The question worth
   *  asking is "how do these three compare", so the select ADDS to a
   *  comparison and the chips below take clubs back out. */
  const [picks, setPicks] = useState<string[]>([]);
  const [layer, setLayer] = useState<"z" | "zs" | "zc">("z");

  /** The players view matching the season on show: "all" is the pooled one. */
  const pView = season === "all" ? "total" : season;
  useEffect(() => {
    if (pMeta) want(pView);
  }, [pMeta, pView, want]);

  /** A player's score on HIS bucket's config, gated the same way the player
   *  board gates it — a metric the gate refuses drops out of numerator and
   *  divisor alike, so the scale stays 0-100. */
  const playerScore = useMemo(() => {
    return (p: Player) => {
      let sum = 0;
      let used = 0;
      for (const [k, w] of Object.entries(allWeights[p.p] ?? {})) {
        if (w <= 0) continue;
        const r = pMeta?.reliability?.[k]?.[p.p];
        if (r !== undefined && r.rho < MARGINAL) continue;
        sum += (p.qa[k] ?? 50) * w;
        used += w;
      }
      return used ? sum / used : 50;
    };
  }, [allWeights, pMeta]);

  const mental = useMemo(
    () => teamMental(players[pView] ?? [], playerScore),
    [players, pView, playerScore],
  );
  const [configOpen, setConfigOpen] = useState(false);

  /** WHICH LEAGUE. leagues[0] used to be taken once and kept, so the board
   *  could only show the first league however many had been built. The index
   *  is the list of what exists; `league` is the choice within it. Every
   *  number here is opponent-adjusted WITHIN a league, so switching swaps
   *  the whole dataset rather than filtering one table. */
  const [index, setIndex] = useState<{ key: string; label: string }[]>([]);
  const [league, setLeague] = useState("");

  useEffect(() => {
    fetch(`${DATA}/index.json`)
      .then((r) => r.json())
      .then((idx: { leagues: { key: string; label: string }[] }) => {
        setIndex(idx.leagues ?? []);
        setLeague((cur) => cur || idx.leagues?.[0]?.key || "");
      })
      .catch(() => setIndex([]));
  }, []);

  useEffect(() => {
    if (!league) return;
    let alive = true;
    setMeta(null);
    setSeason("");            // season labels differ per league
    const from = league === ALL_LEAGUES ? index.map((l) => l.key) : [league];
    if (!from.length) return;
    const short = (k: string) =>
      index.find((l) => l.key === k)?.label.split("-").slice(1).join("-") ?? k;
    const tag = (lk: string) => (r: Row) =>
      from.length > 1 ? { ...r, lg: short(lk) } : r;
    Promise.all(
      from.map((lk) =>
        Promise.all(
          ["meta", "club", "club_season", "spell"].map((f) =>
            fetch(`${DATA}/${lk}/${f}.json`).then((r) => r.json()),
          ),
        ).then(([m, club, clubSeason, spell]) => ({
          lk, m: m as Meta,
          // Tag the league on every row: in a pooled table a club name does
          // not say which league its score is a percentile of.
          // Only tag the league when more than one is pooled. With a single
          // league selected the badge says nothing the page header has not
          // already said, and a redundant chip on every row is noise.
          club: (club as Row[]).map(tag(lk)),
          club_season: (clubSeason as Row[]).map(tag(lk)),
          spell: (spell as Row[]).map(tag(lk)),
        })),
      ),
    )
      .then((parts) => {
        if (!alive || !parts.length) return;
        // The first league's META carries the structure — metric list,
        // reliability gate, grid. Identical shape everywhere; only the rows
        // differ, and those are what get pooled. Season labels are unioned
        // so the picker offers every season any league has.
        const base = parts[0].m;
        // CRESTS FROM EVERY LEAGUE, merged. The pooled table takes its
        // structure from the first league's meta, and taking its badges from
        // there too would leave four leagues' clubs unbadged.
        const crests = Object.assign({}, ...parts.map((x) => x.m.crests ?? {}));
        const seasons = [...new Set(parts.flatMap((x) => x.m.seasons))].sort();
        const labels = Object.assign({}, ...parts.map((x) => x.m.season_labels));
        setMeta(
          from.length > 1
            ? { ...base, seasons, season_labels: labels, crests,
                current_teams: parts.flatMap((x) => x.m.current_teams) }
            : base,
        );
        setCuts({
          club: parts.flatMap((x) => x.club),
          club_season: parts.flatMap((x) => x.club_season),
          spell: parts.flatMap((x) => x.spell),
        });
      })
      .catch(() => alive && setMeta(null));
    return () => {
      alive = false;
    };
  }, [league, index]);

  /** OPEN ON ALL SEASONS, not the one in progress.
   *
   *  A season five rounds old is twenty clubs judged on five matches each,
   *  which is why the table read as a wall of middling numbers — the
   *  reliability gate needs team-seasons to correlate against, and one
   *  partial season gives it almost nothing. The all-seasons view is the
   *  one that has something to say in September; the current season is
   *  still a click away for anyone who wants form rather than standing. */
  useEffect(() => {
    if (meta && !season) setSeason("all");
  }, [meta, season]);

  const quality = useMemo(
    () => (meta?.metrics ?? []).filter((m) => m.kind === "quality"),
    [meta],
  );
  const styles = useMemo(
    () => (meta?.metrics ?? []).filter((m) => m.kind === "style"),
    [meta],
  );

  const spent = Object.values(weights).reduce((a, b) => a + (b || 0), 0);
  const setWeight = (key: string, value: number) =>
    setWeights((prev) => {
      const used = Object.values(prev).reduce((a, b) => a + (b || 0), 0);
      const room = BUDGET - used + (prev[key] ?? 0);
      return { ...prev, [key]: Math.max(0, Math.min(value, room)) };
    });

  /** Every quality metric is percentiled across the rows on show, then
   *  weighted. Adjusted columns are used wherever they exist, so the score
   *  is about the side and not about who it happened to play. */
  const rows = useMemo(() => {
    if (!meta) return [];
    // Pooled view shows the clubs in the league NOW; a past season shows
    // whoever was in it THEN. Without the filter the all-seasons table lists
    // Luton and Sheffield United beside Arsenal, which is history rather
    // than a league table.
    const here = new Set(meta.current_teams);
    const pooled = (cuts.club ?? []).filter((r) => here.has(r.team));
    // A club that spent one of the four seasons up here has 42 matches
    // against everyone else's 118, and one season of noise is not a
    // description of a club. Judged on its own season instead — pick that
    // season from the dropdown and it reappears.
    const fullest = Math.max(...pooled.map((r) => r.matches), 1);
    const src =
      season === "all"
        ? pooled.filter((r) => r.matches >= fullest * 0.6)
        : (cuts.club_season ?? []).filter((r) => r.season === season);
    if (!src.length) return [];

    const pct: Record<string, Map<Row, number>> = {};
    for (const m of meta.metrics) {
      const col = `${m.key}_adj` in (src[0] ?? {}) ? `${m.key}_adj` : m.key;
      const vals = src
        .map((r) => ({ r, v: r[col] }))
        .filter((e) => typeof e.v === "number") as { r: Row; v: number }[];
      vals.sort((a, b) => a.v - b.v);
      const map = new Map<Row, number>();
      vals.forEach((e, i) => {
        const p = vals.length > 1 ? (i / (vals.length - 1)) * 100 : 50;
        // Quality flips so 100 is always good. Style never flips — there is
        // no good end of "goes direct", only more of it and less of it.
        map.set(e.r, m.kind === "quality" && m.invert ? 100 - p : p);
      });
      pct[m.key] = map;
    }

    const active = Object.entries(weights).filter(([k, w]) => {
      if (w <= 0) return false;
      if (blockUnreliable) {
        const r = meta.reliability[k];
        if (r && relTone(r).bad) return false;
      }
      return true;
    });
    // Points per match as a percentile of the same pool, so the two rings
    // are on one scale and the gap between them reads directly.
    const ptsPct = new Map<Row, number>();
    {
      const vals = src
        .map((r) => ({ r, v: r.pts }))
        .filter((e) => typeof e.v === "number") as { r: Row; v: number }[];
      vals.sort((a, b) => a.v - b.v);
      vals.forEach((e, i) =>
        ptsPct.set(e.r, vals.length > 1 ? (i / (vals.length - 1)) * 100 : 50),
      );
    }
    const withStyleKeys = styles.filter((m) => m.phase === "with").map((m) => m.key);
    const againstStyleKeys = styles
      .filter((m) => m.phase === "against")
      .map((m) => m.key);
    const sum = (r: Row, only?: "with" | "against" | "set") => {
      let acc = 0;
      let used = 0;
      for (const [k, w] of active) {
        const m = meta.metrics.find((x) => x.key === k);
        if (!m || (only && m.phase !== only)) continue;
        acc += (pct[k]?.get(r) ?? 50) * w;
        used += w;
      }
      return used ? acc / used : 50;
    };
    return src
      .map(
        (r): Scored => {
          const stylePct = Object.fromEntries(
            styles.map((m) => [m.key, pct[m.key]?.get(r) ?? 50]),
          );
          return {
          ...r,
          score: sum(r),
          withBall: sum(r, "with"),
          against: sum(r, "against"),
          withTags: styleTags(stylePct, withStyleKeys),
          againstTags: styleTags(stylePct, againstStyleKeys),
          result: ptsPct.get(r) ?? 50,
          squad: mental.get(String(r.team))?.squad ?? 50,
          weakest: mental.get(String(r.team))?.weakest ?? 50,
          weakAt: mental.get(String(r.team))?.weakAt ?? "",
          };
        },
      )
      .sort((a, b) => {
        const pick = (r: Scored): number | string =>
          sort.key === "team"
            ? String(r.team)
            : sort.key === "gap"
              ? r.score - r.result
              : sort.key === "weakest"
                ? r.weakest
                : (r[sort.key] as number) ?? -Infinity;
        const x = pick(a);
        const y = pick(b);
        return typeof x === "string" || typeof y === "string"
          ? String(x).localeCompare(String(y)) * sort.dir
          : (x - y) * sort.dir;
      });
  }, [meta, cuts, season, weights, blockUnreliable, styles, mental, sort]);

  /** The club list, and the rows actually rendered.
   *
   *  FILTERED HERE, NOT INSIDE THE MEMO ABOVE, and that is the whole point.
   *  Every score in this table is a PERCENTILE across the rows in the memo,
   *  so filtering before the scoring would re-rank the chosen clubs against
   *  each other — three mid-table sides would come out 100, 50 and 0, and the
   *  table would say something that is not true. Filtering after leaves each
   *  club with its standing in the whole league, which is the only comparison
   *  worth making. It also keeps the select's list complete, instead of
   *  shrinking it to whatever is already picked with no way back. */
  const clubs = useMemo(
    () => [...new Set(rows.map((r) => String(r.team)))].sort((a, b) =>
      a.localeCompare(b),
    ),
    [rows],
  );
  const shown = picks.length
    ? rows.filter((r) => picks.includes(String(r.team)))
    : rows;
  /** Rank in the FULL table, not position in the filtered list. The row
   *  number was the loop index, so comparing three clubs numbered them 1, 2,
   *  3 — a side lying fourteenth would be shown as second. Same trap as
   *  percentiling after a filter, one line further down the page. */
  const rankOf = new Map(rows.map((r, i) => [r, i + 1]));

  if (!meta) return <p className="text-[13.5px] text-ink-2">Loading the teams…</p>;

  const detail = picked ? (cuts.spell ?? []).filter((r) => r.team === picked) : [];
  const shotMax = Math.max(
    0.2,
    ...detail.flatMap((r) =>
      (meta?.grid.cells ?? []).map((c) => {
        const v = r[`${layer}_${c}`];
        return typeof v === "number" ? v : 0;
      }),
    ),
  );
  const stylePct = (r: Row, m: Metric) => {
    const src = cuts.club ?? [];
    const vals = src.map((x) => x[m.key]).filter((v) => typeof v === "number") as number[];
    const v = r[m.key];
    if (typeof v !== "number" || !vals.length) return 50;
    return (vals.filter((x) => x < v).length / vals.length) * 100;
  };

  return (
    <div>
      {/* ---------------------------------------------------- filter bar
          The same control language as the players board, from the same
          definitions in scoreUi — both had grown their own copy of "label in
          12.5px ink beside a px-2 py-1 select", which read as a sentence
          rather than as controls and gave a pointer nothing much to hit.
          There are no positions to group here, so the rail above it is simply
          absent; everything else is shared. */}
      <div className={FILTER_BAR}>
        {index.length > 1 && (
          <Field
            label="league"
            title="Quality is opponent-adjusted within a league, so a score compares a club to its own league and not across them"
          >
            <select
              value={league}
              onChange={(e) => setLeague(e.target.value)}
              className={SELECT}
            >
              {index.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label.split("-").slice(1).join("-") || l.label}
                </option>
              ))}
              <option value={ALL_LEAGUES}>All leagues</option>
            </select>
          </Field>
        )}
        <Field
          label="season"
          title="All seasons pools every season we hold, rather than averaging season ranks."
        >
          <select
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            className={SELECT}
          >
            <option value="all">All seasons</option>
            {meta.seasons.map((s) => (
              <option key={s} value={s}>
                {meta.season_labels[s]}
              </option>
            ))}
          </select>
        </Field>
        {/* Adds to the comparison rather than replacing it. The value snaps
            back to the placeholder so the same control can be used again
            immediately, and the chips below are where the picks live. */}
        <Field
          label="compare clubs"
          title="Add clubs to compare. Scores stay percentiles across the whole league, so each club keeps its real standing instead of being re-ranked against the others you picked."
        >
          <select
            value=""
            onChange={(e) => {
              const v = e.target.value;
              if (v && !picks.includes(v)) setPicks([...picks, v]);
            }}
            className={SELECT}
          >
            <option value="">add a club…</option>
            {clubs
              .filter((c) => !picks.includes(c))
              .map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
          </select>
        </Field>
        <span className="num ml-auto self-center whitespace-nowrap text-[12.5px] text-ink-3">
          {shown.length}
          {picks.length ? ` of ${rows.length}` : ""} clubs
        </span>
      </div>

      <ActiveFilters
        active={[
          ...(season === "all"
            ? []
            : [
                {
                  // Falls back to the season key itself. The label map does
                  // not carry an entry for every value `season` can hold, and
                  // an undefined label renders an empty chip the reader
                  // cannot identify — as well as being the undefined key
                  // React was warning about.
                  label: meta.season_labels[season] ?? season,
                  clear: () => setSeason("all"),
                },
              ]),
          ...picks.map((c) => ({
            label: c,
            clear: () => setPicks(picks.filter((x) => x !== c)),
          })),
        ]}
      />

      {/* The caveat belongs UNDER the controls, not inside them. Inline it
          competed with the selects for the same row and pushed them around as
          its text changed with the selection. */}
      <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
        {season === "all"
          ? (league === ALL_LEAGUES
              ? "Every league pooled. Quality is opponent-adjusted WITHIN a league, so this ranks who stands out most against the sides they actually play — not a claim that a 70 in one league beats a 68 in another."
              : "The clubs in the league now, over every season we have — and only those that were here for most of it. A club up for one of the four is judged on that season instead.")
          : `Whoever was in the league in ${meta.season_labels[season]}.`}
      </p>

      {/* ============================================= the config */}
      <section className="mt-4 rounded-xl border border-line bg-card">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-line px-4 py-3">
          <button
            onClick={() => setConfigOpen((o) => !o)}
            className="flex items-baseline gap-1.5 text-[14px] font-semibold hover:text-home"
          >
            <span className="text-ink-3">{configOpen ? "▾" : "▸"}</span>
            What counts as a good side — and you decide
          </button>
          <span className="num text-[12.5px]">
            <span className={spent === BUDGET ? "font-semibold text-good" : "font-semibold text-[#9a7400]"}>
              {spent}
            </span>
            <span className="text-ink-3"> / {BUDGET}</span>
          </span>
          <label className="ml-auto flex items-center gap-2 text-[12px] text-ink-2">
            <input
              type="checkbox"
              checked={blockUnreliable}
              onChange={(e) => setBlockUnreliable(e.target.checked)}
            />
            ignore metrics that don&apos;t hold up
          </label>
        </div>
        {configOpen && (
          <div className="p-4">
            <p className="mb-3 text-[12px] leading-relaxed text-ink-2">
              Only <strong>quality</strong> is weighted, and only things that
              do not depend on how a side chooses to play. &ldquo;Do their long
              balls stick&rdquo; is out — it only means anything if they play
              long, so it measures a choice rather than a quality. So is pass
              completion, which safe passing flatters. What is left does not
              care how you got there: reached the box, made a big chance, took
              a shot, moved it up the pitch, and the four conceded equivalents.
              Style and points are shown on every row and never scored.
            </p>
            <div className="grid items-start gap-3 sm:grid-cols-3">
              {(["with", "against", "set"] as const).map((phase) => (
                <div key={phase} className="rounded-lg border border-line bg-[#fcfcfd] p-2.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-2">
                    {phase === "with"
                      ? "With the ball"
                      : phase === "against"
                        ? "Against the ball"
                        : "Set pieces"}
                  </div>
                  {quality
                    .filter((m) => m.phase === phase)
                    .map((m) => {
                      const tone = relTone(meta.reliability[m.key]);
                      const w = weights[m.key] ?? 0;
                      const off = tone.bad && blockUnreliable;
                      return (
                        <div key={m.key} className="mt-2">
                          <div className="flex items-baseline justify-between gap-2">
                            <span
                              className="flex items-baseline gap-1.5 text-[12.5px] text-ink-2"
                              title={`${m.desc}\n\n${tone.tip}`}
                            >
                              <i className={`inline-block h-2 w-2 shrink-0 translate-y-[-1px] rounded-full ${tone.dot}`} />
                              {m.label}
                              {m.invert ? " ↓" : ""}
                              {off && (
                                <span className="text-[11px] text-ink-3">not counted</span>
                              )}
                            </span>
                            <span className="num text-[11.5px] text-ink-3">{w}</span>
                          </div>
                          <input
                            type="range"
                            min={0}
                            max={30}
                            value={w}
                            onChange={(e) => setWeight(m.key, Number(e.target.value))}
                            className="w-full accent-[#4a7ba6]"
                          />
                        </div>
                      );
                    })}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ============================================= the table */}
      <div className="mt-6 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-2 text-left font-semibold">#</th>
              <Th k="team" sort={sort} setSort={setSort} align="left" className="pr-3">
                Club
              </Th>
              <Th k="score" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">What the collective produces.</b> Built from team events — box entries, shots, big chances and the same four conceded — every one opponent-adjusted across the whole league, so conceding four shots to Manchester City and four to Sheffield United stop counting the same. This is the STATS LAYER, a different question from Squad.</>}>
                Overall
              </Th>
              <Th k="squad" sort={sort} setSort={setSort} className="bg-[#eef3f7] text-[#1c5b8a]"
                  info={<><b className="text-ink">TEAM MENTAL — the players they have.</b> Every qualifying player&apos;s percentile within his own position, weighted by the minutes he played in it. It runs on the weights you set on the Players tab, so move one there and this moves. A squad rating well above the Overall beside it means the parts are better than the whole.</>}>
                Squad
              </Th>
              <Th k="weakest" sort={sort} setSort={setSort} className="bg-[#eef3f7] text-[#1c5b8a]"
                  info={<><b className="text-ink">The softest position they field.</b> Positions a club never picks are ignored — Liverpool have no wing-backs and Newcastle no attacking midfielder, and that is a shape rather than a hole. Read it with the period in mind: Arsenal&apos;s strikers rate 23 in 25/26 and 60 pooled, which is one bad season, not a standing weakness.</>}>
                Weak spot
              </Th>
              <Th k="withBall" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">The attacking half of Overall.</b> How often they reach the final third and the box, make big chances and get shots away, opponent-adjusted.</>}>
                With ball
              </Th>
              <Th k="against" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">The defensive half of Overall.</b> Box entries, shots and big chances conceded, plus set pieces. Nothing about tackles or interceptions: at team level those predict FEWER points, because a side making a lot of them is a side without the ball.</>}>
                Against
              </Th>
              <Th k="result" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">What they actually won.</b> Points per match, as a percentile of the same pool. Shown, never scored — a side&apos;s points in half a season predict its other half at 0.59 while the process metrics manage 0.78, so scoring points would cost the table its whole advantage.</>}>
                Results
              </Th>
              <Th k="gap" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">Overall minus Results.</b> Positive means the performances are ahead of the points — a side getting less than it deserves, and the process is the better guide to what comes next. Negative is the reverse, and that is the side of the gap that tends to come back. Gaps are enormous after four matches and small over a full season.</>}>
                Gap
              </Th>
              <Th k="matches" sort={sort} setSort={setSort}
                  info={<><b className="text-ink">Matches behind the numbers.</b> The pooled view only shows clubs that were here for most of the period, so a side promoted last summer is judged on its own season rather than against three years of someone else&apos;s.</>}>
                Mt
              </Th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr
                key={`${r.team}-${r.spell ?? r.season ?? "all"}`}
                className="border-t border-line hover:bg-[#fafbfc]"
              >
                <td className="num py-2 pl-4 pr-2 text-ink-3">{rankOf.get(r) ?? i + 1}</td>
                <td className="whitespace-nowrap py-2 pr-3 font-medium">
                  <Link
                    href={`/team/${slugify(String(r.team))}`}
                    className="inline-flex items-center gap-2 hover:text-home hover:underline"
                  >
                    {/* A badge is recognised before a name is read, and this
                        table is twenty rows of them. A club we hold no badge
                        for renders nothing — never a broken image. */}
                    <Crest src={meta.crests?.[String(r.team)]} alt="" size={18} />
                    {r.team}
                  </Link>
                  {/* Pooled view only: a club name does not say which
                      league its score is a percentile of. */}
                  {r.lg && (
                    <span className="ml-1.5 rounded border border-line px-1 py-px text-[10px] font-normal text-ink-3">
                      {String(r.lg)}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-ink">
                  <div className="flex justify-center">
                    <ScoreRing score={r.score} spread={SPREAD_TEAM} />
                  </div>
                </td>
                <td className="bg-[#f7fafc] px-3 py-1.5 text-ink">
                  <div className="flex justify-center">
                    <ScoreRing spread={SPREAD_TEAM} score={r.squad} />
                  </div>
                </td>
                <td
                  className="bg-[#f7fafc] px-3 py-2 text-center text-[12px]"
                  title={
                    r.weakAt
                      ? `Their weakest fielded position is ${posLabel(r.weakAt).toLowerCase()}, at ${r.weakest.toFixed(0)} of 100.`
                      : "no position with enough minutes to judge"
                  }
                >
                  {r.weakAt ? (
                    <>
                      <span className="font-medium text-ink-2">
                        {posShort(r.weakAt)}
                      </span>{" "}
                      <span className="num text-ink-3">{r.weakest.toFixed(0)}</span>
                    </>
                  ) : (
                    <span className="text-ink-3">—</span>
                  )}
                </td>
                <td className="num px-3 py-2 text-center text-[12.5px]">
                  {r.withBall.toFixed(0)}
                </td>
                <td className="num px-3 py-2 text-center text-[12.5px]">
                  {r.against.toFixed(0)}
                </td>
                <td className="px-3 py-1.5 text-ink">
                  <div className="flex items-center justify-center gap-1.5">
                    <ScoreRing spread={SPREAD_TEAM} score={r.result} />
                    <span
                      className="num text-[11.5px] text-ink-3"
                      title={`${typeof r.pts === "number" ? r.pts.toFixed(2) : "—"} points per match`}
                    >
                      {typeof r.pts === "number" ? r.pts.toFixed(2) : "—"}
                    </span>
                  </div>
                </td>
                <td
                  className="num px-2 py-2 text-center text-[12.5px] font-medium"
                  title={
                    r.score - r.result >= 0
                      ? "The process rates them higher than their results do — the side has been getting less than it deserves, and the process is the better guide to what comes next (0.78 against 0.59)."
                      : "Their results are ahead of the process — they have been getting more than the performances merit, and that is the side of the gap that tends to come back."
                  }
                >
                  <span
                    className={
                      Math.abs(r.score - r.result) < 12
                        ? "text-ink-3"
                        : r.score > r.result
                          ? "text-good"
                          : "text-bad"
                    }
                  >
                    {r.score - r.result >= 0 ? "+" : ""}
                    {(r.score - r.result).toFixed(0)}
                  </span>
                </td>
                <td className="num py-2 pl-2 pr-4 text-center text-[12px] text-ink-3">
                  {r.matches}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ============================================= the club, by manager */}
      <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
        Measured per match, then averaged into whatever cut you pick — a club,
        a club in one season, or a manager&apos;s spell. Quality is
        opponent-adjusted across the whole league at once, so conceding four
        shots to Manchester City and four to Sheffield United stop counting the
        same. {meta.min_matches}+ matches required. Style is descriptive and is
        never ranked.
      </p>
    </div>
  );
}
