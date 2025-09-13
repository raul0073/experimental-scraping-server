from fastapi import APIRouter, HTTPException
from typing import Optional
from fastapi.params import Query
from fastapi.responses import JSONResponse
from matplotlib.pylab import mean
import numpy as np
from routes.fbref.players.normalize import sanitize_for_json
from routes.fbref.utils.mental_route_utils import build_team_meta, normalize_mental_scores, pick_best_xi
from services.fbref.loader import FBRefLoaderService
from services.mental.mental_service import MentalRankingService
from services.plotting.player.plotting_service_player import PlayerPlottingService
from services.plotting.team.team_plotting_service import TeamPlottingService

router = APIRouter(prefix="/mental", tags=["Mental Ranking"])


# get by league
@router.get("/{league}/{season}/all")
def get_league_mental_scores(league: str, season: int):
    # 1️ Load players
    players = FBRefLoaderService.load_all_players(league, season)
    if not players:
        raise HTTPException(status_code=404, detail="No players found for league/season")

    # 2️ Compute mental scores
    ranked_players = MentalRankingService(players).score_team_players()
    filtered_players = [p for p in ranked_players if p.get("mental", {}).get("m_raw") is not None]
    if not filtered_players:
        raise HTTPException(status_code=404, detail="No mental scores found for league/season")

    normalize_mental_scores(filtered_players)
    filtered_players.sort(key=lambda p: p["mental"]["m"], reverse=True)

    # 3️ Top players
    top_players = filtered_players[:100]

    # 4️ Teams meta
    teams_sorted = build_team_meta(filtered_players, league, season)

    # 5️ Best XI
    best_xi = pick_best_xi(filtered_players)
 
    # 6️ League meta
    league_meta = {
        "league": league,
        "season": season,
        "teams_count": len(teams_sorted),
        "players_count": len(filtered_players),
        "avg_m": round(mean([p["mental"]["m"] for p in filtered_players]), 2),
        "spread_m": round(max([p["mental"]["m"] for p in filtered_players]) - min([p["mental"]["m"] for p in filtered_players]), 2),
        "top_player": top_players[0]["name"] if top_players else None,
    }

    # 7️ Teams stats
    team_stats = FBRefLoaderService.load_teams_stats(league, season)

    return JSONResponse(sanitize_for_json({
        "league_meta": league_meta,
        "players": top_players,
        "teams": {
            "mental": teams_sorted,
            "stats": team_stats
        },
        "best_eleven": best_xi
       }),  headers={"Content-Encoding": "identity"})


# get all 5 leagues
@router.get("/all")
async def get_all_players_and_teams():
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
    # Best XI
    best_xi = pick_best_xi(top_players)

    league_stats= FBRefLoaderService.load_all_leagues_stats(2425)
    top_players = top_players[:100]
    # Final response
    return JSONResponse(sanitize_for_json({
        "players": top_players,
        "teams": {
            "mental": teams_sorted,
            "stats": league_stats
        },
        "best_eleven": best_xi
    }),  headers={"Content-Encoding": "identity"})

@router.get("/{league}/{season}/{team}")
async def get_team_mental_scores(league: str, season: int, team: str):
    # --- Load team players ---
    team_data = FBRefLoaderService.load_team_players(league, season, team)
    if not team_data:
        raise HTTPException(status_code=404, detail="Team data not found")

    # --- Compute mental scores ---
    scored_players = MentalRankingService(team_data).score_team_players()
    filtered_players = [
        p for p in scored_players
        if p.get("mental", {}).get("m_raw") is not None
        and np.isfinite(p.get("mental", {}).get("m_raw", float("nan")))
    ]
    if not filtered_players:
        raise HTTPException(status_code=404, detail="No mental scores found for this team")

    # --- Sort descending by league-wide percentile 'm' ---
    filtered_players.sort(key=lambda p: p["mental"]["m"], reverse=True)

    # --- Best XI ---
    best_xi = pick_best_xi(filtered_players)

    # --- Team mental summary ---
    team_mental = {
        "avg_m": round(mean([p["mental"]["m"] for p in filtered_players]), 2),
        "count_players": len(filtered_players),
        "leader": {
            "player": filtered_players[0]["name"],
            "m": filtered_players[0]["mental"]["m"],
        },
        "weakest": {
            "player": filtered_players[-1]["name"],
            "m": filtered_players[-1]["mental"]["m"],
        },
    }

    # --- Team-scaled m for charts (0–100) ---
    raw_scores = [p["mental"]["m"] for p in filtered_players]
    min_m, max_m = min(raw_scores), max(raw_scores)
    spread = max_m - min_m or 1e-9
    for p in filtered_players:
        p["mental"]["m_team_scaled"] = round((p["mental"]["m"] - min_m) / spread * 100)

    # --- Load all team stats ONCE ---
    all_team_stats = FBRefLoaderService.load_teams_stats(league, season)
    team_stats = FBRefLoaderService.filter_stats_by_team(all_team_stats, team)

    # --- Instantiate plotting service ONCE ---
    plotter = TeamPlottingService(league, season, team)
    team_charts_data = await plotter.get_team_default_chart()
    heatmaps = await plotter.get_team_heatmaps()

    # --- Return ---
    return JSONResponse(
        sanitize_for_json({
            "players": filtered_players,
            "stats": {
                "mental": team_mental,
                "stats": team_stats,
            },
            "best_eleven": best_xi,
            "plot": {
                "default": team_charts_data,
                "heatmap": {
                            "attacking": heatmaps["attacking"],
                            "defending": heatmaps["defending"]},
            },
        }),
        headers={"Content-Encoding": "identity"},
    )

# get by tname or role.
@router.get("/vv/players/{league}/{season}")
def get_players_by_role_or_name(
    league: str,
    season: int,
    name: Optional[str] = Query(None, description="Filter players by name"),
    role: Optional[str] = Query(None, description="Filter players by role"),
    top_k: Optional[int] = Query(None, description="Limit number of players returned"),
):
    print(f"[DEBUG] Fetching players for league={league}, season={season}, name={name}, role={role}")

    # Load all players
    players = FBRefLoaderService.load_all_players(league, season)
    if not players:
        raise HTTPException(status_code=404, detail="No players found")

    # Score mentally
    scored_players = MentalRankingService(players).score_team_players()

    # Role filter
    if role:
        before = len(scored_players)
        scored_players = [p for p in scored_players if p.get("role") == role]

    # Name filter (partial match)
    if name:
        name_norm = name.lower().strip()
        before = len(scored_players)
        scored_players = [p for p in scored_players if name_norm in (p.get("name") or "").lower()]

    if not scored_players:
        raise HTTPException(status_code=404, detail="No matching players found")

    # Sort by mental score
    scored_players.sort(key=lambda p: p.get("mental", {}).get("m", 0), reverse=True)

    # Limit
    if top_k:
        scored_players = scored_players[:top_k]

    return JSONResponse(sanitize_for_json({
        "league": league,
        "season": season,
        "role": role,
        "name_query": name,
        "count": len(scored_players),
        "players": scored_players,
    }), headers={"Content-Encoding": "identity"})


@router.get("/vv/players/{league}/{season}/plot")
def get_player_plot(
    league: str,
    season: int,
    name: str = Query(..., description="Exact player name for plotting"),
):
    print(f"[DEBUG] Generating plot for league={league}, season={season}, name={name}")

    # Load all players
    players = FBRefLoaderService.load_all_players(league, season)
    if not players:
        raise HTTPException(status_code=404, detail="No players found")

    # Score mentally
    scored_players = MentalRankingService(players).score_team_players()

    # Find exact match
    match = next((p for p in scored_players if (p.get("name") or "").lower() == name.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"No exact match for player {name}")

    # Generate pizza
    service = PlayerPlottingService(players)
    img_base64 = service.plot_player_pizza(match)

    return JSONResponse(sanitize_for_json({
        "league": league,
        "season": season,
        "player": match.get("name"),
        "plot": img_base64,
    }), headers={"Content-Encoding": "identity"})