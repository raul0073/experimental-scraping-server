"use client";

import { useState } from "react";

import {
  MODES, PitchScene, camsFor, portionOf, readSaved,
  type Mode, type ViewName,
} from "./PitchScene";

/** Where the camera presets are DECIDED, rather than inherited.
 *
 *  Seats are pure taste and I cannot see the render, so guessing at them
 *  through screenshots is the slowest loop in this work. Every number in
 *  the default tables was reasoned about by someone looking at arithmetic
 *  instead of a pitch, which is exactly how "overhead" ended up upside down
 *  and every preset ended up too far out.
 *
 *  So this page hands the decision over: fly the camera where it belongs,
 *  name it, and that becomes the seat everywhere — the team page, the shot
 *  map, versus. The defaults are only what is there before anyone has said
 *  otherwise; as soon as one camera is saved for a mode, that mode uses
 *  YOUR list and nothing else.
 *
 *  THE MODE SELECTOR IS THE POINT. A full pitch, a three-quarter shot map
 *  and a half are three different subjects, and one seat cannot frame all
 *  of them — an 80m camera on a 50m subject is a postage stamp in a lot of
 *  dark blue. Each keeps its own list, and they are all set from here.
 */

const BLURB: Record<Mode, string> = {
  full: "The whole pitch — average positions, territory, versus.",
  three: "Three quarters, back from the attacking goal — the shot map.",
  half: "The attacking half only. Nothing ships on this yet; it is kept so a tighter view is one prop away.",
};

export function CameraLab() {
  const [mode, setMode] = useState<Mode>("full");
  const [view, setView] = useState<ViewName>("overhead");
  const saved = readSaved();
  const cams = camsFor(saved, mode);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {MODES.map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              setView(camsFor(saved, m)[0]?.name ?? "overhead");
            }}
            className={`rounded-full border px-3.5 py-1 text-[12.5px] font-medium capitalize transition-colors ${
              mode === m
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {m} pitch
          </button>
        ))}
        <span className="ml-auto num text-[12.5px] text-ink-2">
          {cams.length} camera{cams.length === 1 ? "" : "s"} ·{" "}
          {saved[mode]?.length ? "yours" : "defaults"}
        </span>
      </div>

      <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-3">
        {BLURB[mode]}
      </p>

      <div className="mt-3">
        {/* keyed on the mode so switching rebuilds the canvas rather than
            trying to reframe a camera that was placed for a different
            subject — the initial position is a Canvas prop, not a live one */}
        <PitchScene
          key={mode}
          portion={portionOf(mode)}
          height={560}
          view={view}
          onView={setView}
          tune
          caption={
            <span className="text-ink-3">
              Drag, scroll and pan until it looks right, then{" "}
              <b className="text-ink">Save over</b> the current camera or give
              it a name and <b className="text-ink">Add here</b>. Saved
              cameras apply everywhere on the site immediately.
            </span>
          }
        />
      </div>

      <div className="mt-5 max-w-3xl rounded-xl border border-line bg-card p-4 text-[12.5px] leading-relaxed text-ink-2">
        <b className="text-ink">These are stored in this browser.</b> That is
        enough to use them and to check they are right, but it is not enough
        to ship them — another machine would still get the defaults. When the
        set is how you want it, press <b className="text-ink">Copy code</b>{" "}
        and the three tables come out ready to paste into{" "}
        <span className="num">PitchScene.tsx</span>, which is what makes them
        everyone&apos;s.
      </div>
    </div>
  );
}
