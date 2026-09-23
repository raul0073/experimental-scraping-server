"""The raw material for drawing a team: shots, average positions, passes.

Everything else in the team layer is aggregated into one number per cut.
These three are not — a shot map needs the shots, not their mean — so they
are collected per club and per manager spell and written as their own files,
fetched only by the page that draws them.

SHOTS carry where they were taken, where they crossed the line, and enough
flags to colour them: goal, on target, big chance, set piece, header. Both
ends — the shots a side takes and the shots it faces — because "where do
they get shot at from" is the more useful half and nobody ever draws it.

AVERAGE POSITIONS are taken from a player's CONTROLLED actions rather than
from every event he appears in, so a centre-back's average is where he plays
rather than where he happened to make a tackle. Weighted by nothing: the
mean touch position IS the answer.

PASS NETWORKS need a receiver, which Opta does not record. The receiver is
inferred as the next event by the same team, which is the standard approach
and right for a completed pass — but it IS an inference, so `passes_checked`
reports how often the next event actually belongs to a different player of
the same side, and the page is expected to say so rather than draw lines
that look like facts.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

import numpy as np
import pandas as pd

CONTROLLED = ("Pass", "TakeOn", "Goal", "SavedShot", "MissedShots",
              "ShotOnPost", "BallTouch")
SHOTS = ("Goal", "SavedShot", "MissedShots", "ShotOnPost")
# Only a goalkeeper does these, so they identify one without needing the
# formation grid. Needed because an eleven picked on appearances alone left
# Liverpool without a keeper: Alisson and Mamardashvili split 25/26 between
# them and neither reached the top eleven, so the network was eleven
# outfielders and no origin for the build-up.
KEEPER = ("Claim", "Punch", "KeeperPickup", "Smother", "CrossNotClaimed",
          "KeeperSweeper", "Save", "Penalty Faced")


def _q(qualifiers) -> set:
    try:
        return {x["type"]["displayName"] for x in qualifiers}
    except Exception:
        return set()


def match_plots(match: pd.DataFrame) -> Dict[str, dict]:
    """team -> {shots, faced, positions, passes} for one match."""
    teams = [t for t in match["team"].dropna().unique()]
    if len(teams) != 2:
        return {}
    ev = match.dropna(subset=["team"])
    out: Dict[str, dict] = {
        t: {"shots": [], "faced": [],
            # [sum x, sum y, actions, appearances]
            "pos": defaultdict(lambda: [0.0, 0.0, 0, 0]),
            "gk": Counter(), "pass": Counter()}
        for t in teams
    }

    # ---- shots, both ends -------------------------------------------------
    for r in ev[ev["type"].isin(SHOTS)].itertuples(index=False):
        q = _q(r.qualifiers)
        if "OwnGoal" in q:
            continue
        if r.x is None or r.y is None or np.isnan(r.x) or np.isnan(r.y):
            continue
        shot = {
            "x": round(float(r.x), 1),
            "y": round(float(r.y), 1),
            # who hit it. A shot map you cannot attribute shows a shape; one
            # you can shows that the shape IS a player — Arsenal's right
            # half-space is not a tactic, it is Saka standing in it.
            "who": r.player if isinstance(r.player, str) else "",
            "g": int(r.type == "Goal"),
            "t": int(r.type in ("Goal", "SavedShot")),     # on target
            "b": int("BigChance" in q),
            "s": int(bool(q & {"FromCorner", "SetPiece", "DirectFreekick",
                               "ThrowinSetPiece"})),
            "p": int("Penalty" in q),
            "h": int("Head" in q),
        }
        out[r.team]["shots"].append(shot)
        other = teams[1] if r.team == teams[0] else teams[0]
        # mirrored, so a side's own map of shots faced is in its own frame.
        # The shooter is dropped: on a map of shots FACED he is an opponent
        # who appears twice a season, and naming him says nothing about the
        # side being shot at.
        out[other]["faced"].append({**shot, "who": "",
                                    "x": round(100.0 - float(r.x), 1),
                                    "y": round(100.0 - float(r.y), 1)})

    # ---- average positions ------------------------------------------------
    ctrl = ev[ev["type"].isin(CONTROLLED)].dropna(subset=["player", "x", "y"])
    for r in ctrl.itertuples(index=False):
        p = out[r.team]["pos"][r.player]
        p[0] += float(r.x)
        p[1] += float(r.y)
        p[2] += 1
    # appearances, so an eleven can be picked by who PLAYS rather than by who
    # touches the ball. Ranked on touches, Arsenal's eleven came out as four
    # centre-backs and no striker: Gyökeres started thirty-odd matches and had
    # fewer actions than a rotating full-back, because a striker's job is to
    # be in a place, not to have it.
    for team in teams:
        for name in {r.player for r in
                     ctrl[ctrl["team"] == team].itertuples(index=False)}:
            out[team]["pos"][name][3] += 1
    # who kept goal, counted from acts only a keeper performs
    for r in ev[ev["type"].isin(KEEPER)].dropna(
            subset=["player"]).itertuples(index=False):
        out[r.team]["gk"][r.player] += 1

    # ---- pass network, receiver inferred ---------------------------------
    seq = ev.sort_values(["period", "expanded_minute", "second"])
    players = seq["player"].tolist()
    types = seq["type"].tolist()
    tms = seq["team"].tolist()
    outc = (seq["outcome_type"] == "Successful").tolist()
    checked: Counter = Counter()
    hit: Counter = Counter()
    for i in range(len(seq) - 1):
        if types[i] != "Pass" or not outc[i]:
            continue
        a, b = players[i], players[i + 1]
        checked[tms[i]] += 1
        if tms[i] != tms[i + 1] or a is None or b is None or a == b:
            continue
        hit[tms[i]] += 1
        out[tms[i]]["pass"][(a, b)] += 1
    for t in teams:
        out[t]["checked"] = checked[t]
        out[t]["hit"] = hit[t]
    return out


ELEVEN = 11


def pack(acc: dict, matches: int) -> dict:
    """Turn the running totals into something a page can draw."""
    pos = [
        {"n": name, "x": round(v[0] / v[2], 1), "y": round(v[1] / v[2], 1),
         "t": v[2], "a": v[3]}
        for name, v in acc["pos"].items()
        if v[2] >= max(20, matches * 8)      # a regular, not a cameo
    ]
    # ELEVEN, because a team has eleven players and a picture of fourteen is
    # a picture of no formation at all. Chosen on APPEARANCES first and time
    # on the ball only to break ties: ranked on touches the eleven came out
    # as four centre-backs and no striker, because a striker's job is to be
    # in a place rather than to have the ball in it.
    pos.sort(key=lambda d: (-d["a"], -d["t"]))
    # The keeper gets a reserved slot. A club that shares the job between two
    # of them can have neither in the top eleven — Liverpool's was eleven
    # outfielders — and a network with nobody in goal has no build-up origin.
    keeper = acc["gk"].most_common(1)[0][0] if acc.get("gk") else None
    eleven = pos[:ELEVEN]
    if keeper and all(d["n"] != keeper for d in eleven):
        gk = next((d for d in pos if d["n"] == keeper), None)
        if gk:
            eleven = [gk] + eleven[:ELEVEN - 1]
    pos = eleven
    keep = {d["n"] for d in pos}
    links = [
        {"a": a, "b": b, "n": n}
        for (a, b), n in acc["pass"].most_common()
        if a in keep and b in keep and n >= max(4, matches)
    ][:60]
    return {
        "matches": matches,
        "shots": acc["shots"],
        "faced": acc["faced"],
        "positions": pos,
        "passes": links,
        "passes_checked": acc.get("checked", 0),
        "passes_resolved": acc.get("hit", 0),
    }


def new_acc() -> dict:
    return {"shots": [], "faced": [],
            "pos": defaultdict(lambda: [0.0, 0.0, 0, 0]),
            "gk": Counter(), "pass": Counter(), "checked": 0, "hit": 0}


def merge(into: dict, part: dict) -> None:
    into["shots"].extend(part["shots"])
    into["faced"].extend(part["faced"])
    for name, v in part["pos"].items():
        cur = into["pos"][name]
        cur[0] += v[0]
        cur[1] += v[1]
        cur[2] += v[2]
        cur[3] += v[3]
    into["gk"].update(part["gk"])
    into["pass"].update(part["pass"])
    into["checked"] += part.get("checked", 0)
    into["hit"] += part.get("hit", 0)
