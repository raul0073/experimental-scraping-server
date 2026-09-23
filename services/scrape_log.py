"""One line per network fetch, appended where a human can watch it.

WHY. Every scrape so far has been a black box. A job starts, the terminal
goes quiet for ten minutes, and the only way to find out what it actually
fetched is to read file timestamps afterwards. Twice that silence hid a job
doing work nobody asked for — five leagues when one was wanted, a whole
season's schedule when four matches were missing — and there was no way to
tell the difference between "working" and "wrong" while it happened.

So: every fetch says what it is fetching, BEFORE it fetches it. Not a
progress bar, not a summary at the end — a line naming the league, the
season, and the count, written and flushed immediately.

This file is append-only and rotated by size. It is not the pipeline's
state; nothing reads it back. Losing it costs visibility, never data.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "reports" / "scrape.log"
MAX_BYTES = 2_000_000


def _rotate() -> None:
    try:
        if LOG.exists() and LOG.stat().st_size > MAX_BYTES:
            LOG.replace(LOG.with_suffix(".log.1"))
    except Exception:
        pass


def scrape(what: str, **fields) -> None:
    """Record one fetch. `what` is a short verb-ish label; fields are the
    specifics worth seeing — league, season, counts, the reason it is being
    asked for at all."""
    bits = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
    line = f"{datetime.now():%H:%M:%S}  {what}" + (f"  {bits}" if bits else "")
    try:
        _rotate()
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
    except Exception:
        pass            # visibility must never be able to break a pipeline
    print(f"[scrape] {line}", flush=True)


def banner(what: str) -> None:
    """A separator, so one run is distinguishable from the next."""
    try:
        _rotate()
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{'=' * 64}\n{datetime.now():%Y-%m-%d %H:%M:%S}  {what}\n")
            fh.flush()
    except Exception:
        pass
    print(f"[scrape] === {what}", flush=True)
