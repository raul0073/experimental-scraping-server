"""Backfill the prediction history to season start: reconstruct every played
fixture's prediction WALK-FORWARD (ratings from strictly-prior matches only,
frozen params — the backtest discipline) and grade it. Rows are marked
`retro` to stay distinguishable from live-recorded predictions.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\backfill_history.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.history_service import HistoryService
from services.predictions.prediction_service import SEASON, PredictionService


def main() -> int:
    svc = PredictionService()
    all_preds = {}
    for league in LEAGUE_NAME_MAP:
        fx = FixturesService.load(league, SEASON)
        played = [m for m in fx["matches"]
                  if m["played"] and isinstance(m["week"], int)]
        rows = svc.predict_fixtures(league, played)
        all_preds[league] = rows
        print(f"{league}: reconstructed {len(rows)} played fixtures", flush=True)

    r = HistoryService.record({"all_predictions": all_preds}, retro=True)
    print("record:", r)
    print("grade:", HistoryService.grade())
    print("summary:", HistoryService.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
