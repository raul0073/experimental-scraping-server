from __future__ import annotations

"""Mental ranking, reborn as measured DEPENDABILITY — config-driven.

The original mental model (models/mental/*, services/mental/mental_service.py)
blended role-aware traits over fbref's Opta columns; those died with the
licence in Jan 2026, and season totals never could measure the real question:
who shows up EVERY week. Per-match Understat rosters can.

The algorithm is a weighted blend of percentiles (computed within league +
role bucket, so defenders aren't judged as wingers), over whichever metrics
from the BANK below are enabled in data/config/mental_rank.json — editable
live from /dashboard/mental/config. score = sum(w_i/sum(w) * percentile_i).
GKs excluded; qualification = 8 appearances of 45'+.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.understat.rosters_service import RostersService

DECAY = 0.985
MIN_APPS_45 = 8
SEASONS = ["2526", "2627"]
LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
           "GER-Bundesliga", "FRA-Ligue 1"]
CONFIG_PATH = Path("data/config/mental_rank.json")

# ---- the bank: every dependability metric our data can honestly measure ----
METRICS: Dict[str, Dict[str, Any]] = {
    "avail": {
        "label": "Availability", "unit": "%", "invert": False,
        "desc": "Recency-weighted share of his team's matches he plays 60'+ "
                "(counted from his first appearance for the current club). "
                "The core of dependable: he is simply always there."},
    "minutes_share": {
        "label": "Minutes share", "unit": "%", "invert": False,
        "desc": "Recency-weighted share of possible minutes actually played — "
                "finer-grained than availability (rewards full 90s, "
                "punishes cameo subs)."},
    "starter_share": {
        "label": "Starter share", "unit": "%", "invert": False,
        "desc": "Share of his appearances that were starts, not sub entries — "
                "the manager's own dependability vote."},
    "floor_chain": {
        "label": "Involvement floor", "unit": "xGChain/90", "invert": False,
        "desc": "25th percentile of per-match xGChain/90 — what he gives you "
                "on a BAD day. Dependable players have a high floor, "
                "not just a high peak."},
    "cons_chain": {
        "label": "Consistency", "unit": "%", "invert": False,
        "desc": "1 minus the game-to-game variation of his involvement "
                "(xGChain/90). 100% = identical output every match."},
    "floor_xgxa": {
        "label": "End-product floor", "unit": "xG+xA/90", "invert": False,
        "desc": "25th percentile of per-match (xG+xA)/90 — the bad-day floor "
                "of direct goal threat rather than build-up involvement."},
    "buildup90": {
        "label": "Quiet build-up", "unit": "xGB/90", "invert": False,
        "desc": "Average xGBuildup/90 — involvement in moves EXCLUDING his own "
                "shots and key passes. The unglamorous work that never "
                "shows in highlights."},
    "kp90": {
        "label": "Chance service", "unit": "KP/90", "invert": False,
        "desc": "Key passes per 90 — how reliably he supplies shooters."},
    "discipline": {
        "label": "Discipline", "unit": "cards/90", "invert": True,
        "desc": "Cards per 90 (red = 3 yellows), INVERTED — a dependable "
                "player doesn't leave you with ten men or a suspension."},
    # ---- the MENTAL family: manipulated ratios, not raw volume ----
    "delivery": {
        "label": "Delivery (G v xG)", "unit": "ratio", "invert": False,
        "desc": "Goals versus the xG he was given (shrunk for small samples) — "
                "xG-created vs xG-USED. Above 1 = he banks what the chances "
                "are worth. The mental read on finishing; note it is the "
                "noisiest metric here and mean-reverts."},
    "takeon90": {
        "label": "Attacks his man", "unit": "/90", "invert": False,
        "desc": "Shots taken immediately after beating a defender (Understat "
                "lastAction = TakeOn), per 90 — initiative instead of waiting "
                "for the game to come to him."},
    "aerial90": {
        "label": "Aerial threat", "unit": "/90", "invert": False,
        "desc": "Headed shots + shots straight from an aerial win, per 90. "
                "Honest limit: this is ATTACKING aerial presence — defensive "
                "aerial duels won aren't published by any free source."},
    "finish_starts": {
        "label": "Plays the full shift", "unit": "%", "invert": False,
        "desc": "Average share of the 90 he completes when he starts — "
                "managers hook players they can't trust to run it out."},
    "travels": {
        "label": "Travels well", "unit": "%", "invert": False,
        "desc": "Away-day involvement (xGChain/90) versus his own overall "
                "norm — 100% means away-him equals home-him. Showing up "
                "outside the comfort zone is mental."},
}

DEFAULT_COMPONENTS = [
    {"key": "avail", "weight": 25, "enabled": True},
    {"key": "delivery", "weight": 20, "enabled": True},
    {"key": "floor_chain", "weight": 15, "enabled": True},
    {"key": "takeon90", "weight": 10, "enabled": True},
    {"key": "travels", "weight": 10, "enabled": True},
    {"key": "cons_chain", "weight": 10, "enabled": True},
    {"key": "discipline", "weight": 10, "enabled": True},
    {"key": "minutes_share", "weight": 20, "enabled": False},
    {"key": "starter_share", "weight": 15, "enabled": False},
    {"key": "floor_xgxa", "weight": 20, "enabled": False},
    {"key": "buildup90", "weight": 15, "enabled": False},
    {"key": "kp90", "weight": 10, "enabled": False},
    {"key": "aerial90", "weight": 10, "enabled": False},
    {"key": "finish_starts", "weight": 15, "enabled": False},
]


def load_config() -> List[Dict[str, Any]]:
    if CONFIG_PATH.exists():
        try:
            comps = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["components"]
            known = [c for c in comps if c.get("key") in METRICS]
            for d in DEFAULT_COMPONENTS:  # new bank entries appear disabled
                if not any(c["key"] == d["key"] for c in known):
                    known.append({**d, "enabled": False})
            return known
        except (ValueError, KeyError):
            pass
    save_config(DEFAULT_COMPONENTS)
    return [dict(c) for c in DEFAULT_COMPONENTS]


def save_config(components: List[Dict[str, Any]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"components": components}, indent=1),
                           encoding="utf-8")


def _bucket(pos: str) -> str:
    if not pos or pos == "Sub":
        return ""
    if pos == "GK":
        return "GK"
    if pos.startswith("DM") or pos[0] in ("M", "A"):
        return "MID"
    if pos.startswith("D"):
        return "DEF"
    if pos.startswith("F"):
        return "ATT"
    return ""


def _pctile(values: List[float], q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    i = q * (len(s) - 1)
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def _player_metrics(apps: List[Dict], team_dates: Dict[str, List[str]],
                    shots: Dict[str, int]) -> Optional[Dict[str, float]]:
    apps = sorted(apps, key=lambda a: a["date"])
    apps45 = [a for a in apps if a["minutes"] >= 45]
    if len(apps45) < MIN_APPS_45:
        return None
    team = apps[-1]["team"]
    first = min(a["date"] for a in apps if a["team"] == team)
    sched = sorted({d for d in team_dates.get(team, []) if d >= first}, reverse=True)
    by_date = {a["date"]: a for a in apps if a["team"] == team}
    w_all = w_60 = w_min = 0.0
    for i, d in enumerate(sched):
        w = DECAY ** i
        w_all += w
        a = by_date.get(d)
        if a:
            w_60 += w * (a["minutes"] >= 60)
            w_min += w * min(a["minutes"] / 90.0, 1.0)
    chain90 = [a["chain"] / a["minutes"] * 90 for a in apps45]
    xgxa90 = [a["xgxa"] / a["minutes"] * 90 for a in apps45]
    mean = sum(chain90) / len(chain90)
    var = sum((c - mean) ** 2 for c in chain90) / len(chain90)
    total_min = sum(a["minutes"] for a in apps)
    goals = sum(a["goals"] for a in apps)
    xg = sum(a["xg"] for a in apps)
    starts = [a for a in apps if a["start"]]
    away45 = [a["chain"] / a["minutes"] * 90 for a in apps45 if a["away"]]
    travels = 0.0
    if mean > 0.05 and away45:
        travels = min(sum(away45) / len(away45) / mean * 100, 150.0)
    return {
        "team": team, "apps": len(apps),
        "avail": round((w_60 / w_all if w_all else 0) * 100),
        "minutes_share": round((w_min / w_all if w_all else 0) * 100),
        "starter_share": round(len(starts) / len(apps) * 100),
        "floor_chain": round(_pctile(chain90, 0.25), 2),
        "cons_chain": round(max(0.0, 1.0 - (var ** 0.5) / mean) * 100
                            if mean > 0.05 else 0.0),
        "floor_xgxa": round(_pctile(xgxa90, 0.25), 2),
        "buildup90": round(sum(a["buildup"] / a["minutes"] * 90 for a in apps45)
                           / len(apps45), 2),
        "kp90": round(sum(a["kp"] / a["minutes"] * 90 for a in apps45)
                      / len(apps45), 2),
        "discipline": round((sum(a["yellow"] for a in apps)
                             + 3 * sum(a["red"] for a in apps)) * 90.0 / total_min, 2),
        "delivery": round((goals + 1.0) / (xg + 1.0), 2),
        "takeon90": round(shots.get("takeon", 0) * 90.0 / total_min, 2),
        "aerial90": round(shots.get("aerial", 0) * 90.0 / total_min, 2),
        "finish_starts": round(sum(min(a["minutes"] / 90.0, 1.0) for a in starts)
                               / len(starts) * 100) if starts else 0,
        "travels": round(travels),
    }


def build_rankings(seasons: List[str] = None,
                   components: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    seasons = seasons or SEASONS
    comps = [c for c in (components or load_config())
             if c.get("enabled") and c.get("weight", 0) > 0]
    w_sum = sum(c["weight"] for c in comps) or 1.0

    out_rows: List[Dict[str, Any]] = []
    for league in LEAGUES:
        matches: List[Dict] = []
        for season in seasons:
            data = RostersService.load(league, season)
            if data and data.get("v") == 2:
                matches.extend(data["matches"].values())
        if not matches:
            continue

        # per-player behavioral shot counts (the mental family) from shot events
        from services.understat.shot_events_service import ShotEventsService
        shot_agg: Dict[str, Dict[str, int]] = {}
        for season in seasons:
            sh = ShotEventsService.load(league, season)
            for sm in (sh or {}).get("matches", {}).values():
                for s in sm["shots"]:
                    name = s.get("player")
                    if not name or s.get("result") == "OwnGoal":
                        continue
                    a = shot_agg.setdefault(name, {"takeon": 0, "aerial": 0})
                    if s.get("last_action") == "TakeOn":
                        a["takeon"] += 1
                    if s.get("shot_type") == "Head" or s.get("last_action") == "Aerial":
                        a["aerial"] += 1

        team_dates: Dict[str, List[str]] = {}
        players: Dict[str, Dict] = {}
        for m in matches:
            for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
                team_dates.setdefault(team, []).append(m["date"])
                for p in m["rosters"].get(side, []):
                    mins = p.get("minutes") or 0
                    if not p.get("player") or mins <= 0:
                        continue
                    e = players.setdefault(p["player"], {"apps": [], "pos": {}})
                    e["apps"].append({
                        "date": m["date"], "team": team, "minutes": mins,
                        "away": side == "a",
                        "start": (p.get("position") or "Sub") != "Sub",
                        "chain": p.get("xg_chain") or 0.0,
                        "buildup": p.get("xg_buildup") or 0.0,
                        "xg": p.get("xg") or 0.0,
                        "goals": p.get("goals") or 0,
                        "xgxa": (p.get("xg") or 0.0) + (p.get("xa") or 0.0),
                        "kp": p.get("key_passes") or 0,
                        "yellow": p.get("yellow") or 0, "red": p.get("red") or 0,
                    })
                    pos = p.get("position")
                    if pos and pos != "Sub":
                        e["pos"][pos] = e["pos"].get(pos, 0) + mins

        rows = []
        for name, e in players.items():
            if not e["pos"]:
                continue
            bucket = _bucket(max(e["pos"], key=e["pos"].get))
            if bucket in ("", "GK"):
                continue
            m = _player_metrics(e["apps"], team_dates, shot_agg.get(name, {}))
            if not m:
                continue
            rows.append({"player": name, "league": league, "role": bucket, **m})

        # percentiles within (league, role); TIES SHARE a percentile so a
        # zero-heavy metric (take-ons for defenders) can't invent spread
        for bucket in ("DEF", "MID", "ATT"):
            grp = [r for r in rows if r["role"] == bucket]
            n = len(grp)
            if n < 2:
                continue
            for c in comps:
                key = c["key"]
                ordered = sorted(grp, key=lambda r: r[key],
                                 reverse=METRICS[key]["invert"])
                i = 0
                while i < n:
                    j = i
                    while j + 1 < n and ordered[j + 1][key] == ordered[i][key]:
                        j += 1
                    avg_p = (i + j) / 2.0 / (n - 1) * 100
                    for k in range(i, j + 1):
                        ordered[k][f"{key}_p"] = avg_p
                    i = j + 1
        for r in rows:
            if f"{comps[0]['key']}_p" not in r:
                continue
            r["score"] = round(sum(c["weight"] / w_sum * r[f"{c['key']}_p"]
                                   for c in comps), 1)
        out_rows.extend(r for r in rows if "score" in r)

    out_rows.sort(key=lambda r: -r["score"])
    enabled = [{**c, "norm": round(c["weight"] / w_sum * 100),
                **{k: METRICS[c["key"]][k] for k in ("label", "unit", "desc")}}
               for c in comps]
    return {"players": out_rows, "seasons": seasons,
            "qualified": len(out_rows), "components": enabled}
