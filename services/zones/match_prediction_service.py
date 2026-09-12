from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from models.zones.zones_config import ZONE_IMPORTANCE, ZONE_MATCHUPS

log = logging.getLogger(__name__)

# hand-tuned in the 2025 original; Stage 5 fits these against real results.
DEFAULT_PARAMS = {
    "delta_exp": 1.2,     # non-linearity on zone-advantage deltas
    "delta_coef": 0.9,    # delta -> xG contribution scale
    "delta_cap": 1.5,     # clamp on deltas
    "global_mult": 2.0,   # final xG multiplier
    "base_xg": 0.35,      # floor so even outmatched sides create something
}


class MatchPredictionService:
    """Zone-matchup xG estimator (v2 of the recovered fc273d2 service).

    Pits each of team A's zones against team B's mirrored zone
    (attLeftWide vs defRightWide, mid vs mid, build-up vs press), weights by
    zone importance, and converts advantage deltas into an xG pair.
    Outcome probabilities are NOT computed here — the Stage 5 probability
    layer feeds these xG values into a calibrated Poisson grid with home
    advantage.
    """

    def __init__(self, params: Optional[Dict[str, float]] = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}

    def predict(self, team_a: str, zones_a: Dict[str, Any],
                team_b: str, zones_b: Dict[str, Any]) -> Dict[str, Any]:
        raw_a = self._expected_goals(zones_a, zones_b)
        raw_b = self._expected_goals(zones_b, zones_a)

        sum_a = sum(z["rating"] for z in zones_a.values())
        sum_b = sum(z["rating"] for z in zones_b.values())
        total = (sum_a + sum_b) or 1.0

        xg_a = round(self.params["base_xg"] + raw_a * (sum_a / total) * self.params["global_mult"], 3)
        xg_b = round(self.params["base_xg"] + raw_b * (sum_b / total) * self.params["global_mult"], 3)

        return {
            "team_a": team_a,
            "team_b": team_b,
            "xg": {team_a: xg_a, team_b: xg_b},
            "matchups": self._matchup_labels(team_a, zones_a, team_b, zones_b),
        }

    def _expected_goals(self, attacker: Dict[str, Any], defender: Dict[str, Any]) -> float:
        total = 0.0
        for att_zone, def_zone in ZONE_MATCHUPS.items():
            az, dz = attacker.get(att_zone), defender.get(def_zone)
            if not az or not dz:
                continue
            delta = (az["rating"] - dz["rating"]) / 100.0
            if delta <= 0:
                continue
            delta = min(delta, self.params["delta_cap"])
            total += (delta ** self.params["delta_exp"]) * self.params["delta_coef"] \
                * ZONE_IMPORTANCE.get(att_zone, 1.0)
        return round(total, 4)

    def _matchup_labels(self, team_a, zones_a, team_b, zones_b) -> Dict[str, str]:
        out = {}
        for att_zone, def_zone in ZONE_MATCHUPS.items():
            az, dz = zones_a.get(att_zone), zones_b.get(def_zone)
            if not az or not dz:
                out[att_zone] = "missing"
                continue
            delta = round((az["rating"] - dz["rating"]) / 100.0, 2)
            if delta > 0.2:
                out[att_zone] = f"{team_a} advantage ({delta})"
            elif delta < -0.2:
                out[att_zone] = f"{team_b} advantage ({abs(delta)})"
            else:
                out[att_zone] = "even"
        return out
