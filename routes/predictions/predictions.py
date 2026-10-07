"""The betting surface: this window's picks, the ledger, the monkey's book.

LOCALHOST ONLY, AND IT WAS NOT. main.py binds 0.0.0.0 with
allow_origins=["*"], and routes/admin/admin.py guards every one of its
endpoints with _require_local — this router guarded none. So the picks, the
graded ledger and the bankroll were readable by anything on the network, and
/commit and /grade, which WRITE to the append-only ledger, were callable by
it. A stranger on the same wifi could commit a week's picks.

The web page that reads this is development-only, which protects the PAGE
and does nothing for the DATA behind it. The guard belongs here.

It costs nothing real: the dev site runs on localhost and the browser fetches
127.0.0.1:8080, so a phone on the LAN opening the dev site was already
hitting its own loopback and failing. Nothing that worked stops working.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

from services.predictions.gold_ledger import GoldLedger
from services.predictions.ledger_service import LedgerService
from services.predictions.prediction_service import PredictionService
from services.predictions.slip_ledger import SlipLedger

router = APIRouter(prefix="/predictions", tags=["Predictions"])

LOCAL = {"127.0.0.1", "::1", "localhost"}


def _require_local(request: Request) -> None:
    """Same rule, same words as routes/admin/admin.py — one definition of
    "local" is worth more than a cleverer check in two places."""
    host = (request.client.host if request.client else "") or ""
    if host not in LOCAL:
        raise HTTPException(status_code=403, detail="localhost only")


@router.get("/upcoming")
async def get_upcoming_picks(request: Request, start: Optional[str] = Query(None, description="window start date YYYY-MM-DD")):
    """This window's picks + fixture probabilities. Read-only preview —
    nothing is recorded."""
    _require_local(request)
    try:
        return PredictionService().weekly_picks(start)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"prediction failed: {e}")


@router.post("/commit")
async def commit_picks(request: Request, start: Optional[str] = Query(None, description="window start date YYYY-MM-DD")):
    """Generate picks and record them in the append-only ledger (idempotent
    per season/window/pick-type)."""
    _require_local(request)
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
async def grade_ledger(request: Request):
    """Fill in results for pending picks from the fixtures files."""
    _require_local(request)
    return LedgerService.grade()


@router.get("/ledger")
async def get_ledger(request: Request, season: Optional[str] = Query(None)):
    _require_local(request)
    return {"summary": LedgerService.summary(),
            "entries": LedgerService.entries(season)}


@router.get("/monkey")
async def get_monkey(request: Request):
    """The two paper pots, side by side.

    `monkey` is the slip book: every window's recommended form placed at unit
    per line and graded line-by-line at the breakeven prices frozen on commit.
    `gold` is the same honesty test asked of singles — every certified GOLD
    favorite as its own bet, which is what Gate A measures.

    Both only read their jsonl, so this stays cheap enough to poll.
    """
    _require_local(request)
    try:
        return {"monkey": SlipLedger.monkey(), "gold": GoldLedger.summary()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"monkey failed: {e}")
