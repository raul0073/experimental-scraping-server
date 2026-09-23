"use client";

import { useMemo, useState } from "react";

import { Formation3D, type Field } from "./Formation3D";
import { PitchScene, defaultCam, type ViewName } from "./PitchScene";
import { useKit, useSquad } from "./useSquad";
import { MODEL_CREDIT, isComplete } from "../../lib/credits";

/** Average positions and passing, on the pitch, with territory underneath.
 *
 *  EVERYTHING HERE COMES OUT OF ONE FILE. The pass payload already carries
 *  every pass with its origin, its passer and its inferred receiver, so the
 *  nodes, the links and the density are all derived from the same rows in
 *  the browser. Three numbers that agree with each other beat three numbers
 *  assembled by three different scripts, and it means no new pipeline.
 *
 *  What that costs: this is a PASSING position, not a touch position. The
 *  flat chart on the team page averages every controlled action — tackles,
 *  take-ons, shots — and this averages where he passed from, which is about
 *  seven actions in ten. The caption says so. It is a narrower claim rather
 *  than a worse one.
 */

/** THE ELEVEN, THE LINKS AND THE BINS ALL COME FROM ONE PLACE.
 *  `useSquad` derives them in a single pass over the pass payload and the
 *  zone map uses the same hook, so the side standing on one picture is
 *  provably the side standing on the other. Two copies of an
 *  eleven-by-appearances rule is two copies that drift. */

/** Two passes of a box blur. Binned counts are spiky — one cell with nine
 *  and its neighbour with two is a rendering artefact of where the grid
 *  lines fell, not a fact about the player. */
function smooth(g: Float32Array, gw: number, gz: number, times = 2) {
  let cur = g;
  for (let t = 0; t < times; t++) {
    const out = new Float32Array(cur.length);
    for (let j = 0; j < gz; j++) {
      for (let i = 0; i < gw; i++) {
        let s = 0;
        let n = 0;
        for (let dj = -1; dj <= 1; dj++) {
          for (let di = -1; di <= 1; di++) {
            const x = i + di;
            const y = j + dj;
            if (x < 0 || y < 0 || x >= gw || y >= gz) continue;
            s += cur[y * gw + x];
            n++;
          }
        }
        out[j * gw + i] = s / n;
      }
    }
    cur = out;
  }
  return cur;
}

export function FormationView({
  team, season = "2526", height = 560, tune = false,
}: {
  team: string; season?: string; height?: number; tune?: boolean;
}) {
  const [view, setView] = useState<ViewName>(() => defaultCam("formation", "overhead"));
  const [minLink, setMinLink] = useState(0.35);

  const squad = useSquad(team, season);
  const { kit, hasModel } = useKit(team);
  const built = squad.loaded && squad.spots.length ? squad : null;
  const missing = squad.missing;

  const [selected, setSelected] = useState("");
  const spots = built?.spots ?? [];
  const sel = spots.find((s) => s.name === selected) ?? null;

  const field: Field | null = useMemo(() => {
    if (!built || !sel) return null;
    const raw = built.bins.get(sel.name);
    if (!raw) return null;
    const { gw, gz } = built.grid;
    const g = smooth(raw, gw, gz);
    let max = 0;
    for (const v of g) if (v > max) max = v;
    return { g, gw, gz, max };
  }, [built, sel]);

  const edges = useMemo(() => {
    if (!built) return [];
    const top = built.edges[0]?.n ?? 1;
    return built.edges.filter((e) => e.n >= top * minLink * 0.5);
  }, [built, minLink]);

  /** How much the average position means for the chosen player. Computed
   *  in the shared hook, where the rows already are. */
  const concentration = sel ? squad.near12.get(sel.name) ?? null : null;

  if (missing) {
    return (
      <p className="rounded-xl border border-line bg-card p-4 text-[13px] text-ink-2">
        No event data for {team} in {season}.
      </p>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[12px] text-ink-2">
          links shown
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minLink}
            onChange={(e) => setMinLink(Number(e.target.value))}
            className="w-28"
          />
          <span className="num text-ink-3">{edges.length}</span>
        </label>
        {selected && (
          <button
            onClick={() => setSelected("")}
            className="rounded-full border border-line bg-card px-3 py-0.5 text-[12px] text-ink-2 hover:border-ink-3"
          >
            clear {selected.split(" ").slice(-1)[0]}
          </button>
        )}
        <span className="ml-auto num text-[12.5px] text-ink-2">
          {squad.matches} matches · {spots.length} players ·{" "}
          {squad.everyone.length} used the ball
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-start gap-5">
        <div className="min-w-0 flex-1">
          <PitchScene
            height={height}
            view={view}
            onView={setView}
            tune={tune}
            scene="formation"
            caption={
              sel ? (
                <span>
                  <b className="text-ink">{sel.name}</b> — the surface is where
                  he actually passed from;{" "}
                  {concentration !== null && (
                    <>
                      only{" "}
                      <b className="text-ink">
                        {Math.round(concentration * 100)}%
                      </b>{" "}
                      of it happened within twelve metres of his own average
                      position.{" "}
                    </>
                  )}
                  Click him again to come back out.
                </span>
              ) : (
                <span className="text-ink-3">
                  Discs are average passing positions, sized by volume; each
                  lane is one direction of a pair, so the two sides of a
                  partnership are separate. Click a player to raise his
                  territory.
                </span>
              )
            }
          >
            <Formation3D
              spots={spots}
              edges={edges}
              field={field}
              selected={selected}
              model={hasModel}
              kit={kit}
              onSelect={setSelected}
            />
          </PitchScene>
          {hasModel && (
            <p className="mt-1 text-[11px] text-ink-3">
              {isComplete(MODEL_CREDIT) ? (
                <>
                  Player figure:{" "}
                  <a href={MODEL_CREDIT.url} className="underline"
                     target="_blank" rel="noreferrer noopener">
                    {MODEL_CREDIT.title}
                  </a>{" "}
                  by {MODEL_CREDIT.author}, licensed{" "}
                  <a href={MODEL_CREDIT.licenceUrl} className="underline"
                     target="_blank" rel="noreferrer noopener">
                    {MODEL_CREDIT.licence}
                  </a>.
                </>
              ) : (
                <span className="text-[#b45309]">
                  Player model is loaded but NOT YET ATTRIBUTED — CC-BY needs
                  a title, author and source before this can be published.
                  See app/lib/credits.ts.
                </span>
              )}
            </p>
          )}
        </div>

        <aside className="w-[268px] shrink-0 rounded-xl border border-line bg-card p-3.5 text-[12.5px] leading-relaxed text-ink-2">
          {sel ? (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                selected
              </div>
              <div className="mt-1 font-semibold text-ink">{sel.name}</div>
              <dl className="mt-2 space-y-1">
                <Row k="passes" v={sel.passes.toLocaleString()} />
                <Row k="matches" v={String(sel.apps)} />
                <Row
                  k="within 12m"
                  v={concentration !== null
                    ? `${Math.round(concentration * 100)}%`
                    : "—"}
                />
              </dl>
              <p className="mt-2.5 text-[11.5px] text-ink-3">
                The lower that number, the less his average position means —
                a shuttling midfielder sits in the valley between two peaks
                he actually occupied.
              </p>
              <div className="mt-3 text-[11px] uppercase tracking-wide text-ink-3">
                found most
              </div>
              <ul className="mt-1 space-y-0.5">
                {edges
                  .filter((e) => e.a === sel.name)
                  .slice(0, 5)
                  .map((e) => (
                    <li key={e.b} className="flex justify-between gap-3">
                      <span>{e.b.split(" ").slice(-1)[0]}</span>
                      <span className="num text-ink">{e.n}</span>
                    </li>
                  ))}
              </ul>
            </>
          ) : (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                no player selected
              </div>
              <p className="mt-1.5">
                <b className="text-ink">An average position is a mean</b>, and
                a mean of a wide cloud is a place nobody stood. On this side
                only the goalkeeper spends most of his time near his own
                average (65%); the busiest midfielder manages 15%.
              </p>
              <p className="mt-2">
                Each direction of a partnership gets its own lane, because
                plenty of them are one-way: Raya finds Gyökeres 53 times and
                gets one back. A single line would call that an exchange.
              </p>
              <p className="mt-2">
                Click a player and his real territory rises under the map.
                The dot on a peak is a man with a position; the dot in a
                valley is a man with two.
              </p>
              <p className="mt-2 text-[11.5px] text-ink-3">
                Positions here average where he PASSED from — about seven
                actions in ten. Receivers are inferred from the next touch.
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
