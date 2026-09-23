# Coordinate frames

Every provider puts the origin somewhere different and several put `y` where
you do not expect it. A mirrored pitch is the most expensive bug in this
domain because **nothing looks broken** — the scene renders, the markings are
right, the data is plotted. It simply says a winger plays on the wrong flank,
in every picture, forever.

## The providers

| provider | x | y | units | notes |
|---|---|---|---|---|
| **Opta / WhoScored** | 0 own goal line → 100 opponent's | **0 RIGHT touchline → 100 LEFT** | 0–100 both | y is the trap: it runs right-to-left |
| **Understat** | 0 own goal line → 1 opponent's | 0 → 1 across | 0–1 both | penalties sit at exactly (0.885, 0.500) |
| **StatsBomb** | 0 → 120 toward opponent | 0 → 80 across | yards-ish | y increases toward the **left** touchline |
| **SkillCorner / tracking** | −52.5 → +52.5 | −34 → +34 | metres, centred | already metric; usually needs only an axis swap |

Verify rather than trust. Providers change, and a league feed can differ
from the same provider's cup feed.

### Verifying a frame from the data

- **Penalties.** Filter to penalty shots and take the mean. It must land on
  the spot: 11m from the goal line, dead centre. This confirms both axes'
  scale and the centre, and is the cheapest check available.
- **Goal-mouth spread.** For providers with a goal-mouth coordinate, goals
  must fall inside the posts and under the bar; shots off the post sit just
  outside. That pins the goal frame's own scale.
- **Foot-preference is NOT a reliable check.** Right- and left-footed
  shooters' mean `y` differ by about one part in a hundred — far too little
  to determine which touchline is which. If the data cannot settle it, say
  so and have a human look at one winger's shot map.

## Scene convention

Pick one and export it from the pitch module. A workable default:

```ts
export const PITCH_L = 105;   // along the pitch, scene z
export const PITCH_W = 68;    // across the pitch, scene x

// Opta y (0 = RIGHT touchline) -> scene x, so the left wing appears on the
// left of the picture when the camera is behind the attacking goal
export const toX = (optaY: number) => ((100 - optaY) / 100) * PITCH_W - PITCH_W / 2;

// Opta x (0 = own goal line) -> scene z, attacking toward +z
export const toZ = (optaX: number) => (optaX / 100) * PITCH_L - PITCH_L / 2;
```

`y` is up in Three.js, so the pitch plane is x–z and the vertical axis is
free for whatever the visualisation encodes.

**Never let provider arithmetic appear anywhere else.** Two copies of a
conversion drift, and the drift shows up as one chart mirrored relative to
another — which is far harder to spot than both being wrong.

## The 180° rotation, and the bug it causes

Data stored "in each team's own frame, attacking upwards" means the *same
patch of grass* is cell `j` for one side and cell `n-1-j` for the other. For
a 15-cell grid ordered `[DRW, DRH, DC, DLH, DLW, MRW … ALW]`:

```
index 0  = DRW (own defensive right wing)
index 14 = ALW (attacking left wing)
mirror(j) = 14 - j
```

`DRW ↔ ALW` and `DLW ↔ ARW`: the third flips **and** the flank flips. That
is a 180° rotation of the pitch, which is correct — the two teams face
opposite ways.

The bug is applying only half of it. Flip the third but not the flank and a
side that concedes down its left is drawn leaking down its right. Everything
still looks like plausible football.

```ts
// away-side values, turned into the home side's frame
const cells = meta.grid.cells;
const byCell = new Map(awayRows.map((r) => [r.cell, r.value]));
const inHomeFrame = cells.map((cell, j) => ({
  cell,
  value: byCell.get(cells[cells.length - 1 - j]) ?? 0,
}));
```

## Goal-mouth coordinates

Opta records where a shot crossed the goal line on every attempt, in its own
frame. Read the limits off the data rather than assuming:

- goals never leave `y ∈ [45.4, 54.6]` or `z ∈ [0.6, 36.1]`
- shots off the post reach `y ≈ 44.5` and `z ≈ 41.8`
- misses spill to `y ∈ [30, 71]` and `z = 100`

which places the posts at `y = 45.2 / 54.8` and the bar at `z = 38`:

```ts
const acrossM = ((goalMouthY - 50) / (54.8 - 45.2)) * 7.32;
const heightM = (goalMouthZ / 38) * 2.44;
```

**Validate goals, not misses.** A miss outside the frame is real football; a
*goal* outside the frame is a bad join or a bad conversion. Reject those
rather than drawing a ball through the side netting.

## Joining two providers

One feed has xG, the other has goal-mouth placement, and neither has both.
Joining is worth it, but do it carefully:

- Match on **(fixture date, minute, surname)** rather than the full name.
  Feeds disagree on about one name in eight — *Andy* vs *Andrew Robertson*,
  *Amad Diallo* vs *Amad Diallo Traore* — while surnames agree.
- Allow the minute to differ by ±1.
- Expect ~95% coverage. Clubs with several one-name players (Brazilian
  squads especially) join noticeably worse; report the rate per team rather
  than quoting a single league figure that hides it.
- **Sanity-check the joined result physically**, as above. A player who
  shoots, is blocked and scores the rebound inside the same minute can pick
  up the wrong one of his own attempts.
