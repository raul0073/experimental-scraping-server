from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.fbref.fixtures.fixtures_service import FixturesService

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])


@router.post("/{league}/{season}/build")
async def build_fixtures(league: str, season: str, refresh: bool = Query(False)):
    try:
        svc = FixturesService(league, season, refresh=refresh)
        return svc.build()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Fixtures scrape failed: {e}")


@router.get("/{league}/{season}")
async def get_fixtures(
    league: str,
    season: str,
    team: Optional[str] = Query(None, description="Filter: matches involving this team"),
    played: Optional[bool] = Query(None, description="Filter: True=results only, False=upcoming only"),
    week: Optional[int] = Query(None, description="Filter: matchweek"),
):
    data = FixturesService.load(league, season)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No fixtures on disk for {league} {season} — build first")

    matches = data["matches"]
    if team:
        t = team.lower()
        matches = [m for m in matches if t in (m["home_team"] or "").lower() or t in (m["away_team"] or "").lower()]
    if played is not None:
        matches = [m for m in matches if m["played"] == played]
    if week is not None:
        matches = [m for m in matches if m["week"] == week]

    return {
        "league": data["league"],
        "season": data["season"],
        "count": len(matches),
        "matches": matches,
    }


@router.get("/{league}")
async def list_fixture_seasons(league: str):
    return {"league": league, "seasons": FixturesService.available(league)}
