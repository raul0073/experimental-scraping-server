"""Team zone strength, built from the players who occupy each zone.

This is the benchmark, not a predictor input. It answers the question the
project exists for — how strong is this team in this part of the pitch, and
because of whom — and it needs nothing beyond the season already on disk.

    strength(team, channel) = SUM over players of
        (his share of the team's actions in that channel)
        x (his quality percentile among players of his position)

Quality is a player's percentile WITHIN HIS POSITION on the metrics that
matter for that end of the pitch — attacking quality for attacking channels,
defending quality for defensive ones — so a centre-back is judged as a
centre-back even when his contribution is being read off a zone.

Every zone also names its occupants, because a zone is the players in it;
a number with nobody's name attached is not a description of anything.

Writes data/web/zones.json (and the public copy the site reads).

Usage: .venv/Scripts/python.exe scripts/build_team_zones.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.event_metrics import (
    METRICS, accumulate, finalise, new_accumulator, possession_adjust,
)
from scripts.build_territory import CHANNELS, THIRDS, cell_of
from scripts.experiment_persistence import player_minutes
from scripts.experiment_persistence_by_position import position_map

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
OUT = ROOT / "data" / "web" / "zones.json"
CONTROLLED = ("Pass", "TakeOn", "Goal", "SavedShot", "MissedShots", "ShotOnPost")
CHAN_KEYS = [c for c, *_ in CHANNELS]
MIN_MINUTES = 450          # a zone contributor, not a season regular

# What "good" means at each end. Attacking channels are judged on creating
# and carrying, defensive ones on winning it back and not giving it away.
ATT_QUALITY = {"keypass_90": 1.0, "box_pass_90": 0.8, "bigchance_90": 0.8,
               "takeon_90": 0.7, "carry_box_90": 0.7, "touch_box_90": 0.6,
               "cross_pct": 0.5, "prog_pass_90": 0.6, "giveaway_90": 0.6}
DEF_QUALITY = {"ground_duel_pct": 1.0, "interception_90": 0.9,
               "aerial_def_pct": 0.9, "tackle_pct": 0.8, "recovery_90": 0.8,
               "giveaway_90": 0.8, "dribbled_past_90": 0.7}


def quality(bank: pd.DataFrame, recipe: dict) -> pd.Series:
    """Percentile within position, weighted. Inverted metrics are already
    flipped so 100 is always good."""
    score = pd.Series(0.0, index=bank.index)
    total = 0.0
    for key, weight in recipe.items():
        if key not in bank.columns:
            continue
        pct = pd.Series(np.nan, index=bank.index)
        for _grp, sub in bank.groupby("pos"):
            p = sub[key].rank(pct=True, na_option="keep") * 100
            if METRICS[key]["invert"]:
                p = 100 - p
            pct.loc[sub.index] = p
        score = score.add(pct.fillna(50) * weight, fill_value=0)
        total += weight
    return score / (total or 1)


def build(league: str, season: str) -> dict:
    df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")

    acc, minutes = new_accumulator(), {}
    for _, match in df.groupby("game_id", sort=False):
        played = {p: m for p, (_s, _f, m) in player_minutes(match).items() if m > 0}
        for player, m in played.items():
            minutes[player] = minutes.get(player, 0.0) + m
        accumulate(match, acc, played)
    bank = finalise(acc, minutes, MIN_MINUTES)
    bank["pos"] = bank.index.map(position_map(league, season))
    bank = bank[bank["pos"].notna()]
    bank = possession_adjust(bank, acc)
    att_q, def_q = quality(bank, ATT_QUALITY), quality(bank, DEF_QUALITY)

    ctrl = df[df["type"].isin(CONTROLLED)].dropna(subset=["player", "x", "y"])
    ctrl = ctrl.assign(cell=[cell_of(x, y) for x, y in zip(ctrl["x"], ctrl["y"])])
    ctrl = ctrl.dropna(subset=["cell"])

    teams = {}
    for team, g in ctrl.groupby("team"):
        zones = {}
        for third, *_rest in THIRDS:
            q = att_q if third == "A" else def_q
            in_third = g[g["cell"].str.startswith(third)]
            if in_third.empty:
                continue
            for chan in CHAN_KEYS:
                sub = in_third[in_third["cell"] == f"{third}{chan}"]
                if len(sub) < 40:
                    continue
                counts = sub["player"].value_counts()
                strength, occupants = 0.0, []
                for player, n in counts.items():
                    share = n / len(sub)
                    pq = q.get(player)
                    if pq is None or pd.isna(pq):
                        continue
                    strength += share * float(pq)
                    if len(occupants) < 4:
                        occupants.append({
                            "player": player,
                            "share": round(share * 100, 1),
                            "quality": round(float(pq)),
                            "pos": bank.at[player, "pos"] if player in bank.index else None,
                        })
                zones[f"{third}{chan}"] = {
                    "strength": round(strength, 1),
                    "volume": round(len(sub) / len(in_third) * 100, 1),
                    "by": occupants,
                }
        teams[team] = zones

    # rank each zone across the league so a number means something
    for cell in [f"{t}{c}" for t, *_ in THIRDS for c in CHAN_KEYS]:
        vals = [(t, z[cell]["strength"]) for t, z in teams.items() if cell in z]
        if len(vals) < 5:
            continue
        order = sorted(vals, key=lambda kv: -kv[1])
        for rank, (team, _v) in enumerate(order, 1):
            teams[team][cell]["rank"] = rank
    return {"league": league, "season": season,
            "channels": [{"key": c, "label": lab} for c, _lo, _hi, lab in CHANNELS],
            "thirds": [{"key": t, "label": lab} for t, _lo, _hi, lab in THIRDS],
            "teams": teams}


def main() -> int:
    league = "ENG-Premier League"
    seasons = sorted(p.stem.replace("_stamped", "")
                     for p in (RAW / league).glob("*_stamped.parquet"))
    payload = {"leagues": {}}
    for season in seasons:
        data = build(league, season)
        payload["leagues"].setdefault(league, {})[season] = data
        print(f"OK   {league} {season}: {len(data['teams'])} teams")
    blob = json.dumps(payload, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    pub = ROOT / "web" / "public" / "data" / "zones.json"
    pub.parent.mkdir(parents=True, exist_ok=True)
    pub.write_text(blob, encoding="utf-8")
    print(f"\n-> {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
