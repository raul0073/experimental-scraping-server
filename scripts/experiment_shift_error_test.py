"""QUESTION 2: is the model measurably WRONGER right after a side's style moved?

THE CLAIM UNDER TEST. FormModel decays every side's history at 0.985 a match,
identically, always — football a year ago is 56% as relevant as last week, for
everyone. If a team's style genuinely shifts, that fixed decay is carrying
stale football into the rating, and the model should be visibly worse on the
fixtures straight after the shift. Four previous experiments asked this with
"the manager changed" as the proxy and all four failed. This one measures the
football itself and skips the proxy.

THE SHIFT MEASURE, STATED PLAINLY so the other leg can be compared to it.

    seven style metrics, definitions imported from services/managers/metrics
        press_height  ppda  regain_time  directness  territory
        pass_length   fast_break

    SHORT window   the 5 matches immediately before the fixture
    LONG window    the 15 matches before those (no overlap)
    aggregation    ratio of sums over each window, per the module's house
                   rule — never a mean of per-match ratios
    per metric     d = short - long, then z-scored within league-season
                   across every (team, fixture) observation. The DIFFERENCE
                   is what gets standardised, not the level, because the
                   noise scale of a 5-vs-15 gap is what we need to divide by.
    fixture shift  mean |z| over the seven metrics, taken for each side, and
                   the fixture carries the LARGER of the two: the question is
                   whether EITHER side just moved.

    A team needs all 20 prior matches or it is dropped. Windows reach back
    into the previous season, so history length is CONSTANT at 20 for every
    fixture kept — which is the early-season control: a short history cannot
    inflate the shift because there are no short histories here.

THE ERROR MEASURE, AND WHY IT IS NOT RAW LOG LOSS.

    excess = -log p(y)  -  H(p)          H(p) = -sum p log p

    A model's entropy is its own statement of how hard it finds the fixture,
    and for well-calibrated probabilities E[-log p(y)] = H(p). So `excess` is
    the part of the error the model did not see coming, and comparing it
    across buckets already controls for the thing that wrecks the naive
    version of this test: sides in crisis play differently AND are harder to
    predict for unrelated reasons. A derby and a 1-20 mismatch have wildly
    different log losses and the same expected excess.

    Raw log loss is reported beside it, and the comparison is ALSO run inside
    entropy deciles, because "excess is flat in entropy" is an assumption and
    not a guarantee.

Reads  data/reports/_shift_error_rows.csv   (scripts/experiment_shift_error.py)
Writes data/reports/experiment_shift_error.json

Usage:
    .venv/Scripts/python.exe scripts/experiment_shift_error_test.py
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

# Definitions reused, not reinvented. This module is READ ONLY from here.
from services.managers.metrics import (_median_from_counter, _ratio,
                                       _season_records, _team_bridge)
from services.mental.spells import build as build_spells
from services.understat.understat_service import UnderstatService

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
ROWS = ROOT / "data" / "reports" / "_shift_error_rows.csv"
REPORT = ROOT / "data" / "reports" / "experiment_shift_error.json"

SHORT_W = 5
LONG_W = 15
NEED = SHORT_W + LONG_W

# Each style metric as (numerator counter, denominator counter, scale).
# pass_length is not a ratio and is handled on its own.
RATIO_METRICS: Dict[str, Tuple[str, str, float]] = {
    "press_height": ("def_x_sum", "def_n", 1.0),
    "ppda": ("opp_pass_own60_n", "def_high_n", 1.0),
    "directness": ("direct_n", "pass_end_n", 100.0),
    "territory": ("touch_f3_n", "touch_n", 100.0),
    "fast_break": ("shot_fb_n", "shot_n", 100.0),
    "regain_time": ("regain_sum", "regain_n", 1.0),
}
STYLE_KEYS = list(RATIO_METRICS) + ["pass_length"]


# ------------------------------------------------------------ per-match style
def match_style(league: str, season: str) -> Dict[Tuple[str, str], dict]:
    """(understat_team, date) -> the raw counters for that team that day.

    The counters, not the metrics: a rolling window has to add numerators and
    denominators separately to honour the ratio-of-sums rule."""
    path = RAW / league / f"{season}_stamped.parquet"
    if not path.exists():
        return {}
    recs = _season_records(league, season)
    if not recs:
        return {}

    meta = pd.read_parquet(path, columns=["game_id", "game"])
    meta["game_id"] = meta["game_id"].astype("int64")
    gid_date = {int(g): str(t)[:10] for g, t in
                meta.drop_duplicates("game_id").itertuples(index=False, name=None)}

    ws_dates: Dict[str, set] = defaultdict(set)
    for (gid, team) in recs:
        d = gid_date.get(gid)
        if d:
            ws_dates[team].add(d)

    us = UnderstatService.load(league, season)
    us_dates: Dict[str, set] = defaultdict(set)
    for m in us["matches"]:
        d = str(m["date"])[:10]
        us_dates[m["home_team"]].add(d)
        us_dates[m["away_team"]].add(d)

    bridge = _team_bridge(dict(ws_dates), dict(us_dates))

    out: Dict[Tuple[str, str], dict] = {}
    for (gid, team), rec in recs.items():
        d, us_team = gid_date.get(gid), bridge.get(team)
        if not d or not us_team:
            continue
        keep = {k: rec[k] for _m, (num, den, _s) in RATIO_METRICS.items()
                for k in (num, den)}
        keep["pass_len"] = rec["pass_len"]
        out[(us_team, d)] = keep
    return out


def window_metrics(recs: List[dict]) -> Optional[Dict[str, float]]:
    """The seven metrics over a set of matches, ratio of sums throughout."""
    vals: Dict[str, float] = {}
    for name, (num, den, scale) in RATIO_METRICS.items():
        v = _ratio(float(sum(r[num] for r in recs)),
                   float(sum(r[den] for r in recs)), scale)
        if v is None:
            return None
        vals[name] = v
    lengths: Counter = Counter()
    for r in recs:
        lengths.update(r["pass_len"])
    pl = _median_from_counter(lengths)
    if pl is None:
        return None
    vals["pass_length"] = pl
    return vals


# --------------------------------------------------------------- the analysis
def _days(a: str, b: str) -> float:
    return (pd.Timestamp(a) - pd.Timestamp(b)).days


def entropy(p: List[float]) -> float:
    return float(-sum(q * math.log(max(q, 1e-12)) for q in p))


def boot_diff(a: np.ndarray, b: np.ndarray, seed: int = 0, n: int = 5000) -> dict:
    """Is a's mean above b's? Two independent buckets, so resample each."""
    rng = np.random.default_rng(seed)
    d = float(a.mean() - b.mean())
    draws = np.array([rng.choice(a, len(a), True).mean()
                      - rng.choice(b, len(b), True).mean() for _ in range(n)])
    return {"diff": round(d, 5), "p_worse": round(float((draws > 0).mean()), 4),
            "ci": [round(float(np.percentile(draws, 2.5)), 5),
                   round(float(np.percentile(draws, 97.5)), 5)]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="layer", choices=["ship", "layer", "blend"])
    ap.add_argument("--short", type=int, default=SHORT_W)
    ap.add_argument("--long", type=int, default=LONG_W)
    args = ap.parse_args()
    short_w, long_w = args.short, args.long
    need = short_w + long_w

    if not ROWS.exists():
        print(f"missing {ROWS} — run scripts/experiment_shift_error.py first")
        return 1
    with ROWS.open(encoding="utf-8") as fh:
        fixtures = list(csv.DictReader(fh))
    leagues = sorted({r["league"] for r in fixtures})
    seasons = sorted({r["season"] for r in fixtures})
    print(f"{len(fixtures)} priced fixtures | {leagues} | {seasons}")

    # ---- per-match style counters, for the priced seasons AND the one before
    # each of them, because the long window reaches back over the summer
    all_seasons = sorted(set(seasons) | {"2324", "2425", "2526"})
    style: Dict[str, Dict[Tuple[str, str], dict]] = {}
    # a side's match number WITHIN ITS OWN SEASON. It has to be counted over
    # every match the season contains, not over the fixtures that survive the
    # history filter, or the first kept fixture of 23/24 is called matchday 1.
    md_index: Dict[Tuple[str, str, str], int] = {}
    for lg in leagues:
        for s in all_seasons:
            got = match_style(lg, s)
            if not got:
                continue
            style.setdefault(lg, {}).update(got)
            by_team: Dict[str, List[str]] = defaultdict(list)
            for (team, date) in got:
                by_team[team].append(date)
            for team, dates in by_team.items():
                for i, d in enumerate(sorted(dates)):
                    md_index[(lg, team, d)] = i + 1
            print(f"  style {lg} {s}: {len(got)} team-matches", flush=True)

    # ---- each team's matches in date order, seasons stitched together
    series: Dict[Tuple[str, str], List[Tuple[str, dict]]] = defaultdict(list)
    for lg, d in style.items():
        for (team, date), rec in d.items():
            series[(lg, team)].append((date, rec))
    for k in series:
        series[k].sort()

    # ---- raw per-metric shift for every (fixture, side)
    raw: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    halves: Dict[Tuple[str, str, str], Tuple[dict, dict]] = {}
    for (lg, team), rows in series.items():
        idx = {d: i for i, (d, _r) in enumerate(rows)}
        for date, _rec in rows:
            i = idx[date]
            if i < need:
                continue
            srecs = [r for _d, r in rows[i - short_w:i]]
            lrecs = [r for _d, r in rows[i - need:i - short_w]]
            sh = window_metrics(srecs)
            ln = window_metrics(lrecs)
            if sh is None or ln is None:
                continue
            raw[(lg, team, date)] = {m: sh[m] - ln[m] for m in STYLE_KEYS}
            # SPLIT HALF. The same shift computed twice from two DISJOINT
            # sets of matches — odd-numbered matches of each window against
            # even-numbered ones. Both windows are split, not just the short
            # one: sharing the long term would put a common quantity in both
            # halves and manufacture the agreement this is meant to measure.
            # If these two do not agree, the "shift" is 5-match sampling
            # noise and a null on error means nothing.
            ao = window_metrics(srecs[0::2])
            ae = window_metrics(srecs[1::2])
            bo = window_metrics(lrecs[0::2])
            be = window_metrics(lrecs[1::2])
            if None not in (ao, ae, bo, be):
                halves[(lg, team, date)] = (
                    {m: ao[m] - bo[m] for m in STYLE_KEYS},
                    {m: ae[m] - be[m] for m in STYLE_KEYS})

    # ---- z-score each metric's DIFFERENCE within league-season
    season_of = {(r["league"], r["home"], r["date"]): r["season"] for r in fixtures}
    season_of.update({(r["league"], r["away"], r["date"]): r["season"]
                      for r in fixtures})
    pools: Dict[Tuple[str, str, str], List[float]] = defaultdict(list)
    for (lg, team, date), dv in raw.items():
        s = season_of.get((lg, team, date))
        if s is None:
            continue
        for m in STYLE_KEYS:
            pools[(lg, s, m)].append(dv[m])
    stats = {k: (float(np.mean(v)), float(np.std(v) or 1.0))
             for k, v in pools.items() if len(v) >= 30}

    shift: Dict[Tuple[str, str, str], float] = {}
    for (lg, team, date), dv in raw.items():
        s = season_of.get((lg, team, date))
        zs = []
        for m in STYLE_KEYS:
            st = stats.get((lg, s, m))
            if st is None:
                continue
            zs.append(abs((dv[m] - st[0]) / st[1]))
        if len(zs) == len(STYLE_KEYS):
            shift[(lg, team, date)] = float(np.mean(zs))

    # ---- attach to fixtures
    arm = args.arm
    kept = []
    for r in fixtures:
        key_h = (r["league"], r["home"], r["date"])
        key_a = (r["league"], r["away"], r["date"])
        if key_h not in shift or key_a not in shift:
            continue
        p = [float(r[f"{arm}_H"]), float(r[f"{arm}_D"]), float(r[f"{arm}_A"])]
        tot = sum(p)
        p = [q / tot for q in p]
        y = {"H": 0, "D": 1, "A": 2}[r["y"]]
        h = entropy(p)
        ll = -math.log(max(p[y], 1e-9))
        kept.append({"league": r["league"], "season": r["season"],
                     "date": r["date"], "home": r["home"], "away": r["away"],
                     "shift_h": shift[key_h], "shift_a": shift[key_a],
                     "shift": max(shift[key_h], shift[key_a]),
                     "shift_mean": (shift[key_h] + shift[key_a]) / 2,
                     "H": h, "ll": ll, "excess": ll - h,
                     "gap": abs(float(r["lam_h"]) - float(r["lam_a"])),
                     # the later of the two sides' match numbers, so a fixture
                     # is "early" only when BOTH sides are early
                     "md": max(md_index.get(key_h, 99), md_index.get(key_a, 99)),
                     "lam_h": float(r["lam_h"]), "lam_a": float(r["lam_a"])})
    print(f"\n{len(kept)} of {len(fixtures)} fixtures have a shift for both sides")
    if len(kept) < 200:
        print("too few to say anything")
        return 1

    report: Dict[str, object] = {
        "arm": arm, "short_window": short_w, "long_window": long_w,
        "metrics": STYLE_KEYS, "n_priced": len(fixtures), "n_tested": len(kept),
        "leagues": leagues, "seasons": seasons,
    }

    # ---- 0. IS THE MEASURE A MEASUREMENT? Split-half reliability, reported
    # BEFORE any error comparison, because it decides what a null can mean.
    # Spearman-Brown lifts the two-half correlation to the full window.
    print(f"\nRELIABILITY — same shift from two disjoint halves of the windows")
    print(f"{'metric':<16}{'r_half':>9}{'r_full(SB)':>12}")
    rel = {}
    hk = [k for k in halves if k in shift]
    for m in STYLE_KEYS + ["__score__"]:
        if m == "__score__":
            # the aggregate the test actually uses: mean |z| over the seven
            a, b = [], []
            for k in hk:
                lg, _t, _d = k
                s = season_of.get(k)
                za, zb = [], []
                for mm in STYLE_KEYS:
                    st = stats.get((lg, s, mm))
                    if st is None:
                        continue
                    za.append(abs((halves[k][0][mm] - st[0]) / st[1]))
                    zb.append(abs((halves[k][1][mm] - st[0]) / st[1]))
                if len(za) == len(STYLE_KEYS):
                    a.append(np.mean(za))
                    b.append(np.mean(zb))
            a, b = np.array(a), np.array(b)
        else:
            a = np.array([halves[k][0][m] for k in hk])
            b = np.array([halves[k][1][m] for k in hk])
        if len(a) < 100:
            continue
        r = float(np.corrcoef(a, b)[0, 1])
        sb = 2 * r / (1 + r) if r > -1 else float("nan")
        rel[m] = {"r_half": round(r, 4), "r_full_sb": round(sb, 4), "n": len(a)}
        print(f"{('SHIFT SCORE' if m == '__score__' else m):<16}"
              f"{r:>9.3f}{sb:>12.3f}")
    report["reliability"] = rel

    sh = np.array([r["shift"] for r in kept])
    ex = np.array([r["excess"] for r in kept])
    ll = np.array([r["ll"] for r in kept])
    en = np.array([r["H"] for r in kept])

    print(f"\nshift distribution: mean {sh.mean():.3f}  sd {sh.std():.3f}  "
          f"p50 {np.percentile(sh, 50):.3f}  p90 {np.percentile(sh, 90):.3f}  "
          f"p99 {np.percentile(sh, 99):.3f}  max {sh.max():.3f}")
    print(f"overall: log loss {ll.mean():.4f}  entropy {en.mean():.4f}  "
          f"excess {ex.mean():+.4f}")
    report["overall"] = {"log_loss": round(float(ll.mean()), 4),
                         "entropy": round(float(en.mean()), 4),
                         "excess": round(float(ex.mean()), 4),
                         "shift_mean": round(float(sh.mean()), 4),
                         "shift_p90": round(float(np.percentile(sh, 90)), 4)}

    # ---- 1. quintiles of shift
    print(f"\nBY SHIFT QUINTILE (fixture shift = the more-shifted side)")
    print(f"{'bucket':<12}{'n':>6}{'shift':>9}{'log loss':>11}"
          f"{'entropy':>10}{'excess':>10}")
    qs = np.percentile(sh, [20, 40, 60, 80])
    buckets, quint = [], np.digitize(sh, qs)
    for b in range(5):
        m = quint == b
        buckets.append({"bucket": b + 1, "n": int(m.sum()),
                        "shift": round(float(sh[m].mean()), 4),
                        "log_loss": round(float(ll[m].mean()), 4),
                        "entropy": round(float(en[m].mean()), 4),
                        "excess": round(float(ex[m].mean()), 4)})
        print(f"{'Q' + str(b + 1):<12}{int(m.sum()):>6}{sh[m].mean():>9.3f}"
              f"{ll[m].mean():>11.4f}{en[m].mean():>10.4f}{ex[m].mean():>+10.4f}")
    report["quintiles"] = buckets

    # ---- 2. the tail against the rest, and against a matched rest
    print(f"\nTAIL vs REST  (matched = same contrast inside strata, "
          f"pooled on the high bucket's weights)")
    gap = np.array([r["gap"] for r in kept])
    # two independent ways of saying "these fixtures were alike anyway"
    strata = {
        "entropy_decile": np.digitize(en, np.percentile(en, list(range(10, 100, 10)))),
        "strength_quintile": np.digitize(gap, np.percentile(gap, [20, 40, 60, 80])),
    }

    def matched_diff(hi: np.ndarray, lo: np.ndarray, cells: np.ndarray):
        num = den = 0.0
        used = 0
        for c in np.unique(cells):
            a, b2 = hi & (cells == c), lo & (cells == c)
            if a.sum() >= 10 and b2.sum() >= 10:
                num += a.sum() * (ex[a].mean() - ex[b2].mean())
                den += a.sum()
                used += 1
        return (round(num / den, 5) if den else None, int(den), used)

    tails = []
    for pct in (80, 90, 95):
        cut = float(np.percentile(sh, pct))
        hi, lo = sh >= cut, sh < cut
        b = boot_diff(ex[hi], ex[lo])
        braw = boot_diff(ll[hi], ll[lo])
        mm = {k: matched_diff(hi, lo, v) for k, v in strata.items()}
        tails.append({"pct": pct, "cut": round(cut, 4),
                      "n_high": int(hi.sum()), "n_low": int(lo.sum()),
                      "excess_high": round(float(ex[hi].mean()), 4),
                      "excess_low": round(float(ex[lo].mean()), 4),
                      "excess_diff": b, "raw_ll_diff": braw,
                      "matched": {k: {"diff": v[0], "n_matched": v[1],
                                      "cells": v[2]} for k, v in mm.items()}})
        print(f"  top {100 - pct:>2}%  n={int(hi.sum()):<5} vs {int(lo.sum()):<5}"
              f"  excess {ex[hi].mean():+.4f} vs {ex[lo].mean():+.4f}"
              f"  diff {b['diff']:+.4f} "
              f"[{b['ci'][0]:+.4f},{b['ci'][1]:+.4f}] P(worse)={b['p_worse']:.3f}")
        for k, v in mm.items():
            print(f"        matched on {k:<18}"
                  + (f"{v[0]:+.5f}  (n={v[1]}, {v[2]} cells)"
                     if v[0] is not None else "no usable cells"))
    report["tails"] = tails

    # ---- 3. a regression, because buckets throw information away
    md = np.array([r["md"] for r in kept], dtype=float)
    X = np.column_stack([np.ones(len(kept)), sh, en, md / 38.0])
    beta, *_ = np.linalg.lstsq(X, ex, rcond=None)
    resid = ex - X @ beta
    dof = len(kept) - X.shape[1]
    cov = float(resid @ resid / dof) * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    names = ["const", "shift", "entropy", "matchday/38"]
    print(f"\nOLS  excess ~ shift + entropy + matchday      n={len(kept)}")
    for nm, bb, ss in zip(names, beta, se):
        print(f"  {nm:<14}{bb:>+10.4f}  se {ss:.4f}  t {bb / ss:>+6.2f}")
    report["ols_excess"] = {nm: {"beta": round(float(bb), 5),
                                 "se": round(float(ss), 5),
                                 "t": round(float(bb / ss), 2)}
                            for nm, bb, ss in zip(names, beta, se)}

    # ---- 4. early season, because it is the obvious confound
    print(f"\nEXCLUDING MATCHDAYS 1-6")
    late = md > 6
    if late.sum() > 200:
        shl, exl = sh[late], ex[late]
        cut = float(np.percentile(shl, 90))
        hi, lo = shl >= cut, shl < cut
        b = boot_diff(exl[hi], exl[lo])
        print(f"  n={int(late.sum())}  top 10% n={int(hi.sum())}  "
              f"excess {exl[hi].mean():+.4f} vs {exl[lo].mean():+.4f}  "
              f"diff {b['diff']:+.4f} P(worse)={b['p_worse']:.3f}")
        report["late_season_only"] = {"n": int(late.sum()),
                                      "n_high": int(hi.sum()), "top10": b}

    # ---- 5. PER METRIC, because a mean over seven can bury one that matters
    print(f"\nPER-METRIC: top-decile |z| on that metric alone vs the rest")
    print(f"{'metric':<16}{'n_hi':>6}{'excess_hi':>12}{'excess_lo':>12}"
          f"{'diff':>10}{'P(worse)':>10}")
    per_metric = {}
    for m in STYLE_KEYS:
        zz = []
        for r in kept:
            kh = (r["league"], r["home"], r["date"])
            ka = (r["league"], r["away"], r["date"])
            sh_h = stats.get((r["league"], r["season"], m))
            if sh_h is None:
                zz.append(np.nan)
                continue
            mu, sd = sh_h
            zz.append(max(abs((raw[kh][m] - mu) / sd), abs((raw[ka][m] - mu) / sd)))
        zz = np.array(zz)
        ok = ~np.isnan(zz)
        if ok.sum() < 300:
            continue
        cut = float(np.percentile(zz[ok], 90))
        hi, lo = ok & (zz >= cut), ok & (zz < cut)
        b = boot_diff(ex[hi], ex[lo], seed=7)
        per_metric[m] = {"n_high": int(hi.sum()), **b,
                         "excess_high": round(float(ex[hi].mean()), 4),
                         "excess_low": round(float(ex[lo].mean()), 4)}
        print(f"{m:<16}{int(hi.sum()):>6}{ex[hi].mean():>+12.4f}"
              f"{ex[lo].mean():>+12.4f}{b['diff']:>+10.4f}{b['p_worse']:>10.3f}")
    report["per_metric"] = per_metric

    # ---- 6. DOES THE MEASURE MEASURE ANYTHING? If the shift score is just
    # 5-match sampling noise then a null on error is uninformative rather
    # than a result. A manager change is a bad proxy for style changing, but
    # it is not a NULL proxy: if the direct measure never fires around one,
    # the direct measure is noise and nothing here means anything.
    try:
        starts: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for lg in leagues:
            for s in build_spells(lg, all_seasons, absorb_short=False):
                if s.start:
                    starts[(lg, s.team)].append(str(s.start)[:10])
        near, far = [], []
        for (lg, team, date), _dv in raw.items():
            z = shift.get((lg, team, date))
            if z is None:
                continue
            ds = starts.get((lg, team)) or []
            # the short window is the 5 matches before this fixture, so a
            # tenure that began inside those 5 is what "just changed" means
            fresh = any(0 <= _days(date, d0) <= 45 for d0 in ds)
            (near if fresh else far).append(z)
        if len(near) >= 25:
            nb = boot_diff(np.array(near), np.array(far), seed=11)
            print(f"\nVALIDATION — shift score within 45 days of a new spell")
            print(f"  new manager n={len(near)}  mean shift {np.mean(near):.4f}")
            print(f"  everyone else n={len(far)}  mean shift {np.mean(far):.4f}")
            print(f"  diff {nb['diff']:+.4f} "
                  f"[{nb['ci'][0]:+.4f},{nb['ci'][1]:+.4f}] "
                  f"P(higher)={nb['p_worse']:.3f}")
            report["validation_new_manager"] = {
                "n_near": len(near), "n_far": len(far),
                "shift_near": round(float(np.mean(near)), 4),
                "shift_far": round(float(np.mean(far)), 4), **nb}
        else:
            print(f"\nVALIDATION — only {len(near)} post-change observations")
    except Exception as e:                                       # noqa: BLE001
        print(f"\nspells unavailable: {type(e).__name__}: {e}")

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
