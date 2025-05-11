import sys
from typing import List, Dict, Tuple
from collections import defaultdict, Counter
import logging
from models.players import PlayerModel
from models.stats_aware.stats_aware import SCORE_CONFIG, SCORE_CONFIG_WEIGHTS
from models.team import TeamModel
from typing import List, Dict, Tuple
from collections import defaultdict
import logging
FORMATION_WEIGHTS = {
    "4-3-3": 1.0,
    "4-2-3-1": 0.95,
    "4-4-2": 0.9,
    "3-5-2": 0.85,
    "5-3-2": 0.75,
    "5-2-3": 0.7,
}

class BaseXIService:
    def map_to_simple_position(self, pos_str: str) -> str:
        if not pos_str:
            return ""
        
        # Clean up and prioritize based on order
        parts = [p.strip() for p in pos_str.split(",")]

        for part in parts:
            if part == "GK":
                return "GK"
            elif part == "DF":
                return "DEF"
            elif part == "MF":
                return "MID"
            elif part == "FW":
                return "FWD"

        return ""

    def is_eligible(self, player: PlayerModel) -> bool:
        stats = player.stats.get("standard", [])
        minutes = next((s["val"] for s in stats if s["label"] == "Minutes Played"), 0)
        return minutes >= 910

    def get_score(self, player: PlayerModel) -> float:
        pos = self.map_to_simple_position(player.position)
        config = SCORE_CONFIG.get(pos, {})
        weights = SCORE_CONFIG_WEIGHTS.get(pos, {"pros": 1.0, "important": 2.0, "cons": 1.0})
        score = 0.0

        for impact, stat_map in config.items():
            polarity = 1.0 if impact != "cons" else -1.0
            weight = weights.get(impact, 1.0)
            for stat_type, labels in stat_map.items():
                stat_list = player.stats.get(stat_type, [])
                for label in labels:
                    for stat in stat_list:
                        if stat["label"] == label:
                            val = stat["val"]
                            if isinstance(val, (int, float)) and val > 0:
                                score += polarity * weight * val
                                # DEBUG
                                # print(f"✓ {player.name}: {label} = {val}, weight = {weight}, impact = {impact}")
        return round(score, 2)

    def group_by_position(self, players: List[PlayerModel]) -> Dict[str, List[PlayerModel]]:
        grouped = defaultdict(list)
        for player in players:
            pos = self.map_to_simple_position(player.position)
            if pos:
                grouped[pos].append(player)
        return grouped

    def get_formation_templates(self) -> List[Tuple[int, int, int]]:
        return [(4, 3, 3), (4, 2, 3), (3, 5, 2), (5, 3, 2)]

    def select_best_xi(self, players: List[PlayerModel]) -> Tuple[List[PlayerModel], str]:
        eligible_players = [p for p in players if self.is_eligible(p)]

        for player in eligible_players:
            player.rating = self.get_score(player)

        grouped = self.group_by_position(eligible_players)

        for pos in grouped:
            grouped[pos].sort(key=lambda p: p.rating, reverse=True)

        best_total_score = 0
        best_xi = []
        best_formation = ""

        for def_n, mid_n, fwd_n in self.get_formation_templates():
            logging.info(f"Trying formation DEF:{def_n}, MID:{mid_n}, FWD:{fwd_n}...")
            gk = grouped.get("GK", [])[:1]
            defs = grouped.get("DEF", [])[:def_n]
            mids = grouped.get("MID", [])[:mid_n]
            fwds = grouped.get("FWD", [])[:fwd_n]

            if len(gk) < 1 or len(defs) < def_n or len(mids) < mid_n or len(fwds) < fwd_n:
                logging.warning("Not enough players for formation")
                continue

            temp_xi = gk + defs + mids + fwds
            temp_score = sum(p.rating for p in temp_xi)
            
            temp_score *= FORMATION_WEIGHTS.get(f"{def_n}-{mid_n}-{fwd_n}", 1.0)
            
            if temp_score > best_total_score:
                best_total_score = temp_score
                best_xi = temp_xi
                best_formation = f"{def_n}-{mid_n}-{fwd_n}"

        if not best_xi:
            logging.error("No valid formation could be satisfied from eligible players.")

        return best_xi, best_formation



class BestXIService(BaseXIService):
    def init(self, team: TeamModel):
        self.team = team
        self.players = team.players
        self.league = team.league
        self.season = team.season
        self.name = team.name
        logging.info(f"BestXIService initialized for {self.name} / {self.season}")

    def run(self, team: TeamModel) -> List[PlayerModel]:
        self.team = team
        self.players = team.players
        self.league = team.league
        self.season = team.season
        self.name = team.name
        return self.select_best_xi(self.players)

class LeagueBestXIService(BaseXIService):
    def init(self, teams: List[TeamModel]):
        self.teams = teams
        self.players = [p for team in teams for p in team.players]
        logging.info(f"LeagueBestXIService initialized with {len(self.players)} players from {len(self.teams)} teams.")

    def run(self) -> Tuple[List[PlayerModel], str]:
        return self.select_best_xi(self.players)


