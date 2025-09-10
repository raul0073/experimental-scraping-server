from pathlib import Path
import json
import numpy as np
import pandas as pd
from models.ranking.ranking import LOWER_IS_BETTER, ROLE_BASE_MAP, ROLE_RANK_MAPPING

class FBRefPlayerRankingService:
    def __init__(self, league_slug: str):
        self.league_slug = league_slug
        self.player_dir = Path("data/players") / league_slug

    def load_players(self) -> list[dict]:
        all_players = []

        if not self.player_dir.exists():
            raise FileNotFoundError(f"No such league dir: {self.player_dir}")

        for file in self.player_dir.glob("*.json"):
            team_data = json.loads(file.read_text(encoding="utf-8"))
            team_name = team_data.get("team")
            league_name = team_data.get("league")
            season = team_data.get("season")

            for player in team_data.get("players", []):
                player["__meta__"] = {
                    "team": team_name,
                    "league": league_name,
                    "season": season,
                    "file_path": str(file),
                }

                # Ensure role exists, but do NOT modify if present
                if "role" not in player or not player["role"]:
                    player["role"] = player.get("position", "NA")

                all_players.append(player)

        return all_players

    def rank_players(self):
        players = self.load_players()
        if not players:
            return

        # Flatten to a wide DataFrame
        flat_rows = []
        for player in players:
            row = {
                "name": player.get("name"),
                "position": player.get("position"),
                "role": player.get("role"),          # ORIGINAL role preserved
                "__player__": player,
            }
            for group, stats in (player.get("stats") or {}).items():
                for k, v in (stats or {}).items():
                    row[f"{group}:{k}"] = v
            flat_rows.append(row)

        df = pd.DataFrame(flat_rows)

        # Create base_role only for ranking
        df["base_role"] = df["role"].map(lambda r: ROLE_BASE_MAP.get(r, r))

        for role, weights in ROLE_RANK_MAPPING.items():
            role_df = df[df["base_role"] == role].copy()
            if role_df.empty:
                continue

            breakdowns = {}
            weighted_parts = []

            for key, weight in weights.items():
                if key not in role_df.columns:
                    continue

                col = pd.to_numeric(role_df[key], errors="coerce")
                std = col.std(ddof=0)
                z = (col - col.mean()) / (std if std and np.isfinite(std) else 1.0)

                metric_tail = key.split(":", 1)[1] if ":" in key else key
                if metric_tail in LOWER_IS_BETTER:
                    z = -z

                contribution = z * float(weight)
                weighted_parts.append(contribution)

                for idx, val in zip(role_df.index, contribution):
                    breakdowns.setdefault(idx, {})[key] = float(np.round(val, 5))

            if not weighted_parts:
                continue

            role_df["score"] = np.nansum(np.vstack(weighted_parts), axis=0)

            for idx, row in role_df.iterrows():
                player = row["__player__"]
                player.setdefault("ranking", {})["performance"] = float(np.round(row["score"], 3))
                player["ranking"]["breakdown"] = breakdowns.get(idx, {})

                # ✅ Original role remains untouched
                assert player["role"] == row["role"], f"Role was changed for {player['name']}!"

        self._save_ranked_players(players)

    def _save_ranked_players(self, players: list[dict]):
        files_map: dict[str, list[dict]] = {}

        for p in players:
            path = p["__meta__"]["file_path"]
            files_map.setdefault(path, []).append(p)

        for file_path, plist in files_map.items():
            meta = plist[0]["__meta__"]

            for p in plist:
                p.pop("__meta__", None)

            payload = {
                "league": meta["league"],
                "season": meta["season"],
                "team": meta["team"],
                "players": plist,
            }

            Path(file_path).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
