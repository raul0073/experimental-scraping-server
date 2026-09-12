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
