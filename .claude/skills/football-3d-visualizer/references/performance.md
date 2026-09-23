# Performance

## Keep three.js off pages that do not use it

Three.js plus fiber and drei is roughly 600KB gzipped — often several times
the rest of an analytics site. Dynamic-import the scene so only the view
that needs it pays:

```tsx
const Scene = dynamic(
  () => import("./three/PitchScene").then((m) => m.PitchScene),
  { ssr: false, loading: () => <Placeholder /> },
);
```

`ssr: false` is not optional: there is no canvas to render on a server, and
on a statically exported site there is no server at all.

**Verify it worked** rather than assuming. Grep the built HTML for the chunk
containing `WebGLRenderer` and confirm it appears on zero pages — a bundler
can hoist a dynamic import into a shared chunk if something else references
the module eagerly.

## Instancing

Plain meshes are fine into the low hundreds. Past that, one draw call per
object dominates the frame.

- 22 players and a ball: plain meshes, with per-object materials and click
  handlers. Simpler, and instancing buys nothing.
- A season of shots (5,000–10,000), a particle-style heat cloud, a passing
  network across a whole league: `THREE.InstancedMesh`, with per-instance
  colour via `instanceColor` and position via `setMatrixAt`.

Raycasting against an `InstancedMesh` returns `instanceId`, so hover and
click still work — you look the datum up by index rather than attaching it
to the object.

## Selection: hide, do not fade

When a reader picks one object out of hundreds, fading the rest to low
opacity leaves them lit, still glowing if they have emissive, still casting
shadows and still intercepting clicks. The thing that was selected ends up
buried in the clutter selecting it was meant to clear.

Render only what is selected. It is also dramatically faster.

## Encoding magnitude on a 3D object

Match the geometry to the perceptual channel:

- a **disc** whose value is area → radius goes as `√value`
- a **sphere** whose value is volume → radius goes as `∛value`

Letting radius go as the value directly makes a 0.40 chance sixteen times
the area of a 0.10 one, and every large value shouts while nothing else is
legible. Add a floor so the smallest objects stay clickable.

## Grading an overlay's opacity along its length

A highlight volume — a shot's angle of goal, a pressing cone, a passing
lane — is a solid the camera usually sits *inside*. At its apex every surface
of it meets, so whatever flat opacity looks right across the middle stacks
into a slab of neat colour exactly where the reader is standing.

Fix it with **per-vertex alpha**, fading toward the apex and opening toward
the far end. It solves the density where it is worst and it reads as a beam
thrown at the target rather than as a coloured region.

```ts
// alpha needs a FOUR-component colour attribute — three.js switches on
// USE_COLOR_ALPHA from itemSize, so a 3-component one silently gives a
// uniform overlay back and looks like the gradient simply did nothing
g.setAttribute("color", new THREE.Float32BufferAttribute(rgba, 4));
```

```tsx
<meshBasicMaterial vertexColors transparent depthWrite={false} side={THREE.DoubleSide} />
```

`vertexColors` multiplies by `material.color`, so leave that white. Values
around 0.04 at the apex and 0.2–0.25 at the far end read as a light shaft;
much more and it is a wall again.

## Canvas settings

```tsx
<Canvas
  shadows
  dpr={[1, 2.5]}
  gl={{ antialias: true, alpha: false }}
  camera={{ fov: 42, far: 900 }}
/>
```

- `dpr` is the best quality-per-watt lever; 2.5 is usually the point of
  diminishing returns on a pitch.
- `antialias` is **not** implied by `shadows`, and a pitch is the worst case
  for aliasing — long thin painted lines at grazing angles.
- `alpha: false` saves a compositing pass when the canvas has an opaque
  background anyway.
- Size shadow maps by metres per texel, not by habit: a 2048 map over a 140m
  frustum is 7cm per texel and visibly stepped.

## Render-loop discipline

- Anything animating belongs in `useFrame`, not in React state. A `setState`
  per frame re-renders the tree sixty times a second to move one object.
- Lerp with `Math.min(1, dt * k)` rather than a fixed step, so behaviour is
  frame-rate independent.
- Memoise geometries built from data (`useMemo` on the inputs). Rebuilding a
  `ShapeGeometry` every frame is invisible in a small scene and fatal in a
  large one.
- Cap the work, not the frame rate: prefer fewer objects to a throttled loop.
