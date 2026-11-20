"""The results-page numbers, computed from what is already on disk.

On 2026-11-20 a tie between two draw candidates was settled by looking them
up on a stats site: home record at home, away record away, draws this
season, the last eight with scores, goals per game. Every one of those is a
function of results we hold - Understat carries every match of every league
back to 2014/15 - so the page should carry them next to the candidate
instead of sending the reader elsewhere.

WHAT THIS IS NOT. It is not a second model and it does not rank anything.
`scripts/experiment_draw_window.py` (2026-11-20) measured whether reading
draw rate and goal volume over eight matches, or by venue, predicts draws
better than the classifier's 38-match window: it does not, and the
eight-match venue-split reading is measurably worse. These numbers are the
inputs the classifier already weighs, shown so a human can see them. Draw
inference stays with the classifier.

Names are Understat's, which are the project's canonical spellings for
fixtures, so no mapping is needed.
"""
from typing import Any, Dict, List, Optional

from services.understat.understat_service import UnderstatService

LAST_N = 8


def _timeline(league: str, seasons: List[str], cache: Dict[str, Any]) -> List[Dict]:
    key = f"{league}|{','.join(seasons)}"
    if key not in cache:
        rows = []
        for s in seasons:
            data = UnderstatService.load(league, s) or {}
            for m in data.get("matches", []):
                if m.get("home_goals") is None:
                    continue
                rows.append({**m, "season": s})
        rows.sort(key=lambda m: m["date"])
        cache[key] = rows
    return cache[key]


def _record(games: List[Dict]) -> Dict[str, Any]:
    gp = len(games)
    w = sum(1 for g in games if g["r"] == "W")
    d = sum(1 for g in games if g["r"] == "D")
    lo = gp - w - d
    gf = sum(g["gf"] for g in games)
    ga = sum(g["ga"] for g in games)
    return {"gp": gp, "w": w, "d": d, "l": lo, "gf": gf, "ga": ga,
            "ppg": round((3 * w + d) / gp, 2) if gp else 0.0,
            "draw_pct": round(d / gp, 4) if gp else 0.0}


def _side(timeline: List[Dict], team: str, before: str, season: str,
          at_home: bool) -> Dict[str, Any]:
    games = []
    for m in timeline:
        if m["date"] >= before:
            break
        if team == m["home_team"]:
            gf, ga, opp, home = int(m["home_goals"]), int(m["away_goals"]), m["away_team"], True
        elif team == m["away_team"]:
            gf, ga, opp, home = int(m["away_goals"]), int(m["home_goals"]), m["home_team"], False
        else:
            continue
        games.append({"date": str(m["date"])[:10], "opp": opp, "at": "H" if home else "A",
                      "gf": gf, "ga": ga, "r": "W" if gf > ga else "D" if gf == ga else "L",
                      "season": m["season"], "home": home})
    this = [g for g in games if g["season"] == season]
    venue = [g for g in this if g["home"] is at_home]
    last = games[-LAST_N:]
    return {
        "team": team,
        # this season at this venue - the home side at home, the away side away
        "venue": _record(venue),
        "overall": _record(this),
        "last8": [{k: g[k] for k in ("date", "opp", "at", "gf", "ga", "r")} for g in last],
        "last8_draws": sum(1 for g in last if g["r"] == "D"),
        "last8_goals_pg": round(sum(g["gf"] + g["ga"] for g in last) / len(last), 2) if last else None,
    }


def form_sheet(league: str, home: str, away: str, kickoff: str, season: str,
               seasons: List[str], cache: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Both sides' sheets as of `kickoff` (strictly before it, so a played
    fixture reads as it stood pre-match). None when the league has no data."""
    timeline = _timeline(league, seasons, cache if cache is not None else {})
    if not timeline:
        return None
    before = str(kickoff or "9999-12-31")[:10]
    played = [str(m["date"])[:10] for m in timeline if str(m["date"])[:10] < before]
    return {"season": season,
            # the last result these numbers know about. Understat went dark on
            # 2026-11-01 and the pipeline only warned; a sheet that does not
            # say how old it is would have read as current for three weeks.
            "through": max(played) if played else None,
            "home": _side(timeline, home, before, season, at_home=True),
            "away": _side(timeline, away, before, season, at_home=False)}
