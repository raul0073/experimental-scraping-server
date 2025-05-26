from fastapi import APIRouter, HTTPException, Query
from typing import Dict

from services.db.db_service import DBService
from services.predictions.predictions_service import MatchPredictionService

router = APIRouter(tags=["Match Prediction"])

@router.get("/", response_model=Dict)
def predict_match(
    team_a_slug: str = Query(..., description="Slug of the first team (e.g. arsenal)"),
    team_b_slug: str = Query(..., description="Slug of the second team (e.g. liverpool)")
):
    # 1. Fetch team models
    team_a = DBService.get_team_by_name(team_a_slug)
    team_b = DBService.get_team_by_name(team_b_slug)

    if not team_a or not team_b:
        raise HTTPException(status_code=404, detail="One or both teams not found.")

    if not team_a.zones or not team_b.zones:
        raise HTTPException(status_code=400, detail="One or both teams missing zone data.")

    # 2. Predict
    service = MatchPredictionService(team_a=team_a, team_b=team_b)
    prediction = service.predict()

    # 3. Return result
    return prediction
