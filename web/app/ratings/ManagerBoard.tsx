"use client";

/** THE DATA LAYER AND THE THREE THINGS THAT SIT ON IT.
 *
 *  A static export has no server at runtime, so the page ships as HTML and
 *  asks for its JSON from the browser: the index of built leagues first, then
 *  one league's managers. Everything after that is arithmetic on numbers that
 *  are already comparable — a weighted mean, a shrinkage, a sort.
 *
 *  ONE LEAGUE AT A TIME, ON PURPOSE. Every percentile in the payload is
 *  computed WITHIN a league and the opponent adjustment behind it is fitted
 *  within a league-season. Neither can cross a border, so there is no pooled
 *  view here and there should not be one: a 70 in one league does not beat a
 *  68 in another, and a table that put them in one list would be claiming it
 *  does.
 *
 *  NOTHING IS RESET IN AN EFFECT. Every piece of fetched state is stored with
 *  the league key it belongs to, and what is on screen is DERIVED from that
 *  key matching the current one. The obvious alternative — clearing the
 *  payload synchronously when the league changes — is a cascading render, and
 *  worse, it has a frame in which the old league's rows are still mounted
 *  under the new league's heading. Percentiles from two leagues must never
 *  appear in one list even for a frame.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ActiveFilters, BUDGET, CHECK_BOX, FILTER_BAR, Field, SELECT,
} from "./scoreUi";
import { Fingerprint } from "./Fingerprint";
import { RankTable, type Row, type Sort } from "./RankTable";
import { WeightEditor } from "./WeightEditor";
import { samplePayload } from "./sample";
import { useStoredWeights } from "./weights";
import {
  type LeagueRef,
  type Metric,
  type Payload,
  type Slot,
  DATA,
  defaultsFor,
  keptOf,
  orient,
  rowId,
  scoreRow,
} from "./contract";

const SAMPLE_SCOPE = "__sample__";

/** The pooled LIST. Not a pooled score — see the fetch below. */
const ALL_LEAGUES = "__all__";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return (await r.json()) as T;
}

/** A fetch that has finished, tagged with what it was for. `payload: null`
 *  means the file is not there — which is a real answer, not a pending one. */
type Loaded = { key: string; payload: Payload | null };

export function ManagerBoard() {
  const [index, setIndex] = useState<LeagueRef[]>([]);
  const [indexState, setIndexState] = useState<"loading" | "ok" | "failed">(
    "loading",
  );
  const [league, setLeague] = useState("");
  const [clubPick, setClubPick] = useState("");
  const [minMatches, setMinMatches] = useState(0);
  /** ON BY DEFAULT. The payload holds every spell over four seasons, which is
   *  the right thing to KEEP — it is what the history is for — but the wrong
   *  thing to open on. A reader arriving at a manager ranking wants the men
   *  currently doing the job, not sixty-nine spells of which two thirds
   *  belong to the past. The toggle turns the archive back on. */
  const [activeOnly, setActiveOnly] = useState(true);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [crestsFor, setCrestsFor] = useState<{
    key: string;
    crests: Record<string, string>;
    /** The clubs in this league NOW. The payload spans four seasons, so it
     *  carries relegated sides too, and "in charge now" without this listed
     *  the last man at Luton and Sheffield United as current managers. */
    current: string[];
  } | null>(null);
  /** The sample payload when the reader asked to see the layout, null
   *  otherwise. It is never a fallback for a failed fetch. */
  const [sample, setSample] = useState<Payload | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  /** CLOSED UNTIL ASKED FOR. The fingerprint is a feature of the page, not
   *  the page — it opens itself the moment a reader picks somebody with the
   *  A/B buttons, and otherwise stays out of the way of the ranking. */
  const [printOpen, setPrintOpen] = useState(false);
  const [sort, setSort] = useState<Sort>({ key: "score", dir: -1 });
  /** null until the reader chooses; after that their choice is respected
   *  exactly, including a deliberate clear. `scope` ties it to the league it
   *  was made in, so switching leagues starts fresh. */
  const [pick, setPick] = useState<{
    scope: string;
    a: string | null;
    b: string | null;
  } | null>(null);

  const { stored, save, clear } = useStoredWeights();

  // -------------------------------------------------------------- the index
  useEffect(() => {
    let alive = true;
    getJson<{ leagues?: LeagueRef[] }>(`${DATA}/index.json`)
      .then((idx) => {
        if (!alive) return;
        const ls = idx.leagues ?? [];
        setIndex(ls);
        setIndexState(ls.length ? "ok" : "failed");
        if (ls.length) setLeague((cur) => cur || ls[0].key);
      })
      .catch(() => {
        if (!alive) return;
        setIndex([]);
        setIndexState("failed");
      });
    return () => {
      alive = false;
    };
  }, []);

  // ------------------------------------------------------------ one league
  //
  // ALL LEAGUES pools the five payloads and CHANGES NOTHING ELSE. Every
  // percentile and every score in them was computed inside its own league and
  // stays exactly as published — this view sorts them into one list, it does
  // not re-rank them against each other. That distinction is the whole reason
  // the module docstring above says there is no pooled view: there still is
  // no pooled SCORE, only a pooled LIST, and the note under the table says so
  // rather than leaving a reader to assume a 70 in one league beats a 68 in
  // another. The club column carries its league so no row is ambiguous.
  useEffect(() => {
    if (!league) return;
    let alive = true;
    if (league === ALL_LEAGUES) {
      Promise.all(
        index.map((l) =>
          getJson<Payload>(`${DATA}/${l.key}.json`)
            .then((p) => ({ ...p, _lg: l.label } as Payload & { _lg: string }))
            .catch(() => null),
        ),
      ).then((parts) => {
        if (!alive) return;
        const got = parts.filter(Boolean) as (Payload & { _lg: string })[];
        if (!got.length) {
          setLoaded({ key: league, payload: null });
          return;
        }
        setLoaded({
          key: league,
          payload: {
            ...got[0],
            league: "All leagues",
            metrics: got[0].metrics,
            managers: got.flatMap((p) =>
              p.managers.map((m) => ({ ...m, league: p._lg })),
            ),
          },
        });
      });
      return () => {
        alive = false;
      };
    }
    getJson<Payload>(`${DATA}/${league}.json`)
      .then((p) => alive && setLoaded({ key: league, payload: p }))
      .catch(() => alive && setLoaded({ key: league, payload: null }));
    return () => {
      alive = false;
    };
  }, [league, index]);

  /** Badges are borrowed from the team payload, which already holds one per
   *  club. Missing is fine and common — Crest renders nothing rather than a
   *  broken image — so a failure here resolves to no badges rather than an
   *  error. */
  useEffect(() => {
    if (!league) return;
    let alive = true;
    getJson<{ crests?: Record<string, string>; current_teams?: string[] }>(
      `/data/team/${league}/meta.json`,
    )
      .then(
        (m) =>
          alive
          && setCrestsFor({
            key: league,
            crests: m.crests ?? {},
            current: m.current_teams ?? [],
          }),
      )
      .catch(
        () => alive && setCrestsFor({ key: league, crests: {}, current: [] }),
      );
    return () => {
      alive = false;
    };
  }, [league]);

  // ------------------------------------------- what is actually on show now
  const scope = sample ? SAMPLE_SCOPE : league;
  const payload: Payload | null =
    sample ?? (loaded && loaded.key === league ? loaded.payload : null);
  const crests =
    !sample && crestsFor && crestsFor.key === league ? crestsFor.crests : {};
  /** Empty on the sample and while the meta is in flight, which the filter
   *  reads as "no list, so do not narrow" rather than "no clubs qualify". */
  const currentTeams =
    !sample && crestsFor && crestsFor.key === league ? crestsFor.current : [];
  const ready = payload !== null;
  const missing =
    !ready &&
    (indexState === "failed" || (!!loaded && loaded.key === league));

  // ------------------------------------------------------------- the metrics
  const directional = useMemo<Metric[]>(
    () => (payload?.metrics ?? []).filter((m) => m.directional),
    [payload],
  );
  const fingerprint = useMemo<Metric[]>(
    () => (payload?.metrics ?? []).filter((m) => !m.directional),
    [payload],
  );

  const defaults = useMemo(() => defaultsFor(directional), [directional]);

  /** A stored config is the whole config: a key it does not mention is a key
   *  the reader left at zero, not a key that should quietly inherit a default.
   *  That also means a metric added to the bank after a reader saved arrives
   *  unweighted, which is the honest default — they never chose it. */
  const weights = useMemo(() => {
    if (!stored) return defaults;
    const out: Record<string, number> = {};
    for (const m of directional) out[m.key] = stored[m.key] ?? 0;
    return out;
  }, [stored, defaults, directional]);

  /** Raising one weight can never push the config past the budget: the slider
   *  stops where the remaining room does, so a weighting stays a set of
   *  trade-offs rather than a wish list. */
  const setWeight = useCallback(
    (key: string, value: number) => {
      const used = Object.values(weights).reduce((a, b) => a + (b || 0), 0);
      const room = BUDGET - used + (weights[key] ?? 0);
      save({ ...weights, [key]: Math.max(0, Math.min(value, room)) });
    },
    [weights, save],
  );

  // --------------------------------------------------------------- the rows
  const rows = useMemo<Row[]>(() => {
    const src = payload?.managers ?? [];
    const scored: Row[] = src.map((r) => ({
      ...r,
      s: scoreRow(r, directional, weights),
    }));
    const metric = directional.find((m) => m.key === sort.key);
    const pickVal = (r: Row): number | string => {
      if (sort.key === "manager") return r.manager ?? "";
      if (sort.key === "team") return r.team ?? "";
      if (sort.key === "matches") return r.matches ?? 0;
      if (sort.key === "kept") return keptOf(r);
      // A directional column sorts on its ORIENTED percentile, so "best
      // first" stays best first on a metric where lower is better.
      if (metric) return orient(r.pct?.[metric.key], metric) ?? -Infinity;
      return r.s?.final ?? -Infinity;
    };
    return scored.sort((a, b) => {
      const x = pickVal(a);
      const y = pickVal(b);
      return typeof x === "string" || typeof y === "string"
        ? String(x).localeCompare(String(y)) * sort.dir
        : (x - y) * sort.dir;
    });
  }, [payload, directional, weights, sort]);

  /** Opens on the two best spells by the reader's own weights, so the
   *  comparison is showing something the moment the page settles rather than
   *  asking for two choices before it will draw anything. Derived, not set in
   *  an effect: a choice that belongs to another league simply stops
   *  applying. */
  const chosen = useMemo<Record<Slot, string | null>>(() => {
    const ids = new Set(rows.map(rowId));
    if (pick && pick.scope === scope) {
      const keep = (v: string | null) => (v && ids.has(v) ? v : null);
      return { a: keep(pick.a), b: keep(pick.b) };
    }
    // NOTHING IS CHOSEN UNTIL THE READER CHOOSES. This used to open on the
    // two highest-scoring spells, which put a head-to-head on the page that
    // nobody asked for and made a comparison look like the point of the page
    // rather than a thing you can do on it. The players board does not
    // pre-compare two men either; a comparison is a question, and the page
    // should not answer one that was not asked.
    return { a: null, b: null };
  }, [rows, pick, scope]);

  const onPick = useCallback(
    (slot: Slot, id: string) => {
      // Opening on pick is the whole reason this is discoverable: the A and B
      // buttons sit in the table, the fingerprint is collapsed below it, and
      // without this a reader would press A and watch nothing happen.
      setPrintOpen(true);
      setPick({
        scope,
        a: chosen.a,
        b: chosen.b,
        // Pressing the button a row is already on clears it; the select box
        // passes "" for its "nobody" option, which clears it too.
        [slot]: chosen[slot] === id ? null : id || null,
      });
    },
    [chosen, scope],
  );

  const enterSample = useCallback(() => {
    setSample(samplePayload());
    setPick(null);
  }, []);
  const exitSample = useCallback(() => {
    setSample(null);
    setPick(null);
  }, []);

  // ------------------------------------------------------------- filtering
  //
  // ABOVE THE EMPTY-STATE RETURN, and it has to be. These four sat below it
  // and React threw "a change in the order of Hooks called by ManagerBoard"
  // the moment the payload arrived: the loading render returns early and runs
  // fewer hooks than the render after it. A hook cannot live after a
  // conditional return — the same mistake, in the same session, as the club
  // list on the player board.

  /** THE CURRENT MAN AT EACH CLUB, defined as his LATEST spell there rather
   *  than by a date. A date test needs a notion of "this season" that breaks
   *  every August and in any league whose calendar differs; the last spell a
   *  club has is the man in charge of it, in every league, for ever. */
  const activeIds = useMemo(() => {
    // 🐛 WITHOUT current_teams THIS LISTED RELEGATED CLUBS. The payload spans
    // four seasons, so "the latest spell at each club" happily returned the
    // last man at Luton and Sheffield United — clubs that have not been in
    // this league for two years — and called them managers in charge now.
    // Being the most recent manager of a club is not the same as being a
    // manager in the league.
    const inLeague = currentTeams.length ? new Set(currentTeams) : null;
    const latest = new Map<string, Row>();
    for (const r of rows) {
      if (inLeague && !inLeague.has(r.team)) continue;
      const cur = latest.get(r.team);
      if (!cur || String(r.end ?? "") > String(cur.end ?? "")) {
        latest.set(r.team, r);
      }
    }
    return new Set([...latest.values()].map(rowId));
  }, [rows, currentTeams]);

  const clubs = useMemo(
    () => [...new Set(rows.map((r) => r.team))].sort((a, b) =>
      a.localeCompare(b),
    ),
    [rows],
  );

  /** FILTERED AFTER SORTING, never before. Every percentile in the payload
   *  was computed across the whole league; the rank column and the colour
   *  scale both mean "against this league", so narrowing the list must not
   *  change what any number says. It only changes which rows are on screen. */
  const club = clubs.includes(clubPick) ? clubPick : "";
  const shown = useMemo(
    () =>
      rows.filter(
        (r) =>
          (!club || r.team === club)
          && (r.matches ?? 0) >= minMatches
          && (!activeOnly || activeIds.has(rowId(r))),
      ),
    [rows, club, minMatches, activeOnly, activeIds],
  );
  const rankOf = useMemo(
    () => new Map(rows.map((r, i) => [r, i + 1] as const)),
    [rows],
  );

  // ------------------------------------------------------------ empty state
  if (!ready) {
    return (
      <div>
        <div className="rounded-xl border border-line bg-card p-4 sm:p-5">
          {!missing ? (
            <p className="text-[13.5px] text-ink-2">Loading the managers…</p>
          ) : (
            <>
              <p className="text-[14px] font-semibold">
                The manager ranking has not been built yet.
              </p>
              <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-ink-2">
                This page reads{" "}
                <code className="rounded bg-[#f4f6f8] px-1 py-px text-[12px]">
                  /data/managers/index.json
                </code>{" "}
                and one file per league beside it, written by the pipeline
                alongside the rest of the site&apos;s payloads. Nothing is
                wrong; the files are simply not there yet.
              </p>
              <button
                onClick={enterSample}
                className="mt-3 rounded-md border border-line px-3 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:border-ink-3 hover:text-ink"
              >
                Show the layout with invented numbers
              </button>
              <p className="mt-1.5 text-[11.5px] text-ink-3">
                Nothing in that sample was measured. It exists so the page can
                be looked at, and everything drawn from it says so.
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  const active: { label: string; clear: () => void }[] = [];
  if (club) active.push({ label: club, clear: () => setClubPick("") });
  if (minMatches > 0) {
    active.push({
      label: `${minMatches}+ matches`,
      clear: () => setMinMatches(0),
    });
  }
  if (activeOnly) {
    active.push({
      label: "in charge now",
      clear: () => setActiveOnly(false),
    });
  }

  const spellWord = shown.length === 1 ? "spell" : "spells";
  const hasLeaguePicker = !sample && index.length > 1;

  return (
    <div>

      {sample && (
        <div className="mb-4 rounded-lg border border-[#e2cc8f] bg-[#fdf8ea] px-3 py-2 text-[12.5px] leading-relaxed text-[#7a5f14]">
          <b>Sample data — nothing here was measured.</b> The managers and the
          clubs are invented and so are the numbers. This is the layout, not a
          ranking.{" "}
          <button onClick={exitSample} className="underline underline-offset-2">
            back to the real thing
          </button>
        </div>
      )}

      <div className={FILTER_BAR}>
        {hasLeaguePicker && (
          <Field
            label="league"
            title="Percentiles are computed inside one league. There is no pooled view, because a score in one league cannot be compared with a score in another."
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
        <Field label="club" title="Every spell at one club, including the men who came before.">
          <select
            value={club}
            onChange={(e) => setClubPick(e.target.value)}
            className={SELECT}
          >
            <option value="">All clubs</option>
            {clubs.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        {/* A LENGTH BAR, NOT AN EXCLUSION RULE. Short spells are already
            handled honestly by shrinkage, so this is for a reader who wants
            to see only men with a real body of work — not a correction. */}
        <Field
          label="at least"
          title="Spells shorter than this are hidden. They are not wrong — their scores are already pulled toward 50 by how little evidence they carry — this simply takes them off the page."
        >
          <select
            value={minMatches}
            onChange={(e) => setMinMatches(Number(e.target.value))}
            className={SELECT}
          >
            {[0, 10, 20, 38, 76].map((v) => (
              <option key={v} value={v}>
                {v === 0 ? "any length" : `${v}+ matches`}
              </option>
            ))}
          </select>
        </Field>
        <label
          className={CHECK_BOX}
          title="Only the man currently at each club — his latest spell there. The rest of the list is everyone who has held the job while we have events for it."
        >
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
            className="accent-home"
          />
          in charge now
        </label>
        <span className="num ml-auto self-center whitespace-nowrap text-[12.5px] text-ink-3">
          {shown.length}
          {shown.length !== rows.length ? ` of ${rows.length}` : ""} {spellWord}
          {!sample && payload.generated ? ` · built ${payload.generated}` : ""}
        </span>
      </div>

      <ActiveFilters active={active} />

      <p className="mt-2 text-[12px] leading-relaxed text-ink-2">
        Every manager who has taken a side in this league, for as long as we
        have events for it. The number in the first column is his rank in the
        whole league and does not change when you filter.
      </p>

      <WeightEditor
        directional={directional}
        weights={weights}
        setWeight={setWeight}
        reset={clear}
        dirty={stored !== null}
        open={configOpen}
        setOpen={setConfigOpen}
      />

      <Fingerprint
        fingerprint={fingerprint}
        rows={rows}
        pick={chosen}
        onPick={onPick}
        open={printOpen}
        setOpen={setPrintOpen}
      />

      <RankTable
        rows={shown}
        rankOf={rankOf}
        directional={directional}
        sort={sort}
        setSort={setSort}
        pick={chosen}
        onPick={onPick}
        crests={crests}
      />

      <p className="mt-8 max-w-3xl text-[12px] leading-relaxed text-ink-3">
        One row is one manager at one club, stitched from the man named on each
        match — so a manager who came back to a club appears twice, which is
        two jobs and not one. Every metric is measured per match and then
        aggregated over the spell as a ratio of sums, never as the average of
        per-match ratios: one low-denominator afternoon would otherwise decide
        a season. Percentiles are within this league only. A metric that could
        not be computed for a spell is shown as a dash and dropped from that
        spell&apos;s score rather than filled in at average.
      </p>
    </div>
  );
}
