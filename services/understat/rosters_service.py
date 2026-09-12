from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from soccerdata import Understat

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name
from services.understat.shot_events_service import ShotEventsService

log = logging.getLogger(__name__)

DATA_DIR = Path("data/understat")


class RostersService:
    """Per-match lineup slots (formation position + minutes) per player.

    Extracted from the SAME cached Understat match JSONs the shot-events
    builder fetches (soccerdata caches match_{id}.json), so building rosters
    for already-stored matches costs zero network calls. The stored shots
    file supplies the game ids and the canonical (name-mapped) team names.

    This powers the "typical shape" map: slots are formation ROLES from
    lineups, not measured average positions — no free source publishes
    tracking-based positions post-Opta.
    """

    def __init__(self, league: str, season: str):
        self.league = league
        self.season = season
        self.us = Understat(leagues=[league], seasons=[season])

    def build(self, sleep_s: float = 0.3) -> Dict[str, Any]:
        shots = ShotEventsService.load(self.league, self.season)
        if not shots or not shots.get("matches"):
            raise RuntimeError(f"No shot events on disk for {self.league} {self.season} "
                               "(rosters build follows the shots build)")
        out_path = self.out_path(self.league, self.season)
        existing = self.load(self.league, self.season) or {}
        if existing.get("v") != 2:  # schema bump -> re-extract from cache
            existing = {"league": self.league, "season": self.season,
                        "v": 2, "matches": {}}
        matches: Dict[str, Any] = existing["matches"]

        todo = [gid for gid in shots["matches"] if gid not in matches]
        fetched = errors = 0
        for i, gid in enumerate(todo):
            try:
                data = self.us._read_match("", int(gid))
            except Exception as e:
                log.warning("rosters %s failed: %s", gid, e)
                errors += 1
                continue
            if not data or "rostersData" not in data:
                errors += 1
                continue
            src = shots["matches"][gid]
            rows: Dict[str, list] = {"h": [], "a": []}
            for side in ("h", "a"):
                for p in (data["rostersData"].get(side) or {}).values():
                    rows[side].append({
                        "player": p.get("player"),
                        "position": p.get("position"),
                        "order": _to_int(p.get("positionOrder")),
                        "minutes": _to_int(p.get("time")) or 0,
                        # per-match performance (v2) — feeds the dependability
                        # ("mental") rankings: consistency needs match-level data
                        "goals": _to_int(p.get("goals")) or 0,
                        "own_goals": _to_int(p.get("own_goals")) or 0,
                        "shots": _to_int(p.get("shots")) or 0,
                        "xg": _to_float(p.get("xG")),
                        "xa": _to_float(p.get("xA")),
                        "assists": _to_int(p.get("assists")) or 0,
                        "key_passes": _to_int(p.get("key_passes")) or 0,
                        "xg_chain": _to_float(p.get("xGChain")),
                        "xg_buildup": _to_float(p.get("xGBuildup")),
                        "yellow": _to_int(p.get("yellow_card")) or 0,
                        "red": _to_int(p.get("red_card")) or 0,
                    })
            matches[gid] = {
                "date": src["date"],
                "home_team": src["home_team"],
                "away_team": src["away_team"],
                "rosters": rows,
            }
            fetched += 1
            if sleep_s and i < len(todo) - 1:
                time.sleep(sleep_s)

        existing["match_count"] = len(matches)
        _atomic_write_json(out_path, existing)
        return {"ok": True, "league": self.league, "season": self.season,
                "stored_total": len(matches), "fetched_now": fetched, "errors": errors}

    # ---------- disk access ----------

    @staticmethod
    def out_path(league: str, season: str) -> Path:
        return DATA_DIR / _safe_name(league) / "rosters" / f"{season}.json"

    @staticmethod
    def load(league: str, season: str) -> Optional[Dict[str, Any]]:
        path = RostersService.out_path(league, season)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v: Any) -> Optional[float]:
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None
