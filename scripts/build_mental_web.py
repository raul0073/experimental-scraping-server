"""Build the Mental page's data: every player's metric bank, by position.

The website is a static export, so the CONFIG runs in the browser: this
exports each player's percentile on every metric (within his position), and
the page multiplies those by whatever weights the reader sets. No server,
instant feedback.

Also exports, per metric per position, how well that metric REPEATS
(from the persistence experiment). The page uses it to stop anyone
weighting a number that cannot reproduce itself.

Writes data/web/mental.json

Usage: .venv/Scripts/python.exe scripts/build_mental_web.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.event_metrics import (
    GROUP_LABEL, METRICS, accumulate, finalise, new_accumulator,
    possession_adjust,
)
from scripts.experiment_persistence import player_minutes
from scripts.experiment_persistence_by_position import position_map

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
OUT = ROOT / "data" / "web" / "mental.json"
MIN_MINUTES = 900
GROUPS = ["GK", "CB", "FB", "CM", "AM", "WIDE", "ST"]
GROUP_NAME = {"GK": "Goalkeepers", "CB": "Centre-backs", "FB": "Full-backs",
              "CM": "Central midfield", "AM": "Attacking midfield",
              "WIDE": "Wide attackers", "ST": "Strikers"}


def season_bank(league: str, season: str):
    """Returns (raw bank, possession-adjusted bank)."""
    path = RAW / league / f"{season}_stamped.parquet"
    df = pd.read_parquet(path)
    acc = new_accumulator()
    minutes: dict = {}
    for _, match in df.groupby("game_id", sort=False):
        played_now = {p: m for p, (_s, _f, m) in player_minutes(match).items() if m > 0}
        for player, played in played_now.items():
            minutes[player] = minutes.get(player, 0.0) + played
        accumulate(match, acc, played_now)
    bank = finalise(acc, minutes, MIN_MINUTES)
    bank["pos"] = bank.index.map(position_map(league, season))
    team = (df.dropna(subset=["player"]).groupby("player")["team"]
            .agg(lambda s: s.value_counts().index[0]))
    bank["team"] = bank.index.map(team)
    adj = possession_adjust(bank, acc)
    return bank, adj


def percentiles(bank: pd.DataFrame) -> pd.DataFrame:
    """Percentile WITHIN position — a centre-back is only ranked against
    centre-backs — with inverted metrics flipped so 100 is always good."""
    out = bank.copy()
    for key, meta in METRICS.items():
        if key not in bank.columns:
            continue
        col = pd.Series(np.nan, index=bank.index)
        for grp, sub in bank.groupby("pos"):
            pct = sub[key].rank(pct=True, na_option="keep") * 100
            if meta["invert"]:
                pct = 100 - pct
            col.loc[sub.index] = pct
        out[f"p_{key}"] = col.round(0)
    return out


def reliability() -> tuple:
    """metric -> position -> how well it repeats (and whether it can even be
    measured). Built by scripts/build_reliability.py over the whole bank."""
    path = ROOT / "data" / "reports" / "metric_reliability.json"
    if not path.exists():
        return {}, {}
    d = json.loads(path.read_text(encoding="utf-8"))
    flat = lambda block: {                                        # noqa: E731
        metric: {grp: v["rho"] for grp, v in per.items()}
        for metric, per in block.items()
    }
    return flat(d.get("repeat", {})), flat(d.get("self", {}))


def main() -> int:
    league = "ENG-Premier League"
    seasons = [p.stem.replace("_stamped", "")
               for p in sorted((RAW / league).glob("*_stamped.parquet"))]
    if not seasons:
        print("no stamped seasons — run scripts/stamp_event_state.py first")
        return 1

    _rel = reliability()
    payload = {
        "league": league,
        "seasons": seasons,
        "min_minutes": MIN_MINUTES,
        "groups": [{"key": g, "label": GROUP_NAME[g]} for g in GROUPS],
        "metric_groups": [{"key": k, "label": v} for k, v in GROUP_LABEL.items()],
        "metrics": [
            {"key": k, "label": m["label"], "unit": m["unit"],
             "group": m["group"], "invert": m["invert"], "desc": m["desc"]}
            for k, m in METRICS.items()
        ],
        "reliability": _rel[0],
        "self_reliability": _rel[1],
        "players": {},
    }

    for season in seasons:
        raw, adj = season_bank(league, season)
        bank, badj = percentiles(raw), percentiles(adj)
        rows = []
        for name, r in bank.iterrows():
            if not isinstance(r["pos"], str):
                continue
            a = badj.loc[name]
            row = {"n": name, "t": r["team"], "p": r["pos"],
                   "m": int(r["minutes"]),
                   "v": {}, "q": {}, "va": {}, "qa": {}}
            for key in METRICS:
                for src, vkey, qkey in ((r, "v", "q"), (a, "va", "qa")):
                    val, pct = src.get(key), src.get(f"p_{key}")
                    if val is not None and not pd.isna(val):
                        row[vkey][key] = round(float(val), 2)
                    if pct is not None and not pd.isna(pct):
                        row[qkey][key] = int(pct)
            rows.append(row)
        payload["players"][season] = rows
        print(f"OK   {season}: {len(rows)} players")

    blob = json.dumps(payload, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    # also served to the browser: the config runs client-side, so the page
    # fetches this rather than inlining ~1 MB into the HTML
    pub = ROOT / "web" / "public" / "data" / "mental.json"
    pub.parent.mkdir(parents=True, exist_ok=True)
    pub.write_text(blob, encoding="utf-8")
    print(f"\n-> {OUT} ({OUT.stat().st_size // 1024} KB)")
    print(f"-> {pub}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
