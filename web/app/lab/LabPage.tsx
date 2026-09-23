"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Crumbs } from "../components/Crumbs";

/** The component lab: every 3D piece on its own, with synthetic data.
 *
 *  It fetches nothing. That is the point — a piece that only renders inside
 *  a page with four payloads loaded is a piece nobody can look at while they
 *  are building it, and every visual bug gets found on the real page with
 *  real data, which is the slowest possible place to find one.
 *
 *  The coordinate check is the part worth keeping. Opta's y runs 0 at the
 *  RIGHT touchline, which is the reverse of what anyone assumes, and a
 *  mirrored pitch stays plausible until a winger is on the wrong flank in
 *  every picture on the site.
 */

const Scene = dynamic(
  () => import("../components/three/LabScene").then((m) => m.LabScene),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[520px] items-center justify-center rounded-xl border border-line bg-[#0e1a26] text-[13px] text-white/60">
        building the pitch…
      </div>
    ),
  },
);

const PIECES = [
  { key: "cameras", label: "Cameras",
    note: "Where the presets are decided rather than inherited. Fly the camera where it belongs, name it, and that becomes the seat everywhere on the site — full, three-quarter and half pitches each keep their own list, because one seat cannot frame three different subjects. Defaults only apply until you save one." },
  { key: "pitch", label: "Bare pitch",
    note: "The stage on its own. Stripes, real markings, goals with nets." },
  { key: "coords", label: "Coordinate check",
    note: "Pins at known Opta points. (100, 50) must sit in the middle of the far goal; (0, 0) is the corner to the right of your own keeper." },
  { key: "terrain", label: "Territory columns",
    note: "Fifteen cells, home rising and away hanging below. Synthetic numbers." },
  { key: "part", label: "Three-quarter pitch",
    note: "What a shot map stands on — three quarters, goal at the far end. It was a half until shots from just inside a side's own half started landing off the grass." },
  { key: "shots", label: "Shot map",
    note: "Arsenal, 25/26 — real shots with real xG from Understat. Area is xG, colour is the outcome. Click one and the angle of goal he actually had is drawn to both posts, which is most of what an xG model reads." },
  { key: "formation", label: "Average positions",
    note: "Arsenal, 25/26 — the eleven who played most, plinths sized by volume, with each direction of a partnership in its own lane. That matters: Raya passes to Gyökeres 53 times and gets one back, and a single undirected line would call that an exchange. Click a player and his real territory rises underneath — only the keeper spends most of his time near his own average position (65%), the busiest midfielder manages 15%. The dot on a peak is a man with a position; the dot in a valley is a man with two." },
  { key: "zones", label: "Team zones",
    note: "Arsenal, 25/26 — the fifteen zones as heat on the grass, with the cell boundaries painted on top so you can see which fifteen numbers the colour came from. NO COLUMNS on purpose: a zone value is one number per place, and colour on the plane is what that wants. With the ball, each cell is scored against what a typical side manages THERE — your attacking centre is their defensive centre. Against, it is where the chance BEGAN rather than where the shot was hit, because mapping shots makes every side red in front of its own keeper." },
  { key: "passes", label: "Pass map",
    note: "Arsenal, 25/26 — every pass from the WhoScored event stream, filterable by player and by what became of it. Opta flags whether a pass left the ground, so lofted balls arc and ground passes stay down: a 40m ball along the floor and a 40m diagonal over the top are different actions, and that is the one thing a flat map cannot tell you." },
] as const;

export type Piece = (typeof PIECES)[number]["key"];

export function LabPage() {
  const [piece, setPiece] = useState<Piece>("pitch");
  const [goals, setGoals] = useState(true);
  const current = PIECES.find((p) => p.key === piece)!;

  return (
    <div>
      <Crumbs trail={[{ label: "Lab" }]} />
      <h1 className="font-display text-[26px] leading-tight">Component lab</h1>
      <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-ink-2">
        Each 3D piece on its own, with made-up numbers and no data fetching —
        so a visual problem can be found here rather than on a real page with
        four payloads loaded.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {PIECES.map((p) => (
          <button
            key={p.key}
            onClick={() => setPiece(p.key)}
            className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium transition-colors ${
              piece === p.key
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {p.label}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-[12.5px] text-ink-2">
          <input
            type="checkbox"
            checked={goals}
            onChange={(e) => setGoals(e.target.checked)}
          />
          goals
        </label>
      </div>

      <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-3">
        {current.note}
      </p>

      <div className="mt-3">
        <Scene piece={piece} goals={goals} />
      </div>

      <div className="mt-6 max-w-3xl rounded-xl border border-line bg-card p-4 text-[12.5px] leading-relaxed text-ink-2">
        <b className="text-ink">What to look for.</b> The stripes and the goals
        are what make a rectangle of grass read as football — the first
        version had neither and looked like a lawn with boxes on it. The lines
        are painted geometry 12cm wide rather than hairlines, so they survive
        a low camera angle. Everything is in metres at FIFA dimensions, which
        means a shot drawn just outside the box really was just outside it.
      </div>
    </div>
  );
}
