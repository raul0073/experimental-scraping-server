"""What a team does, and how well — measured per team per match.

The base grain is the MATCH, deliberately. Manager spells and seasons cut
across each other rather than nesting — Glasner's 90 matches span three
seasons, Chelsea's 24/25 spans two managers — so neither can be built from
the other. Measured per match, any cut is a groupby.

Three kinds of number, kept apart because they answer different questions:

    STYLE     how the side plays, split by phase. Long or short, high or
              deep. There is no good or bad here and it is NEVER ranked — a
              table that ranks directness is asserting that one way of
              playing football is correct, which is an opinion wearing a
              number.
    QUALITY   how well it goes. The only thing weighted.
    RESULT    points and goal difference. Shown beside the score, never
              inside it: a ranking that scores points partly becomes the
              league table, and the whole value of this layer is that it
              beats the league table. Measured directly — a side's points in
              the first half of a season predict its second half at 0.59,
              while a six-metric process blend manages 0.78.

SET PIECES ARE SPLIT OUT. 32% of shots and 35% of goals come from one, and
the spread between sides is enormous, so mixing them means crediting a corner
routine and an open-play move as the same capability. Arsenal are the best
set-piece side in the league on output — 0.52 goals a match from them, the
highest — and that was invisible while the two were pooled.

NOTHING STYLE-CONDITIONAL IS RANKED. "Do their long balls stick" only means
something if they play long; "do they play out cleanly" only if they build
from the back. Those measure a choice, not a quality, so they live in style
or nowhere. What survives is what does not care how you got there: did you
reach the box, make a big chance, take a shot, move it up the pitch — and the
four conceded equivalents.

OPPONENT ADJUSTMENT. Every quality metric is fitted across the whole league
at once as

    value in match = league mean + what this team brings
                                 + what this opponent allows
                                 + home advantage

by alternating means. Fitting it per spell instead would measure every
manager against a different baseline, which is the trap.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

import numpy as np
import pandas as pd

FINAL_THIRD = 66.7
DEF_THIRD = 33.3
BOX_X, BOX_Y_LO, BOX_Y_HI = 83.0, 21.1, 78.9
WIDE_LO, WIDE_HI = 21.1, 78.9
LONG_BALL = 32.0

SHOTS = ("Goal", "SavedShot", "MissedShots", "ShotOnPost")
# what makes a SHOT a set-piece shot
SP_SHOT = {"FromCorner", "SetPiece", "DirectFreekick", "ThrowinSetPiece"}
# what makes a PASS a set-piece delivery
SP_PASS = {"CornerTaken", "FreekickTaken", "ThrowIn"}

M: Dict[str, Dict[str, Any]] = {}


def _m(key, label, phase, kind, unit, desc, invert=False):
    M[key] = {"label": label, "phase": phase, "kind": kind, "unit": unit,
              "invert": invert, "desc": desc}


# ---- result: shown beside the score, never inside it ----------------------
_m("pts", "Points", "result", "result", "/match",
   "Points won per match. The outcome, not a process — which is why it is "
   "never weighted. A side's points in the first half of a season predict "
   "its second half at 0.59; the process metrics here manage 0.78.")
_m("gd", "Goal difference", "result", "result", "/match",
   "Goals scored minus conceded, per match.")

# ---- quality: with the ball, open play ------------------------------------
_m("box_entry_op_90", "Reaches the box", "with", "quality", "/match",
   "Open-play entries into the penalty area — a completed pass in, or a "
   "carry in. The single best predictor in the bank of what a side wins "
   "next (0.76 against future points).")
_m("bigchance_op_90", "Makes big chances", "with", "quality", "/match",
   "Chances Opta rates as big, from open play.")
_m("shot_op_90", "Shoots", "with", "quality", "/match",
   "Shots from open play. Penalties excluded entirely — they are awarded "
   "rather than created.")
_m("f3_entry_90", "Reaches the final third", "with", "quality", "/match",
   "Completed passes crossing into the final third, open play.")
_m("prog_pass_90", "Progresses it", "with", "quality", "/match",
   "Completed open-play passes that move the ball meaningfully up the pitch.")

# ---- quality: set pieces, both ends ---------------------------------------
_m("sp_bigchance_90", "Set-piece chances", "set", "quality", "/match",
   "Big chances created from corners, free kicks and long throws. A separate "
   "capability from open-play creation and coached separately.")
_m("sp_shot_90", "Set-piece shots", "set", "quality", "/match",
   "Shots from a set piece.")
_m("sp_bigchance_con_90", "Set-piece chances conceded", "set", "quality",
   "/match", "Big chances given away from set pieces — defending them is its "
   "own skill.", invert=True)
_m("sp_shot_con_90", "Set-piece shots conceded", "set", "quality", "/match",
   "Shots conceded from a set piece.", invert=True)

# ---- quality: against the ball, open play ---------------------------------
_m("box_entry_con_op_90", "Box entries conceded", "against", "quality",
   "/match", "Open-play entries into their own area.", invert=True)
_m("bigchance_con_op_90", "Big chances conceded", "against", "quality",
   "/match", "Big chances given away in open play.", invert=True)
_m("shot_con_op_90", "Shots conceded", "against", "quality", "/match",
   "Open-play shots faced.", invert=True)

# ---- style: with the ball -------------------------------------------------
_m("poss_share", "Keeps the ball", "with", "style", "%",
   "Share of the match's touches.")
_m("directness", "Goes long", "with", "style", "%",
   "Share of passes longer than a third of the pitch.")
_m("tempo", "Tempo", "with", "style", "/min",
   "Passes attempted per minute of their own possession. Not patience — a "
   "direct side records few of these because the ball is in the air.")
_m("width", "Plays wide", "with", "style", "%",
   "Share of touches in the two touchline channels.")
_m("buildup_share", "Builds from the back", "with", "style", "%",
   "Share of passes starting in their own third. Low means a side that is "
   "rarely IN its own third, not one that bypasses it.")
_m("cross_share", "Enters by crossing", "with", "style", "%",
   "Of everything reaching the box, the share arriving as a cross.")

# ---- style: against the ball ----------------------------------------------
_m("press_height", "Defends high", "against", "style", "x",
   "Average pitch position of their defensive actions, 0 their own goal line.")
_m("ppda", "Lets them pass", "against", "style", "passes",
   "Opponent passes allowed per defensive action in the opponent's two "
   "thirds. Low is an intense press; high is a side that sits off.")
_m("recovery_high_pct", "Wins it back high", "against", "style", "%",
   "Share of their recoveries made in the final third.")

ADJUST = [k for k, v in M.items() if v["kind"] == "quality"]
STYLE = [k for k, v in M.items() if v["kind"] == "style"]


def _q(qualifiers) -> set:
    try:
        return {x["type"]["displayName"] for x in qualifiers}
    except Exception:
        return set()


def _in_box(x, y) -> bool:
    return x is not None and x >= BOX_X and BOX_Y_LO <= y <= BOX_Y_HI


def match_rows(match: pd.DataFrame) -> list:
    """Two rows — one per team — of raw counts for a single match."""
    teams = [t for t in match["team"].dropna().unique()]
    if len(teams) != 2:
        return []
    ev = match.dropna(subset=["team"]).copy()
    ev["Q"] = ev["qualifiers"].map(_q)
    ok = ev["outcome_type"] == "Successful"
    minutes = max(1.0, float(match["expanded_minute"].max()))

    acc = {t: defaultdict(float) for t in teams}
    touches_by = {t: 0 for t in teams}
    opp_passes_own_half = {t: 0 for t in teams}
    goals = {t: [0, 0] for t in teams}
    for t in teams:
        sub = match[match["team"] == t]
        if len(sub):
            last = sub.sort_values(["period", "expanded_minute"]).iloc[-1]
            goals[t] = [int(last["team_goals"]), int(last["opp_goals"])]

    for row, q, good in zip(ev.itertuples(index=False), ev["Q"], ok):
        a = acc[row.team]
        t = row.type
        if row.is_touch:
            touches_by[row.team] += 1
            if row.y is not None and (row.y <= WIDE_LO or row.y >= WIDE_HI):
                a["wide_touch"] += 1

        if t == "Pass":
            set_piece = bool(q & SP_PASS)
            a["pass"] += 1
            if row.x is not None and row.x < DEF_THIRD:
                a["build"] += 1
            length = (abs(row.end_x - row.x)
                      if row.end_x is not None and row.x is not None else 0)
            if "Longball" in q or length >= LONG_BALL:
                a["long"] += 1
            if good and row.end_x is not None:
                if _in_box(row.end_x, row.end_y):
                    a["box_entry_sp" if set_piece else "box_entry_op"] += 1
                    if "Cross" in q:
                        a["box_cross"] += 1
                if not set_piece:
                    if row.end_x - row.x >= 10 and row.end_x >= 50:
                        a["prog"] += 1
                    if row.x < FINAL_THIRD <= row.end_x:
                        a["f3"] += 1
            if "BigChanceCreated" in q:
                a["bigchance_sp" if set_piece else "bigchance_op"] += 1
            if row.x is not None and row.x < FINAL_THIRD:
                for other in teams:
                    if other != row.team:
                        opp_passes_own_half[other] += 1
        elif t == "TakeOn" and good and _in_box(row.x, row.y):
            a["box_entry_op"] += 1
        elif t in SHOTS:
            # A penalty is neither open play nor a coached routine: it is
            # awarded. Out of both columns rather than quietly in one.
            if "OwnGoal" not in q and "Penalty" not in q:
                a["shot_sp" if (q & SP_SHOT) else "shot_op"] += 1
        elif t == "BallRecovery":
            a["recovery"] += 1
            if row.x is not None and row.x >= FINAL_THIRD:
                a["recovery_high"] += 1
        if t in ("Tackle", "Interception", "Challenge", "Clearance", "BallRecovery"):
            if row.x is not None:
                a["def_x_sum"] += row.x
                a["def_x_n"] += 1
            if row.x is not None and row.x >= DEF_THIRD:
                a["def_action_high"] += 1

    total_touch = sum(touches_by.values()) or 1
    out = []
    for i, team in enumerate(teams):
        a, o = acc[team], acc[teams[1 - i]]
        share = touches_by[team] / total_touch
        g, c = goals[team]
        rate = lambda k, d=a: d[k] / minutes * 95.0                 # noqa: E731
        box_all = a["box_entry_op"] + a["box_entry_sp"]
        out.append({
            "team": team, "opponent": teams[1 - i],
            "pts": 3 if g > c else (1 if g == c else 0),
            "gd": g - c,
            # with the ball, open play
            "box_entry_op_90": rate("box_entry_op"),
            "bigchance_op_90": rate("bigchance_op"),
            "shot_op_90": rate("shot_op"),
            "f3_entry_90": rate("f3"),
            "prog_pass_90": rate("prog"),
            # set pieces, both ends
            "sp_bigchance_90": rate("bigchance_sp"),
            "sp_shot_90": rate("shot_sp"),
            "sp_bigchance_con_90": rate("bigchance_sp", o),
            "sp_shot_con_90": rate("shot_sp", o),
            # against the ball, open play
            "box_entry_con_op_90": rate("box_entry_op", o),
            "bigchance_con_op_90": rate("bigchance_op", o),
            "shot_con_op_90": rate("shot_op", o),
            # style
            "poss_share": share * 100,
            "directness": (a["long"] / a["pass"] * 100) if a["pass"] else np.nan,
            "tempo": a["pass"] / max(1.0, minutes * share),
            "width": (a["wide_touch"] / touches_by[team] * 100) if touches_by[team] else np.nan,
            "buildup_share": (a["build"] / a["pass"] * 100) if a["pass"] else np.nan,
            "cross_share": (a["box_cross"] / box_all * 100) if box_all else np.nan,
            "press_height": (a["def_x_sum"] / a["def_x_n"]) if a["def_x_n"] else np.nan,
            "ppda": (opp_passes_own_half[team] / a["def_action_high"]
                     if a["def_action_high"] else np.nan),
            "recovery_high_pct": (a["recovery_high"] / a["recovery"] * 100)
                                 if a["recovery"] else np.nan,
        })
    return out


def opponent_adjust(df: pd.DataFrame, keys=None, rounds: int = 40) -> pd.DataFrame:
    """Split each metric into what the team brings and what the opponent allows.

        value = league mean + team term + opponent term + home term

    fitted by alternating means, which for a balanced round-robin settles in
    a handful of passes. The returned column is the league mean plus the
    team's own term — the metric's own scale, with the schedule taken out.
    Conceding four shots to Manchester City and four to Sheffield United stop
    looking like the same afternoon."""
    out = df.copy()
    keys = keys or [k for k in ADJUST if k in df.columns]
    home = out["home"].to_numpy(bool) if "home" in out.columns else None
    for key in keys:
        v = out[key].to_numpy(float)
        seen = ~np.isnan(v)
        if seen.sum() < 20:
            out[f"{key}_adj"] = out[key]
            continue
        mu = float(np.nanmean(v))
        teams = out["team"].to_numpy()
        opps = out["opponent"].to_numpy()
        a, d, h = defaultdict(float), defaultdict(float), 0.0
        for _ in range(rounds):
            resid = v - mu - np.array([d[o] for o in opps]) - (h * home if home is not None else 0)
            for t in np.unique(teams):
                m = seen & (teams == t)
                if m.any():
                    a[t] = float(np.mean(resid[m]))
            resid = v - mu - np.array([a[t] for t in teams]) - (h * home if home is not None else 0)
            for o in np.unique(opps):
                m = seen & (opps == o)
                if m.any():
                    d[o] = float(np.mean(resid[m]))
            if home is not None:
                resid = v - mu - np.array([a[t] for t in teams]) - np.array([d[o] for o in opps])
                h = (float(np.mean(resid[seen & home]))
                     - float(np.mean(resid[seen & ~home]))) / 2.0
        out[f"{key}_adj"] = mu + np.array([a[t] for t in teams])
    return out
