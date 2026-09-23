"""Reference FastAPI sender for match telemetry.

Packs a tracking frame as a compact binary message rather than JSON: a
23-object frame is about 190 bytes here against roughly 2KB as objects,
which over a full match at 25Hz is the difference between 30MB and 300MB.

The client buffers these and interpolates between them in its render loop —
see references/streaming.md. Positions are sent in the PROVIDER'S OWN metric
frame and converted once in the browser, so there is only ever one
implementation of the coordinate conversion.

    uvicorn pitch_frame:app --reload
"""
from __future__ import annotations

import asyncio
import struct
import time
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

# A keyframe every client needs before any position means anything. Never
# hard-code these in the browser: a competition on a 100x64 pitch would
# otherwise silently misplace everyone by a couple of metres.
PITCH = {"length": 105.0, "width": 68.0, "frame": "centre-origin-metres"}
HZ = 25


@dataclass
class Frame:
    """One instant: every tracked object's position on the pitch.

    `xs` and `zs` are parallel arrays — players first in a stable order,
    then the ball. Keeping them flat is what makes the packed form cheap
    and lets the client write straight into an InstancedMesh.
    """
    index: int
    t: float                      # server clock, milliseconds
    xs: list[float] = field(default_factory=list)
    zs: list[float] = field(default_factory=list)

    def pack(self) -> bytes:
        """<uint32 index><float64 t><uint16 n><float32 x,z interleaved>"""
        n = len(self.xs)
        head = struct.pack("<IdH", self.index, self.t, n)
        body = struct.pack(f"<{n * 2}f",
                           *[v for pair in zip(self.xs, self.zs) for v in pair])
        return head + body


async def frames(source) -> "asyncio.AsyncIterator[Frame]":
    """Yield frames at a steady rate from whatever `source` provides.

    Paced against a monotonic clock rather than `sleep(1/HZ)` in a loop: the
    latter accumulates the cost of the work done each tick, so a match drifts
    seconds behind over ninety minutes.
    """
    start = time.perf_counter()
    for i, positions in enumerate(source):
        target = start + i / HZ
        now = time.perf_counter()
        if target > now:
            await asyncio.sleep(target - now)
        yield Frame(index=i, t=time.time() * 1000,
                    xs=[p[0] for p in positions], zs=[p[1] for p in positions])


@app.websocket("/ws/match/{match_id}")
async def stream(ws: WebSocket, match_id: str) -> None:
    await ws.accept()
    # the keyframe first, so the client can size the pitch and colour the
    # teams before a single position arrives
    await ws.send_json({"type": "keyframe", "match": match_id, "pitch": PITCH,
                        "hz": HZ, "objects": ["players", "ball"]})
    try:
        async for frame in frames(load(match_id)):
            # DROP, NEVER QUEUE. A client that has fallen behind wants the
            # current position, not every position it has missed — a growing
            # queue turns a moment of lag into minutes of it.
            try:
                await asyncio.wait_for(ws.send_bytes(frame.pack()),
                                       timeout=1 / HZ)
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        return


def load(match_id: str):
    """Replace with a real source — a parquet of tracking frames, a live
    provider socket, or a simulation. Yields one list of (x, z) per frame."""
    raise NotImplementedError
