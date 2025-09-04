from fastapi import APIRouter, HTTPException
from typing import List, Optional

from fastapi.responses import JSONResponse
import numpy as np

from routes.fbref.players.normalize import sanitize_for_json
from services.fbref.loader import FBRefLoaderService
from services.fbref.player.player_service import FBRefPlayerService
from services.mental.best_11_service import BestXIBuilder
from services.mental.mental_service import MentalRankingService

router = APIRouter(prefix="/mental", tags=["Mental Ranking"])


# get by league
@router.get("/{league}/{season}/all")
def get_league_mental_scores(league: str, season: int):
    # Load raw players
    players = FBRefLoaderService.load_all_players(league, season)
    if not players:
        raise HTTPException(status_code=404, detail="No players found for league/season")

    # Score them
    ranked = MentalRankingService(players).score_team_players()
    filtered = [p for p in ranked if p.get("mental", {}).get("m_raw") is not None]
    filtered.sort(key=lambda p: p["mental"]["m"], reverse=True)

    # Top 50 players
    top_players = filtered[:100]

    # League meta
    league_meta = {
        "league": league,
        "season": season,
        "teams_count": len(set(p["__meta__"]["team"] for p in filtered)),
        "players_count": len(filtered),
        "avg_m": round(sum(p["mental"]["m"] for p in filtered) / len(filtered), 2),
        "spread_m": round(
            max(p["mental"]["m"] for p in filtered) - min(p["mental"]["m"] for p in filtered),
            2,
        ),
        "top_player": top_players[0]["name"] if top_players else None,
    }

    # Best XI squad
    best_eleven = BestXIBuilder(filtered).build()

    return JSONResponse(sanitize_for_json({
        "league_meta": league_meta,
        "players": top_players,
        "best_eleven": best_eleven,
    }))

# get by team
@router.get("/{league}/{season}/{team}")
def get_team_mental_scores(league: str, season: int, team: str):
    players = FBRefLoaderService.load_team_players(league, season, team)
    if not players:
        raise HTTPException(status_code=404, detail="Team data not found")

    scored = MentalRankingService(players).score_team_players()

    players = [p for p in scored if p.get("mental", {}).get("m_raw") is not None]
    players.sort(key=lambda p: p["mental"]["m"], reverse=True)

    top_50 = players[:50]
    return JSONResponse(sanitize_for_json(top_50))


@router.get("/all")
def get_all_players_and_teams():
    import json
    from statistics import mean
    from math import isfinite
    from collections import defaultdict

    all_players = []
    team_grouped: dict[str, list] = {}
    team_meta: dict[str, dict] = {}

    team_paths = FBRefLoaderService.list_available_league_team_paths()

    for item in team_paths:
        league = item["league"]
        team = item["team"]
        path = item["path"]

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            if not isinstance(raw, dict) or "players" not in raw:
                continue

            players = raw["players"]
            players = [p for p in players if isinstance(p, dict) and "name" in p]
            if not players:
                continue

            scored = MentalRankingService(players).score_team_players()
            filtered = [p for p in scored if p.get("mental", {}).get("m_raw") is not None]

            for p in filtered:
                p.setdefault("league", league)
                p.setdefault("team", team)

            all_players.extend(filtered)
            team_grouped[f"{league}:{team}"] = filtered

        except Exception as e:
            print(f"[ERROR] Failed to load {path}: {e}")
            continue

    if not all_players:
        raise HTTPException(status_code=404, detail="No mental scores found")

    # 🔥 Normalize
    raw_scores = [p["mental"]["m_raw"] for p in all_players if isfinite(p["mental"]["m_raw"])]
    if raw_scores:
        min_m = min(raw_scores)
        max_m = max(raw_scores)
        spread = max_m - min_m or 1e-9
        for p in all_players:
            raw = p["mental"]["m_raw"]
            norm = (raw - min_m) / spread
            p["mental"]["m"] = round(norm * 100)

    # 🔥 Top Players
    top_players = sorted(all_players, key=lambda p: p["mental"]["m"], reverse=True)
    top_50 = top_players[:100]

#  Rebuild team_grouped from normalized players
    team_grouped = defaultdict(list)
    for p in all_players:
        key = f"{p['league']}:{p['team']}"
        team_grouped[key].append(p)

    #  Team Meta after normalized m
    team_meta = {}
    for key, team_players in team_grouped.items():
        league, team = key.split(":")
        # keep only finite numbers
        scores = [p["mental"]["m"] for p in team_players if isfinite(p["mental"].get("m", 0))]
        if not scores:
            continue

        # --- robust spread: IQR (Q75 - Q25), fallback to max-min if too few players ---
        if len(scores) >= 4:
            q75, q25 = np.percentile(scores, [75, 25])
            spread_val = q75 - q25
        else:
            spread_val = (max(scores) - min(scores)) if len(scores) >= 2 else 0.0
        # ------------------------------------------------------------------------------

        team_meta[key] = {
            "league": league,
            "team": team,
            "season": 2425,
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


    teams_sorted = sorted(team_meta.values(), key=lambda t: t["avg_m"], reverse=True)

    best_11 = BestXIBuilder(top_players).build()
    print(f"Best XI: {best_11}")
    print(f"teams : {teams_sorted}")
    # Final response
    return JSONResponse(sanitize_for_json({
        "players": top_50,
        "teams": teams_sorted,
        "best_eleven": best_11,
    }))




@router.get("/{league}/{season}/role/{role}")
def get_players_by_role(
    league: str,
    season: int,
    role: str,
    top_k: Optional[int] = None,
):
    # Load all players in the league
    players = FBRefLoaderService.load_all_players(league, season)
    if not players:
        raise HTTPException(status_code=404, detail="No players found")

    # Score them mentally
    scored = MentalRankingService(players).score_team_players()

    # Filter players by role and valid mental scores
    filtered = [
        p for p in scored
        if p.get("role") == role and p.get("mental", {}).get("m_raw") is not None
    ]

    # Sort by mental score
    filtered.sort(key=lambda p: p["mental"]["m"], reverse=True)

    # Slice top_k if provided
    if top_k:
        filtered = filtered[:top_k]

    return JSONResponse(sanitize_for_json({
        "role": role,
        "players": filtered,
        "count": len(filtered),
    }))