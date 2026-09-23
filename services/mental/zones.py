"""Where a team plays, and who wins each part of the pitch.

Fifteen cells — five channels across by three thirds up — which is the grid
`scripts/build_territory.py` already uses for players, reused here so player
territory and team zones line up rather than being two incompatible maps.

The number in each cell is a SHARE, not a count:

    dominance(cell) = the team's actions there
                      -------------------------------------------
                      the team's actions there + the opponent's

50 means the cell was split evenly. That is a genuine midpoint, which makes
this a diverging scale and a heatmap that reads without a legend: one pole
for the parts of the pitch a side owns, one for the parts it cedes, neutral
where the match was even.

MIRRORING. Opta always records events attacking left to right FOR THE TEAM
IN POSSESSION, so the opponent's attacking third is our defensive third in
their coordinates. Every opponent action is therefore reflected — x to 100-x
and y to 100-y — before it is counted against us. Skip that and a side's own
box shows up as the opponent's box, and the map is inside out.

Two more layers on top of the share, because owning a cell and doing
something with it are different:

    shots      shots that STARTED in that cell, per match
    shots_con  the same conceded there

CHANCE ORIGIN is the layer that earns its place. Mapping where shots are
TAKEN is close to useless: every side in the league concedes its shots from
the same place, the middle of its own box, so the map comes out red in front
of the goalkeeper for all twenty and says nothing about how they got there.
What matters is where the ball CAME FROM. Opta links 72% of shots back to
the event that created them, so the creating pass or carry can be located
and its cell credited instead:

    origin     where our shots were played from
    origin_con where the shots against us were played from

That is a map of where a side is got at, rather than a map of where every
goalkeeper stands.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import numpy as np
import pandas as pd

CHANNELS: List[tuple] = [
    ("RW", 0.0, 21.1, "Right wing"),
    ("RH", 21.1, 36.8, "Right half-space"),
    ("C", 36.8, 63.2, "Centre"),
    ("LH", 63.2, 78.9, "Left half-space"),
    ("LW", 78.9, 100.1, "Left wing"),
]
THIRDS: List[tuple] = [("D", 0.0, 33.3, "Defensive"),
                       ("M", 33.3, 66.7, "Middle"),
                       ("A", 66.7, 100.1, "Attacking")]
CELLS = [f"{t}{c}" for t, *_ in THIRDS for c, *_ in CHANNELS]

# What counts as "having the ball here". Deliberately the same list the
# player territory map uses.
CONTROLLED = ("Pass", "TakeOn", "Goal", "SavedShot", "MissedShots",
              "ShotOnPost")
SHOTS = ("Goal", "SavedShot", "MissedShots", "ShotOnPost")

_T_EDGES = np.array([t[1] for t in THIRDS] + [100.1])
_C_EDGES = np.array([c[1] for c in CHANNELS] + [100.1])


def cell_index(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Vectorised cell lookup; -1 where the coordinates are missing."""
    ok = ~(np.isnan(x) | np.isnan(y))
    t = np.clip(np.searchsorted(_T_EDGES, x, side="right") - 1, 0, len(THIRDS) - 1)
    c = np.clip(np.searchsorted(_C_EDGES, y, side="right") - 1, 0, len(CHANNELS) - 1)
    out = t * len(CHANNELS) + c
    return np.where(ok, out, -1)


def match_zones(match: pd.DataFrame) -> list:
    """One row per team: its share of each cell, and shots from each cell."""
    teams = [t for t in match["team"].dropna().unique()]
    if len(teams) != 2:
        return []
    ctrl = match[match["type"].isin(CONTROLLED)].dropna(subset=["x", "y", "team"])
    if ctrl.empty:
        return []
    minutes = max(1.0, float(match["expanded_minute"].max()))

    own = {t: np.zeros(len(CELLS)) for t in teams}
    shots = {t: np.zeros(len(CELLS)) for t in teams}
    origin = {t: np.zeros(len(CELLS)) for t in teams}

    # Where each shot was played FROM, via the event Opta links it to.
    loc = match.dropna(subset=["event_id"]).set_index("event_id")[["x", "y"]]
    sh_all = match[match["type"].isin(SHOTS)].dropna(subset=["team"])
    for r in sh_all.itertuples(index=False):
        rid = r.related_event_id
        if rid is None or (isinstance(rid, float) and np.isnan(rid)):
            continue
        if rid not in loc.index:
            continue
        src = loc.loc[rid]
        if getattr(src, "ndim", 1) > 1:
            src = src.iloc[0]
        idx = cell_index(np.array([float(src["x"])]), np.array([float(src["y"])]))
        if idx[0] >= 0:
            origin[r.team][idx[0]] += 1.0
    for team, g in ctrl.groupby("team"):
        idx = cell_index(g["x"].to_numpy(float), g["y"].to_numpy(float))
        np.add.at(own[team], idx[idx >= 0], 1.0)
        sh = g[g["type"].isin(SHOTS)]
        if len(sh):
            si = cell_index(sh["x"].to_numpy(float), sh["y"].to_numpy(float))
            np.add.at(shots[team], si[si >= 0], 1.0)

    # The opponent's map, reflected into our frame.
    mirrored = {}
    for team, g in ctrl.groupby("team"):
        idx = cell_index(100.0 - g["x"].to_numpy(float),
                         100.0 - g["y"].to_numpy(float))
        v = np.zeros(len(CELLS))
        np.add.at(v, idx[idx >= 0], 1.0)
        mirrored[team] = v

    out = []
    for i, team in enumerate(teams):
        other = teams[1 - i]
        against = mirrored[other]
        total = own[team] + against
        with np.errstate(invalid="ignore", divide="ignore"):
            share = np.where(total > 0, own[team] / total * 100.0, np.nan)
        row = {"team": team, "opponent": other}
        for j, cell in enumerate(CELLS):
            row[f"z_{cell}"] = float(share[j])
            row[f"zs_{cell}"] = float(shots[team][j] / minutes * 95.0)
            row[f"zc_{cell}"] = float(shots[other][len(CELLS) - 1 - j]
                                      / minutes * 95.0)
            row[f"zo_{cell}"] = float(origin[team][j] / minutes * 95.0)
            # mirrored: the opponent's origin cell, reflected into our frame
            row[f"zoc_{cell}"] = float(origin[other][len(CELLS) - 1 - j]
                                       / minutes * 95.0)
        out.append(row)
    return out


SHARE_KEYS = [f"z_{c}" for c in CELLS]
SHOT_KEYS = [f"zs_{c}" for c in CELLS]
SHOT_CON_KEYS = [f"zc_{c}" for c in CELLS]
ORIGIN_KEYS = [f"zo_{c}" for c in CELLS]
ORIGIN_CON_KEYS = [f"zoc_{c}" for c in CELLS]
ALL_KEYS = SHARE_KEYS + SHOT_KEYS + SHOT_CON_KEYS + ORIGIN_KEYS + ORIGIN_CON_KEYS


def grid_meta() -> dict:
    return {
        "cells": CELLS,
        "channels": [{"key": c, "label": lab, "lo": lo, "hi": hi}
                     for c, lo, hi, lab in CHANNELS],
        "thirds": [{"key": t, "label": lab, "lo": lo, "hi": hi}
                   for t, lo, hi, lab in THIRDS],
    }


# ---------------------------------------------------------------------------
# THE PICTURE. The fifteen cells above are the analytical unit — what the
# versus function will argue over. They are not a heatmap: fifteen boxes is a
# grid, and a reader sees a spreadsheet rather than a pitch.
#
# So a second, much finer grid is kept purely to be looked at. 30 by 20 is
# close to the pitch's own proportions, fine enough that a blur turns it into
# the smooth blobs everyone recognises, and small enough that a whole club's
# worth costs a few hundred numbers.
# ---------------------------------------------------------------------------

DENS_W, DENS_H = 30, 20


def _gaussian_kernel(sigma: float) -> np.ndarray:
    r = max(1, int(round(sigma * 2.5)))
    x = np.arange(-r, r + 1, dtype=float)
    k = np.exp(-(x ** 2) / (2 * sigma ** 2))
    return k / k.sum()


def smooth(grid: np.ndarray, sigma: float = 1.3) -> np.ndarray:
    """Separable gaussian blur. Done here rather than in the browser so every
    map of a club is smoothed identically and the shapes stay comparable."""
    k = _gaussian_kernel(sigma)
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, grid)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, out)


def density(match: pd.DataFrame, mirror: bool = False) -> Dict[str, np.ndarray]:
    """team -> a DENS_H x DENS_W count of its controlled actions.

    `mirror` reflects into the opponent's frame, which is how "where they are
    attacked" is built: the opponent's own map, turned round."""
    ctrl = match[match["type"].isin(CONTROLLED)].dropna(subset=["x", "y", "team"])
    out: Dict[str, np.ndarray] = {}
    for team, g in ctrl.groupby("team"):
        x = g["x"].to_numpy(float)
        y = g["y"].to_numpy(float)
        if mirror:
            x, y = 100.0 - x, 100.0 - y
        ok = ~(np.isnan(x) | np.isnan(y))
        xi = np.clip((x[ok] / 100.0 * DENS_W).astype(int), 0, DENS_W - 1)
        # y is 0 at the RIGHT touchline, and the picture wants left wing on
        # top, so the row index is flipped here rather than in the browser.
        yi = np.clip(((100.0 - y[ok]) / 100.0 * DENS_H).astype(int), 0, DENS_H - 1)
        grid = np.zeros((DENS_H, DENS_W))
        np.add.at(grid, (yi, xi), 1.0)
        out[team] = grid
    return out
