from typing import List, Optional, Tuple, Dict
import logging
from collections import defaultdict
import numpy as np
from models.players import PlayerModel
from models.stats_aware.stats_aware import SCORE_CONFIG, SCORE_CONFIG_WEIGHTS
from models.team import TeamModel
from models.users.user import PlayerConfigModel
from services.db.user_config_service import UserConfigService

# Role‐ordering for final XI
DEF_ROLE_ORDER = {3:["CB","CB","CB"],4:["LB","CB","CB","RB"],5:["LB","LCB","CB","RCB","RB"]}
MID_ROLE_ORDER = {2:["CDM","CDM"],3:["LCM","CM","RCM"],4:["LM","LCM","RCM","RM"],5:["LWB","LCM","CDM","RCM","RWB"]}
FWD_ROLE_ORDER = {1:["ST"],2:["CF","ST"],3:["LW","ST","RW"],4:["LW","CF","ST","RW"]}

class BestXIService:
    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id

        # Load user document from DB
        user_doc = UserConfigService(user_id).load()
        players_config_raw = user_doc.get("players_config", {})

        # Validate and store configs, or fallback to defaults
        try:
            config_model = PlayerConfigModel.model_validate(players_config_raw)
            self.score_config = config_model.score_config
            self.score_weights = config_model.score_weights
        except Exception as e:
            import logging
            logging.warning(f"Invalid player config for user {user_id}: {players_config_raw} {e}")
            self.score_config = SCORE_CONFIG
            self.score_weights = SCORE_CONFIG_WEIGHTS
            
            
    def map_to_simple_position(self, pos_str: str) -> str:
        if not pos_str: return ""
        for key in ("GK","FW","MF","DF"):
            if key in pos_str:
                return {"GK":"GK","FW":"FWD","MF":"MID","DF":"DEF"}[key]
        return ""

    def is_eligible(self, p: PlayerModel) -> bool:
        mins = next((s["val"] for s in p.stats.get("standard",[]) if s["label"]=="Minutes Played"), 0)
        return mins >= 910

    def assign_line_roles(self, players: List[PlayerModel], order: List[str]) -> List[PlayerModel]:
        assigned, rem = [], players.copy()
        order = order[: len(players)]

        def role_match(player_role: str, template: str) -> bool:
            if player_role == template:
                return True
            return player_role.endswith(template) or template in player_role

        for template_role in order:
            exact = [p for p in rem if role_match(p.role, template_role)]
            pick  = max(exact, key=lambda x: x.rating) if exact else max(rem, key=lambda x: x.rating)
            assigned.append(pick)
            rem.remove(pick)
        return assigned

    def compute_per90_stats(self, eligible: List[PlayerModel]) -> Tuple[List[Tuple[PlayerModel, Dict[str, float]]], Dict[str, float], float]:
        per90_list = []
        label_max = defaultdict(float)
        max_mins = 0

        for p in eligible:
            mins = next((s["val"] for s in p.stats.get("standard", []) if s["label"] == "Minutes Played"), 0)
            max_mins = max(max_mins, mins)
            statmap = {}
            pos = self.map_to_simple_position(p.position)
            conf = self.score_config.get(pos, {})

            for impact in conf.values():
                for labels in impact.values():
                    for lbl in labels:
                        for sts in p.stats.get("standard", []):
                            if sts["label"] == lbl and isinstance(sts["val"], (int, float)):
                                val = sts["val"]
                                norm = val if lbl.endswith("%") else (val / (mins/90) if mins > 0 else 0.0)
                                statmap[lbl] = norm
                                label_max[lbl] = max(label_max[lbl], norm)
            per90_list.append((p, statmap))

        return per90_list, label_max, max_mins

    def build_percentiles(self, per90_list: List[Tuple[PlayerModel, Dict[str, float]]], label_max: Dict[str, float]) -> Dict[str, Dict[float, float]]:
        pct_map = {}
        for lbl, _ in label_max.items():
            vals = [statmap.get(lbl, 0.0) for (_, statmap) in per90_list]
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            pct_map[lbl] = {v: (sorted_vals.index(v) + 1) / n for v in sorted_vals}
        return pct_map

    def rate_players(self, per90_list: List[Tuple[PlayerModel, Dict[str, float]]], pct_map: Dict[str, Dict[float, float]], max_mins: float):
        for p, statmap in per90_list:
            pos = self.map_to_simple_position(p.position)
            conf = self.score_config.get(pos, {})
            wts = self.score_weights.model_dump()

            contribs = []
            for impact, stat_groups in conf.items():
                sign = 1 if impact != "cons" else -1
                w = wts.get(impact, 1.0)
                for labels in stat_groups.values():
                    for lbl in labels:
                        if lbl in statmap:
                            norm = statmap[lbl]
                            pct = pct_map[lbl].get(norm, 0.0)
                            contribs.append(sign * w * pct)

            perf_01 = sum(contribs) / len(contribs) if contribs else 0.0
            mins = next((s["val"] for s in p.stats.get("standard", []) if s["label"] == "Minutes Played"), 0)
            avail = mins / max_mins if max_mins > 0 else 0.0
            p.rating = round((0.8 * perf_01 + 0.2 * avail) * 100, 1)

    def select_best_xi(self, team: TeamModel) -> Tuple[List[PlayerModel], str]:
        eligible = [p for p in team.players if self.is_eligible(p)]
        if not eligible:
            logging.error("No eligible players.")
            return [], ""

        per90_list, label_max, max_mins = self.compute_per90_stats(eligible)
        pct_map = self.build_percentiles(per90_list, label_max)
        self.rate_players(per90_list, pct_map, max_mins)

        buckets = {"GK":[], "DEF":[], "MID":[], "FWD":[]}
        for p in eligible:
            line = self.map_to_simple_position(p.position)
            if line in buckets:
                buckets[line].append(p)
        for lst in buckets.values():
            lst.sort(key=lambda x: x.rating, reverse=True)

        best_score, best_xi, best_cfg = -1, [], (0, 0, 0)
        for dn in range(3, 6):
            for mn in range(2, 6):
                fn = 10 - dn - mn
                if not (1 <= fn <= 4): continue
                if len(buckets["DEF"]) < dn or len(buckets["MID"]) < mn or len(buckets["FWD"]) < fn:
                    continue
                xi = (
                    buckets["GK"][:1]
                    + buckets["DEF"][:dn]
                    + buckets["MID"][:mn]
                    + buckets["FWD"][:fn]
                )

                gk_rating = xi[0].rating

                def line_avg(code):
                    return np.mean([p.rating for p in xi if self.map_to_simple_position(p.position) == code])

                avg_def = line_avg("DEF")
                avg_mid = line_avg("MID")
                avg_fwd = line_avg("FWD")

                total = (gk_rating + avg_def + avg_mid + avg_fwd) / 4

                if total > best_score:
                    best_score, best_xi, best_cfg = total, xi, (dn, mn, fn)

        if not best_xi:
            logging.error("No valid formation.")
            return [], ""

        dn, mn, fn = best_cfg
        final = []
        final += best_xi[:1]
        final += self.assign_line_roles(best_xi[1:1+dn], DEF_ROLE_ORDER[dn])
        final += self.assign_line_roles(best_xi[1+dn:1+dn+mn], MID_ROLE_ORDER[mn])
        final += self.assign_line_roles(best_xi[-fn:], FWD_ROLE_ORDER[fn])

        formation = f"1-{dn}-{mn}-{fn}"
        logging.info(f"Chosen {formation} score={best_score}")
        return final, formation

    def run(self, team: TeamModel) -> Tuple[List[PlayerModel], str]:
        return self.select_best_xi(team)