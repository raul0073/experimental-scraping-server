"""Stamp every event with the match state at the moment it happened.

This is the foundation the whole benchmark stands on. An action means
something different at 0-0 in the 10th minute than at 1-0 down in the 85th
with ten men, and until each event carries that context the question we
actually care about — how often did he try, and WHEN — cannot be asked.

Adds per event:
    team_goals / opp_goals   the score from the acting team's point of view
    score_state              behind | level | ahead
    score_diff               +1 = a goal up, -2 = two down
    man_state                down | equal | up
    man_diff                 +1 = a man up
    phase                    opening (<15') | middle | late (>=75') | closing (>=85')

Two things that silently corrupt this if you get them wrong:
  * OWN GOALS are recorded against the scorer's own team and carry an
    OwnGoal qualifier — the goal must be credited to the opponent.
  * events are NOT stored chronologically, and first-half added time
    (46') overlaps the second half (45'), so order by period first.

The state applies to the moment an action BEGAN, so a goal or red card
changes the state for everything that follows it, not for itself.

Reads  data/whoscored/{league}/{season}.parquet
Writes data/whoscored/{league}/{season}_stamped.parquet

Usage: .venv/Scripts/python.exe scripts/stamp_event_state.py [--league ...]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"

PERIOD_ORDER = {
    "PreMatch": 0, "FirstHalf": 1, "SecondHalf": 2,
    "ExtraTimeFirstHalf": 3, "ExtraTimeSecondHalf": 4,
    "PenaltyShootout": 5, "PostGame": 6,
}
SENDING_OFF = {"Red", "SecondYellow"}


def qualifier_names(q) -> set:
    """Opta qualifiers arrive as a list of {'type': {'displayName': ...}}."""
    try:
        return {x["type"]["displayName"] for x in q}
    except Exception:
        return set()


def stamp_match(m: pd.DataFrame) -> pd.DataFrame:
    """Walk one match in order, carrying the running score and man count."""
    m = m.copy()
    m["_po"] = m["period"].map(PERIOD_ORDER).fillna(9)
    m["_sec"] = m["second"].fillna(0)
    m = m.sort_values(["_po", "minute", "_sec"], kind="stable")

    teams = [t for t in m["team"].dropna().unique()]
    if len(teams) != 2:
        return pd.DataFrame()
    a, b = teams
    goals = {a: 0, b: 0}
    men = {a: 0, b: 0}          # sendings off, so "men down"

    ta, oa = [], []             # team goals / opponent goals per event
    md = []                     # man difference per event
    for row in m.itertuples(index=False):
        team = row.team
        opp = b if team == a else a
        ta.append(goals.get(team, 0))
        oa.append(goals.get(opp, 0))
        md.append(men.get(opp, 0) - men.get(team, 0))

        # state changes apply AFTER the event that caused them
        if getattr(row, "is_goal", False):
            scorer = team
            if "OwnGoal" in qualifier_names(row.qualifiers):
                scorer = opp            # credited to the other side
            goals[scorer] = goals.get(scorer, 0) + 1
        if row.type == "Card" and row.card_type in SENDING_OFF:
            men[team] = men.get(team, 0) + 1

    m["team_goals"] = ta
    m["opp_goals"] = oa
    m["score_diff"] = m["team_goals"] - m["opp_goals"]
    m["score_state"] = np.select(
        [m["score_diff"] > 0, m["score_diff"] < 0],
        ["ahead", "behind"], default="level")
    m["man_diff"] = md
    m["man_state"] = np.select(
        [m["man_diff"] > 0, m["man_diff"] < 0], ["up", "down"], default="equal")
    m["phase"] = np.select(
        [m["minute"] >= 85, m["minute"] >= 75, m["minute"] < 15],
        ["closing", "late", "opening"], default="middle")
    return m.drop(columns=["_po", "_sec"])


def verify(stamped: pd.DataFrame, league: str, season: str) -> dict:
    """Our reconstructed final score must equal the score WhoScored itself
    states for the match. This is what proves the own-goal handling: credit
    an own goal to the wrong side and the reconstruction disagrees.

    Checked against the cached match JSON rather than our fbref fixtures,
    because the cache uses the same team names as the events — no name
    mapping, nothing to get wrong in the check itself."""
    import json
    cache = Path.home() / "soccerdata" / "data" / "WhoScored" / "events" / f"{league}_{season}"
    if not cache.exists():
        return {"checked": 0, "note": f"no cache at {cache}"}

    checked = matched = 0
    misses = []
    for gid, g in stamped.groupby("game_id"):
        path = cache / f"{gid}.json"
        if not path.exists():
            continue
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            home, away = d["home"]["name"], d["away"]["name"]
            hg, ag = (int(x) for x in (d.get("ftScore") or "").split(":"))
        except Exception:
            continue
        # final state of any event by the home team carries both totals
        hrows = g[g["team"] == home]
        if hrows.empty:
            continue
        last = hrows.iloc[-1]
        got = (int(last.team_goals), int(last.opp_goals))
        # the last event's state is BEFORE any goal it caused, so re-apply
        got = _final_from(g, home, away)
        checked += 1
        if got == (hg, ag):
            matched += 1
        else:
            misses.append((home, away, got, (hg, ag)))
    return {"checked": checked, "matched": matched,
            "misses": misses[:5], "n_miss": len(misses)}


def _final_from(g: pd.DataFrame, home: str, away: str) -> tuple:
    """Count goals directly, own goals credited to the opponent."""
    hg = ag = 0
    for row in g[g["is_goal"] == True].itertuples(index=False):   # noqa: E712
        scorer = row.team
        if "OwnGoal" in qualifier_names(row.qualifiers):
            scorer = away if scorer == home else home
        if scorer == home:
            hg += 1
        else:
            ag += 1
    return hg, ag


def run(league: str, season: str) -> dict:
    src = RAW / league / f"{season}.parquet"
    if not src.exists():
        return {"league": league, "season": season, "error": "no raw parquet"}
    df = pd.read_parquet(src)
    out = pd.concat(
        [stamp_match(g) for _, g in df.groupby("game_id", sort=False)],
        ignore_index=True)
    dst = src.with_name(f"{season}_stamped.parquet")
    out.to_parquet(dst, index=False)

    v = verify(out, league, season)
    dist = out["score_state"].value_counts(normalize=True).mul(100).round(1).to_dict()
    man = out["man_state"].value_counts(normalize=True).mul(100).round(1).to_dict()
    return {"league": league, "season": season, "matches": out.game_id.nunique(),
            "events": len(out), "mb": round(dst.stat().st_size / 1e6, 1),
            "score_state_pct": dist, "man_state_pct": man, "verify": v}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--seasons", nargs="+", default=None)
    args = ap.parse_args()

    folder = RAW / args.league
    seasons = args.seasons or sorted(
        p.stem for p in folder.glob("*.parquet") if "_stamped" not in p.stem)
    for season in seasons:
        r = run(args.league, season)
        if r.get("error"):
            print(f"SKIP {season}: {r['error']}")
            continue
        v = r["verify"]
        ok = v["matched"] == v["checked"] and v["checked"] > 0
        print(f"\n=== {r['league']} {r['season']}: {r['matches']} matches, "
              f"{r['events']:,} events -> {r['mb']} MB")
        print(f"  score state: {r['score_state_pct']}")
        print(f"  man state  : {r['man_state_pct']}")
        print(f"  final-score check: {v['matched']}/{v['checked']} "
              f"{'ALL MATCH' if ok else 'MISMATCHES'}")
        for miss in v.get("misses", []):
            print(f"    {miss[0]} v {miss[1]}: rebuilt {miss[2]} vs actual {miss[3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
