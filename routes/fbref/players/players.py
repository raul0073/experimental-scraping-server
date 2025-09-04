from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from routes.fbref.players.normalize import normalize_scores, sanitize_for_json
from services.fbref.player.player_service import FBRefPlayerService
from services.ranking.player_ranking_service import FBRefPlayerRankingService

router = APIRouter(prefix="/players", tags=["FBref Players"])

@router.post("/{league}/{season}/build")
async def build_league_players(league: str, season: str):
    svc = FBRefPlayerService(league, season)
    svc.build_team_jsons()
    return {"ok": True, "league": league, "season": season}


@router.post("/{league}/rank")
async def rank_league_players(league: str):
    svc = FBRefPlayerRankingService(league)
    svc.rank_players()
    return {"ok": True, "league": league}


@router.get("/{league}/{season}/all")
async def get_all_ranked_players(league: str, season: str):
    svc = FBRefPlayerRankingService(league)
    players = svc.load_players()
    players = normalize_scores(players)

    # Keep only players with a valid performance score
    players = [p for p in players if p.get("ranking", {}).get("performance") is not None]

    # Sort descending by performance
    players.sort(key=lambda p: p["ranking"]["performance"], reverse=True)

    # Take top 50
    top_50 = players[:50]

    # Cleanse for JSON (remove NaNs, infs, etc.)
    top_50 = sanitize_for_json(top_50)

    return JSONResponse(top_50)


@router.get("/{league}/{season}/by-role/{role}")
async def get_ranked_players_by_role(league: str, season: str, role: str):
    svc = FBRefPlayerRankingService(league)
    role = role.upper()
    players = [p for p in svc.load_players() if p.get("role") == role]
    if not players:
        raise HTTPException(status_code=404, detail=f"No players with role '{role}'")
    players = normalize_scores(players)
    return players


@router.get("/{league}/{season}/by-team/{team}")
async def get_ranked_players_by_team(league: str, season: str, team: str):
    svc = FBRefPlayerRankingService(league)
    players = [
        p for p in svc.load_players()
        if p.get("__meta__", {}).get("team", "").replace(" ", "_").lower() == team.replace(" ", "_").lower()
    ]
    if not players:
        raise HTTPException(status_code=404, detail=f"No players found for team '{team}'")
    players = normalize_scores(players)
    return players
