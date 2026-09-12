# Backtest 25/26 — frozen params fit on 24/25

- log-loss (all fixtures, n=1752): **0.9954** vs base-rate predictor 1.0737
- log-loss (confident only, n=1714): **0.9952** vs base-rate predictor 1.0750

## Draw picks — top 4 (5 leagues), Poisson-ranked

- weeks simulated: 38; picks: 152
- **hit rate: 32.9%** (base rate ~ 24.8%; edge +8.1%)
- avg predicted probability of picks: 31.9% (calibration: should track hit rate)
- weekly hits distribution: 0/4×6, 1/4×18, 2/4×10, 3/4×4, 4/4×0

## Draw picks — top 4 (5 leagues), CLASSIFIER-ranked

- weeks simulated: 38; picks: 152
- **hit rate: 32.9%** (base rate ~ 24.8%; edge +8.1%)
- avg predicted probability of picks: 31.9% (calibration: should track hit rate)
- weekly hits distribution: 0/4×6, 1/4×18, 2/4×10, 3/4×4, 4/4×0

## Home-win picks — top 3 (EPL + Ligue 1)

- weeks simulated: 38; picks: 114
- **hit rate: 69.3%** (base rate ~ 43.8%; edge +25.5%)
- avg predicted probability of picks: 67.0% (calibration: should track hit rate)
- weekly hits distribution: 0/3×1, 1/3×7, 2/3×18, 3/3×12
