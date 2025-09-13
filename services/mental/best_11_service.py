from collections import defaultdict
from typing import List, Dict, DefaultDict, Set
from services.plotting.plotting_service import BestXIPlotter

# ====== Constants ======
LINES = {
    "GK": {
            "GK": {"min": 1, "max": 1, "roles": ["GK"]},
},
    "DEF" : {
        "CB": {"min": 2, "max": 3, "roles": ["CB", "LCB", "RCB"]},
        "FB": {"min": 2, "max": 2, "roles": ["FB", "LB", "RB"]},
    },
    "MID" : {
        "DM": {"min": 1, "max": 4, "roles": ["DM", "CDM", "LDM", "RDM"]},
        "CM": {"min": 1, "max": 2, "roles": ["CM", "DM"]},
        "AM": {"min": 1, "max": 2, "roles": ["AM", "CAM"]},
    },
    "ATT" : {
        "W": {"min": 2, "max": 2, "roles": ["LW", "RW", "RM", "LM"]},
        "CF": {"min": 1, "max": 2, "roles": ["CF", "ST"]},
    }
}

FORMATIONS = {
    "433": {
        "GK": {"GK": 1},
        "DEF": {"CB": 2, "FB": 2},
        "MID": {"DM": 1, "CM": 1, "AM": 1, "no_order": True},
        "ATT": {"W": 2, "CF": 1}
    },
    "4231": {
          "GK": {"GK": 1},
        "DEF": {"CB": 2, "FB": 2},
        "MID": {"DM": 1, "CM": 1, "AM": 1, "no_order": False},
        "ATT": {"W": 2, "CF": 1}
    },
    "532": {
          "GK": {"GK": 1},
        "DEF": {"CB": 3, "FB": 2},
        "MID": {"CM": 2, "AM": 1, "no_order": True},
        "ATT": {"CF": 2}
    }
}

ROLE_CATEGORY_MAP = {
    "GK": "GK",
    "CB": "CB", "LCB": "CB", "RCB": "CB",
    "RB": "FB", "LB": "FB", "FB": "FB", "RWB": "FB", "LWB": "FB", "WB": "FB",
    "DM": "DM", "CDM": "DM", "LDM": "DM", "RDM": "DM",
    "CM": "CM", "CAM": "CM",
    "AM": "AM", "CAM": "AM", "CM": "AM",
    "LW": "W", "RW": "W", "LM": "W", "RM": "W", "W": "W",
    "CF": "CF", "ST": "CF"
}

# ====== Builder ======
class BestXIBuilder:
    def __init__(self, players: List[Dict]):
        self.players = [p for p in players if p.get("role") in ROLE_CATEGORY_MAP and p.get("role") != "NA"]
        self.unknown_roles = [p for p in players if p.get("role") not in ROLE_CATEGORY_MAP or p.get("role") == "NA"]
        for p in self.unknown_roles:
            print(f"[WARN] Player {p['name']} has unknown role '{p.get('role')}'")

    @staticmethod
    def _sort_players(players: List[Dict], key_type: str = "mental") -> List[Dict]:
        if key_type == "mental":
            return sorted(players, key=lambda p: p.get("mental", {}).get("m_raw", 0), reverse=True)
        elif key_type == "performance":
            return sorted(players, key=lambda p: p.get("ranking", {}).get("performance", 0), reverse=True)
        return players

    def _pick_subline(self, subline_def: Dict, used_names: Set[str], spots: int, key_type="mental") -> List[Dict]:
        candidates = [p for p in self.players if p["role"] in subline_def["roles"] and p["name"] not in used_names]
        candidates = self._sort_players(candidates, key_type)
        take = min(spots, len(candidates))
        picked = candidates[:take]
        used_names.update(p["name"] for p in picked)
        return picked

    def _pick_line(self, line_def: Dict, formation_line: Dict, used_names: Set[str], key_type="mental") -> List[Dict]:
        picked = []
        no_order = formation_line.get("no_order", False)
        if no_order:
            total_spots = sum(formation_line[k] for k in formation_line if k != "no_order")
            all_roles = []
            for sub_def in line_def.values():
                all_roles.extend(sub_def["roles"])
            candidates = [p for p in self.players if p["role"] in all_roles and p["name"] not in used_names]
            candidates = self._sort_players(candidates, key_type)
            picked = candidates[:total_spots]
            used_names.update(p["name"] for p in picked)
        else:
            for sub_name, spots in formation_line.items():
                if sub_name == "no_order":
                    continue
                sub_def = line_def[sub_name]
                picked.extend(self._pick_subline(sub_def, used_names, spots, key_type))
        return picked

    def _minimal_player(self, p: Dict) -> Dict:
        """Return a minimal cleaned player dictionary for best XI outputs."""
        return {
            "name": p.get("name", ""),
            "position": p.get("position", ""),
            "age": p.get("age", ""),
            "position_text": p.get("position_text", ""),
            "role": p.get("role", ""),
            "mental": p.get("mental", {"m": 0}),
            "performance": p.get("ranking", {"performance": 0}),
            "league": p.get("league", ""),
            "team": p.get("team", ""),
            "profile_img": p.get("profile_img", ""),
            "foot": p.get("foot", ""),
        }

    def build_formation(self, formation_name: str) -> Dict:
        formation_def = FORMATIONS[formation_name]
        used_names = set()
        starting_11 = []

        for line_name, formation_line in formation_def.items():
            line_def = LINES[line_name]
            starting_11.extend(
                self._pick_line(line_def, formation_line, used_names, key_type="mental")
            )

        # Substitutes: pick next best remaining per category
        remaining_players = [p for p in self.players if p["name"] not in used_names]
        subs = self._sort_players(remaining_players, "mental")[:7]  # top 7 subs
        used_names.update(p["name"] for p in subs)

        # Performance-based XI
        perf_used_names = set()
        best_perf_11 = []
        for line_name, formation_line in formation_def.items():
            line_def = LINES[line_name]
            best_perf_11.extend(
                self._pick_line(line_def, formation_line, perf_used_names, key_type="performance")
            )

        return {
            "name": formation_name,
            "formation": formation_def,
            "starting_11": [self._minimal_player(p) for p in starting_11],
            "subs": [self._minimal_player(p) for p in subs],
            "score": sum(p.get("mental", {}).get("m_raw", 0) for p in starting_11),
            "best_performing_eleven": [self._minimal_player(p) for p in best_perf_11],
        }

    def build_best_formations(self, top_n=3) -> List[Dict]:
        results = [self.build_formation(fname) for fname in FORMATIONS.keys()]
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_n]
    @staticmethod
    def categorize_players(players: List[Dict]) -> Dict[str, List[Dict]]:
        categorized: DefaultDict[str, List[Dict]] = defaultdict(list)
        for p in players:
            cat = ROLE_CATEGORY_MAP.get(p.get("role"))
            if cat:
                categorized[cat].append(p)
        for plist in categorized.values():
            plist.sort(key=lambda p: p.get("mental", {}).get("m_raw", 0), reverse=True)
        return categorized

    @staticmethod
    def log_top_players_per_role(players: List[Dict], top_n=10):
        categorized = BestXIBuilder.categorize_players(players)
        return categorized
    
