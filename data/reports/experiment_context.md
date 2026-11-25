# Context layer against the closing line

9897 fixtures, seasons 1920..2526, walk-forward. 'dirichlet' is the same stacker without context, so context's marginal value is context minus dirichlet.

| candidate | log-loss | accuracy | gap to market | calls >=55%: n / hit / expected | calls >=60%: n / hit / expected | vs blend p |
|---|---|---|---|---|---|---|
| blend | 0.98582 | 52.6% | +0.0181 | 3212 / 68.6% / 64.8% | 2171 / 72.0% / 68.3% |  |
| market | 0.96772 | 54.1% | +0.0000 | 3882 / 68.1% / 66.6% | 2769 / 72.2% / 70.3% | 1.0 |
| dirichlet | 0.98305 | 52.6% | +0.0153 | 3787 / 66.6% / 67.0% | 2779 / 69.6% / 70.4% | 0.9992 |
| context | 0.98604 | 52.6% | +0.0183 | 4108 / 65.7% / 66.9% | 3015 / 69.0% / 70.3% | 0.4323 |

context vs dirichlet: {'mean_gain': -0.003, 'p_better': 0.013}

## Gap to market by league

| candidate | Premier League | La Liga | Bundesliga | Serie A |
|---|---|---|---|---|
| blend | +0.0156 (52.7%) | +0.0190 (52.3%) | +0.0145 (52.0%) | +0.0226 (53.3%) |
| market | +0.0000 (54.2%) | +0.0000 (54.1%) | +0.0000 (53.2%) | +0.0000 (54.7%) |
| dirichlet | +0.0151 (52.9%) | +0.0153 (52.5%) | +0.0126 (52.0%) | +0.0177 (53.0%) |
| context | +0.0227 (52.7%) | +0.0125 (53.3%) | +0.0152 (51.6%) | +0.0222 (52.7%) |

## Feature weight (mean |w| over seasons and outcomes, standardised inputs)

- europe_a: 0.079
- gap_title_h: 0.076
- gap_europe_a: 0.076
- gap_title_a: 0.069
- europe_h: 0.056
- gap_europe_h: 0.055
- gap_drop_a: 0.05
- rest_a: 0.049
- gap_drop_h: 0.046
- congested_h: 0.044
- ppg_h: 0.041
- rest_h: 0.04
- dead_h: 0.033
- ppg_a: 0.029
- congested_a: 0.024
- dead_a: 0.023
- midweek: 0.021
- season_frac: 0.013
- derby: 0.013
