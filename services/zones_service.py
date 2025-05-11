from typing import Any, Dict, List
from collections import defaultdict

from models.players import PlayerModel
from models.zones.zones_config import ZONE_CONFIG
from services.fbref_data_service import SoccerDataService


class ZoneService:
    def __init__(self, data_service: SoccerDataService = None):
        self.data_service = data_service

    def compute_all_zones(self, players: List[PlayerModel], team_stats: List[Dict[str, Any]]) -> Dict[str, dict]:
        flat_team_stats = {}
        for d in team_stats:
            if isinstance(d, dict):
                flat_team_stats.update(d)

        zones = {}

        ordered_zone_ids = [
            "defLeftWide", "defLeftHalf", "defCentral", "defRightHalf", "defRightWide",
            "midLeftWide", "midLeftHalf", "midCentral", "midRightHalf", "midRightWide",
            "attLeftWide", "attLeftHalf", "attCentral", "attRightHalf", "attRightWide"
        ]

        for zone_id in ordered_zone_ids:
            config = ZONE_CONFIG.get(zone_id)
            if not config:
                continue

            self.current_zone = zone_id
            zone_players = self._filter_players(players, config["positions"])

            player_rating = self.aggregate_zone_rating(zone_players, config["positions"])
            team_data = self.extract_zone_team_data(flat_team_stats, config["stat_types"])

            zones[zone_id] = {
                "label": config["label"],
                "players": {},  # optional: could be empty or list if needed
                "rating": round(player_rating, 2),
                "team": team_data,
            }

        return zones

    def _filter_players(self, players: List[PlayerModel], positions_config: Dict[str, float]) -> List[PlayerModel]:
        allowed = set(positions_config.keys())
        return [p for p in players if p.role in allowed]

    def aggregate_zone_rating(self, players: List[PlayerModel], positions_config: Dict[str, float]) -> float:
        role_weights = {p.role: positions_config[p.role] for p in players if p.role in positions_config}
        total_weight = sum(role_weights.values())

        if total_weight == 0:
            return 0.0

        weighted_sum = 0.0
        for player in players:
            weight = role_weights.get(player.role, 0)
            weighted_sum += player.rating * weight

        return weighted_sum / total_weight

    def extract_zone_team_data(self, team_stats: Dict[str, float], stat_type_config: Dict[str, Any]) -> Dict[str, float]:
        zone_stats = defaultdict(float)

        for stat_type, config in stat_type_config.items():
            if isinstance(config, dict):
                type_weight = config.get("weight", 1.0)
                keys = config.get("keys", {})
                for key, key_weight in keys.items():
                    val = float(team_stats.get(key, 0))
                    zone_stats[key] += val * type_weight * key_weight
            else:
                stat_keys = self.data_service.get_stat_keys(stat_type) if self.data_service else []
                for key in stat_keys:
                    val = float(team_stats.get(key, 0))
                    zone_stats[key] += val * config

        return dict(zone_stats)
