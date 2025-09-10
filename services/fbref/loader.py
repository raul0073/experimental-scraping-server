import os
from pathlib import Path
import json
from typing import List, Dict

from models.fbref.fbref_types import LEAGUE_NAME_MAP


class FBRefLoaderService:
    @staticmethod
    def load_team_players(league: str, season: int, team: str) -> list[dict]:
        file_path = Path(f"data/players/{league}/{team}.json")
        if not file_path.exists():
            return []

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [p for p in data.get("players", []) if isinstance(p, dict)]
    
    @staticmethod
    def filter_stats_by_team(all_team_stats: dict, team: str):
            # Filter only your team and reformat by stat type
        team_stats = {}
        for stat_type, stats_list in all_team_stats.items():  # e.g., 'defense', 'passing', ...
            # find the dict for your team
            team_entry = next((s for s in stats_list if s.get("team", "").lower() == team.lower()), None)
            if team_entry:
                team_stats[stat_type] = team_entry.get("metrics", {})
        return team_stats
    
    @staticmethod
    def filter_stat_type_by_team(all_team_stats: dict, team: str):
        """
        Filter a single stat_type list to extract only the dict for the given team.
        Returns metrics dict only.
        """
        if not isinstance(all_team_stats, list):
            print("⚠️ Expected a list of team stats for a single stat_type")
            return {}

        team_entry = next((s for s in all_team_stats if s.get("team", "").lower() == team.lower()), None)
        if team_entry:
            return team_entry.get("metrics", {})
        return {}
    
    @staticmethod
    def load_team_team(league: str, season: int, team: str) -> list[dict]:
        file_path = Path(f"data/players/{league}/{team}.json")
        if not file_path.exists():
            return []

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [p for p in data.get("players", []) if isinstance(p, dict)]
    
    @staticmethod
    def load_all_players(league: str, season: int) -> list[dict]:
        player_dir = Path(f"data/players/{league}")
        all_players = []

        if not player_dir.exists():
            raise FileNotFoundError(f"ERROR: No such directory: {player_dir}")

        for file in player_dir.glob("*.json"):  # <-- only .json
            if not file.is_file():
                continue
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"⚠️ Skipping invalid JSON file: {file} ({e})")
                continue

            team = data.get("team")
            league_name = data.get("league")
            actual_season = data.get("season")

            for p in data.get("players", []):
                p["__meta__"] = {
                    "team": team,
                    "league": league_name,
                    "season": actual_season,
                }
                all_players.append(p)

        print(f"✅ Loaded {len(all_players)} players for {league} (ignoring passed-in season)")
        return all_players

    @staticmethod
    def list_available_league_team_paths():
        base = Path("data/players")
        result = []

        for league_dir in base.glob("*"):
            if not league_dir.is_dir():
                continue

            for team_file in league_dir.glob("*.json"):
                result.append({
                    "league": league_dir.name,
                    "team": team_file.stem,
                    "path": str(team_file)
                })

        return result
    
    @staticmethod
    def load_teams_stats(league: str, season: int) -> dict:
        """
        Loads all team_*.json files for a given league/season
        and returns them in a dict keyed by stat_type.
        """
        base_path = f"data/league_init/{league}-{season}"
        if not os.path.isdir(base_path):
            return {}

        team_stats = {}
        for filename in os.listdir(base_path):
            if filename.startswith("team_") and filename.endswith(".json"):
                stat_type = filename.replace("team_", "").replace(".json", "")
                file_path = os.path.join(base_path, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        team_stats[stat_type] = json.load(f)
                except Exception as e:
                    print(f"⚠️ Failed to load {file_path}: {e}")
                    team_stats[stat_type] = {}

        return team_stats
    
    @staticmethod
    def load_league_stats(league: str, season: int) -> Dict[str, dict]:
        """
        Aggregates all team_*.json stats into league totals.
        Returns a dict of {stat_type: {stat_key: total_value}}
        """
        base_path = f"data/league_init/{league}-{season}"
        if not os.path.isdir(base_path):
            return {}

        league_stats: Dict[str, dict] = {}

        for filename in os.listdir(base_path):
            if filename.startswith("team_") and filename.endswith(".json"):
                stat_type = filename.replace("team_", "").replace(".json", "")
                file_path = os.path.join(base_path, filename)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        team_data = json.load(f)
                except Exception as e:
                    print(f"⚠️ Failed to load {file_path}: {e}")
                    continue

                if not isinstance(team_data, list):
                    continue

                totals: Dict[str, float] = {}
                for team_row in team_data:
                    for key, value in team_row.items():
                        if key == "team":
                            continue
                        try:
                            val = float(value)
                        except (ValueError, TypeError):
                            continue
                        totals[key] = totals.get(key, 0) + val

                league_stats[stat_type] = totals

        return league_stats

    @staticmethod
    def load_all_leagues_stats(season: int) -> Dict[str, Dict[str, dict]]:
        """
        Loops over all leagues in data/league_init/*-{season} and returns a dict:
        {
            "English Premier League": { "defense": {...}, "shooting": {...} },
            "Italian Serie A": { "defense": {...}, "shooting": {...} }
        }
        """
        base = Path("data/league_init")
        result: Dict[str, Dict[str, dict]] = {}

        for league_dir in base.glob(f"*-{season}"):
            if not league_dir.is_dir():
                continue

            # Example folder: "ENG-Premier League-2425"
            folder_name = league_dir.name
            league_key = "-".join(folder_name.split("-")[:-1])  
            league_name = LEAGUE_NAME_MAP.get(league_key, league_key)

            stats = FBRefLoaderService.load_league_stats(league_name, season)
            result[league_name] = stats

        return result
