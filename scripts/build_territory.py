"""Where each player actually controls the ball — the territory layer.

The current zones are inferred from ~25 shots a match, which can only say
where a team SHOOTS from. This says where its players operate, from every
deliberate on-ball action they take.

"Controlled" means he had the ball and did something with it on purpose —
a pass, a take-on, a shot. Clearances, blocks, miscontrols and defensive
contacts are excluded: a panicked hoof says nothing about where a player
plays, and including touches would fill the map with them.

Grid: five channels by three thirds. Five is only possible now — Understat's
shot data spans y 0.24-0.85, so the old engine could never see the wings or
the half-spaces separately, while event data covers the full width.

    channels (y):  R wing | R half | centre | L half | L wing
    thirds   (x):  defensive | middle | attacking

Writes data/reports/territory_{season}.json:
    players : occupancy share per cell, average position, and how far a
              player ranges
    teams   : the same aggregated, plus who occupies each cell

Usage: .venv/Scripts/python.exe scripts/build_territory.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from scripts.experiment_persistence import player_minutes
from scripts.experiment_persistence_by_position import position_map

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"

# y = 0 is the RIGHT touchline and y = 100 the LEFT, verified against known
# players: Saka 19.0, Salah 16.4, Mitoma 77.6, Robinson 87.4.
# Channel edges follow the penalty area (21.1 / 78.9), so the half-spaces are
# the strips between the box edge and the width of the goal area.
CHANNELS = [
    ("RW", 0.0, 21.1, "Right wing"),
    ("RH", 21.1, 36.8, "Right half-space"),
    ("C", 36.8, 63.2, "Centre"),
    ("LH", 63.2, 78.9, "Left half-space"),
    ("LW", 78.9, 100.1, "Left wing"),
]
THIRDS = [("D", 0.0, 33.3, "Defensive"), ("M", 33.3, 66.7, "Middle"),
          ("A", 66.7, 100.1, "Attacking")]
CONTROLLED = ("Pass", "TakeOn", "Goal", "SavedShot", "MissedShots",
              "ShotOnPost")
MIN_ACTIONS = 200


def cell_of(x: float, y: float) -> str | None:
    if x is None or y is None or np.isnan(x) or np.isnan(y):
        return None
    third = next((t for t, lo, hi, _ in THIRDS if lo <= x < hi), None)
    chan = next((c for c, lo, hi, _ in CHANNELS if lo <= y < hi), None)
    return f"{third}{chan}" if third and chan else None


CELLS = [f"{t}{c}" for t, *_ in THIRDS for c, *_ in CHANNELS]


def build(league: str, season: str) -> dict:
    df = pd.read_parquet(
        RAW / league / f"{season}_stamped.parquet",
        columns=["game_id", "player", "team", "type", "x", "y"])
    ctrl = df[df["type"].isin(CONTROLLED)].dropna(subset=["player", "x", "y"])
    ctrl = ctrl.assign(cell=[cell_of(x, y) for x, y in zip(ctrl["x"], ctrl["y"])])
    ctrl = ctrl.dropna(subset=["cell"])

    minutes: dict = {}
    full = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
    for _, match in full.groupby("game_id", sort=False):
        for player, (_s, _f, played) in player_minutes(match).items():
            if played > 0:
                minutes[player] = minutes.get(player, 0.0) + played
    del full

    pos = position_map(league, season)
    team_of = ctrl.groupby("player")["team"].agg(
        lambda s: s.value_counts().index[0])

    players = {}
    for player, g in ctrl.groupby("player"):
        n = len(g)
        if n < MIN_ACTIONS:
            continue
        counts = g["cell"].value_counts()
        share = {c: round(counts.get(c, 0) / n * 100, 2) for c in CELLS}
        players[player] = {
            "team": team_of.get(player),
            "pos": pos.get(player),
            "minutes": round(minutes.get(player, 0.0)),
            "actions": int(n),
            "x": round(float(g["x"].mean()), 1),
            "y": round(float(g["y"].mean()), 1),
            # how far he ranges: a full-back who never leaves his flank has a
            # small spread, a roaming midfielder a large one
            "spread_x": round(float(g["x"].std()), 1),
            "spread_y": round(float(g["y"].std()), 1),
            "cells": {c: v for c, v in share.items() if v > 0},
        }

    teams = {}
    for team, g in ctrl.groupby("team"):
        n = len(g)
        counts = g["cell"].value_counts()
        cells = {}
        for c in CELLS:
            sub = g[g["cell"] == c]
            if sub.empty:
                continue
            occupants = sub["player"].value_counts().head(4)
            cells[c] = {
                "share": round(len(sub) / n * 100, 2),
                # a zone IS the players who occupy it
                "by": [{"player": p, "share": round(v / len(sub) * 100, 1)}
                       for p, v in occupants.items()],
            }
        teams[team] = {"actions": int(n), "cells": cells}

    return {"league": league, "season": season,
            "channels": [{"key": c, "label": lab} for c, _lo, _hi, lab in CHANNELS],
            "thirds": [{"key": t, "label": lab} for t, _lo, _hi, lab in THIRDS],
            "players": players, "teams": teams}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--seasons", nargs="*", default=None)
    args = ap.parse_args()

    folder = RAW / args.league
    seasons = args.seasons or sorted(
        p.stem.replace("_stamped", "") for p in folder.glob("*_stamped.parquet"))
    for season in seasons:
        data = build(args.league, season)
        out = ROOT / "data" / "reports" / f"territory_{season}.json"
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"OK   {season}: {len(data['players'])} players, "
              f"{len(data['teams'])} teams -> {out.name} "
              f"({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
