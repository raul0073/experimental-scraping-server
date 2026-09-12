from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from soccerdata import FBref

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name, _sanitize_value

log = logging.getLogger(__name__)

DATA_DIR = Path("data/fixtures")

# fbref renders scores as "2–1" (en dash); tolerate hyphen too
_SCORE_SEPARATORS = ("–", "-")

# fbref occasionally renames teams between seasons (2026-09: "PSG" became
# "Paris SG"), which would sever a club's cross-season history. Canonical name
# = the one our historical data uses.
FBREF_TEAM_ALIASES = {
    "Paris SG": "PSG",
}


class FixturesService:
    """Scrapes schedules + results per league/season and stores them as
    per-match JSON rows in data/fixtures/{league}/{season}.json.

    This is the ground-truth layer: every downstream model calibrates
    against these rows, and upcoming (unplayed) fixtures are what we
    predict on.
    """

    def __init__(self, league: str, season: str, refresh: bool = False):
        self.league = league
        self.season = season
        # no_cache forces a re-scrape — needed mid-season so new results land
        self.fbref = FBref(leagues=[league], seasons=[season], no_cache=refresh)

    def build(self) -> Dict[str, Any]:
        df = self.fbref.read_schedule()
        if df is None or df.empty:
            raise RuntimeError(f"No schedule returned for {self.league} {self.season}")

        df = df.reset_index()
        matches = [self._normalize_row(row) for _, row in df.iterrows()]
        matches = [m for m in matches if m is not None]
        matches.sort(key=lambda m: (m["date"] or "9999", m["home_team"]))

        payload = {
            "league": self.league,
            "season": self.season,
            "match_count": len(matches),
            "played_count": sum(1 for m in matches if m["played"]),
            "matches": matches,
        }
        out = self.out_path(self.league, self.season)
        _atomic_write_json(out, payload)
        log.info(
            "Saved %d matches (%d played) -> %s",
            payload["match_count"], payload["played_count"], out,
        )
        return {
            "ok": True,
            "league": self.league,
            "season": self.season,
            "match_count": payload["match_count"],
            "played_count": payload["played_count"],
        }

    def _normalize_row(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        home = _clean_str(row.get("home_team"))
        away = _clean_str(row.get("away_team"))
        if not home or not away:
            return None
        home = FBREF_TEAM_ALIASES.get(home, home)
        away = FBREF_TEAM_ALIASES.get(away, away)

        home_goals, away_goals = _parse_score(row.get("score"))
        date = _clean_str(row.get("date"))
        if date:
            date = date[:10]  # keep yyyy-mm-dd; source appends a meaningless 00:00:00
        return {
            "date": date,  # ISO yyyy-mm-dd
            "time": _clean_str(row.get("time")),
            "week": _sanitize_value(row.get("week")),
            "home_team": home,
            "away_team": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "played": home_goals is not None,
            "venue": _clean_str(row.get("venue")),
            "referee": _clean_str(row.get("referee")),
            "game_id": _clean_str(row.get("game")),
        }

    # ---------- disk access ----------

    @staticmethod
    def out_path(league: str, season: str) -> Path:
        return DATA_DIR / _safe_name(league) / f"{season}.json"

    @staticmethod
    def load(league: str, season: str) -> Optional[Dict[str, Any]]:
        import json

        path = FixturesService.out_path(league, season)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def available(league: str) -> List[str]:
        base = DATA_DIR / _safe_name(league)
        if not base.exists():
            return []
        return sorted(p.stem for p in base.glob("*.json"))


def _clean_str(v: Any) -> Optional[str]:
    v = _sanitize_value(v)
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_score(v: Any) -> tuple[Optional[int], Optional[int]]:
    s = _clean_str(v)
    if not s:
        return None, None
    for sep in _SCORE_SEPARATORS:
        if sep in s:
            left, _, right = s.partition(sep)
            try:
                return int(left.strip()), int(right.strip())
            except ValueError:
                return None, None
    return None, None
