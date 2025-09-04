
from collections import defaultdict
from typing import List


class BestXIBuilder:
    def __init__(self, players: List[dict]):
        self.players = players

    def build(self) -> List[dict]:
         # 🔥 Best XI
        role_map = {
            "GK": 1,
            "CB": 2,
            "FB": 2,
            "DM" : 1,
            "CM": 1,
            "AM": 1,
            "W": 2,
            "CF": 1,
        }

        role_groups = defaultdict(list)
        for p in self.players:
            role = p.get("role")
            if role in role_map:
                role_groups[role].append(p)

        best_11 = []
        for role, count in role_map.items():
            sorted_role_players = sorted(role_groups[role], key=lambda p: p["mental"]["m"], reverse=True)
            best_11.extend(sorted_role_players[:count])
        return best_11