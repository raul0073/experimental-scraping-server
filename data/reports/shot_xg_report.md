# Shot xG from WhoScored events — 2026-11-27 15:36

149,284 shots, 16,484 goals over 4 seasons and five leagues. 147,028 fitted (own goals and 1,770 penalties aside; penalties take 0.783).

## Hold-out 2526

log-loss 0.2560 against 0.3218 for the goal rate alone; mean xG 0.1008, goal rate 0.0985.

| decile | mean xG | goal rate | shots |
|---|---|---|---|
| 1 | 0.019 | 0.018 | 4350 |
| 2 | 0.028 | 0.026 | 4350 |
| 3 | 0.033 | 0.034 | 4350 |
| 4 | 0.039 | 0.035 | 4350 |
| 5 | 0.044 | 0.041 | 4350 |
| 6 | 0.051 | 0.053 | 4350 |
| 7 | 0.061 | 0.065 | 4350 |
| 8 | 0.080 | 0.078 | 4349 |
| 9 | 0.209 | 0.208 | 4349 |
| 10 | 0.444 | 0.427 | 4349 |

## Calibration to Understat (matches both cover)

| league | matches | slope | intercept | r | mean abs diff after | WhoScored short names unmapped |
|---|---|---|---|---|---|---|
| ENG-Premier League | 468 | 1.087 | +0.049 | 0.960 | 0.173 | — |
| ESP-La Liga | 481 | 1.087 | +0.039 | 0.961 | 0.174 | — |
| ITA-Serie A | 473 | 1.109 | +0.018 | 0.967 | 0.161 | — |
| GER-Bundesliga | 376 | 1.086 | +0.049 | 0.957 | 0.219 | — |
| FRA-Ligue 1 | 381 | 1.055 | +0.046 | 0.960 | 0.185 | — |

## Filled

| league | season | Understat rows | filled from WhoScored | first | last |
|---|---|---|---|---|---|
| ENG-Premier League | 2627 | 88 | 22 | 2026-11-01 | 2026-11-23 |
| ESP-La Liga | 2627 | 104 | 25 | 2026-11-01 | 2026-11-23 |
| ITA-Serie A | 2627 | 93 | 27 | 2026-11-01 | 2026-11-23 |
| GER-Bundesliga | 2627 | 70 | 20 | 2026-11-01 | 2026-11-22 |
| FRA-Ligue 1 | 2627 | 76 | 24 | 2026-08-23 | 2026-11-22 |

model: `data\models\shot_xg.json` · 148s
