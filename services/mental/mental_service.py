# services/fbref/mental_ranking_service.py
from __future__ import annotations
from collections import defaultdict
import numpy as np
import pandas as pd
from typing import List

from models.mental.mental import ROLE_AWARE_MENTAL_TRAIT_MAPPING
from models.ranking.ranking import LOWER_IS_BETTER
from models.players.player_type import RoleType


class MentalRankingService:
    def __init__(self, players: List[dict]):
        self.players = players

    def score_team_players(self) -> List[dict]:
        flat_rows = []
        for player in self.players:
            row = {
                "name": player.get("name"),
                "role": player.get("role", "OTHER"),
                "__player__": player,
            }
            for group, stats in (player.get("stats") or {}).items():
                for k, v in (stats or {}).items():
                    row[f"{group}:{k}"] = v
            flat_rows.append(row)

        df = pd.DataFrame(flat_rows)
        df = df[df.get("standard:Playing Time - Min", 0) >= 600]
        if df.empty:
            return self.players

        trait_scores = []
        breakdowns = {}

        for idx, row in df.iterrows():
            role = row.get("role", "OTHER")
            trait_map = self.merged_trait_map(role)

            trait_vals = {}
            for trait, keys in trait_map.items():
                vals = []
                for key in keys:
                    val = row.get(key)
                    if val is None or not np.isfinite(val):
                        continue
                    z = float(val)
                    if key.split(":")[-1] in LOWER_IS_BETTER:
                        z *= -1
                    vals.append(z)
                if vals:
                    trait_vals[trait] = np.mean(vals)

            if trait_vals:
                breakdowns[idx] = trait_vals
                trait_scores.append(np.mean(list(trait_vals.values())))
            else:
                trait_scores.append(None)

        df["m_raw"] = trait_scores

        # Normalize to 0–100 scale
        valid = df["m_raw"].dropna()
        min_v, max_v = valid.min(), valid.max()
        df["m"] = ((df["m_raw"] - min_v) / (max_v - min_v) * 100).round(1)

        for idx, row in df.iterrows():
            p = row["__player__"]
            if pd.notna(row["m_raw"]):
                p["mental"] = {
                    "m_raw": float(np.round(row["m_raw"], 5)),
                    "m": float(row["m"]),
                    "breakdown": breakdowns.get(idx, {}),
                }

        return self.players


    @staticmethod
    def merged_trait_map(role: str) -> dict[str, list[str]]:
        combined = defaultdict(list)

        # Global mental traits
        for trait, keys in ROLE_AWARE_MENTAL_TRAIT_MAPPING.get("ALL", {}).items():
            combined[trait].extend(keys)

        # Role-specific traits
        for trait, keys in ROLE_AWARE_MENTAL_TRAIT_MAPPING.get(role, {}).items():
            combined[trait].extend(keys)

        return combined