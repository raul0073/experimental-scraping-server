"use client";

import { useEffect, useMemo, useState } from "react";

import { Info } from "../components/Info";
import { posLabel, posShort } from "../lib/positions";

import {
  type Data,
  type Player,
  type Rel,
  ALL_LEAGUES,
  PRESETS,
  useRatings,
} from "./RatingsData";
import {
  ActiveFilters, BUDGET, CHECK_BOX, FILTER_BAR, Field, MARGINAL,
  RELIABLE, SELECT, SPREAD_PLAYER, ScoreRing, THIN_N, scoreColor, tint,
} from "./scoreUi";

/** The combined table: every player, each scored on the config for his own
 *  position. */
const ALL = "ALL";

/** The bar is a SHARE of the PERIOD's available minutes, not a count, and
 *  not a share of his own club's — a Coventry keeper who played all four of
 *  their 26/27 matches was scoring 95% and standing beside men with ten
 *  thousand minutes, because his club had been in the league four weeks.
 *
 *  The rung that makes sense still depends on the period. 85% of five rounds
 *  is 92 players; 85% of four seasons is five, because almost nobody plays
 *  every minute of four years at one club. So the default is the STRICTEST
 *  rung that still leaves a table worth reading, which lands on 85% for the
 *  current season and 30% for the pooled view without anyone choosing it. */
const SHARE_RUNGS = [15, 30, 50, 70, 85];
const USABLE = 0.25;   // a rung must keep this share of the view's rows

/** The position rail, grouped the way a team sheet is — back to front.
 *
 *  Nine pills in one undifferentiated row is a list you have to READ. Four
 *  zones is a shape you RECOGNISE, and every reader already knows the shape,
 *  so the grouping costs nothing to learn. It also makes the neighbouring
 *  choice obvious: someone looking at centre-backs is far more likely to want
 *  full-backs next than strikers, and now those sit together.
 *
 *  Tints run cool at the back to warm at the front. They are deliberately
 *  faint — this is a grouping cue, not a colour code, and anything stronger
 *  would compete with the score colours in the table below, which DO carry
 *  meaning. */
const ZONES: { label: string; keys: string[]; tint: string }[] = [
  { label: "Goal", keys: ["GK"], tint: "bg-[#f3f5f7]" },
  { label: "Defence", keys: ["CB", "FB", "WB"], tint: "bg-[#eef3f8]" },
  { label: "Midfield", keys: ["DM", "CM", "AM"], tint: "bg-[#eff4f1]" },
  { label: "Attack", keys: ["WIDE", "ST"], tint: "bg-[#f9f2ed]" },
];



function Th({
  k,
  sort,
  setSort,
  children,
  align = "right",
  title,
}: {
  k: string;
  sort: { key: string; dir: 1 | -1 };
  setSort: (s: { key: string; dir: 1 | -1 }) => void;
  children: React.ReactNode;
  align?: "left" | "right";
  title?: string;
}) {
  const active = sort.key === k;
  const textual = k === "n" || k === "t" || k === "s";
  return (
    <th
      title={title}
      onClick={() =>
        setSort({
          key: k,
          // first click on a new column sorts biggest-first, which is what
          // anyone reading a ranking wants
          dir: active ? ((sort.dir * -1) as 1 | -1) : textual ? 1 : -1,
        })
      }
      className={`cursor-pointer select-none px-2 py-2 font-semibold transition-colors hover:text-ink ${
        align === "left" ? "text-left" : "text-right"
      } ${active ? "text-ink" : ""}`}
    >
      {children}
      <span className={active ? "" : "opacity-0"}>
        {" "}
        {sort.dir === -1 ? "▾" : "▴"}
      </span>
    </th>
  );
}

/** How much a metric can be trusted FOR THIS BUCKET. Two different failures
 *  are kept apart on purpose: a metric that does not repeat is a bad metric,
 *  while a metric nobody has been able to test yet is an open question, and
 *  colouring them the same would be a lie about what we know. */
function relTone(repeat?: Rel, self?: Rel) {
  if (!repeat) {
    if (self && self.rho >= MARGINAL) {
      return {
        cls: "text-ink-2",
        tip: `measurable within a season (${self.rho}, n=${self.n}) but not yet ` +
          `testable across seasons — too few players have held this role twice`,
      };
    }
    return { cls: "text-ink-3", tip: "not testable for this bucket yet" };
  }
  const thin = repeat.n < THIN_N ? ` — thin sample, n=${repeat.n}` : "";
  if (repeat.rho >= RELIABLE)
    return { cls: "text-good", tip: `repeats across seasons (${repeat.rho}, n=${repeat.n})${thin}` };
  if (repeat.rho >= MARGINAL)
    return { cls: "text-[#9a7400]", tip: `marginal (${repeat.rho}, n=${repeat.n})${thin}` };
  return {
    cls: "text-bad",
    tip: `does NOT repeat (${repeat.rho}, n=${repeat.n}) — a rating built on this is decoration`,
  };
}

/** A dot, because a colour-word on a label is easy to miss when there are
 *  forty of them. Green repeats, amber is marginal, red is noise, hollow
 *  means nobody has been able to test it for this bucket yet. */
function relDot(repeat?: Rel, self?: Rel) {
  if (!repeat) {
    return self && self.rho >= MARGINAL
      ? "border border-ink-3 bg-transparent"
      : "border border-line bg-transparent";
  }
  if (repeat.rho >= RELIABLE) return "bg-good";
  if (repeat.rho >= MARGINAL) return "bg-[#c99a1e]";
  return "bg-bad";
}

const SIDE_TAG: Record<string, string> = {
  R: "R", L: "L", C: "—", RL: "R/L", LR: "R/L",
};


function sumWeights(w: Record<string, number>): number {
  return Object.values(w).reduce((a, b) => a + (b || 0), 0);
}

export function PlayerBoard() {
  const { meta: data, index, league, setLeague, players, want,
          loading: loadingView, allWeights, setAllWeights } = useRatings();
  const [view, setView] = useState<string>("");
  const [pos, setPos] = useState("ALL");
  const isAll = pos === ALL;
  const [side, setSide] = useState("any");
  /** One weight set per bucket, owned by RatingsData so the teams board can
   *  read the same config — team mental IS the squad's player ratings, so it
   *  has to move when these do. */
  const weights = allWeights[pos] ?? {};
  const setWeights = (
    next:
      | Record<string, number>
      | ((prev: Record<string, number>) => Record<string, number>),
  ) =>
    setAllWeights((prev) => ({
      ...prev,
      [pos]: typeof next === "function" ? next(prev[pos] ?? {}) : next,
    }));
  const [blockUnreliable, setBlockUnreliable] = useState(true);
  /** expand every section at once, rather than only the ones in use */
  const [showAll, setShowAll] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  /** The config folds away once it is set, so the table gets the page. */
  /** CLOSED ON ARRIVAL. The weights are the page's argument — what counts
   *  in a centre-back is not what counts in a winger, and it is not for a
   *  model to decide — but opening on a panel of sliders asks every first
   *  visitor to make nine decisions before they have seen a single name.
   *  The default is one opinionated set, the ranking is right there, and
   *  the controls are one click away for anyone who disagrees with it. The
   *  teams board already worked this way; only this one did not. */
  const [configOpen, setConfigOpen] = useState(false);
  /** Defaults to the strictest bar available for the view, so the table opens
   *  on players with a season's worth of evidence behind them rather than on
   *  everyone who cleared 450 minutes. */
  const [minShare, setMinShare] = useState(SHARE_RUNGS[1]);
  /** Off by default: a league ranking is about the league as it is now. */
  const [includeGone, setIncludeGone] = useState(false);
  const [team, setTeam] = useState(ALL);
  /** Positions shown ALONGSIDE `pos`. Kept separate rather than making `pos`
   *  an array because `pos` does a second job — it is the position whose
   *  weights the config panel edits, and that is necessarily one at a time.
   *  Scoring is unaffected either way: scoreOf() already reads
   *  allWeights[p.p], so every player is scored on his own position's config
   *  and percentiled within his own position no matter what is selected.
   *  Comparing central and attacking midfielders is therefore a pure display
   *  filter, and each man keeps the ranking that belongs to his own job. */
  const [extra, setExtra] = useState<string[]>([]);
  const [shareTouched, setShareTouched] = useState(false);
  const [padj, setPadj] = useState(true);
  /** How much of the ranking is his FLOOR rather than his pooled level. The
   *  typical player swings 28 percentile points between seasons, and swing is
   *  close to independent of level — van Dijk moves 4 points across three
   *  seasons while Elliot Anderson moves 46 — so this is real information and
   *  not a restatement of the score.
   *
   *  Half and half by default. Measured on the 112 players at 5,400+ minutes
   *  this is a correction rather than an upheaval — Spearman 0.976 against
   *  the pooled ranking, 15 players moving more than ten places and none more
   *  than twenty-five — and it moves the ones it should: Martinelli pools at
   *  72 with a floor of 9 and drops; Odegaard is 51 pooled and 48 at his
   *  worst, and rises for never dropping.
   *
   *  A man with one season on record keeps his pooled number rather than
   *  being penalised for arriving late. At the default minutes bar nobody is
   *  in that position; lower the bar and the Swing column shows a dash for
   *  anyone the test cannot judge. */
  const [durability, setDurability] = useState(50);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({
    key: "score",
    dir: -1,
  });

  useEffect(() => {
    if (data && view) want(view);
  }, [data, view, want]);

  /** THE POOLED VIEW, not the season in progress.
   *
   *  The old default was this season, on the reasoning that a summer signing
   *  is invisible in a four-season total. That is true, and it is the lesser
   *  problem: five rounds is ~450 minutes, which clears almost nobody's
   *  minutes bar and puts most of the metrics below the reliability gate, so
   *  the table opens thin and half-red in September. The pooled view is the
   *  one with something to say; a reader after current form picks the season
   *  from the dropdown, which is one click and clearly labelled. */
  useEffect(() => {
    if (!data || view) return;
    const pooled = data.views.find((v) => v.key === "total");
    setView(pooled?.key ?? data.views[0]?.key ?? "");
  }, [data, view]);

  const periodMin = data?.period_minutes?.[view] ?? 0;

  /** Pick the strictest rung that still leaves a table worth reading. 85% of
   *  five rounds keeps 92 players; 85% of four seasons keeps five. Rather
   *  than make the reader discover that, the bar follows the period. */
  useEffect(() => {
    if (!data || !view || shareTouched) return;
    const rows = players[view];
    if (!rows?.length) return;
    const best = [...SHARE_RUNGS]
      .reverse()
      .find((v) => rows.filter((r) => r.rs >= v).length >= rows.length * USABLE);
    setMinShare(best ?? SHARE_RUNGS[0]);
  }, [data, view, players, shareTouched]);

  const rel = (key: string) => data?.reliability?.[key]?.[pos];
  const selfRel = (key: string) => data?.self_reliability?.[key]?.[pos];

  const spent = isAll ? BUDGET : sumWeights(weights);
  const left = BUDGET - spent;

  /** How much of the budget the gate is currently throwing away. Spending 20
   *  on a metric that does not repeat is allowed, but the reader should be
   *  able to see that it never reaches the score. */
  const blocked = blockUnreliable && !isAll
    ? Object.entries(weights).reduce((a, [k, w]) => {
        const r = rel(k);
        return a + (w > 0 && r !== undefined && r.rho < MARGINAL ? w : 0);
      }, 0)
    : 0;

  /** Raising one weight can never push the bucket past 100: the slider stops
   *  at whatever budget is left. Spending is a choice between metrics, which
   *  is the whole point of the exercise. */
  const setWeight = (key: string, value: number) =>
    setWeights((prev) => {
      const room = BUDGET - sumWeights(prev) + (prev[key] ?? 0);
      return { ...prev, [key]: Math.max(0, Math.min(value, room)) };
    });

  /** Scale what is already there up or down to exactly 100, keeping the
   *  proportions the reader chose. The last metric absorbs the rounding so
   *  the total is exact rather than 99 or 101. */
  const balance = () =>
    setWeights((prev) => {
      const total = sumWeights(prev);
      if (!total) return prev;
      const keys = Object.keys(prev).filter((k) => (prev[k] ?? 0) > 0);
      const out: Record<string, number> = { ...prev };
      let acc = 0;
      keys.forEach((k, i) => {
        const v = i === keys.length - 1
          ? BUDGET - acc
          : Math.round((prev[k] / total) * BUDGET);
        out[k] = v;
        acc += v;
      });
      return out;
    });

  const groupTotal = (g: string) =>
    (data?.metrics ?? [])
      .filter((m) => m.group === g)
      .reduce((a, m) => a + (weights[m.key] ?? 0), 0);

  /** A player's score always uses the config for HIS bucket, so the same
   *  function serves one position or all nine. Metrics the gate refuses for
   *  that bucket drop out of both the numerator and the divisor, so the score
   *  stays on a 0-100 scale rather than being quietly deflated. */
  const scoreOf = (p: Player) => {
    const q = padj ? p.qa : p.q;
    let sum = 0;
    let used = 0;
    for (const [k, w] of Object.entries(allWeights[p.p] ?? {})) {
      if (w <= 0) continue;
      if (blockUnreliable) {
        const r = data?.reliability?.[k]?.[p.p];
        if (r !== undefined && r.rho < MARGINAL) continue;
      }
      sum += (q[k] ?? 50) * w;
      used += w;
    }
    return used ? sum / used : 0;
  };

  /** Clubs present in the view being shown, so the list never offers one that
   *  would empty the table. Built from the UNFILTERED rows for this view —
   *  taking it from `rows` would shrink the list to the club already chosen,
   *  leaving no way back to another.
   *
   *  ABOVE THE LOADING GUARD, and it has to be: a hook after a conditional
   *  return typechecks perfectly and then throws "Rendered more hooks than
   *  during the previous render" the moment the payload lands. */
  const clubs = useMemo(() => {
    const src = players[view] ?? [];
    return [...new Set(src.map((p) => p.t).filter(Boolean))].sort((a, b) =>
      a.localeCompare(b),
    );
  }, [players, view]);

  /** A club chosen in one league does not exist in the next, and one absent
   *  from the list would filter the table to nothing with no visible cause.
   *
   *  DERIVED RATHER THAN RESET IN AN EFFECT. Clearing the state from a
   *  useEffect works, but it renders once with the dead club, then sets
   *  state, then renders again — a cascading render for something that is
   *  simply a function of what is on screen. Falling back here means there is
   *  never a frame in which the table is empty for a reason the reader cannot
   *  see, and the select reads the same value, so the two cannot disagree. */
  const activeTeam = team !== ALL && clubs.includes(team) ? team : ALL;

  const rows = useMemo(() => {
    if (!data || !view) return [];
    const all = players[view] ?? [];

    // The raw composite is an average of percentiles, so its SIZE depends on
    // how many metrics carry weight, not on the player: the same centre-backs
    // top out at 79 on a five-metric config and 73 on a ten-metric one. That
    // makes the raw value unreadable as a score. Re-ranking it within the
    // bucket removes the dependency — 100 is the best centre-back on YOUR
    // config, whatever size that config is.
    //
    // Ranked over the whole bucket rather than the filtered rows, so moving
    // the minutes bar hides players without silently restating everyone else.
    const pool: Record<string, number[]> = {};
    const raw = new Map<Player, number>();
    for (const p of all) {
      const v = scoreOf(p);
      raw.set(p, v);
      (pool[p.p] ??= []).push(v);
    }
    for (const b of Object.keys(pool)) pool[b].sort((a, z) => a - z);
    const pctOf = (bucket: string, v: number) => {
      const arr = pool[bucket];
      if (!arr || arr.length < 2) return 50;
      let lo = 0;
      let hi = arr.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (arr[mid] < v) lo = mid + 1;
        else hi = mid;
      }
      return (lo / (arr.length - 1)) * 100;
    };

    // His standing in each SEASON separately, ranked inside that season's
    // bucket, so a floor is comparable with the pooled number above it.
    const perSeason: Record<string, Record<string, number>> = {};
    for (const v of data.views) {
      if (v.key === "total") continue;
      const rowsS = players[v.key] ?? [];
      const byBucket: Record<string, { key: string; v: number }[]> = {};
      for (const q of rowsS) {
        (byBucket[q.p] ??= []).push({ key: `${q.n}|${q.p}`, v: scoreOf(q) });
      }
      const out: Record<string, number> = {};
      for (const list of Object.values(byBucket)) {
        list.sort((a, b) => a.v - b.v);
        list.forEach((e, i) => {
          out[e.key] = list.length > 1 ? (i / (list.length - 1)) * 100 : 50;
        });
      }
      perSeason[v.key] = out;
    }
    const careerOf = (p: Player) => {
      const key = `${p.n}|${p.p}`;
      const vals = Object.values(perSeason)
        .map((m) => m[key])
        .filter((v) => v !== undefined);
      if (!vals.length) return { seasons: 0, floor: null as number | null, swing: null as number | null };
      return {
        seasons: vals.length,
        floor: Math.min(...vals),
        swing: vals.length > 1 ? Math.max(...vals) - Math.min(...vals) : null,
      };
    };

    const d = durability / 100;
    const scored = all
      .filter(
        (p) =>
          (isAll || p.p === pos || extra.includes(p.p)) && p.rs >= minShare,
      )
      .filter((p) => side === "any" || p.s.includes(side))
      // DEPARTED PLAYERS ARE OUT BY DEFAULT. The pooled view spans four
      // seasons, so without this the "best in the Premier League" table is
      // led by men who no longer play in it — Rodri, Alexander-Arnold,
      // Konaté, Gordon. The flag comes from the build, which knows who has
      // actually appeared this season; the toggle keeps the old behaviour
      // for anyone comparing across eras.
      .filter((p) => includeGone || !p.gone)
      // CLUB. Matched on the club the ROW is about, not the one he is at now,
      // because that is the club whose shirt the row's numbers were produced
      // in — a 23/24 row for a player since transferred describes what he did
      // THERE, and listing it under his new club would credit the wrong side.
      .filter((p) => activeTeam === ALL || p.t === activeTeam)
      .map((p) => {
        const pooled = pctOf(p.p, raw.get(p) ?? 0);
        const car = careerOf(p);
        // One season gives no floor to speak of, so he is judged on the
        // pooled number alone rather than penalised for arriving late.
        const floor = car.seasons > 1 && car.floor !== null ? car.floor : pooled;
        return {
          ...p,
          score: pooled * (1 - d) + floor * d,
          pooled,
          rawScore: raw.get(p) ?? 0,
          ...car,
        };
      });
    const pick = (p: (typeof scored)[number]) => {
      if (sort.key === "score") return p.score;
      if (sort.key === "m") return p.m;
      if (sort.key === "sh") return p.sh;
      if (sort.key === "n") return p.n;
      if (sort.key === "t") return p.t;
      if (sort.key === "s") return p.s;
      if (sort.key === "p") return p.p;
      if (sort.key === "floor") return p.floor ?? -Infinity;
      if (sort.key === "swing") return p.swing ?? Infinity;
      return (padj ? p.va : p.v)[sort.key] ?? -Infinity;
    };
    return scored.sort((a, b) => {
      const x = pick(a);
      const y = pick(b);
      if (typeof x === "string" || typeof y === "string") {
        return String(x).localeCompare(String(y)) * sort.dir;
      }
      return (x - y) * sort.dir;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, players, view, pos, isAll, side, allWeights, blockUnreliable, minShare, padj, sort, durability, includeGone, activeTeam, extra]);

  if (!data) {
    return <p className="text-[13.5px] text-ink-2">Loading the board…</p>;
  }

  // Every section is always rendered, collapsed when it carries no weight.
  // Filtering metrics out here instead used to delete whole sections from the
  // page — a reader had no way of knowing Goalkeeping existed at all.
  const shown = data.metrics;
  const cols = Object.entries(weights)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([k]) => k);
  const byKey = Object.fromEntries(data.metrics.map((m) => [m.key, m]));
  const bucket = data.buckets.find((b) => b.key === pos);
  const isTotal = view === "total";

  const byBucket = Object.fromEntries(data.buckets.map((b) => [b.key, b]));
  const zonedKeys = new Set(ZONES.flatMap((z) => z.keys));
  // Anything the zone map does not know about still gets a home, so adding a
  // bucket to the payload can never make it silently vanish from the rail.
  const unzoned = data.buckets.filter((b) => !zonedKeys.has(b.key));

  const pickPos = (key: string) => {
    // Weights are NOT reset here. Each bucket keeps its own set, so switching
    // position to check something no longer throws away what you had tuned.
    // "reset to preset" undoes it deliberately.
    setPos(key);
    setExtra([]);
    setSide("any");
    setOpenGroups({});
  };

  /** EVERY PILL IS A PLAIN TOGGLE. This first shipped as a modifier-click —
   *  plain click replaces, ⌘/Ctrl-click adds — which preserved the old
   *  single-select feel and was reported straight back as "I can't do multi
   *  select, it keeps toggling". That is the correct reaction: a control
   *  whose second behaviour is invisible has only one behaviour, and a hint
   *  line does not fix it. It also cannot work on a touch screen at all.
   *
   *  Click adds, click again removes, "All positions" clears. Selecting a
   *  second position now costs one extra click on the first — a real cost,
   *  and worth it for a control that does what it looks like it does. */
  const onPill = (key: string) => {
    if (key === ALL) {
      setPos(ALL);
      setExtra([]);
      return;
    }
    if (pos === key) {
      // Dropping the primary promotes the first companion, so the config
      // panel always has a position to edit and never blanks out.
      setPos(extra.length ? extra[0] : ALL);
      setExtra(extra.slice(1));
      return;
    }
    if (extra.includes(key)) {
      setExtra(extra.filter((k) => k !== key));
      return;
    }
    // Adding to nothing is the first pick, and only THAT resets side and the
    // open sections — adding a second position must not silently undo a
    // filter the reader set for the first.
    if (pos === ALL) pickPos(key);
    else setExtra([...extra, key]);
  };

  const posPill = (key: string, label: string, title?: string) => {
    const on = key === ALL ? isAll : pos === key || extra.includes(key);
    return (
      <button
        key={key}
        title={title}
        onClick={() => onPill(key)}
        className={`rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors ${
          on
            ? "border-home bg-[#e9f1f8] text-[#1c5b8a] shadow-[0_1px_2px_rgba(28,91,138,0.12)]"
            : "border-transparent bg-card/70 text-ink-2 hover:border-ink-3 hover:bg-card"
        }`}
      >
        {label}
      </button>
    );
  };

  const SIDE_LABEL: Record<string, string> = {
    R: "right side",
    L: "left side",
    C: "central",
  };
  const active: { label: string; clear: () => void }[] = [];
  if (!isAll && bucket) {
    active.push({
      label: bucket.label,
      clear: () => {
        setPos(extra.length ? extra[0] : ALL);
        setExtra(extra.slice(1));
      },
    });
  }
  for (const k of extra) {
    const b = byBucket[k];
    if (b) {
      active.push({
        label: b.label,
        clear: () => setExtra(extra.filter((x) => x !== k)),
      });
    }
  }
  if (activeTeam !== ALL) {
    active.push({ label: activeTeam, clear: () => setTeam(ALL) });
  }
  if (side !== "any") {
    active.push({ label: SIDE_LABEL[side] ?? side, clear: () => setSide("any") });
  }
  if (includeGone) {
    active.push({
      label: "including players who left",
      clear: () => setIncludeGone(false),
    });
  }
  // Only when the reader MOVED it. Untouched, the bar is chosen for them by
  // the effect above, and showing that as a filter they set would be a lie —
  // clearing it hands the choice back rather than jumping to a fixed rung.
  if (shareTouched) {
    active.push({
      label: `played at least ${minShare}%`,
      clear: () => setShareTouched(false),
    });
  }

  return (
    <div>
      {/* ------------------------------------------------ position rail
          The zone label sits ABOVE its pills rather than beside them. Inline,
          four labels cost about 240px of the rail's width and pushed Attack
          onto a second line; stacked they cost nothing, because each label is
          narrower than the pills beneath it. All nine positions then fit on
          one row, which is the whole point of grouping them. */}
      <div className="flex flex-wrap items-end gap-2">
        <span className="mb-1.5">
          {posPill(
            ALL,
            "All positions",
            "Every player in one table. Each is scored on the config for his own position, and a score is a percentile within that position — so 85 means top 15% at the job he does, whoever he is.",
          )}
        </span>
        {ZONES.map((zone) => {
          const inZone = zone.keys
            .map((k) => byBucket[k])
            .filter(Boolean) as typeof data.buckets;
          if (!inZone.length) return null;
          return (
            <div
              key={zone.label}
              className={`flex flex-col gap-1 rounded-xl border border-line ${zone.tint} px-2 py-1.5`}
            >
              <span className="px-1 text-[9.5px] font-semibold uppercase tracking-[0.08em] text-ink-3">
                {zone.label}
              </span>
              <div className="flex items-center gap-1.5">
                {inZone.map((b) => posPill(b.key, b.label, b.desc))}
              </div>
            </div>
          );
        })}
        {unzoned.length > 0 && (
          <div className="flex flex-col gap-1 rounded-xl border border-line bg-[#f5f5f5] px-2 py-1.5">
            <span className="px-1 text-[9.5px] font-semibold uppercase tracking-[0.08em] text-ink-3">
              Other
            </span>
            <div className="flex items-center gap-1.5">
              {unzoned.map((b) => posPill(b.key, b.label, b.desc))}
            </div>
          </div>
        )}
        <span className="mb-2 self-end text-[11px] text-ink-3">
          {extra.length > 0
            ? `${1 + extra.length} positions — each still scored and ranked within his own`
            : "click positions to add or remove them"}
        </span>
      </div>

      {/* ---------------------------------------------------- filter bar */}
      <div className={"mt-3 " + FILTER_BAR}>
        {/* LEAGUE. Percentiles are computed WITHIN a league, so this is not a
            filter over one table — it swaps the whole dataset, and the cached
            views are cleared with it. Hidden when only one league has been
            built, so it does not imply a choice that is not there. */}
        {index.length > 1 && (
          <Field
            label="league"
            title="Scores are percentiles within this league — a 90 here means top 10% of this league, not of Europe"
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
        {/* CLUB. Unlike league, this is a plain filter over one table — the
            percentiles behind every score stay the league's, so a club view
            shows where its players stand IN THE LEAGUE, not against each
            other. That is the useful question and the only honest one. */}
        <Field
          label="club"
          title="Filters the table to one club. Scores stay percentiles within the whole league, so this shows where a club's players stand in it — not against each other."
        >
          <select
            value={activeTeam}
            onChange={(e) => setTeam(e.target.value)}
            className={SELECT}
          >
            <option value={ALL}>All clubs</option>
            {clubs.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="side"
          title="A left winger and a right winger are ranked together, because they are asked for the same things. This only filters the list."
        >
          <select
            value={side}
            onChange={(e) => setSide(e.target.value)}
            className={SELECT}
          >
            <option value="any">both</option>
            <option value="R">right</option>
            <option value="L">left</option>
            <option value="C">central</option>
          </select>
        </Field>
        <Field
          label="played at least"
          title="His minutes IN THIS ROLE as a share of everything his club played in the period on show. A share rather than a minute count, so the same bar means the same thing five rounds into a season and across three of them."
        >
          <select
            value={minShare}
            onChange={(e) => {
              setMinShare(Number(e.target.value));
              setShareTouched(true);
            }}
            className={SELECT}
          >
            {SHARE_RUNGS.map((v) => (
              <option key={v} value={v}>
                {v}%
                {periodMin
                  ? ` — ${Math.round((periodMin * v) / 100).toLocaleString()} min`
                  : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="season"
          title="All seasons pools the raw events of every season, rather than averaging season ranks."
        >
          <select
            value={view}
            onChange={(e) => setView(e.target.value)}
            className={SELECT}
          >
            {data.views.map((v) => (
              <option key={v.key} value={v.key}>
                {v.label}
              </option>
            ))}
          </select>
        </Field>
        {/* The pooled view spans four seasons, so it lists everyone who has
            ever cleared the bar — including players who have left. A league
            ranking is about the league as it is now, so they are out by
            default and this brings them back for cross-era comparisons. */}
        <label
          className={CHECK_BOX}
          title="Players with no appearance in the season in progress are hidden by default"
        >
          <input
            type="checkbox"
            checked={includeGone}
            onChange={(e) => setIncludeGone(e.target.checked)}
            className="accent-home"
          />
          include players who left
        </label>
        <span className="num ml-auto self-center whitespace-nowrap text-[12.5px] text-ink-3">
          {loadingView ? "loading…" : `${rows.length} players`}
        </span>
      </div>

      <ActiveFilters active={active} />

      {league === ALL_LEAGUES && (
        <p className="mt-2 text-[11.5px] leading-relaxed text-[#6b5606]">
          Every score is a percentile <em>within its own league</em>, and the
          opponent adjustment behind it cannot cross one either. So this ranks
          who is most outstanding <b>for the league he plays in</b> — it is not
          a claim that a 90 in one league beats an 88 in another.
        </p>
      )}

      {bucket && (
        <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">{bucket.label}.</span>{" "}
          {bucket.desc}
        </p>
      )}
      {isAll && (
        <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
          <span className="font-semibold text-ink">Every position at once.</span>{" "}
          Each player is scored on the config for his own job — a keeper on the
          keeper weights, a striker on the striker weights — and every score is
          a percentile <em>within that position</em>. So 85 means top 15% at
          what he does, and the ranking asks who is most outstanding for his
          role rather than who is the better footballer. Pick a position to
          change its weights; the combined table picks them up.
        </p>
      )}

      {/* ==================================================== the config */}
      <section className="mt-4 rounded-xl border border-line bg-card">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2 border-b border-line px-4 py-3">
          <button
            onClick={() => setConfigOpen((o) => !o)}
            className="flex items-baseline gap-1.5 text-[14px] font-semibold hover:text-home"
          >
            <span className="text-ink-3">{configOpen ? "▾" : "▸"}</span>
            What counts as good — and you decide
          </button>
          <span className="num text-[12.5px]">
            <span
              className={
                spent === BUDGET
                  ? "font-semibold text-good"
                  : "font-semibold text-[#9a7400]"
              }
            >
              {spent}
            </span>
            <span className="text-ink-3"> / {BUDGET}</span>
            {blocked > 0 && (
              <span
                className="text-bad"
                title="These weights sit on metrics that do not repeat for this bucket, so the gate is ignoring them. Untick 'ignore metrics that don't repeat' to spend them anyway."
              >
                {" · "}
                {blocked} ignored
              </span>
            )}
          </span>
          <div className="h-1.5 w-32 overflow-hidden rounded-full bg-line">
            <div
              className={spent > BUDGET ? "h-full bg-bad" : "h-full bg-[#4a7ba6]"}
              style={{ width: `${Math.min(100, (spent / BUDGET) * 100)}%` }}
            />
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-ink-3">
            <span className="flex items-center gap-1">
              <i className="inline-block h-2 w-2 rounded-full bg-good" /> repeats
              <Info>
                <b className="text-ink">Repeats — rank correlation 0.60+.</b> The
                same players finish top of this metric season after season, so
                it is describing the footballer rather than the year he had.
                Take-ons for a winger sit at 0.79: Salah runs at people every
                season.
              </Info>
            </span>
            <span className="flex items-center gap-1">
              <i className="inline-block h-2 w-2 rounded-full bg-[#c99a1e]" /> marginal
              <Info>
                <b className="text-ink">Marginal — 0.40 to 0.60.</b> Some of
                last season&apos;s order survives into this one, a lot of it
                does not. Worth a small weight, not a big one. Interceptions
                for a full-back sit here at 0.46.
              </Info>
            </span>
            <span className="flex items-center gap-1">
              <i className="inline-block h-2 w-2 rounded-full bg-bad" /> noise
              <Info>
                <b className="text-ink">Noise — below 0.40.</b> Where a player
                ranked last season tells you nothing about where he ranks this
                season. Almost always a success <em>rate</em>: whether a duel
                came off depends more on who he faced than on him. Tackle
                success for a centre-back is −0.12, worse than a coin flip,
                while tackles attempted holds at 0.58.
              </Info>
            </span>
            <span className="flex items-center gap-1">
              <i className="inline-block h-2 w-2 rounded-full border border-ink-3" /> untested
              <Info>
                <b className="text-ink">Untested — not yet checkable.</b> The
                test needs the same player in the same role in two consecutive
                seasons, and too few qualify in this bucket — only eight men
                held down wing-back for a season. Unknown, not failed, so it
                is left uncoloured rather than being called good or bad. More
                seasons on disk clears it.
              </Info>
            </span>
          </div>
        </div>

        {configOpen && isAll && (
          <div className="p-4 text-[12.5px] leading-relaxed text-ink-2">
            There is no single set of weights that means anything across nine
            positions — a keeper cannot be scored on take-ons. So the combined
            table scores every player on his own bucket&apos;s config. Pick a
            position above to edit its weights, and come back here to see the
            effect.
          </div>
        )}
        {configOpen && !isAll && (
        <div className="p-4">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[12px]">
            <span className="text-ink-3">
              {left === 0
                ? "budget fully spent"
                : left > 0
                  ? `${left} left to spend`
                  : `${-left} over budget`}
            </span>
            {spent !== BUDGET && (
              <button onClick={balance} className="text-home hover:underline">
                balance to 100
              </button>
            )}
            <button
              onClick={() => setWeights(PRESETS[pos] ?? {})}
              className="text-ink-3 hover:text-ink hover:underline"
            >
              reset to preset
            </button>
            <label className="flex items-center gap-2 text-ink-2">
              <input
                type="checkbox"
                checked={blockUnreliable}
                onChange={(e) => setBlockUnreliable(e.target.checked)}
              />
              ignore metrics that don&apos;t repeat
            </label>
            <label
              className="flex items-center gap-2 text-ink-2"
              title="A defender at a dominant side contests ~16% fewer duels simply because opponents have less of the ball. This scales every rate to an even game so nobody is punished for their team being good."
            >
              <input
                type="checkbox"
                checked={padj}
                onChange={(e) => setPadj(e.target.checked)}
              />
              adjust for possession
            </label>
            <label
              className={`flex items-center gap-2 ${isTotal ? "text-ink-2" : "text-ink-3"}`}
              title={
                isTotal
                  ? "Blends his WORST season into the ranking. At 0 he is judged on all his football pooled; at 100 purely on his floor. The typical player swings 28 percentile points between seasons, so this moves things."
                  : "Needs more than one season — switch the view to All seasons."
              }
            >
              judge on his floor
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={durability}
                disabled={!isTotal}
                onChange={(e) => setDurability(Number(e.target.value))}
                className="w-24 accent-[#4a7ba6] disabled:opacity-40"
              />
              <span className="num w-8 text-[11.5px] text-ink-3">{durability}%</span>
            </label>
            <button
              onClick={() => {
                setShowAll((s) => !s);
                setOpenGroups({});
              }}
              className="ml-auto text-home hover:underline"
            >
              {showAll ? "collapse unused sections" : `expand all ${data.metric_groups.length} sections`}
            </button>
          </div>

          <div className="mt-3 grid items-start gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {data.metric_groups.map((mg) => {
              const items = shown.filter((m) => m.group === mg.key);
              if (!items.length) return null;
              const sub = groupTotal(mg.key);
              const open = openGroups[mg.key] ?? (showAll || sub > 0);
              return (
                <div
                  key={mg.key}
                  className="rounded-lg border border-line bg-[#fcfcfd]"
                >
                  <button
                    onClick={() =>
                      setOpenGroups((prev) => ({ ...prev, [mg.key]: !open }))
                    }
                    className="flex w-full items-center justify-between px-2.5 py-1.5 text-left"
                  >
                    <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-2">
                      <span className="text-ink-3">{open ? "▾" : "▸"}</span>
                      {mg.label}
                    </span>
                    <span className="num text-[11.5px] text-ink-3">
                      {sub > 0 ? sub : ""}
                    </span>
                  </button>
                  {open && (
                    <div className="border-t border-line px-2.5 pb-2">
                      {items.map((m) => {
                        const tone = relTone(rel(m.key), selfRel(m.key));
                        const w = weights[m.key] ?? 0;
                        return (
                          <div key={m.key} className="mt-2">
                            <div className="flex items-baseline justify-between gap-2">
                              {/* No `title` here: the Info icon sits inside
                                  this span, so a native tooltip on the parent
                                  fires over the popover and hides it. */}
                              <span
                                className={`flex items-baseline gap-1.5 text-[12.5px] ${tone.cls}`}
                              >
                                <i
                                  className={`inline-block h-2 w-2 shrink-0 translate-y-[-1px] rounded-full ${relDot(rel(m.key), selfRel(m.key))}`}
                                />
                                {m.label}
                                {m.invert ? " ↓" : ""}
                                <Info align="left">
                                  <b className="text-ink">{m.label}</b>
                                  {m.invert ? " — lower is better." : "."}{" "}
                                  {m.desc}
                                  <span className="mt-1.5 block border-t border-line pt-1.5">
                                    <b className="text-ink">
                                      For {bucket?.label.toLowerCase() ?? pos}:
                                    </b>{" "}
                                    {rel(m.key)
                                      ? `repeats season to season at ${rel(m.key)!.rho} (${rel(m.key)!.n} players).`
                                      : "not yet testable across seasons — too few players have held this role twice."}{" "}
                                    {selfRel(m.key)
                                      ? `Agrees with itself inside a season at ${selfRel(m.key)!.rho} (${selfRel(m.key)!.n}).`
                                      : ""}
                                  </span>
                                </Info>
                              </span>
                              <span className="num text-[11.5px] text-ink-3">
                                {w}
                              </span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={40}
                              value={w}
                              onChange={(e) =>
                                setWeight(m.key, Number(e.target.value))
                              }
                              className="w-full accent-[#4a7ba6]"
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        )}
      </section>

      {/* ===================================================== the board */}
      <div className="mt-6 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-[13.5px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-2 text-left font-semibold">#</th>
              <Th k="n" sort={sort} setSort={setSort} align="left">Player</Th>
              {isAll && (
                <Th k="p" sort={sort} setSort={setSort} align="left"
                    title="Which job this row is about. Every score is a percentile within the position, which is what makes them comparable across these.">
                  Pos
                </Th>
              )}
              <Th k="t" sort={sort} setSort={setSort} align="left">Team</Th>
              <Th k="s" sort={sort} setSort={setSort} align="left"
                  title="Which side of the pitch he played this role on. R/L means he genuinely played both.">
                Side
              </Th>
              <Th k="score" sort={sort} setSort={setSort}>Score</Th>
              {cols.map((c) => (
                <Th key={c} k={c} sort={sort} setSort={setSort} title={byKey[c]?.desc}>
                  {byKey[c]?.label}
                </Th>
              ))}
              {isTotal && (
                <>
                  <Th k="floor" sort={sort} setSort={setSort}
                      title="His worst single season, as a percentile in his position. The dependability question: how bad does he get?">
                    Floor
                  </Th>
                  <Th k="swing" sort={sort} setSort={setSort}
                      title="Best season minus worst. The median Premier League player moves 28 percentile points; van Dijk moves 4.">
                    Swing
                  </Th>
                </>
              )}
           
              <Th k="m" sort={sort} setSort={setSort}>Min</Th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 60).map((p, i) => {
              const vals = padj ? p.va : p.v;
              const pcts = padj ? p.qa : p.q;
              return (
                <tr key={`${p.n}-${p.p}`} className="border-t border-line hover:bg-[#fafbfc]">
                  <td className="num py-2 pl-4 pr-2 text-ink-3">{i + 1}</td>
                  <td className="whitespace-nowrap py-2 pr-3 font-medium">
                    {p.n}
                  </td>
                  {isAll && (
                    <td
                      className="whitespace-nowrap py-2 pr-3 text-[12px] font-medium text-ink-2"
                      title={posLabel(p.p)}
                    >
                      {posShort(p.p)}
                    </td>
                  )}
                  <td className="whitespace-nowrap py-2 pr-3 text-[12.5px] text-ink-2">
                    {p.t}
                    {/* In the pooled view the club alone does not say whose
                        league the percentile is of, and that is the one
                        thing a reader must not have to guess. */}
                    {p.lg && (
                      <span className="ml-1.5 rounded border border-line px-1 py-px text-[10px] text-ink-3">
                        {p.lg}
                      </span>
                    )}
                    {p.tn && (
                      <span
                        className="ml-1 text-[11px] text-ink-3"
                        title={`This row is his time at ${p.t}. He plays for ${p.tn} now.`}
                      >
                        → {p.tn}
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-2 pr-3 text-[12px] text-ink-3">
                    {SIDE_TAG[p.s] ?? p.s}
                  </td>
                  <td
                    className="px-3 py-1.5 text-ink"
                    title={`${p.score.toFixed(0)} of 100 among ${p.p}s on your config.
Underlying composite ${p.rawScore.toFixed(1)} — his average percentile across the weighted metrics, which is why it sits nearer the middle: nobody is top-10% at ten independent things at once.`}
                  >
                    <div className="flex justify-end">
                      <ScoreRing score={p.score} />
                    </div>
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c}
                      className="num px-2 py-2 text-right"
                      style={{ background: tint(pcts[c]) }}
                    >
                      {vals[c] === undefined ? (
                        <span className="text-ink-3">—</span>
                      ) : (
                        <>
                          {vals[c]}
                          <span className="ml-1 text-[11px] text-ink-3">
                            ({pcts[c] ?? "-"})
                          </span>
                        </>
                      )}
                    </td>
                  ))}
                  {isTotal && (
                    <>
                      <td className="num px-2 py-2 text-right text-[12px] text-ink-3">
                        {p.floor === null || p.seasons < 2
                          ? "—"
                          : p.floor.toFixed(0)}
                      </td>
                      <td
                        className="num px-2 py-2 text-right text-[12px]"
                        title={p.seasons === 1 ? "only one season on record" : `${p.seasons} seasons`}
                      >
                        {p.swing === null ? (
                          <span className="text-ink-3">—</span>
                        ) : (
                          <span className={p.swing <= 12 ? "text-good" : p.swing >= 35 ? "text-bad" : "text-ink-3"}>
                            {p.swing.toFixed(0)}
                          </span>
                        )}
                      </td>
                    </>
                  )}
                
                  <td className="num py-2 pl-2 pr-4 text-right text-[12px] text-ink-3">
                    {p.m.toLocaleString()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!rows.length && (
          <p className="p-4 text-[13px] text-ink-2">
            No players — give at least one metric a weight, or lower the
            minutes bar.
          </p>
        )}
      </div>

      <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
        Numbers are the raw per-90 or percentage, with the player&apos;s
        percentile within his bucket in brackets. Minutes are minutes{" "}
        <em>in that role</em>: a player who split his season between two
        positions appears in both tables, each row built only from the minutes
        he spent there. {data.min_share}% of his club&apos;s minutes required to appear at all. Data: {data.league},
        Opta event streams.
      </p>
    </div>
  );
}
