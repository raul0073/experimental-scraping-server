"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { PITCH_L, Pitch3D, PitchLights } from "./Pitch3D";
import { SceneGuard } from "./SceneGuard";

/** The canvas, the camera and the controls — shared by every 3D view.
 *
 *  THE CAMERA IS THE READER'S, NOT THE PAGE'S. The first version ran an
 *  easing function every single frame that pulled the camera back toward
 *  whichever preset was selected. It only stopped once it was within 0.4
 *  units of the seat — which it always was — so any drag was immediately
 *  undone and any scroll snapped back. From the outside it looked as though
 *  orbit and zoom simply did not work.
 *
 *  Now a flight happens ONCE, when a preset is clicked, and the first touch
 *  of the mouse cancels it for good. After that the controls own the camera
 *  and the presets are shortcuts back, not a leash.
 *
 *  The orbit is free in every direction but DOWN THROUGH THE GROUND. That
 *  one is not a taste constraint: the turf, the markings and the run-off are
 *  single planes facing up, so from underneath they are not dark, they are
 *  ABSENT — you get the nets and the hoardings floating over nothing, and
 *  the pitch has vanished. There is no view down there to protect.
 */

/** A camera's name. NOT a fixed union any more: the list of seats belongs to
 *  whoever is looking at the scene, so a name is whatever they called it. */
export type ViewName = string;

type Vec3 = [number, number, number];
export type Seat = { pos: Vec3; target: Vec3 };
export type Cam = Seat & { name: string };

/** Where each seat is AND what it looks at, and both depend on WHAT IS BEING
 *  FRAMED.
 *
 *  One set of positions was used for every mode, sized for the full 105
 *  metres — so on a part pitch the camera sat eighty metres from a
 *  fifty-metre subject and everything was a postage stamp in the middle of
 *  a lot of dark blue.
 *
 *  The part-pitch seats also aim well up the pitch rather than at the middle
 *  of what is drawn: shots cluster between the penalty spot and the edge of
 *  the box, and framing the centre wastes a third of the picture on grass
 *  nobody shoots from.
 *
 *  FROM HALFWAY is the one seat with a direction in it. Every other view
 *  frames the subject and the reader works out which way is which; this one
 *  is the attacking view — stood behind the play, looking at the goal being
 *  shot at — which only means anything if the camera is actually pointed
 *  down the pitch rather than at the middle of what is drawn.
 *
 *  THESE ARE DEFAULTS, NOT THE LAST WORD. The tuner below lets whoever is
 *  looking at the scene fly the camera where they want it and capture the
 *  seat; captured seats win over everything here. Numbers chosen by someone
 *  who can see the render beat numbers reasoned about by someone who cannot.
 */
/** OVERHEAD SITS ON THE −z SIDE OF ITS TARGET, and the 0.1 is not noise.
 *
 *  Looking straight down is the one degenerate case for `lookAt`: the up
 *  vector is parallel to the view and which way the image lands is decided
 *  by whatever tiny offset happens to exist. With the camera on the +z side
 *  the resolved up comes out as world −z, so the attacking goal is at the
 *  BOTTOM of the picture — upside down against every football diagram ever
 *  drawn, which reads to anyone looking at it as "the sides are swapped".
 *  Nudging the camera to the far side of the target instead puts the attack
 *  up the screen, where it belongs.
 */
const FULL: Cam[] = [
  { name: "overhead", pos: [0, 96, -0.1], target: [0, 0, 0] },
  { name: "touchline", pos: [74, 26, 0], target: [0, 0, 0] },
  { name: "behind the goal", pos: [0, 18, PITCH_L / 2 + 38], target: [0, 0, 0] },
  { name: "from halfway", pos: [0, 13, -18], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [50, 34, 60], target: [0, 0, 0] },
];
/** Three quarters — what the shot map stands on. Aimed at z = 32 rather than
 *  the region's own middle of 13, because the extra quarter exists to stop
 *  rare long-range attempts falling off the grass, not to be looked at. */
const THREE_Q: Cam[] = [
  { name: "overhead", pos: [0, 66, 31.9], target: [0, 0, 32] },
  { name: "touchline", pos: [56, 19, 34], target: [0, 0, 34] },
  { name: "behind the goal", pos: [0, 13, PITCH_L / 2 + 34], target: [0, 0, 32] },
  { name: "from halfway", pos: [0, 12, -30], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [40, 24, 76], target: [0, 0, 32] },
];
const HALF: Cam[] = [
  { name: "overhead", pos: [0, 50, 37.9], target: [0, 0, 38] },
  { name: "touchline", pos: [46, 15, 38], target: [0, 0, 38] },
  { name: "behind the goal", pos: [0, 11, PITCH_L / 2 + 30], target: [0, 0, 38] },
  { name: "from halfway", pos: [0, 11, -14], target: [0, 1.6, PITCH_L / 2 - 8] },
  { name: "corner", pos: [33, 19, 74], target: [0, 0, 38] },
];

export type Mode = "full" | "three" | "half";
export const MODES: Mode[] = ["full", "three", "half"];
const TABLES: Record<Mode, Cam[]> = { full: FULL, three: THREE_Q, half: HALF };
export const modeOf = (portion: number): Mode =>
  portion > 0.999 ? "full" : portion > 0.6 ? "three" : "half";
export const portionOf = (m: Mode) => (m === "full" ? 1 : m === "three" ? 0.75 : 0.5);

/* ------------------------------------------------------------ saved seats */

/** Captured seats live in the browser, per mode and per view.
 *
 *  They are read on EVERY scene, not only where the tuner is shown, so a
 *  seat tuned in the lab is immediately the seat the team page and the
 *  versus page use. "Copy code" then turns the lot into the literal above,
 *  which is how a captured seat stops being one person's browser setting and
 *  becomes the default everyone gets.
 */
const STORE = "predictorous.cameras.v3";
export type Saved = Partial<Record<Mode, Cam[]>>;

export function readSaved(): Saved {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(STORE) || "{}") as Saved;
  } catch {
    return {};
  }
}

/** WHICH CAMERA A VIEW OPENS ON, per view rather than per mode.
 *
 *  The seat a shot map should land on is not the seat a zone map should,
 *  even though both are looking at the same pitch — one wants to be behind
 *  the goal and the other wants to be above it. That choice was hard-coded
 *  in every view as a string nobody could change without editing the file,
 *  which is the same mistake the camera list itself used to be.
 *
 *  Keyed by a scene name so a view keeps its own answer, and read with a
 *  fallback so a scene that has never been set still opens somewhere
 *  sensible.
 */
const OPENS = "predictorous.cameraDefaults.v1";

export function defaultCam(scene: string, fallback: ViewName): ViewName {
  if (typeof window === "undefined" || !scene) return fallback;
  try {
    const d = JSON.parse(window.localStorage.getItem(OPENS) || "{}");
    return typeof d[scene] === "string" ? (d[scene] as ViewName) : fallback;
  } catch {
    return fallback;
  }
}

function setOpensOn(scene: string, name: string) {
  try {
    const d = JSON.parse(window.localStorage.getItem(OPENS) || "{}");
    d[scene] = name;
    window.localStorage.setItem(OPENS, JSON.stringify(d));
  } catch {
    /* blocked storage — the choice still applies for this session */
  }
}

export function camsFor(saved: Saved, mode: Mode): Cam[] {
  const own = saved[mode];
  return own && own.length ? own : TABLES[mode];
}

export function writeSaved(s: Saved) {
  try {
    window.localStorage.setItem(STORE, JSON.stringify(s));
  } catch {
    /* private mode, blocked storage — the seat still applies this session */
  }
}

const n1 = (v: number) => Math.round(v * 10) / 10;

/** Emits the seat tables exactly as they appear in this file, with captured
 *  seats substituted in — so tuning ends in a paste, not a transcription. */
export function asCode(saved: Saved) {
  const row = (c: Cam) =>
    `  { name: ${JSON.stringify(c.name)}, pos: [${c.pos.join(", ")}], ` +
    `target: [${c.target.join(", ")}] },`;
  const table = (name: string, mode: Mode) =>
    `const ${name}: Cam[] = [\n` +
    camsFor(saved, mode).map(row).join("\n") +
    `\n];`;
  return [
    table("FULL", "full"),
    table("THREE_Q", "three"),
    table("HALF", "half"),
  ].join("\n");
}

/* ------------------------------------------------------------- the canvas */

/** Hands the toolbar a way to read the live camera. The camera and the
 *  controls only exist inside the Canvas, so something has to be in there
 *  to fetch them — but nothing here runs per frame: it hands out a closure
 *  that reads the current values whenever it is called. */
function Grab({
  intoRef,
}: {
  intoRef: React.MutableRefObject<(() => Seat) | null>;
}) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as {
    target?: THREE.Vector3;
  } | null;

  useEffect(() => {
    intoRef.current = () => {
      const t = controls?.target;
      return {
        pos: [n1(camera.position.x), n1(camera.position.y), n1(camera.position.z)],
        target: t ? [n1(t.x), n1(t.y), n1(t.z)] : [0, 0, 0],
      };
    };
    return () => {
      intoRef.current = null;
    };
  }, [camera, controls, intoRef]);

  return null;
}

/** THE POLAR LIMIT IS NOT THE WHOLE JOB. It stops the camera swinging under
 *  the pitch, but panning moves the camera and the target together — so a
 *  long drag downward walks the pair straight through the grass and the
 *  angle never changes. This catches that: if the camera has gone below shin
 *  height, lift it back and lift the target by the same amount, which is the
 *  downward pan undone rather than a snap to somewhere else.
 *
 *  Priority stays at the default. A positive one in R3F means taking over
 *  the render loop, and drei's controls already update at −1, so plain 0
 *  runs after them — which is the order this needs.
 */
const FLOOR = 0.8;

function KeepAbove() {
  useFrame(({ camera, controls }) => {
    if (camera.position.y >= FLOOR) return;
    const lift = FLOOR - camera.position.y;
    camera.position.y = FLOOR;
    const c = controls as unknown as {
      target?: THREE.Vector3; update?: () => void;
    } | null;
    if (c?.target) {
      c.target.y += lift;
      c.update?.();
    }
  });
  return null;
}

/** Says when there is actually something to look at.
 *
 *  A 3D scene is NOT ready when React has mounted it. The turf is generated
 *  on a canvas (about 80ms of blade strokes and a Sobel pass), the player
 *  model is 761KB that has to arrive and be decoded, and every geometry in
 *  the view is built on first render. Until all of that lands the canvas is
 *  a dark rectangle — which is indistinguishable from the black rectangle a
 *  crashed WebGL context leaves, and that ambiguity is exactly how "it shows
 *  for a second and dies" became a bug report on this project.
 *
 *  So readiness is reported from INSIDE the Suspense boundary, on the first
 *  frame that actually draws. Suspense resolving means the assets are in;
 *  one frame later means they are on screen. Anything earlier is a guess. */
function FirstFrame({ onReady }: { onReady: () => void }) {
  const done = useRef(false);
  useFrame(() => {
    if (done.current) return;
    done.current = true;
    onReady();
  });
  return null;
}

function Fly({
  to, target, flyingRef,
}: {
  to: Vec3;
  target: Vec3;
  flyingRef: React.MutableRefObject<boolean>;
}) {
  const dest = useMemo(() => new THREE.Vector3(...to), [to]);
  const look = useMemo(() => new THREE.Vector3(...target), [target]);
  /** THE FIRST ARRIVAL IS A CUT, NOT A FLIGHT.
   *
   *  Easing in from wherever the Canvas happened to create the camera looks
   *  smooth on one pitch and is a liability on a page with several: each
   *  canvas starts its own lerp, they run at whatever frame rate they get
   *  while the rest of the page is still laying out, and a scene that is
   *  briefly offscreen or resizing can settle somewhere its neighbour did
   *  not. Two maps of the same thing then open at visibly different zooms,
   *  which reads as one of them being broken.
   *
   *  Snapping on mount makes the opening frame deterministic and identical
   *  everywhere. Flights are kept for what they are actually for: moving
   *  between presets once someone is looking. */
  const first = useRef(true);
  useFrame(({ camera, controls }, dt) => {
    if (!flyingRef.current) return;
    if (first.current) {
      first.current = false;
      camera.position.copy(dest);
      const c0 = controls as unknown as { target: THREE.Vector3; update: () => void } | null;
      if (c0?.target) {
        c0.target.copy(look);
        c0.update();
      } else {
        camera.lookAt(look);
      }
      flyingRef.current = false;
      return;
    }
    camera.position.lerp(dest, Math.min(1, dt * 3.2));
    const c = controls as unknown as { target: THREE.Vector3; update: () => void } | null;
    if (c?.target) {
      c.target.lerp(look, Math.min(1, dt * 3.2));
      c.update();
    } else {
      camera.lookAt(look);
    }
    if (camera.position.distanceTo(dest) < 0.6) flyingRef.current = false;
  });
  return null;
}

export type Focus = {
  pos: Vec3;
  target: Vec3;
};

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
  const [opensOn, setOpens] = useState(() => defaultCam(scene, ""));
  const [ready, setReady] = useState(false);

  const mode = modeOf(portion);
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
    commit(left.length ? left : TABLES[mode]);
    if (current === name) set((left[0] ?? TABLES[mode][0]).name);
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

  return (
    <figure className="m-0">
      <div className="flex flex-wrap items-center gap-2">
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
        {legend && <span className="ml-auto">{legend}</span>}
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
              disabled={!!focus}
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
              className="w-40 rounded border border-line bg-card px-2 py-0.5 text-[11.5px]"
            />
            <button className={pill} onClick={add} disabled={!newName.trim() || !!focus}>
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
        className="relative mt-2 overflow-hidden rounded-xl border border-line"
        style={{ height, background: "linear-gradient(#0e1a26, #172836)" }}
      >
        {/* THE PLACEHOLDER IS A PITCH. A spinner says "something is
            happening"; an outline of the thing you asked for says what, and
            it lands in the same place the real one will, so the page does
            not jump when it arrives. It fades rather than cuts, because a
            hard swap reads as a flicker at these durations. */}
        <div
          aria-hidden={ready}
          className={`pointer-events-none absolute inset-0 z-10 flex items-center justify-center transition-opacity duration-500 ${
            ready ? "opacity-0" : "opacity-100"
          }`}
          style={{ background: "linear-gradient(#0e1a26, #172836)" }}
        >
          <div className="flex flex-col items-center gap-3">
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
        <SceneGuard>
        {/* ANTIALIASING IS NOT ON BY DEFAULT once `shadows` is set, and a
            pitch is nothing but long thin painted lines meeting the camera
            at a grazing angle — the worst case there is. Without it the
            markings crawl and stair-step and the whole thing reads as a
            match engine from 2003. `dpr` up to 2.5 costs fill rate and
            buys most of the rest. */}
        <Canvas
          shadows
          dpr={[1, 2.5]}
          gl={{ antialias: true, alpha: false }}
          // `near` is 0.5, not the 0.1 default. With `far` at 900 that was a
          // 9000:1 depth range, and the painted lines — 3cm above the turf
          // and sixty metres away — fell inside one depth-buffer step and
          // broke into dashes. Nothing is ever within half a metre of this
          // lens; orbit stops at two.
          camera={{ position: seat, fov: 42, near: 0.5, far: 900 }}
        >
          {/* FOG IS WHAT REMOVES THE EDGE. Extending the surround stops the
              pitch looking cut out, but a huge flat plane just moves the
              hard line further away — it is still a line. Fog in the sky's
              own colour dissolves the ground into the background instead,
              so there is nothing to notice: grass gives way to darker turf
              and then to distance. */}
          <color attach="background" args={["#10202c"]} />
          <fog attach="fog" args={["#10202c", 130, 330]} />
          <PitchLights />
          {/* Anything that loads — a texture, a font, a model — suspends,
              and a suspending component inside a Canvas with no boundary
              above it unmounts the entire scene. That is a black rectangle
              indistinguishable from one that is still loading. */}
          <Suspense fallback={null}>
            <Pitch3D portion={portion} goals={goals} arena={arena}>
              {children}
            </Pitch3D>
            <FirstFrame onReady={() => setReady(true)} />
          </Suspense>
          <OrbitControls
            makeDefault
            target={target}
            // Straight down to just above the horizon, all the way round,
            // panning on. The stop is a hair short of a right angle rather
            // than at it, so the camera never lands exactly level with the
            // target and leaves the grass edge-on and one pixel thick.
            minPolarAngle={0}
            maxPolarAngle={Math.PI / 2 - 0.02}
            minDistance={2}
            maxDistance={520}
            enablePan
            enableDamping
            dampingFactor={0.08}
            zoomSpeed={0.9}
            onStart={() => {
              flyingRef.current = false;
            }}
          />
          <Fly to={seat} target={target} flyingRef={flyingRef} />
          <KeepAbove />
          {tune && <Grab intoRef={grabRef} />}
        </Canvas>
        </SceneGuard>
      </div>

      <p className="mt-1.5 min-h-[1.4em] text-[12.5px] text-ink-2">
        {caption ?? (
          <span className="text-ink-3">
            Drag to orbit · scroll to zoom · right-drag to pan. A preset flies
            you back.
          </span>
        )}
      </p>
    </figure>
  );
}
