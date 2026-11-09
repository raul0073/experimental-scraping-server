"""The one number the ledgers and the window logic have to agree on.

WINDOW_GRACE_DAYS is how long after its last kickoff a booked round may
stay "live" with rows still pending. Past it, `_pending_window` stops
serving the round and the three graders void whatever never matched a
result, with a note on the row — abandoned fixture, renamed club, a match
the fixture file never carried. Without an expiry one such row held the
whole betting surface forever (10-07 to 10-23, 2026); the self-check case
"a pending row that can never resolve does not freeze the window forever"
is the regression test.

Seven days: longer than any round straddles, shorter than two rounds, so a
late Monday kickoff grades normally and a dead row is released before the
following weekend.
"""
from __future__ import annotations

from datetime import date, timedelta

WINDOW_GRACE_DAYS = 7


def stale_floor(today: date | None = None) -> str:
    """ISO date: a pending row with a kickoff before this is void-able."""
    return ((today or date.today()) - timedelta(days=WINDOW_GRACE_DAYS)).isoformat()


VOID_NOTE = (f"void: no result matched within {WINDOW_GRACE_DAYS} days of kickoff "
             f"(fixture abandoned, renamed or missing from the fixture file)")
