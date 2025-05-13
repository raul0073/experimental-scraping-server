from typing import Any, Dict, List, Optional, Union
from collections import defaultdict
import logging

from models.players import PlayerModel
from models.stats_type import TeamStatBlock
from models.zones.zones_config import ZONE_CONFIG, POSITIONS_FALLBACK_MAP
from services.fbref_data_service import SoccerDataService


class ZoneService:
    def __init__(self, data_service: SoccerDataService):
        if not data_service:
            raise ValueError("ZoneService requires a SoccerDataService instance")
        self.data_service = data_service

    def compute_all_zones(
        self,
        players: List[PlayerModel],
        team_stats: List[Dict[str, Any]],
        team_stats_against: List[Dict[str, Any]],
    ) -> Dict[str, dict]:
        """
        Calculate normalized zone ratings from player performance, team stats, and opponent stats.
        Returns a dictionary mapping each zone ID to its metadata and normalized score.
        """
        zones: Dict[str, dict] = {}
        raw_scores: Dict[str, dict] = {}

        flat_own = self._flatten_stats(team_stats)
        flat_against = self._flatten_stats(team_stats_against)

        # 1️⃣ Compute raw scores for each zone
        for zone_id, config in ZONE_CONFIG.items():
            try:
                zone_players = self._filter_players(players, config["positions"])
                player_score = self._score_players(zone_players, config["positions"])

                team_score = self._score_stats(flat_own, config.get("pros", {}).get("team", {})) \
                            - self._score_stats(flat_own, config.get("cons", {}).get("team", {}))

                against_score = self._score_stats(flat_against, config.get("pros", {}).get("against", {})) \
                            - self._score_stats(flat_against, config.get("cons", {}).get("against", {}))

                raw_scores[zone_id] = {
                    "label": config["label"],
                    "players": [p.model_dump() for p in zone_players],
                    "raw": {
                        "team": team_score,
                        "against": against_score,
                        "players": player_score,
                    },
                }

            except Exception as e:
                logging.exception(f"❌ Error computing zone '{zone_id}': {e}")

        # 2️⃣ Normalize raw scores to 0–100 scale
        max_team = max((v["raw"]["team"] for v in raw_scores.values()), default=1.0)
        max_against = max((v["raw"]["against"] for v in raw_scores.values()), default=1.0)
        max_players = max((v["raw"]["players"] for v in raw_scores.values()), default=1.0)

        for zone_id, data in raw_scores.items():
            team_norm = (data["raw"]["team"] / max_team) * 100 if max_team else 0.0
            raw_against = data["raw"]["against"]
            normalized_against = (abs(raw_against) / max(abs(v["raw"]["against"]) for v in raw_scores.values())) * 100

            # Flip sign if original was negative
            against_norm = -normalized_against if raw_against < 0 else normalized_against
            against_norm = max(0, 100 + against_norm)
            player_norm = (data["raw"]["players"] / max_players) * 100 if max_players else 0.0

            final_score = round(
                (team_norm * 0.4) +
                (against_norm * 0.4) +
                (player_norm * 0.3), 2
            )

            zones[zone_id] = {
                "label": data["label"],
                "rating": final_score,
                "players": data["players"],
                "breakdown": {
                    "team": round(team_norm, 2),
                    "against": round(against_norm, 2),
                    "players": round(player_norm, 2),
                }
            }

        return zones


    def _filter_players(self, players: List[PlayerModel], positions_config: Dict[str, float]) -> List[PlayerModel]:
        valid_roles = set(positions_config.keys())
        return [p for p in players if p.role in valid_roles]

    def _flatten_stats(self, stat_blocks: List[Dict[str, Any]]) -> Dict[str, float]:
        flat: Dict[str, float] = {}
        for block in stat_blocks:
            for row in block.get("rows", []):
                label, val = row.get("label"), row.get("val")
                if label and isinstance(val, (int, float)):
                    flat[label] = val
        return flat

    def _score_stats(self, flat: Dict[str, float], keys: Dict[str, List[str]]) -> float:
        return sum(flat.get(key, 0.0) for stat_keys in keys.values() for key in stat_keys)

    def _score_players(self, players: List[PlayerModel], weights: Dict[str, float]) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for player in players:
            weight = self.get_position_weight(player.role, weights)
            if weight > 0:
                total_weight += weight
                weighted_sum += player.rating * weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @staticmethod
    def get_position_weight(role: str, config: Dict[str, float]) -> float:
        if role in config:
            return config[role]
        fallback = POSITIONS_FALLBACK_MAP.get(role)
        return config.get(fallback, 0.0) * 0.8 if fallback in config else 0.0
