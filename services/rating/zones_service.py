from typing import Any, Dict, List, Optional
from models.players import PlayerModel
from models.zones.zones_config import ZONE_CONFIG, POSITIONS_FALLBACK_MAP, ZONE_SCALERS, ZoneBreakdown, ZoneBreakdownEntry, ZoneData, ZonePlayerBreakdown, ZonePlayerContribution
import logging
ZONE_ROLE_WEIGHTS = {
    "def": {"team": 0.25, "against": 0.50, "players": 0.25},
    "mid": {"team": 0.45, "against": 0.25, "players": 0.30},
    "att": {"team": 0.30, "against": 0.25, "players": 0.45},
}

class ZoneService:
    def __init__(self, data_service: Optional[Any] = None):
        self.data_service = data_service
        self.zone_config = ZONE_CONFIG
        self.zone_scalers = ZONE_SCALERS

    def set_custom_config(self, zone_config: Optional[Dict[str, dict]], zone_scalers: Optional[Dict[str, float]]):
        if zone_config:
            self.zone_config = zone_config
        if zone_scalers:
            self.zone_scalers = zone_scalers
            
    def compute_all_zones(
            self,
            players: List[PlayerModel],
            team_stats: List[Dict[str, Any]],
            team_stats_against: List[Dict[str, Any]],
            zone_config: Optional[Dict[str, dict]] = None,
            zone_scalers: Optional[Dict[str, Dict[str, float]]] = None,
        ) -> Dict[str, ZoneData]:

            zone_config = zone_config or ZONE_CONFIG
            zone_scalers = zone_scalers or ZONE_SCALERS
            flat_own = self._flatten_stats(team_stats)
            flat_against = self._flatten_stats(team_stats_against)
            raw_scores: Dict[str, dict] = {}

            for zone_id, config in zone_config.items():
                try:
                    scalers = zone_scalers.get(zone_id, {})
                    zone_players = self._filter_players(players, config["positions"])
                    player_score = self._score_players(zone_players, config["positions"])

                    team_pros = self._score_stats(flat_own, config.get("pros", {}).get("team", {}), scalers)
                    team_cons = self._score_stats(flat_own, config.get("cons", {}).get("team", {}), scalers)
                    team_score = team_pros["score"] - team_cons["score"]

                    against_pros = self._score_stats(flat_against, config.get("pros", {}).get("against", {}), scalers)
                    against_cons = self._score_stats(flat_against, config.get("cons", {}).get("against", {}), scalers)
                    against_score = against_pros["score"] - against_cons["score"]

                    raw_scores[zone_id] = {
                        "label": config["label"],
                        "players": [
                            {
                                **p.model_dump(),
                                "_zone_position_config": config["positions"]
                            } for p in zone_players
                        ],
                        "raw": {
                            "team": team_score,
                            "against": against_score,
                            "players": player_score
                        },
                        "keys": {
                            "team": {"pros": team_pros["keys"], "cons": team_cons["keys"]},
                            "against": {"pros": against_pros["keys"], "cons": against_cons["keys"]},
                        },
                    }
                except Exception as e:
                    logging.exception(f"Error computing zone '{zone_id}': {e}")

            max_team = max((v["raw"]["team"] for v in raw_scores.values()), default=1.0)
            max_against = max((abs(v["raw"]["against"]) for v in raw_scores.values()), default=1.0)
            max_players = max((v["raw"]["players"] for v in raw_scores.values()), default=1.0)

            zones: Dict[str, ZoneData] = {}
            for zone_id, data in raw_scores.items():
                prefix = zone_id[:3]
                blend = ZONE_ROLE_WEIGHTS.get(prefix, ZONE_ROLE_WEIGHTS["mid"])

                team_norm = (data["raw"]["team"] / max_team) * 100
                against_norm = (data["raw"]["against"] / max_against) * 50 + 50  # Normalize to 0-100 center 50
                player_norm = (data["raw"]["players"] / max_players) * 100 if max_players else 0.0

                final_score = round(
                    team_norm * blend["team"] +
                    against_norm * blend["against"] +
                    player_norm * blend["players"], 2
                )

                zones[zone_id] = ZoneData(
                    label=data["label"],
                    rating=final_score,
                    breakdown=ZoneBreakdown(
                        team=ZoneBreakdownEntry(
                            score=round(team_norm, 2),
                            raw=round(data["raw"]["team"], 2),
                            pros=data["keys"]["team"]["pros"],
                            cons=data["keys"]["team"]["cons"],
                            weight=blend["team"]
                        ),
                        against=ZoneBreakdownEntry(
                            score=round(against_norm, 2),
                            raw=round(data["raw"]["against"], 2),
                            pros=data["keys"]["against"]["pros"],
                            cons=data["keys"]["against"]["cons"],
                            weight=blend["against"]
                        ),
                        players=ZonePlayerBreakdown(
                            score=round(player_norm, 2),
                            raw=round(data["raw"]["players"], 2),
                            weight=blend["players"],
                            contributions=[
                                ZonePlayerContribution(
                                    name=p["name"],
                                    rating=p["rating"],
                                    minutes=self._get_minutes_played(PlayerModel(**p)),
                                    position_weight=self.get_position_weight(
                                    p["role"],
                                    p.get("_zone_position_config", {})
                                )
                                ) for p in data["players"]
                            ]
                        )
                    )
                )

            return zones

    def _score_stats(
        self,
        flat: Dict[str, float],
        keys_config: Dict[str, List[str]],
        scalers: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        score = 0.0
        used_keys: List[str] = []
        missing_keys: List[str] = []
        for stat_keys in keys_config.values():
            for key in stat_keys:
                if key in flat:
                    scale = scalers.get(key, 1.0) if scalers else 1.0
                    score += flat[key] * scale
                    used_keys.append(key)
                else:
                    missing_keys.append(key)
        if missing_keys:
            logging.warning(f"Missing keys: {missing_keys}")
            
        return {"score": score, "keys": used_keys}

    def _filter_players(self, players: List[PlayerModel], positions_config: Dict[str, float]) -> List[PlayerModel]:
        return [p for p in players if p.role in positions_config]

    def _flatten_stats(self, stat_blocks: List[Any]) -> Dict[str, float]:
        flat: Dict[str, float] = {}

        for block in stat_blocks:
            rows = block.rows if hasattr(block, "rows") else block.get("rows", [])
            for row in rows:
                label = row.label if hasattr(row, "label") else row.get("label")
                val = row.val if hasattr(row, "val") else row.get("val")
                if label and isinstance(val, (int, float)):
                    flat[label] = val

        return flat

    def _get_minutes_played(self, p: PlayerModel) -> float:
        """
        Look up “Minutes Played” in the player's stats.standard list.
        """
        # Grab the array of {label, val, rank} dicts:
        standard_list = getattr(p.stats, "standard", None) or p.stats.get("standard", [])
        # If for any reason it’s not there, fall back to flat p.stats list:
        if not isinstance(standard_list, list):
            standard_list = p.stats if isinstance(p.stats, list) else []

        for blk in standard_list:
            if blk.get("label") == "Minutes Played":
                try:
                    minutes = float(blk.get("val", 0))
                except (TypeError, ValueError):
                    minutes = 0.0
                return minutes

        return 0.0

    def _score_players(self, players: List[PlayerModel], weights: Dict[str, float]) -> float:
        """
        Minutes-weighted, position-weighted average of player.rating.
        """
        # build (player, minutes) list
        mins_list = [(p, self._get_minutes_played(p)) for p in players]
        total_minutes = sum(m for _, m in mins_list) or 1.0

        # sum up rating * pos_weight * (mins/total)
        score = 0.0
        for p, mins in mins_list:
            pos_w = self.get_position_weight(p.role, weights)
            share = mins / total_minutes
            score += p.rating * pos_w * share

        return score


    def get_position_weight(self, role: str, config: Dict[str, float]) -> float:
        checked = set()
        current = role.strip().upper()
        depth = 0

        while current not in checked and depth < 10:
            if current in config:
                return config[current]

            checked.add(current)
            fallback = POSITIONS_FALLBACK_MAP.get(current)

            if fallback and fallback not in checked:
                current = fallback
                depth += 1
            else:
                break

        logging.warning(f"No position weight match for role='{role}' (normalized='{current}') in config keys {list(config.keys())}")
        return 0.0
             
        
    def _score_player_metrics_for_zones(
        self,
        player: PlayerModel,
        keys_config: Dict[str, List[str]],
        scalers: Dict[str, float]
    ) -> float:
        """
        Flatten this player’s own stat blocks, 
        score them exactly the same way we do for the team, 
        then return pros.score – cons.score.
        """
        # we assume PlayerModel holds e.g. .stats.standard or .stats.zones,
        # but if every player has the same blocks shape as team_stats then:
        flat = self._flatten_stats(player.stats.get("standard"))  

        pros = self._score_stats(flat, keys_config.get("pros", {}).get("team", {}), scalers)
        cons = self._score_stats(flat, keys_config.get("cons", {}).get("team", {}), scalers)
        return pros["score"] - cons["score"]