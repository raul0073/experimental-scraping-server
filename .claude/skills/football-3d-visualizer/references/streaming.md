# Streaming match telemetry

Tracking data arrives at 10–25Hz. The browser renders at 60–144Hz. Those two
clocks never line up, and the whole problem is bridging them without the
motion looking wrong.

## Never render packets as they land

The instinct is to set state on every message and let React draw it. That
produces visible stutter: network timing jitters by tens of milliseconds,
frames do not, and the eye reads the mismatch as players twitching.

**Buffer and interpolate.** Hold at least two frames, keep a playback clock
that runs slightly behind real time, and in the render loop interpolate
between the two frames that straddle the clock.

```ts
// one or two packet intervals of latency, traded for smooth motion
const DELAY_MS = 120;

useFrame(() => {
  const t = performance.now() - DELAY_MS;
  const [a, b] = buffer.straddling(t);
  if (!a || !b) return;
  const k = (t - a.t) / (b.t - a.t || 1);
  for (let i = 0; i < count; i++) {
    dummy.position.set(
      a.x[i] + (b.x[i] - a.x[i]) * k,
      0,
      a.z[i] + (b.z[i] - a.z[i]) * k,
    );
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;
});
```

Writing matrices directly and flagging `needsUpdate` keeps this out of React
entirely — a `setState` per frame re-renders the tree to move a sprite.

## The server clock is the truth

Drive playback from a clock you control, not from packet arrival. That clock
can be paused, scrubbed, slowed to half speed and run backwards — all of
which a tactical tool needs and none of which works if position is whatever
arrived last.

For replay, the same interpolation path works unchanged: the buffer is fed
from a file instead of a socket.

## Wire format

Send flat typed arrays, not an object per player. A frame is:

```
frame_index : uint32
timestamp   : float64   (server clock, ms)
positions   : float32[] (x, z interleaved, players then ball)
```

A 23-object frame is ~190 bytes packed against ~2KB as JSON. At 25Hz across
a match that is the difference between 30MB and 300MB.

`scripts/pitch_frame.py` is a reference FastAPI sender.

## Backpressure and reconnection

- If the client falls behind, **drop frames rather than queue them** — old
  positions have no value, and a growing queue turns latency into minutes.
- On reconnect, request the current frame index rather than replaying from
  the start.
- Send a small keyframe on connect: pitch dimensions, team colours, shirt
  numbers, the coordinate frame in use. Never hard-code those on the client;
  a competition that plays on a 100×64 pitch will otherwise silently
  misplace everyone.

## Coordinate conversion belongs on the client

Send metres in the provider's own frame and convert once in the browser,
using the same `toX` / `toZ` the rest of the scene uses. Converting on the
server means two implementations of the same arithmetic, and the drift shows
up as tracking that disagrees with the event overlay drawn on top of it.

## What to check when motion looks wrong

| symptom | usual cause |
|---|---|
| players twitch or stutter | rendering packets directly; no interpolation |
| motion smooth but laggy | delay buffer too large — reduce toward one packet interval |
| players slide through each other on a jump | interpolating across a discontinuity; detect large deltas and snap |
| everyone drifts one way over time | client clock used instead of server timestamps |
| ball lags the players | ball sampled at a different rate; interpolate it on its own timeline |
