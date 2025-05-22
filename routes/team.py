import logging
from fastapi import APIRouter, Body, HTTPException, Query
from models.team import TeamInitPayload, TeamModel
from models.users.user import UserAnalyzeTeam
from services.db.db_service import DBService
from services.db.user_config_service import UserConfigService
from services.rating.analysis_service import TeamAnalysisService
from services.team_init_service import TeamDataService

router = APIRouter()

@router.post("/init")
def init_team(team: TeamInitPayload = Body(...)):
    try:
        existing = DBService.get_team_by_name(team.name)
        if existing:
            return existing
        else:
            team_model: TeamModel = TeamDataService.init_team(team)
            team_id = DBService.update_team(team_model)
            return team_model
    
    except Exception as e:
            import traceback
            traceback.print_exc()  
            raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/teams")
def get_all_teams():
    try:
        return DBService.get_all_teams()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch teams: {str(e)}")
    
    
@router.get("/analyze")
def analyze_team(
    team_name: str = Query(..., description="Name of the team"),
    user_id: str = Query(..., description="User ID to fetch user config"),
):
    try:
        if not team_name:
            raise HTTPException(403, detail="Team name is undifined")
        
        team = DBService.get_team_by_name(team_name)
        
        if not team:
            raise HTTPException(404, detail="Team not found in db")

        user_config = UserConfigService.get_user_config(user_id)
        user_id = user_id
        result = TeamAnalysisService.analyze(team, user_config, user_id)
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to analyze team: {str(e)}")