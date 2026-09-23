"use client";

import { useState } from "react";

import { PitchScene, type ViewName } from "./PitchScene";
import { TerrainCells, type Cell } from "./TerrainCells";

/** Territory, on the shared pitch. This file is only the wiring — the stage
 *  is `PitchScene`, the content is `TerrainCells`, and neither knows about
 *  the other beyond the coordinate helpers they both import. */

const HOME = "#2fa85f";
const AWAY = "#2f7fd0";

export function TerrainView({
  home, away, homeName, awayName, height = 500,
}: {
  home: Cell[];
  away: Cell[];
  homeName: string;
  awayName: string;
  height?: number;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState<ViewName>("corner");

  const caption = (() => {
    if (!hover) return null;
    const [side, cell] = hover.split("|");
    const third = { D: "own third", M: "middle third", A: "final third" }[
      cell[0] as "D" | "M" | "A"
    ];
    const chan: Record<string, string> = {
      RW: "right wing", RH: "right half-space", C: "centre",
      LH: "left half-space", LW: "left wing",
    };
    const who = side === "home" ? homeName : awayName;
    return (
      <>
        <b className="text-ink">{who}</b> — {chan[cell.slice(1)] ?? cell.slice(1)}{" "}
        in {side === "home" ? "the" : "their"} {third}
      </>
    );
  })();

  return (
    <PitchScene
      height={height}
      view={view}
      onView={setView}
      caption={caption}
      legend={
        <span className="flex items-center gap-3 text-[11.5px] text-ink-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: HOME }} />
            {homeName}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: AWAY }} />
            {awayName}
          </span>
        </span>
      }
    >
      <TerrainCells
        home={home}
        away={away}
        homeColour={HOME}
        awayColour={AWAY}
        onHover={setHover}
      />
    </PitchScene>
  );
}
