# -------------------- UTILS --------------------
from typing import List, Dict
from collections import defaultdict
from statistics import mean
from math import isfinite
import numpy as np

from services.mental.best_11_service import FORMATIONS, LINES, BestXIBuilder


def normalize_mental_scores(players: List[Dict]) -> None:
    """Attach 'm' (normalized 0-100) based on 'm_raw'."""
    raw_scores = [p["mental"]["m_raw"] for p in players if isfinite(p["mental"]["m_raw"])]
    min_m, max_m = min(raw_scores), max(raw_scores)
    spread = max_m - min_m or 1e-9
    for p in players:
        raw = p["mental"]["m_raw"]
        p["mental"]["m"] = round((raw - min_m) / spread * 100)


def build_team_meta(players: List[Dict], league: str, season: int) -> List[Dict]:
    """Compute average, spread, leaders, weakest player per team."""
    team_grouped = defaultdict(list)
    for p in players:
        key = p.get("__meta__", {}).get("team") or p.get("team")
        if key:
            team_grouped[key].append(p)

    team_meta = {}
    for team, team_players in team_grouped.items():
        scores = [p["mental"]["m"] for p in team_players if isfinite(p["mental"].get("m", 0))]
        if not scores:
            continue

        # Spread: IQR if enough players, else max-min
        if len(scores) >= 4:
            q75, q25 = np.percentile(scores, [75, 25])
            spread_val = q75 - q25
        else:
            spread_val = (max(scores) - min(scores)) if len(scores) >= 2 else 0.0

        team_meta[team] = {
            "league": league,
            "team": team,
            "season": season,
            "avg_m": round(mean(scores), 2),
            "spread_m": round(float(spread_val), 2),
            "count_players": len(scores),
            "leader": {
                "player": max(team_players, key=lambda p: p["mental"]["m"])["name"],
                "m": round(max(scores))
            },
            "weakest": {
                "player": min(team_players, key=lambda p: p["mental"]["m"])["name"],
                "m": round(min(scores))
            }
        }

    return sorted(team_meta.values(), key=lambda t: t["avg_m"], reverse=True)


def pick_best_xi(players: List[Dict]) -> Dict:
    """
    Return:
      - top 3 formations by mental score (with starting 11 and subs)
      - best performing eleven based on 'ranking.performance' across all players
    """
    # Log top players per role for debug
    BestXIBuilder.log_top_players_per_role(players, top_n=10)

    builder = BestXIBuilder(players)
    top_formations_raw = builder.build_best_formations(top_n=3)

    # Minimal player dict helper
    def minimal_player(p: Dict) -> Dict:
        return {
            "name": p.get("name", ""),
            "position": p.get("position", ""),
            "age": p.get("age", ""),
            "position_text": p.get("position_text", ""),
            "role": p.get("role", ""),
            "mental": p.get("mental", {"m": 0, "m_raw": 0}),
            "performance": p.get("ranking", {"performance": 0}),
            "league": p.get("league", ""),
            "team": p.get("team", ""),
            "profile_img": p.get("profile_img", ""),
            "foot": p.get("foot", ""),
        }

    # Build top formations with minimal player data
    top_formations = []
    for formation in top_formations_raw:
        used_names = {p["name"] for p in formation["starting_11"]}
        remaining_players = [p for p in players if p["name"] not in used_names]
        remaining_players.sort(key=lambda p: p.get("mental", {}).get("m_raw", 0), reverse=True)
        subs = remaining_players[:7]

        top_formations.append({
            "formation": formation["name"],
            "score": formation["score"],
            "best_eleven": [minimal_player(p) for p in formation["starting_11"]],
            "subs": [minimal_player(p) for p in subs],
        })

    # Build best performing eleven using the same builder/formation logic
    formation_name = "433"  # or pick a default formation you prefer
    used_names = set()
    starting_11_perf = []

    for line_name, formation_line in FORMATIONS[formation_name].items():
        line_def = LINES[line_name]
        starting_11_perf.extend(
            builder._pick_line(line_def, formation_line, used_names, key_type="performance")
        )

    # Pick top 7 subs by performance
    remaining_players_perf = [p for p in players if p["name"] not in used_names]
    remaining_players_perf.sort(
        key=lambda p: float(p.get("ranking", {}).get("performance", "-inf")),
        reverse=True
    )
    subs_perf = remaining_players_perf[:7]

    best_performing_eleven = {
        "formation": formation_name,
        "score": sum(float(p.get("ranking", {}).get("performance", 0)) for p in starting_11_perf),
        "best_eleven": [minimal_player(p) for p in starting_11_perf],
        "subs": [minimal_player(p) for p in subs_perf],
    }

    return {
        "top_formations": top_formations,
        "best_performing_eleven": best_performing_eleven,
    }