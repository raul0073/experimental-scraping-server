"use client";

import { useState } from "react";

import { PitchScene, defaultCam, type ViewName } from "../components/three/PitchScene";
import { ZoneHeat, cellLabel, type ZoneValues } from "../components/three/ZoneHeat";

/** One phase of the fixture, as zone tiles on the pitch.
 *
 *  THE COMPONENT IS THE LAB'S, not a second one written for this page.
 *  `ZoneHeat` is the piece that was iterated on until it read properly —
 *  fifteen inset tiles with the figure printed on each, grass showing
 *  between them, no smooth wash claiming resolution the data never had.
 *  This is a wrapper that feeds it and writes the caption.
 *
 *  One map per phase, because "who wins the left wing" has no answer that
 *  does not first say who has the ball. Each is drawn in the frame of the
 *  side ATTACKING in it, so up the picture is forward for whoever is on it.
 *
 *  THE SCALE IS SHARED with the other phase and passed in. These are chances
 *  a match, not percentiles — rescaling each map to its own hottest cell
 *  would make a mismatch look like two equally colourful pictures, which is
 *  exactly the failure the attack-times-defence form exists to avoid.
 */
export function ZonePitch({
  values, attacking, defending, scale, height = 430,
}: {
  values: ZoneValues;
  attacking: string;
  defending: string;
  scale: number;
  height?: number;
}) {
  const [view, setView] = useState<ViewName>(() =>
    defaultCam("match-zones", "overhead"),
  );
  const [cell, setCell] = useState("");
  const v = cell ? values[cell] : undefined;

  return (
    <PitchScene
      height={height}
      view={view}
      onView={setView}
      scene="match-zones"
      legend={
        <span className="flex items-center gap-2 text-[11.5px] text-ink-3">
          rare
          <span
            className="inline-block h-2.5 w-20 rounded-sm"
            style={{ background: "linear-gradient(90deg,#26965c,#f6ce24,#e22a20)" }}
          />
          their way in
        </span>
      }
      caption={
        cell && typeof v === "number" ? (
          <span>
            <b className="text-ink capitalize">{cellLabel(cell)}</b> —{" "}
            <b className="num text-ink">{v.toFixed(2)}</b> chances a match for{" "}
            {attacking} from there
            {v >= scale * 0.66
              ? ", their best route in"
              : v <= scale * 0.25
                ? `, a door ${defending} keep shut`
                : ""}
            . Click again to clear.
          </span>
        ) : (
          <span className="text-ink-3">
            {attacking} on the ball. Each cell is how many chances a match
            they should get from there — their rate against what {defending}{" "}
            concede in the same place. Click one.
          </span>
        )
      }
    >
      <ZoneHeat
        values={values}
        lo={0}
        hi={scale}
        decimals={2}
        selected={cell}
        onSelect={setCell}
      />
    </PitchScene>
  );
}
