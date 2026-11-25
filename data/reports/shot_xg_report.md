# Shot xG from WhoScored events — 2026-11-25 16:29

149,284 shots, 16,484 goals over 4 seasons and five leagues. 147,028 fitted (own goals and 1,770 penalties aside; penalties take 0.783).

## Hold-out 2526

log-loss 0.2560 against 0.3218 for the goal rate alone; mean xG 0.1008, goal rate 0.0985.

| decile | mean xG | goal rate | shots |
|---|---|---|---|
| 1 | 0.019 | 0.018 | 4350 |
| 2 | 0.028 | 0.027 | 4350 |
| 3 | 0.033 | 0.034 | 4350 |
| 4 | 0.039 | 0.034 | 4350 |
| 5 | 0.044 | 0.043 | 4350 |
| 6 | 0.051 | 0.053 | 4350 |
| 7 | 0.061 | 0.064 | 4350 |
| 8 | 0.080 | 0.078 | 4349 |
| 9 | 0.209 | 0.208 | 4349 |
| 10 | 0.443 | 0.428 | 4349 |

## Calibration to Understat (matches both cover)

| league | matches | slope | intercept | r | mean abs diff after | WhoScored short names unmapped |
|---|---|---|---|---|---|---|
| ENG-Premier League | 468 | 1.088 | +0.049 | 0.960 | 0.173 | — |
| ESP-La Liga | 481 | 1.087 | +0.039 | 0.960 | 0.175 | — |
| ITA-Serie A | 472 | 1.108 | +0.017 | 0.968 | 0.161 | — |
| GER-Bundesliga | 376 | 1.085 | +0.049 | 0.957 | 0.219 | — |
| FRA-Ligue 1 | 381 | 1.053 | +0.048 | 0.960 | 0.186 | — |

## Filled

| league | season | Understat rows | filled from WhoScored | first | last |
|---|---|---|---|---|---|
| ENG-Premier League | 2627 | 88 | 22 | 2026-11-01 | 2026-11-23 |
| ESP-La Liga | 2627 | 104 | 25 | 2026-11-01 | 2026-11-23 |
| ITA-Serie A | 2627 | 93 | 27 | 2026-11-01 | 2026-11-23 |
| GER-Bundesliga | 2627 | 70 | 20 | 2026-11-01 | 2026-11-22 |
| FRA-Ligue 1 | 2627 | 76 | 24 | 2026-08-23 | 2026-11-22 |

model: `data\models\shot_xg.json` · 82s
