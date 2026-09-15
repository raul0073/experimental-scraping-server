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
# evidence shrinkage: final scores are pulled toward neutral 50 by sample
# size — score = 50 + (raw-50) * n/(n+K) with n = minutes/90. A 37-game
# player keeps ~76% of his deviation, a 20-game player ~62%, a 5-game
# early-season sample ~29%. More games = more trust, as it should be.
K_EVIDENCE = 12.0
SEASONS = ["2526", "2627"]
LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
           "GER-Bundesliga", "FRA-Ligue 1"]
ROLES = ("DEF", "MID", "ATT", "GK")
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
    # ---- fbref counting family (season aggregates joined by name; the
    # tables that SURVIVED the Opta loss — user caught this 2026-09-15) ----
    "tklw90": {
        "label": "Wins his tackles", "unit": "/90", "invert": False,
        "desc": "Tackles WON per 90 (fbref) — not volume, wins. The closest "
                "surviving stat to 'competes and comes out with the ball'."},
    "int90": {
        "label": "Reads the game", "unit": "/90", "invert": False,
        "desc": "Interceptions per 90 (fbref) — anticipation: being where the "
                "pass was going before it was played."},
    "fld90": {
        "label": "Draws fouls", "unit": "/90", "invert": False,
        "desc": "Fouls drawn per 90 (fbref) — carries into contact and makes "
                "defenders break the rules; buys free kicks and cards."},
    "fls90": {
        "label": "Clean aggression", "unit": "fouls/90", "invert": True,
        "desc": "Fouls committed per 90 (fbref), INVERTED — competes without "
                "conceding free kicks; pairs with the cards metric."},
    "sot_share": {
        "label": "Hits the target", "unit": "%", "invert": False,
        "desc": "Share of his shots on target (fbref, needs 8+ shots) — "
                "shooting composure regardless of chance quality."},
    "killer90": {
        "label": "Killer balls", "unit": "/90", "invert": False,
        "desc": "Through balls, chipped passes and lay-offs that DIRECTLY "
                "created a shot, per 90 (from shot events: he is the assister "
                "and that was the pass type). The surviving window into "
                "incisive passing."},
    "cross_created90": {
        "label": "Crosses that arrive", "unit": "/90", "invert": False,
        "desc": "Crosses that actually found a shooter, per 90 — delivery "
                "QUALITY, unlike raw cross volume."},
    "gk_save_pct": {
        "label": "Save% (real)", "unit": "%", "invert": False,
        "desc": "Actual saves / shots on target faced (fbref, needs 10+ SoT "
                "faced) — real stopping, no xG proxy. The Raya-fixer: a "
                "keeper behind a great defense is no longer punished for "
                "having little xG to 'prevent'."},
    # ---- goalkeeper family ----
    "shot_stop": {
        "label": "Shot-stopping", "unit": "prevented/90", "invert": False,
        "desc": "Goals prevented versus the xG his team faced while he was on "
                "the pitch, per 90. Understat xG is pre-shot, so this is the "
                "standard keeper over/under-performance proxy — real signal, "
                "noisy season to season."},
    "clean_sheet": {
        "label": "Clean sheets", "unit": "%", "invert": False,
        "desc": "Share of his 60'+ appearances conceding zero — the keeper's "
                "bottom-line dependability stat."},
}

# overlap families: metrics in one family partly COUNT THE SAME THING
# (user caught the xG triangle 2026-09-15: xG+xA floor / xG-per-shot /
# xGChain floor). The config UI warns when a recipe stacks siblings.
FAMILY: Dict[str, str] = {
    "avail": "presence", "minutes_share": "presence",
    "starter_share": "presence", "finish_starts": "presence",
    "floor_chain": "xg_involve", "cons_chain": "xg_involve",
    "buildup90": "xg_involve",
    "big_games": "context", "travels": "context",
    "floor_xgxa": "chance_quality", "box_presence": "chance_quality",
    "shot_selection": "chance_quality",
    "delivery": "finishing", "sot_share": "finishing",
    "assist_delivery": "creation", "kp90": "creation",
    "killer90": "creation", "cross_created90": "creation",
    "takeon90": "initiative", "fld90": "initiative",
    "discipline": "cleanliness", "fls90": "cleanliness",
    "aerial90": "dead_ball", "sp_threat": "dead_ball",
    "tklw90": "ball_winning", "int90": "ball_winning",
    "shot_stop": "gk_stopping", "gk_save_pct": "gk_stopping",
    "clean_sheet": "gk_outcome",
}
FAMILY_LABEL: Dict[str, str] = {
    "presence": "presence/minutes (all measure 'plays a lot')",
    "xg_involve": "xG-involvement (all derived from xGChain)",
    "context": "context ratios (vs own norm)",
    "chance_quality": "chance quality (good chances ≈ in-box ≈ high xG/shot)",
    "finishing": "finishing execution (G v xG ≈ on-target rate)",
    "creation": "creation (assists v xA ≈ key-pass volume)",
    "initiative": "initiative/contact",
    "cleanliness": "cleanliness (fouls ≈ cards)",
    "dead_ball": "dead-ball threat (headers ≈ set-piece shots)",
    "ball_winning": "ball-winning (tackles ≈ interceptions)",
    "gk_stopping": "shot-stopping (xG proxy vs real Save% — same construct!)",
    "gk_outcome": "defensive outcome",
}

# per-role default recipes — you can't expect a defender to attack his man
DEFAULT_ROLE_COMPONENTS: Dict[str, List[Dict[str, Any]]] = {
    # gate era (2026-09-15): presence is an eligibility gate, so no presence
    # metric is scored anywhere; recipes lean on the fbref counting family
    # and shot-event mining, at most one metric per family unless the two
    # halves are genuinely different skills (tackles vs interceptions).
    "GK": [
        {"key": "gk_save_pct", "weight": 30, "enabled": True},
        {"key": "clean_sheet", "weight": 22, "enabled": True},
        {"key": "buildup90", "weight": 12, "enabled": True},
        {"key": "discipline", "weight": 8, "enabled": True},
        {"key": "shot_stop", "weight": 15, "enabled": False},
        {"key": "big_games", "weight": 8, "enabled": False},
        {"key": "travels", "weight": 8, "enabled": False},
        {"key": "cons_chain", "weight": 5, "enabled": False},
        {"key": "fls90", "weight": 5, "enabled": False},
        {"key": "avail", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 10, "enabled": False},
        {"key": "starter_share", "weight": 8, "enabled": False},
        {"key": "finish_starts", "weight": 5, "enabled": False},
    ],
    "DEF": [
        {"key": "tklw90", "weight": 18, "enabled": True},
        {"key": "discipline", "weight": 14, "enabled": True},
        {"key": "int90", "weight": 12, "enabled": True},
        {"key": "clean_sheet", "weight": 12, "enabled": True},
        {"key": "aerial90", "weight": 10, "enabled": True},
        {"key": "big_games", "weight": 10, "enabled": True},
        {"key": "buildup90", "weight": 8, "enabled": True},
        {"key": "cross_created90", "weight": 6, "enabled": True},
        {"key": "fld90", "weight": 5, "enabled": True},
        {"key": "shot_stop", "weight": 10, "enabled": False},
        {"key": "fls90", "weight": 8, "enabled": False},
        {"key": "floor_chain", "weight": 8, "enabled": False},
        {"key": "travels", "weight": 8, "enabled": False},
        {"key": "cons_chain", "weight": 6, "enabled": False},
        {"key": "sp_threat", "weight": 6, "enabled": False},
        {"key": "killer90", "weight": 5, "enabled": False},
        {"key": "floor_xgxa", "weight": 5, "enabled": False},
        {"key": "delivery", "weight": 5, "enabled": False},
        {"key": "takeon90", "weight": 4, "enabled": False},
        {"key": "avail", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 10, "enabled": False},
        {"key": "starter_share", "weight": 8, "enabled": False},
        {"key": "finish_starts", "weight": 5, "enabled": False},
    ],
    "MID": [
        {"key": "floor_chain", "weight": 16, "enabled": True},
        {"key": "big_games", "weight": 12, "enabled": True},
        {"key": "killer90", "weight": 12, "enabled": True},
        {"key": "tklw90", "weight": 10, "enabled": True},
        {"key": "discipline", "weight": 10, "enabled": True},
        {"key": "fld90", "weight": 10, "enabled": True},
        {"key": "int90", "weight": 8, "enabled": True},
        {"key": "floor_xgxa", "weight": 8, "enabled": True},
        {"key": "buildup90", "weight": 8, "enabled": False},
        {"key": "travels", "weight": 8, "enabled": False},
        {"key": "cons_chain", "weight": 6, "enabled": False},
        {"key": "kp90", "weight": 6, "enabled": False},
        {"key": "fls90", "weight": 6, "enabled": False},
        {"key": "assist_delivery", "weight": 5, "enabled": False},
        {"key": "cross_created90", "weight": 5, "enabled": False},
        {"key": "sot_share", "weight": 5, "enabled": False},
        {"key": "delivery", "weight": 5, "enabled": False},
        {"key": "aerial90", "weight": 5, "enabled": False},
        {"key": "takeon90", "weight": 4, "enabled": False},
        {"key": "sp_threat", "weight": 4, "enabled": False},
        {"key": "avail", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 10, "enabled": False},
        {"key": "starter_share", "weight": 8, "enabled": False},
        {"key": "finish_starts", "weight": 5, "enabled": False},
    ],
    "ATT": [
        {"key": "delivery", "weight": 18, "enabled": True},
        {"key": "box_presence", "weight": 16, "enabled": True},
        {"key": "big_games", "weight": 14, "enabled": True},
        {"key": "takeon90", "weight": 10, "enabled": True},
        {"key": "aerial90", "weight": 8, "enabled": True},
        {"key": "killer90", "weight": 8, "enabled": True},
        {"key": "discipline", "weight": 4, "enabled": True},
        {"key": "sot_share", "weight": 8, "enabled": False},
        {"key": "floor_xgxa", "weight": 8, "enabled": False},
        {"key": "fld90", "weight": 8, "enabled": False},
        {"key": "travels", "weight": 8, "enabled": False},
        {"key": "shot_selection", "weight": 6, "enabled": False},
        {"key": "floor_chain", "weight": 5, "enabled": False},
        {"key": "cons_chain", "weight": 5, "enabled": False},
        {"key": "kp90", "weight": 5, "enabled": False},
        {"key": "assist_delivery", "weight": 5, "enabled": False},
        {"key": "cross_created90", "weight": 5, "enabled": False},
        {"key": "sp_threat", "weight": 5, "enabled": False},
        {"key": "fls90", "weight": 4, "enabled": False},
        {"key": "tklw90", "weight": 4, "enabled": False},
        {"key": "int90", "weight": 3, "enabled": False},
        {"key": "avail", "weight": 10, "enabled": False},
        {"key": "minutes_share", "weight": 10, "enabled": False},
        {"key": "starter_share", "weight": 8, "enabled": False},
        {"key": "finish_starts", "weight": 5, "enabled": False},
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
                    stored = roles.get(role)
                    if stored is None:  # role added later (GK) -> full defaults
                        out[role] = [dict(c) for c in DEFAULT_ROLE_COMPONENTS[role]]
                        continue
                    comps = [c for c in stored if c.get("key") in METRICS]
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
        "evid": round(total_min / 90.0, 1),  # minutes-worth of full matches
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
        "shot_stop": round((sum(a.get("xga", 0.0) for a in apps)
                            - sum(a.get("conc", 0) for a in apps))
                           * 90.0 / total_min, 2),
        "clean_sheet": round(sum(1 for a in apps if a["minutes"] >= 60
                                 and a.get("conc", 0) == 0)
                             / max(1, sum(1 for a in apps if a["minutes"] >= 60)) * 100),
        "killer90": round(shots.get("killer", 0) * 90.0 / total_min, 2),
        "cross_created90": round(shots.get("cross_cr", 0) * 90.0 / total_min, 2),
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
                   roles_cfg: Dict[str, List[Dict[str, Any]]] = None,
                   min_share: int = 60) -> Dict[str, Any]:
    """min_share: eligibility GATE (user decision 2026-09-15) — a player must
    have played at least this % of his team's possible minutes (recency-
    weighted, counted from his first appearance for the current club, so a
    January signing playing every minute qualifies at once). Presence is a
    condition for being ranked, not a scored trait — percentiles are computed
    within the ELIGIBLE pool only."""
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

        # per-player behavioral shot counts (the mental family) + per-match
        # defensive lines (xG faced / goals conceded per side) for keepers
        shot_agg: Dict[str, Dict[str, float]] = {}
        defense: Dict[tuple, Dict[str, list]] = {}
        for season in seasons:
            sh = ShotEventsService.load(league, season)
            for sm in (sh or {}).get("matches", {}).values():
                dkey = (sm["date"], sm["home_team"], sm["away_team"])
                dd = defense.setdefault(dkey, {"h": [0.0, 0], "a": [0.0, 0]})
                for s in sm["shots"]:
                    side_def = "a" if s.get("side") == "h" else "h"
                    dd[side_def][0] += s.get("xg") or 0.0
                    if s.get("result") in ("Goal", "OwnGoal"):
                        dd[side_def][1] += 1
                    name = s.get("player")
                    if not name or s.get("result") == "OwnGoal":
                        continue
                    ast = s.get("assist_player")
                    if ast:
                        b = shot_agg.setdefault(ast, {"takeon": 0, "aerial": 0,
                                                      "box": 0, "sp": 0, "shot_xg": 0.0})
                        la_ = s.get("last_action")
                        if la_ in ("Throughball", "Chipped", "LayOff"):
                            b["killer"] = b.get("killer", 0) + 1
                        elif la_ == "Cross":
                            b["cross_cr"] = b.get("cross_cr", 0) + 1
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

        # fbref counting stats, both seasons summed, keyed by normalized name
        from services.fbref.player_stats_service import (FbrefPlayerStatsService,
                                                         norm_name)
        fbp: Dict[str, Dict] = {}
        for season in seasons:
            d = FbrefPlayerStatsService.load(league, season)
            for nm, p in (d or {}).get("players", {}).items():
                k = norm_name(nm)
                agg = fbp.setdefault(k, {"n90s": 0.0})
                agg["n90s"] += p.get("n90s") or 0.0
                for f in ("tklw", "int", "fld", "fls", "sh", "sot",
                          "sota", "saves"):
                    agg[f] = agg.get(f, 0.0) + (p.get(f) or 0.0)
        last_idx: Dict[str, list] = {}
        for k in fbp:
            last_idx.setdefault(k.split()[-1], []).append(k)

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
                    d = defense.get((m["date"], m["home_team"], m["away_team"]),
                                    {"h": [0.0, 0], "a": [0.0, 0]})[side]
                    e = players.setdefault(p["player"], {"apps": [], "pos": {}})
                    e["apps"].append({
                        "date": m["date"], "team": team, "opp": opp,
                        "xga": d[0], "conc": d[1],
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
            if not bucket:
                continue
            m = _player_metrics(e["apps"], team_dates, shot_agg.get(name, {}), top6)
            if not m:
                continue
            if m["minutes_share"] < min_share:
                continue  # presence is the gate, not a score
            fb = fbp.get(norm_name(name))
            if fb is None:
                cands = last_idx.get(norm_name(name).split()[-1], [])
                fb = fbp[cands[0]] if len(cands) == 1 else None
            n90 = fb["n90s"] if fb else 0.0

            def _p90(f):
                return round(fb[f] / n90, 2) if fb and n90 >= 3 else None
            m.update({
                "tklw90": _p90("tklw"), "int90": _p90("int"),
                "fld90": _p90("fld"), "fls90": _p90("fls"),
                "sot_share": round(fb["sot"] / fb["sh"] * 100)
                if fb and fb.get("sh", 0) >= 8 else None,
                "gk_save_pct": round(fb["saves"] / fb["sota"] * 100, 1)
                if bucket == "GK" and fb and fb.get("sota", 0) >= 10 else None,
            })
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
                have = [r for r in grp if r.get(key) is not None]
                for r in grp:  # no fbref name-join / below sample floor:
                    if r.get(key) is None:  # neutral, never punished
                        r[f"{key}_p"] = 50.0
                nh = len(have)
                if nh < 2:
                    for r in have:
                        r[f"{key}_p"] = 50.0
                    continue
                ordered = sorted(have, key=lambda r: r[key],
                                 reverse=METRICS[key]["invert"])
                i = 0
                while i < nh:
                    j = i
                    while j + 1 < nh and ordered[j + 1][key] == ordered[i][key]:
                        j += 1
                    avg_p = (i + j) / 2.0 / (nh - 1) * 100
                    for k in range(i, j + 1):
                        ordered[k][f"{key}_p"] = avg_p
                    i = j + 1
            for r in grp:
                raw = sum(c["weight"] / w_sum[bucket] * r[f"{c['key']}_p"]
                          for c in comps)
                kept = r["evid"] / (r["evid"] + K_EVIDENCE)
                r["score_raw"] = round(raw, 1)
                r["kept_pct"] = round(kept * 100)
                r["score"] = round(50.0 + (raw - 50.0) * kept, 1)
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
