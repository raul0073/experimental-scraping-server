"""Manager (and referee) tables, extracted from the WhoScored match cache.

Every cached match JSON carries `home.managerName` and `away.managerName`,
so who was in charge is recorded per match — which means tenures do not need
to be collected from anywhere else, they fall out of the data we already
fetch: a manager's spell at a club is simply his first to last match there.

This reads soccerdata's local cache and makes NO network requests, so it can
be re-run at any time (including while a scrape is in progress) and simply
sees more matches each time.

Writes:
    data/managers/{league}/{season}.json   per-match manager rows
    data/managers/tenures.json             derived spells, across clubs

Usage: .venv/Scripts/python.exe scripts/build_managers.py
"""
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path.home() / "soccerdata" / "data" / "WhoScored" / "events"
OUT = ROOT / "data" / "managers"


def rows_for(folder: Path) -> list:
    """One row per TEAM per match: who managed, against whom, and the result.
    Team-rows rather than match-rows because a manager's record is a property
    of his side, not of the fixture."""
    out = []
    for path in sorted(folder.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        home, away = d.get("home") or {}, d.get("away") or {}
        if not home.get("managerName") and not away.get("managerName"):
            continue
        score = (d.get("ftScore") or "").replace(" ", "")
        try:
            hg, ag = (int(x) for x in score.split(":"))
        except (ValueError, AttributeError):
            hg = ag = None
        ref = (d.get("referee") or {}).get("name")
        kickoff = (d.get("startDate") or "")[:10]
        for side, opp, venue in ((home, away, "home"), (away, home, "away")):
            gf, ga = (hg, ag) if venue == "home" else (ag, hg)
            out.append({
                "game_id": path.stem,
                "date": kickoff,
                "team": side.get("name"),
                "manager": side.get("managerName"),
                "venue": venue,
                "opponent": opp.get("name"),
                "opponent_manager": opp.get("managerName"),
                "gf": gf, "ga": ga,
                "result": (None if gf is None else
                           "W" if gf > ga else "D" if gf == ga else "L"),
                "referee": ref,
                "attendance": d.get("attendance"),
                "venue_name": d.get("venueName"),
            })
    return out


def tenures(all_rows: list) -> list:
    """A spell is a manager at a club: first match to last. Because the same
    manager appears at several clubs, this is what lets a rating travel with
    the man instead of describing the squad he inherited."""
    spells = defaultdict(lambda: {"matches": 0, "W": 0, "D": 0, "L": 0,
                                  "gf": 0, "ga": 0, "first": None, "last": None})
    for r in all_rows:
        if not r["manager"] or not r["date"]:
            continue
        s = spells[(r["manager"], r["team"], r["league"])]
        s["matches"] += 1
        if r["result"]:
            s[r["result"]] += 1
        if r["gf"] is not None:
            s["gf"] += r["gf"]
            s["ga"] += r["ga"]
        s["first"] = min(s["first"] or r["date"], r["date"])
        s["last"] = max(s["last"] or r["date"], r["date"])
    out = []
    for (manager, team, league), s in spells.items():
        played = s["W"] + s["D"] + s["L"]
        out.append({
            "manager": manager, "team": team, "league": league,
            "first": s["first"], "last": s["last"], "matches": s["matches"],
            "w": s["W"], "d": s["D"], "l": s["L"],
            "gf": s["gf"], "ga": s["ga"],
            "ppg": round((s["W"] * 3 + s["D"]) / played, 3) if played else None,
        })
    out.sort(key=lambda r: (r["manager"], r["first"] or ""))
    return out


def main() -> int:
    if not CACHE.exists():
        print(f"no WhoScored cache at {CACHE}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for folder in sorted(p for p in CACHE.iterdir() if p.is_dir()):
        league, _, season = folder.name.rpartition("_")
        rows = rows_for(folder)
        if not rows:
            continue
        for r in rows:
            r["league"], r["season"] = league, season
        all_rows.extend(rows)
        path = OUT / league.replace("/", "-") / f"{season}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(
            {"league": league, "season": season,
             "generated": date.today().isoformat(), "rows": rows},
            ensure_ascii=False, indent=1), encoding="utf-8")
        managers = {r["manager"] for r in rows if r["manager"]}
        print(f"OK   {league} {season}: {len(rows) // 2} matches, "
              f"{len(managers)} managers")

    spells = tenures(all_rows)
    (OUT / "tenures.json").write_text(json.dumps(
        {"generated": date.today().isoformat(), "spells": spells},
        ensure_ascii=False, indent=1), encoding="utf-8")
    multi = defaultdict(set)
    for s in spells:
        multi[s["manager"]].add(s["team"])
    across = {m: t for m, t in multi.items() if len(t) > 1}
    print(f"\nOK   tenures.json: {len(spells)} spells, {len(multi)} managers"
          f" ({len(across)} at more than one club)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
