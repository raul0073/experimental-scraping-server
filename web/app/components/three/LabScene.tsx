"use client";

import { useState } from "react";

import { CameraLab } from "./CameraLab";
import { FormationView } from "./FormationView";
import { Markers, type Marker } from "./Markers";
import { PassView } from "./PassView";
import { PitchScene, defaultCam, type ViewName } from "./PitchScene";
import { ShotView } from "./ShotView";
import { TerrainCells, type Cell } from "./TerrainCells";
import { ZoneView } from "./ZoneView";

/** Whatever the lab is currently showing, on the shared pitch. */

const CELLS = ["DRW", "DRH", "DC", "DLH", "DLW",
               "MRW", "MRH", "MC", "MLH", "MLW",
               "ARW", "ARH", "AC", "ALH", "ALW"];

/** Made up, but shaped like real data: a side creates most of its chances in
 *  the final third and almost none in its own. Flat noise would hide exactly
 *  the problems this page exists to catch. */
const HOME: Cell[] = CELLS.map((cell, i) => ({
  cell,
  value: [0.05, 0.08, 0.12, 0.07, 0.04,
          0.22, 0.4, 0.55, 0.38, 0.2,
          0.9, 1.45, 1.8, 1.3, 0.85][i],
}));
/** The away side, ALREADY TURNED into the home side's frame — which is what
 *  the real page passes, and the turn that has caught me twice. */
const AWAY: Cell[] = CELLS.map((cell, i) => ({
  cell,
  value: [0.7, 1.1, 1.35, 0.95, 0.6,
          0.18, 0.32, 0.44, 0.3, 0.16,
          0.04, 0.07, 0.1, 0.06, 0.03][i],
}));

/** The four points that prove the frame. Opta x: 0 own goal line, 100
 *  theirs. Opta y: 0 RIGHT touchline, 100 LEFT. */
const PINS: Marker[] = [
  { x: 100, y: 50, label: "(100,50) far goal", colour: "#ff5c5c" },
  { x: 0, y: 50, label: "(0,50) own goal", colour: "#5cc8ff" },
  { x: 100, y: 100, label: "(100,100) far LEFT corner", colour: "#ffd23f" },
  { x: 0, y: 0, label: "(0,0) own RIGHT corner", colour: "#8ee86a" },
  { x: 50, y: 50, label: "(50,50) centre spot", colour: "#ffffff" },
  { x: 88.5, y: 50, label: "(88.5,50) penalty spot", colour: "#ff9f1c" },
];

export function LabScene({
  piece, goals,
}: {
  piece: "pitch" | "coords" | "terrain" | "part" | "shots" | "passes"
       | "formation" | "cameras" | "zones";
  goals: boolean;
}) {
  if (piece === "cameras") return <CameraLab />;
  if (piece === "zones") return <ZoneView team="Arsenal" season="2526" tune />;
  if (piece === "shots") return <ShotView team="Arsenal" season="2526" tune />;
  if (piece === "passes") return <PassView team="Arsenal" season="2526" tune />;
  if (piece === "formation")
    return <FormationView team="Arsenal" season="2526" tune />;
  return <Base piece={piece} goals={goals} />;
}

function Base({
  piece, goals,
}: {
  piece: "pitch" | "coords" | "terrain" | "part";
  goals: boolean;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState<ViewName>(() =>
    defaultCam(`lab-${piece}`, "corner"),
  );

  return (
    <PitchScene
      portion={piece === "part" ? 0.75 : 1}
      goals={goals}
      height={520}
      view={view}
      onView={setView}
      scene={"lab-" + piece}
      tune
      caption={
        piece === "terrain" && hover ? (
          <span className="num">{hover}</span>
        ) : piece === "coords" ? (
          <span className="text-ink-3">
            If (100,100) is not the FAR LEFT corner as you look up the pitch,
            the y axis is flipped.
          </span>
        ) : null
      }
    >
      {piece === "terrain" && (
        <TerrainCells home={HOME} away={AWAY} onHover={setHover} />
      )}
      {piece === "coords" && <Markers points={PINS} />}
    </PitchScene>
  );
}
