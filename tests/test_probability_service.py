"""Unit tests for services/predictions/probability_service.py — the pure
arithmetic every published triplet is built from."""
from __future__ import annotations

import pytest

from services.predictions.probability_service import (
    DRAW_CALL_MIN,
    MAX_GOALS,
    call_outcome,
    modal_scores_by_outcome,
    outcome_probs,
    score_grid,
    unified_probs,
)

LAMBDAS = [(1.4, 1.1, 0.0), (0.8, 0.9, -0.1), (2.5, 0.6, 0.05), (1.0, 1.0, -0.13)]


@pytest.mark.parametrize("lh,la,rho", LAMBDAS)
def test_score_grid_sums_to_one(lh, la, rho):
    grid = score_grid(lh, la, rho)
    assert len(grid) == MAX_GOALS + 1 and all(len(r) == MAX_GOALS + 1 for r in grid)
    assert sum(sum(r) for r in grid) == pytest.approx(1.0, abs=1e-9)
    assert all(v >= 0 for r in grid for v in r)


@pytest.mark.parametrize("lh,la,rho", LAMBDAS)
def test_outcome_probs_triplet_sums_to_one(lh, la, rho):
    p = outcome_probs(lh, la, rho)
    assert set(p) == {"home", "draw", "away"}
    # each side is rounded to 4 dp, so the sum may be off by rounding only
    assert sum(p.values()) == pytest.approx(1.0, abs=2e-4)


def test_outcome_probs_favours_the_stronger_side():
    assert outcome_probs(2.5, 0.6)["home"] > outcome_probs(0.6, 2.5)["home"]
    assert outcome_probs(0.6, 2.5)["away"] > 0.5


def test_dixon_coles_rho_moves_draw_mass():
    # negative rho inflates 0-0 and 1-1 — exactly where draws live
    assert outcome_probs(1.2, 1.2, -0.13)["draw"] > outcome_probs(1.2, 1.2, 0.0)["draw"]


def test_unified_probs_keeps_home_away_ratio_and_sets_draw():
    poisson = {"home": 0.50, "draw": 0.20, "away": 0.30}
    u = unified_probs(poisson, 0.31)
    assert u["draw"] == 0.31
    assert sum(u.values()) == pytest.approx(1.0, abs=2e-4)
    assert u["home"] / u["away"] == pytest.approx(poisson["home"] / poisson["away"], rel=1e-3)


def test_unified_probs_without_classifier_is_the_poisson_triplet():
    poisson = {"home": 0.4, "draw": 0.3, "away": 0.3}
    assert unified_probs(poisson, None) is poisson


def test_call_outcome_applies_draw_call_min():
    assert call_outcome({"home": 0.45, "draw": DRAW_CALL_MIN, "away": 0.24}) == "draw"
    assert call_outcome({"home": 0.45, "draw": DRAW_CALL_MIN - 0.001, "away": 0.24}) == "home"
    assert call_outcome({"home": 0.30, "draw": 0.25, "away": 0.45}) == "away"
    # the ceiling rule beats the argmax: a 0.33 draw is called over a 0.40 home
    assert call_outcome({"home": 0.40, "draw": 0.33, "away": 0.27}) == "draw"


def test_modal_scores_match_their_outcome():
    best = modal_scores_by_outcome(1.4, 1.1, -0.1)
    for outcome, (score, p) in best.items():
        h, a = map(int, score.split("-"))
        assert {"home": h > a, "draw": h == a, "away": h < a}[outcome]
        assert 0 < p <= 1
