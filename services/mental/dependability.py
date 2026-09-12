from __future__ import annotations

"""Mental ranking, reborn as measured DEPENDABILITY — config-driven, PER ROLE.

The original mental model (models/mental/*) blended role-aware traits over
fbref's Opta columns; those died with the licence in Jan 2026. This rebuild
runs on per-match Understat rosters + shot events we cache ourselves, and
keeps the old system's best idea: the recipe DIFFERS BY POSITION — you can't
expect a defender to attack his man.

Each role bucket (DEF / MID / ATT) has its own set of enabled metrics and
weights in data/config/mental_rank.json, editable at /dashboard/mental/config.
score = sum(w_i/sum(w) * percentile_i) with percentiles computed within
league + role, ties sharing a rank. GKs excluded; qualification = 8
appearances of 45'+ across the two seasons.
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
ROLES = ("DEF", "MID", "ATT")
CONFIG_PATH = Path("data/config/mental_rank.json")

# ---- the bank: every dependability signal our data can honestly measure ----
METRICS: Dict[str, Dict[str, Any]] = {
    "avail": {
        "label": "Availability", "unit": "%", "invert": False,
        "desc": "Recency-weighted share of his team's matches he plays 60'+ "
                "(from his first appearance for the current club). The core "
                "of dependable: he is simply always there."},
    "minutes_share": {
        "label": "Minutes share", "unit": "%", "invert": False,
        "desc": "Recency-weighted share of possible minutes actually played — "
                "rewards full 90s, punishes cameo subs."},
    "starter_share": {
        "label": "Starter share", "unit": "%", "invert": False,
        "desc": "Share of appearances that were starts — the manager's own "
                "dependability vote."},
    "finish_starts": {
        "label": "Plays the full shift", "unit": "%", "invert": False,
        "desc": "Average share of the 90 he completes when he starts — "
                "managers hook players they can't trust to run it out."},
    "floor_chain": {
        "label": "Involvement floor", "unit": "xGCh/90", "invert": False,
        "desc": "25th percentile of per-match xGChain/90 — what he gives you "
                "on a BAD day. High floor, not high peak."},
    "cons_chain": {
        "label": "Consistency", "unit": "%", "invert": False,
        "desc": "1 minus game-to-game variation of involvement. "
                "100% = identical output every match."},
    "floor_xgxa": {
        "label": "End-product floor", "unit": "xG+xA/90", "invert": False,
        "desc": "25th percentile of per-match (xG+xA)/90 — bad-day floor of "
                "direct goal threat."},
    "buildup90": {
        "label": "Quiet build-up", "unit": "xGB/90", "invert": False,
        "desc": "xGBuildup/90 — involvement in moves excluding his own shots "
                "and key passes. The unglamorous work."},
    "kp90": {
        "label": "Chance service", "unit": "KP/90", "invert": False,
        "desc": "Key passes per 90 — how reliably he supplies shooters."},
    "discipline": {
        "label": "Discipline", "unit": "cards/90", "invert": True,
        "desc": "Cards per 90 (red = 3 yellows), INVERTED — no ten-men "
                "disasters, no suspensions."},
    # ---- the MENTAL family: manipulated ratios, not raw volume ----
    "delivery": {
        "label": "Delivery (G v xG)", "unit": "ratio", "invert": False,
        "desc": "Goals versus the xG he was given (shrunk) — xG-created vs "
                "xG-USED. Above 1 = banks what the chances are worth. "
                "Noisiest metric here; mean-reverts."},
    "assist_delivery": {
        "label": "Final-ball delivery", "unit": "ratio", "invert": False,
        "desc": "Assists versus xA (shrunk) — do his final balls actually get "
                "finished. Partly teammates' finishing; treat gently."},
    "takeon90": {
        "label": "Attacks his man", "unit": "/90", "invert": False,
        "desc": "Shots immediately after beating a defender (lastAction "
                "TakeOn) per 90 — initiative, not waiting."},
    "box_presence": {
        "label": "Lives in the box", "unit": "/90", "invert": False,
        "desc": "Shots from inside the penalty area per 90 (penalties "
                "excluded) — relentless positioning hunger."},
    "shot_selection": {
        "label": "Shot selection", "unit": "xG/shot", "invert": False,
        "desc": "Average chance quality he shoots from (needs 8+ shots, else "
                "0) — doesn't waste possession on hopeful hits."},
    "sp_threat": {
        "label": "Set-piece threat", "unit": "/90", "invert": False,
        "desc": "Shots from corners and set pieces per 90 — dead-ball "
                "reliability; a defender can top this."},
    "aerial90": {
        "label": "Aerial threat", "unit": "/90", "invert": False,
        "desc": "Headed shots + shots straight from an aerial win, per 90. "
                "Honest limit: ATTACKING aerials only — defensive duels won "
                "aren't published free."},
    "big_games": {
        "label": "Big-game presence", "unit": "%", "invert": False,
        "desc": "Involvement (xGChain/90) against top-6 opposition versus his "
                "own norm — 100% = same player when it matters. Needs 3+ such "
                "45'+ apps, else neutral 100."},
    "travels": {
        "label": "Travels well", "unit": "%", "invert": False,
        "desc": "Away-day involvement versus his own norm — showing up "
                "outside the comfort zone is mental."},
}

# per-role default recipes — you can't expect a defender to attack his man
DEFAULT_ROLE_COMPONENTS: Dict[str, List[Dict[str, Any]]] = {
    "DEF": [
        {"key": "avail", "weight": 25, "enabled": True},
        {"key": "big_games", "weight": 15, "enabled": True},
        {"key": "discipline", "weight": 15, "enabled": True},
        {"key": "cons_chain", "weight": 10, "enabled": True},
        {"key": "floor_chain", "weight": 10, "enabled": True},
        {"key": "travels", "weight": 10, "enabled": True},
        {"key": "aerial90", "weight": 10, "enabled": True},
        {"key": "finish_starts", "weight": 5, "enabled": True},
        {"key": "sp_threat", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 15, "enabled": False},
        {"key": "starter_share", "weight": 10, "enabled": False},
        {"key": "buildup90", "weight": 10, "enabled": False},
        {"key": "kp90", "weight": 5, "enabled": False},
        {"key": "floor_xgxa", "weight": 5, "enabled": False},
        {"key": "delivery", "weight": 5, "enabled": False},
        {"key": "assist_delivery", "weight": 5, "enabled": False},
        {"key": "takeon90", "weight": 5, "enabled": False},
        {"key": "box_presence", "weight": 5, "enabled": False},
        {"key": "shot_selection", "weight": 5, "enabled": False},
    ],
    "MID": [
        {"key": "avail", "weight": 20, "enabled": True},
        {"key": "floor_chain", "weight": 15, "enabled": True},
        {"key": "big_games", "weight": 15, "enabled": True},
        {"key": "travels", "weight": 10, "enabled": True},
        {"key": "cons_chain", "weight": 10, "enabled": True},
        {"key": "delivery", "weight": 10, "enabled": True},
        {"key": "kp90", "weight": 10, "enabled": True},
        {"key": "discipline", "weight": 10, "enabled": True},
        {"key": "assist_delivery", "weight": 10, "enabled": False},
        {"key": "buildup90", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 15, "enabled": False},
        {"key": "starter_share", "weight": 10, "enabled": False},
        {"key": "finish_starts", "weight": 10, "enabled": False},
        {"key": "floor_xgxa", "weight": 5, "enabled": False},
        {"key": "takeon90", "weight": 5, "enabled": False},
        {"key": "box_presence", "weight": 5, "enabled": False},
        {"key": "shot_selection", "weight": 5, "enabled": False},
        {"key": "sp_threat", "weight": 5, "enabled": False},
        {"key": "aerial90", "weight": 5, "enabled": False},
    ],
    "ATT": [
        {"key": "avail", "weight": 15, "enabled": True},
        {"key": "delivery", "weight": 20, "enabled": True},
        {"key": "box_presence", "weight": 15, "enabled": True},
        {"key": "takeon90", "weight": 10, "enabled": True},
        {"key": "big_games", "weight": 10, "enabled": True},
        {"key": "travels", "weight": 10, "enabled": True},
        {"key": "floor_xgxa", "weight": 10, "enabled": True},
        {"key": "shot_selection", "weight": 10, "enabled": True},
        {"key": "aerial90", "weight": 5, "enabled": False},
        {"key": "sp_threat", "weight": 5, "enabled": False},
        {"key": "assist_delivery", "weight": 10, "enabled": False},
        {"key": "kp90", "weight": 5, "enabled": False},
        {"key": "cons_chain", "weight": 10, "enabled": False},
        {"key": "floor_chain", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 10, "enabled": False},
        {"key": "starter_share", "weight": 10, "enabled": False},
        {"key": "finish_starts", "weight": 10, "enabled": False},
        {"key": "buildup90", "weight": 5, "enabled": False},
        {"key": "discipline", "weight": 10, "enabled": False},
    ],
}


def load_config() -> Dict[str, List[Dict[str, Any]]]:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            roles = cfg.get("roles")
            if roles:
                out = {}
                for role in ROLES:
                    comps = [c for c in roles.get(role, []) if c.get("key") in METRICS]
                    have = {c["key"] for c in comps}
                    for d in DEFAULT_ROLE_COMPONENTS[role]:  # new bank entries: off
                        if d["key"] not in have:
                            comps.append({**d, "enabled": False})
                    out[role] = comps
                return out
        except (ValueError, KeyError):
            pass
    save_config({r: [dict(c) for c in DEFAULT_ROLE_COMPONENTS[r]] for r in ROLES})
    return {r: [dict(c) for c in DEFAULT_ROLE_COMPONENTS[r]] for r in ROLES}


def save_config(roles: Dict[str, List[Dict[str, Any]]]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"v": 2, "roles": roles}, indent=1),
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


def _season_of(date: str) -> str:
    return "2627" if date >= "2026-07-01" else "2526"


def _player_metrics(apps: List[Dict], team_dates: Dict[str, List[str]],
                    shots: Dict[str, float],
                    top6: Dict[str, set]) -> Optional[Dict[str, Any]]:
    apps = sorted(apps, key=lambda a: a["date"])
    apps45 = [a for a in apps if a["minutes"] >= 45]
    team = apps[-1]["team"]
    # qualification keyed to HIS OWN team's played count (leagues start on
    # different weekends and schedules drift — a league-wide bar was hiding
    # whole teams that had simply played one round fewer)
    team_played = len(set(team_dates.get(team, [])))
    min_apps = max(2, min(MIN_APPS_45, round(0.6 * team_played)))
    if len(apps45) < min_apps:
        return None
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
    assists = sum(a["assists"] for a in apps)
    xa = sum(a["xa"] for a in apps)
    n_shots = sum(a["shots"] for a in apps)
    starts = [a for a in apps if a["start"]]

    away45 = [a["chain"] / a["minutes"] * 90 for a in apps45 if a["away"]]
    travels = 0.0
    if mean > 0.05 and away45:
        travels = min(sum(away45) / len(away45) / mean * 100, 150.0)

    big45 = [a["chain"] / a["minutes"] * 90 for a in apps45
             if a["opp"] in top6.get(_season_of(a["date"]), set())]
    big_games = 100.0
    if mean > 0.05 and len(big45) >= 3:
        big_games = min(sum(big45) / len(big45) / mean * 100, 150.0)

    return {
        "team": team, "apps": len(apps),
        "avail": round((w_60 / w_all if w_all else 0) * 100),
        "minutes_share": round((w_min / w_all if w_all else 0) * 100),
        "starter_share": round(len(starts) / len(apps) * 100),
        "finish_starts": round(sum(min(a["minutes"] / 90.0, 1.0) for a in starts)
                               / len(starts) * 100) if starts else 0,
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
        "assist_delivery": round((assists + 1.0) / (xa + 1.0), 2),
        "takeon90": round(shots.get("takeon", 0) * 90.0 / total_min, 2),
        "box_presence": round(shots.get("box", 0) * 90.0 / total_min, 2),
        "shot_selection": round(shots.get("shot_xg", 0.0) / n_shots, 3)
        if n_shots >= 8 else 0.0,
        "sp_threat": round(shots.get("sp", 0) * 90.0 / total_min, 2),
        "aerial90": round(shots.get("aerial", 0) * 90.0 / total_min, 2),
        "big_games": round(big_games),
        "travels": round(travels),
    }


def build_rankings(seasons: List[str] = None,
                   roles_cfg: Dict[str, List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    from services.understat.shot_events_service import ShotEventsService
    from services.understat.understat_service import UnderstatService

    seasons = seasons or SEASONS
    roles_cfg = roles_cfg or load_config()
    comps_by_role = {r: [c for c in roles_cfg[r] if c.get("enabled") and c.get("weight", 0) > 0]
                     for r in ROLES}
    w_sum = {r: (sum(c["weight"] for c in comps_by_role[r]) or 1.0) for r in ROLES}

    out_rows: List[Dict[str, Any]] = []
    for league in LEAGUES:
        matches: List[Dict] = []
        for season in seasons:
            data = RostersService.load(league, season)
            if data and data.get("v") == 2:
                matches.extend(data["matches"].values())
        if not matches:
            continue

        # top-6 opposition per season (points table from understat results)
        top6: Dict[str, set] = {}
        for season in seasons:
            us = UnderstatService.load(league, season)
            pts: Dict[str, int] = {}
            for m in (us or {}).get("matches", []):
                if m.get("home_goals") is None:
                    continue
                hg, ag = m["home_goals"], m["away_goals"]
                for t, gf, ga in ((m["home_team"], hg, ag), (m["away_team"], ag, hg)):
                    pts[t] = pts.get(t, 0) + (3 if gf > ga else 1 if gf == ga else 0)
            top6[season] = set(sorted(pts, key=pts.get, reverse=True)[:6])

        # per-player behavioral shot counts (the mental family)
        shot_agg: Dict[str, Dict[str, float]] = {}
        for season in seasons:
            sh = ShotEventsService.load(league, season)
            for sm in (sh or {}).get("matches", {}).values():
                for s in sm["shots"]:
                    name = s.get("player")
                    if not name or s.get("result") == "OwnGoal":
                        continue
                    a = shot_agg.setdefault(name, {"takeon": 0, "aerial": 0,
                                                   "box": 0, "sp": 0, "shot_xg": 0.0})
                    a["shot_xg"] += s.get("xg") or 0.0
                    if s.get("last_action") == "TakeOn":
                        a["takeon"] += 1
                    if s.get("shot_type") == "Head" or s.get("last_action") == "Aerial":
                        a["aerial"] += 1
                    if (s.get("x") or 0) >= 0.843 and s.get("situation") != "Penalty":
                        a["box"] += 1
                    if s.get("situation") in ("FromCorner", "SetPiece"):
                        a["sp"] += 1

        team_dates: Dict[str, List[str]] = {}
        players: Dict[str, Dict] = {}
        for m in matches:
            for side, team, opp in (("h", m["home_team"], m["away_team"]),
                                    ("a", m["away_team"], m["home_team"])):
                team_dates.setdefault(team, []).append(m["date"])
                for p in m["rosters"].get(side, []):
                    mins = p.get("minutes") or 0
                    if not p.get("player") or mins <= 0:
                        continue
                    e = players.setdefault(p["player"], {"apps": [], "pos": {}})
                    e["apps"].append({
                        "date": m["date"], "team": team, "opp": opp,
                        "minutes": mins, "away": side == "a",
                        "start": (p.get("position") or "Sub") != "Sub",
                        "chain": p.get("xg_chain") or 0.0,
                        "buildup": p.get("xg_buildup") or 0.0,
                        "xg": p.get("xg") or 0.0,
                        "xa": p.get("xa") or 0.0,
                        "goals": p.get("goals") or 0,
                        "assists": p.get("assists") or 0,
                        "shots": p.get("shots") or 0,
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
            m = _player_metrics(e["apps"], team_dates, shot_agg.get(name, {}), top6)
            if not m:
                continue
            rows.append({"player": name, "league": league, "role": bucket, **m})

        # percentiles within (league, role) using THAT ROLE'S recipe;
        # ties share a percentile so zero-heavy metrics can't invent spread
        for bucket in ROLES:
            grp = [r for r in rows if r["role"] == bucket]
            n = len(grp)
            comps = comps_by_role[bucket]
            if n < 2 or not comps:
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
            for r in grp:
                r["score"] = round(sum(c["weight"] / w_sum[bucket] * r[f"{c['key']}_p"]
                                       for c in comps), 1)
        out_rows.extend(r for r in rows if "score" in r)

    out_rows.sort(key=lambda r: -r["score"])
    enabled = {role: [{**c, "norm": round(c["weight"] / w_sum[role] * 100),
                       **{k: METRICS[c["key"]][k] for k in ("label", "unit", "desc")}}
                      for c in comps_by_role[role]] for role in ROLES}
    col_keys: List[str] = []
    for role in ROLES:
        for c in comps_by_role[role]:
            if c["key"] not in col_keys:
                col_keys.append(c["key"])
    columns = [{"key": k, **{f: METRICS[k][f] for f in ("label", "unit", "desc")}}
               for k in col_keys]
    return {"players": out_rows, "seasons": seasons,
            "qualified": len(out_rows),
            "components": enabled, "columns": columns}
