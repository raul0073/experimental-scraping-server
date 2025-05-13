from fastapi import APIRouter, Body, HTTPException
from models.team import TeamInitPayload, TeamModel
from services.db_service import DBService
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
            team_id = DBService.save_team(team_model)
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