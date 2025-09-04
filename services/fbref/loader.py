from pathlib import Path
import json
from typing import List

class FBRefLoaderService:
    @staticmethod
    def load_team_players(league: str, season: int, team: str) -> List[dict]:
        file_path = Path(f"data/players/{league}/{team}.json")
        if file_path.exists():
            return json.loads(file_path.read_text(encoding="utf-8"))
        return []

    @staticmethod
    def load_all_players(league: str, season: int) -> list[dict]:
        player_dir = Path("data/players") / league
        all_players = []

        if not player_dir.exists():
            raise FileNotFoundError(f"❌ No such directory: {player_dir}")

        for file in player_dir.glob("*.json"):
            data = json.loads(file.read_text(encoding="utf-8"))
            team = data.get("team")
            league = data.get("league")
            actual_season = data.get("season")

            for p in data.get("players", []):
                p["__meta__"] = {
                    "team": team,
                    "league": league,
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