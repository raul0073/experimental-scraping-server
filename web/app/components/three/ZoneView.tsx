"use client";

import { useEffect, useMemo, useState } from "react";

import { Formation3D } from "./Formation3D";
import { PitchScene, defaultCam, type ViewName } from "./PitchScene";
import { useKit, useSquad } from "./useSquad";
import { CELLS, ZoneHeat, cellLabel, type ZoneValues } from "./ZoneHeat";

/** A club's zone map on the pitch, with the numbers beside it.
 *
 *  The data is already on disk and already careful, so this reads it rather
 *  than deriving anything new:
 *
 *    z_{cell}_n   share of the ball there, scored AGAINST WHAT A TYPICAL
 *                 SIDE MANAGES IN THAT CELL. The normalisation is the
 *                 whole point — your attacking centre is the opponent's
 *                 defensive centre, where they have the ball while playing
 *                 out, so a flat midpoint would call every side in the
 *                 league weak in its own attacking third.
 *    zoc_{cell}   chances against them that BEGAN there — the cell the ball
 *                 was played from, not where the shot was hit. Mapping
 *                 where shots are taken makes every side red in front of
 *                 its own keeper, which is true and tells you nothing.
 */

type Row = Record<string, string | number | undefined> & {
  team: string; season?: string; matches?: number;
};

const DATA = "/data/team/eng-premier-league";

const SIDES = [
  { key: "with", label: "With the ball" },
  { key: "against", label: "Where they are got at" },
] as const;

/** Which column a cell's number lives in. Module level rather than a closure
 *  inside the component: defined inline it is a new function on every render,
 *  so every memo that used it would either rebuild constantly or lie about
 *  its dependencies. */
const field = (side: "with" | "against", cell: string) =>
  side === "with" ? `z_${cell}_n` : `zoc_${cell}`;

export function ZoneView({
  team, season = "2526", height = 560, tune = false,
}: {
  team: string; season?: string; height?: number; tune?: boolean;
}) {
  const [side, setSide] = useState<"with" | "against">("with");
  const [showSide, setShowSide] = useState(true);
  const squad = useSquad(team, season);
  const { kit, hasModel } = useKit(team);
  const [view, setView] = useState<ViewName>(() => defaultCam("zones", "overhead"));
  const [got, setGot] = useState<Row[] | null>(null);

  useEffect(() => {
    let live = true;
    fetch(`${DATA}/club_season.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => live && setGot(Array.isArray(d) ? d : d ? Object.values(d) : null))
      .catch(() => live && setGot(null));
    return () => {
      live = false;
    };
  }, []);

  const league = useMemo(
    () => (got ?? []).filter((r) => r.season === season),
    [got, season],
  );
  const row = league.find((r) => r.team === team) ?? null;

  const values: ZoneValues = useMemo(() => {
    const out: ZoneValues = {};
    if (row) {
      for (const c of CELLS) {
        const v = row[field(side, c)];
        out[c] = typeof v === "number" ? v : undefined;
      }
    }
    return out;
  }, [row, side]);

  /** 🐛 THE SCALE WAS THE LEAGUE'S, AND IT KILLED THE PICTURE.
   *
   *  Chances conceded were scaled 0 to the league's worst cell, 2.19. A good
   *  side's own fifteen then span 0.39 to 0.57 of the ramp and every cell
   *  comes out the same yellow-green — the map looked broken rather than
   *  flattering. Comparability between clubs is not worth a map that cannot
   *  show the one club it is about.
   *
   *  So the COLOUR is the club's own range, and the LEAGUE COMPARISON is a
   *  number in the sidebar ("3rd of 20 here"), which is exactly the division
   *  of labour this kind of view wants: the picture shows shape, numbers
   *  carry precision.
   *
   *  Share of the ball keeps 0-100 because that number already means
   *  something absolute — 50 is a typical side in that cell — and rescaling
   *  it to the club's own spread would throw that away.
   */
  const [lo, hi] = useMemo(() => {
    if (side === "with") return [0, 100];
    let min = Infinity;
    let max = -Infinity;
    for (const c of CELLS) {
      const v = row?.[`zoc_${c}`];
      if (typeof v === "number") {
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
    if (!Number.isFinite(min)) return [0, 1];
    // a floor under the span, so a side whose cells barely differ is not
    // amplified into a dramatic map by rounding noise
    return [min, Math.max(max, min + 0.15)];
  }, [row, side]);

  const [selected, setSelected] = useState("");
  const v = selected ? values[selected] : undefined;

  /** Where this cell sits among the fifteen for this side. The colour says
   *  hot or cold; the rank says whether that is unusual for them. */
  const rank = useMemo(() => {
    if (!selected || typeof v !== "number") return null;
    const all = CELLS.map((c) => values[c]).filter(
      (x): x is number => typeof x === "number",
    );
    const above = all.filter((x) => x > v).length;
    return { at: above + 1, of: all.length };
  }, [selected, v, values]);

  /** And where they sit in the LEAGUE in this cell, which is the question
   *  the map itself cannot answer — a cell can be their hottest and still
   *  be nothing much by the standards of the division. */
  const inLeague = useMemo(() => {
    if (!selected || typeof v !== "number" || !league.length) return null;
    const all = league
      .map((r) => r[field(side, selected)])
      .filter((x): x is number => typeof x === "number");
    if (all.length < 4) return null;
    const above = all.filter((x) => x > v).length;
    return { at: above + 1, of: all.length };
  }, [selected, v, league, side]);

  const explain = () => {
    if (!selected) return null;
    const where = cellLabel(selected);
    if (typeof v !== "number") return `No data for the ${where}.`;
    if (side === "with") {
      const much = v >= 80 ? "far more" : v >= 60 ? "more"
        : v >= 40 ? "about as much" : v >= 20 ? "less" : "far less";
      return `${team} have ${much} of the ball in the ${where} than a typical side does there — ${v.toFixed(0)} out of 100 against the rest of the league.`;
    }
    return `${v.toFixed(2)} chances a match against ${team} begin in the ${where}, counted where the ball was played FROM rather than where the shot was hit. High here is the route opponents use to get at them.`;
  };

  if (got && !row) {
    return (
      <p className="rounded-xl border border-line bg-card p-4 text-[13px] text-ink-2">
        No zone data for {team} in {season}.
      </p>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {SIDES.map((s) => (
          <button
            key={s.key}
            onClick={() => {
              setSide(s.key);
              setSelected("");
            }}
            className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium transition-colors ${
              side === s.key
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {s.label}
          </button>
        ))}
        <label className="flex items-center gap-1.5 text-[12px] text-ink-2">
          <input type="checkbox" checked={showSide}
                 onChange={(e) => setShowSide(e.target.checked)} />
          show the side
        </label>
        <span className="ml-auto num text-[12.5px] text-ink-2">
          {row?.matches ?? 0} matches ·{" "}
          {side === "with" ? "0-100 against the league" : "chances a match"}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-start gap-5">
        <div className="min-w-0 flex-1">
          <PitchScene
            height={height}
            view={view}
            onView={setView}
            tune={tune}
            scene="zones"
            legend={
              <span className="flex items-center gap-2 text-[11.5px] text-ink-3">
                {side === "with" ? "0" : "their lowest"}
                <span
                  className="inline-block h-2.5 w-24 rounded-sm"
                  style={{
                    background:
                      "linear-gradient(90deg,#26965c,#f6ce24,#e22a20)",
                  }}
                />
                {side === "with" ? "100" : "their highest"}
              </span>
            }
            caption={
              selected ? (
                <span>
                  <b className="text-ink">{cellLabel(selected)}</b> — click it
                  again to clear.
                </span>
              ) : (
                <span className="text-ink-3">
                  Colour is the measure, smoothed between the fifteen cells;
                  the painted grid is the cells themselves, so you can see
                  which numbers it was built from. Click one for its data.
                </span>
              )
            }
          >
            <ZoneHeat
              values={values}
              lo={lo}
              hi={hi}
              curve={side === "with" ? "linear" : "sqrt"}
              decimals={side === "with" ? 0 : 2}
              selected={selected}
              onSelect={setSelected}
            />
            {/* THE SIDE, AS CONTEXT ONLY. A hot cell is a fact about a
                place; the eleven standing in it are the reason. No lanes
                and no territory here — this is the zone map, and a passing
                network over a heat map is two pictures fighting. */}
            {showSide && squad.spots.length > 0 && (
              <Formation3D
                spots={squad.spots}
                edges={[]}
                field={null}
                selected=""
                model={hasModel}
                kit={kit}
                onSelect={() => {}}
              />
            )}
          </PitchScene>
        </div>

        <aside className="w-[280px] shrink-0 rounded-xl border border-line bg-card p-3.5 text-[12.5px] leading-relaxed text-ink-2">
          {selected ? (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                selected zone
              </div>
              <div className="mt-1 font-semibold capitalize text-ink">
                {cellLabel(selected)}
              </div>
              <div className="num mt-2 text-[26px] font-bold leading-none text-ink">
                {typeof v === "number"
                  ? side === "with" ? v.toFixed(0) : v.toFixed(2)
                  : "—"}
              </div>
              <div className="text-[11.5px] text-ink-3">
                {side === "with" ? "out of 100 vs the league here"
                                 : "chances against, per match"}
              </div>
              <p className="mt-2.5">{explain()}</p>
              <dl className="mt-3 space-y-1">
                {rank && (
                  <Row k="among their 15" v={`${rank.at} of ${rank.of}`} />
                )}
                {inLeague && (
                  <Row k="in the league here"
                       v={`${inLeague.at} of ${inLeague.of}`} />
                )}
                <Row k="matches" v={String(row?.matches ?? "—")} />
              </dl>
              {rank && inLeague && (
                <p className="mt-2.5 text-[11.5px] text-ink-3">
                  Their own hottest cell can still be ordinary for the
                  division — the first line is about them, the second about
                  everyone.
                </p>
              )}
            </>
          ) : (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                no zone selected
              </div>
              <p className="mt-1.5">
                {side === "with" ? (
                  <>
                    <b className="text-ink">Measured cell by cell.</b> Your
                    attacking centre is the opponent&apos;s defensive centre,
                    where they have the ball while playing out — so a flat
                    midpoint would call every side in the league weak in its
                    own attacking third. Each cell is scored against what a
                    typical side manages <i>there</i>.
                  </>
                ) : (
                  <>
                    <b className="text-ink">Where the chance began</b>, not
                    where the shot was hit. Mapping shots makes every side in
                    the league red in front of its own keeper, which is true
                    and tells you nothing; this says which route opponents
                    actually use.
                  </>
                )}
              </p>
              <p className="mt-2 text-[11.5px] text-ink-3">
                No columns on purpose. A zone value is one number per place,
                and colour on the plane is what that wants — height would
                turn the pitch into a bar chart in perspective and hide the
                thing it stands on.
              </p>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-3">{k}</dt>
      <dd className="num text-ink">{v}</dd>
    </div>
  );
}
