import logging
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from models.plotting.plot import ChartRequest

router = APIRouter()


@router.get("/test-radar")
def test_radar():
    try:
        from services.plotting.plot_service import PlottingService
        image = PlottingService.generate_radar_chart(
            keys=["Tackles", "Interceptions", "Blocks", "Clearances", "Aerials"],
            values=[3.2, 2.1, 1.8, 4.0, 2.5],
            player_name="Ben White"
        )
        return {"image_base64": f"data:image/png;base64,{image}"}
    except Exception as e:
        return {"error": str(e)}
    
    
@router.post("/test-pizza")
def generate_chart(request: ChartRequest = Body(...)):
    try:
        from services.plotting.plot_service import PlottingService
        keys = [m.key for m in request.metrics]
        values = [m.value for m in request.metrics]

        if request.chart_type == "pizza":
            image_base64 = PlottingService.generate_pizza_chart_mplsoccer(
                player_name=request.player_name,
                metrics=request.metrics
            )
        elif request.chart_type == "radar":
            image_base64 = PlottingService.generate_radar_chart(
                keys=keys,
                values=values,
                player_name=request.player_name,
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid chart_type")

        return {"image_base64": image_base64}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))