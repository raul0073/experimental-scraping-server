"""Which leagues do we actually have enough data for?

ONE RULE, DERIVED FROM DISK, USED EVERYWHERE. The daily update and the
"Update all to today" button must cover the same leagues, and that set
changes as the backfill lands. Hardcoding it means someone has to remember
to change it in two places on the day La Liga becomes usable — and the day
it is forgotten, the site either publishes a table of 50s for a league with
no history, or silently stops updating one that has it.

WHAT "ENOUGH" MEANS. The ratings table is built from the event stream, and
its reliability gate is a split-half correlation ACROSS team-seasons. One
season gives n=20 and only 4 of 23 metrics survive; the complete seasons
give n~60 and 20 of 23. So a league counts as ready once its COMPLETE
seasons are on disk AND STAMPED — stamped, because nothing downstream reads
the raw parquet.

The current season does not count towards readiness: it is partial by
definition, and being partial is exactly what produced the wall of 50s.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"

ALL_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "ITA-Serie A",
    "GER-Bundesliga",
    "FRA-Ligue 1",
]

# The finished seasons the backfill delivers. A league needs all of these
# before its ratings mean anything.
REQUIRED_SEASONS = ("2425", "2526")


# A finished season is 380 matches in a twenty-club league and 306 in an
# eighteen-club one. This is the floor for calling one COMPLETE.
#
# 🐛 EXISTENCE WAS NOT ENOUGH. The first version asked only whether a
# stamped file was there, so a season the backfill had abandoned part-way
# counted as done: Serie A passed readiness on 100 of 380 matches for 24/25
# and Ligue 1 on 220 of 306 for 25/26. That is about five matches a club —
# exactly the thinness that made La Liga's ratings table a wall of 50s, and
# it would have been published as a real rating rather than an empty one.
#
# 280 sits below the smallest full season (306) by enough to tolerate a
# handful of genuinely unavailable matches, and far above a partial fetch.
MIN_SEASON_MATCHES = 280


def _match_count(path: Path) -> int:
    try:
        import pandas as pd
        return int(pd.read_parquet(path, columns=["game_id"])["game_id"].nunique())
    except Exception:
        return 0


def stamped_seasons(league: str) -> set:
    """Seasons whose STAMPED parquet exists AND looks complete.

    Stamped, because nothing downstream opens the raw parquet. Complete,
    because a half-fetched season is worse than an absent one — absent is
    visibly missing, half-fetched publishes a confident rating built on five
    matches a club."""
    try:
        return {p.stem.replace("_stamped", "")
                for p in (RAW / league).glob("*_stamped.parquet")
                if _match_count(p) >= MIN_SEASON_MATCHES}
    except Exception:
        return set()


def is_ready(league: str) -> bool:
    return set(REQUIRED_SEASONS).issubset(stamped_seasons(league))


def ready_leagues() -> list:
    """Leagues the daily is allowed to build. Never empty in practice —
    but if it were, callers should do nothing rather than guess."""
    return [lg for lg in ALL_LEAGUES if is_ready(lg)]


def readiness() -> dict:
    """Per-league detail, for showing WHY a league is or is not included."""
    out = {}
    for lg in ALL_LEAGUES:
        have = stamped_seasons(lg)
        missing = [s for s in REQUIRED_SEASONS if s not in have]
        out[lg] = {
            "ready": not missing,
            "stamped": sorted(have),
            "missing": missing,
        }
    return out
