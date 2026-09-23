---
name: football-3d-visualizer
description: >
  Real-time 3D football tactical visualisation — pitch geometry, coordinate
  frames, camera behaviour, in-scene labelling, and telemetry streaming with
  React Three Fiber, Three.js and FastAPI WebSockets. Use this whenever the
  work involves drawing a football pitch or anything standing on one (shot
  maps, heat maps, pass networks, formations, player or ball tracking,
  territory), converting Opta / StatsBomb / Understat / SkillCorner
  coordinates into a 3D scene, streaming match telemetry to a browser, or
  fixing a 3D football scene that renders wrong — mirrored pitches, labels
  that dwarf the pitch, cameras that snap back, black canvases, jittery
  tracking. Also use it when someone asks for "better" or "less flat" match
  visuals, or says a 3D pitch looks like a bad match engine, even if they
  never mention Three.js by name.
---

# 3D football visualisation

A football pitch is a plane, and almost every football metric is *a value at
a place on that plane*. That is what makes 3D worth the trouble here: height
is free and unused, and people read height far more accurately than colour.
It is also what makes it easy to waste — a 3D bar chart is strictly worse
than a bar chart, and a flat disc lying on grass is a 2D scatter plot that
happens to be rendered by a GPU.

Before building anything, answer one question: **does the third dimension
carry information, or decoration?** Good answers in this domain:

- *height on the pitch plane* — territory, pressure, chance volume per zone
- *the goal as a real object* — the angle a shooter actually had, where the
  ball crossed the line, what a keeper could reach
- *trajectory* — a pass or shot through space, including its arc
- *time* — but almost always better as animation than as a third axis

If the answer is "it looks cooler", build it flat. You will get a chart
people can read, in a tenth of the time.

## The rule that keeps 3D honest

**3D shows shape. Numbers stay readable for precision.** A reader looks at
the scene to understand a side and reads a label or a table to quote a
figure. The moment someone has to estimate a value by eyeing a column
against a perspective view, the third dimension has cost more than it gave.

## Coordinate frames — read `references/coordinates.md` before converting

This is where the expensive mistakes live. Every provider uses a different
frame, several of them put y where you do not expect it, and **a mirrored
pitch looks completely plausible** — nothing is obviously broken, it just
quietly reports that a winger plays on the wrong flank in every picture on
the site.

Two rules that prevent most of it:

1. **One conversion function, exported from the pitch module.** Every other
   component imports `toX()` / `toZ()`. If provider arithmetic appears in
   two files, they will disagree eventually.
2. **Build a coordinate-check view early** — labelled pins at known points
   `(own goal, far goal, each corner, the penalty spot)`. It takes ten
   minutes and it is the only thing that catches a mirror. Put a pin at the
   penalty spot derived from provider coordinates next to the painted spot
   derived from FIFA dimensions; if they do not coincide, one is wrong.

Two-team scenes need special care: when both sides are drawn on one pitch,
one team's data must be **rotated 180°** into the other's frame, which flips
*the third and the flank together*. Getting only one of those right is the
classic bug.

## Making a pitch read as football

Real dimensions are cheap and worth it — a shot drawn just outside the box
should really be just outside it. `references/pitch-geometry.md` has the
full table and the marking-by-marking build order.

What actually makes a green rectangle read as football, in order of effect:

1. **Mowing stripes.** Eight to ten alternating bands. This does more than
   everything else combined.
2. **Goals, with nets.** A pitch without goals is a lawn.
3. **Lines as painted geometry with real width (~12cm)**, lying on the
   grass — not `LineBasicMaterial` hairlines, which vanish at any camera
   angle except straight down.
4. **A surround that runs far past the camera's reach.** A tight dark
   rectangle a few metres off the touchline draws a hard black frame and the
   pitch reads as cut out and pasted onto a void.
5. **Antialiasing and adequate shadow resolution.** A pitch is nothing but
   long thin lines meeting the camera at a grazing angle — the worst case
   for aliasing. Set `gl={{ antialias: true }}` explicitly; enabling
   `shadows` on a Canvas does not imply it.

## Scale and surface — read `references/ground-and-turf.md`

A correct pitch on an empty plane still reads as a diagram, for two reasons
that neither geometry nor a nicer green will fix.

**Nothing in the picture has a known height.** The goal is 2.44m but the eye
has nothing to check that against, so the scene flattens and could as easily
be a model on a table. Put in objects whose size people already know, across
the range: corner flags (1.5m), perimeter hoardings (1m), dugouts (2.1m),
floodlight pylons (20m+). The hoardings do the most work — a converging run
of boards is a horizon, and everything else gets measured against it.

**A flat colour has no surface.** Generate the turf: one height field, from
which come a colour map and a normal map that agree with each other. Draw it
on a canvas rather than loading an image — no fetch, so it cannot suspend,
and it tiles by construction.

And stripes are not two shades of green. They are the same grass bent in
opposite directions, which takes a constant *lean* baked into the normals
(zero-mean bump noise rotated 180° measures a 0.0% difference) and a negated
`normalScale` to mirror it (`texture.rotation` changes where you sample, not
what the sampled vector means). The reference has the measurements.

## Camera — the reader's, not the page's

The single most common failure is a camera that fights the user. If you
animate toward a preset every frame, any drag is undone instantly and any
scroll snaps back; from the outside it looks as though orbit and zoom are
simply broken.

- A flight happens **once**, when a preset is chosen, and the first pointer
  interaction cancels it permanently (`OrbitControls onStart`).
- Named seats — *overhead, touchline, behind the goal, corner* — beat free
  navigation for getting somewhere useful. Keep **overhead** because it
  matches the 2D map people already know.
- **Seat positions must depend on what is framed.** A half-pitch view using
  full-pitch distances puts the camera 80m from a 50m subject.
- "Behind the goal" means behind the **attacking** goal.
- Allow full rotation and panning — **except down through the ground**. The
  turf, the markings and the run-off are single planes facing up, so from
  underneath they are not dark, they are *absent*: nets and hoardings
  floating over nothing, with the pitch gone. Stop a hair short of a right
  angle (`maxPolarAngle: Math.PI / 2 - 0.02`) rather than at it, so the
  camera never lands exactly level with the target and leaves the grass
  edge-on and one pixel thick.
- **The polar limit is not the whole job.** Panning moves the camera and the
  target together, so a long downward drag walks the pair straight through
  the pitch without ever changing the angle. Clamp the camera's height too,
  lifting the target by the same amount so it reads as the pan being undone
  rather than a snap:

```tsx
useFrame(({ camera, controls }) => {          // default priority: a positive
  if (camera.position.y >= FLOOR) return;     // one takes over the render
  const lift = FLOOR - camera.position.y;     // loop, and drei's controls
  camera.position.y = FLOOR;                  // already update at −1
  controls.target.y += lift;
  controls.update();
});
```

  Check every preset and every one-off focus against the limit before
  shipping it: a seat the controls immediately clamp is a preset that
  silently lands somewhere other than where it says.

For a shot map and similar half-pitch work, aim at the penalty spot rather
than the centre of the half — the action clusters between the spot and the
edge of the box.

**Store a seat as `{ pos, target }`, never a position alone.** Some views
need their own aim — "from halfway", looking down the pitch at the goal, is
meaningless pointed at the middle of the frame — and a seat that carries both
is also a seat that can be captured whole.

### Let the person who can see the render set the numbers

Camera seats are pure taste, and guessing at them through screenshot round
trips is the slowest loop in this work. Put a **capture button** in the lab:
it reads the live `camera.position` and `controls.target`, rounds them, and
saves them against the current view. Worth getting right:

- Save per **mode as well as per view** — full-pitch and half-pitch seats are
  different numbers for the same name.
- Persist to `localStorage` and read it in **every** scene, not just the lab.
  A seat tuned in the lab should immediately be the seat the real pages use,
  or nobody can tell whether it worked.
- Read the saved value in a **guarded lazy `useState` initialiser**, not an
  effect — an effect gives one render at the old position and a visible jump.
- Add a **"copy code"** button that emits the seat tables as source. Without
  it the tuning lives in one browser and dies there; with it, capturing ends
  in a paste and the numbers become everyone's defaults.
- Capturing must **not** trigger a flight — the camera is already where it
  was just put. And disable it while a one-off focus (a shooter's eye) is
  active, or you capture that instead of the preset.

## Labels in a 3D scene — read `references/labels.md`

Three traps, all of which produce confident-looking broken output:

- **`distanceFactor` scales labels UP as the camera closes in.** A value
  tuned at 80m makes text fill a third of the frame at 12m. Tune at the
  *closest* camera position you support.
- **drei's `<Text>` fetches a font**, which suspends. A suspending component
  inside a `<Canvas>` with no boundary above it unmounts the whole scene —
  a black rectangle indistinguishable from one still loading. Prefer HTML
  labels, and wrap scene contents in `<Suspense>` regardless.
- **Billboard or flat is a decision, not a default.** Things painted on the
  grass (distances, angles, zone labels) read as a diagram when flat, but
  shrink to nothing at grazing angles. Things in the air (a point in the
  goal mouth, a player marker) must face the viewer or they go edge-on and
  disappear. Decide per element, by whether it belongs to the ground.

Always wrap a 3D canvas in an **error boundary**. A failed WebGL scene
renders nothing, identical to one still loading, with the real error only in
the console — which is how a bug report becomes "it shows for a second and
crashes".

## Performance

Detail is in `references/performance.md`. The short version:

- **Lazy-load the 3D bundle.** Three.js is ~600KB gzipped. Dynamic-import
  the scene with `ssr: false` so pages that show tables carry none of it,
  then verify by grepping the built HTML for the chunk name.
- **`THREE.InstancedMesh` past a few hundred objects** — 22 outfield players
  and a ball can be plain meshes; ten thousand shots cannot.
- **Hide rather than fade on selection.** Fading five hundred objects to 12%
  leaves them lit, glowing and eating clicks.
- `dpr={[1, 2.5]}` is usually the best quality-per-watt lever.

## Streaming telemetry — read `references/streaming.md`

For live or replayed tracking (player and ball positions at 10–25Hz):

- **Interpolate on the client, never render raw packets.** Buffer one or two
  frames and interpolate between them in the render loop. Rendering packets
  as they land produces visible stutter because network timing never matches
  frame timing.
- **Send compact typed arrays, not JSON objects per player.** A frame is a
  flat `Float32Array` of positions plus a frame index.
- **The server's clock is the truth; the client's frame rate is not.**
  Drive interpolation from a playback clock that can be paused, scrubbed and
  rate-changed independently of the render loop.

`scripts/pitch_frame.py` is a reference FastAPI WebSocket sender with the
packing format, and `references/streaming.md` has the matching client hook.

## Reference files

| file | read it when |
|---|---|
| `references/coordinates.md` | converting any provider's data, or a scene looks mirrored |
| `references/pitch-geometry.md` | building or correcting pitch markings |
| `references/ground-and-turf.md` | the scene looks flat, small, or made of felt; stripes, grass, stadium furniture |
| `references/labels.md` | text in a scene is the wrong size, hidden, or crashing |
| `references/performance.md` | frame rate, bundle size, or thousands of objects |
| `references/streaming.md` | live or replayed tracking data |

## Working method

Build a **component lab page** — every piece on its own, with synthetic data
and no fetching. A piece that only renders inside a page with four payloads
loaded is a piece nobody can iterate on, and every visual bug gets found in
the slowest possible place. Give the synthetic data a realistic *shape*
(most chances in the final third, almost none in your own half); flat noise
hides exactly the problems the lab exists to catch.

Then expect to be told it looks wrong several times. Visual work converges
by showing, not by reasoning — if you cannot see the render yourself, say so
early and ask for screenshots rather than guessing through iterations.

**Measure whatever can be measured.** Some of this work is not really visual:
procedural textures, coordinate conversions and lighting mechanisms can all
be ported to a standalone script that writes a PNG and prints a number. That
is how "the stripes look a bit subtle" becomes "the flip buys 0.0%, so the
mechanism is wrong" — in minutes, and without spending someone else's
attention on a screenshot round trip.
