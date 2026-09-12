from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.predictions.ledger_service import LedgerService
from services.predictions.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/upcoming")
async def get_upcoming_picks(start: Optional[str] = Query(None, description="window start date YYYY-MM-DD")):
    """This window's picks + fixture probabilities. Read-only preview —
    nothing is recorded."""
    try:
        return PredictionService().weekly_picks(start)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"prediction failed: {e}")


@router.post("/commit")
async def commit_picks(start: Optional[str] = Query(None, description="window start date YYYY-MM-DD")):
    """Generate picks and record them in the append-only ledger (idempotent
    per season/window/pick-type)."""
    try:
        svc = PredictionService()
        weekly = svc.weekly_picks(start)
        result = LedgerService.commit(weekly)
        return {"ok": True, **result,
                "draw_picks": weekly["draw_picks"],
                "home_win_picks": weekly["home_win_picks"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"commit failed: {e}")


@router.post("/grade")
async def grade_ledger():
    """Fill in results for pending picks from the fixtures files."""
    return LedgerService.grade()


@router.get("/ledger")
async def get_ledger(season: Optional[str] = Query(None)):
    return {"summary": LedgerService.summary(),
            "entries": LedgerService.entries(season)}
