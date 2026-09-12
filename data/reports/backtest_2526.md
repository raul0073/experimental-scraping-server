# Backtest 25/26 — frozen params fit on 24/25

- log-loss (all fixtures, n=1752): **0.9959** vs base-rate predictor 1.0737
- log-loss (confident only, n=1687): **0.9957** vs base-rate predictor 1.0741

## Draw picks — top 4 (5 leagues), Poisson-ranked

- weeks simulated: 38; picks: 152
- **hit rate: 32.2%** (base rate ~ 24.8%; edge +7.4%)
- avg predicted probability of picks: 31.9% (calibration: should track hit rate)
- weekly hits distribution: 0/4×6, 1/4×19, 2/4×9, 3/4×4, 4/4×0

## Draw picks — top 4 (5 leagues), CLASSIFIER-ranked

- weeks simulated: 38; picks: 152
- **hit rate: 32.2%** (base rate ~ 24.8%; edge +7.4%)
- avg predicted probability of picks: 31.9% (calibration: should track hit rate)
- weekly hits distribution: 0/4×6, 1/4×19, 2/4×9, 3/4×4, 4/4×0

## Home-win picks — top 3 (EPL + Ligue 1)

- weeks simulated: 38; picks: 114
- **hit rate: 68.4%** (base rate ~ 43.8%; edge +24.7%)
- avg predicted probability of picks: 66.7% (calibration: should track hit rate)
- weekly hits distribution: 0/3×1, 1/3×7, 2/3×19, 3/3×11
