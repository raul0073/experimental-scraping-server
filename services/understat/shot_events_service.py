from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from soccerdata import Understat

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name, _sanitize_value
from services.understat.understat_service import load_name_map

log = logging.getLogger(__name__)

DATA_DIR = Path("data/understat")


class ShotEventsService:
    """Per-shot events (x, y, xG, situation, lastAction) for every match.

    We call soccerdata's raw match reader instead of read_shot_events because
    the library drops `lastAction` — the field that recovers the shot-linked
    versions of the stats fbref lost (through balls, take-ons, crosses,
    punished turnovers). Coordinates are Understat fractions (0-1, attacking
    left->right); zone mapping happens downstream in the zones engine.

    Understat caches one JSON per match on disk, so re-runs and weekly
    increments only fetch matches not seen before.
    """

    def __init__(self, league: str, season: str, refresh: bool = False):
        self.league = league
        self.season = season
        # cached instance for per-match JSONs (played matches never change);
        # the schedule listing must bypass cache mid-season or new matches
        # are invisible
        self.us = Understat(leagues=[league], seasons=[season])
        self._us_fresh = (Understat(leagues=[league], seasons=[season], no_cache=True)
                          if refresh else self.us)

    def build(self, sleep_s: float = 1.0, save_every: int = 50,
              limit: Optional[int] = None) -> Dict[str, Any]:
        name_map = load_name_map().get(self.league, {})
        out = self.out_path(self.league, self.season)
        existing = self.load(self.league, self.season) or {
            "league": self.league, "season": self.season, "matches": {},
        }
        matches: Dict[str, Any] = existing["matches"]

        schedule = self._us_fresh.read_schedule(include_matches_without_data=False).reset_index()
        todo = []
        for _, row in schedule.iterrows():
            gid = str(_sanitize_value(row["game_id"]))
            if bool(row.get("is_result")) and gid not in matches:
                todo.append((gid, row))
        if limit is not None:
            todo = todo[:limit]

        log.info("%s %s: %d matches already stored, %d to fetch",
                 self.league, self.season, len(matches), len(todo))

        fetched = errors = 0
        for i, (gid, row) in enumerate(todo):
            try:
                data = self.us._read_match(str(row.get("url", "")), int(gid))
            except Exception as e:
                log.warning("match %s failed: %s", gid, e)
                errors += 1
                continue
            if data is None:
                errors += 1
                continue

            home = name_map.get(str(row["home_team"]).strip(), str(row["home_team"]).strip())
            away = name_map.get(str(row["away_team"]).strip(), str(row["away_team"]).strip())
            shots: List[Dict[str, Any]] = []
            for team_shots in data["shotsData"].values():
                for s in team_shots:
                    shots.append({
                        "side": s.get("h_a"),
                        "minute": _to_int(s.get("minute")),
                        "player": _sanitize_value(s.get("player")),
                        "assist_player": _sanitize_value(s.get("player_assisted")),
                        "x": _to_float(s.get("X")),
                        "y": _to_float(s.get("Y")),
                        "xg": _to_float(s.get("xG")),
                        "situation": _sanitize_value(s.get("situation")),
                        "shot_type": _sanitize_value(s.get("shotType")),
                        "last_action": _sanitize_value(s.get("lastAction")),
                        "result": _sanitize_value(s.get("result")),
                    })
            matches[gid] = {
                "date": str(row["date"])[:10],
                "home_team": home,
                "away_team": away,
                "shots": shots,
            }
            fetched += 1
            if fetched % save_every == 0:
                self._save(out, existing)
                log.info("%s %s: %d/%d fetched (checkpoint)",
                         self.league, self.season, fetched, len(todo))
            if sleep_s and i < len(todo) - 1:
                time.sleep(sleep_s)

        self._save(out, existing)
        return {
            "ok": True, "league": self.league, "season": self.season,
            "stored_total": len(matches), "fetched_now": fetched, "errors": errors,
        }

    def _save(self, out: Path, payload: Dict[str, Any]) -> None:
        payload["match_count"] = len(payload["matches"])
        payload["shot_count"] = sum(len(m["shots"]) for m in payload["matches"].values())
        _atomic_write_json(out, payload)

    # ---------- disk access ----------

    @staticmethod
    def out_path(league: str, season: str) -> Path:
        return DATA_DIR / _safe_name(league) / "shots" / f"{season}.json"

    @staticmethod
    def load(league: str, season: str) -> Optional[Dict[str, Any]]:
        path = ShotEventsService.out_path(league, season)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
