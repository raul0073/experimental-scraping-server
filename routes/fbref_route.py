from fastapi import APIRouter, HTTPException, Query
from models.stats_type import StatsOptions
from services.fbref.fbref_data_service import SoccerDataService

router = APIRouter()

@router.get("/")
async def get_team_stats(
    team: str = Query(..., description="Team name (e.g., 'Arsenal')"),
    stats_type: StatsOptions = Query(..., description="Type of statistics"),
    against: bool = Query(..., description="Whether to fetch opponent stats"),
    league: str = Query(
        "ENG-Premier League",
        description="League name (default is 'ENG-Premier League')",
    ),
    season: str = Query("2425", description="Season (default is '2425')"),
):
    """Fetch statistics for a team."""
    try:
        # Fetch team stats
        sds = SoccerDataService(league, season)
        team_stats = sds.get_team_stats(
            team=team, stats_type=stats_type, against=against
        )

        return {"team": team, "stats_type": stats_type, "data": team_stats}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player")
def get_player_stats(
    team: str = Query(..., description="The name of the team"),
    stats_type: StatsOptions = Query(..., description="Type of statistics"),
    player_name: str = Query(..., description="The name of the player to filter by"),
    league: str = Query(
        "ENG-Premier League",
        description="League name (default is 'ENG-Premier League')",
    ),
    season: str = Query("2425", description="Season (default is '2425')"),
):
    """Fetch statistics for a specific player in a team."""
    try:
        # Initialize the SoccerDataService with dynamic league and season
        service = SoccerDataService(league=league, season=season)

        # Fetch player stats
        player_stats = service.get_player_stats_df(
            team=team, stats_type=stats_type.value, player_name=player_name
        )

        return {
            "team": team,
            "player": player_name,
            "stats_type": stats_type.value,
            "data": player_stats,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching {team} stats: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/season")
async def get_team_season_stats(
    team: str = Query(..., description="Team name (e.g., 'Arsenal')"),
    stats_type: StatsOptions = Query(..., description="Type of statistics"),
    against: bool = Query(..., description="Whether to fetch opponent stats"),
    league: str = Query(
        "ENG-Premier League",
        description="League name (default is 'ENG-Premier League')",
    ),
    season: str = Query("2425", description="Season (default is '2425')"),
):
    """Fetch season statistics for a team."""
    try:
        # Initialize the SoccerDataService with dynamic league and season
        sds = SoccerDataService(league, season)

        # Fetch team season stats
        team_season_stats = sds.get_team_stats(
            team=team, stats_type=stats_type, against=against
        )

        return {"data": team_season_stats}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
