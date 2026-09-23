from __future__ import annotations
import math
from typing import Dict, List, Tuple

MAX_GOALS = 10


def _dc_tau(hg: int, ag: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles low-score correction — adjusts 0-0/1-0/0-1/1-1 mass,
    which is exactly where draw probabilities live."""
    if hg == 0 and ag == 0:
        return 1.0 - lh * la * rho
    if hg == 0 and ag == 1:
        return 1.0 + lh * rho
    if hg == 1 and ag == 0:
        return 1.0 + la * rho
    if hg == 1 and ag == 1:
        return 1.0 - rho
    return 1.0


def score_grid(lam_home: float, lam_away: float, rho: float = 0.0) -> List[List[float]]:
    """(MAX_GOALS+1)^2 matrix of scoreline probabilities, renormalized."""
    ph = [math.exp(-lam_home) * lam_home ** k / math.factorial(k) for k in range(MAX_GOALS + 1)]
    pa = [math.exp(-lam_away) * lam_away ** k / math.factorial(k) for k in range(MAX_GOALS + 1)]
    grid = [[ph[h] * pa[a] * _dc_tau(h, a, lam_home, lam_away, rho)
             for a in range(MAX_GOALS + 1)] for h in range(MAX_GOALS + 1)]
    total = sum(sum(row) for row in grid) or 1.0
    return [[max(v, 0.0) / total for v in row] for row in grid]


def outcome_probs(lam_home: float, lam_away: float, rho: float = 0.0) -> Dict[str, float]:
    grid = score_grid(lam_home, lam_away, rho)
    home = draw = away = 0.0
    for h in range(MAX_GOALS + 1):
        for a in range(MAX_GOALS + 1):
            if h > a:
                home += grid[h][a]
            elif h == a:
                draw += grid[h][a]
            else:
                away += grid[h][a]
    return {"home": round(home, 4), "draw": round(draw, 4), "away": round(away, 4)}


def top_scorelines(lam_home: float, lam_away: float, rho: float = 0.0,
                   n: int = 3) -> List[Tuple[str, float]]:
    grid = score_grid(lam_home, lam_away, rho)
    flat = [(f"{h}-{a}", grid[h][a])
            for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1)]
    flat.sort(key=lambda kv: kv[1], reverse=True)
    return [(s, round(p, 4)) for s, p in flat[:n]]


def unified_probs(poisson: Dict[str, float], p_draw_clf: float | None) -> Dict[str, float]:
    """The tool's single official outcome triplet: the draw classifier (the
    calibrated draw estimator) owns P(draw); home/away keep their Poisson
    ratio and rescale to fill the rest."""
    if p_draw_clf is None:
        return poisson
    rest = 1.0 - p_draw_clf
    s = (poisson["home"] + poisson["away"]) or 1.0
    return {"home": round(poisson["home"] / s * rest, 4),
            "draw": round(p_draw_clf, 4),
            "away": round(poisson["away"] / s * rest, 4)}


# A pure argmax essentially never says draw (draws cap at ~32-35% while a
# win side spreads to 36%+), which misrepresents football — ~26% of matches
# draw. Rule (user decision 2026-09-15): once the calibrated draw probability
# reaches the draw CEILING zone, the call is a draw.
#
# RE-SWEPT 2026-09-20 on 1,714 walk-forward fixtures — every 25/26 match of
# all five leagues — priced by the model that now ships. See
# scripts/sweep_draw_call.py and data/reports/sweep_draw_call.json.
#
# 🐛 The old 0.32 was swept on 194 graded live rows and came with a note that
# 0.30 "would cost 6pp" of accuracy. There is no such cliff: across the full
# grid accuracy moves smoothly, 52.2% at 0.33 down to 50.9% at 0.30. A
# six-point step between adjacent thresholds was the sample being too small
# to answer the question, not a decision boundary.
#
# WHAT MOVED THE CHOICE WAS SUPPLY, NOT PURITY. Over ~38 rounds:
#
#   0.32   96 draw calls  = 2.5 a week   hit 34.4%  (+8.8 over base)
#   0.31  187 draw calls  = 4.9 a week   hit 32.6%  (+7.0 over base)
#
# The product commits to FOUR draw picks a week. At 0.32 the model makes two
# and a half calls a week, so the ticket cannot be filled from its own stated
# calls — a threshold with a better hit rate that cannot supply the product
# is worse than one that can. 0.31 costs 0.2pp of overall accuracy (52.0% vs
# a grid best of 52.2%) and its draw calls still beat the 25.6% base rate at
# p=0.019.
DRAW_CALL_MIN = 0.31


def call_outcome(probs: Dict[str, float]) -> str:
    """The model's single stated call for a fixture."""
    if probs.get("draw", 0.0) >= DRAW_CALL_MIN:
        return "draw"
    return max(probs, key=probs.get)


def modal_scores_by_outcome(lam_home: float, lam_away: float,
                            rho: float = 0.0) -> Dict[str, Tuple[str, float]]:
    """Most likely scoreline GIVEN each outcome. The unconditional modal
    score is usually 1-1 for even fixtures (a draw's mass concentrates in one
    cell while a win's spreads over many) — presenting per-outcome modes
    avoids that misleading headline."""
    grid = score_grid(lam_home, lam_away, rho)
    best = {"home": ("", 0.0), "draw": ("", 0.0), "away": ("", 0.0)}
    for h in range(MAX_GOALS + 1):
        for a in range(MAX_GOALS + 1):
            key = "home" if h > a else "draw" if h == a else "away"
            if grid[h][a] > best[key][1]:
                best[key] = (f"{h}-{a}", round(grid[h][a], 4))
    return best
