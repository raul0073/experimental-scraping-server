import base64
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from openai import BaseModel

from models.mental.mental_categories import TEAM_MENTAL_MAPPING
from services.fbref.loader import FBRefLoaderService
from services.plotting.team.team_plotting_service import TeamPlottingService


router = APIRouter(prefix="/plot", tags=["Plotting Route"])
class MetricsPayload(BaseModel):
    metrics: Dict[str, List[str]] 
# -------------------------
# Team-level chart with metrics payload
# -------------------------
@router.post("/{league}/{season}/{team}/{chart_type}")
async def get_team_chart_data(
    league: str,
    season: int,
    team: str,
    chart_type: str,
    payload: MetricsPayload
):
    metrics = payload.metrics
    if not metrics:
        raise HTTPException(status_code=400, detail="No metrics provided in payload")

    teams_stats_raw = FBRefLoaderService.load_teams_stats(league, season)
    results = {}

    for stat_type, keys in metrics.items():
        if not keys:
            raise HTTPException(status_code=400, detail=f"No keys provided for stat_type: {stat_type}")

        team_stat_list = teams_stats_raw.get(stat_type, [])
        if not team_stat_list:
            continue

        # Map each metric to its ranked list
        rank_mapping = {}
        for k in keys:
            ranked_teams = sorted(
                [t for t in team_stat_list if t.get("metrics", {}).get(k)],
                key=lambda t: t["metrics"][k]["rank"]
            )
            rank_mapping[k] = ranked_teams

        team_entry = next((t for t in team_stat_list if t.get("team", "").lower() == team.lower()), {})
        team_metrics = team_entry.get("metrics", {})

        data_for_keys = {}

        for k in keys:
            team_val = team_metrics.get(k, {}).get("value", 0)
            team_rank = team_metrics.get(k, {}).get("rank", None)

            league_best_team_entry = rank_mapping[k][0] if rank_mapping[k] else {}
            best_team_name = league_best_team_entry.get("team", "")
            best_value = league_best_team_entry.get("metrics", {}).get(k, {}).get("value", 0)

            # Rank-based normalization: 100 = best, 0 = worst
            num_teams = len(rank_mapping[k])
            normalized = 0
            if team_rank and num_teams > 1:
                normalized = round((num_teams - team_rank) / (num_teams - 1) * 100, 2)
            elif team_rank:
                normalized = 100.0

            data_for_keys[k] = {
                "team_value": team_val,
                "normalized": normalized,
                "team_rank": team_rank,
                "league_best_value": best_value,
                "league_best_team": best_team_name
            }

        results[stat_type] = data_for_keys

    return {
        "league": league,
        "season": season,
        "team": team,
        "chart_type": chart_type,
        "data": results,
        "metrics": metrics
    }

@router.post("/{league}/{season}/{team}/{chart_type}")
async def get_team_chart_data(
    league: str,
    season: int,
    team: str,
    chart_type: str,
    payload: MetricsPayload
):
    metrics = payload.metrics
    if not metrics:
        raise HTTPException(status_code=400, detail="No metrics provided in payload")

    teams_stats_raw = FBRefLoaderService.load_teams_stats(league, season)
    results = {}

    for stat_type, keys in metrics.items():
        if not keys:
            raise HTTPException(status_code=400, detail=f"No keys provided for stat_type: {stat_type}")

        # Radar constraints
        if chart_type == "radar":
            if len(keys) < 5 or len(keys) > 8:
                raise HTTPException(
                    status_code=400,
                    detail=f"Radar chart requires 5–8 metrics per stat_type. Got {len(keys)} for {stat_type}"
                )

        team_stat_list = teams_stats_raw.get(stat_type, [])
        if not team_stat_list:
            continue

        # Rank mapping for each key
        rank_mapping = {}
        for k in keys:
            ranked_teams = sorted(
                [t for t in team_stat_list if t.get("metrics", {}).get(k)],
                key=lambda t: t["metrics"][k]["rank"]
            )
            rank_mapping[k] = ranked_teams

        team_entry = next((t for t in team_stat_list if t.get("team", "").lower() == team.lower()), {})
        team_metrics = team_entry.get("metrics", {})

        data_for_keys = {}

        for k in keys:
            team_val = team_metrics.get(k, {}).get("value", 0)
            team_rank = team_metrics.get(k, {}).get("rank", None)

            league_best_team_entry = rank_mapping[k][0] if rank_mapping[k] else {}
            best_team_name = league_best_team_entry.get("team", "")
            best_value = league_best_team_entry.get("metrics", {}).get(k, {}).get("value", 0)
            best_rank = league_best_team_entry.get("metrics", {}).get(k, {}).get("rank", 1)

            num_teams = len(rank_mapping[k])
            team_normalized = 100.0 if team_rank == 1 else round((num_teams - team_rank) / (num_teams - 1) * 100, 2) if team_rank else 0
            league_normalized = 100.0  # league-best is always 100

            data_for_keys[k] = {
                "team_value": team_val,
                "team_normalized": team_normalized,
                "team_rank": team_rank,
                "league_best_value": best_value,
                "league_best_team": best_team_name,
                "league_normalized": league_normalized
            }

        results[stat_type] = data_for_keys

    return {
        "league": league,
        "season": season,
        "team": team,
        "chart_type": chart_type,
        "data": results,
        "metrics": metrics
    }

@router.post("/{league}/{season}/{team}")
async def get_team_default_chart(league: str, season: int, team: str):
    # Load all team stats
    all_team_stats = FBRefLoaderService.load_teams_stats(league, season)
    if not all_team_stats:
        raise HTTPException(status_code=404, detail="League/team stats not found")

    # Count teams for normalization
    sample_stat_type = next(iter(all_team_stats))
    total_teams = len(all_team_stats.get(sample_stat_type, []))

    data = {}

    for category, metrics in TEAM_MENTAL_MAPPING.items():
        category_data = {}

        for m in metrics:
            stat_type = m["stat_type"]
            key = m["key"]

            stat_list = all_team_stats.get(stat_type, [])
            if not stat_list:
                continue

            # Team entry
            team_entry = next((s for s in stat_list if s.get("team", "").lower() == team.lower()), {})
            team_metrics = team_entry.get("metrics", {})

            team_value = team_metrics.get(key, {}).get("value", 0)
            team_rank = team_metrics.get(key, {}).get("rank", None)
            team_normalized = normalize_rank(team_rank, total_teams) if team_rank else 0

            # League best
            league_best_entry = max(
                stat_list,
                key=lambda t: t.get("metrics", {}).get(key, {}).get("value", float("-inf")),
                default={}
            )
            league_best_team = league_best_entry.get("team", "")
            league_best_value = league_best_entry.get("metrics", {}).get(key, {}).get("value", 0)
            league_best_rank = league_best_entry.get("metrics", {}).get(key, {}).get("rank", 1)
            league_normalized = normalize_rank(league_best_rank, total_teams)

            category_data[key] = {
                "team_value": team_value,
                "team_rank": team_rank,
                "team_normalized": team_normalized,
                "league_best_value": league_best_value,
                "league_best_team": league_best_team,
                "league_normalized": league_normalized
            }

        data[category] = category_data

    return {
        "league": league,
        "season": season,
        "team": team,
        "chart_type": "default",
        "data": data,
        "metrics": TEAM_MENTAL_MAPPING
    }