"""How much did the match hang on this moment?

The mental question is not how much a player does, it is when he does it. A
goal at 0-0 in the 85th minute decides a football match; the third in a 3-0
decides nothing. Weighting every event by the state it happened in says so,
and — unlike slicing the season into "while behind" buckets — it throws
nothing away. That matters: a player logs about 400 events while behind in a
season but only ELEVEN while a man down, and a third of players never go a
man down at all. As a bucket that is unrankable. As a weight it is free.

Nobody decides the weights. They are read out of the matches we already have:

    for every team, for every minute, record (score difference, man
    difference, minutes left) and what the match eventually finished

    xpts(state)      = 3*P(win) + 1*P(draw) from that state
    leverage(state)  = what one goal, either way, would do to xpts

At 0-0 late, a goal moves a team from one point to three, so leverage is
high. At 3-0 late, a goal moves nothing, so it is near zero. Leverage is
then rescaled so the average event in the league weighs exactly 1.0, which
keeps a leverage-weighted rate on the same scale as the flat one and makes
the ratio between them readable: above 1 means he does more of it when it
counts.

Writes data/config/leverage.json.

Usage: .venv/Scripts/python.exe scripts/build_leverage.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
OUT = ROOT / "data" / "config" / "leverage.json"

# Clamps. Beyond a three-goal margin the match is over as a contest and the
# extra goals change nothing, so they share a cell rather than each getting a
# thinly-populated one of their own. Same for going two men down: it happens
# a handful of times a season.
DIFF_CAP = 3
MEN_CAP = 1
TIME_BIN = 5          # minutes remaining, bucketed
MIN_CELL = 40         # below this the cell is smoothed, not trusted raw


def state_minutes(df: pd.DataFrame) -> pd.DataFrame:
    """One row per team per minute: the state then, and the final result.

    The state is carried forward from the last event at or before that
    minute, because a minute with no events is still a minute of football
    being played in that state."""
    rows = []
    for gid, match in df.groupby("game_id", sort=False):
        end = int(match["expanded_minute"].max())
        if end < 45:
            continue
        for team, g in match.groupby("team"):
            g = g.sort_values(["period", "expanded_minute"])
            last = g.iloc[-1]
            final = int(last["team_goals"]) - int(last["opp_goals"])
            # step function of state over the match
            seen = (g[["expanded_minute", "score_diff", "man_diff"]]
                    .dropna().astype(int).values)
            if not len(seen):
                continue
            idx, diff, men = 0, 0, 0
            for minute in range(end + 1):
                while idx < len(seen) and seen[idx][0] <= minute:
                    diff, men = int(seen[idx][1]), int(seen[idx][2])
                    idx += 1
                rows.append((
                    int(np.clip(diff, -DIFF_CAP, DIFF_CAP)),
                    int(np.clip(men, -MEN_CAP, MEN_CAP)),
                    min(95, ((end - minute) // TIME_BIN) * TIME_BIN),
                    1 if final > 0 else (0 if final == 0 else -1),
                ))
    return pd.DataFrame(rows, columns=["diff", "men", "left", "result"])


def _xpts(sub: pd.DataFrame) -> float:
    return 3 * float((sub["result"] == 1).mean()) + float((sub["result"] == 0).mean())


def expected_points(obs: pd.DataFrame) -> tuple:
    """(diff, men, left) -> expected points.

    Estimated as a surface plus an offset rather than cell by cell. Eleven-a-
    side cells are dense (69,000 team-minutes at 0-0 alone) so the shape over
    score difference and time is read straight off them. Red-card cells are
    not — 83 of 173 hold fewer than forty observations — but POOLED OVER TIME
    they are comfortable, 577 to 1,135 each. So the man difference enters as
    one offset per score state, measured on the pooled data, instead of being
    asked of cells too thin to answer. Estimating it cell by cell smoothed
    the effect away and would have reported it as absent."""
    dense = obs[obs["men"] == 0]
    base = {}
    for (d, t), g in dense.groupby(["diff", "left"]):
        if len(g) >= MIN_CELL:
            base[(d, t)] = _xpts(g)
    by_diff = {d: _xpts(g) for d, g in dense.groupby("diff")}

    # fill any thin eleven-a-side cell from its own score state
    for d in range(-DIFF_CAP, DIFF_CAP + 1):
        for t in range(0, 96, TIME_BIN):
            base.setdefault((d, t), by_diff.get(d, 1.0))

    offset, n_off = {}, {}
    for d in range(-DIFF_CAP, DIFF_CAP + 1):
        level = by_diff.get(d)
        for m in range(-MEN_CAP, MEN_CAP + 1):
            if m == 0 or level is None:
                offset[(d, m)] = 0.0
                continue
            sub = obs[(obs["diff"] == d) & (obs["men"] == m)]
            n_off[(d, m)] = len(sub)
            offset[(d, m)] = (_xpts(sub) - level) if len(sub) >= 150 else 0.0

    table = {}
    for d in range(-DIFF_CAP, DIFF_CAP + 1):
        for m in range(-MEN_CAP, MEN_CAP + 1):
            for t in range(0, 96, TIME_BIN):
                table[(d, m, t)] = float(
                    np.clip(base[(d, t)] + offset[(d, m)], 0.0, 3.0))
    return table, offset, n_off


def build(table: dict) -> dict:
    """leverage(state) = the average absolute move in expected points that one
    goal, scored by either side, would produce from here."""
    lev = {}
    for (d, m, t), base in table.items():
        up = table.get((min(d + 1, DIFF_CAP), m, t), base)
        down = table.get((max(d - 1, -DIFF_CAP), m, t), base)
        lev[(d, m, t)] = (abs(up - base) + abs(base - down)) / 2
    return lev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    args = ap.parse_args()
    seasons = sorted(p.stem.replace("_stamped", "")
                     for p in (RAW / args.league).glob("*_stamped.parquet"))
    if not seasons:
        print("no stamped seasons")
        return 1

    frames = []
    for s in seasons:
        df = pd.read_parquet(RAW / args.league / f"{s}_stamped.parquet")
        obs = state_minutes(df)
        frames.append(obs)
        print(f"{s}: {len(obs):,} team-minutes")
    obs = pd.concat(frames, ignore_index=True)
    print(f"total: {len(obs):,} team-minutes\n")

    xpts, offset, n_off = expected_points(obs)
    print("man-difference offsets in expected points (pooled over time)")
    for (d, m), v in sorted(offset.items()):
        if m and n_off.get((d, m)):
            print(f"   score {d:>+2}, a man {'down' if m < 0 else 'up  '}:"
                  f" {v:>+6.2f}   n={n_off[(d, m)]:,}")

    lev = build(xpts)
    # Adversity is a DIFFERENT question from leverage: not how much the
    # result hangs on this moment, but how bad the moment is. A goal down and
    # a man down is 0.08 expected points — close to lost — while the swing a
    # goal would produce there is ordinary. Both come off the same surface.
    adv = {k: 1.0 - v / 3.0 for k, v in xpts.items()}

    # Rescale so the average EVENT weighs 1.0 — not the average cell, because
    # cells are wildly unequal in how much football happens in them.
    counts = obs.groupby(["diff", "men", "left"]).size().to_dict()
    tot = sum(counts.values())
    for table in (lev, adv):
        mean = sum(table[k] * n for k, n in counts.items() if k in table) / tot
        for k in table:
            table[k] /= mean

    print(f"\nleverage at men level, by score difference and minutes LEFT")
    print(f"{'left':>6}", end="")
    for d in range(-DIFF_CAP, DIFF_CAP + 1):
        print(f"{d:>+7}", end="")
    print()
    for t in range(0, 96, 15):
        print(f"{t:>6}", end="")
        for d in range(-DIFF_CAP, DIFF_CAP + 1):
            print(f"{lev.get((d, 0, t), 0):>7.2f}", end="")
        print()

    print(f"\nADVERSITY at men level, by score difference and minutes LEFT")
    print(f"{'left':>6}", end="")
    for d in range(-DIFF_CAP, DIFF_CAP + 1):
        print(f"{d:>+7}", end="")
    print()
    for t in range(0, 96, 15):
        print(f"{t:>6}", end="")
        for d in range(-DIFF_CAP, DIFF_CAP + 1):
            print(f"{adv.get((d, 0, t), 0):>7.2f}", end="")
        print()

    print(f"\nwhere the two part company, at 0-0 and a goal down")
    print(f"{'state':<26}{'leverage':>10}{'adversity':>11}")
    for label, key in (
        ("0-0, 90 min left", (0, 0, 90)), ("0-0, 5 min left", (0, 0, 0)),
        ("0-0, a man down, 5 left", (0, -1, 0)),
        ("a goal down, 30 left", (-1, 0, 30)),
        ("a goal down + a man down, 30", (-1, -1, 30)),
        ("three up, 5 left", (3, 0, 0)),
    ):
        print(f"{label:<26}{lev.get(key, 0):>10.2f}{adv.get(key, 0):>11.2f}")

    payload = {
        "league": args.league, "seasons": seasons,
        "team_minutes": int(len(obs)),
        "diff_cap": DIFF_CAP, "men_cap": MEN_CAP, "time_bin": TIME_BIN,
        "note": "leverage = average move in expected points from one goal. "
                "adversity = how bad the position is, 1 - xpts/3. Both "
                "rescaled so the average league event weighs 1.0.",
        "xpts": {f"{d}|{m}|{t}": round(v, 4) for (d, m, t), v in xpts.items()},
        "leverage": {f"{d}|{m}|{t}": round(v, 4) for (d, m, t), v in lev.items()},
        "adversity": {f"{d}|{m}|{t}": round(v, 4) for (d, m, t), v in adv.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
