"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Crest } from "../components/Crest";
import { crestFor, useCrests } from "./TeamHead";
import { Crumbs } from "../components/Crumbs";
import { Called } from "./Called";
import { SideXI } from "./SideXI";
import { ZonePitch } from "./ZonePitch";

/** Which half of the zone question is on screen.
 *  matchup  what should happen when these two meet (attack x leak)
 *  attack   where this side creates, against anyone
 *  defend   where this side is got at, by anyone */
type Phase = "matchup" | "attack" | "defend";

const PHASES: { key: Phase; label: string; hint: string }[] = [
  { key: "matchup", label: "Matchup",
    hint: "Their attack against this opponent's defence — what should happen on the day" },
  { key: "attack", label: "Attacking phase",
    hint: "Where this side creates its chances, regardless of opponent" },
  { key: "defend", label: "Defensive phase",
    hint: "Where this side concedes chances from, regardless of opponent" },
];
import { MatchPasses } from "./MatchPasses";
import { MatchShots } from "./MatchShots";
import type { RoundData } from "@/lib/data";
import { posLabel, posShort } from "../lib/positions";
import { matchTeam } from "../lib/teamName";
import { buildSquad, type Squad } from "../lib/squad";
import { RatingsData, useRatings } from "../ratings/RatingsData";
import { PRESET, type TeamRow, percentiles, scoreTeams } from "../ratings/teamScore";

/** One side against another, zone by zone.
 *
 *  THE WHOLE THING TURNS ON ONE FACT: the fifteen cells are stored in each
 *  team's OWN frame, attacking upwards. Cell 0 is your defensive right wing
 *  and cell 14 is your attacking left wing, so the same patch of grass is
 *  cell j for one side and cell 14 - j for the other — a 180 degree turn,
 *  which flips the third AND the flank. Forget the flank half and every map
 *  on the page is mirrored: a side that is got at down its left is drawn
 *  leaking down its right, and it looks plausible.
 *
 *  Two maps, one per phase, because "who wins the left wing" has no answer
 *  that does not say who has the ball. Each is drawn in the frame of the
 *  side ATTACKING in it, so up the picture is always forward for whoever is
 *  on the ball.
 *
 *  What a cell holds is an EDGE, not a rate: how much this attack uses that
 *  zone, against how much that defence leaks from it, both percentiled
 *  across the league in the same period. 50 is neutral.
 */

const DATA = "/data/team/eng-premier-league";

/** The process Elo: a log-multiplier on chances, carried continuously across
 *  seasons and updated on what each side CREATED rather than on results. */
type Elo = {
  params: { k: number; home_adv: number; conv: number; rho: number };
  table: { team: string; attack: number; defence: number; rating: number }[];
};

type Absent = {
  player: string; reason: string; status: string;
  bucket: string | null; rating: number | null; minutes: number | null;
};
type Injuries = {
  rated_on: string;
  teams: Record<string, {
    fixture: string; date: string; out: Absent[];
    n_out: number; n_doubt: number; rated: number;
  }>;
};


const MAX_GOALS = 8;
const fact = (n: number) => {
  let f = 1;
  for (let i = 2; i <= n; i++) f *= i;
  return f;
};

/** Dixon-Coles: a plain Poisson is wrong about football in exactly four
 *  places — 0-0, 1-0, 0-1 and 1-1 — and this is the correction for them. */
function tau(h: number, a: number, lh: number, la: number, rho: number) {
  if (h === 0 && a === 0) return 1 - lh * la * rho;
  if (h === 0 && a === 1) return 1 + lh * rho;
  if (h === 1 && a === 0) return 1 + la * rho;
  if (h === 1 && a === 1) return 1 - rho;
  return 1;
}

/** The scoreline grid, and everything read off it. */
function project(lh: number, la: number, rho: number) {
  const ph = Array.from({ length: MAX_GOALS + 1 },
    (_, i) => (Math.exp(-lh) * lh ** i) / fact(i));
  const pa = Array.from({ length: MAX_GOALS + 1 },
    (_, i) => (Math.exp(-la) * la ** i) / fact(i));
  const g: number[][] = ph.map((x, h) =>
    pa.map((y, a) => x * y * (h < 2 && a < 2 ? tau(h, a, lh, la, rho) : 1)));
  const total = g.flat().reduce((s, v) => s + v, 0) || 1;
  let home = 0, draw = 0, away = 0;
  const lines: { h: number; a: number; p: number }[] = [];
  g.forEach((row, h) => row.forEach((v, a) => {
    const p = v / total;
    if (h > a) home += p; else if (h === a) draw += p; else away += p;
    lines.push({ h, a, p });
  }));
  lines.sort((x, y) => y.p - x.p);
  return { home, draw, away, lines: lines.slice(0, 4), lh, la };
}
type Row = { team: string; matches: number } & Record<string, number | string>;
type Metric = {
  key: string; label: string; phase: string; kind: string;
  unit: string; invert: boolean; desc: string;
};
type Meta = {
  league: string;
  crests: Record<string, string>;
  current_season: string;
  seasons: string[];
  season_labels: Record<string, string>;
  grid: { cells: string[] };
  metrics: Metric[];
  reliability: Record<string, { rho?: number; predicts?: number }>;
};

export function VersusPage({ round }: { round: RoundData | null }) {
  return (
    <RatingsData>
      <Inner round={round} />
    </RatingsData>
  );
}

/** The fixture this pair IS, if the coming round has one.
 *
 *  🐛 MATCHED THROUGH THE NAME RESOLVER, not on equality. The round export
 *  and the team layer come from different feeds and disagree on seven of
 *  twenty clubs in both directions — "Coventry City" against "Coventry",
 *  "Nottingham" against "Nottingham Forest", "Manchester Utd" against "Man
 *  Utd". On equality alone four fixtures in ten found their prediction and
 *  the other six silently showed none. */
function fixtureFor(round: RoundData | null, home: string, away: string) {
  if (!round || !home || !away) return null;
  for (const [league, data] of Object.entries(round.leagues)) {
    const names = data.fixtures.flatMap((x) => [x.home, x.away]);
    const h = matchTeam(home, names);
    const a = matchTeam(away, names);
    if (!h || !a) continue;
    const f = data.fixtures.find((x) => x.home === h && x.away === a);
    if (f) return { f, league };
  }
  return null;
}

function Inner({ round }: { round: RoundData | null }) {
  const params = useSearchParams();
  const { meta: pMeta, players, want, allWeights } = useRatings();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [clubSeasons, setClubSeasons] = useState<Row[]>([]);
  const [clubs, setClubs] = useState<Row[]>([]);
  const [season, setSeason] = useState("");
  /** SEEDED FROM THE URL, not synced to it. A fixture link arrives with a
   *  pair; after that the pickers belong to whoever is looking, and writing
   *  their choices back into the address bar would fight them every time
   *  they changed one. */
  const [home, setHome] = useState(() => params.get("home") ?? "");
  const [away, setAway] = useState(() => params.get("away") ?? "");
  const [elo, setElo] = useState<Elo | null>(null);
  /** ONE PHASE PER CARD. A single toggle for both made the only question
   *  worth asking impossible: "their attack against this defence" needs one
   *  side ATTACKING and the other DEFENDING, and a shared control can never
   *  show that pair. Each card now owns its own. */
  const [phaseH, setPhaseH] = useState<Phase>("matchup");
  const [phaseA, setPhaseA] = useState<Phase>("matchup");
  const [inj, setInj] = useState<Injuries | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${DATA}/meta.json`).then((r) => r.json()),
      fetch(`${DATA}/club.json`).then((r) => r.json()),
      fetch(`${DATA}/club_season.json`).then((r) => r.json()),
      fetch(`${DATA}/elo.json`).then((r) => (r.ok ? r.json() : null)),
      fetch(`${DATA}/injuries.json`).then((r) => (r.ok ? r.json() : null)),
    ])
      .then(([m, c, cs, e, i]: [Meta, Row[], Row[], Elo | null, Injuries | null]) => {
        setMeta(m);
        setClubs(c);
        setClubSeasons(cs);
        setElo(e);
        setInj(i);
        setSeason(m.current_season);
      })
      .catch(() => setMeta(null));
  }, []);

  const pView = !season ? "" : season === "all" ? "total" : season;
  /** The season the EVENT payloads are keyed by. "All seasons" is a real
   *  option for the tables, which hold a row per club per season, and a
   *  meaningless one for the pass and shot files, which are written per
   *  season — so the pitches fall back to the current one rather than
   *  asking for a file called "total". */
  const eventSeason =
    !season || season === "all" ? meta?.current_season ?? "" : season;
  useEffect(() => {
    if (pMeta && pView) want(pView);
  }, [pMeta, pView, want]);

  const pool = useMemo(
    () => (season === "all" ? clubs : clubSeasons.filter((r) => r.season === season)),
    [season, clubs, clubSeasons],
  );

  /** Whoever is in the league in this period, alphabetically. */
  const teams = useMemo(
    () => [...new Set(pool.map((r) => String(r.team)))].sort(),
    [pool],
  );
  useEffect(() => {
    if (!teams.length) return;
    // A fixture link arrives spelling clubs the way the round export does,
    // which is not how this table spells them. Translate before falling
    // back, or every link with a renamed club lands on Arsenal.
    if (!teams.includes(home)) setHome(matchTeam(home, teams) ?? teams[0]);
    if (!teams.includes(away)) setAway(matchTeam(away, teams) ?? teams[1] ?? teams[0]);
  }, [teams, home, away]);

  const scores = useMemo(
    () => (meta ? scoreTeams(pool as TeamRow[], meta.metrics, meta.reliability) : new Map()),
    [pool, meta],
  );
  const pct = useMemo(
    () => (meta ? percentiles(pool as TeamRow[], meta.metrics) : {}),
    [pool, meta],
  );

  /** The league's average chance origin per cell — the baseline an attack
   *  and a defence are both measured against. */
  const zoneMean = useMemo(() => {
    const out: Record<string, number> = {};
    if (!meta || !pool.length) return out;
    for (const cell of meta.grid.cells) {
      const vals = pool
        .map((r) => r[`zo_${cell}`])
        .filter((v) => typeof v === "number") as number[];
      out[cell] = vals.length
        ? vals.reduce((a, b) => a + b, 0) / vals.length
        : 0;
    }
    return out;
  }, [meta, pool]);

  const squads = useMemo(() => {
    const all = players[pView] ?? [];
    const rel = pMeta?.reliability as never;
    const of = (t: string) => (t ? buildSquad(all, t, allWeights, rel) : null);
    return { home: of(home), away: of(away) };
  }, [players, pView, home, away, allWeights, pMeta]);

  const rowOf = (t: string) => pool.find((r) => r.team === t) ?? null;
  const hRow = rowOf(home);
  const aRow = rowOf(away);

  /** EXPECTED CHANCES A MATCH from each cell. `attack` is the side on the
   *  ball; the map is drawn in ITS frame, so cell j of the attacker meets
   *  cell 14-j of the defender.
   *
   *      expected = attack's rate there x defence's rate conceded there
   *                 / the league's average there
   *
   *  The attack-times-defence form matters more than it looks. The first
   *  version averaged two PERCENTILES, which threw the level away entirely:
   *  Manchester City concede few chances anywhere, but percentiled cell by
   *  cell they are still most leaky somewhere, and Burnley — the worst
   *  attack in the league — came out at 95 of 100 down that flank. The page
   *  read "Burnley should come through against Manchester City", which is
   *  not a finding, it is a broken denominator. Multiplying rates keeps the
   *  level: a poor attack against a good defence is low, whatever the shape
   *  of either. Both sides' maps then share one scale, so a mismatch LOOKS
   *  like a mismatch instead of two equally colourful pictures. */
  /** THREE QUESTIONS, NOT ONE. The matchup number answers "what should
   *  happen when these two meet", which is the right default but hides
   *  which side of it is doing the work: a hot cell can be a fine attack or
   *  a soft defence, and the product cannot tell you which.
   *
   *  The two halves were already stored, in the team's own frame, so this
   *  needs no new data:
   *    attack   zo_{cell}   chances this side ORIGINATES from there
   *    defend   zoc_{cell}  chances they CONCEDE from there
   *  Every mode returns a MULTIPLE of the league norm for that cell, so a
   *  number reads on its own — 1.0x is ordinary, 2.0x is twice the league —
   *  and two cards in different phases stay comparable. "0.34 chances a
   *  match" told a reader nothing; "1.8x" tells them it is a strength.
   *
   *  `mode` is required on purpose. A default would let a caller silently
   *  fall back to one shared phase, which is the bug this replaced. */
  const chanceMap = (
    attack: Row | null, defend: Row | null, mode: Phase,
  ) => {
    const out: Record<string, number | undefined> = {};
    if (!meta || !attack || !defend) return out;
    const cells = meta.grid.cells;
    cells.forEach((cell, j) => {
      const mirror = cells[cells.length - 1 - j];
      const mu = zoneMean[cell];
      if (!mu) {
        out[cell] = undefined;
        return;
      }
      if (mode === "attack") {
        const v = attack[`zo_${cell}`];
        out[cell] = typeof v === "number" ? v / mu : undefined;
        return;
      }
      if (mode === "defend") {
        // zoc_ is already mirrored into this side's own frame by the build,
        // so it is read straight — no second flip here.
        const v = attack[`zoc_${cell}`];
        out[cell] = typeof v === "number" ? v / mu : undefined;
        return;
      }
      const threat = attack[`zo_${cell}`];
      const leak = defend[`zoc_${mirror}`];
      out[cell] =
        typeof threat !== "number" || typeof leak !== "number"
          ? undefined
          : (threat / mu) * (leak / mu);
    });
    return out;
  };

  /** The coming round's own answer for this pair, if it has one.
   *
   *  ABOVE THE EARLY RETURN, with every other hook. Put below it, the first
   *  render bails at `if (!meta)` having called one fewer hook than the
   *  second, and React refuses the whole page. That is the fourth time this
   *  exact shape has landed in this project. */
  const called = useMemo(
    () => fixtureFor(round, home, away),
    [round, home, away],
  );

  if (!meta) return <p className="text-[13.5px] text-ink-2">Loading…</p>;

  const label =
    season === "all" ? "All seasons" : meta.season_labels[season] ?? season;
  const hs = hRow ? scores.get(hRow as TeamRow) : undefined;
  const as_ = aRow ? scores.get(aRow as TeamRow) : undefined;

  /** ONE SCALE ACROSS BOTH MAPS. Each side rescaled to its own hottest cell
   *  makes a mismatch look like two equally colourful pictures — the whole
   *  reason the edge keeps the LEVEL rather than percentiling it away is so
   *  that a poor attack against a good defence stays low, and that only
   *  survives if both maps are drawn against the same number.
   *
   *  Not a hook: it is thirty values and it sits below the early return, so
   *  memoising it would buy nothing and cost a dependency list. */
  /** 🐛 A SINGLE SHARED SCALE MADE ONE CARD REPAINT THE OTHER. Taking the
   *  maximum across both maps meant switching Leeds to "attacking" lowered
   *  the ceiling and set Arsenal's matchup map alight — from the outside,
   *  changing one card changed both.
   *
   *  The reason is that the phases are not on one range, which I claimed
   *  they were when normalising to league multiples. Attacking and defending
   *  are a SINGLE multiple (ordinary 1.0, rarely past 2.5). Matchup is a
   *  PRODUCT of two of them, so ordinary is still 1.0 but the top reaches
   *  3-4. Colouring a product against a single multiple is not a comparison,
   *  it is a category error.
   *
   *  So: share the scale only while both cards ask the same question — where
   *  "the hotter side is visibly hotter" is a true statement — and give each
   *  its own the moment they diverge. */
  const mapHNow = chanceMap(hRow, aRow, phaseH);
  const mapANow = chanceMap(aRow, hRow, phaseA);
  const peak = (m: Record<string, number | undefined>) =>
    Math.max(0.01, ...Object.values(m)
      .filter((v): v is number => typeof v === "number"));
  const sameQuestion = phaseH === phaseA;
  const scaleH = sameQuestion
    ? Math.max(peak(mapHNow), peak(mapANow)) : peak(mapHNow);
  const scaleA = sameQuestion ? scaleH : peak(mapANow);

  /** WHO IS AHEAD, ZONE BY ZONE. The matchup number for a cell is this
   *  side's attack against that opponent's leak there; the opponent's number
   *  for the SAME patch of grass is their attack against this side's leak,
   *  which lives at the mirrored cell in their frame. Comparing the two is
   *  the only honest way to say who wins a zone, and it is what the two
   *  pictures were silently asking the reader to do in their head. */
  const mapH = chanceMap(hRow, aRow, "matchup");
  const mapA = chanceMap(aRow, hRow, "matchup");
  const zoneCells = meta.grid.cells;
  let leadsH = 0;
  let leadsA = 0;
  zoneCells.forEach((cell, j) => {
    const mirror = zoneCells[zoneCells.length - 1 - j];
    const mine = mapH[cell];
    const theirs = mapA[mirror];
    if (typeof mine !== "number" || typeof theirs !== "number") return;
    if (mine > theirs) leadsH += 1;
    else if (theirs > mine) leadsA += 1;
  });

  /** Each side's own best routes, listed separately.
   *
   *  A single mixed top-three is always the stronger team three times over —
   *  true, and it tells the reader nothing about how the weaker side might
   *  hurt them, which is the half of a preview worth reading. */
  const routes = (att: Row | null, def: Row | null, mode: Phase) => {
    if (!att || !def) return [] as { cell: string; edge: number }[];
    const m = chanceMap(att, def, mode);
    return meta.grid.cells
      .map((cell) => ({ cell, edge: m[cell] }))
      .filter((e): e is { cell: string; edge: number } => e.edge !== undefined)
      .sort((a, b) => b.edge - a.edge);
  };
  const hRoutes = routes(hRow, aRow, phaseH);
  const aRoutes = routes(aRow, hRow, phaseA);
  const hTotal = hRoutes.reduce((a, e) => a + e.edge, 0);
  const aTotal = aRoutes.reduce((a, e) => a + e.edge, 0);

  /** Both sides in the HOME side's frame, for one shared pitch.
   *
   *  The away side's numbers are computed in ITS frame — cell j for them is
   *  cell 14-j for the home side, a 180 degree turn that flips the third and
   *  the flank together. Put on the same pitch without that turn, the away
   *  team's attacking third would be drawn at the end they are defending,
   *  and it would look entirely plausible.
   *
   *  PLAIN CONSTS, NOT useMemo. Everything they derive from — hRoutes,
   *  aRoutes — is itself recomputed every render below the early return, so
   *  memoising the last step saved nothing and cost a hook AFTER a
   *  conditional return, which React refuses outright: the first render bails
   *  at `if (!meta)` having called nineteen hooks, the next reaches these two
   *  and calls twenty-one. Fifteen array entries do not need a cache. */

  /** THE BOTTOM LINE — the page's own reading of the fixture, in sentences,
   *  built from the same numbers drawn above it. Never a prediction and
   *  never a price: it says where the match is likely to be contested, which
   *  is the part the single score cannot carry. */
  const bottomLine = (() => {
    if (!hs || !as_ || !hRoutes.length || !aRoutes.length) return null;
    const gap = hs.score - as_.score;
    const lead = Math.abs(gap) >= 20 ? "clearly" : Math.abs(gap) >= 8 ? "narrowly" : null;
    const better = gap > 0 ? home : away;
    const worse = gap > 0 ? away : home;
    const phase =
      Math.abs(hs.withBall - as_.withBall) > Math.abs(hs.against - as_.against)
        ? "with the ball"
        : "against it";
    const hi = hRoutes[0];
    const ai = aRoutes[0];
    const aTop = aRoutes[0].edge;
    return { lead, better, worse, phase, gap, hi, ai, aTop };
  })();

  /** THE PREDICTION. The process Elo gives each side a log-multiplier on
   *  chances; the pair becomes a lambda pair, and the lambda pair becomes a
   *  scoreline distribution through the same Dixon-Coles grid the predictor
   *  already uses.
   *
   *  Run TWICE — once on the ratings alone, once with the absentees deducted
   *  — and both are shown. The deduction is NOT a fitted quantity: it prices
   *  a missing player at his rating above replacement, scaled by what a
   *  single player is worth to a side, and that scaling has not been through
   *  a gate. Showing both is the honest form: the reader sees exactly what
   *  the injury news is doing rather than being handed one number with it
   *  silently baked in. */
  const rating = (team: string) =>
    elo?.table.find((t) => t.team === team) ?? null;

  /** What a side is missing, in log-chance units. A player rated 50 is a
   *  replacement and costs nothing; the scale below says a whole team of
   *  100s would create about 35% more than a team of 50s, which is roughly
   *  the spread the ratings themselves show. Eleven players share it. */
  const INJURY_SCALE = 0.30;
  const lost = (team: string) => {
    const out = inj?.teams[team]?.out ?? [];
    let v = 0;
    for (const p of out) {
      if (p.rating === null) continue;          // never rated: cannot value
      const weight = p.status === "Out" ? 1 : 0.4;   // doubtful is partial
      v += (Math.max(0, p.rating - 50) / 50) * INJURY_SCALE / 11 * weight;
    }
    return v;
  };

  const forecast = (() => {
    if (!elo) return null;
    const rh = rating(home);
    const ra = rating(away);
    if (!rh || !ra) return null;
    const { home_adv, conv, rho } = elo.params;
    const raw = project(
      Math.exp(rh.attack - ra.defence + home_adv) * conv,
      Math.exp(ra.attack - rh.defence) * conv, rho);
    const adj = project(
      Math.exp(rh.attack - lost(home) - ra.defence + home_adv) * conv,
      Math.exp(ra.attack - lost(away) - rh.defence) * conv, rho);
    return { raw, adj, moved: Math.abs(adj.lh - raw.lh) + Math.abs(adj.la - raw.la) };
  })();

  /** A side's route, put as hard as its share of the afternoon deserves. */
  const routePhrase = (
    who: string, total: number, other: number,
    r: { cell: string; edge: number },
  ) => {
    const w = where(r.cell, meta);
    const n = <span className="num">{r.edge.toFixed(2)}</span>;
    const share = total / (total + other || 1);
    if (share >= 0.58) {
      return (
        <>
          <strong className="font-semibold">{who}</strong> should come through
          the {w}, worth {n} chances a match on its own.
        </>
      );
    }
    if (share >= 0.42) {
      return (
        <>
          <strong className="font-semibold">{who}</strong> will look to the{" "}
          {w}, their best at {n} a match.
        </>
      );
    }
    return (
      <>
        <strong className="font-semibold">{who}</strong> are unlikely to see
        much of it — their best route, the {w}, is worth {n} a match.
      </>
    );
  };

  return (
    <div>
      <Crumbs trail={[{ href: "/ratings", label: "Ratings" }, { label: "Match" }]} />

      <h1 className="font-display text-[26px] leading-tight">
        {home && away ? `${home} v ${away}` : "Match"}
      </h1>
      <p className="mt-1 max-w-4xl text-[13px] leading-relaxed text-ink-2">
        What the model expects, and the evidence underneath it — the shape
        each side turns up in, where the match is likely to be decided, the
        chances each creates and concedes, and who is missing. A probability
        on its own is the least trustworthy thing we publish; everything
        below is the working.
      </p>

      {/* The two sides facing each other, the way a match graphic is read:
          home on the left, away on the right, everything between them. */}
      {/* STACKED ON A PHONE, FACING EACH OTHER ON A LAPTOP.
          `flex-wrap` alone put Arsenal and the "v" on one line and Aston
          Villa on the next — the divider ended up beside one club instead of
          between the two, which is the one thing it is for. Below `sm` this
          is three rows: home, the "v" as a real horizontal rule, away. */}
      <div className="mt-5 rounded-xl border border-line bg-card px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4">
          <Pick label="Home" value={home} set={setHome} teams={teams} meta={meta} />
          <div className="flex items-center gap-3 sm:flex-col sm:gap-0">
            <span className="h-px flex-1 bg-line sm:hidden" />
            <span className="font-display text-[15px] tracking-[0.08em] text-ink-3">
              v
            </span>
            <span className="text-[11px] text-ink-3 sm:mt-0.5">
              {meta.season_labels[season] ?? season}
            </span>
            <span className="h-px flex-1 bg-line sm:hidden" />
          </div>
          <Pick
            label="Away"
            value={away}
            set={setAway}
            teams={teams}
            meta={meta}
            right
          />
        </div>
      </div>

      {called && (
        <div className="mt-5">
          <Called f={called.f} league={called.league} />
        </div>
      )}

      {/* --------------------------------------------- the two elevens */}
      <section className="mt-6">
        <h2 className="text-[16px] font-semibold">The shape each turns up in</h2>
        <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
          The eleven who filled the shape most often, each standing where he
          averages on the ball, with the passes between them. Both drawn
          attacking up the picture, so the two are read the same way round
          rather than as they would meet.
        </p>
        {home && away && eventSeason ? (
          <div className="mt-3 grid gap-6 lg:grid-cols-2">
            <SideXI key={home} team={home} season={eventSeason} />
            <SideXI key={away} team={away} season={eventSeason} />
          </div>
        ) : null}
      </section>

      {/* ------------------------------------------------ the head-to-head */}
      <section className="mt-5">
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-[13px]">
            <tbody>
              {[
                ["Overall", hs?.score, as_?.score, "process, opponent-adjusted"],
                ["With the ball", hs?.withBall, as_?.withBall, ""],
                ["Against the ball", hs?.against, as_?.against, ""],
                ["Squad", squads.home?.rating, squads.away?.rating,
                  "the players they have, on your weights"],
              ].map(([name, h, a, hint]) => (
                <Bar
                  key={String(name)}
                  name={String(name)}
                  hint={String(hint)}
                  h={typeof h === "number" ? h : undefined}
                  a={typeof a === "number" ? a : undefined}
                />
              ))}
              <Bar
                name="Points a match"
                hint="the result, not the process"
                h={typeof hRow?.pts === "number" ? hRow.pts : undefined}
                a={typeof aRow?.pts === "number" ? aRow.pts : undefined}
                raw
              />
            </tbody>
          </table>
        </div>
      </section>

      {/* --------------------------------------------------- the bottom line */}
      {bottomLine && (
        <section className="mt-8 rounded-xl border border-line bg-[#fbfcfd] p-5">
          <h2 className="text-[11px] uppercase tracking-[0.14em] text-ink-3">
            The bottom line
          </h2>
          <p className="mt-2 max-w-4xl text-[14.5px] leading-relaxed text-ink">
            {bottomLine.lead ? (
              <>
                <strong className="font-semibold">{bottomLine.better}</strong>{" "}
                are {bottomLine.lead} the better side on process —{" "}
                <span className="num">{Math.max(hs!.score, as_!.score).toFixed(0)}</span>{" "}
                to{" "}
                <span className="num">{Math.min(hs!.score, as_!.score).toFixed(0)}</span>{" "}
                — and the gap is wider {bottomLine.phase}.
              </>
            ) : (
              <>
                There is almost nothing between them on process —{" "}
                <span className="num">{hs!.score.toFixed(0)}</span> against{" "}
                <span className="num">{as_!.score.toFixed(0)}</span>.
              </>
            )}{" "}
            {routePhrase(home, hTotal, aTotal, bottomLine.hi)}{" "}
            {routePhrase(away, aTotal, hTotal, bottomLine.ai)}
          </p>
          <p className="mt-2.5 text-[13px] text-ink-2">
            On these rates the match projects to{" "}
            <strong className="font-semibold">
              <span className="num">{hTotal.toFixed(1)}</span> chances for{" "}
              {home}
            </strong>{" "}
            against{" "}
            <strong className="font-semibold">
              <span className="num">{aTotal.toFixed(1)}</span> for {away}
            </strong>{" "}
            — each side&apos;s rate in a zone multiplied by what the other
            concedes there, against the league average.
          </p>
          <p className="mt-2 text-[11.5px] text-ink-3">
            Written from the maps below, not from a model of the result.
            Nothing here is a prediction or a price.
          </p>
        </section>
      )}

      {/* ------------------------------------------------------- the maps */}
      <section className="mt-8">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[16px] font-semibold">Where it is decided</h2>

        </div>


        <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
          Each map is drawn in the frame of the side <em>on the ball</em>, so
          up the picture is always forward for them. The same patch of grass
          is a different cell for each team — your attacking left wing is
          their defensive right — and the maps account for that turn.
        </p>

        <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
          Every number is a MULTIPLE of what a typical side manages in that
          same cell, so <span className="num">1.0&times;</span> is ordinary
          and <span className="num">2.0&times;</span> is twice the league.
          Each card picks its own phase — set one to attacking and the other
          to defending to read the pair that actually decides the fixture.
          {!sameQuestion && (
            <>
              {" "}
              <b className="text-ink-2">
                The two cards are asking different questions, so each is
                coloured against its own range
              </b>{" "}
              — compare the numbers, not the heat.
            </>
          )}
        </p>
        <div className="mt-4 grid gap-8 lg:grid-cols-2">
          <Half
            title={
              phaseH === "defend" ? `When ${home} are defending`
                : phaseH === "attack" ? `${home} on the ball`
                : `When ${home} have it`
            }
            subtitle={
              phaseH === "defend" ? "where they are got at"
                : phaseH === "attack" ? "where they create"
                : `${hTotal.toFixed(1)}× normal, summed`
            }
            values={mapHNow}
            routes={hRoutes}
            attack={home}
            defend={away}
            meta={meta}
            scale={scaleH}
            phase={phaseH}
            onPhase={setPhaseH}
            leads={leadsH}
            cells={zoneCells.length}
          />
          <Half
            title={
              phaseA === "defend" ? `When ${away} are defending`
                : phaseA === "attack" ? `${away} on the ball`
                : `When ${away} have it`
            }
            subtitle={
              phaseA === "defend" ? "where they are got at"
                : phaseA === "attack" ? "where they create"
                : `${aTotal.toFixed(1)}× normal, summed`
            }
            values={mapANow}
            routes={aRoutes}
            attack={away}
            defend={home}
            meta={meta}
            scale={scaleA}
            phase={phaseA}
            onPhase={setPhaseA}
            leads={leadsA}
            cells={zoneCells.length}
          />
        </div>
        <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">
          A zone is only as trustworthy as the football behind it. Early in a
          season these move a long way on one afternoon.
        </p>
      </section>

      {/* ---------------------------------------------------- the shots */}
      {home && away && eventSeason ? (
        <MatchShots home={home} away={away} season={eventSeason} />
      ) : null}

      {home && away && eventSeason ? (
        <MatchPasses home={home} away={away} season={eventSeason} />
      ) : null}

      {/* ------------------------------------------------- who is missing */}
      {inj && (inj.teams[home] || inj.teams[away]) && (
        <section className="mt-8">
          <h2 className="text-[16px] font-semibold">Who is missing</h2>
          <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
            Named on WhoScored&apos;s match preview, which is published before
            kickoff — so this is knowable on Thursday for a Saturday game
            rather than read off a team sheet afterwards. Each absentee is
            valued at his rating from{" "}
            {inj.rated_on.replace(/(\d\d)(\d\d)/, "20$1/$2")}, the last
            complete season: a player injured since August has no useful
            record of this one, which is the whole reason he is missing.
          </p>
          <div className="mt-3 grid gap-5 lg:grid-cols-2">
            {[home, away].map((t) => (
              <OutList key={t} team={t} d={inj.teams[t]} />
            ))}
          </div>
        </section>
      )}

      {/* --------------------------------------------------- the forecast */}
      {forecast && (
        <section className="mt-8 overflow-hidden rounded-xl border border-line bg-card">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line bg-[#fbfcfd] px-5 py-3">
            <h2 className="text-[15px] font-semibold">A second opinion</h2>
            <span className="text-[11.5px] text-ink-3">
              process Elo → Dixon-Coles · independent of the model at the top
            </span>
          </div>

          <div className="grid gap-6 p-5 lg:grid-cols-[minmax(0,320px)_1fr]">
            <div>
              <Odds p={forecast.adj} home={home} away={away} />
              <div className="num mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3">
                <span>
                  expected goals{" "}
                  <b className="text-ink-2">
                    {forecast.adj.lh.toFixed(2)} – {forecast.adj.la.toFixed(2)}
                  </b>
                </span>
                <span>
                  likeliest{" "}
                  <b className="text-ink-2">
                    {forecast.adj.lines
                      .slice(0, 3)
                      .map((l) => `${l.h}-${l.a}`)
                      .join(" · ")}
                  </b>
                </span>
              </div>
              {forecast.moved > 0.005 && (
                <p className="mt-2.5 text-[11.5px] leading-relaxed text-ink-3">
                  {/* 🐛 THIS USED TO SAY "POINTS OF WIN PROBABILITY". It is
                      not: `moved` is a sum of LAMBDA differences, so the
                      units are expected goals. Reading 0.08 goals out as
                      "7.8 points" overstated the injury effect by two orders
                      of magnitude on every fixture. */}
                  The absentees are already in these numbers — they take{" "}
                  <span className="num text-ink-2">
                    {forecast.moved.toFixed(2)}
                  </span>{" "}
                  off the expected goals between them.
                </p>
              )}
            </div>

            <div className="space-y-2.5 text-[12px] leading-relaxed text-ink-3">
              <p className="rounded-lg border border-[#e4d49a] bg-[#fdf8e7] p-2.5 text-[#6b5606]">
                <b>It will not agree with the call at the top, and that is
                the point.</b>{" "}
                That one is the shipped model, built on Understat xG. This one
                is built on process Elo and never sees it. Across the current
                round this arm runs about{" "}
                <span className="num">+4.7</span> points hotter on the home
                side and <span className="num">−3.5</span> on the draw,
                because it projects{" "}
                <span className="num">3.03</span> goals a game against the
                shipped model&apos;s <span className="num">2.57</span> — and
                more goals make an exact tie less likely. The league actually
                scores about <span className="num">2.75</span>, so the truth
                sits between them and nearer the top of the page.
              </p>
              <p>
                The ratings are a process Elo: a log-multiplier on chances,
                carried across seasons and updated on what each side{" "}
                <em>created</em> rather than on results, because a half-season
                of points predicts the next half at{" "}
                <span className="num">0.59</span> and the process metrics
                predict it at <span className="num">0.78</span>.
              </p>
              <p>
                Scored against 25/26 it runs at{" "}
                <span className="num">1.039</span> log-loss against a base
                rate of <span className="num">1.085</span> — clearly better
                than guessing, and behind the model the site ships at{" "}
                <span className="num">1.034</span>. It is shown because two
                independent readings that agree are worth more than one, and
                because hiding the disagreement would be the only way to get
                it wrong.
              </p>
              <p className="text-bad">
                The injury deduction has NOT been through a gate. It prices a
                missing player at his rating above replacement and the scaling
                is reasoned rather than fitted, so the direction is the part
                worth reading and the last decimal is decoration.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ------------------------------------------------------ the squads */}
      <section className="mt-8">
        <h2 className="text-[16px] font-semibold">Position by position</h2>
        <p className="mt-1 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
          Each club&apos;s players percentiled inside their own position across
          the league, weighted by the minutes they played there. Only positions
          a side actually fields appear — a club that never picks a wing-back
          has a shape, not a hole.
        </p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-[13px]">
            <tbody>
              {[...new Set([
                ...Object.keys(squads.home?.at ?? {}),
                ...Object.keys(squads.away?.at ?? {}),
              ])].map((b) => (
                <Bar
                  key={b}
                  name={posShort(b)}
                  hint={posLabel(b)}
                  h={squads.home?.at[b]}
                  a={squads.away?.at[b]}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** One phase: the map, its OWN legend right beneath it, and the routes it
 *  shows. The legend used to sit once at the far right of the section
 *  heading, a screen away from the colours it explained. */
function Half({
  title, subtitle, values, routes, attack, defend, meta, scale,
  phase, onPhase, leads, cells,
}: {
  title: string;
  subtitle: string;
  values: Record<string, number | undefined>;
  routes: { cell: string; edge: number }[];
  attack: string;
  defend: string;
  meta: Meta;
  /** shared by both maps, so the hotter side is visibly the hotter side */
  scale: number;
  phase: Phase;
  onPhase: (p: Phase) => void;
  /** in matchup mode: zones where this side's number beats the opponent's in
   *  the same patch of grass. The answer to "who is winning where". */
  leads: number;
  cells: number;
}) {
  const crests = useCrests();
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <div className="flex flex-wrap items-start gap-5">
        <div>
          <div className="flex items-center gap-2">
            <Crest src={crestFor(crests, attack)} alt="" size={22} />
            <div>
              <div className="text-[13px] font-semibold text-ink">{title}</div>
              <div className="text-[11.5px] text-ink-3">{subtitle}</div>
            </div>
          </div>

          {/* THE PILLS BELONG TO THE CARD. One shared control could never
              show the pair that matters — this side attacking while the
              other defends — because it moved both at once. */}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {PHASES.map((f) => (
              <button
                key={f.key}
                onClick={() => onPhase(f.key)}
                title={f.hint}
                className={`rounded-full border px-2.5 py-0.5 text-[11.5px] transition-colors ${
                  phase === f.key
                    ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                    : "border-line bg-card text-ink-2 hover:border-ink-3"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {phase === "matchup" && (
            <div className="mt-1.5 text-[11.5px] text-ink-2">
              Ahead in{" "}
              <b className={leads > cells / 2 ? "text-good" : "text-ink"}>
                {leads} of {cells}
              </b>{" "}
              zones
            </div>
          )}
          {/* min-w-[320px] plus the card's own padding is wider than a 375px
              screen, so the PAGE scrolled rather than the card. Full width
              below `sm`; the sized column is a laptop concern. */}
          <div className="mt-1.5 w-full sm:w-[min(520px,46vw)] sm:min-w-[320px]">
            <ZonePitch
              values={values}
              attacking={attack}
              defending={defend}
              scale={scale}
            />
          </div>
        </div>
        <div className="min-w-0 flex-1 sm:min-w-[170px]">
          <h3 className="text-[12px] uppercase tracking-wider text-ink-3">
            {attack}&apos;s best routes
          </h3>
          {routes.length === 0 ? (
            <p className="mt-1.5 text-[12.5px] text-ink-3">
              Not enough played to compare zones.
            </p>
          ) : (
            <ol className="mt-1.5 space-y-2">
              {routes.slice(0, 3).map((r) => (
                <li key={r.cell} className="flex items-baseline gap-2">
                  <span
                    className="num inline-flex h-[22px] w-[38px] shrink-0 items-center justify-center rounded-md text-[11.5px] font-bold text-white"
                    style={{
                      background:
                        r.edge >= scale * 0.66 ? "#b3261e"
                          : r.edge >= scale * 0.33 ? "#d98324" : "#9aa3ab",
                    }}
                  >
                    {r.edge.toFixed(1)}&times;
                  </span>
                  <span className="text-[12.5px] leading-snug text-ink-2">
                    {where(r.cell, meta)}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-2 text-[11.5px] leading-relaxed text-ink-3">
            Chances a match {attack} should get from there, given what{" "}
            {defend} concede there.
          </p>
        </div>
      </div>
    </div>
  );
}

/** One side's absentees, worst loss first. An unrated player is still listed
 *  — he is still missing — but marked, because counting him at zero and
 *  counting him at nothing look identical in a total and are not. */
function OutList({
  team, d,
}: {
  team: string;
  d?: { fixture: string; date: string; out: Absent[]; n_out: number; n_doubt: number };
}) {
  if (!d || !d.out.length) {
    return (
      <div className="rounded-lg border border-line bg-[#fbfcfd] p-3">
        <b className="text-[13px]">{team}</b>
        <p className="mt-1 text-[12.5px] text-ink-3">
          Nobody named out in the latest preview.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-line bg-[#fbfcfd] p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <b className="text-[13px]">{team}</b>
        <span className="text-[11.5px] text-ink-3">
          <span className="num">{d.n_out}</span> out
          {d.n_doubt > 0 && (
            <>
              , <span className="num">{d.n_doubt}</span> doubtful
            </>
          )}
          {" · "}
          {d.date}
        </span>
      </div>
      <ul className="mt-2 space-y-1">
        {d.out.map((p) => (
          <li
            key={p.player}
            className="flex items-baseline justify-between gap-3 text-[12.5px]"
          >
            <span className="truncate">
              {p.player}
              {p.status !== "Out" && (
                <span className="ml-1.5 text-[11px] text-ink-3">doubtful</span>
              )}
            </span>
            <span className="shrink-0 text-[11.5px]">
              {p.rating === null ? (
                <span className="text-ink-3" title="no Premier League record to rate him on">
                  unrated
                </span>
              ) : (
                <>
                  <span className="mr-1.5 text-ink-3">{posShort(p.bucket ?? "")}</span>
                  <span
                    className="num font-semibold"
                    style={{
                      color: p.rating >= 70 ? "#b3261e"
                        : p.rating >= 45 ? "#8a6d1c" : "#6b7280",
                    }}
                  >
                    {p.rating.toFixed(0)}
                  </span>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}


function Pick({
  label, value, set, teams, meta, right,
}: {
  label: string; value: string; set: (v: string) => void;
  teams: string[]; meta: Meta;
  /** the away side, mirrored so the two face each other */
  right?: boolean;
}) {
  return (
    <label
      // THE MIRROR ONLY APPLIES SIDE BY SIDE. `flex-row-reverse` exists so the
      // two clubs face each other across the "v"; stacked on a phone it just
      // puts one badge on the left and one on the right of a vertical list,
      // which reads as a mistake rather than as a fixture. Below `sm` both
      // sides run the same way round.
      className={`flex min-w-0 items-center gap-3 ${
        right ? "sm:flex-row-reverse sm:text-right" : ""
      }`}
    >
      <Crest src={meta.crests?.[value] ?? ""} alt={value} size={46} />
      <span className="flex min-w-0 flex-col">
        <span className="text-[10.5px] uppercase tracking-[0.12em] text-ink-3">
          {label}
        </span>
        <select
          value={value}
          onChange={(e) => set(e.target.value)}
          // A native select sizes itself to its WIDEST option, so a fixed
          // max-width is what keeps "Borussia Mönchengladbach" from setting
          // the width of this box and scrolling the page sideways.
          className={`-ml-1 w-full min-w-0 max-w-[190px] cursor-pointer truncate rounded-md border border-transparent bg-transparent px-1 py-0.5 text-[17px] font-semibold hover:border-line ${
            right ? "sm:text-right" : ""
          }`}
        >
          {teams.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </span>
    </label>
  );
}

/** One comparison, drawn as two bars growing out of a shared centre — the
 *  only layout where the winner is obvious without reading either number. */
function Bar({
  name, hint, h, a, raw,
}: {
  name: string; hint?: string; h?: number; a?: number; raw?: boolean;
}) {
  const span = raw ? Math.max(h ?? 0, a ?? 0, 1) : 100;
  const w = (v?: number) => (v === undefined ? 0 : (v / span) * 100);
  const lead = h !== undefined && a !== undefined ? h - a : 0;
  const fmt = (v?: number) =>
    v === undefined ? "—" : raw ? v.toFixed(2) : v.toFixed(0);
  return (
    <tr className="border-t border-line first:border-t-0">
      <td className="num w-14 py-2 pl-4 pr-2 text-right text-[13px] font-semibold">
        {fmt(h)}
      </td>
      <td className="w-[38%] py-2">
        <span className="flex justify-end">
          <span
            className="h-2.5 rounded-l-full"
            style={{
              width: `${w(h)}%`,
              background: lead > 0 ? "#2f6f4f" : "#b8c0c7",
            }}
          />
        </span>
      </td>
      <td
        className="whitespace-nowrap px-3 py-2 text-center text-[12px] text-ink-2"
        title={hint}
      >
        {name}
      </td>
      <td className="w-[38%] py-2">
        <span
          className="block h-2.5 rounded-r-full"
          style={{
            width: `${w(a)}%`,
            background: lead < 0 ? "#1c5b8a" : "#b8c0c7",
          }}
        />
      </td>
      <td className="num w-14 py-2 pl-2 pr-4 text-[13px] font-semibold">
        {fmt(a)}
      </td>
    </tr>
  );
}

/** A cell key as words. "ALW" is the attacking left wing; nobody reads a
 *  three-letter code and the maps are worth nothing if the prose beside
 *  them has to be decoded. */
function where(cell: string, meta: Meta): string {
  const thirds: Record<string, string> = {
    D: "defensive third",
    M: "middle third",
    A: "attacking third",
  };
  const channels: Record<string, string> = {
    LW: "left wing",
    LH: "left half-space",
    C: "centre",
    RH: "right half-space",
    RW: "right wing",
  };
  const t = thirds[cell.slice(0, 1)];
  const c = channels[cell.slice(1)];
  return t && c ? `${c}, ${t}` : cell;
}

/** A triplet as three bars.
 *
 *  A column of percentages is a table; three bars against a common baseline
 *  is a shape, and the shape is what says whether a 43% favourite is a
 *  comfortable afternoon or a coin flip that landed. Same treatment as the
 *  model's own call at the top of the page, so the two can be compared by
 *  eye rather than by arithmetic.
 */
function Odds({
  p, home, away,
}: {
  p: { home: number; draw: number; away: number };
  home: string;
  away: string;
}) {
  const rows: [string, number, string][] = [
    [home, p.home, "#2f6fae"],
    ["Draw", p.draw, "#c9a227"],
    [away, p.away, "#c2572a"],
  ];
  return (
    <div className="space-y-1.5">
      {rows.map(([name, v, colour]) => (
        <div key={name} className="flex items-center gap-2.5">
          <span className="w-[104px] shrink-0 truncate text-[12.5px] text-ink-2">
            {name}
          </span>
          <span className="num w-[46px] shrink-0 text-right text-[14px] font-semibold text-ink">
            {(v * 100).toFixed(1)}%
          </span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-[#eef1f3]">
            <span
              className="block h-full rounded-full"
              style={{ width: `${v * 100}%`, background: colour }}
            />
          </span>
          <span className="num w-[36px] shrink-0 text-right text-[11.5px] text-ink-3">
            {v > 0 ? (1 / v).toFixed(2) : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}
