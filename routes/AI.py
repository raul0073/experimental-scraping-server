from fastapi import APIRouter, Body, HTTPException, Query
from typing import Dict, List
from pydantic import BaseModel
from models.stats_type import StatsOptions
from services.ai_service import AIService


router = APIRouter()

class StatType(BaseModel):
    label: str
    val: float
    rank: int
    

class PlayerStatsRequest(BaseModel):
    stats: List[StatType]
    stats_type: StatsOptions
    player_name: str
    player_role: str


@router.post("/player-summary")
def get_player_summary(request: PlayerStatsRequest = Body(...)):
    try:
        # Extracting stats and preparing the player data
        player_name = request.player_name.strip()  
        stats_type = request.stats_type.value  
        stats = [stat.model_dump() for stat in request.stats]  
        
        # Generate both summary and radar chart using AIService
        summary = AIService.generate_player_stat_summary(
            player_name=player_name,
            stat_type=stats_type,
            stats=stats
        )
        return {
            "summary": summary,
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching {request.player_name} AI summary: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )