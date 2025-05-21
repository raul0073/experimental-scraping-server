import logging
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from models.plotting.plot import ChartRequest

router = APIRouter()


@router.post("/charts")
def generate_charts(request: ChartRequest = Body(...)):
    try:
        from services.plotting.plot_service import PlottingService

        pizza_base64 = PlottingService.generate_pizza_chart_mplsoccer(
            player_name=request.player_name,
            player_position=request.player_position,
            metrics=request.pizza_metrics,
        )

        radar_base64 = PlottingService.generate_radar_chart_mplsoccer(
            player_name=request.player_name,
            player_position=request.player_position,
            metrics=request.radar_metrics,
        )

        return {
            "pizza_chart": pizza_base64,
            "radar_chart": radar_base64
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))