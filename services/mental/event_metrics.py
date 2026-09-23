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
DEF_THIRD = 33.3
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
    # ---- shooting ------------------------------------------------------
    # Penalties are excluded from every rate here. They are converted about
    # four times in five by whoever takes them, so including them measures
    # who the manager trusts from twelve yards rather than how a player
    # shoots. The penalty itself is not lost — it is counted in the decisive
    # acts, where a spot-kick in the 89th at 1-1 is exactly the point.
    "shot_90": {"label": "Shots", "unit": "/90", "invert": False,
                "group": "shooting",
                "desc": "Shots attempted per 90, penalties excluded. Volume "
                        "is a choice: whether he takes it on."},
    "shot_box_pct": {"label": "Shoots from in the box", "unit": "%",
                     "invert": False, "group": "shooting",
                     "desc": "Share of his shots taken inside the area. Shot "
                             "selection — the discipline to work a better one "
                             "rather than hit it from 30 yards."},
    "shot_dist": {"label": "Average shot distance", "unit": "m", "invert": True,
                  "group": "shooting",
                  "desc": "How far out he shoots from, in pitch units. The "
                          "same trait as the one above, as a distance."},
    "shot_target_pct": {"label": "Hits the target", "unit": "%",
                        "invert": False, "group": "shooting",
                        "desc": "Share of shots on target — saved, or in."},
    "goal_90": {"label": "Goals", "unit": "/90", "invert": False,
                "group": "shooting",
                "desc": "Non-penalty goals per 90."},
    "conversion_pct": {"label": "Converts", "unit": "%", "invert": False,
                       "group": "shooting",
                       "desc": "Non-penalty goals per shot. Famously the "
                               "least stable number in football — check what "
                               "the gate says for this position before you "
                               "weight it."},
    "bigchance_shot_90": {"label": "Big chances he gets", "unit": "/90",
                          "invert": False, "group": "shooting",
                          "desc": "Chances Opta rates as big that fell to "
                                  "him. Getting into those positions is a "
                                  "repeatable habit; what happens next may "
                                  "not be."},
    "bigchance_conv_pct": {"label": "Takes his big chances", "unit": "%",
                           "invert": False, "group": "shooting",
                           "desc": "Share of big chances he scored. The "
                                   "number everyone reaches for to call a "
                                   "player a bottler, on a sample of about "
                                   "ten a season."},
    "bigchance_missed_90": {"label": "Big chances missed", "unit": "/90",
                            "invert": True, "group": "shooting",
                            "desc": "Big chances that fell to him and did "
                                    "not go in, per 90."},
    # ---- decisive acts --------------------------------------------------
    "decisive_90": {"label": "Decisive acts", "unit": "/90", "invert": False,
                    "group": "decisive",
                    "desc": "Goals, assists, big chances made, saves, "
                            "last-ditch blocks and tackles, penalties won — "
                            "minus own goals, errors, penalties conceded and "
                            "red cards. Valued in goals and netted off. One "
                            "list for every position; what a player is judged "
                            "on sorts itself out, a keeper's being 95% saves "
                            "and a striker's 71% goals."},
    "decisive_lev_90": {"label": "Decisive acts, weighted by the moment",
                        "unit": "/90", "invert": False, "group": "decisive",
                        "desc": "The same, with every act weighted by how "
                                "much the match hung on it. A goal at level "
                                "with five minutes left counts 2.3 times; the "
                                "fourth in a 4-0 counts nothing."},
    "decisive_bad_90": {"label": "Costly mistakes", "unit": "/90",
                        "invert": True, "group": "decisive",
                        "desc": "The negatives alone — own goals, errors, "
                                "penalties conceded, red cards — per 90."},
    "availability_pct": {"label": "Available", "unit": "%", "invert": False,
                         "group": "decisive",
                         "desc": "Share of his club's minutes he was on the "
                                 "pitch for, across the matches his club "
                                 "played while he was there. Being fit and "
                                 "being picked is part of being dependable."},
    # ---- goalkeeping ---------------------------------------------------
    # Without these a keeper was ranked purely on his passing, which is at
    # most half his job. Note which of them are about the keeper and which
    # are about the side in front of him: he does not choose how many shots
    # he faces, so save and concede rates say as much about his defence as
    # about him. What he DOES choose — whether to come for the cross,
    # whether to hold it or parry it, how far off his line he lives — is his.
    "save_pct": {"label": "Saves what he faces", "unit": "%", "invert": False,
                 "group": "keeping",
                 "desc": "Saves as a share of shots on target faced (saves "
                         "plus goals conceded). Heavily driven by the quality "
                         "of chance he faces, which is not his doing."},
    "save_90": {"label": "Saves", "unit": "/90", "invert": False,
                "group": "keeping",
                "desc": "Saves per 90. A busy keeper is usually a keeper "
                        "behind a bad defence."},
    "conceded_90": {"label": "Goals conceded", "unit": "/90", "invert": True,
                    "group": "keeping",
                    "desc": "Goals conceded per 90 while he was on the pitch. "
                            "As much a measure of his team as of him."},
    "catch_pct": {"label": "Holds it", "unit": "%", "invert": False,
                  "group": "keeping",
                  "desc": "Share of saves he catches rather than parries. A "
                          "choice, and a nerve."},
    "parry_danger_pct": {"label": "Parries into danger", "unit": "%",
                         "invert": True, "group": "keeping",
                         "desc": "Of the saves he parries, the share he pushes "
                                 "back into a dangerous area rather than away."},
    "claim_90": {"label": "Comes for crosses", "unit": "/90", "invert": False,
                 "group": "keeping",
                 "desc": "High claims attempted per 90 — command of his box."},
    "claim_pct": {"label": "Claims it cleanly", "unit": "%", "invert": False,
                  "group": "keeping",
                  "desc": "Share of high claims he takes cleanly, counting "
                          "crosses he came for and missed against him."},
    "punch_90": {"label": "Punches", "unit": "/90", "invert": False,
                 "group": "keeping",
                 "desc": "Punches per 90 — the alternative to catching it."},
    "sweeper_90": {"label": "Sweeps behind the line", "unit": "/90",
                   "invert": False, "group": "keeping",
                   "desc": "Actions off his line to clear up behind the "
                           "defence. How high he dares to live."},
    # ---- creation ------------------------------------------------------
    "assist_90": {"label": "Assists", "unit": "/90", "invert": False,
                  "group": "creation",
                  "desc": "Deliberate assists per 90. Opta tags 536 of these "
                          "a season against 690 goals credited as assisted — "
                          "the gap is deflections and knock-downs, where the "
                          "assisting touch was not a chosen pass. Only the "
                          "chosen ones count here. Like goals, an assist "
                          "depends on someone else finishing, so check the "
                          "gate before weighting it heavily."},
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
    # ---- mistakes: the mental cost of giving it away ---------------------
    # Opta's Error flag fires ~1.7 times a match across BOTH teams, so a
    # player collects one or two a season and no rating can stand on it.
    # The same instinct measured on a base twenty times larger: every time
    # he lost the ball through his own doing.
    "error_90": {"label": "Errors (Opta flag)", "unit": "/90", "invert": True,
                 "group": "mistakes",
                 "desc": "Mistakes Opta flags as leading directly to a shot. "
                         "About 1.7 a match across both teams, so a single "
                         "season cannot rank anyone on it — kept visible, but "
                         "it will not repeat."},
    "miscontrol_90": {"label": "Miscontrols", "unit": "/90", "invert": True,
                      "group": "mistakes",
                      "desc": "Touches where the ball got away from him."},
    "giveaway_90": {"label": "Gives it away", "unit": "/90", "invert": True,
                    "group": "mistakes",
                    "desc": "Every loss of possession through his own doing — "
                            "dispossessed, miscontrolled, or an outright "
                            "error. The measurable version of 'he makes "
                            "mistakes'."},
    "giveaway_def_90": {"label": "Gives it away in his own third",
                        "unit": "/90", "invert": True, "group": "mistakes",
                        "desc": "The same, but only where it costs: losses in "
                                "his defensive third, which is where a mistake "
                                "becomes a chance for the opponent."},
    "dribbled_past_90": {"label": "Dribbled past", "unit": "/90",
                         "invert": True, "group": "mistakes",
                         "desc": "Times an opponent beat him one-on-one."},
    "fouled_90": {"label": "Gets fouled", "unit": "/90", "invert": False,
                  "group": "discipline",
                  "desc": "Fouls won per 90 — carries into contact."},
}

GROUP_LABEL = {
    "decisive": "Decisive acts", "intent": "Intent on the ball",
    "shooting": "Shooting", "keeping": "Goalkeeping", "creation": "Creation",
    "progression": "Progression", "possession": "Keeping it",
    "duels": "Duels", "defending": "Defending", "discipline": "Discipline", "mistakes": "Mistakes",
}

DUEL_TYPES = ("Aerial", "Tackle", "Challenge")
SHOT_TYPES = ("Goal", "SavedShot", "MissedShots", "ShotOnPost")
GOAL_X, GOAL_Y = 100.0, 50.0

# ---------------------------------------------------------------------------
# DECISIVE ACTS — the things that actually change a football match.
#
# One universal list for every position, because an action is an action: a
# goal is a goal whoever scores it, and a last-ditch block in the 90th is the
# same act from a striker as from a centre-back. No per-position weighting is
# applied and none is needed — the composition sorts itself out. A keeper's
# decisive acts come out 95% saves and 4% errors, a striker's 71% goals, a
# centre-back's 46% last-ditch defending and 24% mistakes. Nobody is judged
# on goals he was never going to score.
#
# Values are in goals. A shot on target goes in roughly three times in ten,
# so a save is worth about 0.3 of a goal and a last-ditch block on a clear
# chance rather more. A penalty is discounted because winning the spot-kick
# and being trusted to take it are not the same act as making the chance.
# Deliberately excluded, as noise diverted from a player's ordinary totals:
# headers won, duels, take-ons, passes, recoveries, ordinary clearances and
# ordinary tackles. Routine shot blocks are excluded too — 2,765 a season is
# a defender standing in the way, not a decisive act; only the ones Opta tags
# LastMan survive.
DECISIVE = {
    "goal": 1.0,
    "penalty_goal": 0.6,
    "assist": 0.7,
    "bigchance_created": 0.4,
    "save": 0.3,
    "lastman": 0.5,
    "penalty_won": 0.6,
    "own_goal": -1.0,
    "error": -0.5,
    "penalty_conceded": -0.6,
    "red_card": -1.0,
}


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
DEFENSIVE_KEYS = {"save_90", "conceded_90", "claim_90", "punch_90", "dribbled_past_90", "tackle_90", "interception_90", "clearance_90", "recovery_90",
                  "ground_duel_90", "aerial_def_90", "lastman_90"}
ATTACKING_KEYS = {"shot_90", "goal_90", "assist_90", "decisive_90", "decisive_lev_90", "bigchance_shot_90", "bigchance_missed_90",
                  "giveaway_90", "giveaway_def_90", "miscontrol_90", "takeon_90", "keypass_90", "cross_90", "box_pass_90",
                  "prog_pass_90", "final_third_90", "touch_box_90",
                  "carry_box_90", "pass_90", "dispossessed_90",
                  "bigchance_90", "throughball_90", "switch_90",
                  "aerial_att_90", "carry_box_90"}


def decisive_value(event_type, qualifiers, outcome, card) -> float:
    """What this one event was worth, in goals. 0.0 for the vast majority."""
    q = _qnames(qualifiers)
    if event_type == "Goal":
        if "OwnGoal" in q:
            return DECISIVE["own_goal"]
        return DECISIVE["penalty_goal" if "Penalty" in q else "goal"]
    if event_type == "Pass":
        if "IntentionalGoalAssist" in q:
            return DECISIVE["assist"]
        if "BigChanceCreated" in q:
            return DECISIVE["bigchance_created"]
        return 0.0
    if event_type == "Save":
        if "OutfielderBlock" in q:
            # only the last-ditch ones; the rest is standing in the way
            return DECISIVE["lastman"] if "LastMan" in q else 0.0
        return DECISIVE["save"]
    if event_type in ("Tackle", "Interception"):
        return DECISIVE["lastman"] if "LastMan" in q else 0.0
    if event_type == "Foul" and "Penalty" in q:
        return (DECISIVE["penalty_won"] if outcome == "Successful"
                else DECISIVE["penalty_conceded"])
    if event_type == "Error":
        return DECISIVE["error"]
    if event_type == "Card" and card in ("Red", "SecondYellow"):
        return DECISIVE["red_card"]
    return 0.0


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
    has_lev = "w_lev" in ev.columns
    for row in ev.itertuples(index=False):
        a = acc[row.player]
        t, ok = row.type, row.outcome_type == "Successful"
        q = _qnames(row.qualifiers)

        # Decisive acts, plain and weighted by how much the match hung on the
        # moment. Kept apart on purpose: one says what he did, the other when
        # he did it, and the gate gets to judge them separately.
        dv = decisive_value(t, row.qualifiers, row.outcome_type, row.card_type)
        if dv:
            a["decisive"] += dv
            a["decisive_lev"] += dv * (row.w_lev if has_lev else 1.0)
            if dv < 0:
                a["decisive_bad"] += -dv

        if t in SHOT_TYPES:
            # An own goal is the opponent's event on this player's name, and
            # a penalty is a different skill — neither belongs in a shooting
            # rate. Both are counted elsewhere.
            if "OwnGoal" not in q:
                pen = "Penalty" in q
                if not pen:
                    a["shot_att"] += 1
                    a["shot_on"] += t in ("Goal", "SavedShot")
                    if _in_box(row.x, row.y):
                        a["shot_box"] += 1
                    if row.x is not None and row.y is not None:
                        a["shot_dist_sum"] += float(np.hypot(
                            GOAL_X - row.x, (GOAL_Y - row.y) * 0.7))
                        a["shot_dist_n"] += 1
                    if t == "Goal":
                        a["goal"] += 1
                if "BigChance" in q:
                    a["bigchance_shot"] += 1
                    if t == "Goal":
                        a["bigchance_scored"] += 1
                    else:
                        a["bigchance_missed"] += 1

        if t == "Pass":
            a["pass_att"] += 1
            a["pass_ok"] += ok
            if "KeyPass" in q:
                a["keypass"] += 1
            if "IntentionalGoalAssist" in q:
                a["assist"] += 1
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
            a["giveaway"] += 1
            if row.x is not None and row.x < DEF_THIRD:
                a["giveaway_def"] += 1
        elif t == "BallTouch" and not ok:
            a["miscontrol"] += 1
            a["giveaway"] += 1
            if row.x is not None and row.x < DEF_THIRD:
                a["giveaway_def"] += 1
        elif t == "Challenge":
            a["dribbled_past"] += 1
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
            a["giveaway"] += 1
            if row.x is not None and row.x < DEF_THIRD:
                a["giveaway_def"] += 1
        elif t == "Save":
            # An outfielder throwing himself in front of a shot is logged as
            # a Save too. That is a block, not goalkeeping.
            if "OutfielderBlock" not in q:
                a["save"] += 1
                if "Collected" in q:
                    a["save_caught"] += 1
                if "ParriedSafe" in q or "ParriedDanger" in q:
                    a["save_parried"] += 1
                    if "ParriedDanger" in q:
                        a["parried_danger"] += 1
        elif t == "Claim":
            a["claim_att"] += 1
            a["claim_ok"] += ok
        elif t == "CrossNotClaimed":
            a["claim_att"] += 1          # he came for it and did not get it
        elif t == "Punch":
            a["punch"] += 1
        elif t == "KeeperSweeper":
            a["sweeper"] += 1

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
        # `<= 0` as well as the bar: the caller may pass a bar of zero
        # when it is filtering on a share of the club's minutes instead,
        # and a per-90 of nothing divides by nothing.
        if mins <= 0 or mins < min_minutes:
            continue
        p90 = lambda k: a.get(k, 0) / mins * 90                     # noqa: E731

        def pct(ok, att, floor=15):
            n = a.get(att, 0)
            return (a.get(ok, 0) / n * 100) if n >= floor else np.nan

        # Shots on target faced = the ones he saved plus the ones he did not.
        # `conceded` is banked by the caller, because a goal is scored by the
        # opponent and never appears on the keeper's own events.
        #
        # Every player carries a `conceded` count — goals let in while he was
        # on the pitch — so without the save floor an outfielder would report
        # a save percentage of 0% off a denominator of thirty rather than the
        # blank he deserves.
        a["shots_faced"] = ((a.get("save", 0) + a.get("conceded", 0))
                            if a.get("save", 0) >= 10 else 0)

        rows.append({
            "player": player, "minutes": round(mins),
            "decisive_90": p90("decisive"),
            "decisive_lev_90": p90("decisive_lev"),
            "decisive_bad_90": p90("decisive_bad"),
            "availability_pct": np.nan,
            "save_pct": pct("save", "shots_faced", 20),
            "save_90": p90("save"), "conceded_90": p90("conceded"),
            "catch_pct": pct("save_caught", "save", 15),
            "parry_danger_pct": pct("parried_danger", "save_parried", 10),
            "claim_90": p90("claim_att"),
            "claim_pct": pct("claim_ok", "claim_att", 10),
            "punch_90": p90("punch"), "sweeper_90": p90("sweeper"),
            "shot_90": p90("shot_att"),
            "shot_box_pct": pct("shot_box", "shot_att", 10),
            "shot_dist": ((a["shot_dist_sum"] / a["shot_dist_n"])
                          if a.get("shot_dist_n", 0) >= 10 else np.nan),
            "shot_target_pct": pct("shot_on", "shot_att", 10),
            "goal_90": p90("goal"),
            "conversion_pct": pct("goal", "shot_att", 15),
            "bigchance_shot_90": p90("bigchance_shot"),
            "bigchance_conv_pct": pct("bigchance_scored", "bigchance_shot", 6),
            "bigchance_missed_90": p90("bigchance_missed"),
            "takeon_90": p90("takeon_att"), "takeon_pct": pct("takeon_ok", "takeon_att"),
            "overrun_90": p90("overrun"), "dispossessed_90": p90("dispossessed"),
            "carry_box_90": p90("carry_box"),
            "assist_90": p90("assist"),
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
            "miscontrol_90": p90("miscontrol"),
            "giveaway_90": p90("giveaway"),
            "giveaway_def_90": p90("giveaway_def"),
            "dribbled_past_90": p90("dribbled_past"),
        })
    if not rows:
        # a part-played season can leave a bucket with nobody over the
        # bar; an empty table is the right answer, not a crash
        return pd.DataFrame(columns=["player"]).set_index("player")
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
