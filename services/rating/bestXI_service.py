from typing import List, Tuple, Dict
import logging
from collections import defaultdict

import numpy as np
from models.players import PlayerModel
from models.stats_aware.stats_aware import SCORE_CONFIG, SCORE_CONFIG_WEIGHTS
from models.team import TeamModel

# Role‐ordering for final XI
DEF_ROLE_ORDER = {3:["CB","CB","CB"],4:["LB","CB","CB","RB"],5:["LB","LCB","CB","RCB","RB"]}
MID_ROLE_ORDER = {2:["CDM","CDM"],3:["LCM","CM","RCM"],4:["LM","LCM","RCM","RM"],5:["LWB","LCM","CDM","RCM","RWB"]}
FWD_ROLE_ORDER = {1:["ST"],2:["CF","ST"],3:["LW","ST","RW"],4:["LW","CF","ST","RW"]}


class BestXIService:
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
            """LCB matches CB, RCM matches CM, CAM matches AM/CM/CF as needed."""
            if player_role == template:
                return True
            # loose: template at the end (LCB → CB) or inside (CAM contains AM)
            return player_role.endswith(template) or template in player_role

        for template_role in order:
            exact = [p for p in rem if role_match(p.role, template_role)]
            pick  = max(exact, key=lambda x: x.rating) if exact else max(rem, key=lambda x: x.rating)
            assigned.append(pick)
            rem.remove(pick)
        return assigned

    def select_best_xi(self, team: TeamModel) -> Tuple[List[PlayerModel], str]:
        
        # 1) Filter & collect per-90 stats & track max per label
        eligible = [p for p in team.players if self.is_eligible(p)]
        if not eligible:
            logging.error("No eligible players.")
            return [], ""

        per90_list: List[Tuple[PlayerModel, Dict[str, float]]] = []
        label_max: Dict[str, float] = defaultdict(float)
        max_mins = 0

        for p in eligible:
            mins = next(
                (s["val"] for s in p.stats.get("standard", [])
                 if s["label"] == "Minutes Played"),
                0
            )
            max_mins = max(max_mins, mins)
            statmap: Dict[str, float] = {}

            pos = self.map_to_simple_position(p.position)
            conf = SCORE_CONFIG.get(pos, {})

            # build statmap of per-90 or percent metrics
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

        # 2) Build percentiles
        pct_map: Dict[str, Dict[float, float]] = {}
        for lbl, mx in label_max.items():
            vals = [statmap.get(lbl, 0.0) for (_, statmap) in per90_list]
            sorted_vals = sorted(vals)
            n = len(sorted_vals)
            pct_map[lbl] = { v: (sorted_vals.index(v) + 1) / n for v in sorted_vals }

        # 3) Score each player 0–100
        for p, statmap in per90_list:
            pos = self.map_to_simple_position(p.position)
            conf = SCORE_CONFIG.get(pos, {})
            wts  = SCORE_CONFIG_WEIGHTS

            contribs: List[float] = []
            for impact, stat_groups in conf.items():
                sign = 1 if impact != "cons" else -1
                w    = wts.get(impact, 1.0)
                for labels in stat_groups.values():
                    for lbl in labels:
                        if lbl in statmap:
                            norm = statmap[lbl]
                            pct  = pct_map[lbl].get(norm, 0.0)
                            contribs.append(sign * w * pct)

            perf_01 = sum(contribs) / len(contribs) if contribs else 0.0

            mins = next(
                (s["val"] for s in p.stats.get("standard", [])
                 if s["label"] == "Minutes Played"),
                0
            )
            avail = mins / max_mins if max_mins > 0 else 0.0

            p.rating = round((0.8 * perf_01 + 0.2 * avail) * 100, 1)

        # 4) Group & sort by line
        buckets = {"GK":[], "DEF":[], "MID":[], "FWD":[]}
        for p in eligible:
            line = self.map_to_simple_position(p.position)
            if line in buckets:
                buckets[line].append(p)
        for lst in buckets.values():
            lst.sort(key=lambda x: x.rating, reverse=True)

        logging.info(
            f"Counts -> GK={len(buckets['GK'])}, DEF={len(buckets['DEF'])}, "
            f"MID={len(buckets['MID'])}, FWD={len(buckets['FWD'])}"
        )

        # 5) Flexible XI search
        best_score, best_xi, best_cfg = -1, [], (0, 0, 0)
        for dn in range(3, 6):          
            for mn in range(2, 6):      
                fn = 10 - dn - mn       
                if not (1 <= fn <= 4):  
                    continue
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

                total = (gk_rating + avg_def + avg_mid + avg_fwd) / 4      # neutral metric

                if total > best_score:
                    best_score, best_xi, best_cfg = total, xi, (dn, mn, fn)

        if not best_xi:
            logging.error("No valid formation.")
            return [], ""

        # 6) Final role ordering
        dn,mn,fn = best_cfg
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
