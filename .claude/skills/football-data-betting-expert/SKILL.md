---
name: football-data-betting-expert
description: Football analytics + betting-form mathematics expert, built from this repo's validated predictor. Use whenever the conversation involves football/soccer data (xG, xA, PPDA, Poisson, team strength, draws, match prediction), betting structures (Winner/Toto forms, שיטה, יאנקי, טריקסי, באנקר, system K/N, Asian handicaps, fair odds, breakeven, +EV, vig, CLV), pick evaluation, bankroll simulation, or changes to this repo's prediction/advisor/monkey services — even when the user doesn't name the skill and just says things like "why is this pick here", "is this form worth it", "improve the draws", or pastes a betting slip.
---

# Football Data & Betting Expert

Domain expertise distilled from a working predictor (this repo) whose every claim
was gated by walk-forward backtests. Prefer the validated numbers below over
general intuition — each one displaced an intuition that tested wrong.

## Domain focus

- Quantitative football analytics: xG/npxG/xA, PPDA, deep completions, Poisson
  score grids, Dixon-Coles, multiplicative team-strength models, zone/territory
  models from shot-event coordinates
- Betting-market mechanics: fair odds, breakeven, per-line EV, vig removal,
  closing-line value, Asian-handicap derivation from score grids
- Winner (Toto) form structures: שיטה K/N, יאנקי, לאקי 15, טריקסי, פטנט, באנקר —
  line mechanics, scenario math, profit thresholds, bankroll simulation

## Validated laws of this domain (each one was tested here)

1. **Draws are a variance event, not a trait.** Per-fixture draw probability
   lives in ~20–32%; no free pre-match signal beats ~32% per pick (three
   independent rankers converged). Draw-heavy weeks are binomial clumping
   (overdispersion ≈ 1.0) — never chase last week's draws.
2. **Outcome-accuracy ceiling ≈ 52–56% overall** (draws are 25% of outcomes and
   never the argmax). The 65%+ vein is the confident tier: favorites ≥55%
   realized 65–67% across two backtest seasons and live play.
3. **Structure choice is P(profit) math, not vibes.** Draw pairs (~9–10× a line)
   are the profit engine of draw systems; at fair prices every banker added to a
   draw system RAISES cash-back frequency but LOWERS profit frequency. Bankers
   are a price tool (use only when the book prices the leg above fair).
4. **System K/N pays every winning combination simultaneously** — the panel's
   rows are independent bets; "2 מתוך 4" is the first-payout threshold, not a
   cap. Max-win = sum of all lines.
5. **No structure creates +EV from negative-EV legs.** A line is worth taking
   iff price × probability > 1, leg by leg. Structures only reshape variance.
6. **Calibrate, never hand-tune; ship only what a frozen out-of-sample season
   confirms.** Sophisticated upgrades (opponent adjustment, context features)
   were REJECTED by this gate here — expect nulls and honor them.
7. **fbref post-2026 has only basic counting stats** (Opta licence lost, values
   stripped retroactively); Understat is the free xG/shot-event backbone.
   Understat shot y spans only ~0.24–0.85 — wide-lane models built on shot
   coordinates are unsupported by data (3 lanes max).

## How to work in this repo

- Prediction stack: `services/predictions/` (form_model, probability_service,
  draw_model, prediction_service, strategy_advisor, ledger/history/slip_ledger).
  Zones: `services/zones/`. Data builders: `scripts/build_*.py`.
- Every model change re-runs `scripts/run_recal_chain.py` (calibrate → classifier
  → frozen backtests both seasons → zone blend) and ships only if the numbers
  hold. Record outcomes in `progress.md` (always) per repo `rules.md`.
- Odds/stakes are the USER'S domain: compute fair values, breakevens, EV given
  prices they volunteer — never ingest odds feeds or advise stake sizes.

## Reference resources

- `references/formulas.md` — the internal formula sheet: fair odds/EV, system
  scenario enumeration, trixy distribution, strength-model constants, unified
  probability triplet, Asian-handicap/vig/CLV conversions. Read it before doing
  any betting-math or model-parameter work; quote formulas from it rather than
  re-deriving.
