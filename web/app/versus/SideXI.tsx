"use client";

import { useState } from "react";

import { Formation3D } from "../components/three/Formation3D";
import { PitchScene, defaultCam, type ViewName } from "../components/three/PitchScene";
import { territoryFor, useKit, useSquad } from "../components/three/useSquad";
import { TeamHead } from "./TeamHead";

/** One side's eleven on the pitch, with the lab's interactivity kept.
 *
 *  THE STRIPPED VERSION WAS WRONG. The first attempt took the controls off
 *  on the reasoning that a match page is a glance rather than a study — but
 *  a picture you cannot interrogate is a picture nobody trusts, and the
 *  whole point of putting these here was to show the working. So the slider
 *  and the click are back: they are what makes it evidence instead of
 *  decoration.
 *
 *  What is dropped is only the side panel, because two of these sit beside
 *  each other and the numbers would be four columns of text where the
 *  pictures should be. Everything it said is in the caption instead.
 */

/** OPEN WITH EVERY LANE SHOWING. This started at 0.62 on the reasoning that
 *  a hundred and ten directed pairs is a cobweb at half the page width —
 *  true, but it meant the first thing a reader saw was a side with eight
 *  connections, which looks like a team that barely passes. The full map is
 *  the honest picture and the one people come for; the slider thins it for
 *  anyone who wants the spine instead. */
const START = 0.1;

export function SideXI({
  team, season, height = 430,
}: {
  team: string; season: string; height?: number;
}) {
  const squad = useSquad(team, season);
  const { kit, hasModel } = useKit(team);
  const [view, setView] = useState<ViewName>(() =>
    defaultCam("match-xi", "overhead"),
  );
  const [minLink, setMinLink] = useState(START);
  const [picked, setPicked] = useState("");

  const sel = squad.spots.find((s) => s.name === picked) ?? null;
  const field = sel ? territoryFor(squad, sel.name) : null;
  const near = sel ? squad.near12.get(sel.name) ?? null : null;

  const top = squad.edges[0]?.n ?? 1;
  const edges = squad.edges.filter((e) => e.n >= top * minLink);

  if (squad.missing) {
    return (
      <div className="rounded-xl border border-line bg-card p-4 text-[12.5px] text-ink-3">
        No event data for {team} in {season}.
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <TeamHead
          team={team}
          /* NO FORMATION STRING. It was derived by fitting the average
             positions to the nearest named shape, which is a guess dressed
             as a fact — "3-4-2-1" for a side nobody would call that — and
             the picture below already shows where everyone stood. What the
             header owes the reader instead is WHICH QUESTION this answers,
             because the team page shows a different eleven for a good
             reason. */
          note={`where they actually played · ${squad.matches} matches`}
        />
        <label className="ml-auto flex items-center gap-1.5 text-[11.5px] text-ink-2">
          links
          <input
            type="range"
            min={0.1}
            max={0.95}
            step={0.03}
            value={minLink}
            onChange={(e) => setMinLink(Number(e.target.value))}
            className="w-20"
          />
          <span className="num text-ink-3">{edges.length}</span>
        </label>
      </div>

      <div className="mt-1.5">
        <PitchScene
          height={height}
          view={view}
          onView={setView}
          scene="match-xi"
          caption={
            sel ? (
              <span>
                <b className="text-ink">{sel.name}</b> — the surface is where
                he passed from
                {near !== null && (
                  <>
                    ; only <b className="text-ink">{Math.round(near * 100)}%</b>{" "}
                    of it within twelve metres of that dot
                  </>
                )}
                . Click him again to clear.
              </span>
            ) : (
              <span className="text-ink-3">
                Each disc is a man&apos;s average position on the ball, sized
                by volume; each lane is one direction of a partnership. Click
                a player to raise his real territory.
              </span>
            )
          }
        >
          <Formation3D
            spots={squad.spots}
            edges={edges}
            field={field}
            selected={picked}
            model={hasModel}
            kit={kit}
            onSelect={setPicked}
          />
        </PitchScene>
      </div>
    </div>
  );
}
