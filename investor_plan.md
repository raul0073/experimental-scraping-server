# Investor Plan — Football Draw/Home Predictor ("the Monkey")

*Drafted 2026-09-11. This is a model-quality assessment and scenario math, not investment
advice; nobody involved is a licensed advisor. Sports betting risks total loss of stake.
All odds-dependent numbers below use a price band the operator supplied (2.65–3.15 for
draws); the system never ingests odds feeds — price judgment stays with the operator.*

## 1. What this is

A walk-forward-validated football prediction system for season 2026/27 covering the top 5
European leagues, producing weekly: 4 draw picks (for Winner שיטה/trixy structures) and
home-win context picks, with a strategy advisor that ranks bet structures by exact
P(profit). Every claim below survived a frozen out-of-sample season; several sophisticated
"upgrades" (opponent adjustment, context features) were tested and **rejected** because
they didn't — this discipline is the product.

## 2. The asset

- **Model**: decay-weighted xG strength ratings → Poisson score grid → draw classifier
  (logistic, 11 features, trained on 11 seasons, n=17,134) → unified probabilities.
  Zone/territory layer (9 zones from shot events) for explanation and a small calibrated
  λ-blend.
- **Infrastructure (the audit trail)**: every pick is committed *before* kickoff to an
  append-only ledger, graded automatically against score and real xG; every advised slip
  is booked by "the Monkey" (1000₪ paper pot, 10₪/line convention) and graded line-by-line
  at frozen breakeven prices; daily scheduled run. Nothing is retro-edited — first
  prediction stands.

## 3. Validated performance (audited, reproducible)

| Claim | Number | Evidence |
|---|---|---|
| Draw pick hit rate (top-4/week, 5-league pool) | **28.9%** vs 24.8% pooled base (+4.1pp) | frozen 25/26 backtest |
| Draw per-pick ceiling (sport limit, 3 independent rankers) | ~32% | tested & converged |
| Confident favorites ("GOLD", model p ≥ 55%) | **65–67% realized** | 24/25 (66.2%, n=627), 25/26, live 26/27 (66.7%) |
| Overall outcome accuracy ceiling | 52–56% | both backtest seasons |
| Draw-week clustering | random (overdispersion ≈ 1.0) | tested — never chase last week |
| Banker effect on draw systems at fair prices | every banker **lowers** P(profit) | exact scenario enumeration |

## 4. Unit economics — flagship slip (שיטה 2/4: 4 draws, 6 double lines, 60₪)

EV per window = 60·(p²o² − 1). Per-leg law: a leg is +EV iff p×odds > 1 — **no structure
can rescue negative-EV legs** (structures only reshape variance).

| Hit rate p | Breakeven odds (per draw) | EV at 2.65 | EV at 2.90 | EV at 3.15 |
|---|---|---|---|---|
| 25% (base-rate slippage) | 4.00 | −56% | −47% | −38% |
| **29% (validated)** | **3.45** | **−41%** | **−29%** | **−17%** |
| 32% (ceiling) | 3.12 | −28% | −14% | **+1.6%** |

**Reading**: inside the supplied 2.65–3.15 band, the flagship is −EV at validated skill.
It becomes breakeven only at ceiling skill *and* top-of-band prices. The prediction edge
(+4.1pp over base) is real; it is simply smaller than the bookmaker margin at those prices.

GOLD home singles: realized 66% → breakeven **1.52**. Any GOLD pick priced above 1.52 is
+EV at realized skill. This is the most investable vein in the system.

## 5. Season projections (Monte Carlo, 200k seasons/cell, seed 7)

Pot starts at 1000₪, 60₪/window. "Ruin" = pot can no longer fund a full slip.
Full grid: `data/reports/investor_projection.json` (regenerate: `scripts/investor_projection.py`).

| Scenario | P(season profit) | Median final | 5%–95% range | P(ruin) |
|---|---|---|---|---|
| 18 windows, p=29%, odds 2.90 | 19% | 677₪ | 172–1,266₪ | 0.6% |
| 18 windows, p=29%, odds 3.15 | 33% | 813₪ | 218–1,508₪ | 0.6% |
| 18 windows, p=32%, odds 3.15 | 51% | 1,011₪ | 416–1,805₪ | 0.2% |
| 30 windows, p=29%, odds 2.90 | 11% | 461₪ | −211–1,218₪ | 22% |
| 30 windows, p=29%, odds 3.15 | 24% | 688₪ | −105–1,581₪ | 12% |
| 30 windows, p=32%, odds 3.15 | 47% | 986₪ | 192–2,078₪ | 4% |

Variance note: in profitable seasons the single 4/4 week historically carries ~40% of
returns — the strategy's income is lumpy by construction.

## 6. The investable thesis (conditions, not promises)

Money should follow this system **only** where the math clears:

1. **Price-gated draws**: play the שיטה only in weeks where offered draw odds ≥ ~3.45
   (validated skill) — the dashboard shows each pick's breakeven; skipping weeks is a
   position.
2. **GOLD home singles above 1.52**: the highest-confidence, lowest-variance vein
   (65–67% realized across three samples).
3. **The refund floor is a dampener, not profit**: 2/4 returns ~51% of stake — it cuts
   drawdowns, it does not create EV.
4. Anything not clearing breakeven stays on the Monkey (paper) — which is also the
   marketing asset: a public, ungameable track record.

## 7. Risk register

- **Variance dominance**: even +EV cells are near coin-flip seasons; 1000₪ pots at 30
  windows carry material ruin risk in −EV cells (up to 68% worst-grid).
- **Model risk**: hit rates are backtested + one live month; regression toward 25% base
  would push breakeven to 4.00.
- **Data risk**: free pipeline depends on Understat (xG backbone) after fbref's Opta loss;
  a second licence loss has no free replacement.
- **Market risk**: Winner's odds band, limits and form rules can change; CLV unmeasured
  (no odds ingestion by design).
- **Key-person**: single operator prices every slip by hand.

## 8. Roadmap & decision gates

1. **Now → season end**: full paper season on the Monkey (automated daily run already live).
2. **Gate A (mid-season)**: live GOLD n ≥ 150 with realized ≥ 62% → GOLD singles graduate
   to smallest real stakes *if* priced > 1.52.
3. **Gate B (season end)**: Monkey ROI + measured frequency of ≥3.45 draw weeks decides
   whether the שיטה ever plays for real money.
4. Repo re-initialization under the product name; this plan and the audit trail travel.

## 9. Reproducibility

Every number above regenerates from the repo: `scripts/run_recal_chain.py` (model +
frozen backtests), `scripts/backtest_season.py --eval 2425`, `scripts/investor_projection.py`
(this plan's grid), dashboard History/Monkey tabs (live audit). If a number can't be
regenerated, it doesn't belong in this document.
