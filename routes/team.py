from fastapi import APIRouter, Body, HTTPException

from models.team import TeamInitPayload, TeamModel
from services.team_init_service import TeamDataService

router = APIRouter()

@router.post("/init")
def init_team(team: TeamInitPayload = Body(...)):
    try:
        return TeamDataService.init_team(team)
    except Exception as e:
            import traceback
            traceback.print_exc()  
            raise HTTPException(status_code=500, detail=str(e))