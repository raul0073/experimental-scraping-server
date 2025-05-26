from models.team import TeamModel
from typing import Dict

from models.zones.zones_config import ZoneData

# Zone Matchup Mapping: Attacking zone vs Opponent defensive zone
ZONE_MATCHUPS = {
    # Wide
    "attLeftWide": "defRightWide",
    "attRightWide": "defLeftWide",

    # Half-Spaces
    "attLeftHalf": "defRightHalf",
    "attRightHalf": "defLeftHalf",

    # Central Attack
    "attCentral": "defCentral",

    # Midfield
    "midLeftWide": "midRightWide",
    "midLeftHalf": "midRightHalf",
    "midCentral": "midCentral",
    "midRightHalf": "midLeftHalf",
    "midRightWide": "midLeftWide",

    # Defensive Build-Up vs Press Zones
    "defLeftWide": "attRightWide",
    "defLeftHalf": "attRightHalf",
    "defCentral": "attCentral",
    "defRightHalf": "attLeftHalf",
    "defRightWide": "attLeftWide",
}
ZONE_IMPORTANCE = {
    "attCentral": 1.4,
    "attLeftHalf": 1.2,
    "attRightHalf": 1.2,
    "attLeftWide": 1.0,
    "attRightWide": 1.0,
    "midCentral": 1.0,
    "midLeftHalf": 0.8,
    "midRightHalf": 0.8,
    "midLeftWide": 0.6,
    "midRightWide": 0.6,
    "defCentral": 1.1,
    "defLeftHalf": 0.9,
    "defRightHalf": 0.9,
    "defLeftWide": 0.7,
    "defRightWide": 0.7,
}
class MatchPredictionService:
    def __init__(self, team_a: TeamModel, team_b: TeamModel):
        self.team_a = team_a
        self.team_b = team_b

    def predict(self) -> Dict:
        raw_xg_a = self.compute_expected_goals(self.team_a, self.team_b)
        raw_xg_b = self.compute_expected_goals(self.team_b, self.team_a)
        raw_xg_a = self.compute_expected_goals(self.team_a, self.team_b)
        raw_xg_b = self.compute_expected_goals(self.team_b, self.team_a)

        # 2. Global zone strength 
        sum_a = sum(z.rating for z in self.team_a.zones.values())
        sum_b = sum(z.rating for z in self.team_b.zones.values())
        total = sum_a + sum_b or 1.0 

        # 3. Scale final xG using total zone strength ratio 
        scale_a = sum_a / total
        scale_b = sum_b / total

        xg_a = round(raw_xg_a * scale_a * 2, 2)  # tune the multiplier if needed
        xg_b = round(raw_xg_b * scale_b * 2, 2)
        
        return {
            "team_a": self.team_a.name,
            "team_b": self.team_b.name,
            "score_prediction": f"{xg_a:.1f} - {xg_b:.1f}",
            "xg": {
                self.team_a.name: xg_a,
                self.team_b.name: xg_b
            },
            "matchups": self.get_zone_matchups()
        }

    def compute_expected_goals(self, attacker: TeamModel, defender: TeamModel) -> float:
        total = 0.0
        for att_zone_id, def_zone_id in ZONE_MATCHUPS.items():
            att_zone = attacker.zones.get(att_zone_id)
            def_zone = defender.zones.get(def_zone_id)

            if not att_zone or not def_zone:
                continue

            # Normalize ratings into 0–1 range
            att_rating = min(att_zone.rating + self._player_boost(att_zone), 100) / 100.0
            def_rating = min(def_zone.rating, 100) / 100.0

            delta = att_rating - def_rating
            weight = ZONE_IMPORTANCE.get(att_zone_id, 1.0)
            xg = self._scale_rating_to_xg(delta) * weight
            total += xg

            print(f"[{att_zone_id}] att: {att_rating:.2f}, def: {def_rating:.2f}, delta: {delta:.2f}, xG: {xg:.2f}")

        return round(total, 2)

    def _player_boost(self, zone: ZoneData) -> float:
        players = zone.breakdown.players.contributions
        if not players:
            return 0.0
        weighted_sum = sum(p.rating * p.position_weight for p in players)
        total_weight = sum(p.position_weight for p in players)
        if total_weight == 0:
            return 0.0
        boost = (weighted_sum / total_weight) * 0.1  # Tune this weight
        return round(boost, 3)

    def _scale_rating_to_xg(self, delta: float) -> float:
        if delta <= 0:
            return 0.0

        # Amplify separation for top teams
        delta = min(delta, 1.5)

        # Linear base with soft non-linearity
        xg = (delta ** 1.2) * 0.9  # was 1.4 * 0.6
        return round(xg, 2)

    def get_zone_matchups(self) -> Dict[str, str]:
        output = {}
        for att_zone_id, def_zone_id in ZONE_MATCHUPS.items():
            a = self.team_a.zones.get(att_zone_id)
            b = self.team_b.zones.get(def_zone_id)

            if not a or not b:
                output[att_zone_id] = "missing"
                continue

            # Add player boost (optional but useful)
            att_rating = min(a.rating + self._player_boost(a), 100) / 100.0
            def_rating = min(b.rating, 100) / 100.0
            raw_delta = att_rating - def_rating

            # Clamp delta for matchup label
            clamped_delta = round(min(max(raw_delta, -1.5), 1.5), 2)

            # Decide outcome label
            if clamped_delta > 0.2:
                output[att_zone_id] = f"{self.team_a.name} advantage ({clamped_delta})"
            elif clamped_delta < -0.2:
                output[att_zone_id] = f"{self.team_b.name} advantage ({abs(clamped_delta)})"
            else:
                output[att_zone_id] = "even"

        return output
