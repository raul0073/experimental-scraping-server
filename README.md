# Predictorous

A football match-probability model for Europe's big five leagues, and the
static site that publishes it: [predictorous.com](https://predictorous.com).

Every fixture gets a home/draw/away probability and a fair price. Every
prediction is written to an append-only ledger before kickoff, graded after,
and never revised. The site's headline is not accuracy but calibration and
proper scoring rules, measured against two baselines and against bookmaker
closing prices. Ideas that were tested and lost are published alongside the
ones that shipped, with the numbers.

Built and run by one person. The code is here so the record can be checked.

## What the model is

```
Understat shots (13 seasons, 5 leagues)      fbref fixtures & results
          │                                            │
   form xG ratings  ──►  scoreline grid  ──►  outcome triplet (ship arm)
   (38-match window, decay 0.985, opponent-adjusted, promoted-club priors)
          │
   zone matchups (9 zones, 4 fitted channels) nudge the expected goals
          │
   process Elo on xG (13 seasons)  ──►  second triplet (Elo arm)
          │
   draw classifier (logistic, 11 features, n = 17,134) sets each arm's P(draw)
          │
   PUBLISHED = average of the two arms          ← the blend, since 2026-11-09
          │
   committed to data/history/predictions.jsonl before kickoff, graded after
          │
   10,000-run season simulation with per-team strength error (SD 0.53 log-odds)
```

Numbers that matter, all out of sample:

| | log loss | notes |
|---|---|---|
| Blend (ships) | 0.984 | 11,311 fixtures, 8 frozen seasons, every fold fitted only on earlier seasons |
| Elo arm alone | 0.990 | same rows |
| Base rate | 1.073 | per-season home/draw/away shares |
| A third each | 1.099 | |

The live 2026/27 record, log loss and Brier against the same baselines, the
per-outcome calibration, and the comparison with closing odds are on the site
and regenerated daily from the ledger. Nothing on the site is typed in by hand.

## Layout

```
services/predictions/   the model: form_model, probability_service, draw_model,
                        prediction_service (the blend), history_service (ledger)
services/zones/         zone engine and the fitted channels
services/market/        bookmaker closing odds as a benchmark (football-data.co.uk)
services/understat, services/fbref, services/whoscored   sources
scripts/run_daily.py    the daily update: sources → grading → derived → payloads
scripts/publish.py      selfcheck → update → check → build → deploy → push
scripts/export_web.py   writes data/web/*.json for the site
scripts/build_market.py the market benchmark payload
scripts/experiment_*.py every experiment behind "What I rejected"
scripts/selfcheck.py    the no-network harness that gates every publish
tests/                  pytest suite (runs the same cases)
data/                   committed: fixtures, Understat, config, ledgers, reports,
                        web payloads. Not committed: WhoScored event streams.
web/                    Next.js static export, reads ../data/web at build time
```

`projectInfo.md` is the original spec; `progress.md` is the dated engineering
log, including every bug and every reversal; `rules.md` are the working rules
(no retroactive picks, calibrate don't hand-tune, files on disk, no DB).

## Running it

```bash
# Python 3.13
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt

# the harness: seconds, no network, works on copies of the ledgers
.venv/Scripts/python.exe scripts/selfcheck.py
.venv/Scripts/python.exe -m pytest -q

# rebuild payloads from what is on disk (no scrape)
.venv/Scripts/python.exe scripts/run_daily.py --no-scrape

# the site
cd web && pnpm install && pnpm build        # static export in web/out
```

The full daily (`scripts/publish.cmd`) scrapes incrementally, grades, rebuilds
every payload, builds the site, deploys to Cloudflare Pages and pushes — in
that order, so the commit means "this is what is live".

## Rules the ledger lives by

1. A prediction is recorded before kickoff or it is marked as reconstructed
   and kept out of every headline figure. The 146 opening-round fixtures
   rebuilt on 2026-09-10 are reported apart on the site, by design.
2. The first prediction stands. The ledger is never rewritten, including when
   the model changes — the date of each change is on the record.
3. No constant is hand-tuned: xG scaling, home advantage, decay, the draw
   level and the simulation's strength error are fitted on frozen seasons and
   the fit is written down.
4. Nothing on the site is betting advice. No market price feeds a
   prediction; closing prices are used only after the fact, as a benchmark.

## Data and licences

Shot and xG data from Understat; fixtures and results from fbref; event
streams from WhoScored for the ratings pages (raw streams never leave the
machine, only derived metrics are published); closing odds from
football-data.co.uk. The 3D player figure is CC-BY and credited beside it
(`web/app/lib/credits.ts`).
