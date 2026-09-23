# The ground and the turf

A geometrically perfect pitch on an empty plane still reads as a diagram.
Two things are missing, and neither is "a nicer green".

## 1. Nothing in the picture has a known height

The goal is 2.44m tall, but the eye has nothing to check that against, so the
scene flattens: it could be a model on a table or a real ground shot from a
helicopter and there is no way to tell. Perspective alone does not fix this —
convergence tells you about *relative* depth, not scale.

Give the eye objects whose size it already knows, spread across the range:

| object | height | what it does |
|---|---|---|
| corner flag | 1.5m | the near reference, and the smallest |
| perimeter hoardings | 1.0m | a continuous line at a fixed distance — parallel lines converging is the strongest depth cue there is |
| dugout | 2.1m | human scale, obviously built for people |
| floodlight pylon | 20–25m | settles whether this is big |

The hoardings do the most work of the four. A dugout or a flag is one object
at one distance; a run of boards is a *horizon* that converges, and it gives
every other object something to be measured against.

Details that matter more than they should:

- **Size the furniture against the region actually drawn**, not the full
  pitch. In half-pitch mode, furniture placed at full-pitch corners floats
  past the edge of the grass; placed at the drawn region's corners, the same
  code produces a closed training arena, which is a coherent thing to be
  looking at.
- **Corner flags go at real corners only.** In half-pitch mode the near edge
  of the grass is the halfway line. A flag there quietly tells the reader
  something false about where they are.
- **Check your camera seats against the new geometry.** A pylon 16m out from
  the corner can land on top of a "corner" preset. Dot the pylon's offset
  from the camera against the view direction — if it is negative the pylon is
  behind the lens and cannot be in shot.
- **Generate the advertising artwork on a canvas**, with your own text. It
  needs no fetch, so it cannot suspend, and a ground ringed with real brands
  is a different kind of claim entirely.
- **Anisotropic filtering on the boards.** A hoarding run is seen almost
  edge-on from every seat, which is the case trilinear filtering handles
  worst; without it the far half turns to grey mush by about thirty metres.
  `texture.anisotropy = gl.capabilities.getMaxAnisotropy()`.
- An **open-fronted dugout** is one box with `side: THREE.BackSide` — only
  faces pointing away from the camera render, so you look through the near
  wall and see the inside of the far one. Add the roof as a separate slab,
  because BackSide culls it from above and leaves an open crate.

## 2. A flat colour has no surface

Lit by a directional sun, a constant colour returns the same value at every
point. The turf reads as paper, and shadows falling on it look pasted rather
than cast.

Build **one height field** and derive both maps from it, so they agree —
disagreeing colour and normal maps look subtly wrong in a way nobody can
name. Two components:

- `patch` — low-frequency value noise (3 octaves, e.g. 4/9/24 lattices).
  Mower wander, wear, where the water lands.
- `blade` — tens of thousands of short strokes, each fading along its length
  so it has a tip. The fade is what reads as grass rather than as noise.

```ts
colour    = 0.62 + patch * 0.05 + blade * 0.30   // brightness only
heightFor = blade + patch * 0.10                  // normals want the detail
```

Keep the colour map near-neutral so the mesh's own `color` still decides the
hue — one texture then serves every band, and the run-off and surrounds too.

**Scale the blades by a high percentile, not the maximum.** A handful of
pixels where several strokes crossed will otherwise set the scale and press
everything else flat. The symptom is unmistakable: the pitch looks like
billiard cloth.

**Tile by construction.** Write the strokes with wrapped indices and sample
the noise lattices with wrapped lookups, and the result tiles with no seam
whatever the tile size.

### Keeping the repeat invisible

A seamless tile is not the same as an unnoticeable one. 512 pixels over a 5m
tile is fourteen repeats across a pitch, and it read as an obvious grid —
worse than the flat green it replaced. Two things cause that, and only one is
about size:

- **The tile was too small.** 1024 over 9m keeps just under a centimetre per
  texel and cuts the repeat to seven. Go coarser still for distant ground —
  20m+, since nobody is inspecting blades at 200 metres.
- **The colour map carried the low-frequency noise.** That is the only
  content with features big enough for the eye to match between tiles, so
  every repeat showed the same blotch in the same place. Take the patchiness
  almost entirely out of the colour and leave it in the normals, where it
  becomes lighting rather than pigment.

Real grass over eighteen metres is nearly uniform in colour anyway. The
texture you see in a photograph of a pitch is light on blades, not pigment.
If the colour map looks boring on its own, that is usually correct.

**Colour maps can only darken.** An 8-bit texture multiplies, so a mean of
0.79 means every tinted colour comes out 21% darker than the hex you wrote.
Pitch the greens brighter to compensate, or the "improvement" is a pitch in
shadow.

## 3. Mowing stripes, and two things that look right but do nothing

Stripes are not two shades of grass. They are the **same grass bent in
opposite directions**, so one band returns the sun toward you and the next
away. Two corrections are needed to reproduce that, and both are invisible
until measured.

**A zero-mean normal map cannot make a stripe.** Rotating ordinary bump noise
by 180° measures a *0.0%* brightness difference. Diffuse lighting is
near-linear in the normal, so the average over a symmetric perturbation is
identical either way. The grass has to actually lean — add a constant tilt to
every normal along the mower's direction of travel:

```ts
const nx = -(h[x + 1] - h[x - 1]) * SLOPE - LIE;   // LIE ≈ 0.24
const ny = -(h[y + 1] - h[y - 1]) * SLOPE;
```

That measures ~14% between bands, which is about what a photograph shows.

**`texture.rotation` does not rotate the normal.** It changes where the
shader samples, not what the sampled vector means, so the lean would point
the same way in every band. What mirrors the perturbation is negating
`normalScale`:

```tsx
normalScale={flip ? new THREE.Vector2(-1, -1) : new THREE.Vector2(1, 1)}
```

The two together — rotated lookup, mirrored normal — are a genuine 180° turn
of the surface.

**Get the axis right.** Bands stacked along the pitch's *length* were cut by
a mower driving across its *width*, so the grass lies along the width. Lean
along the wrong axis and the stripe is weak or absent depending on where the
sun happens to be.

The difference is diffuse, so it is fixed by the sun rather than by where the
reader is standing — exactly like a photograph. Keep a small colour
difference between the bands as well (~3%), purely as a floor so the stripes
never disappear entirely at an unlucky sun angle.

## 4. Measure it outside the browser

Procedural texture work is the one part of a 3D scene you can test without
rendering anything. Port the generator to a standalone script, write PNGs,
and check:

- the colour map **tiled 2×2** — a seam runs straight down the middle if the
  wrapping is wrong
- the normal map, for banding or a stuck channel
- a **stripe test**: the same field twice, the second mirrored, both lit by
  one hard-coded sun, with the mean brightness of each half printed

That last one is what turns "the stripes look a bit subtle" into "the flip
buys 0.0%, the mechanism is wrong". A script that prints a number converges
in minutes; iterating on screenshots does not.
