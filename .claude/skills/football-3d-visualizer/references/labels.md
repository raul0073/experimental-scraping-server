# Labels and text in a 3D scene

Text is where 3D scenes most often go wrong in ways that look like the
component is broken rather than mis-tuned.

## `distanceFactor` scales labels UP as the camera closes in

drei's `<Html distanceFactor={n}>` renders at roughly `n / distance`. A
value tuned while looking at the whole pitch from 80m makes the same label
three or four times normal size from a close camera at 12m — one player's
name filling a third of the frame and hiding the goal behind it.

**Tune at the closest camera position the view supports**, not the default
one. Rough starting points for a football scene:

| use | factor |
|---|---|
| small annotations — distances, angles, zone values | 10–12 |
| a selected object's name and primary value | 11–14 |
| a headline result that should dominate | 35–45 |

## drei `<Text>` fetches a font, and that can kill the scene

`<Text>` renders through troika-three-text, which loads a font file before it
can draw. Loading suspends. **A component that suspends inside a `<Canvas>`
with no boundary above it unmounts the entire scene** — you get a black
rectangle, indistinguishable from one still loading, with the real error only
in the console. The bug report that comes back is "it shows for a second and
crashes".

Prefer `<Html>` labels: they use the page's own font, cannot fetch, cannot
fail, and inherit the site's typography for free. If you do want SDF text in
the scene, bundle the font locally and wrap it in `<Suspense>`.

Wrap scene contents in `<Suspense fallback={null}>` regardless — textures and
models suspend too.

## Billboard or flat is a decision per element

Ask whether the thing belongs to the **ground** or to the **air**.

**Painted flat on the grass** (`<Html transform rotation={[-Math.PI/2, 0, yaw]}>`)
— distances, angles, zone names. These read as a diagram drawn on the pitch,
which is exactly right for a measurement. The cost: they take perspective
with the pitch and shrink toward nothing at grazing angles, so if the view
spends most of its time low and behind, a flat label is a bad trade.

**Billboard, facing the viewer** — a point in the goal mouth, a player
marker, an outcome chip. Anything at height *must* turn to face the camera:
geometry fixed to a vertical plane goes edge-on and vanishes the moment the
camera leaves that plane, which is most of the time.

Mixing both deliberately is good design. Defaulting everything to billboard
makes a scene of floating captions; defaulting everything to flat makes half
of it invisible.

## Over a coloured overlay, a label needs a plate — not a shadow

White text with a dark text-shadow is the reflex and it works over grass. It
fails over a selection overlay, because the overlay is painted in the datum's
own colour, the label hangs directly in front of it, and a soft dark shadow
on a saturated field is no contrast at all: the name reads as a dark smudge
on red.

Give the label a solid dark plate and put the datum's colour on its **edge**,
where it says which object the label belongs to without competing with the
text. That works over any overlay colour, so it does not need revisiting when
a new outcome category shows up.

## Placement: overlap is a geometry problem

Labels collide in predictable places and moving them is easy once you see
why. The common one: an angle marker at the *midpoint* of its arc points
straight at the goal — which, from behind the shooter, is exactly where the
object's own name label hangs. Offset it a quarter of the way round the arc
instead.

More generally: **the axis the reader looks down is the one place nothing
should sit.** Every useful camera on a shot lines up with the shot — behind
the goal, behind the shooter, at his eye — so a label at the midpoint of
that line, the ball's own label, and the reader's eye all fall on the same
column of screen, and the far one disappears behind the near one. Height
does not save it, because perspective already puts the far label higher.

Push labels **sideways off the line**, not up. A few metres along the ground
perpendicular is enough, and it survives every camera:

```ts
const [dx, dz] = [0 - sx, goalZ - sz];
const L = Math.hypot(dx, dz) || 1;
const perp = [dz / L, -dx / L];        // in the ground plane
// midpoint of the line, then five metres to one side of it
[sx * 0.5 + perp[0] * 5, 1.3, sz + dz * 0.5 + perp[1] * 5]
```

Put the two annotations of one object on opposite sides — angle hugging the
vertex on one, distance out on the other — and they cannot collide at any
viewing angle.

## Mark an angle like an angle

A number floating beside a vertex is a caption. An angle is a small arc
struck across the corner it belongs to, with the degrees beside the arc.
That single change turns a scene from "data dumped on a render" into a
diagram someone can read.

## Always wrap a canvas in an error boundary

A failed WebGL canvas renders nothing at all. It is visually identical to
one still loading, so the only available bug report is "it doesn't work".
An error boundary turns that into a sentence on screen and a retry button:

```tsx
export class SceneGuard extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    return this.state.error
      ? <Message text={this.state.error.message} onRetry={...} />
      : this.props.children;
  }
}
```

This is worth having from the first commit, not added after a black screen.
