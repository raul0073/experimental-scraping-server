from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.zones.zones_config import (
    TURNOVER_ACTIONS,
    ZONE_LABELS,
    ZONES,
    shot_lane,
)
from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name
from services.understat.shot_events_service import ShotEventsService
from services.understat.understat_service import UnderstatService

log = logging.getLogger(__name__)

DATA_DIR = Path("data/zones")


def zone_advantage(zones: Dict[str, Any], home: str, away: str):
    """Importance-weighted matchup delta sum per side (used by the calibrated
    lambda blend and its calibration script)."""
    from models.zones.zones_config import ZONE_IMPORTANCE, ZONE_MATCHUPS
    if home not in zones or away not in zones:
        return None
    zh, za = zones[home], zones[away]
    adv_h = sum(ZONE_IMPORTANCE.get(a, 1.0) * (zh[a]["rating"] - za[d]["rating"]) / 100.0
                for a, d in ZONE_MATCHUPS.items())
    adv_a = sum(ZONE_IMPORTANCE.get(a, 1.0) * (za[a]["rating"] - zh[d]["rating"]) / 100.0
                for a, d in ZONE_MATCHUPS.items())
    return adv_h, adv_a

# v3 component weights per band (players optional — weights renormalize).
# NOTE: fbref defensive-volume basics (TklW+Int) were removed after the Stage 4
# gate showed they correlate POSITIVELY with goals conceded (bad teams defend
# more) — volume is not quality. The v2 per-flank "wide" cross signal is gone
# with the wide lanes (no data source resolves crosses by flank).
BAND_WEIGHTS = {
    "att": {"production": 0.55, "players": 0.45},
    "def": {"concession": 0.75, "players": 0.25},
    "mid": {"control": 0.70, "players": 0.30},  # per-zone 'control' comp differs
}
MATCH_DECAY = 0.985  # per-match recency decay
PUNISHED_TURNOVER_WEIGHT = 0.5  # extra pain for conceding off own turnovers
LANE_SHRINKAGE = 0.35  # anchor low-volume lanes toward overall team quality

# defender's zone attacked when the shooter's lane is X (mirror)
_MIRROR_LANE = {"Left": "Right", "Central": "Central", "Right": "Left"}


class ZonesEngine:
    """Computes 0-100 zone ratings per team from a rolling, time-decayed
    window of matches. All inputs are reproducible post-Opta sources:
    shot events (locations + lastAction), PPDA/deep completions, fbref basics.
    """

    def __init__(self, league: str, season: str):
        self.league = league
        self.season = season

    def build(self, as_of_date: Optional[str] = None, window: int = 38,
              persist: bool = True, include_players: bool = True) -> Dict[str, Any]:
        shots_data = ShotEventsService.load(self.league, self.season)
        us_data = UnderstatService.load(self.league, self.season)
        if not shots_data or not shots_data.get("matches"):
            raise RuntimeError(f"No shot events on disk for {self.league} {self.season}")
        if not us_data:
            raise RuntimeError(f"No understat match data for {self.league} {self.season}")

        team_matches = self._collect_team_matches(shots_data, us_data, as_of_date, window)
        if not team_matches:
            raise RuntimeError("No matches in window")

        raw: Dict[str, Dict[str, Dict[str, float]]] = {}
        for team, matches in team_matches.items():
            raw[team] = self._team_raw_components(matches)

        player_scores = None
        if include_players:
            from services.zones.player_layer import PlayerLayer
            player_scores = PlayerLayer.team_band_scores(self.league, self.season)
            # NOTE: season-cumulative player stats — fine live, but backtest
            # calibration passes include_players=False to stay walk-forward-clean.

        ratings = self._normalize(raw, player_scores)
        payload = {
            "league": self.league,
            "season": self.season,
            "as_of": as_of_date or "latest",
            "window": window,
            "team_count": len(ratings),
            "teams": ratings,
        }
        if persist:
            out_dir = DATA_DIR / _safe_name(self.league) / self.season
            _atomic_write_json(out_dir / f"{as_of_date or 'latest'}.json", payload)
            if as_of_date:
                _atomic_write_json(out_dir / "latest.json", payload)
        return payload

    # ------------------------------------------------ inputs

    def _collect_team_matches(self, shots_data, us_data, as_of_date, window):
        """Per team: last `window` matches before as_of_date, newest first,
        each with own/conceded shots and match-level control stats."""
        us_by_key = {(m["date"], m["home_team"], m["away_team"]): m
                     for m in us_data["matches"]}
        per_team: Dict[str, List[Dict]] = {}
        rows = sorted(shots_data["matches"].values(), key=lambda m: m["date"], reverse=True)
        for m in rows:
            if as_of_date and m["date"] >= as_of_date:
                continue
            us = us_by_key.get((m["date"], m["home_team"], m["away_team"]), {})
            for side, team, opp in (("h", m["home_team"], m["away_team"]),
                                    ("a", m["away_team"], m["home_team"])):
                lst = per_team.setdefault(team, [])
                if len(lst) >= window:
                    continue
                pre = "home" if side == "h" else "away"
                pre_opp = "away" if side == "h" else "home"
                lst.append({
                    "shots_for": [s for s in m["shots"] if s["side"] == side],
                    "shots_against": [s for s in m["shots"] if s["side"] != side],
                    "ppda": us.get(f"{pre}_ppda"),
                    "deep_for": us.get(f"{pre}_deep"),
                    "deep_against": us.get(f"{pre_opp}_deep"),
                })
        return per_team

    # ------------------------------------------------ raw components

    def _team_raw_components(self, matches: List[Dict]) -> Dict[str, Dict[str, float]]:
        """Decay-weighted per-match averages of every zone component."""
        comp: Dict[str, Dict[str, float]] = {z: {} for z in ZONES}
        w_total = 0.0
        acc: Dict[str, float] = {}

        for i, m in enumerate(matches):  # newest first
            w = MATCH_DECAY ** i
            w_total += w

            for s in m["shots_for"]:
                if s["xg"] is None or s["y"] is None:
                    continue
                lane = shot_lane(s["y"])
                acc[f"att{lane}:xg"] = acc.get(f"att{lane}:xg", 0.0) + w * s["xg"]
                acc["att:total"] = acc.get("att:total", 0.0) + w * s["xg"]

            for s in m["shots_against"]:
                if s["xg"] is None or s["y"] is None:
                    continue
                dz_lane = _MIRROR_LANE[shot_lane(s["y"])]
                key = f"def{dz_lane}:xga"
                pain = s["xg"]
                if s.get("last_action") in TURNOVER_ACTIONS:
                    pain += PUNISHED_TURNOVER_WEIGHT * s["xg"]
                    # turnovers we GIFT into shots — a screen failure
                    acc["mid:turnover_conceded"] = \
                        acc.get("mid:turnover_conceded", 0.0) + w * s["xg"]
                acc[key] = acc.get(key, 0.0) + w * pain
                acc["def:total"] = acc.get("def:total", 0.0) + w * pain

            # turnovers we CONVERT into shots — pressing yield
            for s in m["shots_for"]:
                if s.get("last_action") in TURNOVER_ACTIONS and s["xg"] is not None:
                    acc["mid:turnover_won"] = acc.get("mid:turnover_won", 0.0) + w * s["xg"]

            if m["ppda"] is not None:
                acc["mid:ppda"] = acc.get("mid:ppda", 0.0) + w * m["ppda"]
            if m["deep_for"] is not None:
                acc["mid:deep_for"] = acc.get("mid:deep_for", 0.0) + w * (m["deep_for"] or 0)
            if m["deep_against"] is not None:
                acc["mid:deep_against"] = acc.get("mid:deep_against", 0.0) + w * (m["deep_against"] or 0)

        for k, v in acc.items():
            acc[k] = v / w_total if w_total else 0.0

        # shrink each lane toward the team's MEAN LANE (total/3): the lane
        # signal stays primary, the anchor stabilizes low-volume lanes
        att_anchor = acc.get("att:total", 0.0) / 3.0
        def_anchor = acc.get("def:total", 0.0) / 3.0
        for lane in ("Left", "Central", "Right"):
            comp[f"att{lane}"]["production"] = (
                acc.get(f"att{lane}:xg", 0.0) + LANE_SHRINKAGE * att_anchor)
            comp[f"def{lane}"]["concession"] = -(
                acc.get(f"def{lane}:xga", 0.0) + LANE_SHRINKAGE * def_anchor)
        # midfield by FUNCTION — three separately-measured duel zones
        comp["midProgress"]["control"] = acc.get("mid:deep_for", 0.0)
        comp["midPress"]["control"] = (-acc.get("mid:ppda", 0.0)) \
            + 3.0 * acc.get("mid:turnover_won", 0.0)
        comp["midShield"]["control"] = -acc.get("mid:deep_against", 0.0) \
            - 3.0 * acc.get("mid:turnover_conceded", 0.0)
        return comp

    # ------------------------------------------------ normalize + blend

    def _normalize(self, raw: Dict[str, Dict],
                   player_scores: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Any]:
        teams = [t for t in raw if not t.startswith("_")]
        result: Dict[str, Any] = {t: {} for t in teams}

        def pct(values: Dict[str, float]) -> Dict[str, float]:
            ordered = sorted(values.items(), key=lambda kv: kv[1])
            n = len(ordered)
            return {t: (100.0 if n == 1 else round(i / (n - 1) * 100, 2))
                    for i, (t, _) in enumerate(ordered)}

        def player_band_values(band: str) -> Optional[Dict[str, float]]:
            if not player_scores:
                return None
            vals = [s.get(band) for s in player_scores.values() if s.get(band)]
            if not vals:
                return None
            covered = sum(1 for t in teams if t in player_scores)
            if covered < 0.8 * len(teams):
                return None
            median = sorted(vals)[len(vals) // 2]
            return {t: player_scores.get(t, {}).get(band, median) for t in teams}

        for zone in ZONES:
            band = "mid" if zone == "mid" else zone[:3]
            weights = dict(BAND_WEIGHTS[band])
            players_vals = player_band_values(band) if band in ("att", "mid") else None
            if players_vals is None:
                weights.pop("players", None)
            wsum = sum(weights.values())

            comp_pcts: Dict[str, Dict[str, float]] = {}
            for cname in weights:
                if cname == "players":
                    comp_pcts[cname] = pct(players_vals)
                else:
                    comp_pcts[cname] = pct({t: raw[t][zone].get(cname, 0.0) for t in teams})

            for t in teams:
                score = sum(comp_pcts[c][t] * w for c, w in weights.items()) / wsum
                result[t][zone] = {
                    "rating": round(score, 2),
                    "label": ZONE_LABELS[zone],
                    "components": {c: comp_pcts[c][t] for c in weights},
                }
        return result
