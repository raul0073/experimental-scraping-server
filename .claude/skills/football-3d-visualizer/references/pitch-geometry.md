# Pitch geometry

Real dimensions cost nothing and buy accuracy that people notice: a shot
drawn just outside the box really was just outside it.

## FIFA dimensions, metres

| element | size |
|---|---|
| pitch | 105 × 68 |
| line width | 0.12 |
| goal | 7.32 wide × 2.44 high, posts ~0.12 |
| goal area (six-yard box) | 18.32 × 5.5 |
| penalty area | 40.32 × 16.5 |
| penalty spot | 11 from the goal line |
| centre circle | 9.15 radius |
| penalty arc (the D) | 9.15 radius, struck from the spot |
| corner arc | 1 radius |

## What makes it read as football

In order of effect. The first two matter more than every geometric detail
combined.

**1. Mowing stripes.** Eight to ten bands alternating between two close
greens, running across the pitch. A flat green rectangle is a lawn; striped
grass is a pitch before a single line is drawn.

**2. Goals, with nets.** Four posts and a light wireframe plane for the net.
Without them, a rectangle of grass viewed from behind the byline is an empty
field and the whole scene feels wrong in a way people struggle to name.

**3. Lines as painted geometry.** 12cm-wide planes lying on the grass, not
`LineBasicMaterial`. Hairlines are one pixel wide, do not take light, and
disappear at any angle except straight down. See **Markings that break into
dashes** below — laying them on the turf is the fiddly part.

**4. A surround that runs far past the camera's reach.** A tight dark
rectangle a few metres off the touchline draws a hard frame and the pitch
looks cut out and pasted onto a void. Extend it well beyond the furthest
camera position and keep it close to the turf in tone, with a narrower band
of darker grass just off the pitch the way a real ground has run-off.

**5. Antialiasing.** Long thin lines meeting the camera at a grazing angle
are the worst case for aliasing. `gl={{ antialias: true }}` must be set
explicitly — enabling `shadows` on a Canvas does not imply it — and
`dpr={[1, 2.5]}` handles most of the rest.

**6. Shadow resolution.** Work out metres per texel: a 2048 map over a 140m
frustum is 7cm per texel and every shadow edge is visibly stepped. 4096 over
160m is ~4cm and reads clean. Add `shadow-normalBias` to stop acne on the
flat turf.

## Building the markings

Two primitives cover everything:

```tsx
// a straight strip of paint
<mesh position={[x, 0.012, z]} rotation={[-Math.PI / 2, 0, rot]}>
  <planeGeometry args={[w, d]} />
  <meshStandardMaterial color="#f2f6f3" roughness={0.9} />
</mesh>

// an arc: centre circle, the D, corner quadrants
<mesh position={[x, 0.012, z]} rotation={[-Math.PI / 2, 0, 0]}>
  <ringGeometry args={[r - 0.06, r + 0.06, 96, 1, from, to - from]} />
  <meshStandardMaterial color="#f2f6f3" side={THREE.DoubleSide} />
</mesh>
```

### Markings that break into dashes

Paint lying a centimetre above the turf is a **coplanar decal**, and a pitch
is the worst case for one: the far markings are sixty metres away and the
camera is set up to see a whole stadium. The symptom is lines that dissolve
into dots and dashes down the far end while the near ones look fine, and it
is a depth-buffer precision problem, not an antialiasing one.

`near: 0.1` with `far: 900` is a 9000:1 range, and depth precision falls off
with distance — at sixty metres one buffer step can be larger than the gap
between the paint and the grass, so which surface wins is decided per pixel
by rounding. Three fixes, and use all three because each leaves a case:

```tsx
camera={{ near: 0.5, far: 900 }}        // 5x the precision, costs nothing
// paint at y = 0.03, not 0.012 — still far too small to read as a step
<meshStandardMaterial polygonOffset polygonOffsetFactor={-2} polygonOffsetUnits={-4} />
```

`near` is the big one. Raise it as far as the closest camera position allows
— with orbit `minDistance` at 2 there is nothing within half a metre of the
lens, so 0.5 is free. (`logarithmicDepthBuffer` also solves it, but it costs
performance and does not cooperate with `polygonOffset`.)

### The rotation trap that catches every arc

A ring is built in its own **XY plane** and then rotated flat by `-π/2` about
X. That maps **local +Y to world −Z**. So a world direction `(dx, dz)` is a
local angle of `atan2(-dz, dx)` — there is a sign flip hiding in every arc
you place by angle.

This catches corner arcs and angle markers reliably. Prefer an explicit
lookup over a clever formula; a nested ternary computing which quarter of a
circle to draw is unreadable and will be wrong for half its cases:

```ts
// corner at (ex * halfWidth, ez * halfLength); the arc bulges INTO the pitch
const CORNER_FROM: Record<string, number> = {
  "1,1": Math.PI / 2,
  "1,-1": Math.PI,
  "-1,1": 0,
  "-1,-1": -Math.PI / 2,
};
```

### The D

Only the part of the 9.15m circle **outside** the penalty area is drawn. The
box edge is `16.5 − 11 = 5.5m` from the spot, so the arc runs
`acos(5.5 / 9.15) = 53.1°` either side of straight ahead — a 106° sweep.

```ts
const half = Math.acos(Math.min(1, (PEN_D - SPOT) / CIRCLE));
```

Note where the clamp goes. `Math.min(1, PEN_D - SPOT) / CIRCLE` clamps 5.5
to 1 *before* dividing and gives `acos(1/9.15) = 83.7°` — a 167° sweep that
wraps back **inside** the box, the one place the D never goes. The `min`
guards `acos` against a ratio above 1; it is not a limit on the distance.

Checks on the corrected arc: it meets the box edge 7.31m either side of
centre and reaches 3.65m beyond the line at its deepest.

## Half-pitch mode

Shot maps and final-third work want the attacking half only — the other half
holds about four shots a season and drawing it halves the useful resolution.

- Clip the grass, the touchlines and the stripes to `z ≥ 0`
- Draw one goal and one set of end markings
- Draw the halfway line and the **half** of the centre circle that survives
- Camera seats and the orbit target both need their own values; reusing
  full-pitch ones puts the camera 80m from a 50m subject
