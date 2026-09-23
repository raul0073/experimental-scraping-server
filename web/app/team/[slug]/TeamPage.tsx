"use client";

import { useEffect, useMemo, useState } from "react";

import { BestXI } from "../../components/BestXI";
import { Crest } from "../../components/Crest";
import { Crumbs } from "../../components/Crumbs";
import { PassNetwork, type Link, type Node } from "../../components/PassNetwork";
import { PitchZones, ZoneLegend } from "../../components/PitchZones";
import { Pizza, PizzaLegend, type Slice } from "../../components/Pizza";
import { ShotLegend, ShotMap, type Shot } from "../../components/ShotMap";
import { Tabs, useTab } from "../../components/Tabs";
import { bestXI } from "../../lib/bestXI";
import { posLabel, posShort } from "../../lib/positions";
import { buildSquad, scorePlayer } from "../../lib/squad";
import { RatingsData, type Player, useRatings } from "../../ratings/RatingsData";
import {
  PRESET,
  type TeamRow,
  percentiles,
  scoreTeams,
} from "../../ratings/teamScore";

type Metric = {
  key: string;
  label: string;
  phase: string;
  kind: string;
  unit: string;
  invert: boolean;
  desc: string;
};
type Meta = {
  league: string;
  /** team name -> badge url, resolved ONCE in the builder. Guessing the
   *  filename here gave "Man Utd" -> /logos/…/Man Utd.png, which is not the
   *  file: the badge is "Manchester Utd.png". */
  crests: Record<string, string>;
  current_season: string;
  seasons: string[];
  season_labels: Record<string, string>;
  grid: { cells: string[] };
  metrics: Metric[];
  reliability: Record<string, { rho?: number; predicts?: number }>;
};
type Row = { team: string; matches: number } & Record<string, number | string>;

/** The drawing material, packed. A shot is five numbers and a name index
 *  rather than nine named fields — written out longhand the 27 clubs came to
 *  8.5 MB, almost all of it the word "bigchance" and a manager's spell key
 *  repeated on every shot he had nothing to do with. */
type Plots = {
  seasons: string[];
  shooters: string[];
  spells: { key: string; manager: string; start: string; matches: number }[];
  shots: number[][];
  faced: number[][];
  cuts: Record<
    string,
    {
      matches: number;
      positions: Node[];
      passes: Link[];
      passes_checked: number;
      passes_resolved: number;
    }
  >;
};

/** Which players a manager picked, and for how long. The RATING is not here
 *  on purpose: it depends on the weights the reader sets, so the build ships
 *  minutes and the page does the weighting. Move a slider on the players tab
 *  and the manager edge moves with it, which is right — it is their idea of
 *  a good player being tested against what the side produced. */
type Manager = {
  spell: string;
  team: string;
  manager: string;
  start: string;
  end: string;
  matches: number;
  seasons: string[];
  short: boolean;
  /** season -> "name|bucket" -> minutes */
  minutes: Record<string, Record<string, number>>;
};

const DATA = "/data/team/eng-premier-league";
const TEAM_TABS = ["squad", "formations", "data"] as const;

/** One result. d: date, o: opponent, h: 1 at home, gf/ga: goals, r: W/D/L. */
type Game = {
  d: string; o: string; h: number; gf: number; ga: number; r: "W" | "D" | "L";
};

const RESULT: Record<string, { bg: string; fg: string; word: string }> = {
  W: { bg: "#1a7f37", fg: "#ffffff", word: "won" },
  D: { bg: "#9aa3ab", fg: "#ffffff", word: "drew" },
  L: { bg: "#b3261e", fg: "#ffffff", word: "lost" },
};

/** The last five, most recent LAST — left to right is forwards in time,
 *  which is how anyone reads a row of results without being told. */
function Form({ games }: { games: Game[] }) {
  if (!games.length) return null;
  return (
    <span className="flex items-center gap-1" aria-label="recent form">
      {games.map((g) => {
        const r = RESULT[g.r];
        return (
          <span
            key={`${g.d}-${g.o}`}
            title={`${r.word} ${g.gf}-${g.ga} ${g.h ? "at home to" : "away to"} ${g.o}, ${g.d}`}
            className="num inline-flex h-[19px] w-[19px] items-center justify-center rounded-[5px] text-[11px] font-bold"
            style={{ background: r.bg, color: r.fg }}
          >
            {g.r}
          </span>
        );
      })}
    </span>
  );
}

/** [x, y, flags, season, spell, shooter] -> something with names on it.
 *  Bit order is fixed by the builder: goal, on target, big chance, set
 *  piece, penalty, header. */
function unpackShot(r: number[], shooters: string[]): Shot {
  return {
    x: r[0],
    y: r[1],
    goal: !!(r[2] & 1),
    target: !!(r[2] & 2),
    big: !!(r[2] & 4),
    setPiece: !!(r[2] & 8),
    head: !!(r[2] & 32),
    who: r[5] >= 0 ? (shooters[r[5]] ?? "") : "",
  };
}
const isPenalty = (r: number[]) => !!(r[2] & 16);

/** Same diverging ring as the tables: 50 is the middle of the league by
 *  construction, so the scale has a real midpoint and never a hue in it. */
function Ring({ v, label, hint }: { v: number; label: string; hint?: string }) {
  const R = 22;
  const C = 2 * Math.PI * R;
  const t = Math.max(-1, Math.min(1, (v - 50) / 30));
  const mid = [154, 163, 171];
  const to = t < 0 ? [179, 38, 30] : [26, 127, 55];
  const c = mid.map((m, i) => Math.round(m + (to[i] - m) * Math.abs(t)));
  return (
    <div className="flex flex-col items-center gap-1" title={hint}>
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={R} fill="none" stroke="#eef0f2" strokeWidth="5" />
        <circle
          cx="28"
          cy="28"
          r={R}
          fill="none"
          stroke={`rgb(${c[0]},${c[1]},${c[2]})`}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${(C * Math.max(0, Math.min(100, v))) / 100} ${C}`}
          transform="rotate(-90 28 28)"
        />
        <text
          x="28"
          y="28"
          textAnchor="middle"
          dominantBaseline="central"
          className="num"
          fontSize="15"
          fontWeight="600"
          fill="currentColor"
        >
          {v.toFixed(0)}
        </text>
      </svg>
      <span className="text-[11px] uppercase tracking-wider text-ink-3">{label}</span>
    </div>
  );
}

export function TeamPage({ slug, team }: { slug: string; team: string }) {
  return (
    <RatingsData>
      <Inner slug={slug} team={team} />
    </RatingsData>
  );
}

function Inner({ slug, team }: { slug: string; team: string }) {
  const { meta: pMeta, players, want, allWeights } = useRatings();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [clubs, setClubs] = useState<Row[]>([]);
  const [spells, setSpells] = useState<Row[]>([]);
  const [side, setSide] = useState<"with" | "against">("with");
  // This season by default: it is what a reader wants, and a club promoted
  // last summer has no pooled row at all, so "all seasons" shows them
  // nothing. Set once the meta names the current season.
  const [season, setSeason] = useState("");
  const [clubSeasons, setClubSeasons] = useState<Row[]>([]);
  const [plots, setPlots] = useState<Plots | null>(null);
  const [allSpells, setAllSpells] = useState<Row[]>([]);
  const [managers, setManagers] = useState<Manager[]>([]);
  /** A manager to set BESIDE the period, chosen rather than all of them at
   *  once. Drawing every spell in a row put Aston Villa's four matches of
   *  26/27 next to Emery's 118 across four seasons and invited the reader to
   *  compare them, which is not a comparison. Empty means the period alone. */
  const [withMgr, setWithMgr] = useState("");
  const [tab, setTab] = useTab("tab", TEAM_TABS);
  const [form, setForm] = useState<Record<string, Record<string, Game[]>>>({});

  useEffect(() => {
    Promise.all([
      fetch(`${DATA}/meta.json`).then((r) => r.json()),
      fetch(`${DATA}/club.json`).then((r) => r.json()),
      fetch(`${DATA}/spell.json`).then((r) => r.json()),
      fetch(`${DATA}/club_season.json`).then((r) => r.json()),
      fetch(`${DATA}/manager.json`).then((r) => (r.ok ? r.json() : [])),
      fetch(`${DATA}/form.json`).then((r) => (r.ok ? r.json() : {})),
    ])
      .then(([m, c, sp, cs, mg, fm]: [Meta, Row[], Row[], Row[], Manager[],
                                      Record<string, Record<string, Game[]>>]) => {
        setForm(fm);
        setMeta(m);
        setClubs(c);
        setAllSpells(sp);
        // EVERY spell in the league, not just this club's: the edge is a
        // rank against the other managers in the competition, so they all
        // have to be scored before this one can be placed among them.
        setManagers(mg);
        // By DATE. pandas groups alphabetically, so the last row was De
        // Zerbi rather than Hurzeler, and game ids cannot order a season.
        setSpells(
          sp
            .filter((r) => r.team === team)
            .sort((a, b) => String(a.start ?? "").localeCompare(String(b.start ?? ""))),
        );
        setClubSeasons(cs);
      })
      .catch(() => setMeta(null));
  }, [team]);

  /** The maps come in their own file, per club, because they are the only
   *  thing here that cannot be reduced to a number and they are the only
   *  thing a reader who does not open this page never pays for. */
  useEffect(() => {
    let live = true;
    fetch(`${DATA}/plots/${slug}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((p: Plots | null) => live && setPlots(p))
      .catch(() => live && setPlots(null));
    return () => {
      live = false;
    };
  }, [slug]);

  /** One period drives everything: the squad, the scores and the maps. */
  const pView = !season ? "" : season === "all" ? "total" : season;
  useEffect(() => {
    if (meta && !season) setSeason(meta.current_season);
  }, [meta, season]);

  useEffect(() => {
    if (pMeta && pView) want(pView);
  }, [pMeta, pView, want]);

  /** Every season this club's managers worked in. A spell can span three of
   *  them, and rating a player on a pooled four-year number would credit a
   *  manager for a version of him he never had. */
  useEffect(() => {
    if (!pMeta) return;
    const need = new Set<string>();
    for (const m of managers) for (const s of Object.keys(m.minutes)) need.add(s);
    for (const s of need) want(s);
  }, [pMeta, managers, want]);

  /** season -> "name|bucket" -> his percentile inside his own position that
   *  season, on the reader's weights. The same scorer the squad box uses. */
  const ratings = useMemo(() => {
    const out: Record<string, Map<string, number>> = {};
    const rel = pMeta?.reliability as never;
    const score = (p: Player) => scorePlayer(p, allWeights, rel);
    for (const [view, list] of Object.entries(players)) {
      if (!list || view === "total") continue;
      const byB: Record<string, Player[]> = {};
      for (const p of list) (byB[p.p] ??= []).push(p);
      const map = new Map<string, number>();
      for (const group of Object.values(byB)) {
        const sorted = group
          .map((p) => ({ p, v: score(p) }))
          .sort((a, b) => a.v - b.v);
        sorted.forEach((e, i) =>
          map.set(
            `${e.p.n}|${e.p.p}`,
            sorted.length > 1 ? (i / (sorted.length - 1)) * 100 : 50,
          ),
        );
      }
      out[view] = map;
    }
    return out;
  }, [players, allWeights, pMeta]);

  /** TEAM MENTAL IS THIS LIST. Every player percentiled inside his own
   *  position on the weights set on the players tab, then weighted by the
   *  minutes he played there. Change a slider over there and this moves. */
  const squad = useMemo(
    () => buildSquad(players[pView] ?? [], team, allWeights,
                     pMeta?.reliability as never),
    [players, pView, team, allWeights, pMeta],
  );

  /** The best eleven they could put out, against a real shape. The formation
   *  is chosen rather than assumed: whichever the squad scores highest in. */
  const xi = useMemo(() => {
    const all = players[pView] ?? [];
    if (!all.length) return null;
    const rel = pMeta?.reliability as never;
    const pct = new Map<Player, number>();
    const byB: Record<string, Player[]> = {};
    for (const p of all) (byB[p.p] ??= []).push(p);
    for (const list of Object.values(byB)) {
      const sorted = list
        .map((p) => ({ p, v: scorePlayer(p, allWeights, rel) }))
        .sort((a, b) => a.v - b.v);
      sorted.forEach((e, i) =>
        pct.set(e.p, sorted.length > 1 ? (i / (sorted.length - 1)) * 100 : 50),
      );
    }
    return bestXI(all, team, (p) => pct.get(p) ?? 50);
  }, [players, pView, team, allWeights, pMeta]);

  /** The same scorer the board uses. Reading `club.score` off the file gave
   *  every club a flat 50, because the score is derived from the weights and
   *  never stored. */
  const pool = useMemo(
    () => (season === "all" ? clubs : clubSeasons.filter((r) => r.season === season)),
    [season, clubs, clubSeasons],
  );
  const scores = useMemo(
    () =>
      meta ? scoreTeams(pool as TeamRow[], meta.metrics, meta.reliability) : new Map(),
    [pool, meta],
  );
  const club = pool.find((r) => r.team === team) ?? null;
  const mine = club ? scores.get(club as TeamRow) : undefined;

  /** The wedges are THE METRICS THE SCORE ACTUALLY USES, in phase order and
   *  weight order within a phase.
   *
   *  Drawn from every quality metric it was a third set pieces — four wedges
   *  out of twelve for the part of the game that carries ten points of the
   *  hundred, and the four least trustworthy numbers on the page besides.
   *  The picture said the set piece is a third of what a team is, which is
   *  not what the model thinks and not what anyone watching would say.
   *
   *  Percentiled inside the selected period, so a pizza for 25/26 ranks them
   *  against that season's league rather than against four years of it.
   */
  const slices = useMemo<Slice[]>(() => {
    if (!meta || !club) return [];
    const pct = percentiles(pool as TeamRow[], meta.metrics);
    const order = { with: 0, against: 1, set: 2 } as Record<string, number>;
    return meta.metrics
      .filter((m) => m.kind === "quality" && (PRESET[m.key] ?? 0) > 0)
      .sort(
        (a, b) =>
          (order[a.phase] ?? 9) - (order[b.phase] ?? 9) ||
          (PRESET[b.key] ?? 0) - (PRESET[a.key] ?? 0),
      )
      .map((m) => ({
        key: m.key,
        label: m.label,
        phase: m.phase,
        weight: PRESET[m.key],
        desc: m.desc,
        v: pct[m.key]?.get(club as TeamRow) ?? 50,
      }));
  }, [meta, club, pool]);

  /** Shots for the selected period. Penalties dropped here rather than in the
   *  builder so the count is still available if it is ever wanted. */
  const shotsFor = useMemo(() => {
    if (!plots) return { taken: [] as Shot[], faced: [] as Shot[] };
    const si = plots.seasons.indexOf(season);
    const pick = (rows: number[][]) =>
      rows
        .filter((r) => !isPenalty(r) && (season === "all" || r[3] === si))
        .map((r) => unpackShot(r, plots.shooters));
    return { taken: pick(plots.shots), faced: pick(plots.faced) };
  }, [plots, season]);

  const cut = plots?.cuts[season === "all" ? "all" : season] ?? null;

  /** Where this club sits in the league on each score, so a number on the
   *  page says "3rd of 20" rather than floating free. */
  const rankOf = (key: string, invert = false) => {
    const vals = pool
      .map((r) => r[key])
      .filter((v) => typeof v === "number") as number[];
    const mine = club?.[key];
    if (typeof mine !== "number" || !vals.length) return null;
    const better = vals.filter((v) => (invert ? v < mine : v > mine)).length;
    return { rank: better + 1, of: vals.length };
  };


  /** What a cell's number MEANS, in a sentence, when it is clicked. A heat
   *  map whose numbers need a legend to decode has only half worked. */
  const explain = (cell: string, v: number | undefined, where: string) => {
    if (v === undefined || Number.isNaN(v)) return `No data for the ${where}.`;
    if (side === "with") {
      const rank = v >= 80 ? "far more" : v >= 60 ? "more" : v >= 40 ? "about as much" : v >= 20 ? "less" : "far less";
      return `${team} have ${rank} of the ball in the ${where} than a typical side does there — ${v.toFixed(0)} out of 100 against the rest of the league. The comparison is against that cell alone, because every side has less of the ball in its own attacking third than in its own half.`;
    }
    return `${v.toFixed(2)} chances a match against ${team} begin in the ${where} — counted where the ball was played FROM, not where the shot was taken. High here means this is the route opponents use to get at them.`;
  };

  /** SQUAD VS RESULTS, per manager spell.
   *
   *  `squad` is the players he picked, each percentiled inside his own
   *  position on your weights and weighted by the minutes he gave him — so
   *  this measures SELECTION, not just who was on the books.
   *
   *  `expected` is what the league's own squad-to-points line says a squad
   *  that good should take. `surplus` is the rest.
   *
   *  What this is NOT is proof about the manager, and the first version of
   *  it was worse: collective score minus squad rating correlated 0.17 with
   *  points and put Brentford bottom of the league on 1.47 a game, because
   *  the collective score is nine-tenths open play and Brentford are not.
   *  This version repeats at 0.50 season to season, but it moves no more
   *  when a club changes manager (0.27) than when it keeps one (0.29), so
   *  it is a property of the club until a bigger sample says otherwise.
   *
   *  ABOVE THE EARLY RETURNS, with every other hook. Sitting below them it
   *  ran only once `meta` had arrived, so the second render called one more
   *  hook than the first and React refused the whole page.
   */
  const managerRows = useMemo(() => {
    if (!meta || !allSpells.length || !managers.length) return [];
    const byKey = new Map(allSpells.map((r) => [String(r.spell), r]));
    const squadOf = (m: Manager) => {
      let num = 0;
      let den = 0;
      for (const [season, mins] of Object.entries(m.minutes)) {
        const map = ratings[season];
        if (!map) continue;
        for (const [k, v] of Object.entries(mins)) {
          const r = map.get(k);
          if (r === undefined) continue;
          num += r * v;
          den += v;
        }
      }
      return den ? num / den : undefined;
    };
    const all = managers
      .map((m) => {
        const row = byKey.get(m.spell);
        const pts = typeof row?.pts === "number" ? row.pts : undefined;
        return { m, row, squad: squadOf(m), pts };
      })
      .filter((e) => e.squad !== undefined && e.pts !== undefined);
    // The line is fitted across the league's spells, so it moves with your
    // weights too. Short spells are excluded from the FIT but still get a
    // number: ten matches is thin, not meaningless.
    const fit = all.filter((e) => e.m.matches >= 20);
    let slope = 0;
    let icept = 0;
    if (fit.length > 4) {
      const xs = fit.map((e) => e.squad as number);
      const ys = fit.map((e) => e.pts as number);
      const mx = xs.reduce((a, b) => a + b, 0) / xs.length;
      const my = ys.reduce((a, b) => a + b, 0) / ys.length;
      const cov = xs.reduce((a, x, i) => a + (x - mx) * (ys[i] - my), 0);
      const varx = xs.reduce((a, x) => a + (x - mx) ** 2, 0);
      slope = varx ? cov / varx : 0;
      icept = my - slope * mx;
    }
    return all
      .filter((e) => e.m.team === team)
      .map((e) => {
        const expected = slope * (e.squad as number) + icept;
        return {
          ...e.m,
          squad: e.squad as number,
          pts: e.pts as number,
          expected,
          surplus: (e.pts as number) - expected,
        };
      })
      .sort((a, b) => a.start.localeCompare(b.start));
  }, [meta, allSpells, managers, ratings, team]);

  if (!meta) {
    return <p className="text-[13.5px] text-ink-2">Loading {team}…</p>;
  }
  if (!club) {
    // Promoted clubs have no pooled row — four matches is under the bar that
    // keeps one-season sides out of an all-time table. Say so rather than
    // spin on a "loading" that will never finish.
    return (
      <div>
        <Crumbs
          trail={[
            { href: "/ratings", label: "Ratings" },
            { href: "/ratings?tab=teams", label: "Teams" },
            { label: team },
          ]}
        />
        <h1 className="mt-2 font-display text-[26px]">{team}</h1>
        <p className="mt-3 max-w-2xl text-[13.5px] text-ink-2">
          Nothing to show for{" "}
          {season === "all" ? "every season pooled" : meta.season_labels[season] ?? season}.
          A club only promoted this summer has too few matches to appear in a
          multi-season table.
        </p>
        <label className="mt-4 flex w-fit items-center gap-2 text-[12.5px] text-ink-2">
          try
          <select
            value={season}
            onChange={(e) => setSeason(e.target.value)}
            className="rounded-md border border-line bg-card px-2 py-1"
          >
            <option value="all">All seasons</option>
            {meta.seasons.map((sn) => (
              <option key={sn} value={sn}>
                {meta.season_labels[sn]}
              </option>
            ))}
          </select>
        </label>
      </div>
    );
  }

  const cells = meta.grid.cells;
  const zoneVals = (row: Row) => {
    const out: Record<string, number | undefined> = {};
    for (const c of cells) {
      const v = row[side === "with" ? `z_${c}_n` : `zoc_${c}`];
      out[c] = typeof v === "number" ? v : undefined;
    }
    return out;
  };
  // One scale across every map on the page, so two managers of the same club
  // are comparable rather than each normalised to its own hottest cell.
  const conMax = Math.max(
    0.1,
    ...[club, ...spells].flatMap((r) =>
      cells.map((c) =>
        typeof r[`zoc_${c}`] === "number" ? (r[`zoc_${c}`] as number) : 0,
      ),
    ),
  );
  /** The man in charge NOW: the spell that ran latest. */
  const current = spells[spells.length - 1];
  const since =
    current && typeof current.start === "string" && current.start.length >= 7
      ? new Date(`${current.start}T00:00:00`).toLocaleDateString(undefined, {
          month: "short",
          year: "numeric",
        })
      : null;

  /** Where they sit in the CURRENT league table, by total points. */
  const leaguePos = (() => {
    if (!meta) return null;
    const cur = clubSeasons.filter((r) => r.season === meta.current_season);
    if (cur.length < 4) return null;
    const tot = (r: Row) =>
      (typeof r.pts === "number" ? r.pts : 0) * (Number(r.matches) || 0);
    const sorted = [...cur].sort((a, b) => tot(b) - tot(a));
    const i = sorted.findIndex((r) => r.team === team);
    return i < 0 ? null : { pos: i + 1, of: sorted.length };
  })();
  const quality = meta.metrics.filter((m) => m.kind === "quality");
  const pts = typeof club.pts === "number" ? club.pts : null;
  const ptsRank = rankOf("pts");
  /** What the period actually IS. Hardcoding "All seasons" over a map that
   *  follows the selector labelled Aston Villa's four matches of 26/27 as
   *  four years of football. */
  const periodLabel =
    season === "all" ? "All seasons" : meta.season_labels[season] ?? season;
  const compareSpell = spells.find((sp) => String(sp.spell) === withMgr) ?? null;
  /** The last five of the selected period. On "all seasons" that is the tail
   *  of the current one — nobody means four years ago by form. */
  const recent = (form[team]?.[season === "all" ? "all" : season] ?? []).slice(-5);

  return (
    <div>
      <Crumbs
        trail={[
          { href: "/ratings", label: "Ratings" },
          { href: "/ratings?tab=teams", label: "Teams" },
          { label: team },
        ]}
      />

      <div className="mt-2 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-line pb-5">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <Crest src={meta.crests?.[team] ?? ""} alt={team} size={56} />
          <div>
            <h1 className="font-display text-[28px] leading-tight tracking-[0.01em]">
              {team}
            </h1>
            <p className="mt-0.5 text-[13px] text-ink-2">
              {leaguePos && (
                <>
                  <span className="font-semibold text-ink">
                    {leaguePos.pos}
                    {["th", "st", "nd", "rd"][
                      leaguePos.pos % 100 >= 11 && leaguePos.pos % 100 <= 13
                        ? 0
                        : Math.min(leaguePos.pos % 10, 4) % 4
                    ]}
                  </span>{" "}
                  in the league now ·{" "}
                </>
              )}
              {current ? String(current.manager) : "—"}
              {since && <span className="text-ink-3"> since {since}</span>} ·{" "}
              <span className="num">{club.matches}</span> matches
              {pts !== null && (
                <>
                  {" "}
                  · <span className="num">{pts.toFixed(2)}</span> pts a match
                  {ptsRank && (
                    <span className="text-ink-3">
                      {" "}
                      ({ptsRank.rank} of {ptsRank.of})
                    </span>
                  )}
                </>
              )}
            </p>
            {recent.length > 0 && (
              <p className="mt-1.5 flex items-center gap-2 text-[12px] text-ink-3">
                <span className="uppercase tracking-wider">form</span>
                <Form games={recent} />
                <span className="num">
                  {recent.filter((g) => g.r === "W").length}W{" "}
                  {recent.filter((g) => g.r === "D").length}D{" "}
                  {recent.filter((g) => g.r === "L").length}L
                </span>
              </p>
            )}
          </div>
        </div>
        {/* The period selector and both rings: wrapping and a tighter gap on
            a phone, where 265px of controls was the widest thing in the
            header and pushed the page off its own right edge. */}
        <div className="flex flex-wrap items-end gap-x-5 gap-y-3 sm:gap-x-6">
          <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
            period
            <select
              value={season}
              onChange={(e) => setSeason(e.target.value)}
              className="rounded-md border border-line bg-card px-2 py-1"
              title="Drives everything on this page — the squad, the scores and the maps."
            >
              <option value="all">All seasons</option>
              {meta.seasons.map((sn) => (
                <option key={sn} value={sn}>
                  {meta.season_labels[sn]}
                </option>
              ))}
            </select>
          </label>
          <Ring
            v={mine?.score ?? 50}
            label="Overall"
            hint="What the collective produces, from team events, opponent-adjusted."
          />
          <Ring
            v={squad.rating}
            label="Squad"
            hint="Team mental: the players they have, on your weights from the players tab."
          />
        </div>
      </div>

      {/* Three tabs rather than eight sections down a page. Everything that
          answers "who have they got" is in one, "how do they set up" in the
          next, and the numbers in the third — and the header above stays put,
          so the period selector and both rings are always in reach. */}
      <div className="mt-5">
        <Tabs
          tabs={TEAM_TABS}
          value={tab}
          onChange={setTab}
          labels={{ squad: "Squad", formations: "Formations", data: "Data hub" }}
        />
      </div>

      {/* ----------------------------------------------------- best eleven */}
      {tab === "squad" && !xi && (players[pView] ?? []).length > 0 && (
        <p className="mt-7 max-w-2xl text-[12.5px] text-ink-3">
          Not enough players with minutes in{" "}
          {season === "all" ? "this period" : meta.season_labels[season]} to
          field an eleven.
        </p>
      )}
      {/* The eleven on one side, the squad it came out of on the other —
          they answer each other, and stacked they were two scrolls apart. */}
      {tab === "squad" && (
      <div className="mt-7 grid items-start gap-9 xl:grid-cols-[360px_minmax(0,1fr)]">

      {xi && (
        <section>
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="text-[16px] font-semibold">Best eleven</h2>
            {/* The match page shows a DIFFERENT eleven from the same squad,
                and it is not a contradiction: this is who rates highest,
                that is who actually played. Saying so is cheaper than
                forcing them to agree — and the gap between them, where the
                ratings and the manager disagree, is the interesting part. */}
            <span className="text-[11.5px] text-ink-3">
              strongest available, by rating
            </span>
            <span className="rounded-full border border-line bg-card px-2.5 py-0.5 text-[12px] font-medium text-ink-2">
              {xi.formation}
            </span>
            <span className="num text-[12.5px] text-ink-3">
              averages {xi.rating.toFixed(0)}
            </span>
          </div>
          <div className="mt-3">
            <BestXI xi={xi} width={340} />
          </div>
          <p className="mt-2.5 text-[12px] leading-relaxed text-ink-2">
            The strongest side this squad can field, on your weights.{" "}
            <strong className="font-semibold">
              The shape is an output, not an assumption
            </strong>{" "}
            — five formations are filled and the one the players score highest
            in wins, so a club with two good wing-backs comes out in a back
            three because that is what it has. Every slot must be filled by
            someone who plays there, which is the difference from a
            leaderboard: the eleven best-rated players at most clubs are four
            centre-backs and no striker.
          </p>
          <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
            Picked from players with at least{" "}
            <span className="num">{xi.minShare ?? 0}%</span> of the
            period&apos;s minutes in the role.
            {(xi.minShare ?? 0) < 20 && (
              <>
                {" "}
                <span className="text-ink-2">
                  The bar had to drop this low to field eleven at all, so read
                  the back of this side as thin evidence.
                </span>
              </>
            )}
            {xi.unfilled > 0 && (
              <>
                {" "}
                <span className="text-bad">
                  {xi.unfilled} slot{xi.unfilled > 1 ? "s" : ""} could not be
                  filled in any shape
                </span>{" "}
                — too few players with enough minutes in this period.
              </>
            )}
          </p>
        </section>
      )}

      {/* ------------------------------------------------------ the squad */}
      <section>
        <h2 className="text-[16px] font-semibold">The squad</h2>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          Team mental <em>is</em> this list — every player&apos;s percentile
          within his own position, weighted by the minutes he played there, on
          the weights you set on the players tab. Their softest position is{" "}
          <strong className="font-semibold">
            {squad.weak ? posLabel(squad.weak.bucket).toLowerCase() : "—"}
            {squad.weak?.score !== undefined
              ? ` at ${squad.weak.score.toFixed(0)}`
              : ""}
          </strong>{" "}
          — and only positions they actually field count, because a club that
          never picks a wing-back has a shape rather than a hole.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {squad.byBucket.map((g) => {
            const weak = g.bucket === squad.weak?.bucket;
            return (
              <div
                key={g.bucket}
                className={`rounded-lg border p-3 ${
                  weak ? "border-bad/40 bg-[#fdf6f5]" : "border-line bg-card"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span
                    className="text-[12px] font-semibold uppercase tracking-wider text-ink-2"
                    title={posLabel(g.bucket)}
                  >
                    {posShort(g.bucket)}
                    {weak && (
                      <span className="ml-1.5 text-[10px] normal-case text-bad">
                        weak spot
                      </span>
                    )}
                  </span>
                  <span className="num text-[13px] font-semibold">
                    {g.score?.toFixed(0) ?? "—"}
                  </span>
                </div>
                {/* The two numbers had nothing saying what they were. A
                    header row costs one line per card and removes the
                    guess. */}
                <div className="mt-1.5 flex items-baseline justify-between gap-2 border-b border-line pb-1 text-[10px] uppercase tracking-wider text-ink-3">
                  <span>player</span>
                  <span className="shrink-0">
                    <span title="His percentile against every player in this position in the league, on your weights.">
                      rating
                    </span>
                    <span className="ml-2" title="Minutes he played in this position in the selected period.">
                      mins
                    </span>
                  </span>
                </div>
                {g.players.slice(0, 5).map((e) => (
                  <div
                    key={e.p.n}
                    className="mt-1 flex items-baseline justify-between gap-2"
                  >
                    <span className="truncate text-[12.5px]">{e.p.n}</span>
                    <span className="num shrink-0 text-[11.5px] text-ink-3">
                      <span
                        className="font-semibold text-ink-2"
                        title={`${e.v.toFixed(0)} of 100 against every ${posShort(g.bucket)} in the league`}
                      >
                        {e.v.toFixed(0)}
                      </span>
                      <span className="ml-2" title="minutes in this position">
                        {e.p.m.toLocaleString()}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </section>
      </div>
      )}

      {/* Zones and the pass network SIDE BY SIDE: both answer "where do
          they play", one as territory and one as a shape, and reading one
          under the other means holding the first in your head. Two columns
          from 1280px, stacked below it. */}
      {tab === "formations" && (
      <div className="mt-8 grid items-start gap-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
      <section>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[16px] font-semibold">Zones</h2>
          {(
            [
              ["with", "With the ball"],
              ["against", "Against the ball"],
            ] as const
          ).map(([k, lab]) => (
            <button
              key={k}
              onClick={() => setSide(k)}
              className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium transition-colors ${
                side === k
                  ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                  : "border-line bg-card text-ink-2 hover:border-ink-3"
              }`}
            >
              {lab}
            </button>
          ))}
          <span className="ml-auto">
            <ZoneLegend
              label={
                side === "with"
                  ? "share of the ball there, against a typical side"
                  : "chances against them that started there, per match"
              }
            />
          </span>
        </div>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          {side === "with"
            ? "How much of the ball they have in each part of the pitch, measured against what a typical side manages THERE. Your attacking centre is the opponent's defensive centre, where they have it while playing out, so a flat midpoint would call every side in the league weak in its own attacking third."
            : "Where the chances against them BEGIN — the cell the ball was played from, not where the shot was hit. Mapping where shots are taken makes every side in the league red in front of its own goalkeeper, which is true and tells you nothing; this says where they are actually got at. Opta links 72% of shots back to the pass or carry that made them."}
        </p>
        <div className="mt-4 flex flex-wrap items-start gap-6 sm:gap-8">
          <PitchZones
            values={zoneVals(club)}
            title={periodLabel}
            subtitle={`${club.matches} matches`}
            width={260}
            lo={0}
            hi={side === "with" ? 100 : conMax}
            decimals={side === "with" ? 0 : 2}
            explain={explain}
          />
          {spells.length > 0 && (
            <div className="min-w-0 max-w-full">
              {/* A native select sizes itself to its WIDEST option, and these
                  options are full legal names — "Vítor Manuel de Oliveira
                  Lopes Pereira (38)" is wider than a 375px phone. A flex item
                  will not shrink below that on its own (`min-width: auto`), so
                  the label wraps and the select is allowed to give way; the
                  chosen name still shows in full because the box is as wide as
                  the row, and the options are a native dropdown either way. */}
              <label className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] text-ink-2">
                compare with
                <select
                  value={withMgr}
                  onChange={(e) => setWithMgr(e.target.value)}
                  className="min-w-0 max-w-full flex-1 truncate rounded-md border border-line bg-card px-2 py-1 sm:flex-none"
                >
                  <option value="">nobody</option>
                  {spells.map((sp) => (
                    <option key={String(sp.spell)} value={String(sp.spell)}>
                      {String(sp.manager)} ({sp.matches})
                    </option>
                  ))}
                </select>
              </label>
              {compareSpell ? (
                <PitchZones
                  values={zoneVals(compareSpell)}
                  title={String(compareSpell.manager)}
                  subtitle={`${compareSpell.matches} matches, his whole spell`}
                  width={260}
                  lo={0}
                  hi={side === "with" ? 100 : conMax}
                  decimals={side === "with" ? 0 : 2}
                  explain={explain}
                />
              ) : (
                <p className="max-w-[260px] text-[12px] leading-relaxed text-ink-3">
                  A manager&apos;s map covers his whole spell, which may run
                  across several seasons — so it is a different span from the
                  period on the left, not a like-for-like second opinion.
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-[16px] font-semibold">
          Average positions and passing
        </h2>
        <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">
          Where each player had the ball on average, and who he played it to.
          Averaged over the whole period rather than one match, so this is a
          habit and not an afternoon — a player moved to a new job in January
          sits between the two he did.
        </p>
        {!plots ? (
          <p className="mt-3 text-[12.5px] text-ink-3">Loading…</p>
        ) : !cut ? (
          <p className="mt-3 text-[12.5px] text-ink-3">
            Too few matches in{" "}
            {season === "all" ? "this period" : meta.season_labels[season]} to
            draw a network — four is the floor, below which the lines are one
            team selection rather than a pattern.
          </p>
        ) : (
          <div className="mt-4">
            <PassNetwork
              nodes={cut.positions}
              links={cut.passes}
              resolved={
                cut.passes_checked
                  ? cut.passes_resolved / cut.passes_checked
                  : undefined
              }
              title={
                season === "all" ? "All seasons" : meta.season_labels[season]
              }
              subtitle={`${cut.matches} matches`}
              width={340}
            />
          </div>
        )}
      </section>
      </div>
      )}

      {/* ------------------------------------------------- the pizza chart */}
      {tab === "data" && (
      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Where they rank</h2>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          The ten things the score is actually built from, as percentiles
          against the rest of the league in the same period, and in the order
          they carry weight. Longer is always better — conceding metrics are
          flipped, so a long wedge there means they concede few. Nothing here
          is style: how a side plays is on the table, not in this picture.
        </p>
        <div className="mt-3 flex flex-wrap items-start gap-6 xl:gap-10">
          <div className="min-w-0">
            <Pizza
              slices={slices}
              size={680}
              label={`${team} percentiles, ${periodLabel}`}
            />
            <div className="mt-1">
              <PizzaLegend phases={["with", "against", "set"]} />
            </div>
          </div>
          <div className="min-w-[240px] max-w-sm text-[12.5px] leading-relaxed text-ink-2">
            <p>
              <strong className="font-semibold">{periodLabel}</strong>, against
              the {pool.length} clubs in the league over the same span. The
              dashed rings are the 25th and 75th percentiles and the solid one
              is the median, so a wedge past the solid ring is better than half
              the league.
            </p>
            <p className="mt-2 text-ink-3">
              Two set-piece wedges rather than four, because set pieces carry
              ten points of the hundred and a chart that gave them a third of
              the circle was saying something the model does not. A side gets
              about eleven set-piece big chances in half a season — too few to
              tell a good routine from a good week — so creating from them is
              left out entirely and only the two that survive both gates are
              drawn.
            </p>
          </div>
        </div>
      </section>
      )}

      {/* ------------------------------------------------------- shot maps */}
      {tab === "data" && (
      <section className="mt-8">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[16px] font-semibold">Shots</h2>
          <span className="ml-auto">
            <ShotLegend />
          </span>
        </div>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          Where every shot was struck from, both ends, drawn from the halfway
          line up. The two maps are in the same frame — the right of one
          picture is the right of the other — so a side that shoots from the
          left and is shot at from the left is visible at a glance.
        </p>
        {!plots ? (
          <p className="mt-3 text-[12.5px] text-ink-3">Loading the maps…</p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-6 sm:gap-8">
            <ShotMap
              shots={shotsFor.taken}
              title="Shots taken"
              subtitle={
                season === "all" ? "all seasons" : meta.season_labels[season]
              }
              width={260}
            />
            <ShotMap
              shots={shotsFor.faced}
              title="Shots faced"
              subtitle="mirrored into their own half"
              width={260}
              faced
            />
          </div>
        )}
      </section>
      )}

      {/* --------------------------------------------- squad vs results */}
      {tab === "squad" && managerRows.length > 0 && (
        <section className="mt-8">
          <h2 className="text-[16px] font-semibold">Squad against results</h2>
          <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
            The players each manager actually picked — percentiled inside
            their own positions on your weights, then weighted by the minutes
            he gave them — set against what the side went on to take. The
            league&apos;s own squad-to-points line says what a squad that good
            is worth; the surplus is the rest.
          </p>
          {/* phone: one card per spell. The surplus is the column the whole
              section is about and it is the last of six, so on a narrow
              screen it is the one a sideways scroll hides. Here it sits
              beside the name and the four numbers it came from are under it,
              each still labelled. */}
          <ul className="mt-3 space-y-2 sm:hidden">
            {managerRows.map((r) => (
              <li
                key={r.spell}
                className="rounded-xl border border-line bg-card p-3"
              >
                <div className="flex items-baseline justify-between gap-2">
                  {/* flex, not a bare span: `truncate` needs a block to
                      measure against, and the badge has to survive the
                      name being cut rather than be cut with it. */}
                  <span className="flex min-w-0 items-baseline text-[14px] font-medium">
                    <span className="truncate">{r.manager}</span>
                    {r.short && (
                      <span className="ml-1.5 shrink-0 whitespace-nowrap text-[10.5px] font-normal text-ink-3">
                        short spell
                      </span>
                    )}
                  </span>
                  <span
                    className={`num shrink-0 text-[15px] font-semibold ${
                      r.surplus > 0.12
                        ? "text-good"
                        : r.surplus < -0.12
                          ? "text-bad"
                          : "text-ink-3"
                    }`}
                    title="Points a match above or below what the league's squad-to-points line expects."
                  >
                    {r.surplus > 0 ? "+" : ""}
                    {r.surplus.toFixed(2)}
                  </span>
                </div>
                <dl className="mt-2 grid grid-cols-4 gap-x-2 border-t border-line pt-2 text-[11.5px]">
                  {[
                    { k: "matches", v: String(r.matches) },
                    { k: "squad", v: r.squad.toFixed(0) },
                    { k: "expected", v: r.expected.toFixed(2) },
                    { k: "actual", v: r.pts.toFixed(2) },
                  ].map((c) => (
                    <div key={c.k}>
                      <dt className="text-ink-3">{c.k}</dt>
                      <dd className="num mt-0.5 text-[13px]">{c.v}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>

          <div className="mt-3 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-3 text-left font-semibold">Manager</th>
                  <th className="px-2 py-2 text-center font-semibold">Mt</th>
                  <th className="px-2 py-2 text-center font-semibold" title="The players he picked, rated on your weights.">Squad</th>
                  <th className="px-2 py-2 text-center font-semibold" title="What the league's squad-to-points line expects from a squad that good.">Expected</th>
                  <th className="px-2 py-2 text-center font-semibold">Actual</th>
                  <th className="px-2 py-2 text-center font-semibold">Surplus</th>
                </tr>
              </thead>
              <tbody>
                {managerRows.map((r) => (
                  <tr key={r.spell} className="border-t border-line">
                    <td className="whitespace-nowrap py-2 pl-4 pr-3 font-medium">
                      {r.manager}
                      {r.short && (
                        <span className="ml-1.5 text-[10.5px] font-normal text-ink-3">
                          short spell
                        </span>
                      )}
                    </td>
                    <td className="num px-2 py-2 text-center text-ink-3">
                      {r.matches}
                    </td>
                    <td className="num px-2 py-2 text-center">
                      {r.squad.toFixed(0)}
                    </td>
                    <td className="num px-2 py-2 text-center text-ink-3">
                      {r.expected.toFixed(2)}
                    </td>
                    <td className="num px-2 py-2 text-center font-medium">
                      {r.pts.toFixed(2)}
                    </td>
                    <td
                      className={`num px-2 py-2 text-center font-semibold ${
                        r.surplus > 0.12
                          ? "text-good"
                          : r.surplus < -0.12
                            ? "text-bad"
                            : "text-ink-3"
                      }`}
                    >
                      {r.surplus > 0 ? "+" : ""}
                      {r.surplus.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-ink-3">
            <strong className="font-semibold text-ink-2">
              Read this as a property of the club, not a verdict on the man.
            </strong>{" "}
            The surplus repeats at 0.50 from one season to the next, so it is
            measuring something real — but it moves no more when a club
            changes manager (0.27) than when it keeps one (0.29). Twelve
            manager changes in four seasons of one league is too thin to
            separate the two, and until it is, calling this a manager&apos;s
            edge would be naming a cause we have not shown.
          </p>
        </section>
      )}

      {/* --------------------------------------------------- by manager */}
      {tab === "data" && spells.length > 1 && (
        <section className="mt-8">
          <h2 className="text-[16px] font-semibold">By manager</h2>
          <p className="mt-1 max-w-3xl text-[12.5px] text-ink-2">
            In the order they held the job. Every number opponent-adjusted, so
            a manager is not flattered by an easy run of fixtures.
          </p>
          {/* phone: one card per spell, the metrics as a two-column list.
              This table is four columns plus EVERY quality metric — a dozen
              of them — so it is the widest thing on the page by some way.
              Nothing is dropped: every metric that has a column has a row
              here, with the same opponent-adjusted number in it. */}
          <ul className="mt-3 space-y-2 sm:hidden">
            {spells.map((sp) => (
              <li
                key={String(sp.spell)}
                className="rounded-xl border border-line bg-card p-3"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-[14px] font-medium">
                    {String(sp.manager)}
                  </span>
                  <span className="num shrink-0 text-[11.5px] text-ink-3">
                    from {String(sp.start ?? "").slice(0, 7)} ·{" "}
                    {String(sp.matches)} mt
                  </span>
                </div>
                <div className="num mt-1 text-[12.5px]">
                  <span className="text-ink-3">pts a match </span>
                  <span className="font-semibold">
                    {typeof sp.pts === "number" ? sp.pts.toFixed(2) : "—"}
                  </span>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-line pt-2">
                  {quality.map((m) => {
                    const v = sp[`${m.key}_adj`] ?? sp[m.key];
                    return (
                      <div
                        key={m.key}
                        className="flex min-w-0 items-baseline justify-between gap-2"
                        title={m.desc}
                      >
                        <dt className="min-w-0 truncate text-[11.5px] text-ink-2">
                          {m.label}
                        </dt>
                        <dd className="num shrink-0 text-[12px]">
                          {typeof v === "number" ? v.toFixed(2) : "—"}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </li>
            ))}
          </ul>

          <div className="mt-3 hidden overflow-x-auto rounded-xl border border-line bg-card sm:block">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 pl-4 pr-3 text-left font-semibold">Manager</th>
                  <th className="px-2 py-2 text-left font-semibold">From</th>
                  <th className="px-2 py-2 text-center font-semibold">Mt</th>
                  <th className="px-2 py-2 text-center font-semibold">Pts</th>
                  {quality.map((m) => (
                    <th
                      key={m.key}
                      className="px-2 py-2 text-center font-semibold"
                      title={m.desc}
                    >
                      {m.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {spells.map((sp) => (
                  <tr key={String(sp.spell)} className="border-t border-line">
                    <td className="whitespace-nowrap py-2 pl-4 pr-3 font-medium">
                      {String(sp.manager)}
                    </td>
                    <td className="num whitespace-nowrap px-2 py-2 text-left text-[12px] text-ink-3">
                      {String(sp.start ?? "").slice(0, 7)}
                    </td>
                    <td className="num px-2 py-2 text-center text-ink-3">
                      {sp.matches}
                    </td>
                    <td className="num px-2 py-2 text-center font-medium">
                      {typeof sp.pts === "number" ? sp.pts.toFixed(2) : "—"}
                    </td>
                    {quality.map((m) => {
                      const v = sp[`${m.key}_adj`] ?? sp[m.key];
                      return (
                        <td key={m.key} className="num px-2 py-2 text-center">
                          {typeof v === "number" ? v.toFixed(2) : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
