from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from routes.fbref.league.league_route_helper import _find_league_dir, _index_by_team, _list_stat_types, _load_stat_file, _merge_team_metrics, _scan_league_dirs
from services.fbref.league.fbref_utils import _sanitize

router = APIRouter(prefix="", tags=["stats"])

@router.get("/leagues")
def list_leagues() -> Dict[str, Any]:
    rows = _scan_league_dirs()
    leagues: Dict[str, List[str]] = {}
    for r in rows:
        leagues.setdefault(r["league"], []).append(r["season"])
    result = [{"league": k, "seasons": sorted(v, reverse=True)} for k, v in sorted(leagues.items())]
    if not result:
        raise HTTPException(status_code=404, detail="No league folders under data/league_init")
    return {"ok": True, "count": len(result), "leagues": result}

@router.get("/league/{league_name}/stats_types")
def league_stats_types(league_name: str, season: Optional[str] = Query(None)) -> Dict[str, Any]:
    try:
        ldir = _find_league_dir(league_name, season)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    stypes = _list_stat_types(ldir)
    if not stypes:
        raise HTTPException(status_code=404, detail="No team_*.json files for this league/season")
    return {"ok": True, "league": league_name, "season": season or ldir.name.rsplit("-", 1)[-1], "stats_types": stypes}

@router.get("/league/{league_name}")
def get_league(
    league_name: str,
    season: Optional[str] = Query(None, description="e.g. 2425; if omitted, latest"),
    stat_type: str = Query("all", description="'all' or one of /stats_types"),
) -> Dict[str, Any]:
    """
    stat_type = 'all'  -> merges all team_*.json files into a single per-team metrics object.
    stat_type = name   -> returns only that file's rows.
    """
    try:
        ldir = _find_league_dir(league_name, season)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    resolved_season = season or ldir.name.rsplit("-", 1)[-1]

    stypes = _list_stat_types(ldir)
    if not stypes:
        raise HTTPException(status_code=404, detail="No team_*.json files for this league/season")

    if stat_type == "all":
        teams_index: Dict[str, Dict[str, Any]] = {}
        for st in stypes:
            rows = _load_stat_file(ldir, st)
            # index/merge by team
            if not teams_index:
                teams_index = _index_by_team(rows)
            else:
                # merge additional metrics into existing teams, create if missing
                add_index = _index_by_team(rows)
                for team, obj in add_index.items():
                    base = teams_index.setdefault(team, {
                        "league": obj.get("league"),
                        "season": obj.get("season"),
                        "team": team,
                        "metrics": {}
                    })
                    _merge_team_metrics(base, obj.get("metrics", {}))
        teams = list(teams_index.values())
        teams.sort(key=lambda x: (x.get("team") or ""))  # stable order
        return {"ok": True, "league": league_name, "season": resolved_season, "stat_type": "all", "count": len(teams), "teams": _sanitize(teams)}

    # single stat type
    if stat_type not in stypes:
        raise HTTPException(status_code=404, detail=f"stat_type '{stat_type}' not found. Available: {stypes}")
    rows = _load_stat_file(ldir, stat_type)
    return {"ok": True, "league": league_name, "season": resolved_season, "stat_type": stat_type, "count": len(rows), "teams": _sanitize(rows)}

# Optional: team-by-name across merged or single stat file
@router.get("/team/{league_name}/{team_name}")
def get_team(league_name: str, team_name: str, season: Optional[str] = Query(None)) -> Dict[str, Any]:
    try:
        ldir = _find_league_dir(league_name, season)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # merge all and then pick the team (simple & consistent)
    stypes = _list_stat_types(ldir)
    if not stypes:
        raise HTTPException(status_code=404, detail="No team_*.json files for this league/season")
    merged = {}
    for st in stypes:
        rows = _load_stat_file(ldir, st)
        idx = _index_by_team(rows)
        merged = merged or {k: v for k, v in idx.items()}
        for k, v in idx.items():
            base = merged.setdefault(k, {"league": v.get("league"), "season": v.get("season"), "team": k, "metrics": {}})
            _merge_team_metrics(base, v.get("metrics", {}))

    team_key = team_name
    payload = merged.get(team_key)
    if not payload:
        # try a case-insensitive match
        for k in merged:
            if k.lower() == team_name.lower():
                payload = merged[k]
                break
    if not payload:
        raise HTTPException(status_code=404, detail=f"Team not found: {team_name}")

    resolved_season = season or ldir.name.rsplit("-", 1)[-1]
    return {"ok": True, "league": league_name, "season": resolved_season, "team": team_name, "data": _sanitize(payload)}