from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List
from soccerdata import FBref
from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name, _sanitize, _sanitize_value


class FBrefService:
    """
    Fetches FBref player stats for a league+season,
    saves one JSON per team into data/teams/<league>/<team>.json
    """

    def __init__(self, league: str, season: str):
        self.league = league
        self.season = season
        self.fbref = FBref(leagues=[league], seasons=[season])
        self.base_dir = Path("data/teams") / _safe_name(league)
        logging.info("FBrefService: %s / %s", league, season)

    def _team_list(self) -> List[str]:
        """Get list of teams in this league/season."""
        df = self.fbref.read_team_season_stats(stat_type="standard", opponent_stats=False)
        if df is None or df.empty:
            return []
        return sorted(df.reset_index()["squad"].dropna().unique().tolist())

    def fetch_team(self, team: str) -> Dict[str, Any]:
        """Fetch stats for a single team, return JSON object."""
        df = self.fbref.read_player_season_stats(stat_type="standard")
        if df is None or df.empty:
            return {"league": self.league, "season": self.season, "team": team, "players": []}

        df = df.reset_index()
        team_df = df[df["squad"].str.lower() == team.lower()]
        if team_df.empty:
            return {"league": self.league, "season": self.season, "team": team, "players": []}

        players: List[Dict[str, Any]] = []
        for _, row in team_df.iterrows():
            metrics = {k: _sanitize_value(v) for k, v in row.items() if k not in ("player", "squad", "nation", "pos")}
            players.append({
                "player": row["player"],
                "pos": row.get("pos"),
                "metrics": metrics,
            })

        return {
            "league": self.league,
            "season": self.season,
            "team": team,
            "players": players,
        }

    def save_team(self, team: str) -> Path:
        data = self.fetch_team(team)
        path = self.base_dir / f"{_safe_name(team)}.json"
        _atomic_write_json(path, _sanitize(data))
        return path

    def save_all_teams(self) -> Dict[str, Any]:
        teams = self._team_list()
        summary: Dict[str, Any] = {"league": self.league, "season": self.season, "teams": []}

        for t in teams:
            try:
                path = self.save_team(t)
                summary["teams"].append({"team": t, "file": str(path)})
            except Exception as e:
                logging.exception("failed to save %s", t)
                summary["teams"].append({"team": t, "error": str(e)})

        return summary