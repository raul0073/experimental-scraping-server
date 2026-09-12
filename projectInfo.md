# Project Info — Match Outcome Predictor

_Last updated: 2026-08-07. Supersedes README.md (which describes a deleted 2025 layout — treat it as historical)._

## Core Purpose

Revive this project as a weekly predictor tool for the 2026/27 season, producing two ranked pick lists per matchweek:

| Prediction | Count | Leagues | P(outcome) |
|---|---|---|---|
| Most likely **draws** | top 4 | EPL + Serie A (pooled) | P(draw) |
| Most likely **home wins** | top 3 | EPL + Ligue 1 (pooled) | P(home win) |

### Why these leagues

- **Serie A** — highest number of draws last season; structurally draw-prone (tactical, low-tempo matches).
- **Ligue 1** — highest number of home wins last season; strong home advantage to exploit.
- **EPL** — most competitive league; included in both lists because competitiveness creates *value*: draws and home wins that models/markets underprice.

## How It Works

Pipeline, run once per matchweek:

```
fbref (via soccerdata lib)
   │
   ├── fixtures + results  ──────────────┐
   ├── team stats (for + AGAINST)        │
   └── player stats ──► player ratings   │
                              │          │
                     ZONES ENGINE        │
              (15-zone team strength)    │
                              │          │
                    zone matchups ──► xG per side
                              │
                    PROBABILITY LAYER
             (Poisson score grid + home advantage,
              calibrated on real past results)
                              │
                 P(home) / P(draw) / P(away) per fixture
                              │
                        PICK SELECTOR
          (rank, pool leagues, top-4 draws / top-3 home wins,
           confidence tags; later: mental-model tie-breaker)
```

### 1. The Zones Engine (recovered from git history)

The core team-strength model. The pitch is a 3×5 grid of 15 zones (def/mid/att × leftWide/leftHalf/central/rightHalf/rightWide). Each zone gets a 0–100 rating blending three components, weighted by third:

| Component | What it is | def | mid | att |
|---|---|---|---|---|
| team | zone-relevant "pros − cons" stat sums | 0.25 | 0.45 | 0.30 |
| against | what opponents do to you in that zone | 0.50 | 0.25 | 0.25 |
| players | minutes- & position-weighted ratings of players occupying the zone | 0.25 | 0.30 | 0.45 |

Match prediction pits each attacking zone against the opponent's mirrored defensive zone (`attLeftWide` vs `defRightWide`, etc.), weights by zone importance (attCentral 1.4 → wide mid 0.6), and converts rating deltas to xG per side.

**Provenance (important):**
- Full zone→stat mappings for all 15 zones exist **only in commit `12f98ee`** (first commit). Later commits gutted the in-code config (14 of 15 zones empty) when configs moved to per-user Mongo storage — that Mongo data is lost.
- The mature service + prediction code is at commit `fc273d2` (`services/rating/zones_service.py`, `services/predictions/predictions_service.py`, deleted from the tree in `91f7179`).
- Revival recipe: **config from `12f98ee` + code from `fc273d2`**, adapted to current data shapes.

**Known adaptations required:**
1. Old code read Mongo docs with human-readable stat labels (`"Tackles Won"`); current data files use raw fbref column names (`"Tackles_TklW"`). Needs a stat-name mapping layer (~50 names) and a new `_flatten_stats`.
2. Opponent ("against") stats are not scraped today (`opponent_stats=False` everywhere). Must be enabled and data regenerated — the against-component is 25–50% of every zone rating.
2b. ~~Per-match team stats~~ REVISED (see Stage 3): zone inputs come from **season aggregates** (last-season final + current-season to-date, blended by matches played — team structure moves at season scale). The fast-moving *form* signal comes from per-match results (fbref fixtures) + per-match real xG (Understat), both walk-forward-able. Weekly aggregate snapshots are archived date-stamped so future seasons get exact walk-forward states.
3. Old `player.rating` came from deleted rating services; substitute current `ranking.performance` (z-scored, role-weighted — `services/ranking/player_ranking_service.py`).
4. The old xG scaling constants (`×2` multiplier, `delta^1.2 × 0.9`, player boost `×0.1`) were hand-tuned guesses. They must be **calibrated by backtest**, not trusted.

### 2. The Probability Layer (new)

The old system output scorelines ("1.8 - 1.2"). We need outcome probabilities:

- Feed the zone-derived xG pair into a **Poisson score grid** (0–8 goals each side) → sum cells to get P(home)/P(draw)/P(away).
- Add a **home-advantage term** (fitted per league — this is the whole edge in Ligue 1).
- **Calibrate against completed seasons** (2025/26 fully available on fbref, optionally 24/25): fit the scaling constants + home advantage by maximizing prediction accuracy/log-loss on real results. Report backtest hit rate per pick type so we know what the tool is actually worth before the season starts.

### 3. Pick Selector (new)

- Rank fixtures of the upcoming matchweek by target probability; pool the leagues per pick type; take top 4 (draws) / top 3 (home wins).
- Attach per pick: fixture + kickoff datetime, all three probabilities, xG pair, zone matchup breakdown (the "why"), confidence tag (data completeness + margin over league baseline).

### Season Handling & Cold Start

The model must work from matchweek 1 of a new season, when current-season data is nonexistent/noise. Design: **no hard season boundary** — all zone inputs are computed over a rolling, time-decayed window of each team's last ~35–40 matches (recent matches weighted more, ~14-month-old matches near zero). Consequences:

- **Matchweeks 1–6**: predictions run mostly on last-season signal — valid, but tagged lower confidence; the walk-forward backtest measures early-season hit rate separately so we know whether week 1–4 picks are historically worth taking at all.
- **Matchweeks ~5–12**: current season blends in progressively (roughly 65/35 old/new at MW5, dominance by MW10–12).
- **Backtesting is walk-forward**: each past matchweek is predicted using only data available before it — the same code path as live, so backtest results honestly estimate live performance.
- **Promoted teams** (no top-flight window): conservative priors (bottom-quartile zone ratings), or second-division data where fbref coverage allows (Championship yes; Serie B / Ligue 2 to verify). Their fixtures get low confidence, which naturally keeps them out of early-season picks.
- **Summer transfers**: the players component follows the *current squad* — a player's rating comes from his last ~2500 minutes wherever played, mapped to his new team. Eligibility filters (min minutes) are window-based, not season-based, so August doesn't empty every squad.

### The Mental Model's Role — secondary, deferred

The player mental system (`services/mental/`, role-aware trait scoring) stays **out of the v1 predictor**:

- **Double-counting**: zone ratings already embed player quality; mental scores derive from the same fbref stats.
- **Calibration first**: draw probabilities live in a narrow band (~22–32%); extra hand-tuned inputs hurt calibration more than they help.

Planned experiment (post-v1): use mental aggregates as a **tie-breaker/filter** on candidate picks — e.g. composure/discipline differential as a draw tilt (two disciplined teams → fewer errors → draws), or vetoing marginal home-win picks against mentally strong away sides. Keep only if it measurably improves backtest hit rate. The mental dashboard/plotting side of the project remains alive independently.

## Data Storage & Freshness

- **No database.** Mongo is gone for good; all storage is files on disk (per-match rows + derived aggregates as JSON/parquet, calibration constants as JSON). Data volume is tiny (5 leagues × ~380 matches/season). SQLite is the future upgrade path if ever needed — not Mongo.
- **Prediction ledger** (append-only file): every matchweek's picks are written *before* results exist, then graded after. This is how live hit rate is measured honestly — no retroactive picks.
- **Freshness model**: data is as fresh as the last scrape run; fbref itself publishes advanced stats hours-to-a-day after matches. Weekly cadence: scrape after the round completes (e.g. Tuesday), predict before the next round.
- **fbref rate-limits hard** — soccerdata throttles requests, so a full refresh is a minutes-long job. Scrapes must be incremental (only new matches; soccerdata's HTML cache in `data/fbref/cache/` helps) and run scheduled, not ad hoc before kickoff.

## Output Spec

`GET /api/v2/predictions/{matchweek?}` →

```json
{
  "season": "2627",
  "matchweek": 3,
  "generated_at": "...",
  "draw_picks": [
    {
      "rank": 1,
      "league": "ITA-Serie A",
      "fixture": "Torino vs Genoa",
      "kickoff": "2026-08-23T17:30:00Z",
      "probabilities": {"home": 0.30, "draw": 0.34, "away": 0.36},
      "xg": {"Torino": 1.1, "Genoa": 1.2},
      "confidence": "high",
      "why": {"attCentral": "even", "midCentral": "even", "...": "..."}
    }
  ],
  "home_win_picks": [ "... same shape, ranked by P(home)" ]
}
```

Plus a backtest endpoint/report: hit rate of top-4-draw and top-3-home-win picks over the calibration season(s).

## Data Reality (discovered 2026-08-07, Stage 3)

**fbref lost its advanced data** after a data-provider change — verified 2026-08-07 at the *value* level: the advanced pages (defense, possession, passing, GCA, keeper_adv) still exist with full column skeletons, but the values are stripped **retroactively for all seasons, including 24/25** (e.g. squad defense table: 100 of 380 cells filled — only 90s, TklW, Int). Do not be fooled by pages/columns existing; check values. The legacy rich 24/25 data on disk is a one-off historical artifact that fbref itself no longer serves. `TeamStatsService` still fetches the advanced pages and stores any non-null cells, so if fbref ever repopulates, snapshots auto-heal. Consequences:

- **Understat is the xG/advanced backbone**: per-match xG, npxG, PPDA (pressing), deep completions, xPts — all 5 leagues, walk-forward-able, joined 100% to fbref fixtures.
- **The 12f98ee zone stat lists are ~78% dead** (6 of 27 keys survive — see `data/reports/zone_stat_coverage.md`). Stage 4 redesigns zone inputs around surviving fbref basics + Understat signals + player-level basics, keeping the 15-zone structure, position weights, matchup logic, and blend architecture.
- The mental system's trait mappings (built on advanced player stats) will also degrade for new-season data — flagged for the post-v1 mental experiments.

## Current State (as of 2026-08-07)

Works / reusable:
- fbref ingestion plumbing via `soccerdata` (player scrape route `POST /players/{league}/{season}/build`).
- Player ranking (`ranking.performance`) and mental scoring pipelines.
- 5 leagues configured: EPL, La Liga, Serie A, Bundesliga, Ligue 1 (`models/fbref/fbref_types.py`).

Broken / missing:
- App won't boot without `.env` — `core/config.py` requires `MONGODB_URI`, `DB_NAME`, `ADMIN_KEY`, `OPENAI_KEY`, none of which any live code uses → make optional.
- All data on disk is season 2024/25 (two seasons stale); no code regenerates `data/league_init/` (its producer script was never committed).
- No fixtures/schedules/results ingestion anywhere (`soccerdata`'s `read_schedule()` unused).
- No opponent stats on disk.
- Zones + prediction code exists only in git history (see provenance above).
- Misc bugs: `normalize_rank` NameError in `routes/plotting/plot.py`; duplicate route in same file; route-ordering bug shadowing `/mental/vv/*`; `requirements.txt` is UTF-16 encoded; Dockerfile only copies `main.py`; README stale.
- Local env: no Python venv with dependencies installed (fresh clone).

## Future / Out of Scope for v1

- ~~Odds ingestion + value detection~~ — **permanently out of scope** (user decision 2026-08-07): the odds/value side is the user's own domain; the tool supplies picks + honest probabilities only.
- Mental-model tie-breaker experiment (see above).
- Away-win picks, other leagues (La Liga, Bundesliga data already flows through the same pipeline).

## Stages

Ordering rule: data before models, models before picks. Each stage has a gate that must pass before the next begins. Live progress is tracked in `progress.md` (always up to date); working agreements in `rules.md`.

Agreed scope decisions: backtest on **both** 24/25 + 25/26; scrape **all 5 leagues** (same code, keeps La Liga/Bundesliga free for later); **no rush for MW1** of 2026/27 — build right, start picking from ~MW3–4 (early weeks are lowest-confidence anyway).

1. **Boot & hygiene** *(small)* — `.env`-optional config (drop Mongo/OpenAI requirements), fix `normalize_rank` crash, duplicate plot route, `/mental/vv/*` route-ordering bug, re-encode `requirements.txt`, set up venv. **Gate:** server boots clean; `GET /api/v2/leagues` returns 5 leagues; existing dashboard endpoints still work.
2. **Fixtures & results** *(small–medium)* — fixtures service on `soccerdata.read_schedule()`; schedules + final scores, seasons 2425/2526/2627, all 5 leagues. **Gate:** ~380 matches per league-season on disk, spot-checked; 26/27 fixtures visible.
3. **Team stats (aggregates) + real per-match xG** *(medium)* — REDESIGNED 2026-08-07 (originally per-match fbref team stats; dropped — ~3,000 Cloudflare-bypassed pages for the only benefit of exact mid-season backtest states; fbref schedule also no longer publishes per-match xG). Replacement, ~20× cheaper:
   - **Season-aggregate team stats, for + against** (`read_team_season_stats(opponent_stats=True)`), 5 leagues, seasons 2425/2526 (+2627 as it accrues) — feeds the zones; committed script replaces the never-committed `league_init` producer.
   - **Snapshot archive**: every weekly scrape saved date-stamped (`data/team_stats/{league}/{season}/{date}.json`), never overwritten → builds true walk-forward history for future seasons.
   - **Understat per-match real xG** (verified working): `Understat.read_schedule()` → per-match `home_xg`/`away_xg` for all 5 leagues, all seasons — powers the walk-forward xG form model and calibration target, and lets the ledger grade predicted-xG vs real-xG per pick.
   - **Team-name mapping** fbref ↔ Understat (e.g. "Manchester Utd" ↔ "Manchester United") via soccerdata's `teamname_replacements.json`.
   **Gate:** aggregates on disk for all league-seasons with zone-config coverage report; Understat xG joined to ≥99% of played fbref fixtures.
   *Consequence for Stage 5:* zone constants calibrate cross-season (24/25 aggregates → predict 25/26; zero leakage, conservative); the xG-form component calibrates fully walk-forward per matchweek.
4. **Zones revival** *(the big one)* — config from `12f98ee` + service from `fc273d2`; stat-name adapter; rolling time-decay window builder; player ratings from `ranking.performance` with squad-following. **Gate:** 15 zones rated for all teams; sanity report (top attackers top attCentral, promoted-team priors applied, no zone silently zero).
5. **Probabilities, calibration & backtest** *(the important one)* — Poisson grid + per-league home advantage; constants fit walk-forward on 24/25+25/26; backtest report of top-4-draw / top-3-home-win hit rates per matchweek band vs naive baseline. **Gate: go/no-go for the project** — if draw picks hit at baseline rate, iterate here, don't build onward.
6. **Pick selector, API & ledger** *(small)* — `predictions` route (JSON shape above), append-only ledger, single `run_weekly` script (scrape → rate → predict → ledger, grades last week automatically). **Gate:** one command produces the matchweek's picks end-to-end.

Post-v1 backlog: mental tie-breaker experiment, odds ingestion + value detection, away-win picks, **per-GW "Best XI that will thrive"** — for each gameweek, pick the 11 players (across leagues) best positioned to over-perform, combining mental scores with zone-matchup advantages (e.g. a winger whose zone rating towers over the opposing fullback's defensive-wide zone that week; reuses `BestXIBuilder` + zones engine).
