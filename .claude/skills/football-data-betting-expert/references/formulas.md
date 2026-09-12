# Internal formulas — fair odds, EV, forms, model constants

All formulas here are the ones actually shipped/validated in this repo.
Probabilities `p` are the model's unified triplet unless stated.

## 1. Fair odds / value

- Fair (breakeven) odds of a leg: `o_fair = 1 / p`
- A line is value iff `Π(p_i · o_i) > 1` over its legs (single leg: `p·o > 1`)
- EV of a form (stake 1/line): `EV = Σ_lines Π_legs(p_i · o_i) − L` where L = #lines
- Vig removal (1X2, prices o_H,o_D,o_A): implied `q_i = 1/o_i`,
  booksum `S = Σ q_i` (>1); fair probabilities `q_i / S`; margin = `S − 1`
- Closing-line value: `CLV = o_taken / o_closing − 1` (positive = beat the close);
  track only if the user supplies both prices

## 2. Poisson machinery

- Score grid: `P(h,a) = Pois(h; λ_H) · Pois(a; λ_A) · τ(h,a)` normalized, goals 0–10
- Dixon-Coles τ adjusts {0,1}×{0,1}; **fitted ρ = 0 on xG lambdas here** — omit
- Outcome probs = grid sums; modal score PER OUTCOME (never the unconditional
  mode — it reads "always 1-1" for even games)
- Unified triplet: classifier owns P(draw); H/A keep Poisson ratio:
  `H' = H·(1−D_clf)/(H+A)`, `A'` likewise (validated: improved log-loss + home picks)
- Asian handicap fair lines from the grid: e.g. AH −1.5 home win prob
  `= Σ_{h−a≥2} P(h,a)`; AH −1 win `= Σ_{h−a≥2}`, push `= P(h−a=1)`,
  fair quarter-lines split adjacent lines 50/50. Totals: O2.5 `= Σ_{h+a≥3} P(h,a)`

## 3. Team-strength form model (shipped constants)

- `λ_H = (att_H · def_A / μ) · home_boost_league`, `λ_A` mirrored
- att/def = decay-weighted rolling means of xG for/against:
  DECAY 0.985/match, WINDOW 38, MIN_MATCHES 5 (else league-avg prior + low-conf)
- Boosts + ρ refit per season on the season BEFORE the eval season; μ = pool mean
- Opponent adjustment (strength of schedule): **tested, REJECTED** (balanced
  round-robins self-average; frozen eval worsened)
- Draw classifier: logistic over 11 features (Poisson draw, tempo, evenness,
  rolling draw-rates, PPDA, context) trained on 11 seasons (~17k matches);
  more history beat fancier model class (GBM overfit)

## 4. Winner (Toto) form mathematics

- שיטה K/N: all `C(N,K)` combinations are independent lines; **all winning
  lines pay simultaneously**; first payout at K hits; max-win = Σ all lines
- Hit-count distribution over legs (independent): DP
  `d ← d*(1−p) shifted + d*p` per leg → P(exactly k hits)
- Exact scenario table: enumerate all 2^N hit subsets; per subset
  `lines_won = C(|hits|∩combo…)`, return `= Σ_{K-subsets of hits} Π o_i`;
  aggregate by hit count → chance / lines won / %-of-form back / profit?
- Profit threshold: smallest hit count whose return > total stake — for draw
  pairs (o≈3.1): 2/4 profits at 2 hits (pair ≈9.6 vs 6 staked); adding a banker
  (o≈1.3) drops pair payout to ≈4 and adds lines → **banker dilution law**
- Catalog: יאנקי 4→11 (6D+4T+1Q) · לאקי 15 4→15 (+singles) · טריקסי 3→4 ·
  פטנט 3→7 · שיטה K/N generic · באנקר = leg present in every line (true banker
  mode) vs banker-as-selection (just N+1); Winner slips show the latter
- Bankroll sim (the Monkey): unit/line 10₪, pot 1000₪, returns at frozen fair
  prices — structural result; real odds shift actuals

## 5. Validated performance references (frozen backtests)

| Metric | 24/25 | 25/26 | live 26/27 |
|---|---|---|---|
| Outcome accuracy | 53.8% | 51.9% | ~55% |
| GOLD tier (fav ≥55%) | 66.2% (n=627) | — | 66.7% |
| Home picks top-3/wk | 62.3% | 68.4% | — |
| Draw picks top-4/wk (5-league pool) | 29.6% | 32.2% | — |
| Exact-score (modal of predicted outcome) | — | ~10.5% | ~11% |

Draw base rates (pooled 5-league) ≈ 24.8%; league draw ceilings ~32–35%.
Trixy at ~32%/pick: money-back ≈ 1 week in 3, 3/4 ≈ 1–3/season, 4/4 ≈ once per
2–4 seasons. P(4/4) scales as p⁴ — per-pick probability is the only lever.
