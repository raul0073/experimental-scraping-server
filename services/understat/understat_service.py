from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from soccerdata import Understat

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name, _sanitize_value

log = logging.getLogger(__name__)

DATA_DIR = Path("data/understat")
NAME_MAP_PATH = Path("data/config/team_name_map.json")


class UnderstatService:
    """Per-match real xG layer (Understat), stored with fbref-normalized team
    names so everything downstream joins on one naming scheme.

    Understat is the only remaining free source of per-match xG after fbref
    lost its advanced data — it also provides npxG, PPDA (pressing) and deep
    completions per team per match.
    """

    def __init__(self, league: str, season: str, refresh: bool = False):
        self.league = league
        self.season = season
        # refresh bypasses the cached league page — required mid-season, or a
        # stale preseason page serves zero matches forever
        self.us = Understat(leagues=[league], seasons=[season], no_cache=refresh)

    def build(self) -> Dict[str, Any]:
        df = self.us.read_team_match_stats().reset_index()
        if df is None or df.empty:
            raise RuntimeError(f"No Understat data for {self.league} {self.season}")

        name_map = load_name_map().get(self.league, {})

        # Understat keeps originally-scheduled dates for postponed matches;
        # fbref's fixture date is authoritative. A (home, away) pair occurs
        # exactly once per season, so the pair is a safe join key.
        from services.fbref.fixtures.fixtures_service import FixturesService
        fx = FixturesService.load(self.league, self.season)
        fbref_date_by_pair = (
            {(m["home_team"], m["away_team"]): m["date"] for m in fx["matches"]} if fx else {}
        )

        matches: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            home_raw = str(row["home_team"]).strip()
            away_raw = str(row["away_team"]).strip()
            home = name_map.get(home_raw, home_raw)
            away = name_map.get(away_raw, away_raw)
            matches.append({
                "date": fbref_date_by_pair.get((home, away), str(row["date"])[:10]),
                "understat_date": str(row["date"])[:10],
                "home_team": home,
                "away_team": away,
                "home_goals": _sanitize_value(row.get("home_goals")),
                "away_goals": _sanitize_value(row.get("away_goals")),
                "home_xg": _sanitize_value(row.get("home_xg")),
                "away_xg": _sanitize_value(row.get("away_xg")),
                "home_npxg": _sanitize_value(row.get("home_np_xg")),
                "away_npxg": _sanitize_value(row.get("away_np_xg")),
                "home_ppda": _sanitize_value(row.get("home_ppda")),
                "away_ppda": _sanitize_value(row.get("away_ppda")),
                "home_deep": _sanitize_value(row.get("home_deep_completions")),
                "away_deep": _sanitize_value(row.get("away_deep_completions")),
                "home_xpts": _sanitize_value(row.get("home_expected_points")),
                "away_xpts": _sanitize_value(row.get("away_expected_points")),
                "understat_game_id": _sanitize_value(row.get("game_id")),
            })

        matches.sort(key=lambda m: (m["date"] or "9999", m["home_team"]))
        payload = {
            "league": self.league,
            "season": self.season,
            "match_count": len(matches),
            "matches": matches,
        }
        out = self.out_path(self.league, self.season)
        _atomic_write_json(out, payload)
        log.info("Saved %d Understat matches -> %s", len(matches), out)
        return {"ok": True, "league": self.league, "season": self.season, "match_count": len(matches)}

    def build_players(self) -> Dict[str, Any]:
        """Player season stats (xG, npxG, xA, shots, key passes, xGChain,
        xGBuildup) — the Understat side of the future zones player layer.
        Stored separately from the legacy fbref player files."""
        df = self.us.read_player_season_stats().reset_index()
        if df is None or df.empty:
            raise RuntimeError(f"No Understat player data for {self.league} {self.season}")

        name_map = load_name_map().get(self.league, {})
        players = []
        for _, row in df.iterrows():
            team_raw = str(row.get("team", "")).strip()
            players.append({
                "player": _sanitize_value(row.get("player")),
                "team": name_map.get(team_raw, team_raw),
                "position": _sanitize_value(row.get("position")),
                "matches": _sanitize_value(row.get("matches")),
                "minutes": _sanitize_value(row.get("minutes")),
                "goals": _sanitize_value(row.get("goals")),
                "xg": _sanitize_value(row.get("xg")),
                "npxg": _sanitize_value(row.get("np_xg")),
                "assists": _sanitize_value(row.get("assists")),
                "xa": _sanitize_value(row.get("xa")),
                "shots": _sanitize_value(row.get("shots")),
                "key_passes": _sanitize_value(row.get("key_passes")),
                "xg_chain": _sanitize_value(row.get("xg_chain")),
                "xg_buildup": _sanitize_value(row.get("xg_buildup")),
            })

        payload = {
            "league": self.league,
            "season": self.season,
            "player_count": len(players),
            "players": players,
        }
        out = DATA_DIR / _safe_name(self.league) / "players" / f"{self.season}.json"
        _atomic_write_json(out, payload)
        log.info("Saved %d Understat players -> %s", len(players), out)
        return {"ok": True, "league": self.league, "season": self.season, "player_count": len(players)}

    # ---------- name mapping ----------

    def learn_name_map(self) -> Dict[str, str]:
        """Learn Understat->fbref team name pairs by matching played games on
        (date, home_goals, away_goals) against the fbref fixtures files.
        Unambiguous matches teach us name pairs; the result is merged into
        data/config/team_name_map.json (committed, hand-editable).
        """
        from services.fbref.fixtures.fixtures_service import FixturesService

        fx = FixturesService.load(self.league, self.season)
        if fx is None:
            raise RuntimeError(f"fbref fixtures missing for {self.league} {self.season} — build those first")

        fbref_by_key: Dict[Tuple, List[Dict]] = {}
        for m in fx["matches"]:
            if not m["played"]:
                continue
            fbref_by_key.setdefault((m["date"], m["home_goals"], m["away_goals"]), []).append(m)

        us_df = self.us.read_team_match_stats().reset_index()
        # Understat dates are stale for rescheduled matches, so a (date, score)
        # key can collide with a *different* fbref match and teach garbage.
        # Vote per candidate pair and require >=3 independent confirmations —
        # a real team yields ~38 learning opportunities, a collision 1-2.
        from collections import Counter
        votes: Counter = Counter()
        for _, row in us_df.iterrows():
            key = (str(row["date"])[:10], _sanitize_value(row.get("home_goals")), _sanitize_value(row.get("away_goals")))
            candidates = fbref_by_key.get(key, [])
            if len(candidates) != 1:
                continue
            fb = candidates[0]
            for us_name, fb_name in ((str(row["home_team"]).strip(), fb["home_team"]),
                                     (str(row["away_team"]).strip(), fb["away_team"])):
                if us_name != fb_name:
                    votes[(us_name, fb_name)] += 1

        learned: Dict[str, str] = {}
        for us_name in {u for (u, _f) in votes}:
            best, n = max(((f, n) for (u, f), n in votes.items() if u == us_name), key=lambda x: x[1])
            if n >= 3:
                learned[us_name] = best
            else:
                log.warning("Skipping low-confidence mapping %s -> %s (%d votes)", us_name, best, n)

        merge_name_map(self.league, learned)
        log.info("Learned %d name mappings for %s", len(learned), self.league)
        return learned

    # ---------- disk access ----------

    @staticmethod
    def out_path(league: str, season: str) -> Path:
        return DATA_DIR / _safe_name(league) / f"{season}.json"

    @staticmethod
    def load(league: str, season: str) -> Optional[Dict[str, Any]]:
        path = UnderstatService.out_path(league, season)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def load_name_map() -> Dict[str, Dict[str, str]]:
    if not NAME_MAP_PATH.exists():
        return {}
    return json.loads(NAME_MAP_PATH.read_text(encoding="utf-8"))


def merge_name_map(league: str, new_entries: Dict[str, str]) -> None:
    data = load_name_map()
    league_map = data.setdefault(league, {})
    league_map.update(new_entries)
    data[league] = dict(sorted(league_map.items()))
    _atomic_write_json(NAME_MAP_PATH, data)
