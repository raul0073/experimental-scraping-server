from fastapi import APIRouter, Body, HTTPException, Query
from typing import Dict, List
from pydantic import BaseModel
from models.stats_type import PlayerStatsRequest, StatsOptions
from services.ai.ai_service import AIService


router = APIRouter()

@router.post("/player-summary")
def get_player_summary(request: PlayerStatsRequest = Body(...)):
    try:
        player_name = request.player_name.strip()  
        stats_type = request.stats_type.value  
        stats = [stat.model_dump() for stat in request.stats]  
        
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