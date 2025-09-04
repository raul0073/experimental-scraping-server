from pathlib import Path
import json
import re
from turtle import position
from typing import Optional
import numpy as np
import pandas as pd

from models.players.player_type import RoleType
from models.ranking.ranking import LOWER_IS_BETTER, ROLE_RANK_MAPPING
STANDARD_ROLES = {"GK", "CB", "FB", "DM", "CM", "AM", "W", "CF"}
class FBRefPlayerRankingService:
    def __init__(self, league_slug: str):
        # league_slug must match how you saved the JSONs under data/players/<slug>
        self.league_slug = league_slug
        self.player_dir = Path("data/players") / league_slug




    @staticmethod
    def infer_role(position_text: Optional[str], position: Optional[str]) -> str:
        import re

        text = (position_text or "").strip()
        pos = (position or "").strip().upper()
        print(f"[INFO] Inferring role for player: position_text='{text}' position='{pos}'")

        # Standard role map
        role_map = {
            "GK": "GK",
            "CB": "CB",
            "FB": "FB",
            "DM": "DM",
            "CM": "CM",
            "AM": "AM",
            "W": "W",
            "CF": "CF"
        }

        # Normalize text
        clean_text = text.replace("▪", "").replace(" ", "").upper()

        # Extract parentheses content for more precise info
        paren_match = re.search(r"\((.*?)\)", clean_text)
        inner_roles = []
        side = None
        if paren_match:
            inner = paren_match.group(1)
            # Detect side info
            side_match = re.search(r"(LEFT|RIGHT|L|R)", inner)
            if side_match:
                side = side_match.group(1)[0].upper()
            # Extract roles inside parentheses
            inner_roles = [r for r in re.split(r"[-,]", inner) if r and r.upper() not in ("L", "R", "LEFT", "RIGHT")]

        # If no parentheses roles, use main text
        if not inner_roles:
            main_roles = re.split(r"[-,]", clean_text)
            inner_roles = [r for r in main_roles if r and r not in ("L", "R", "LEFT", "RIGHT")]

        # Pick the first role we recognize
        for r in inner_roles:
            std_role = role_map.get(r)
            if std_role:
                # Apply side suffix for CB, FB, AM, W
                if side and std_role in ("CB", "FB", "AM", "W"):
                    if std_role == "CB":
                        return f"CB"
                    if std_role == "FB":
                        return f"FB"
                    if std_role in ("AM", "W"):
                        return f"W"
                return std_role

        # Fallback mapping based on broad position if parsing failed
        fallback_map = {
            "GK": "GK",
            "DF": "CB",
            "MF": "CM",
            "FW,MF": "AM",
            "MF,FW": "AM",
            "FW": "CF"
        }

        return fallback_map.get(pos, "CF")  # always return something, default striker



    


    def load_players(self) -> list[dict]:
        all_players = []

        if not self.player_dir.exists():
            raise FileNotFoundError(f"No such league dir: {self.player_dir}")

        for file in self.player_dir.glob("*.json"):
            team_data = json.loads(file.read_text(encoding="utf-8"))
            for player in team_data.get("players", []):
                player["__meta__"] = {
                    "team": team_data.get("team"),
                    "league": team_data.get("league"),
                    "season": team_data.get("season"),
                    "file_path": str(file),  # <--- track original file
                }

                position = player.get("position")
                position_text = player.get("position_text")
                player["role"] = self.infer_role(position_text, position)

                all_players.append(player)

        return all_players
    def rank_players(self):
        players = self.load_players()
        if not players:
            return

        # Flatten to a wide DF: one row per player
        flat_rows = []
        for player in players:
            row = {
                "name": player.get("name"),
                "position": player.get("position"),
                "role": player.get("role"),
                "__player__": player,
            }
            for group, stats in (player.get("stats") or {}).items():
                for k, v in (stats or {}).items():
                    row[f"{group}:{k}"] = v
            flat_rows.append(row)

        df = pd.DataFrame(flat_rows)

        for role, weights in ROLE_RANK_MAPPING.items():
            if "role" not in df.columns:
                continue

            role_df = df[df["role"] == role].copy()
            if role_df.empty:
                continue

            breakdowns = {}  # {row_idx: {metric: value}}
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

                # Store each player's contribution to breakdown
                for idx, val in zip(role_df.index, contribution):
                    breakdowns.setdefault(idx, {})[key] = float(np.round(val, 5))

            if not weighted_parts:
                continue

            role_df["score"] = np.nansum(np.vstack(weighted_parts), axis=0)

            for idx, row in role_df.iterrows():
                player = row["__player__"]
                player.setdefault("ranking", {})["performance"] = float(np.round(row["score"], 3))
                player["ranking"]["breakdown"] = breakdowns.get(idx, {})

        self._save_ranked_players(players)

    def _save_ranked_players(self, players: list[dict]):
        # Re-group by original file path to write to correct source
        files_map: dict[str, list[dict]] = {}

        for p in players:
            path = p["__meta__"]["file_path"]
            files_map.setdefault(path, []).append(p)

        for file_path, plist in files_map.items():
            meta = plist[0]["__meta__"]

            for p in plist:
                p.pop("__meta__", None)  # cleanup before saving

            payload = {
                "league": meta["league"],
                "season": meta["season"],
                "team": meta["team"],
                "players": plist,
            }

            Path(file_path).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
