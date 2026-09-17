"""How well does each metric repeat, for each position?

Runs over the WHOLE metric bank (not the handful the first experiment used),
so every slider on the Mental page can be coloured by whether the number
behind it is measurable at all.

Two questions, both answered per position:

    repeat   a player's season against his next season — is it a trait?
    self     the season's odd matches against its even ones — can we even
             measure it? A metric that cannot agree with itself inside one
             season is noise, and its cross-season failure says nothing
             about football.

Writes data/reports/metric_reliability.json, consumed by build_mental_web.

Usage: .venv/Scripts/python.exe scripts/build_reliability.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from services.mental.event_metrics import METRICS, accumulate, finalise, new_accumulator
from scripts.experiment_persistence import player_minutes
from scripts.experiment_persistence_by_position import position_map

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
OUT = ROOT / "data" / "reports" / "metric_reliability.json"
MIN_FULL = 900        # cross-season
MIN_HALF = 450        # each half of a split season
MIN_PLAYERS = 20      # below this a correlation is not worth reporting


def bank(league: str, season: str, min_minutes: int, half: str | None = None):
    df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
    if half:
        gids = sorted(df["game_id"].unique())
        keep = {g for i, g in enumerate(gids) if (i % 2 == 0) == (half == "even")}
        df = df[df["game_id"].isin(keep)]
    acc, minutes = new_accumulator(), {}
    for _, match in df.groupby("game_id", sort=False):
        for player, (_s, _f, played) in player_minutes(match).items():
            if played > 0:
                minutes[player] = minutes.get(player, 0.0) + played
        accumulate(match, acc)
    out = finalise(acc, minutes, min_minutes)
    out["pos"] = out.index.map(position_map(league, season))
    return out


def correlate(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """metric -> position -> rho, for positions with enough players."""
    shared = a.index.intersection(b.index)
    res: dict = {}
    for metric in METRICS:
        if metric not in a.columns or metric not in b.columns:
            continue
        for grp in sorted({g for g in a["pos"].dropna().unique()}):
            players = [p for p in shared
                       if a.at[p, "pos"] == grp and b.at[p, "pos"] == grp]
            if len(players) < MIN_PLAYERS:
                continue
            x, y = a.loc[players, metric], b.loc[players, metric]
            ok = x.notna() & y.notna()
            if int(ok.sum()) < MIN_PLAYERS:
                continue
            rho = x[ok].rank().corr(y[ok].rank())
            if pd.isna(rho):
                continue
            res.setdefault(metric, {})[grp] = {
                "rho": round(float(rho), 3), "n": int(ok.sum())}
    return res


def main() -> int:
    league = "ENG-Premier League"
    seasons = sorted(p.stem.replace("_stamped", "")
                     for p in (RAW / league).glob("*_stamped.parquet"))
    if len(seasons) < 2:
        print("need two stamped seasons")
        return 1
    s1, s2 = seasons[0], seasons[1]

    print(f"cross-season {s1} v {s2} ...", flush=True)
    repeat = correlate(bank(league, s1, MIN_FULL), bank(league, s2, MIN_FULL))

    print(f"split-half within {s2} ...", flush=True)
    self_ = correlate(bank(league, s2, MIN_HALF, "odd"),
                      bank(league, s2, MIN_HALF, "even"))

    payload = {"league": league, "seasons": [s1, s2],
               "repeat": repeat, "self": self_}
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"\n{'metric':<20}{'pos':>6}{'repeats':>9}{'self':>8}")
    print("-" * 46)
    for metric in METRICS:
        for grp, r in sorted(repeat.get(metric, {}).items()):
            s = self_.get(metric, {}).get(grp, {}).get("rho")
            print(f"{metric:<20}{grp:>6}{r['rho']:>9.2f}"
                  f"{('%.2f' % s) if s is not None else '--':>8}")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
