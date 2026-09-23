"""How OFTEN does he do it? The consistency axis.

Everything else in the bank asks how good a player was over a season. That
is a mean, and a mean cannot tell two very different footballers apart: a
winger who attempts four take-ons in thirty of thirty-four matches and one
who averages the same from eight enormous games and twenty-six anonymous
ones produce an identical row. The difference between them is the whole of
what "dependable" means.

So: compute every metric MATCH BY MATCH, then ask what share of his matches
cleared the bucket's own median. A hit rate of 0.80 means he was at or above
a typical player in his position four weeks in five.

    hit rate(player, bucket, metric)
        = share of his matches at or above median(all matches by all players
          in that bucket, that metric)

The median is taken over player-MATCHES rather than player-seasons, because
the question is about turning up on a given Saturday.

Only per-90 rate metrics are asked. A percentage over one match has a
denominator of three or four — a keeper's catch rate on two saves is not a
fact about him — and averaging that noise is how the last pressure
experiment failed. Matches under 20 minutes in the role are dropped for the
same reason.

Then the usual gate, because a consistency score that does not repeat is a
description of one season rather than a trait:

    --gate          his hit rate this season against his hit rate next season
    default         build data/web/consistency.json for the site

Usage: .venv/Scripts/python.exe scripts/build_consistency.py --gate
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.event_metrics import (
    METRICS, accumulate, finalise, new_accumulator,
)
from services.mental.positions import BUCKET_ORDER, load_match, match_roles
from services.mental.role_bank import RAW, _event_buckets, seasons_on_disk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "consistency.json"
PUB = ROOT / "web" / "public" / "data" / "consistency.json"
REPORT = ROOT / "data" / "reports" / "consistency_gate.json"

MIN_MATCH_MINUTES = 20     # below this a per-90 is an extrapolation, not a fact
MIN_MATCHES = 10           # matches in the role before a hit rate means anything
MIN_PLAYERS = 15
# rates only: a percentage computed on one match has a denominator of three
KEYS = [k for k, m in METRICS.items() if m["unit"] == "/90"]


def match_rows(match: pd.DataFrame, roles: dict) -> list:
    """One row per (player, bucket) for a single match: his per-90 rates in
    that match, in that role."""
    name_of = (match.dropna(subset=["player_id"])
               .groupby("player_id")["player"].first())
    minutes: dict = defaultdict(float)
    for pid, spells in roles.items():
        name = name_of.get(pid)
        if name is None:
            continue
        for s in spells:
            if s["end"] > s["start"]:
                minutes[(name, s["bucket"])] += s["end"] - s["start"]

    buckets = _event_buckets(match, roles)
    rows = []
    for bucket, idx in buckets.dropna().groupby(buckets.dropna()).groups.items():
        acc = new_accumulator()
        accumulate(match.loc[idx], acc)
        mins = {n: m for (n, b), m in minutes.items()
                if b == bucket and m >= MIN_MATCH_MINUTES}
        if not mins:
            continue
        bank = finalise(acc, mins, MIN_MATCH_MINUTES)
        if bank.empty:
            continue
        for name, r in bank.iterrows():
            row = {"player": name, "bucket": bucket, "minutes": r["minutes"]}
            for k in KEYS:
                if k in bank.columns:
                    row[k] = r[k]
            rows.append(row)
    return rows


def season_matches(league: str, season: str) -> pd.DataFrame:
    df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
    out = []
    for gid, match in df.groupby("game_id", sort=False):
        doc = load_match(league, season, gid)
        if doc is None:
            continue
        out.extend(match_rows(match, match_roles(doc)))
    return pd.DataFrame(out)


def hit_rates(per_match: pd.DataFrame) -> pd.DataFrame:
    """(player, bucket) -> share of his matches at or above the bucket median.

    A player who never performs the action at all sits below the median every
    week and scores 0, which is correct: he is consistently not doing it."""
    frames = []
    for bucket, g in per_match.groupby("bucket"):
        med = {k: float(g[k].median()) for k in KEYS
               if k in g.columns and g[k].notna().any()}
        hits = pd.DataFrame(index=g.index)
        for k, m in med.items():
            hits[k] = (g[k] >= m).astype(float).where(g[k].notna())
        hits["player"] = g["player"].values
        agg = hits.groupby("player").agg(["mean", "count"])
        keep = agg[(KEYS[0], "count")] >= MIN_MATCHES if KEYS[0] in med else None
        rows = {}
        for k in med:
            rows[k] = agg[(k, "mean")] * 100
        out = pd.DataFrame(rows)
        out["matches"] = g.groupby("player").size()
        out = out[out["matches"] >= MIN_MATCHES]
        out["bucket"] = bucket
        frames.append(out)
    return pd.concat(frames).set_index("bucket", append=True) if frames \
        else pd.DataFrame()


def gate(league: str, seasons: list) -> list:
    tables = {}
    for s in seasons:
        print(f"  {s} ...", flush=True)
        pm = season_matches(league, s)
        if pm.empty:
            continue
        tables[s] = hit_rates(pm)
        print(f"     {len(tables[s])} player-roles with {MIN_MATCHES}+ matches")

    results = []
    have = [s for s in seasons if s in tables]
    for a_s, b_s in zip(have, have[1:]):
        a, b = tables[a_s], tables[b_s]
        shared = a.index.intersection(b.index)
        for bucket in BUCKET_ORDER:
            keys = [k for k in shared if k[1] == bucket]
            if len(keys) < MIN_PLAYERS:
                continue
            for k in KEYS:
                if k not in a.columns or k not in b.columns:
                    continue
                x, y = a.loc[keys, k], b.loc[keys, k]
                ok = x.notna() & y.notna()
                if int(ok.sum()) < MIN_PLAYERS:
                    continue
                rho = x[ok].rank().corr(y[ok].rank())
                if pd.isna(rho):
                    continue
                results.append({"pair": f"{a_s}->{b_s}", "bucket": bucket,
                                "metric": k, "n": int(ok.sum()),
                                "rho": round(float(rho), 3)})
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--gate", action="store_true",
                    help="test whether a hit rate repeats season to season")
    args = ap.parse_args()
    seasons = seasons_on_disk(args.league)

    if args.gate:
        results = gate(args.league, seasons)
        print(f"\nDOES CONSISTENCY REPEAT? hit rate, season against next season")
        print(f"{'':<22}", end="")
        for b in BUCKET_ORDER:
            print(f"{b:>7}", end="")
        print("\n" + "-" * (22 + 7 * len(BUCKET_ORDER)))
        for k in KEYS:
            row = {r["bucket"]: r["rho"] for r in results if r["metric"] == k}
            if not row:
                continue
            print(f"{k:<22}", end="")
            for b in BUCKET_ORDER:
                print(f"{row[b]:>7.2f}" if b in row else f"{'--':>7}", end="")
            print()
        good = [r for r in results if r["rho"] >= 0.4]
        print(f"\nmeasured: {len(results)}   moderate or better: {len(good)} "
              f"({len(good) / (len(results) or 1) * 100:.0f}%)")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"league": args.league,
                                      "min_matches": MIN_MATCHES,
                                      "results": results}, indent=1),
                          encoding="utf-8")
        print(f"-> {REPORT}")
        return 0

    payload = {"league": args.league, "min_matches": MIN_MATCHES,
               "metrics": KEYS, "players": {}}
    total = []
    for s in seasons:
        print(f"  {s} ...", flush=True)
        pm = season_matches(args.league, s)
        if pm.empty:
            continue
        total.append(pm)
        payload["players"][s] = _rows(hit_rates(pm))
        print(f"     {len(payload['players'][s])} rows")
    if len(total) > 1:
        payload["players"]["total"] = _rows(hit_rates(pd.concat(total)))
    blob = json.dumps(payload, ensure_ascii=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    PUB.parent.mkdir(parents=True, exist_ok=True)
    PUB.write_text(blob, encoding="utf-8")
    print(f"\n-> {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


def _rows(table: pd.DataFrame) -> list:
    out = []
    for (player, bucket), r in table.iterrows():
        c = {k: int(round(r[k])) for k in KEYS
             if k in table.columns and not pd.isna(r[k])}
        out.append({"n": player, "p": bucket,
                    "mt": int(r["matches"]), "c": c})
    return out


if __name__ == "__main__":
    raise SystemExit(main())
