from __future__ import annotations
from collections import defaultdict
from typing import List
import numpy as np
import pandas as pd

from models.mental.mental import ROLE_AWARE_MENTAL_TRAIT_MAPPING
from models.ranking.ranking import LOWER_IS_BETTER

# Mapping FBRef/Transfermarkt-style positions to mental roles
ROLE_MAPPING = {
    "GK": "GK",
    "CB": "CB",
    "LCB": "CB",
    "RCB": "CB",
    "LB": "FB",
    "LWB": "FB",
    "RB": "FB",
    "RWB": "FB",
    "CDM": "DM",
    "DM": "DM",
    "CM": "CM",
    "LCM": "CM",
    "RCM": "CM",
    "CAM": "AM",
    "LAM": "AM",
    "RAM": "AM",
    "LM": "W",
    "RM": "W",
    "LW": "W",
    "RW": "W",
    "CF": "CF",
    "ST": "CF",
    "LS": "CF",
    "RS": "CF",
}

class MentalRankingService:
    def __init__(self, players: List[dict]):
        self.players = players

    def score_team_players(self) -> List[dict]:
        """Compute mental score for all players, balanced across roles and trait categories."""

        flat_rows = []
        for player in self.players:
            raw_role = player.get("role", "OTHER")
            mental_role = ROLE_MAPPING.get(raw_role, "OTHER")
            row = {"name": player.get("name"), "role": mental_role, "__player__": player}
            for group, stats in (player.get("stats") or {}).items():
                for k, v in (stats or {}).items():
                    row[f"{group}:{k}"] = v
            flat_rows.append(row)

        df = pd.DataFrame(flat_rows)
        df["standard:Playing Time - Min"] = df.get("standard:Playing Time - Min", 0).fillna(0)
        df = df[df["standard:Playing Time - Min"] >= 300]
        if df.empty:
            return self.players

        breakdowns = {}
        m_raw_list = []

        for idx, row in df.iterrows():
            role = row.get("role", "OTHER")
            trait_map = self.merged_trait_map(role)

            trait_scores = []
            trait_breakdown = {}

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
                    avg_trait = np.mean(vals)
                    trait_scores.append(avg_trait)
                    trait_breakdown[trait] = avg_trait

            # Fallback: if no trait values, compute simple normalized playing time metric
            if trait_scores:
                m_raw = np.mean(trait_scores)
            else:
                # Prevent None for m_raw: fallback to 50% + small variation by minutes
                m_raw = 50.0 + min(0.5, row.get("standard:Playing Time - Min", 0)/3000)

            breakdowns[idx] = trait_breakdown
            m_raw_list.append(m_raw)

        df["m_raw"] = m_raw_list

        # --- Role-aware normalization ---
        df["m"] = np.nan
        for role, group in df.groupby("role"):
            valid = group["m_raw"].dropna()
            if valid.empty:
                continue
            min_v, max_v = valid.min(), valid.max()
            if min_v == max_v:
                df.loc[group.index, "m"] = 50.0
            else:
                df.loc[group.index, "m"] = ((group["m_raw"] - min_v) / (max_v - min_v) * 100).round(1)

        # --- Write back to player dict ---
        for idx, row in df.iterrows():
            player_obj = row["__player__"]
            player_obj["mental"] = {
                "m_raw": float(np.round(row["m_raw"], 5)),
                "m": float(row["m"]),
                "breakdown": breakdowns.get(idx, {}),
            }

        return self.players

    @staticmethod
    def merged_trait_map(role: str) -> dict[str, list[str]]:
        """
        Combine global 'ALL' traits with role-specific traits.
        Ensures all trait keys are lists and handles missing keys gracefully.
        """
        combined = defaultdict(list)

        # Global traits (fallback)
        for trait, keys in ROLE_AWARE_MENTAL_TRAIT_MAPPING.get("ALL", {}).items():
            if isinstance(keys, str):
                keys = [keys]
            combined[trait].extend(keys)

        # Role-specific traits
        for trait, keys in ROLE_AWARE_MENTAL_TRAIT_MAPPING.get(role, {}).items():
            if isinstance(keys, str):
                keys = [keys]
            combined[trait].extend(keys)

        return combined
