"""Which metrics are allowed to matter, for each position bucket?

This is the config. Not a list of numbers someone thought sounded mental —
a list of numbers that survive two tests, asked separately of every bucket
because a wing-back and a centre-back are not being asked the same question:

    repeat   his season against his next season. Is it a trait, or did it
             happen to him once?
    self     a season's odd matches against its even ones. Can we measure
             it at all? A metric that will not agree with itself inside one
             season is noise, and its failure to repeat across two says
             nothing about the player.

Both are asked of the role, not the man: Rice's central-midfield minutes are
correlated against his central-midfield minutes the following season, and
his defensive-midfield minutes separately. Mixing them would put a
midfielder's two different jobs on both axes of the same scatter.

Where several season pairs exist their player-pairs are STACKED rather than
averaged, so one rho is computed from all the evidence there is. Small
buckets stay small — a wing-back ranking is drawn from a handful of teams —
so every result carries its n and the page is expected to show it.

Writes data/reports/metric_reliability.json, consumed by build_mental_web.

Usage: .venv/Scripts/python.exe scripts/build_reliability.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from services.mental.event_metrics import METRICS
from services.mental.positions import BUCKET_LABEL, BUCKET_ORDER
from services.mental.role_bank import Store, banks, fold_season, seasons_on_disk

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reports" / "metric_reliability.json"
# Ten full matches in the role, in each of two consecutive seasons.
#
# This sat at 450 while only two seasons were on disk, because at 900 three
# of the nine buckets returned nothing at all — the same player has to log
# the same role twice, and wing-backs, attacking midfielders and strikers
# rotate. With 23/24 scraped there are two season-pairs to stack instead of
# one, and 900 now covers eight of nine buckets with materially bigger
# samples (centre-backs 75 player-pairs, up from 51). Fewer minutes per
# season means a noisier estimate, which ATTENUATES the correlation, so the
# looser bar was biased toward refusing real traits. Worth leaving behind.
#
# Wing-back still returns nothing and probably always will: only eight men
# hold the role for a full season. It falls back to the split-half test,
# which the page renders as "untested" rather than as a failure.
MIN_FULL = 900
MIN_HALF = 450        # each half of a split season
MIN_PLAYERS = 15      # below this a correlation is not worth reporting

# what a rho means. Deliberately stricter for `self` than for `repeat`: a
# metric that cannot reproduce itself inside one season cannot be rescued by
# a good cross-season number, which would then be a coincidence.
def verdict(rho: float) -> str:
    return ("strong" if rho >= 0.6 else
            "moderate" if rho >= 0.4 else
            "weak" if rho >= 0.25 else
            "noise")


def role_banks(league: str, season: str, min_minutes: int,
               half: str | None = None) -> dict:
    store = Store()
    fold_season(league, season, store, half=half)
    return banks(store, min_minutes)


def stack(pairs: list) -> dict:
    """metric -> bucket -> {rho, n}, from stacked (earlier, later) banks."""
    obs = defaultdict(lambda: defaultdict(lambda: ([], [])))
    for a, b in pairs:
        for bucket in BUCKET_ORDER:
            if bucket not in a or bucket not in b:
                continue
            shared = a[bucket].index.intersection(b[bucket].index)
            if shared.empty:
                continue
            for metric in METRICS:
                if metric not in a[bucket].columns or metric not in b[bucket].columns:
                    continue
                x = a[bucket].loc[shared, metric]
                y = b[bucket].loc[shared, metric]
                ok = x.notna() & y.notna()
                if not ok.any():
                    continue
                xs, ys = obs[metric][bucket]
                xs.extend(x[ok].tolist())
                ys.extend(y[ok].tolist())

    res: dict = {}
    for metric, per in obs.items():
        for bucket, (xs, ys) in per.items():
            if len(xs) < MIN_PLAYERS:
                continue
            rho = pd.Series(xs).rank().corr(pd.Series(ys).rank())
            if pd.isna(rho):
                continue
            res.setdefault(metric, {})[bucket] = {
                "rho": round(float(rho), 3), "n": len(xs)}
    return res


def main() -> int:
    global MIN_FULL, MIN_HALF
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--min-full", type=int, default=MIN_FULL)
    ap.add_argument("--min-half", type=int, default=MIN_HALF)
    ap.add_argument("--dry-run", action="store_true",
                    help="report coverage without overwriting the config")
    args = ap.parse_args()
    MIN_FULL, MIN_HALF = args.min_full, args.min_half
    seasons = seasons_on_disk(args.league)
    if len(seasons) < 2:
        print(f"need two stamped seasons, found {seasons}")
        return 1

    print(f"seasons on disk: {', '.join(seasons)}")
    full = {}
    for s in seasons:
        print(f"  bank {s} ({MIN_FULL}+ min in role) ...", flush=True)
        full[s] = role_banks(args.league, s, MIN_FULL)
    repeat = stack([(full[a], full[b]) for a, b in zip(seasons, seasons[1:])])

    halves = []
    for s in seasons:
        print(f"  split-half {s} ({MIN_HALF}+ min in role) ...", flush=True)
        halves.append((role_banks(args.league, s, MIN_HALF, "odd"),
                       role_banks(args.league, s, MIN_HALF, "even")))
    self_ = stack(halves)

    payload = {"league": args.league, "seasons": seasons,
               "min_full": MIN_FULL, "min_half": MIN_HALF,
               "min_players": MIN_PLAYERS,
               "repeat": repeat, "self": self_}
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"\n{'':24}", end="")
    for b in BUCKET_ORDER:
        print(f"{b:>7}", end="")
    print("\n" + "-" * (24 + 7 * len(BUCKET_ORDER)))
    for metric in METRICS:
        row = repeat.get(metric, {})
        if not row:
            continue
        print(f"{metric:<24}", end="")
        for b in BUCKET_ORDER:
            r = row.get(b)
            print(f"{r['rho']:>7.2f}" if r else f"{'--':>7}", end="")
        print()
    print("\n(cross-season rho. '--' = fewer than "
          f"{MIN_PLAYERS} players in that bucket in both seasons)")

    keep = sum(1 for m in METRICS for b in BUCKET_ORDER
               if repeat.get(m, {}).get(b, {}).get("rho", 0) >= 0.4)
    tot = sum(1 for m in METRICS for b in BUCKET_ORDER if repeat.get(m, {}).get(b))
    print(f"\nmetric/bucket pairs measured: {tot}   "
          f"moderate or better: {keep}")
    print(f"{'bucket':<8}{'repeat':>8}{'max n':>7}{'self':>8}{'max n':>7}")
    for b in BUCKET_ORDER:
        rs = [v[b] for v in repeat.values() if b in v]
        ss = [v[b] for v in self_.values() if b in v]
        print(f"{b:<8}{len(rs):>8}{max((r['n'] for r in rs), default=0):>7}"
              f"{len(ss):>8}{max((s['n'] for s in ss), default=0):>7}")
    print(f"-> {OUT}" if not args.dry_run else "\n(dry run — config not written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
