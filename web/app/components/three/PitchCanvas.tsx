"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import type { Seat, Vec3 } from "./cameras";
import { round1 as n1 } from "./cameras";
import { LabelScale, labelScaleFor } from "./labelScale";
import { Pitch3D, PitchLights } from "./Pitch3D";

/** THE CANVAS. Everything in this file touches WebGL, and nothing outside it
 *  in the scene stack does any more.
 *
 *  It used to live in `PitchScene.tsx` alongside the toolbar, the camera
 *  tuner, the caption and the loading placeholder — none of which need three,
 *  all of which now have to render on a phone BEFORE anyone has asked for a
 *  3D scene. Splitting the file is what lets `PitchScene` import this one
 *  lazily: on a small screen the flat map draws and the 600KB is never
 *  fetched.
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

/** Publishes how wide this canvas actually is, as a label-size ratio. It has
 *  to be inside the Canvas to know, and it re-renders only when the size
 *  crosses into a new value — which is a resize, not a frame. */
function Labels({ children }: { children: React.ReactNode }) {
  const width = useThree((s) => s.size.width);
  const scale = labelScaleFor(width);
  return <LabelScale.Provider value={scale}>{children}</LabelScale.Provider>;
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

export default function PitchCanvas({
  children,
  portion = 1,
  goals = true,
  arena = true,
  seat,
  target,
  flyingRef,
  grabRef,
  tune = false,
  dpr,
  onReady,
}: {
  children?: React.ReactNode;
  portion?: number;
  goals?: boolean;
  arena?: boolean;
  seat: Vec3;
  target: Vec3;
  flyingRef: React.MutableRefObject<boolean>;
  grabRef: React.MutableRefObject<(() => Seat) | null>;
  tune?: boolean;
  /** Device pixel ratio ceiling. THE BEST QUALITY-PER-WATT LEVER THERE IS,
   *  and the reason it is a prop: 2.5 on a laptop is the point of diminishing
   *  returns, and 2.5 on a phone with a 3x screen means shading roughly six
   *  times the pixels of the CSS box on a chip with no fan and a battery. The
   *  caller knows which it is looking at. */
  dpr: [number, number];
  onReady: () => void;
}) {
  return (
    /* ANTIALIASING IS NOT ON BY DEFAULT once `shadows` is set, and a
       pitch is nothing but long thin painted lines meeting the camera
       at a grazing angle — the worst case there is. Without it the
       markings crawl and stair-step and the whole thing reads as a
       match engine from 2003. */
    <Canvas
      shadows
      dpr={dpr}
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
        <Labels>
          <Pitch3D portion={portion} goals={goals} arena={arena}>
            {children}
          </Pitch3D>
        </Labels>
        <FirstFrame onReady={onReady} />
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
  );
}
