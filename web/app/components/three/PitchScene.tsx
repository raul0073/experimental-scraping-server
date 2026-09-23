"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import {
  type Cam, type Focus, type Mode, type Saved, type Seat, type Vec3,
  type ViewName,
  asCode, camsFor, modeOf, readSaved, setOpensOn, writeSaved,
} from "./cameras";
import { SceneGuard } from "./SceneGuard";
import { useFullscreen, useNarrow } from "./viewport";

/** THE FRAME AROUND A PITCH: the toolbar, the caption, and the decision
 *  about whether there should be a 3D scene inside it at all.
 *
 *  THIS FILE NO LONGER IMPORTS THREE, and that is the point of it. The canvas
 *  moved to `PitchCanvas.tsx` and is fetched only when a 3D view is actually
 *  asked for. Everything here — the seats, the storage, the pills, the flat
 *  fallback — is plain React, so a phone renders the whole component and
 *  never downloads the renderer.
 *
 *  ON A PHONE THE FLAT MAP IS THE DEFAULT. A 3D pitch in a 340-pixel box is
 *  mostly sky: the grass you can read is a band across the middle, the near
 *  end is enormous and the far end is a smear, and any label long enough to
 *  name a player covers a third of the picture. A flat pitch answers "where
 *  were the chances" better at that size, so it opens there and 3D is one
 *  tap away. A laptop still opens in 3D, where the depth is doing work.
 *
 *  AND WHEN SOMEONE DOES WANT THE SCENE ON A PHONE, the answer is the whole
 *  screen rather than a slightly larger box. Hence the fullscreen control,
 *  which takes the toolbar and the caption with it so the presets and the
 *  reading are still there.
 *
 *  A view that hands in no `flat` gets a card instead of a scene on a small
 *  screen — "show the 3D pitch" — rather than 600KB nobody asked for. That
 *  is a worse answer than a flat map and it is the honest one: there is no
 *  2D rendering of that scene to show, so it says so.
 */

export {
  type Cam, type Focus, type Mode, type Saved, type Seat, type ViewName,
  type Vec3, MODES, asCode, camsFor, defaultCam, modeOf, portionOf, readSaved,
  writeSaved,
} from "./cameras";

/** The canvas, and nothing else in the tree, pulls in three. `ssr: false` is
 *  not optional: there is no canvas to render on a server, and on a statically
 *  exported site there is no server at all. The import does not run until
 *  this component is rendered, which is what keeps the chunk off a phone. */
const PitchCanvas = dynamic(() => import("./PitchCanvas"), { ssr: false });

export function PitchScene({
  children,
  portion = 1,
  goals = true,
  arena = true,
  height = 480,
  view,
  onView,
  focus,
  caption,
  legend,
  tune = false,
  scene = "",
  flat,
  flatNote,
}: {
  children?: React.ReactNode;
  /** how much of the pitch to draw, back from the attacking goal — 1 for
   *  all of it, 0.75 for a shot map. See Pitch3D. */
  portion?: number;
  goals?: boolean;
  /** hoardings, corner flags, dugouts and floodlights. Off strips the scene
   *  back to bare grass — useful when checking geometry, wrong for anything
   *  a reader looks at, because nothing else in the picture has a known
   *  height and the whole thing flattens. */
  arena?: boolean;
  /** The height the scene wants on a laptop. On a phone it is a CEILING, not
   *  a promise: a 520px box on a 667px screen leaves no room for the caption
   *  that explains it, so the box takes the smaller of this and most of the
   *  viewport. */
  height?: number;
  view?: ViewName;
  onView?: (v: ViewName) => void;
  /** A one-off camera position that overrides the preset — used to drop to
   *  a shooter's eye. Set it and the camera flies there; clear it and the
   *  current preset takes over again. */
  focus?: Focus | null;
  caption?: React.ReactNode;
  legend?: React.ReactNode;
  /** show the camera tuner. Lab only — the seats it writes apply everywhere,
   *  but the controls for setting them do not belong on a reader's page. */
  tune?: boolean;
  /** what this view IS, so it can remember which camera to open on. A view
   *  that passes nothing keeps whatever its caller chose. */
  scene?: string;
  /** THE FLAT RENDERING OF THE SAME DATA, if there is one. Given, it is what
   *  a phone opens on and what the 2D/3D switch switches to. Left out, the
   *  switch does not appear and a small screen gets a load-it-yourself card:
   *  a control that silently does nothing would be worse than either. */
  flat?: React.ReactNode;
  /** one line under the flat map saying what the flat one cannot show, so
   *  the reader knows what taking the 3D view would buy them */
  flatNote?: React.ReactNode;
}) {
  const [own, setOwn] = useState<ViewName>(
    portion > 0.999 ? "corner" : "behind the goal",
  );
  const current = view ?? own;
  const set = onView ?? setOwn;
  const flyingRef = useRef(true);
  const grabRef = useRef<(() => Seat) | null>(null);

  // guarded lazy init rather than an effect: reading storage in an effect
  // means one render with the wrong camera and a visible jump
  const [saved, setSaved] = useState<Saved>(readSaved);
  const [code, setCode] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [opensOn, setOpens] = useState("");
  const [ready, setReady] = useState(false);

  const narrow = useNarrow();
  const shell = useRef<HTMLDivElement | null>(null);
  const fs = useFullscreen(shell);

  /** HOW TALL THIS WAS BEFORE IT LEFT THE PAGE.
   *
   *  Only the FALLBACK fullscreen needs it. `position: fixed` takes the
   *  scene out of flow, so everything below it jumps up by the height of a
   *  pitch — and when the reader closes it again the page has scrolled
   *  somewhere else. Reserving the space keeps the article still underneath.
   *  Measured continuously while in the page, so a filter that changes the
   *  toolbar's wrapping is already accounted for. */
  const [parked, setParked] = useState(0);
  const faking = fs.on && !fs.native;
  useEffect(() => {
    const el = shell.current;
    if (!el || faking || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setParked(el.offsetHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, [faking]);

  /** Nothing behind a fake fullscreen should scroll, or a drag on the pitch
   *  moves the article under it. The real API does this for us. */
  useEffect(() => {
    if (!faking) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [faking]);

  /** WHICH RENDERING IS ON SCREEN. `null` means "whatever this screen should
   *  open on"; a tap on the switch pins it either way for the session. */
  const [want3d, setWant3d] = useState<boolean | null>(null);
  const show3d = want3d ?? narrow === false;

  // Which camera this scene opens on is a localStorage read, so it happens
  // after mount — the prerendered HTML has no window.
  useEffect(() => {
    if (!scene) return;
    try {
      const d = JSON.parse(
        window.localStorage.getItem("predictorous.cameraDefaults.v1") || "{}",
      );
      if (typeof d[scene] === "string") setOpens(d[scene]);
    } catch {
      /* blocked storage — the tuner just shows nothing pinned */
    }
  }, [scene]);

  // Leaving 3D unmounts the canvas, so coming back is a fresh scene with a
  // fresh first frame. Without this reset the placeholder stays hidden and
  // the reader watches a black box build itself with no sign that it is.
  useEffect(() => {
    if (!show3d) setReady(false);
  }, [show3d]);

  const mode: Mode = modeOf(portion);
  const cams = camsFor(saved, mode);
  const mine = !!saved[mode]?.length;
  /** A NAME THAT NO LONGER EXISTS IS NOT AN ERROR. Cameras can be deleted
   *  while a page is holding the name of one, so an unmatched name falls
   *  back to the first rather than leaving the scene with no seat at all. */
  const cam = cams.find((c) => c.name === current) ?? cams[0];
  const seat = focus ? focus.pos : cam.pos;
  const target = focus ? focus.target : cam.target;

  // a new preset — or a new focus — starts a flight; a drag ends it.
  // Capturing deliberately does NOT: the camera is already where it was put.
  useEffect(() => {
    flyingRef.current = true;
  }, [current, focus]);

  const commit = (list: Cam[]) => {
    const next: Saved = { ...saved, [mode]: list };
    setSaved(next);
    writeSaved(next);
    setCode(null);
  };

  /** Overwrite the camera currently selected with wherever the lens is now. */
  const update = () => {
    const s = grabRef.current?.();
    if (!s) return;
    commit(cams.map((c) => (c.name === cam.name ? { ...c, ...s } : c)));
  };

  /** Save where the lens is now as a NEW camera. Naming it the same as an
   *  existing one replaces that one, which is what anyone typing a name
   *  they already used means by it. */
  const add = () => {
    const s = grabRef.current?.();
    const name = newName.trim();
    if (!s || !name) return;
    const without = cams.filter((c) => c.name !== name);
    commit([...without, { name, ...s }]);
    setNewName("");
    set(name);
  };

  const drop = (name: string) => {
    const left = cams.filter((c) => c.name !== name);
    // never leave a mode with nothing to look through
    commit(left.length ? left : camsFor({}, mode));
    if (current === name) set((left[0] ?? camsFor({}, mode)[0]).name);
  };

  const resetMode = () => {
    const next: Saved = { ...saved };
    delete next[mode];
    setSaved(next);
    writeSaved(next);
    setCode(null);
  };

  const pill =
    "rounded-full border border-line bg-card px-2.5 py-0.5 text-[11.5px] " +
    "text-ink-2 transition-colors hover:border-ink-3 disabled:opacity-40 " +
    "disabled:hover:border-line";

  /** THE BOX'S HEIGHT. Full screen it takes what is left after the toolbar
   *  and the caption; on a phone it is capped against the viewport so the
   *  sentence explaining the picture is on screen WITH the picture. */
  const boxHeight = fs.on
    ? undefined
    : narrow
      ? `min(${height}px, 62vh)`
      : height;

  const canSwitch = !!flat;

  /* --------------------------------------------------------------- pieces */

  const switcher = canSwitch && (
    <span className="inline-flex shrink-0 overflow-hidden rounded-full border border-line">
      {[
        { on: false, label: "2D" },
        { on: true, label: "3D" },
      ].map((o) => (
        <button
          key={o.label}
          type="button"
          onClick={() => setWant3d(o.on)}
          aria-pressed={show3d === o.on}
          title={
            o.on
              ? "The scene, with depth and the shooter's eye. Downloads the 3D renderer."
              : "A flat pitch — the whole map at once, and no download."
          }
          className={`px-2.5 py-0.5 text-[11.5px] transition-colors ${
            show3d === o.on
              ? "bg-[#e9f1f8] font-semibold text-[#1c5b8a]"
              : "bg-card text-ink-2"
          }`}
        >
          {o.label}
        </button>
      ))}
    </span>
  );

  const fullscreenBtn = (
    <button
      type="button"
      onClick={fs.toggle}
      title={
        fs.on
          ? "back into the page"
          : "fill the screen — the only size a pitch is worth looking at on a phone"
      }
      className={`${pill} shrink-0`}
    >
      {fs.on ? "✕ close" : "⛶ full screen"}
    </button>
  );

  /** THE PRESETS. Five pills wrap onto three rows at 375px and push the
   *  picture off the bottom of the screen, so below `sm` the same five are a
   *  select — the pattern the ranking table already uses for its sort. The
   *  choice is not hidden, it is folded. */
  const presets = show3d && (
    narrow ? (
      <label className="flex min-w-0 flex-1 items-center gap-2 text-[12px] text-ink-2">
        camera
        <select
          value={cam.name}
          onChange={(e) => {
            flyingRef.current = true;
            set(e.target.value);
          }}
          className="min-w-0 flex-1 rounded-md border border-line bg-card px-2 py-1 text-[12px] capitalize"
        >
          {cams.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
    ) : (
      <>
        {cams.map((c) => (
          <button
            key={c.name}
            onClick={() => {
              flyingRef.current = true;
              set(c.name);
            }}
            className={`rounded-full border px-3 py-0.5 text-[12px] capitalize transition-colors ${
              cam.name === c.name
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {c.name}
          </button>
        ))}
      </>
    )
  );

  const placeholder = (
    /* THE PLACEHOLDER IS A PITCH. A spinner says "something is
       happening"; an outline of the thing you asked for says what, and
       it lands in the same place the real one will, so the page does
       not jump when it arrives. It fades rather than cuts, because a
       hard swap reads as a flicker at these durations. */
    <div
      aria-hidden={ready}
      className={`pointer-events-none absolute inset-0 z-10 flex items-center justify-center transition-opacity duration-500 ${
        ready ? "opacity-0" : "opacity-100"
      }`}
      style={{ background: "linear-gradient(#0e1a26, #172836)" }}
    >
      <div className="flex flex-col items-center gap-3 px-4 text-center">
        <svg
          viewBox="0 0 68 105"
          className="h-[min(58%,230px)] w-auto"
          fill="none"
          stroke="rgba(255,255,255,0.22)"
          strokeWidth="0.9"
        >
          <rect x="1" y="1" width="66" height="103" rx="0.5" />
          <line x1="1" y1="52.5" x2="67" y2="52.5" />
          <circle cx="34" cy="52.5" r="9.15" />
          <rect x="13.8" y="1" width="40.3" height="16.5" />
          <rect x="13.8" y="87.5" width="40.3" height="16.5" />
          <rect x="24.8" y="1" width="18.3" height="5.5" />
          <rect x="24.8" y="98.5" width="18.3" height="5.5" />
          <circle cx="34" cy="12" r="0.6" fill="rgba(255,255,255,0.22)" />
          <circle cx="34" cy="93" r="0.6" fill="rgba(255,255,255,0.22)" />
        </svg>
        <span className="text-[12px] tracking-wide text-white/55">
          building the pitch<span className="animate-pulse">…</span>
        </span>
      </div>
    </div>
  );

  /** No flat rendering exists for this scene, and the screen is small. Say
   *  what taking the 3D view costs rather than spending it unasked. */
  const offer = (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 px-6 text-center">
      <span className="text-[13px] text-white/75">
        This one is only drawn in 3D.
      </span>
      <button
        type="button"
        onClick={() => setWant3d(true)}
        className="rounded-full border border-white/30 px-4 py-1.5 text-[13px] text-white/90 transition-colors hover:border-white/60"
      >
        Show the 3D pitch
      </button>
      <span className="max-w-xs text-[11.5px] leading-relaxed text-white/45">
        It fetches about 600KB of renderer. On a phone the full-screen
        control above is the size worth looking at it in.
      </span>
    </div>
  );

  /* ---------------------------------------------------------------- render */

  return (
    <figure className="m-0" style={faking ? { height: parked } : undefined}>
      <div
        ref={shell}
        className={
          fs.on
            ? `${fs.native ? "h-screen" : "fixed inset-0 z-50"} flex flex-col gap-1 overflow-hidden bg-card p-3`
            : undefined
        }
      >
        <div className="flex flex-wrap items-center gap-2">
          {presets}
          {switcher}
          {fullscreenBtn}
          {/* THE LEGEND GOES UNDER THE PICTURE ON A PHONE. Beside the pills
              it is a second wrapping row of swatches between the reader and
              the map, and on the shot view it is also the filter — which
              nobody finds above a picture they have not seen yet. */}
          {legend && !narrow && <span className="ml-auto">{legend}</span>}
        </div>

        {tune && (
          <div className="mt-2 rounded-lg border border-dashed border-line bg-card px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
              <b className="text-ink">Cameras</b>
              <span className="text-ink-3">
                {mode} pitch · {mine ? "yours" : "defaults"}
              </span>
              <button
                className={pill}
                onClick={update}
                disabled={!!focus || !show3d}
                title={
                  focus
                    ? "clear the selection first — this would save the shooter's eye"
                    : `move ${cam.name} to where the camera is now`
                }
              >
                Save over &ldquo;{cam.name}&rdquo;
              </button>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && add()}
                placeholder="new camera name"
                className="w-40 max-w-full rounded border border-line bg-card px-2 py-0.5 text-[11.5px]"
              />
              <button className={pill} onClick={add}
                      disabled={!newName.trim() || !!focus || !show3d}>
                Add here
              </button>
              <button className={pill} onClick={() => drop(cam.name)}
                      disabled={cams.length < 2 && !mine}>
                Delete &ldquo;{cam.name}&rdquo;
              </button>
              <button className={pill} onClick={resetMode} disabled={!mine}>
                Restore defaults
              </button>
              {scene && (
                <button
                  className={pill}
                  onClick={() => {
                    setOpensOn(scene, cam.name);
                    setOpens(cam.name);
                  }}
                  disabled={opensOn === cam.name}
                  title={`open this view on "${cam.name}" from now on`}
                >
                  {opensOn === cam.name
                    ? `Opens on "${cam.name}"`
                    : `Open on "${cam.name}"`}
                </button>
              )}
              <button
                className={pill}
                onClick={() => {
                  const text = asCode(saved);
                  setCode(code ? null : text);
                  navigator.clipboard?.writeText(text).catch(() => {});
                }}
              >
                {code ? "Hide code" : "Copy code"}
              </button>
              <span className="num ml-auto text-ink-3">
                pos {cam.pos.join(", ")} · aim {cam.target.join(", ")}
              </span>
            </div>
            {code && (
              <pre className="num mt-2 max-h-56 overflow-auto rounded border border-line bg-[#0e1a26] p-2 text-[11px] leading-relaxed text-white/80">
                {code}
              </pre>
            )}
          </div>
        )}

        <div
          className={`relative mt-2 overflow-hidden rounded-xl border border-line ${
            fs.on ? "min-h-0 flex-1" : ""
          }`}
          style={{
            height: boxHeight,
            // DARK WHENEVER SOMETHING WHITE IS DRAWN ON IT: the scene, the
            // loading placeholder, the SceneGuard message and the offer card
            // are all white-on-dark. A flat map brings its own green and
            // wants the page's background around it, not a black slab.
            background:
              show3d || !flat || narrow === undefined
                ? "linear-gradient(#0e1a26, #172836)"
                : "transparent",
          }}
        >
          {/* Until the media query has been read there is no honest answer to
              "3D or flat", and guessing one means the prerendered HTML and
              the first client render disagree. One frame of the placeholder
              is cheaper than a hydration mismatch and a visible swap. */}
          {narrow === undefined ? (
            placeholder
          ) : show3d ? (
            <SceneGuard>
              {placeholder}
              <PitchCanvas
                portion={portion}
                goals={goals}
                arena={arena}
                seat={seat}
                target={target}
                flyingRef={flyingRef}
                grabRef={grabRef}
                tune={tune}
                // A phone shading 2.5x the CSS box is a hot phone with a flat
                // battery; 1.75 is most of the way there for a quarter less
                // fill. Full screen it matters more, not less.
                dpr={narrow ? [1, 1.75] : [1, 2.5]}
                onReady={() => setReady(true)}
              >
                {children}
              </PitchCanvas>
            </SceneGuard>
          ) : flat ? (
            flat
          ) : (
            offer
          )}
        </div>

        {legend && narrow && <div className="mt-2">{legend}</div>}

        {/* The caption is the reading, and it belongs to the data rather than
            to the renderer — the same sentence about the same selected shot
            is true flat or in 3D. Only the "how to fly the camera" default is
            3D-specific, because on a flat map there is no camera. */}
        <p className="mt-1.5 min-h-[1.4em] text-[12.5px] text-ink-2">
          {caption ??
            (show3d ? (
              <span className="text-ink-3">
                Drag to orbit · scroll to zoom · right-drag to pan. A preset
                flies you back.
              </span>
            ) : null)}
        </p>
        {/* WHAT THE FLAT VIEW CANNOT SHOW YOU, said out loud. Dropping the
            third dimension drops real information on some of these maps, and
            a reader who is not told has no way to know what the 3D button is
            for. */}
        {!show3d && flat && flatNote && (
          <p className="text-[11.5px] leading-relaxed text-ink-3">{flatNote}</p>
        )}
        {fs.on && !fs.native && (
          <p className="text-[11px] text-ink-3">
            This browser would not hand over the whole screen — iPhone Safari
            does not offer it for part of a page — so the scene is pinned over
            the page instead. Escape, or the close button, brings it back.
          </p>
        )}
      </div>
    </figure>
  );
}
