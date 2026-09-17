"""The metric bank, computed from Opta event streams.

Replaces the eight-number placeholder with what the events actually support.
Every metric is defined here once, with a label, a unit, whether higher is
better, and an honest description — the same contract the old mental bank
used, so a config page can render it without knowing anything about events.

Notable: aerial duels split into OFFENSIVE and DEFENSIVE. The previous
system could only ever see attacking headers ("defensive duels aren't
published by any free source"); the event stream carries both.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

import numpy as np
import pandas as pd

# pitch is 0-100 in both directions, attacking left -> right
FINAL_THIRD = 66.7
BOX_X, BOX_Y_LO, BOX_Y_HI = 83.0, 21.1, 78.9
PROGRESSIVE_GAIN = 10.0        # metres of pitch (in 0-100 units) up the field
SWITCH_WIDTH = 35.0            # lateral shift that counts as a switch

METRICS: Dict[str, Dict[str, Any]] = {
    # ---- intent on the ball -------------------------------------------
    "takeon_90": {"label": "Runs at his man", "unit": "/90", "invert": False,
                  "group": "intent",
                  "desc": "Attacking take-ons attempted per 90. Attempts, not "
                          "completions — trying is the trait that repeats."},
    "takeon_pct": {"label": "Beats his man", "unit": "%", "invert": False,
                   "group": "intent",
                   "desc": "Share of take-ons completed. Noisier than the "
                           "attempt rate; treat gently."},
    "overrun_90": {"label": "Overruns it", "unit": "/90", "invert": True,
                   "group": "intent",
                   "desc": "Take-ons where he ran the ball too far, per 90."},
    "dispossessed_90": {"label": "Loses it", "unit": "/90", "invert": True,
                        "group": "intent",
                        "desc": "Dispossessed per 90 — tackled out of "
                                "possession while carrying."},
    "carry_box_90": {"label": "Carries into the box", "unit": "/90",
                     "invert": False, "group": "intent",
                     "desc": "Take-ons completed inside the penalty area per 90."},
    # ---- creation ------------------------------------------------------
    "keypass_90": {"label": "Key passes", "unit": "/90", "invert": False,
                   "group": "creation",
                   "desc": "Passes that directly set up a shot, per 90."},
    "bigchance_90": {"label": "Big chances created", "unit": "/90",
                     "invert": False, "group": "creation",
                     "desc": "Passes that created a chance Opta rates as big."},
    "box_pass_90": {"label": "Passes into the box", "unit": "/90",
                    "invert": False, "group": "creation",
                    "desc": "Completed passes finishing inside the penalty "
                            "area, per 90."},
    "cross_90": {"label": "Crosses", "unit": "/90", "invert": False,
                 "group": "creation",
                 "desc": "Crosses attempted per 90."},
    "cross_pct": {"label": "Crosses that find a man", "unit": "%",
                  "invert": False, "group": "creation",
                  "desc": "Share of crosses completed — delivery quality "
                          "rather than volume."},
    "throughball_90": {"label": "Through balls", "unit": "/90", "invert": False,
                       "group": "creation",
                       "desc": "Passes played through the defensive line."},
    # ---- progression ---------------------------------------------------
    "prog_pass_90": {"label": "Progressive passes", "unit": "/90",
                     "invert": False, "group": "progression",
                     "desc": "Completed passes moving the ball meaningfully "
                             "up the pitch."},
    "final_third_90": {"label": "Into the final third", "unit": "/90",
                       "invert": False, "group": "progression",
                       "desc": "Completed passes entering the final third."},
    "switch_90": {"label": "Switches of play", "unit": "/90", "invert": False,
                  "group": "progression",
                  "desc": "Long passes that change the side of the pitch."},
    "longball_pct": {"label": "Long balls that stick", "unit": "%",
                     "invert": False, "group": "progression",
                     "desc": "Completion rate of long passes."},
    # ---- keeping the ball ----------------------------------------------
    "pass_90": {"label": "On the ball", "unit": "/90", "invert": False,
                "group": "possession",
                "desc": "Passes attempted per 90 — involvement, not quality."},
    "pass_pct": {"label": "Keeps possession", "unit": "%", "invert": False,
                 "group": "possession",
                 "desc": "Pass completion. Flattered by safe, short passing."},
    "touch_box_90": {"label": "Touches in the box", "unit": "/90",
                     "invert": False, "group": "possession",
                     "desc": "Any touch inside the opposition penalty area."},
    # ---- duels: ground and air kept apart, because they are different
    # jobs. A small technical midfielder can dominate on the floor and lose
    # everything in the air; lumping them together hides exactly that.
    "ground_duel_90": {"label": "Ground duels", "unit": "/90", "invert": False,
                       "group": "duels",
                       "desc": "Tackles and challenges contested per 90 — "
                               "duels on the floor, air excluded."},
    "ground_duel_pct": {"label": "Ground duels won", "unit": "%",
                        "invert": False, "group": "duels",
                        "desc": "Share of ground duels won. A challenge is a "
                                "duel he was beaten in, so it counts against."},
    "aerial_90": {"label": "Aerial duels", "unit": "/90", "invert": False,
                  "group": "duels",
                  "desc": "All aerial duels contested per 90, both ends."},
    "aerial_pct": {"label": "Aerial duels won", "unit": "%", "invert": False,
                   "group": "duels", "desc": "Share of aerial duels won."},
    "aerial_def_90": {"label": "Defensive headers", "unit": "/90",
                      "invert": False, "group": "duels",
                      "desc": "Aerial duels contested while defending. Not "
                              "available from free sources before events."},
    "aerial_def_pct": {"label": "Defensive headers won", "unit": "%",
                       "invert": False, "group": "duels",
                       "desc": "Win rate in defensive aerial duels."},
    "aerial_att_90": {"label": "Attacking headers", "unit": "/90",
                      "invert": False, "group": "duels",
                      "desc": "Aerial duels contested while attacking."},
    "aerial_att_pct": {"label": "Attacking headers won", "unit": "%",
                       "invert": False, "group": "duels",
                       "desc": "Win rate in attacking aerial duels."},
    "tackle_90": {"label": "Tackles", "unit": "/90", "invert": False,
                  "group": "defending", "desc": "Tackles attempted per 90."},
    "tackle_pct": {"label": "Tackles won", "unit": "%", "invert": False,
                   "group": "defending",
                   "desc": "Share of tackles that won the ball."},
    "interception_90": {"label": "Reads the game", "unit": "/90",
                        "invert": False, "group": "defending",
                        "desc": "Interceptions per 90 — being where the pass "
                                "was going."},
    "clearance_90": {"label": "Clearances", "unit": "/90", "invert": False,
                     "group": "defending",
                     "desc": "Clearances per 90. High for deep defences; read "
                             "with the team in mind."},
    "recovery_90": {"label": "Wins it back", "unit": "/90", "invert": False,
                    "group": "defending",
                    "desc": "Loose balls recovered per 90."},
    "lastman_90": {"label": "Last-man tackles", "unit": "/90", "invert": False,
                   "group": "defending",
                   "desc": "Tackles made as the last defender."},
    "press_height": {"label": "Defends high", "unit": "x", "invert": False,
                     "group": "defending",
                     "desc": "Average pitch position of his defensive actions "
                             "(0 = own goal line, 100 = theirs)."},
    # ---- discipline and mistakes ---------------------------------------
    "foul_90": {"label": "Fouls", "unit": "/90", "invert": True,
                "group": "discipline", "desc": "Fouls conceded per 90."},
    "card_90": {"label": "Cards", "unit": "/90", "invert": True,
                "group": "discipline",
                "desc": "Bookings per 90 (a red counts as three)."},
    "error_90": {"label": "Errors", "unit": "/90", "invert": True,
                 "group": "discipline",
                 "desc": "Mistakes Opta flags as leading to a shot. Rare, so "
                         "unreliable over a single season."},
    "fouled_90": {"label": "Gets fouled", "unit": "/90", "invert": False,
                  "group": "discipline",
                  "desc": "Fouls won per 90 — carries into contact."},
}

GROUP_LABEL = {
    "intent": "Intent on the ball", "creation": "Creation",
    "progression": "Progression", "possession": "Keeping it",
    "duels": "Duels", "defending": "Defending", "discipline": "Discipline",
}

DUEL_TYPES = ("Aerial", "Tackle", "Challenge")


def _qnames(q) -> set:
    try:
        return {x["type"]["displayName"] for x in q}
    except Exception:
        return set()


def _in_box(x, y) -> bool:
    return x is not None and x >= BOX_X and BOX_Y_LO <= y <= BOX_Y_HI


# Defensive work depends on the opponent having the ball, attacking work on
# your own team having it. A defender at a dominant side contests ~18% fewer
# duels simply because opponents hold the ball less — measured across the top
# three clubs. So these are additionally expressed per OPPORTUNITY: scaled to
# what the player would do in an even, 50/50 game.
DEFENSIVE_KEYS = {"tackle_90", "interception_90", "clearance_90", "recovery_90",
                  "ground_duel_90", "aerial_def_90", "lastman_90"}
ATTACKING_KEYS = {"takeon_90", "keypass_90", "cross_90", "box_pass_90",
                  "prog_pass_90", "final_third_90", "touch_box_90",
                  "carry_box_90", "pass_90", "dispossessed_90",
                  "bigchance_90", "throughball_90", "switch_90",
                  "aerial_att_90", "carry_box_90"}


def accumulate(match: pd.DataFrame, acc: dict, minutes: dict | None = None) -> None:
    """Add one match's events into the running per-player totals.

    `minutes` (player -> minutes played in THIS match) lets us bank each
    player's exposure to his own team's possession and to the opponent's,
    which is what the possession-adjusted rates are built on."""
    if minutes:
        touches = match[match["is_touch"] == True].groupby("team").size()  # noqa: E712
        total = float(touches.sum()) or 1.0
        share = (touches / total).to_dict()
        team_of = match.dropna(subset=["player"]).groupby("player")["team"].first()
        for player, played in minutes.items():
            own = share.get(team_of.get(player), 0.5)
            acc[player]["own_poss_min"] += played * own
            acc[player]["opp_poss_min"] += played * (1.0 - own)

    ev = match.dropna(subset=["player"])
    for row in ev.itertuples(index=False):
        a = acc[row.player]
        t, ok = row.type, row.outcome_type == "Successful"
        q = _qnames(row.qualifiers)

        if t == "Pass":
            a["pass_att"] += 1
            a["pass_ok"] += ok
            if "KeyPass" in q:
                a["keypass"] += 1
            if "BigChanceCreated" in q:
                a["bigchance"] += 1
            if "Cross" in q:
                a["cross_att"] += 1
                a["cross_ok"] += ok
            if "Throughball" in q:
                a["throughball"] += 1
            if "Longball" in q:
                a["long_att"] += 1
                a["long_ok"] += ok
                if row.end_y is not None and row.y is not None and \
                        abs(row.end_y - row.y) >= SWITCH_WIDTH:
                    a["switch"] += 1
            if ok and row.end_x is not None:
                if row.end_x - row.x >= PROGRESSIVE_GAIN and row.end_x >= 50:
                    a["prog_pass"] += 1
                if row.x < FINAL_THIRD <= row.end_x:
                    a["final_third"] += 1
                if _in_box(row.end_x, row.end_y):
                    a["box_pass"] += 1
        elif t == "TakeOn":
            if "Defensive" not in q:           # attacking take-ons only
                a["takeon_att"] += 1
                a["takeon_ok"] += ok
                if ok and _in_box(row.x, row.y):
                    a["carry_box"] += 1
            if "OverRun" in q:
                a["overrun"] += 1
        elif t == "Aerial":
            if "Defensive" in q:
                a["aerial_def_att"] += 1
                a["aerial_def_ok"] += ok
            else:
                a["aerial_att_att"] += 1
                a["aerial_att_ok"] += ok
        elif t == "Tackle":
            a["tackle_att"] += 1
            a["tackle_ok"] += ok
            if "LastMan" in q:
                a["lastman"] += 1
        elif t == "Interception":
            a["interception"] += 1
        elif t == "Clearance":
            a["clearance"] += 1
        elif t == "BallRecovery":
            a["recovery"] += 1
        elif t == "Dispossessed":
            a["dispossessed"] += 1
        elif t == "Foul":
            # Opta logs the offence on the offender and the win on the victim
            if ok:
                a["fouled"] += 1
            else:
                a["foul"] += 1
        elif t == "Card":
            a["card"] += 3 if row.card_type in ("Red", "SecondYellow") else 1
        elif t == "Error":
            a["error"] += 1

        if t in ("Tackle", "Challenge"):
            a["ground_duel_att"] += 1
            a["ground_duel_ok"] += ok
        elif t == "Aerial":
            a["aerial_all_att"] += 1
            a["aerial_all_ok"] += ok
        if t in ("Tackle", "Interception", "Clearance", "BallRecovery"):
            if row.x is not None:
                a["def_x_sum"] += row.x
                a["def_x_n"] += 1
        if row.is_touch and _in_box(row.x, row.y):
            a["touch_box"] += 1


def finalise(acc: dict, minutes: dict, min_minutes: int) -> pd.DataFrame:
    """Turn raw counts into the published bank: rates per 90 and win rates."""
    rows = []
    for player, a in acc.items():
        mins = minutes.get(player, 0.0)
        if mins < min_minutes:
            continue
        p90 = lambda k: a.get(k, 0) / mins * 90                     # noqa: E731

        def pct(ok, att, floor=15):
            n = a.get(att, 0)
            return (a.get(ok, 0) / n * 100) if n >= floor else np.nan

        rows.append({
            "player": player, "minutes": round(mins),
            "takeon_90": p90("takeon_att"), "takeon_pct": pct("takeon_ok", "takeon_att"),
            "overrun_90": p90("overrun"), "dispossessed_90": p90("dispossessed"),
            "carry_box_90": p90("carry_box"),
            "keypass_90": p90("keypass"), "bigchance_90": p90("bigchance"),
            "box_pass_90": p90("box_pass"), "cross_90": p90("cross_att"),
            "cross_pct": pct("cross_ok", "cross_att"),
            "throughball_90": p90("throughball"),
            "prog_pass_90": p90("prog_pass"), "final_third_90": p90("final_third"),
            "switch_90": p90("switch"), "longball_pct": pct("long_ok", "long_att"),
            "pass_90": p90("pass_att"), "pass_pct": pct("pass_ok", "pass_att", 50),
            "touch_box_90": p90("touch_box"),
            "ground_duel_90": p90("ground_duel_att"),
            "ground_duel_pct": pct("ground_duel_ok", "ground_duel_att", 20),
            "aerial_90": p90("aerial_all_att"),
            "aerial_pct": pct("aerial_all_ok", "aerial_all_att", 20),
            "aerial_def_90": p90("aerial_def_att"),
            "aerial_def_pct": pct("aerial_def_ok", "aerial_def_att"),
            "aerial_att_90": p90("aerial_att_att"),
            "aerial_att_pct": pct("aerial_att_ok", "aerial_att_att"),
            "tackle_90": p90("tackle_att"), "tackle_pct": pct("tackle_ok", "tackle_att"),
            "interception_90": p90("interception"), "clearance_90": p90("clearance"),
            "recovery_90": p90("recovery"), "lastman_90": p90("lastman"),
            "press_height": (a["def_x_sum"] / a["def_x_n"]) if a.get("def_x_n") else np.nan,
            "foul_90": p90("foul"), "card_90": p90("card"),
            "error_90": p90("error"), "fouled_90": p90("fouled"),
        })
    return pd.DataFrame(rows).set_index("player")


def possession_adjust(bank: pd.DataFrame, acc: dict) -> pd.DataFrame:
    """Re-express rates per OPPORTUNITY instead of per minute.

    A defensive action needs the opponent to have the ball; an attacking one
    needs your own team to. Scaling each to an even 50/50 game stops a
    player being penalised — or flattered — by how much of the ball his team
    happens to enjoy."""
    out = bank.copy()
    for player in bank.index:
        a = acc.get(player, {})
        own, opp = a.get("own_poss_min", 0.0), a.get("opp_poss_min", 0.0)
        mins = own + opp
        if mins <= 0:
            continue
        # a 50/50 game gives each side half the minutes-of-possession
        def_scale = (mins * 0.5 / opp) if opp > 0 else 1.0
        att_scale = (mins * 0.5 / own) if own > 0 else 1.0
        for key in DEFENSIVE_KEYS & set(out.columns):
            out.at[player, key] = bank.at[player, key] * def_scale
        for key in ATTACKING_KEYS & set(out.columns):
            out.at[player, key] = bank.at[player, key] * att_scale
    return out


def new_accumulator() -> dict:
    return defaultdict(lambda: defaultdict(float))
