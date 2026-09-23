# Progress

_Always up to date. What's done, what's in flight, what's next. Spec: `projectInfo.md`. Rules: `rules.md`._

**v1 PIPELINE COMPLETE ✅ — all 6 stage gates passed (2026-08-07). First 2026/27 MW1 picks committed to the ledger. Next: frontend dashboard (Option A), weekly-run scheduling, repo re-init under new name.**

## DEPLOYMENT — decided 2026-09-21, to do TOMORROW once the data is aligned

**Cloudflare Pages, direct upload.** Not today — the backfill has to finish
and all five leagues have to be aligned first.

`next.config.ts` already sets `output: "export"`, so `pnpm build` emits a
plain `out/` of HTML, CSS and JS with no Node in production. The question of
"local server injecting HTML vs a regular Next build" does not arise: for
this project they are the same thing.

```
out/  78 MB, 538 files        (largest single file 1.06 MB)
  data   60 MB  ← pass maps dominate
  logos 8.9 MB
after the backfill: roughly 200 MB / ~1,200 files
```

Cloudflare's free tier is comfortably above that (25 MB per file, 20,000
files). Direct upload rather than a git integration, because the payload
directories are gitignored and 200 MB of JSON has no business in the repo:

```
npx wrangler pages deploy out --project-name predictorous
```

**LIVE as of 2026-09-23.** `predictorous.com`, `predictorous.pages.dev` and
the per-deploy alias all serve 200 — HTML, `_next` chunks, `/data/*.json`
and deep routes (`/team/man-city`) alike, with a real 404 on an unknown
path. Only `www.predictorous.com` is dead: no DNS record. Add `www` as a
second custom domain on the Pages project, or CNAME it to the apex.

**Share card done.** `scripts/build_og_image.py` renders
`web/public/og.png` (1200×630, 81 KB) in the site's own fonts, wired into
`layout.tsx` for both Open Graph and Twitter with alt text. It deliberately
carries **no live figures**: social platforms cache the image on their own
schedule, so a baked-in "50.8%" would keep being shown long after the record
moved. The calibration bars are the real bucket shape but unlabelled — the
claim "this model is measured" without a number that expires. Fonts are
fetched once into `data/cache/fonts/` (gitignored), not committed.

Still to do for share previews: per-page metadata for the six pages that
inherit the root title verbatim.

⚠️ **I wrongly called this "a betting tool" when weighing Vercel's
non-commercial Hobby terms.** It is not. The site publishes probabilities
and fair prices and says plainly that it never sees anyone's book. That
mislabelling would have ruled out a perfectly good host for no reason.
Vercel Hobby would in fact be fine; Cloudflare is chosen on its limits.

⚠️ **Still blocks going public: CC-BY attribution for the player model.**
Title, author and source URL into `web/app/lib/credits.ts`. Publishing
without it is a licence breach, not an oversight.

**If size ever bites**, 45 of the 60 MB is pass maps at ~573 KB per
team-season. They are fetched per team on demand, so this is a hosting cost
and not page weight; quantising the coordinates would cut it hard without
changing what the picture shows. Do nothing until it matters.

## 🐛 I CORRUPTED TWO EVENT SEASONS FIXING A DIFFERENT BUG (2026-09-23)

`write_events`' retry path existed for a real Arrow failure — a missing
`player` reads as a float NaN in a column of strings. The fix coerced EVERY
object column to string, which is far more than the broken one:

- `is_goal` / `is_shot`: `True`/`None` -> the STRING `'True'` and `pd.NA`.
  `bool(pd.NA)` RAISES, which killed `stamp_event_state.py:82` and is why
  Serie A and Ligue 1 could not become ready with complete data on disk.
- `qualifiers`: an array of dicts -> a string repr of one. `qualifier_names`
  does structured access inside a bare `except`, so it silently returned an
  empty set — **own goals stopped being detected** and were credited to the
  scoring team. Every future qualifier metric would have read empty too.

Blast radius was exactly the two seasons re-fetched through that path
(ITA 24/25, FRA 25/26). Fixed three ways: `write_events` now coerces only
columns whose non-null values are actually strings; `stamp_event_state`
normalises flags on read (parsing text, not `astype(bool)`, which maps
`'False'` to True); and `scripts/repair_event_parquet.py` detects the damage
by VALUE TYPE, not dtype — the first version tested `dtype != bool` and
condemned all twenty files, since `object` holding True/None is the native
and correct shape.

⚠️ **The in-place repair was not good enough and the files were rebuilt from
the soccerdata JSON cache instead.** `literal_eval` silently dropped cells:
clean seasons carry qualifiers on 100% of events, the repaired ones came back
at 76% (ITA) and 37% (FRA). The repair script overwrote without keeping a
backup, so the evidence was gone — **that is the lesson worth keeping: a
repair that destroys its input cannot be audited.** The cache held all 380
and 306 matches, so the rebuild cost nothing but CPU.

## DAILY: THE INTERNATIONAL-BREAK GATE (2026-09-23)

A blank daily used to run in full — five schedule fetches at ~10 month pages
each, a fetch loop that asked for nothing, and a complete rebuild of ratings,
Elo and every payload, to reproduce yesterday's numbers exactly.

`idle_check()` is **derived from the fixture calendar, never a list of break
dates**: a hardcoded calendar covers one case, goes stale every season and
needs a human to remember it. The fixture list already knows, for every
league, and it is on disk. It therefore also covers midweek gaps, winter
breaks and the close season for free.

Idle does NOT mean do nothing. Injuries move on international duty and
kickoff times get shifted, so fixtures, injuries, grading, predictions and
export still run; events, stamping, ratings, Elo, mental, shots and passes —
everything that can only change when a match is played — are skipped.

Two safeguards, both of which are the whole point:
- **The marker is written only on a clean run.** An idle gate that inherits
  a failed run turns one bad morning into a permanent silent outage.
- **The marker records the READY LEAGUE SET.** The backfill stamp runs before
  the gate by design, so a league whose events finally land becomes ready
  without anyone noticing — but that is not "football happened", so the naive
  gate skipped every build that would have put it on the site. Serie A and
  Ligue 1 would have sat at ready-but-invisible through the whole break. A
  change in the ready set is work.

Verified: last match 2026-09-20, next 2026-10-09 (16 days).

## WALK-FORWARD VERDICT — the layer is out (2026-09-23)

11,311 fixtures · 8 eval seasons · 4 leagues (Ligue 1 excluded, data short).
Per eval season S: boosts/rho refit on S−1, classifier trained only on
seasons before S, Elo fitted only on seasons before S. Report:
`data/reports/experiment_walk_forward.json`, rows in `_walk_forward_rows.csv`.

⚠️ **THE FIRST RUN'S ANSWER WAS WRONG AND WAS REVERSED HERE.** That run said
blend beat ship by +0.0012 at P=0.96. It was produced while
`DrawModel.train(out_path=None)` was silently overwriting the PRODUCTION
classifier on every fold — `path = out_path or PARAMS_PATH`. Fixed to a
scratch path; the rerun prints the production classifier's season count
before and after as a guard (11 seasons / n=17,134, unchanged).

**Triplet log loss, pooled:**

```
arm       log-loss  accuracy  gain vs ship  P(better)
ship        0.9842     52.4%             —          —
blend       0.9843     52.7%      -0.00016      0.418
layer       0.9850     52.7%      -0.00077      0.183   <- was shipped
elo_clf     0.9901     52.3%      -0.00588      0.000
```

**Draw RANKING — the metric that actually matters**, since the use is four
picks a gameweek and only the order matters. `analyse_draw_ranking.py`
scores precision at the top k% of each league-season (four from a
five-league weekend ≈ top 9%), CIs bootstrapped over league-seasons:

```
arm      top 5%   top 10%   top 20%   P(>ship @10%)
ship      33.5%     30.9%     30.3%              —
blend     33.0%     31.6%     30.1%           0.718
layer     31.9%     30.1%     29.7%           0.248
elo_clf   31.9%     30.1%     29.7%           0.248
```

Base draw rate 25.4%, so every arm ranks draws well above chance — the old
"worse than chance" scare was a single-league small-sample fluke, now dead.

**Why the layer fails, precisely.** `layer = unified_probs(blend,
elo_clf["draw"])` — it keeps blend's home:away ratio and substitutes the
classifier's P(draw). So the layer's draw ORDERING *is* the classifier's,
which is why their draw rows are identical to four decimals. The layer was
added on the belief the classifier ranks draws better than the shipped
model. It does not — it ranks them worse. The layer imports a downgrade.

**Decision: drop the layer.** It loses to ship on the triplet (P=0.183) and
on draw ranking (P=0.248), and it is strictly dominated by blend on both.
Ship vs blend is a genuine coin flip — no difference here is significant —
so the tiebreak is the use case: blend is the best of the four at the
trixy-like cutoff. **Switch the predictor to plain blend.**

Per league at top 10%, blend wins or ties ENG/GER/ITA; ship wins ESP
(36.1% vs 33.8%). Per-league arm selection is tempting and NOT justified —
that is choosing on the test set with four leagues.

TODO: the rows carry no date, so a true gameweek could not be simulated.
Add `date` to the walk-forward rows and re-score "top four this weekend"
directly rather than via a percentage proxy.

## 🐛 PARKED — the Elo conv_lookback will not stay put

`calibrate_elo_conv.py` chose per-league lookbacks (ENG 3, ITA 1, ESP 1,
GER 4, FRA 1). They keep reverting to the default of 3 for ESP, GER and FRA
— ITA alone holds. Tried twice; the code path reads correct
(`build_elo_all.py:150` reads it, `:196` writes it, one write path only),
and an isolated single-league run DOES round-trip correctly. A multi-league
run does not.

**Fixed along the way, and it is the likely cause of the drift:**
`build_elo_all` wrote `elo_params.json` WHOLE, so a run with `--league X`
replaced the file with only that league and deleted the other four — the
predictor silently lost its Elo arm for them, and the next full run refitted
from defaults. Same failure as the ratings index. Now merges into what is
already on disk (`all_params = dict(prior)`).

**The fix to make, rather than more archaeology:** move the lookback into
its own config file that `build_elo_all` only ever READS. A value that is
never written back cannot be lost in a round trip.

## NEXT SESSION — everything left open as of 2026-09-20 evening

## THE ORDER OF OPERATIONS (user, 2026-09-21 — I got this wrong)

**We are still in the ENGLAND-ONLY phase.** The sequence is:

1. **Now** — daily runs on ENG-Premier League only. Still testing.
2. **Next** — `predictorous-backfill` populates 2324→2627 events for ESP,
   ITA, GER, FRA.
3. **Only once that is complete** — widen the daily to all five leagues.

🐛 **What I did wrong.** I registered the daily with no `--league`, so it
ran across all five. That made it start *initialising* 26/27 events for
leagues that have not been backfilled — aligning data we do not have yet,
in the wrong order — and its derived steps would then have published the
hollow all-50s ratings tables for those leagues. I also created
`data/web/team/esp-la-liga/` by running `build_team_web` for La Liga as a
test, which is what put La Liga on the ratings page in the first place.

**Corrected:**
- The 09:00 run was stopped mid-flight (before `export_web`, so nothing
  hollow was published — the site still serves the 09-20 payload).
- `predictorous-daily` now runs
  `run_daily.py --league "ENG-Premier League"`.
- `data/web/team/index.json` and its public mirror restored to England
  only; `esp-la-liga/` removed from both. `merge_index` preserves whatever
  is listed, so England-only runs keep it that way.
- The empty `fra-ligue-1/`, `ger-bundesliga/`, `ita-serie-a/` folders are
  left alone — they are not in the index, so they are inert, and the
  backfill will fill them properly when its turn comes.

⚠️ **When widening after the backfill**, the daily's league list is the
only change needed — drop `--league` from the scheduled task. Everything
downstream already loops over `LEAGUES`.

## 2026-09-21 09:05 — BACKFILL BACK ON, NIGHTLY (user decision)

**Why it came back.** The ratings table is built from the EVENT stream —
`build_team_web` reads `{season}_stamped.parquet` — and its reliability gate
is a split-half correlation ACROSS team-seasons. Measured:

```
            seasons   n    metrics passing the gate
EPL             4     60   20 of 23   (+ every metric has a `predicts` value)
La Liga         1     20    4 of 23   (+ NO `predicts` values at all)
```

That is why La Liga rendered every cell as 50 — with "ignore metrics that
don't hold up" ticked, 19 of 23 were discarded, and `predicts_points` had
returned `{}` because it needs 20+ matches per team-season and 26/27 has ~7.
So the empty-dict fix stops the crash but builds a HOLLOW table; the numbers
need the history. Nothing else does: predictor, projected tables and track
record all run off Understat, complete for five leagues and thirteen
seasons.

**Scheduled**: `predictorous-backfill`, **daily 01:00, capped at 7h30m** →
`scripts/run_event_leagues.cmd`. ESP/ITA/GER/FRA × 2627, 2526, 2425, 2324 —
~4,116 matches, ~12h30m, so about two nights. It runs 01:00-08:30, stops
clear of the 09:00 daily, and resumes the next night; already-fetched
matches are skipped so a finished run is a fast no-op.
**Delete the task once the log shows nothing left to fetch.**

- **`StartWhenAvailable` is OFF, deliberately.** That setting is what made
  the 20 Sep job fire at 08:30 the next morning after the machine missed
  01:00. A missed night is now skipped, not moved into the working day.
- **Newest season first, all four leagues, then the next.** An interruption
  leaves every league at the same depth. Two seasons across four leagues is
  a usable rating; four seasons of one league and nothing else is not.
- **Quoting verified by dry run** before scheduling, because this is exactly
  what was lost last night: `['--league', 'ESP-La Liga', '--seasons',
  '2627']` — one argument, quotes intact.

🐛 **`build_team_web` was destroying the ratings index.** It wrote
`index.json` containing ONLY the league it had just built, and the board
reads `leagues[0]` — so building La Liga made the ratings page show La Liga
INSTEAD OF the Premier League. Worse, the daily's per-league loop left the
index set to whichever league ran last (Ligue 1). Invisible while only one
league was ever built; destructive the moment there were five. Now merges
and sorts by `LEAGUE_ORDER` with England first.

## 2026-09-21 09:00 — THE DAILY NOW ACTUALLY UPDATES EVERYTHING

**User: "DAILY MUST UPDATE: rankings, predictor, projected table, track
record. ALL MUST CONSUME THE UPDATE."** Three things were stopping that,
and none of them announced itself.

### 🐛 1. The stamping step did not exist

Nothing reads `{season}.parquet`. `role_bank.seasons_on_disk` globs
`*_stamped.parquet`, so team web, zones, territory, passes, shots and the
mental role bank ALL read the stamped copy. `run_daily` fetched events every
morning into a file **no consumer opens**, and mentioned `_stamped` only in
a comment. Measured staleness when found:

```
ENG-Premier League 2627   raw 09-17 12:13   stamped 09-18 09:38
ESP-La Liga        2627   raw 09-20 19:36   stamped NONE
GER-Bundesliga     2425   raw 09-21 08:38   stamped NONE
```

Added `stamp_event_state.py` per league as step 1b, after the fetch and
before anything derived. Runs even under `--no-scrape`.

### 🐛 2. Predictions were priced from yesterday's ratings

`run_daily` called `run_weekly.py` FIRST — and run_weekly grades, predicts
AND simulates. So the published triplet, which since 2026-09-20 blends the
Elo arm, was built every morning from an Elo table that had not yet seen
last night's results. A full day of lag inside the job whose purpose is not
being a day behind.

`run_weekly.py` gained `--sources-only`, splitting it at the point where it
stops reading the world and starts depending on ratings. The daily order is
now:

```
1   sources          run_weekly.py --sources-only
1b  events + STAMP   per league, current season, played fixtures only
2   ratings          team web, plots, form, injuries, elo, reliability, mental
3   grade+predict+sim run_weekly.py --no-refresh   <- consumes step 2
4   payloads         shots, passes, kits, export_web
```

Track record is graded in 3, the predictor is priced in 3 from step 2's
ratings, the projected table is simulated in 3 from those prices, and
step 4 exports all of it. Every consumer now sees the same day's data.

### 🐛 3. Team web crashed for any league without event history

`predicts_points` keeps only team-seasons with 20+ matches, then concats a
groupby. A league whose only events are the season in progress has ~7
matches a side, so the frame emptied and `pd.concat` raised "No objects to
concatenate" — taking down the whole rankings build for four of five
leagues. It is a DIAGNOSTIC ("do these metrics predict points"); not being
answerable in September is normal and must not stop the rankings
publishing. Returns `{}` when empty. La Liga now builds 20 clubs from the
current season alone — **the rankings need no backfill.**

### The UPDATE ALL TO TODAY button

`routes/admin/admin.py` — `POST /api/v2/admin/update` starts `run_daily.py`
detached, `GET /api/v2/admin/status` reports whether it is running, how the
last one exited, when the payload the SITE is serving was generated, and a
log tail. `web/app/predictor/Freshness.tsx` puts it on `/`.

- **Localhost only.** The endpoint starts a subprocess and the API binds
  0.0.0.0 with CORS `*`; the guard is on the socket peer, which a header
  cannot forge. The button itself is additionally `NODE_ENV === development`
  so it never ships — verified absent from the production build.
- **One at a time.** A second request while one runs is refused, not
  queued: run_daily rewrites the payloads the site reads, and two
  interleaved runs would mix a round.json from one with a record.json from
  another.
- **Two clocks, deliberately.** `Data from <date>` comes from the payload
  compiled into the page; the API reports what is on disk. If the pipeline
  ran but the site was never rebuilt they disagree, and that otherwise
  invisible state gets its own warning.
- The freshness line ships in **all** environments and turns red at 2+ days
  old. The button does not.

⚠️ Note: the API server must be restarted to pick up new routes (done —
PID 22376). `data/reports/daily_manual.log` holds manual-run output.

### Correction to yesterday's note

The 19:32 rebuild **did** complete — it wrote `2026-09-20 19:32 24/35 ok`
after I checked the log, so "the rebuild died, the site has the old model"
was wrong. The site does have the layer. Eleven steps failed, all of them
the team-web / injuries / passes steps that bugs 1 and 3 above explain.

## 2026-09-21 08:45 — BACKFILL ABANDONED, DAILY ONLY (user decision)

**"Stop the big load scrape. Only do the daily."** The multi-season event
backfill is off. `predictorous-event-scrape` is unregistered, nothing is
running, and the only scheduled job is now `predictorous-daily` at 09:00.

**What the overnight run actually did: almost nothing, because of a quoting
bug.**

```
build_whoscored_events.py: error: unrecognized arguments: Liga
build_whoscored_events.py: error: unrecognized arguments: A
```

🐛 `run_event_leagues.cmd` passed `--league %%~L`, and the tilde STRIPS THE
QUOTES — so `"ESP-La Liga"` reached argparse as `--league ESP-La` plus a
stray `Liga`. Every league name containing a space died in under a second:
La Liga, Serie A, Ligue 1. `GER-Bundesliga` has no space, so it was the only
one that ran, and the log looked busy while three quarters of the job
evaporated. Pre-existing in that file, never caught because the file had
never actually been executed. Fixed (`%%L` for the argument, `%%~L` only in
echo lines) in both .cmd files, though neither is scheduled now.

🐛 **And it fired at 08:30, not 01:00.** `StartWhenAvailable` means a task
that missed its window runs at the first opportunity — the machine was not
awake at 01:00, so it started during the working day. `WakeToRun` did not
help. If a night-only job is ever wanted again, leave `StartWhenAvailable`
OFF so a missed window means skipped, not "surprise scrape at breakfast".

**Two fixes that make "daily" genuinely daily:**

🐛 `run_daily.py` called `build_whoscored_events.py --league X` with no
`--seasons`, and that script's default was `["2425", "2526"]` — so for any
league without history on disk **the daily update silently began a
2,744-match backfill.** The default is now the current season and run_daily
passes `--seasons 2627` explicitly.

🐛 `build()` fetched every game_id `read_schedule()` returned, including
fixtures not yet played. New `played_ids()` filters on kickoff + 3h.
Measured: EPL 380 fixtures → 50 played, Bundesliga 306 → 36. A daily run now
asks for ~230 across five leagues instead of 1,752, and skips what is
already stored.

**Scheduled now — the only job:**
`predictorous-daily`, daily 09:00 → `scripts/run_daily.py`, 3h limit.
Today's first run does a one-off catch-up of the ~194 missing 26/27 matches
(~35 min of fetching) plus the derived rebuild; after that it is a handful
of new matches a day.

⚠️ Consequence of abandoning the backfill: **the other four leagues have no
event history**, so their match pages still have no shot maps, pass maps or
zones — 24 of 30 fixtures a round. Only 26/27 will fill in, day by day, as
matches are played. If that gap needs closing, the backfill has to be run
deliberately (`run_event_leagues.cmd`, now fixed) — it is not coming back on
its own.

**IN THE MORNING, IN THIS ORDER**

1. - [ ] **Watch the first `predictorous-daily` run (09:00 today).** It does
       a one-off catch-up of the ~194 missing 26/27 matches across the four
       leagues, then the derived rebuild and export — roughly an hour. Check
       `data/reports/daily.log` and `data/reports/event_pilot.log`. Every
       run after this is a handful of matches.

2. - [ ] **Decide whether the event backfill ever happens.** Without it the
       other four leagues have no 24/25 or 25/26 events, so their match
       pages have no shot maps, pass maps or zones — 24 of 30 fixtures a
       round. 26/27 fills in day by day from now on, so the gap shrinks on
       its own over the season. `run_event_leagues.cmd` is fixed and ready
       if it is ever wanted deliberately; nothing schedules it.

⚠️ **THE SITE IS STILL SERVING THE OLD MODEL.** The 19:32 rebuild died when
the session's background task was torn down — `daily.log` still reads
`18:05 11/11 ok`. The layer, the recalibrated conv and DRAW_CALL_MIN 0.31
are all on disk and verified, but nothing published has been regenerated.
Step 4 is what makes the switch visible.

**Model — the questions today's work opened rather than closed**
- [ ] **Layer vs blend is unresolved and may not be resolvable on one
      season.** They differ by 0.0001 nats and two picks in 200. Either
      accept the tie and stop testing variants, or settle it on more
      seasons (below).
- [ ] **Option B — walk-forward retrain across 18/19…25/26, ~14,000
      fixtures.** `backtest_season.py` already has the protocol: refit
      boosts/rho on S−1, train the classifier only on seasons before S.
      Tests the METHOD rather than the frozen artifact, which is the right
      claim for `/rejected` and `/how-it-works`. Needs no scraping.
- [ ] ⚠️ **The record page mixes eras.** The 230 graded rows behind the
      calibration panel were produced by the OLD model; everything from
      here is the layer. Either mark the switch date on the panel or regrade
      history through the new model. **Do before launch** — an honesty page
      that is quietly dishonest is worse than no page.
- [ ] Re-check `DRAW_CALL_MIN` once 26/27 has enough graded rows. 0.31 was
      chosen on 25/26; the supply argument (4.9 calls a week) is the part
      that matters and should be re-verified against real rounds.

**Site — before launch**
- [ ] **Responsive.** See the detailed suspect list in `## Next up`.
- [ ] ⚠️ **CC-BY attribution for the player model.** Still missing; still
      blocks publishing.
- [ ] **`/viz` is orphaned** — the tile grid was its only entry point.
      Decide: nav slot, folded into another page, or retired.
- [ ] **Deployment.** `out/` is 70 MB today, ~200 MB after tonight (45 MB of
      it pass maps at 573 KB each). Decide where it goes, how it gets there
      after the 09:00 run, and whether the pass export gets trimmed.
- [ ] Zones refactor — user has an idea now the pitch looks right.
- [ ] Player model appearance — parked deliberately.

**Debt found today, not urgent**
- [ ] `build_process_elo.py`'s `CACHE` and `REPORT` are single shared paths,
      not per-league — `--cached` after a different league silently fits on
      the wrong matches. Not hit today because nothing passes `--cached`.
- [ ] `slugify` is copy-pasted into three client components. `web/lib/
      league.ts` now exists precisely so it does not have to be; consolidate.
- [ ] 8 pre-existing lint errors, all `setState` inside an effect
      (`Tabs`, `MentalBoard` ×2, `MentalData`, `MentalTabs`, `TeamPage`,
      `TeamBoard`, `VersusPage`). `web/lib/useStored.ts` shows the
      `useSyncExternalStore` pattern that fixes this class.
- [ ] **The 09:00 daily scheduled task is still not registered.** Tonight's
      task is a ONE-OFF for the scrape only. Nothing updates the site daily
      yet.
- [ ] 81 untracked git paths — none of the last several sessions' work is
      committed.

## SHIPPED 2026-09-20: the layer, recalibrated conv, DRAW_CALL_MIN 0.31

Three changes, in dependency order — conv feeds the Elo arm, the Elo arm
feeds the published triplet, and the threshold sits on top of whatever the
model finally outputs.

### 1. conv recalibrated — the level was fitted on a bygone era

`conv` (goals per unit of expected chances) was solved over every training
season and over-projected the holdout in all five leagues: x1.03 in the
Bundesliga to x1.15 in Serie A, the Premier League's 3.01 against an actual
2.75. Cause is drift, not a bug — Serie A really did return 2.43 a match in
25/26 — so a twelve-season average describes a scoring era that has passed.

`scripts/calibrate_elo_conv.py` picks the lookback by walk-forward INSIDE
the training seasons, never against the holdout. The error curve came out
**monotone — "all" is the worst setting in every league** — which is the
signature of drift dominating noise, and is why a one-to-four season
lookback is not overfitting. Chosen per league: EPL 3, Bundesliga 4, the
other three 1. Projection error falls to x0.99–x1.07; log-loss moves by at
most 0.002 either way, confirming the old docstring's claim that log-loss is
nearly blind to level (which is exactly why the level had to be fixed
separately — the grid could never have found it).

`build_elo_all.fit` now takes the lookback and carries each league's value
forward through `elo_params.json`, **because run_daily calls it every
morning and would otherwise silently revert this.**

### 2. The published triplet is now a LAYER

Two questions, different winners, on 1,714 fixtures:

| | winner | |
|---|---|---|
| what PRICES a match | blend of ship + elo_clf | log-loss 0.9924 vs ship 0.9937 |
| what RANKS a draw | elo_clf | top-200 picks 32.5% vs ship 29.5%, p=0.0175 |

So `unified_probs` takes the blended triplet for the home:away ratio and
hands P(draw) to the Elo arm — one extra call, not a new model, because
that function is already how the shipped model is assembled.

| arm | triplet LL | top-200 draws |
|---|---:|---:|
| **layer** | **0.9925** | **32.5%** |
| blend | 0.9924 | 31.5% |
| ship | 0.9937 | 29.5% |
| elo_clf | 0.9975 | 32.5% |
| mix_se | 0.9957 | 27.5% |
| mix_es | 0.9982 | 29.5% |
| elo | 1.0002 | 27.5% |

**Layer and blend are indistinguishable from each other** (0.0001 nats, two
picks in 200); layer is taken because it is best-or-tied on both axes.
Blend over ship is +0.0013 nats at P(better)=0.74 — directional, not proven.
The solid result is that both beat ship at ranking draws, and the product
ranks draws.

🐛 **The first run of this comparison was against the wrong ship.** It left
out the zone-channel boost that production applies to the lambdas before the
grid and the classifier ever see them — a component worth ~0.0024 nats,
larger than the +0.0018 margin being measured. Zones also cannot just be
loaded, since the live engine builds them from `["2526","2627"]` and scoring
25/26 with them is scoring a season with knowledge of itself; they are
rebuilt per date, walk-forward. With zones in, blend's edge fell from
P=0.859 to P=0.740 and the best draw ranker changed from blend to elo_clf —
i.e. the omission would have produced a different decision.

**The naive layerings failed and are kept as arms so they stay disproved:**
ship's ratio with the Elo's raw draw (0.9957) and the Elo's ratio with
ship's draw (0.9982) both land between their parents and beat neither. There
is also a structural reason swapping a draw cannot help the picks — a ticket
ranks by P(draw) alone, so `mix_es` has ship's pick ranking exactly.

### 3. DRAW_CALL_MIN 0.32 → 0.31

🐛 **There was never a cliff.** The old 0.32 was swept on 194 live rows with
a note that 0.30 "would cost 6pp". Across 1,714 rows accuracy moves smoothly
— 52.2% at 0.33 down to 50.9% at 0.30. The 6pp step was the sample being too
small to answer, not a boundary.

**Supply decided it, not hit rate.** Over ~38 rounds:

```
0.32    96 draw calls = 2.5 a week   hit 34.4%  (+8.8 over base)
0.31   187 draw calls = 4.9 a week   hit 32.6%  (+7.0 over base)
```

The product commits to FOUR draw picks a week. At 0.32 the model makes two
and a half calls a week, so **the ticket cannot be filled from its own
stated calls** — a better hit rate that cannot supply the product is worse
than one that can. 0.31 costs 0.2pp of accuracy (52.0% vs a grid best of
52.2%) and still beats the 25.6% base at p=0.019.
`scripts/sweep_draw_call.py`, re-runnable from the cached rows without a
ten-minute zone rebuild.

### Verified live

All five leagues price with the Elo arm active. Mean published P(draw) on
upcoming 26/27 fixtures is 0.268 against 0.259 on the holdout — no
inflation. Fixtures carry `probabilities_ship` and `probabilities_elo`
alongside the official triplet so any call can be audited afterwards.

⚠️ **The record page now mixes eras.** The 230 graded rows behind the
calibration panel were produced by the OLD model; everything from here is
the layer. The panel does not say so, and it should before launch — either
by marking the switch date or by regrading history through the new model.

## WHICH MODEL SHIPS: the blend. Settled 2026-09-20, on 1,714 fixtures.

**The question was never waiting on Monday.** The Elo that ships is fitted
from UNDERSTAT xG (`build_elo_all.py` → `matches_from_understat`), and
Understat carries thirteen seasons of all five leagues — 21,819 played
fixtures already on disk. Only `build_process_elo.py`'s *research* loader
reads the event stream, which is why widening had been mistaken for a
scraping problem. It was two hardcoded constants:
`LEAGUE = "ENG-Premier League"` and `TEST = "2526"`.

**Why the test season stays 25/26.** The shipped draw classifier on disk was
trained on 1415…2425 — eleven seasons. Scoring it on any of those is marking
its own homework. 25/26 is the one complete season the frozen artifact has
never seen, so widening happens across LEAGUES: ×5 the sample, leakage
boundary untouched. New script: `scripts/experiment_draw_arms_all.py`.

**The verdict — blend wins both jobs.** (1,714 fixtures, draw rate 25.6%.)

| arm | triplet LL | acc | top-40×5 draws | p |
|---|---:|---:|---:|---:|
| **blend** | **0.9934** | **52.4%** | **34.0%** | **0.0048** |
| elo_clf | 0.9964 | 52.0% | 31.5% | 0.034 |
| elo | 0.9992 | 52.1% | 31.5% | 0.034 |
| ship | 0.9952 | 51.6% | 28.0% | 0.235 |
| mix_se | 0.9968 | 51.7% | 31.5% | 0.034 |
| mix_es | 0.9976 | 52.1% | 28.0% | 0.235 |

Base log-loss 1.0729, base draw rate 25.6%. Blend's draw edge survives
Bonferroni over six arms (0.0288). On the published triplet the gain over
ship is real but small — +0.0018 nats, P(better) 0.859 — so the honest
reading is "blend is better at picking draws and no worse at pricing
matches", which is enough to switch given the product ranks draws.

**Blend is also the CONSISTENT one, which decided it.** Heterogeneity across
the five leagues: blend Q=7.26, p=0.123 (leagues indistinguishable); ship
Q=9.77, p=0.044 (significantly inconsistent — 16/40 in La Liga, 6/40 in the
Premier League). A picker that is good on average by being excellent in two
leagues and poor in two others is not the same asset as one that is good
everywhere.

🐛 **RETRACTION — the "shipped ranks draws worse than chance" finding was a
small-sample fluke.** On EPL alone it was 15.0% against a 27.7% base,
p=0.047, and it was written up as significantly bad. Across five leagues
shipped lands at 28.0% against 25.6% — slightly POSITIVE. The EPL 15% is
visible in the per-league table as one bad cell (6/40), not a property of the
model. Anything citing that number needs correcting.

⚠️ **Do not restrict the weekly picks to one league.** Blend by league:
EPL 20.0%, Bundesliga 27.5%, La Liga 40.0%, Serie A 45.0%, Ligue 1 37.5%. The
34% pooled figure depends on picking from wherever the best four are; an
EPL-only ticket would have run BELOW base rate for this season.

**The layering idea was measured, and it does not work.** `mix_se` (ship's
home:away ratio + Elo's draw) and `mix_es` (Elo's ratio + ship's draw) both
land between their parents and beat neither. There is also a structural
reason it cannot help the picks: a ticket ranks by P(draw) alone, so
substituting the draw component *is* substituting the entire ranking —
`mix_es` has ship's draw ranking exactly, `mix_se` has the Elo's. Layering
changes what is PUBLISHED, not what is PICKED. What actually helps is
averaging the whole triplet, which is what the blend already does.

**Still open:** `DRAW_CALL_MIN = 0.32` was fitted on 194 rows and needs
re-sweeping on these 1,714; and the Elo arm's `conv` (3.03 projected goals
against ~2.75 actual) is still uncalibrated.

🐛 **Fixed in passing:** `run_daily.py` called `build_process_elo.py --league`
for every league. That script's default loader reads the WhoScored stamped
parquet, which exists for EPL only — so the first five-league daily run would
have failed four of those steps with `KeyError: 'kick'` on an empty frame. It
now calls `build_elo_all.py` once, outside the loop. (Its `CACHE` and
`REPORT` paths are still shared rather than per-league — `--cached` after a
different league silently fits on the wrong matches. Not hit today; worth
fixing before anyone uses that flag.)

## The site is a predictor (decided 2026-09-20)

**The call.** Rating site or predictor site — predictor, because *a rating
cannot be wrong*. Nothing ever tells you "Arsenal 4th best" was false, which
is why there are a thousand power rankings and none of them have to be good.
A prediction is graded every weekend by someone other than us, and every
asset worth showing exists only because of that grading: 230 graded rows, the
calibration buckets, the picks ledger, `/rejected`. A rating site cannot have
a rejected-experiments page, because there is nothing to have been wrong about.

**Ratings are not the losing product — they are the inputs.** Process Elo
feeds Dixon-Coles feeds the number on the fixture; the chain was already
built, the nav just presented an input as a co-equal offer. The fixture is
the unit: it carries the claim, the working (XI, shots, passes, zones), and
the grade.

**Shipped for it:**

- **`/` is the predictor.** `web/app/predictor/PredictorPage.tsx`, rendered
  from both `/` and — via a client redirect, not a second copy — `/predictor`,
  so old bookmarks still land. The three-tile landing page is gone; it
  described the codebase, not the product. `SubNav` moved out of the predictor
  layout into the page, because `/` does not sit under that layout and would
  otherwise lose the way through to the projected tables and the record.
- **Calibration is a collapsible at the top**
  (`web/app/predictor/Calibration.tsx`). The old version printed *half* a
  comparison: "said 36.8% · n=70" small and grey, "41.4%" big and bold — so
  the eye lands on the number that means nothing alone, and the claim had to
  be reconstructed by subtracting two differently-sized numbers. Now each
  bucket is two bars on a shared 0–100 track; close bars = honest
  probability, no arithmetic. Also fixes the five-into-four wrap that left
  the last bucket orphaned. The n=6 bucket landing at 100% is dimmed and
  labelled "too thin to read" rather than dropped — hiding it would be
  picking which of our own numbers to show.
- **Leagues are pills, not a scroll** (`web/app/predictor/RoundTables.tsx`).
  Five stacked tables meant the Ligue 1 reader scrolled past four leagues
  every week. Choice persists per browser; a stored league missing from the
  payload falls back rather than blanking the page.

**Two things this turned up.** `lib/data.ts` opens `node:fs` at import time,
so any client component importing a *value* from it kills the build with
"the chunking context does not support external modules" — which is why
`slugify` is copy-pasted into three components already. Pure helpers now live
in `web/lib/league.ts` and `data.ts` re-exports them. And `web/lib/useStored.ts`
replaces the read-localStorage-in-an-effect pattern with `useSyncExternalStore`,
which is the actual API for this: no cascading render, no hydration mismatch.
Lint errors stayed at 8, all pre-existing.

⚠️ `/viz` is now unlinked — the tile grid was its only entry point. Route
still resolves; decide whether it earns a nav slot or retires.

## Event scrape for the other four leagues (scheduled 2026-09-20)

**Measured, not estimated: 10.9s a match.** 750 matches ran 09:35–11:51 on
17 Sep; 23/24's 380 ran 01:00–02:08 the night after. The docstring saying
"~29s a match" was stale by 3× and would have budgeted 35 hours for this —
corrected in `build_whoscored_events.py`.

**The gap is only WhoScored events.** Understat has 13 seasons × 5 leagues and
fixtures has 3 seasons × 5 leagues; both already aligned. Events exist for
EPL alone.

| | matches | at 10.9s |
|---|---:|---:|
| one full season, four leagues (380+380+306+306) | 1,372 | 4h09 |
| 26/27 played so far (ESP 64, ITA 45, GER 33, FRA 42) | 184 | 0h33 |
| **24/25 + 25/26 + 26/27** | **2,928** | **8h52** |
| all four seasons (adds 23/24) | 4,300 | 13h01 |

Disk ≈ 92 KB/match across raw + stamped, so ~270 MB for the three-season run.
Gitignored.

**Why it matters, given the decision above:** the predictor publishes 30
fixtures a round across five leagues and only the six English ones have a
match page with anything on it. The events fill the other 24. They are *not*
needed for the model — nothing in the predictor path reads these parquets
(`grep` for whoscored hits passes, shots, zones, territory, leverage,
role_bank only), so Monday's draw-ranking re-test is unblocked today.

**Scheduled**: Windows task `predictorous-event-scrape`, one-off,
2026-09-21 01:00, `WakeToRun`, 16h limit → `scripts/run_event_leagues.cmd`.
Cancel with `Unregister-ScheduledTask -TaskName predictorous-event-scrape`.

**26/27 goes first, all four leagues, before any history** — 184 matches is
half an hour and it is the half hour that matters. League-by-league would
mean an interruption at hour four left La Liga done and three untouched.

**Verified end to end before leaving it unattended**: a live run fetched 20
La Liga 26/27 matches (30,766 events), so `read_events` works for a non-EPL
league. Resumable, so those 20 are skipped tonight.

## THREAD 2 of 4 — Team ranking (in flight, 2026-09-18)

**User's framing, and a correction to mine:** the team layer is NOT a
temperament measure. It is a CAPABILITY PROFILE, because the predictor will
read from it — "how good are they, broken down into what good means". Style
and quality are reported together but only quality is ranked.

- [x] **Manager spells** (`services/mental/spells.py`). Taken literally the
      data gives 159 spells with a MEDIAN OF TWO MATCHES, because WhoScored
      lists caretakers on some fixtures and flips back (Burnley: Parker /
      Jackson / Parker / Jackson at one match each). Stitched in two passes —
      absorb blips bracketed by the same name, then relabel surviving short
      runs — operating on the NAME SEQUENCE, not by merging spell objects,
      which had left one manager holding two spells at a club. Result: **47
      spells, 40 managers, all 2,280 team-matches assigned, none under 10,
      median 38**. Takeover dates verified against reality (Glasner Feb 2024,
      Slot Aug 2024, Potter Jan 2025).
- [x] 🐛 **`game_id` IS NOT CHRONOLOGICAL WITHIN A SEASON.** It rises across
      seasons, which is why this went unnoticed, but 23/24's ids span a range
      of 74,000 against 24/25's 379. Sorting a season by id is arbitrary and
      had Palace hiring Glasner mid-season, reverting to Hodgson, then hiring
      him again. Everything chronological must sort by `startTime`.
      **Still outstanding:** `role_bank.last_club` picks a player's latest
      match by game_id — right across seasons, so the club is correct, but it
      may pick the wrong match inside the final season (matters only for a
      January transfer).
- [x] **Unit of computation is the MATCH** (user's call, and correct):
      spells and seasons cut across each other — Glasner's 90 matches span
      three seasons, Chelsea's 24/25 spans two managers — so neither can be
      built from the other. Every cut is a groupby: club, club x season,
      spell. League table shows CLUBS; the team page shows SPELLS; the
      predictor reads the current spell.
- [x] **28 team metrics** (`services/mental/team_metrics.py`), tagged phase
      (with / against the ball) and kind (style / quality). Style is never
      ranked — a table that ranks directness asserts that one way of playing
      is correct.
- [x] **Opponent adjustment**, fitted across each season's whole league at
      once as `value = league mean + team term + opponent term + home`, by
      alternating means. Fitted per spell instead would measure every manager
      against a different baseline. Sanity check it works: Arsenal's raw 8.16
      shots conceded becomes 8.52 adjusted, because a good side never plays
      itself and so faces a weaker schedule than average.
- [x] 🐛 **The first gate returned exactly 1.00 for every quality metric** —
      arithmetic, not reliability. The adjustment yields ONE number per team,
      constant across its matches, so both halves inherited the identical
      value. Fixed by re-fitting the adjustment INSIDE each half.
- [x] **Gate (split-half, per manager spell): 26 of 28 at 0.40+.** Far more
      reliable than the player layer, as the sample argued it would be — a
      team logs 28,964 events a season against a player's ~2,000. pass_pct
      0.93, buildup_ok_pct 0.93, recovery 0.91, poss_share 0.90, shot_90
      0.84, shot_con_90 0.83, ppda 0.82. Two fail and both make sense:
      `shot_dist_con` 0.37 (where the opponent shoots from is his choice) and
      `interception_90` 0.33.
- [x] **Teams page** (`web/app/teams/`) with its own weight config, style
      shown but unrankable, and a click-through to the club broken down by
      manager. Nav is now Predictor / Players / Teams / How it works — the
      Visualiser tab removed as agreed.

Liverpool under Klopp against Slot, straight out of the data: PPDA 6.2 to
8.0, press height 36.9 to 33.9, shots 18.9 to 15.0 adjusted.

### Team layer rebuilt after the user's eye test failed it (2026-09-18)

- [x] **Set pieces split from open play.** 32% of shots and 35% of goals come
      from one, and the spread is huge, so pooling them credited a corner
      routine and an open-play move as the same capability. Note the measure
      that matters: Arsenal's set-piece SHARE looks low (their open-play
      volume is enormous) while their set-piece OUTPUT is the best in the
      league at 0.52 goals a match. Share was the wrong lens.
      Gate: defending set pieces repeats (0.53); CREATING from them barely
      does (0.22) — about eleven big chances a half-season is too few to
      measure, a sample limit rather than an absence.
- [x] **Config thinned from 13 to 10, everything style-conditional dropped.**
      `long_ok_pct` only means something if a side plays long, `pass_pct` is
      flattered by safe passing, `buildup_ok_pct` presumes they build from the
      back. Those measure a CHOICE, not a quality. What survives does not care
      how you got there: reached the box, made a big chance, took a shot,
      moved it up, and the conceded equivalents.
- [x] **Points in as a column, never in the score** (user's call). Justified:
      a side's points in half a season predict its other half at **0.59**,
      while a six-metric process blend manages **0.78**. Scoring points would
      make the ranking partly the league table and lose exactly that edge.
- [x] **Results ring + GAP column.** Process percentile beside results
      percentile, and the difference. Hull 26/27: process 20, results 88, gap
      −68 — 20th on performance, 2nd on points. Gaps collapse with sample
      (±68 at four matches, −15 to +17 over 38).
- [x] **Style split by phase**, three tags each for with-the-ball and
      against-the-ball, in words rather than six numeric columns.
- [x] 🐛 **Adding 26/27 wrecked the points gate**: `predicts_points` halves
      every team-season, and four-match seasons became two-match halves.
      Twenty rows of that dragged conceding big chances from −0.53 to −0.18,
      so the gate then discarded it. Now requires 20+ matches to halve.
- [x] 🐛 **Short-tenure clubs excluded from the pooled team view** — Leeds,
      Sunderland and Ipswich had 42 matches against everyone else's 118. One
      season of noise is not a description of a club; they appear in their own
      season instead.
- [x] 🐛 **Player share denominator was the CLUB's minutes, not the PERIOD's.**
      A Coventry keeper who played all four of their 26/27 matches scored 95%
      and stood beside men with ten thousand minutes, because his club had
      been in the league four weeks. Now the period's fullest programme
      (2627 = 400 min, a season = ~3,900, pooled = 11,987).
- [x] **The minutes bar follows the period.** 85% of five rounds keeps 92
      players; 85% of four seasons keeps five. The default is now the
      strictest rung that still leaves a quarter of the rows.

### ⚠ CORRECTION — what was built is the TEAM STATS LAYER, not team mental

Agreed with the user 2026-09-18, and it reframes thread 2. In the user's
model **a club's mentality is the collection of players it has**, so team
mental is the SQUAD'S PLAYER RATINGS AGGREGATED. What is on the Teams tab
today is measured directly from team events — box entries, shots, chances
conceded — which is the **team stats layer**, a thing never discussed and
built under the wrong name. It is good work and it stays; it is just not
team mental.

**The three sit together, and the gap between two of them is the third:**

    team mental        what this squad SHOULD be capable of
                       (aggregated from the player ranks)
    team stats layer   what the collective ACTUALLY produces
                       (measured from team events — built)
    MANAGER EDGE       the difference between them

A squad of individually strong players producing weak collective output is
badly coached or badly fitted; a modest squad producing more than the sum of
its parts is the opposite. That is why the two layers are not a duplication —
the user's own worry — and neither can be dropped: the edge needs both.
It also gives a manager a number: his points per game against what his
squad's ratings predicted.

### THREAD 2 remaining, in the user's order (next session, 2026-09-18 pm)

1. **Team mental** — minutes-weighted aggregate of the squad's player ranks.
   **BOTH the average AND the weakest link** (user's call): a side with three
   brilliant players and a hole at centre-back is not described by a mean,
   and "where is this team soft" is exactly what the versus function needs.
2. **Zones — 15 cells** (5 channels x 3 thirds, the grid already in
   `build_territory.py`; the user was explicit that this is how an analyst
   looks at a pitch). Per team AND per manager spell, so the shift under a
   new manager is visible cell by cell.
   NOTE: `scripts/build_team_zones.py` predates the team layer and builds
   zone strength by summing PLAYER ratings. Measure zones straight from
   events instead, as `team_metrics.py` does.
3. **Manager edge** — squad rating vs collective output vs points per game.
4. **Team stats layer** — built; needs positioning against 1-3 rather than
   standing alone. This is where style earns its place.
5. **Versus** — one team against one, zone by zone: who wins which battle.
   The thing the predictor actually consumes, and the reason style is not
   decoration.

Only after all five does the predictor get fed.

### Plots on the team page (2026-09-18)

Order set by the user: **plots → manager edge → predictor test run (EPL
only) → other four leagues (scrape Sunday or Monday, after the latest
fixtures) → visuals**. No player page this session or the next.

- [x] **`services/mental/plots.py` + `scripts/build_team_plots.py`** — shots
      at both ends, average positions, pass networks. Shots stored ONCE and
      tagged with season + spell index rather than copied into every cut;
      written longhand the 27 clubs came to **8.5 MB, now 2.1 MB** (worst
      club 111 KB). Positions and passes are aggregates so they are stored
      per cut, floor 4 matches.
- [x] **Shot maps** — attacking half only, penalties excluded, shooter named
      on hover (`shooters` list + index per club). 🐛 Shots FACED arrive
      mirrored into the side's own frame, so they sit at LOW x — drawn with
      the attacking-half mapping every faced map on the site was **empty**.
      The defensive map is now flipped so the goal being shot at is at the
      top of both pictures and the two are comparable left-to-right.
- [x] **Pass networks** — receiver INFERRED as the next touch by the same
      side; resolves for **98.9%** of completed passes and the page says so.
      Eleven players, not fourteen: ranked on touches the eleven came out as
      four centre-backs and no striker, so selection is by APPEARANCES with
      touches only as a tiebreak. 🐛 Liverpool then had no keeper (Alisson
      and Mamardashvili split 25/26) — a goalkeeper slot is now reserved,
      the keeper identified from acts only a keeper performs.
- [x] **Pizza chart** — interactive SVG, kept over an mplsoccer render at
      the user's call ("i cant interact with something that small"); the
      mplsoccer version was built, rejected and deleted. Wedges are **the
      ten metrics the score is actually built from**, in phase then weight
      order: drawn from all twelve quality metrics it was a third set
      pieces, which carry ten points of the hundred.
- [x] 🐛 **Zone maps were mislabelled.** The primary map is filtered by the
      period selector but its title was hardcoded "All seasons" — Aston
      Villa's four matches of 26/27 read as four years. Title now follows
      the period, and manager spells moved from a row of maps to a **compare
      dropdown**, because a 4-match period beside a 118-match spell is not a
      comparison.
- [x] 🐛 **Coventry and Hull had no page at all.** `generateStaticParams`
      read `club.json`, the pooled table, which excludes clubs under the
      10-match floor — and under `output: export` a route that was never
      generated is a hard error, not a soft 404. Built from the union of
      `club.json` and `club_season.json`; 25 → **27 pages**.
- [x] 🐛 **Crests.** The team page built `/logos/{league}/{team}.png` by
      hand, so "Man Utd" never found "Manchester Utd.png"; and
      `Nottingham.png` sat alone in a folder spelled with an underscore. The
      page now reads the resolved `meta.crests` map, and `crest_map()` scans
      both folder spellings. **19 of 20 current clubs resolve.** Still
      genuinely missing a badge FILE: Burnley, Leicester, Luton, Sheff Utd,
      Southampton, West Ham, Wolves.
- [x] **WIDE** no longer shown raw — `web/app/lib/positions.ts` mirrors
      `BUCKET_SHORT`/`BUCKET_LABEL`, so the squad cards and the weakest-
      position column read "WNG" / "Winger".
- [x] **Navigation** — `Crumbs.tsx` on every page below the top level, and
      the header nav marks the active section (a team page lights up
      Mental). The mental tab is now linkable as `/mental?tab=teams`.

### Manager edge (2026-09-18) — MEASURED, RENAMED, NOT ATTRIBUTED

`scripts/build_manager_edge.py` ships **per-spell player minutes** (61 spells,
72 KB) so the page can ask "which players did he pick, and for how long".
The rating stays client-side because it depends on the reader's weights.

Two definitions tested, on 60 full club-seasons (26/27 excluded at
`MIN_SEASON_MATCHES = 20` — four matches had Arsenal "over-achieving by 1.35
points a game"):

- ❌ **collective − squad — REJECTED.** Correlates **0.17** with points.
  Its extremes are a list of playing STYLES, not of over-achievers:
  Brentford bottom of the league on 1.47 points a game, Bournemouth top on
  1.26. The collective score is nine-tenths open play and some sides are
  built on set pieces. Needed a fix first even to get that far — squad is a
  percentile among PLAYERS (35–70) and collective among CLUBS (4–91), so
  raw subtraction was mostly the difference in spread.
- ⚠️ **points − points the squad predicts — KEPT, but as a CLUB property.**
  Repeats at **0.50** season to season and the extremes are recognisable
  (Emery's Villa twice and Nuno's Forest over; Kompany's Burnley and
  Maresca's Chelsea under). But it moves **no more when a club changes
  manager (0.27) than when it keeps one (0.29)**, and the first definition's
  change test was p = 0.12 on 12 changes. **Four seasons of one league
  cannot separate the manager from the club**, so the page calls it "Squad
  against results" and says so in as many words.

Report: `data/reports/manager_edge.json`. Re-run the test alone with
`--gate-only` (skips the 4-minute minutes build).

### Predictor test run — Premier League only (2026-09-18)

`scripts/experiment_predictor_epl.py`. Walk-forward on 1,140 EPL matches,
train 23/24+24/25, test 25/26 (350 matches after matchday 3). **Every rating
is an expanding mean rebuilt before each round**, seeded from last season's
final standing at `PRIOR = 6` matches — the season-long opponent-adjusted
averages the team pages show contain the result of the match they would be
predicting. Season normalisation uses earlier seasons only, for the same
reason.

| model | log-loss | accuracy |
|---|---|---|
| base rate | 1.0880 | 42.0% |
| points (ppg difference) | 1.0364 | 48.6% |
| **process (team layer)** | **1.0342** | 48.6% |
| **both** | **1.0254** | 47.7% |

So the event-derived process metrics beat a points baseline on their own and
add **+0.0110** on top of it. The team layer carries match-level signal.

- 🐛 **Caught a sign error in the first run.** `process` scored 1.0883
  against a base rate of 1.0880 — landing exactly on the base rate is not a
  null result, it is a broken feature. The conceded metrics count what the
  opponent was ALLOWED, so higher is worse, and subtracting them from the
  other side's attack made a leaky back four read as a hard one. The four
  ratings now go to the model separately and it learns the signs itself.

**But that is the wrong opponent.** Beating a points baseline is not the
question — the shipped model already prices fixtures from Understat xG
through Dixon-Coles and the draw classifier.
`scripts/experiment_predictor_stack_epl.py` runs both arms on the SAME 350
EPL fixtures (train 24/25, test 25/26, name-matched Understat↔WhoScored by
the same token rule as the crests; `--cached` re-scores without the 4-minute
rebuild):

| arm | log-loss | accuracy |
|---|---|---|
| shipped, as served | 1.0337 | 48.6% |
| shipped, recalibrated | 1.0318 | 48.3% |
| process only | 1.0420 | 47.7% |
| shipped + process ×4 | 1.0482 | 45.4% |
| shipped + one feature | 1.0381 | 47.1% |
| shipped + process, C=0.05 | **1.0317** | **50.3%** |

❌ **NOT SHIPPED.** The best the layer manages is **+0.0001** log-loss, and
only at C=0.05 — regularised so hard the process features are nearly off.
Left free they make it clearly worse (1.0482 vs 1.0318): seven parameters on
350 training matches memorises. The likely cause is collinearity — box
entries, shots and big chances ARE chance creation, so the layer reproduces
Understat xG instead of adding to it. The accuracy gain is 2 points on 350
matches against a standard error near 2.7, so it is not evidence either.

**Retest on five leagues** (~1,750 test matches) once the other four are
scraped; that is where an edge this small either appears or dies. Report:
`data/reports/experiment_predictor_stack_epl.json`.

### Versus, tabs, best XI, form (2026-09-19)

- [x] **Versus** (`web/app/versus/`, `/versus`) — one side against another,
      zone by zone, two teams picked in the browser. **The whole thing turns
      on the reflection**: the fifteen cells are stored in each team's own
      frame, so the same patch of grass is cell *j* for one side and cell
      *14 − j* for the other — a 180° turn that flips the third AND the
      flank (`DRW ↔ ALW`). Get the flank half wrong and every map is
      mirrored plausibly. Each cell is an EDGE: the attacker's chance origin
      there against the defender's leak from there, both percentiled across
      the league. Verified not degenerate — spread sd 14–23 on close
      fixtures, and Brentford's edge on Brighton lands in the middle third
      and their own right wing, which is the direct side the metrics said
      they were.
- [x] 🐛 **The first versus measure threw the LEVEL away.** Averaging two
      percentiles per cell is purely relative: Manchester City concede few
      chances anywhere, but ranked cell by cell they are still leakiest
      somewhere, so Burnley — the worst attack in the league — scored **95
      of 100** down that flank and the page read "Burnley should come
      through against Manchester City". Replaced with
      **attack x defence / league average**, the standard form, which keeps
      the level: Burnley 5.6 expected chances a match against City's 17.5,
      Arsenal 7.8 against Liverpool 6.6. Both maps now share one colour
      scale so a mismatch looks like one, and the page states the projected
      chance counts.
- [x] **Versus reworked as an analytics page** — crests facing each other,
      a written **bottom line** built from the same numbers as the maps,
      each map carrying its OWN legend beside it rather than one at the far
      right of the heading, and each side's best routes listed under its own
      map (a single mixed top three was the stronger team three times over,
      which says nothing about how the weaker side might hurt them).
- [x] **Team page tabs** — Squad / Formations / Data hub
      (`components/Tabs.tsx`, shared with the mental tab, state in the URL).
      Zones and the pass network now sit SIDE BY SIDE, not stacked.
- [x] **Best eleven** (`lib/bestXI.ts`) — the shape is an OUTPUT: five
      formations are filled and the one the squad scores highest in wins.
      🐛 Greedy filling was wrong and wrong invisibly. Liverpool field no
      centre-midfielder at all (Gravenberch, Mac Allister, Jones and
      Szoboszlai all bucket as DM) and Szoboszlai qualifies in four
      positions — so the wide and holding slots took both attacking
      midfielders and the XI came out a man short with no way to see it was
      avoidable. Fixed with **augmenting paths**: an empty slot asks a
      player whether his current slot can be refilled by someone else,
      recursively. Liverpool now field eleven with Wirtz shifted to AM.
- [x] **Form** (`scripts/build_team_form.py`) — last five W/D/L in the team
      header, coloured, hover for the scoreline. Ordered by KICKOFF, never
      game id.
- [x] **"WIDE" → "AW" / "Attacking winger"** (user's call: same construction
      as AM and DM, so the column decodes from its neighbours). An earlier
      "WNG" failed — the first thing asked of it was what it meant. Two real
      bugs behind the complaint: the combined players table printed the raw
      bucket key, and `meta.json` was STALE, still saying "Wide attacker"
      from a build before the label changed — so the players board and the
      team page disagreed. Payload rebuilt.

### Manager change as a predictor input (2026-09-19) — SUGGESTIVE, NOT PROVEN

`scripts/experiment_predictor_manager.py`. The claim: `FormModel`'s decayed
38-match window does not know a club changed manager, so a side three games
into a tenure is rated ~90% on the predecessor's football. Train 23/24, test
24/25 + 25/26 (700 fixtures, **206 with a side under 10 matches into a
tenure** — 29%).

| arm | log-loss | on new manager | accuracy |
|---|---|---|---|
| naive (window as now) | 1.0760 | 1.0486 | 47.4% |
| **seed from league mean** | **1.0733** | **1.0396** | **48.0%** |
| full spell-scoping | 1.0892 | 1.0769 | 47.3% |
| "matches into tenure" feature | 1.1098 | 1.1189 | 46.0% |

- ⚠️ **The first version of this test was a FALSE NEGATIVE.** Spell-scoping
  changed TWO things — the seed AND swapping a within-season window for a
  cross-season one — and lost by 0.0132. Isolating the seed reversed the
  sign. Always change one thing.
- ✅ **What works is ONLY the seed.** Under a new manager, start from the
  league average rather than from his predecessor. Gain is **3x larger on
  the fixtures it targets (+0.0090) than overall (+0.0027)**, which is the
  signature a real fix for a 29% subset should have.
- ❌ **Throwing away the club's history HURTS** (full spell-scoping, −0.0132
  — five times the seed effect, opposite direction). The club's past
  football does carry to a new manager, because the squad does. Consistent
  with the manager-edge result: **the club is the unit, not the manager.**
- ⚠️ **Not significant.** Paired bootstrap on the same fixtures:
  P(better) = **0.84** both overall and on the targeted subset, and both
  95% CIs include zero ([−0.0078, +0.0287] on new managers). 206 affected
  fixtures in one league cannot settle it. **Retest on five leagues** —
  ~1,000 affected fixtures would shrink the interval about 2.2x.

### Injury / suspension data — AVAILABLE, needs a scrape

`soccerdata`'s `WhoScored.read_missing_players(match_id=...)` returns injured
and suspended players with reason and status, and the docstring says "ahead
of each game" — it reads `/Matches/{id}/Preview`, which is published BEFORE
kickoff, so it is legitimately usable pre-match rather than hindsight.

Cost: **one page fetch per match, nothing cached yet** (`~/soccerdata/data/
WhoScored/previews/` is empty against 1,194 event files). That is a scrape of
the same order as the event scrape — fold it into Monday's run rather than
doing it ad hoc.

Also spotted: `soccerdata` exposes **ClubElo** and **Sofascore** readers, and
the predictor has no Elo of any kind.

### Process Elo — the rating spine (2026-09-19)

`scripts/build_process_elo.py`. Replaces the expanding-season-mean, whose
three faults were structural: it resets every August, needs a hand-picked
`PRIOR = 6` seed, and needs a separate opponent-adjustment pass. An online
rating has none of them — and it is **walk-forward by construction**, so
there is no window to get wrong and no seed to leak through.

Multiplicative, because the predictor needs a SCORELINE:
`log λ_home = A_home − D_away + HOME`, each rating moving by the log-residual
after every match. The λ pair drops straight into the Dixon-Coles grid.

**Fitted K=0.16, home=0.15, decay=1.0, conv=0.18, rho=−0.05** on 23/24+24/25.
K held at 0.16 when the grid was widened, so it is a real optimum.

| | log-loss | accuracy |
|---|---|---|
| base rate | 1.0852 | — |
| **process Elo** | **1.0388** | 45.3% |
| shipped Understat-xG model | 1.0337 | 48.6% |

- ❌ **My "feed it big chances" hypothesis was WRONG and the test said so.**
  Four observables compared head to head: origins **1.0388**, shots 1.0416,
  box entries 1.0457 (but best accuracy, 48.7%), **big chances 1.0631 —
  the worst**. There are only ~2 big chances a side a match, and a rating
  fed two events an afternoon learns too slowly to be worth the extra
  quality per event. **Volume beats weighting here.**
- ⚠️ So the Elo beats the base rate by 0.046 but is **0.005 behind the
  shipped xG model**. Consistent with everything else: our observables count
  chance QUANTITY, Understat's xG weighs chance QUALITY.
- **The one untested combination is the obvious next step: feed the Elo
  Understat xG.** That keeps the structure (no reset, no seed, opponent-aware,
  cross-season) and uses the observable that actually discriminates.
- 🐛 The table shipped only current clubs, so versus lost its projection for
  any relegated side with no explanation. Now ships every club ever rated,
  flagged `current`.

### 🐛 `conv` WAS FITTED BY THE WRONG CRITERION — and it inverted a finding

`conv` means "goals per unit of the observable": a pure LEVEL calibration.
Fitted by log-loss it came out at 1.0 and the page projected **3.77 goals a
match against an actual 2.75** — every scoreline a third too generous while
the probabilities beside it were fine. Log-loss is nearly blind to the
level, because an outcome depends on the RATIO of the two lambdas.

Solved from the data instead (`conv = mean goals / mean λ`), and the
observable ranking **inverted**:

| observable | TEST before | TEST after | acc after |
|---|---|---|---|
| Understat xG | 1.0358 | **1.0304** | 48.7% |
| big chances | 1.0631 *(worst)* | **1.0323** *(2nd)* | **50.0%** |
| chance origins | 1.0388 | 1.0372 | 45.3% |
| open-play shots | 1.0416 | 1.0422 | 46.3% |
| box entries | 1.0457 | 1.0456 | 48.7% |

**So "volume beats weighting" was wrong and I had already written it down.**
A big chance is worth about one goal in its own units; the grid stopped at
0.5, so that arm was forced to half the level it needed and lost on the
handicap. Quality-weighted observables win once the level is right. The
lesson is about the harness: a parameter meaning "the level" must be fitted
to the level, never to a criterion that cannot see it.

### THE TEST RUN — process Elo against the shipped predictor

`scripts/experiment_elo_vs_shipped.py`. **372 identical EPL fixtures of
25/26**, neither arm having seen the season, shipped running exactly as
served (Dixon-Coles → draw classifier → `unified_probs`).

| arm | log-loss | accuracy |
|---|---|---|
| base rate | 1.0889 | 41.7% |
| shipped | 1.0326 | 48.9% |
| **process Elo** | **1.0321** | 48.7% |
| **blend of the two** | **1.0292** | 48.1% |

Paired bootstrap on the same fixtures:

- **elo vs shipped: P(better) 0.519** — dead level. Worth stating plainly:
  an online rating with **no seed, no season reset, no separate
  opponent-adjustment pass and no draw classifier** matches the full stack.
  Equal accuracy, a fraction of the machinery.
- **blend vs shipped: +0.0034, P 0.790**; blend vs elo: +0.0029, P 0.772.
  The blend beating BOTH means the two disagree usefully — they are not the
  same model wearing different clothes. Suggestive, not established; both
  CIs include zero on 372 fixtures.

**Retest on five leagues** (~1,750 fixtures) — the same argument as the
manager seed, and the same fix.

### THE LAYERED MODEL — corrections to history, not a rival predictor

**The user's frame, and it is the right one:** a team is as strong as its
players, shaped by a manager who chooses which of them play and what they
try to do, and measured by how well they do it. The manager is not a third
term — he is the COMBINER, acting through two observable channels:
**selection** and **style**. That is why four separate attempts to find a
manager effect all failed: there was nothing left over to find.

**And the insight that follows:** a team's recent xG already contains its
players, its manager's selection and its style. The history is not wrong —
it is OUT OF DATE whenever the team that produced it is not the team about
to play. So the layers earn their place as a CORRECTION TO CHANGE, not as a
better average.

- ⚠️ **Every earlier experiment in this folder was invalid.** They ran the
  Elo arm with stages [2] zones, [4] draw classifier and [5] unified_probs
  REMOVED, then reported `elo 1.0321 vs shipped 1.0326` as like-for-like. It
  was two stages against five. Nobody asked for those layers to be dropped.
  The "blend beats both" result is void for the same reason — it averaged a
  five-stage output with a two-stage one, and is not a layer in this
  architecture at all.

`scripts/build_change_layers.py` + `scripts/experiment_layered.py`. The FULL
stack runs in both arms; one correction is applied to the lambda:

    lam *= exp(w_missing * missing + w_stale * stale)

`missing` is the rating value of regulars not in today's twenty — derived
from the matchday squad lists, so it works for **every match on disk**,
which the preview scrape cannot do. `stale` is the share of the rating
window predating the current manager. Both walk-forward, both ZERO when
nothing changed.

Fitted on 24/25: **w_missing = −4.5, w_stale = 0.0**.

| cut | n | shipped | layered | gain | shipped hit | layered hit |
|---|---|---|---|---|---|---|
| all | 372 | 1.0326 | 1.0303 | +0.0023 | 48.9% | 48.7% |
| most changed | 116 | 0.9965 | 0.9940 | +0.0025 | 49.1% | **50.0%** |
| some change | 116 | 1.0424 | 1.0372 | +0.0052 | 48.3% | 46.6% |
| **unchanged** | 140 | 1.0545 | **1.0545** | **+0.0000** | 49.3% | 49.3% |

- ✅ **The architecture works.** Where nothing changed the two models are
  bit-identical, +0.0000. The correction can only fire where the team has
  actually moved.
- ✅ Gains positive wherever it fires; best hit rate on the most-changed cut.
- ❌ **Of the manager's two channels, only SELECTION earns anything.**
  `w_stale` fitted to exactly 0.0 — "this manager is new so the history is
  stale" is worth nothing once availability is in. The squad is what
  carries, which is the fifth independent confirmation this week.
- ⚠️ **Not significant.** Paired bootstrap on the 232 fixtures it touches:
  **P(better) = 0.633**, CI [−0.0201, +0.0271].

`scripts/predict_upcoming.py` shows both arms for the coming round with the
correction spelled out per side. Nothing is wired into
`prediction_service.py`.

### Injuries — scraped, valued, wired

- `scripts/scrape_injuries.py` — absentees for UPCOMING fixtures only, from
  the match preview page, which is published BEFORE kickoff. ~50 pages a day
  across five leagues against the ~5,700 a full backfill would need. Added
  to `run_weekly.py`; safe to run daily.
- `scripts/build_injury_web.py` — joins each absentee to his rating from the
  **last complete season**, because a player injured since August has no
  useful record of this one. 18 clubs, 76 absentees, **55% rated**; the
  unrated are summer signings with no PL history, so there is no basis to
  value them and they contribute nothing rather than a guess.
- 🐛 Preview pages say "Manchester United" where the event feed says "Man
  Utd", and `utd` is not a prefix of `united` — the token matcher needed
  that one alias or Man Utd's absentees landed under a key nothing looks up.

### Versus — now ends with a projection

Elo → λ pair → Dixon-Coles → triplet and likeliest scorelines, shown **twice**
(ratings alone, and with the absentees deducted) because the injury deduction
is reasoned, not fitted. Both numbers visible beats one number with an
ungated adjustment baked into it.

**Next:** other four leagues — scrape Sunday or Monday, after the latest
fixtures.

**Also noted:** the user suggests a football DATA-ANALYST skill for this tab
rather than the betting-expert one — the useful part of that skill here was
its "calibrate, never hand-tune" discipline, not its market mechanics.

### 3D visuals — replacing the flat plots (2026-09-19/20)

User's brief: *"ground breaking 3d visuals... replace the boring 2d plotting
to something it is fun and intuitive to look at."* three.js + fiber + drei,
dynamic-imported so no other page pays the ~600KB.

- **One stage, shared by everything** (`Pitch3D.tsx` / `PitchScene.tsx`).
  FIFA dimensions in metres; Opta→scene conversion lives in `toX`/`toZ` and
  nowhere else. `/lab` renders all five pieces off the same components.
- **Shot map** (`ShotCloud.tsx`) — balls sized by ∛xG (volume, not radius),
  coloured by outcome; click one to stand at the shooter's eye with the
  angle-to-goal wedge, distance, xG and where in the goal it finished.
  Selection **hides** the rest rather than fading them, which is both the
  honest reading and far faster.
- 🐛 **drei `<Text>` took the whole scene down.** The troika font fetch
  suspends, and a suspending component inside a Canvas with no boundary
  above it unmounts everything — a black rectangle indistinguishable from
  one still loading. Replaced with `<Html>`, plus `<Suspense>` and a
  `SceneGuard`. Every asset since is generated in-memory for this reason.
- 🐛 **The camera fought the reader.** A `useFrame` easing toward the preset
  ran every frame, so any drag was undone and orbit looked broken. A flight
  now happens once and `onStart` cancels it for good.
- 🐛 **The D was drawn inside the box.** `Math.min(1, PEN_D - SPOT)` clamps
  5.5 to 1 *before* dividing — a 167° sweep instead of 106°. The `min`
  guards `acos`, it is not a limit on the distance.
- 🐛 **`useFrame` below an early return** in `TerrainCells` — the hook count
  changed on an unrecognised cell key and React tore the tree down. This is
  the reported "columns show for a second and crash". Third time this class
  of bug has landed; hooks go above every guard.
- **`football-3d-visualizer` skill** (`.claude/skills/`) — coordinates,
  pitch geometry, labels, performance, streaming, + a reference telemetry
  sender. Written after the pitch fixes so the reasoning is captured.

### 🐛 THE PITCH WAS MIRRORED (2026-09-20)

User: *"sides seems flipped in av pos, right side winger appears on left."*
Correct, and it had been wrong for weeks in every view built on `toX` —
pass map, zone columns, coordinate pins. Nothing looked broken, because a
mirrored pitch never does; it took the whole eleven on screen at once.

Settled two ways rather than by convention:

- **Which side is low y — from the data.** Opta means, Arsenal 25/26: Saka
  18.9, Timber 18.5, Saliba 32.0 against Trossard 77.8, Martinelli 69.6,
  Magalhães 67.2. Low y is the attacking team's RIGHT. Understat agrees
  (Saka 0.382, Trossard 0.563), so both feeds share the convention.
- **Which way that is in the scene — from the geometry.** For any observer
  `right = forward × up`. A player attacking +z gives
  `(0,0,1) × (0,1,0) = (-1,0,0)`: his right hand is world −x. Cross-checked
  against three's own `lookAt`, which puts world +x on screen right for a
  camera at +z looking back at the origin — `(0,0,-1) × (0,1,0) = (1,0,0)`,
  the same rule.
- So y = 0 must be **−x**. `toX` sent it to **+34**. Fixed to
  `(optaY / 100) * PITCH_W - PITCH_W / 2`.
- **`shotX` was never wrong** — Understat's low y is also the right and
  `(uy - 0.5) * PITCH_W` already sent it to −x. That is exactly why the shot
  map looked fine while everything on `toX` did not, and why this took so
  long to surface.
- Zone `CHANNELS` already had RW at y 0–21.1, so the labels were right all
  along and only the conversion was mirrored.
- 🐛 Second flip, in the overhead seat: looking straight down is the
  degenerate case for `lookAt`, and with the camera on the +z side of its
  target the resolved up came out as world −z — the attacking goal at the
  BOTTOM of the picture, upside down against every football diagram drawn.
  Moved to the far side of the target.

### The site gets a spine (2026-09-20)

User's recap: the predictor and the visuals are good; mental ranking and
versus are unclear. Diagnosis agreed — **the good work had no home and the
uncertain pages had no reason**. Every visual was in /lab while the pages on
the site were the ones nobody could place.

- 📊 **THE PREDICTOR IS GOOD, AND NOW THERE ARE NUMBERS.** Graded on 230
  live rows: **51.3% outright** against 41.7% for always picking the home
  side (+9.6pp), log loss **1.0024 against 1.0768** for league base rates
  (6.9% better), and calibrated where the mass is — the 25–35% band holds
  320 observations, says 29.9% and happens 29.1%. At the top it is
  UNDER-confident: says 66.8%, happens 83.3%. The good direction to be wrong
  in.
- 📊 **And the draw rule is close to free**, which was the user's question.
  `DRAW_CALL_MIN = 0.32` calls a draw once the calibrated draw probability
  reaches 0.32 regardless of which side is higher. On 230 rows: shipped call
  50.9%, pure argmax 51.3% — **one fixture in 230**. Of the 38 it flips, the
  rule wins 12 and argmax wins 13. Its draw calls hit 33.3% against a 24.8%
  base rate, so they carry real signal. ⚠️ But the threshold was swept on
  194 rows and the recorded cliff (0.0pp at 0.32, 6pp at 0.30) is the shape
  of a fit to noise, not a finding. Re-sweep on five leagues before touching
  it either way.
- **VERSUS IS NOW THE FIXTURE PAGE.** Predictor rows link into it, the
  shipped model's call and triplet sit at the top, and the evidence is
  underneath. The page's own process-Elo projection stays, LABELLED as a
  second opinion — two independent models that disagree is information, and
  hiding the disagreement would be the only way to get it wrong.
- 🐛 **The links resolved for four fixtures in ten.** The round export and
  the team layer come from different feeds and disagree on seven of twenty
  clubs in BOTH directions — "Coventry City"/"Coventry",
  "Nottingham"/"Nottingham Forest", "Manchester Utd"/"Man Utd". Ported the
  token matcher that `build_injury_web.py` already uses rather than writing
  a second rule that would drift from it. **20/20 names, 10/10 fixtures**,
  and a bare "Manchester" still resolves to null rather than guessing.
- 🐛 The fixture page would not build: `useSearchParams` cannot resolve
  during prerender, so the route needs a Suspense boundary or the export
  fails outright.
- 🐛 And I put a `useMemo` below the early return — the fourth time that
  shape has landed in this project, and the first time it was mine.
- **Mental → Ratings.** The name promised psychology and delivered event
  metrics, which is why nobody could place the page. Route, nav, titles and
  copy all reframed as a capability profile — the correction the user had
  already made for the team layer, applied to the player side.
- **`/rejected` publishes what lost**: the team layer at +0.0001, the
  manager effect rejected four ways, the blend at P=0.790, the manager seed
  at 0.840, availability at 0.633, context draw features inside noise, and
  my own "volume beats weighting" claim reversed by my own arithmetic error.
  Almost no project shows this and it is the most credible thing on the site.
- **Match page, on the user's instruction:** the 3D zone map came off it
  entirely ("only use stuff we have tested in the lab"); the two elevens go
  side by side at the top; the projection shows ONE number with the
  absentees already in rather than asking the reader to choose; and the shot
  maps are in, taken AND faced.
- **Shots faced needed no new data** — the league file already carries the
  opponent on every row, so the shots against a side are everyone else's
  rows filtered to them. Arsenal 25/26: 553 taken, 315 faced. Drawn in the
  SHOOTER's frame, not mirrored, because "where do they get got at from" is
  a question about the attacker's position.
- 🐛 Pass payloads existed for 25/26 only while the site's current season is
  26/27, so every eleven on a match page would have 404'd. Built 24/25 and
  26/27 as well. Also split the event season from the table period —
  "All seasons" is real for the tables and meaningless for a per-season
  event file.

### Daily updates, and the results the site was hiding (2026-09-20)

- 🐛 **THE SITE WAS SHOWING A PREDICTION WHERE A READER EXPECTS A RESULT.**
  User: *"i can see yesterdays matches with no result.... why?"* The results
  were on disk — the fixtures file refreshed at 10:04 with Brentford 3-0
  Chelsea, Brighton 3-0 Arsenal — but `round.json` was from the 16th and had
  never been regenerated. Worse, the column headed "Score" was the PREDICTED
  modal scoreline, so a Sunday reader saw "1-1" for a match that finished
  3-0. A site whose stated claim is "what it expects, what happened, and what
  it learned" was publishing the first and hiding the second.
- 🐛 **And the round emptied itself as the weekend went on.** The season sim
  holds only UNPLAYED fixtures, so regenerating showed four of a ten-fixture
  round with the other six simply gone. Played fixtures are now read back out
  of the history log — which also means the page shows what we ACTUALLY said
  at the time rather than what the model would say now with the result in
  hand. Round 5: **10 fixtures, 6 played, 4 calls right.**
- The predictor table leads with the result once there is one, "said X"
  underneath, and marks the call hit or miss.
- **`scripts/run_daily.py`** — one chain, 09:00, sources → grading → derived
  → payloads → export, every step non-fatal so a source being down costs
  that source and not the day. **Incremental by design**: the event scraper
  asks only for matches missing from its parquet, Understat fetches what is
  new, fixtures refresh in place — so a daily cadence means a handful of
  matches and there is never a big scrape to nurse. Verified 11/11 steps in
  6.8 min for one league, rebuild-only.
- Export runs LAST, because it reads the sim and the graded history the
  steps above just refreshed. Running it first is exactly how round.json
  ended up four days older than the results sitting beside it.
- **Match page**: named after the match rather than "Versus", season picker
  gone (it is always now), and every heading that names a club carries its
  badge — resolved through the same name matcher as the fixture join, 20/20.
- 🐛 **The two zone maps rendered at different label sizes** and it was never
  the camera: both canvases draw the PITCH identically, so only the `<Html>`
  differed — and `distanceFactor` derives its scale from the canvas's
  measured size, which is stale on a canvas measured before the grid gave it
  its width. Took the dependency out instead of chasing it: a zone value is
  a number to be READ, so it is now screen-space and constant, legible at
  every zoom and incapable of disagreeing between two canvases.

### The Monday call, and a loader (2026-09-20)

- **Per-canvas 3D loader.** A scene is not ready when React mounts it: the
  turf is generated on a canvas (~80ms), the player model is 761KB to fetch
  and decode, and every geometry is built on first render. Until then the
  canvas is a dark rectangle — indistinguishable from the black rectangle a
  crashed WebGL context leaves, which is how "it shows for a second and
  dies" became a bug report here. Readiness is now reported from INSIDE the
  Suspense boundary on the first frame that actually draws, and the
  placeholder is an outline of a pitch in the same place the real one lands,
  fading rather than cutting.
- 📊 **CORRECTION TO WHAT I TOLD THE USER.** I said the Elo arm scores worse
  than the shipped model at 1.039 against 1.034. The actual experiment
  (`experiment_elo_vs_shipped`, n=372) says **elo 1.0321, shipped 1.0326,
  blend 1.0292** — Elo is a hair BETTER and P(better) is **0.519**, a coin
  flip. The 1.039 figure was page copy from a different cut and I repeated
  it without checking.
- 📊 **THE DRAW-PICK NUMBERS ARE THE ONES THAT MATTER, and they are stark.**
  The product is four draw picks a week, so the metric is the top-picks hit
  rate, not log loss. On 25/26 (base rate 27.7%): **shipped top-40 picks hit
  15.0%, Elo 32.5%**, elo_clf 22.5%, blend 20.0%.
- ⚠️ **But read the direction correctly.** Tested against the base rate,
  Elo's 13 hits in 40 is unremarkable (p = 0.30) while the shipped model's 6
  is **significantly BAD (p = 0.047)**. The finding is not "Elo picks draws
  well" — it is "the shipped model ranks draws worse than chance", which is
  a different and more actionable problem.
- **So the Monday call is not switch-or-keep.** The headline probabilities
  are indistinguishable across all four arms and nothing justifies moving
  them. What needs deciding is which arm RANKS the draw picks, and Monday
  takes the top 40 to about 190, which settles it.

### Why the two models disagree, and a nav that ships (2026-09-20)

- 📊 **THE GAP BETWEEN THE HEADER AND THE PROJECTION IS SYSTEMATIC, AND IT IS
  THE GOALS.** User asked why Brighton–Arsenal reads 23/26/51 at the top and
  33/24/43 lower down. Measured across the whole live round: the Elo arm runs
  **+4.7pp on home, −3.5pp on draw**, −1.2pp away. The cause is not the
  ratings — it is that the Elo arm projects **3.03 goals a game against the
  shipped model's 2.57**, and higher lambdas make an exact tie less likely.
  The league scores about 2.75, so the truth sits between them and nearer the
  shipped model. Brighton's λ is 1.51 on the Elo arm against 0.87 shipped;
  that one number is the whole 10pp. Same `conv` constant that bit this
  project before, still running hot. Now stated on the page rather than left
  as an unexplained contradiction.
- 🐛 **I had the units wrong in my own caption.** `forecast.moved` is a sum of
  LAMBDA differences — expected goals — and I printed it as "×100 points of
  win probability". It read 0.078 goals out as "7.8 points", overstating the
  injury effect by two orders of magnitude on every fixture.
- **The projection panel redesigned**: three bars against a common baseline
  rather than a column of percentages, so it can be compared with the call at
  the top of the page by eye instead of by arithmetic. Retitled "a second
  opinion", which is what it is.
- 🐛 **Two maps of the same thing opened at different zooms.** The first
  arrival was an eased flight, so each canvas ran its own lerp at whatever
  frame rate it got while the page was still laying out — one could settle
  where its neighbour did not. Mount is now a CUT, deterministic and
  identical everywhere; flights are kept for moving between presets once
  somebody is looking.
- **Weight panels collapsed by default** (user, for a shippable site). It
  turned out to be one line: the disclosure already existed and the TEAMS
  board already opened shut — only the players board opened expanded, asking
  every first visitor to make nine decisions before seeing a single name.
  The feature survives, the argument survives, the barrier goes. Both
  toggles reworded to read as an invitation rather than a heading.
- **Nav cut to two products and a drawer.** Predictor and Ratings in the top
  row; How it works and What we rejected under More. **Fixture came out
  entirely** — it is not a destination, it is where a fixture from the
  predictor opens, and a nav item invited people to arrive with no fixture
  chosen, which is the emptiest version of the page.

### Match page, second pass (2026-09-20)

- 🐛 **"Why do I see 3?"** — on the first paint `home` and `away` are both
  `""`, so `[home, away].map` produced two panels keyed on the SAME empty
  string. React kept one alive when the real names arrived and the page
  showed three shot maps, one of them nameless. Nothing on the match page
  now paints until both clubs are known, and the keys are the club names.
- **Shots are a MATCHUP, not a toggle** (user). The tabbed version put "shots
  they face" behind a click, so comparing an attack with the defence it is
  about meant flipping states and holding the first in your head — the same
  mistake as one undirected pass line, where the information is present and
  the picture refuses to make the comparison. Now one row per phase: this
  side's attempts beside what the other concedes. Both halves drawn in the
  SHOOTER's frame, because "where do they get got at from" is a question
  about where the attacker stood.
- **All the visuals on the page are the lab's 3D ones.** "Where it is
  decided" is the zone tiles, not the flat maps; the elevens and the shot
  maps were already. `PitchZones` and its prose helper came out.
- **The elevens got their interactivity back.** Stripping the controls was
  wrong: a picture you cannot interrogate is a picture nobody trusts, and
  these are here to show the working. Slider and click-for-territory
  restored; only the side panel stays off, because two of them side by side
  would be four columns of text where the pictures should be. Links start at
  0.62 rather than the lab's 0.35 — eleven players make 110 directed pairs
  and nearly all exist, so the lab default is a cobweb at half the width.
- Match-page scenes have their own camera keys (`match-xi`, `match-zones`)
  defaulting to overhead, so they do not inherit the shot map's seat.
- **Pass maps side by side** (user), same treatment: the lab's `PassView`
  with the side panel off and the filters kept, because a club plays ~18,000
  passes a season and every one on screen is a carpet rather than a map —
  which subset you ask for IS the question. Opens on "led to a shot", about
  350 passes, legible at half the page width. `PassView` gained `compact`
  and a `scene` key so the match page does not inherit the lab's camera.
- ✅ Verified the live round can actually draw it: **20/20 fixture clubs have
  26/27 pass data** and the 26/27 shot file holds all 20 clubs, 1,277 shots.
- ⚠️ **I deleted `where` and `Shot` by accident** — a brace-matching script
  run over JSX consumed past the function it was meant to remove. They are
  reconstructed from their call sites and behave the same, but they are not
  byte-identical to what was there. Worth a look at the projection panel.
- ⚠️ **`web/app/versus/` is untracked, and so are 80 other paths** — the
  skill, the model, the kit config, every experiment report. None of this
  session's work is in git. That is the single biggest risk on the project
  right now and it is one `git add` away.

### Zone map round two, and the XI was wrong (2026-09-20)

- 🐛 **"The eleven who appeared most" is not a team.** User spotted it:
  Arsenal came out with Martinelli AND Trossard on the left and no
  left-back, because Calafiori rotated to 26 appearances and finished
  twelfth while both wingers made 30. Every shape drawn was a lie. The XI is
  now chosen by FILLING A SHAPE — each formation in `lib/bestXI` carries the
  Opta position of every slot, players are matched to slots by metres out of
  position plus a rotation penalty, and one slot can only be filled once.
  Calafiori is back in at left wing-back.
- 📊 **And the shape it picks says something true.** Arsenal fit 3-4-2-1
  better than 4-3-3 at every penalty setting, because their full-backs
  average **x = 53–55** — wing-back territory. That is not an error: average
  PASSING positions describe the in-possession shape, and a modern 4-3-3
  with Timber inverting and Calafiori pushing on genuinely IS a back three
  in build-up. Labelled as the in-possession shape rather than as the team
  sheet. Raising the rotation penalty to force 4-3-3 was tried and is worse
  — at 70 it puts Eze at centre-back.
- 🐛 **The smooth wash was not intuitive, and the reason is exact.** User:
  *"it isnt intuitve at all. not like the rest of the visuals. why?"*
  Because every other view puts OBJECTS on a pitch — balls, ribbons,
  figures — and that one REPLACED the pitch with a stain. Stripes, markings
  and boxes all went under it, taking every cue that made the rest read as
  football, and it left nothing to look at: no edges, no focus, no number.
  Rebuilt as fifteen inset tiles with the figure printed on each. The grass
  shows between them, clicking one is obvious, and it stops implying detail
  between cells that fifteen numbers never had.
- 🐛 **"Where they are got at" looked empty** — it was not, it was FLAT.
  Scaled 0 to the league's worst cell (2.19), a good side's own fifteen span
  0.39–0.57 of the ramp and come out one colour. Colour is now the club's
  own range and the league comparison is a number in the sidebar, which is
  the right division of labour: shape in the picture, precision in the
  figures.
- **Per-view default camera** (user). Each scene remembers which camera it
  opens on — a shot map wants to be behind the goal, a zone map above it —
  saved under its own key rather than hard-coded in every file as a string
  nobody could change.
- Third labels off the grass, so it is clear which way the side is playing;
  and the squad can be overlaid on the zone map as context, because a hot
  cell is a fact about a place and the eleven standing in it are the reason.
- 🐛 Caught in review: a shell-quoting accident wrote three **literal NUL
  bytes** into `useSquad.ts` as the pass-pair separator. It ran correctly —
  NUL is a fine separator — but an invisible control character in source is
  a hazard for diffs, editors and git. Replaced with the escape.

### Team zones as heat on the pitch (2026-09-20)

User: *"not the versus terrain u did, but team zones... i do think of it as
HEAT MAP on 3d pitch. u couldnt make a terrain like and i think nor should
we, keep it football pitch."* Agreed, and the skill's own gate says so:

- **THE THIRD DIMENSION CARRIES NOTHING HERE, deliberately.** A zone value
  is one number per place on the plane and colour on the plane is what that
  wants; the column version was built first and rejected on sight, because
  it turned a pitch into a bar chart in perspective and you could not see
  the pitch through it. What the 3D stage earns instead is CONTEXT — the
  goal and the box are right there, so "where they get got at" is read
  against the goal — and CONTINUITY with the shot and pass maps. Said out
  loud rather than dressed up as a 3D feature.
- **Smooth heat AND the cells still painted.** Fifteen flat rectangles is a
  spreadsheet laid on grass; interpolating fifteen numbers into a smooth
  surface looks like a heat map but silently claims resolution the data does
  not have. Doing both settles it — you can see exactly which fifteen
  numbers the colour came from. Interpolation runs between cell CENTRES at
  their real uneven spacing (wings 21% each, half-spaces 16, centre 26).
- **No new pipeline**: reads `z_{cell}_n` and `zoc_{cell}` straight out of
  `club_season.json`, the same careful measures the flat map already uses —
  share of the ball scored against a typical side IN THAT CELL, and chances
  that BEGAN there rather than where the shot was hit.
- 📊 **The ramp had to be square-rooted, and the data said so.** Chances
  conceded run a median of 0.42 against a league max of 2.19, and the top is
  not one outlier (the highest six are 1.77–2.19). Linear put the median
  cell at **19% of the colour range** and spent four fifths of it on a
  handful of cells; a square root moves it to **44%**, hides nothing and
  keeps every cell in order. Share of the ball is already a 0–100 score
  against the league and well spread, so it stays linear.
- Low values stay see-through rather than opaque: a green heat map over
  green grass is invisible at the bottom of the scale, and fixing that by
  making it solid buries the pitch it is supposed to sit on. Fading instead
  reads as "not much happens here" and keeps the markings visible.
- Sidebar gives the number, a plain-English reading, the cell's rank among
  the club's own fifteen AND its rank in the league for that cell — because
  a club's hottest cell can still be ordinary for the division.

### Kits in club colours (2026-09-20)

- `scripts/build_kits.py` reads every crest on disk and writes a shirt and
  shorts colour per club. Not "the commonest pixel" — a badge is mostly
  outline and background, so the modal colour of half the league is white.
  Ranked by **count weighted by saturation** instead, which asks which
  colour a club IS rather than which pixel is commonest. 96 clubs across
  five leagues, automatically.
- **A badge is not a kit**, so `data/config/kit_overrides.json` corrects the
  handful it cannot know: Spurs play white behind a navy crest, Leeds white
  behind a yellow one, City sky blue behind a navy one. Stable for years,
  one line each.
- 🐛 Only 19 of 20 EPL clubs came out: the same league is on disk under two
  spellings, `ENG-Premier League` and `ENG-Premier_League`, and the second
  holds exactly one club. Both are read and merged now — the kind of miss
  that otherwise shows up as one blank figure months later.
- 🐛 **Colour keys could not make the shirt PLAIN, and the atlas proved it.**
  Exported the base colour map and looked at it: hundreds of small UV
  islands butted together with no gutters, so neighbouring texels are as
  likely to be an elbow and a knee as two parts of one garment. That kills
  both the colour key (the same white is the stripes AND the socks) and any
  dilation trick (it would bleed across islands).
- **So the garment comes from GEOMETRY.** `scripts/build_kit_regions.py`
  rasterises every triangle into UV space carrying its height up the body,
  and ships the answer as a 22 KB indexed PNG — 0 leave, 1 shirt, 2 shorts,
  3 socks. Height says which garment, colour says garment-or-skin. The
  measurement is the whole argument, and two of four colours are bimodal:
  **white sits at 0.08–0.27 AND at 0.79** (socks, and the stripes across the
  chest); **dark at 0.01–0.06 AND at 0.49** (boots, and the shorts); yellow
  0.52–0.84; skin 0.30–0.98. Nothing but geometry separates those.
  Coverage 68% of the atlas; shirt 25%, shorts 15%, socks 7.9%.
- **Plain falls out of the shading rule.** The target is multiplied by the
  texel's own max channel, and a white stripe and the yellow around it both
  peak at 1.0 — so they land on the same colour and the stripe disappears,
  while folds and baked occlusion survive. Socks now take their own colour,
  defaulting to the shorts.
- 🐛 The optimise step moved the texture behind `EXT_texture_webp`, so
  `textures[i].source` is absent and the image hangs off the extension. Easy
  to miss, because every glTF written before WebP has `source`.
- Shading survives because the target colour is **multiplied** by the
  source's own value rather than replacing the pixel, so folds and baked
  occlusion come through. Shorts need their own curve: near-black has no
  range to scale, and multiplying any colour by 0.1 gives black.
- One repaint for the whole side, not one per player — the clones share a
  material, so it is eleven draw calls over one texture. `flipY` and colour
  space are copied from the source, since a glTF atlas is authored with
  flipY off and a CanvasTexture defaults to neither.

### Cameras belong to the user now (2026-09-20)

User: *"ALLOW ME TO SET THE CAMERAS DEFAULT!!! use only cameras i SET, add a
cameras tab."* Fair — every number in the seat tables was reasoned about by
someone looking at arithmetic instead of a pitch, which is how overhead
ended up upside down and every preset ended up too far out.

- `ViewName` is no longer a fixed union; a camera is `{name, pos, target}`
  and the list is user-defined per mode. Save over the current one, add a
  new one by name, delete, restore defaults. Defaults apply only until one
  camera is saved for that mode — after that the list is theirs and nothing
  else shows.
- **New lab tab `Cameras`** with a mode selector, because full, three-quarter
  and half are three different subjects and one seat cannot frame all three.
  Keyed on mode so switching rebuilds the canvas — the initial camera is a
  Canvas prop, not a live one.
- Saved to localStorage and read by EVERY scene, so a camera set in the lab
  is what the team page uses immediately. **Copy code** emits all three
  tables for pasting, which is what turns one browser's settings into
  everyone's.
- A name that no longer exists falls back to the first camera rather than
  leaving a scene with no seat, and deleting the last one restores defaults.

### Average positions in 3D — and why the flat one was answering nothing (2026-09-20)

Lab only for now; the user will judge it before it goes near the team page.

- 📊 **AN AVERAGE POSITION IS A PLACE NOBODY STOOD.** Measured before
  designing anything — the share of a player's actions within twelve metres
  of his own average position, Arsenal 25/26: **Raya 65%, Gabriel 31%,
  Saliba 28%, Timber 23%, Zubimendi 18%, Rice 15%, Martinelli 12%.** Only
  the goalkeeper is well described by a point. So a 3D version of the dot
  chart would be a scatter plot with extra steps, and the third dimension
  goes on the selected player's TERRITORY instead: a density surface, so you
  can see whether a man's node sits on a peak or in the valley between the
  two jobs he did. One player at a time — eleven mounds is mud.
- 📊 **Directed lanes, and the data says they are needed.** `{a, b, n}` was
  always directed in the payload and the flat chart draws one line per pair.
  Of 40 pairs with 25+ passes only 40% are within a quarter of even, and 12
  are lopsided past 1.6×: **Raya→Gyökeres 53 against 1**, Gabriel→Gyökeres
  32 against 3, Gyökeres→Rice 14 against 42, Raya→Rice 118 against 56. The
  high-volume centre-back pairs ARE symmetric (Gabriel/Saliba 330/327), so
  the top of the chart looked like the direction did not matter — it is the
  progression passes where it does, and one line calls a 53-to-1 relationship
  an exchange.
- **Derived entirely client-side from the pass payload.** Nodes, links and
  density all come out of the same rows in one pass, so no new pipeline and
  the three cannot disagree. Appearances come from distinct (opponent, home)
  — a fixture is uniquely identified inside a season — which reproduces the
  eleven-by-appearances rule without shipping another field. Cost: these are
  PASSING positions, about seven actions in ten, not every controlled touch
  like the flat chart. A narrower claim, stated in the caption.
- **Real player model wired, and cut 97% first.** The Sketchfab download was
  **22.8 MB — 195,928 triangles and four PNG textures worth 16 MB** — for
  figures that are thirty pixels tall from most seats, on a site whose whole
  build was 1.5 MB. `web/scripts/optimise-model.sh` (gltf-transform) gets it
  to **761 KB and 14,959 triangles** with 1024px WebP: `--compress false` on
  purpose, because meshopt needs a client decoder and the geometry was never
  the problem — the textures were 73% of the file. The SOURCE lives in
  `data/models/`, not `web/public/`, because anything under public/ is
  copied into the export referenced or not, which would have shipped the
  22 MB original next to the 761 KB one.
- **Scale is measured, never assumed**: models are authored in centimetres,
  inches or "1.0 = a person", so the bounding box is measured and the height
  set to 1.82m. `clone()` shares geometry and material, so eleven figures
  are eleven draw calls over ONE upload — which is also why selection shows
  on the base and the label rather than by tinting a figure, since
  recolouring one would recolour the side.
- **The solid puck is gone.** It was right when it WAS the player; under a
  figure it read as a game-character selection ring and the eye went to the
  slab instead of the man. Replaced by a soft contact shadow that fades out
  (a `RingGeometry` with radial segments, because a circle has one centre
  vertex and a vertex-alpha gradient across it is a straight cone) plus a
  thin ring at the radius. Still both the volume reading and the click
  target — a 1.8m figure is a small thing to hit on a 105m pitch.
- ⚠️ **CC-BY is unattributed so far.** `app/lib/credits.ts` holds the entry
  and the view prints a visible warning under the pitch whenever the model
  loads without a title, author and source URL, so it cannot quietly ship in
  breach. Still needed from the user.
- **Players are figures at human height, never scaled.** Sizing a person by
  involvement would wreck the one thing the arena exists for — flags,
  hoardings and pylons are there to give the eye known sizes, and a 2.6m
  Rice beside a 1.4m Gyökeres destroys all of it. Volume goes on the plinth,
  which is also the click target. Built from primitives so there is no fetch
  to suspend; a real `.glb` drops into `Figure` with nothing else changing.
  **Asset wanted from the user:** glb, ≤25k tris, static pose, licence that
  permits public use (CC-BY fine with an attribution line, NC not).

### Pass maps (2026-09-20)

- 🐛 **"I don't see the goal indicator any more" — and it was never the
  renderer.** Every one of Ødegaard's 22 shots had no goal-mouth point while
  Arsenal sat at 81%; one player at exactly 0% is the shape of a name
  mismatch. WhoScored spells him **Ødegaard**, Understat **Odegaard**, and
  `surname()` lowercased without normalising, so `"ødegaard" != "odegaard"`.
  Added a `fold()` that NFKD-decomposes and names the letters that have no
  decomposition at all (ø, đ, ł, ð, þ, ı, æ, œ, ß — separate letters in
  their own alphabets, not accented ones). **Placement coverage 25/26:
  81% → 97% of shots, 73% → 98% of goals.** Ødegaard 0/22 → 22/22.
- **`scripts/build_pass_web.py`** — every pass a club played, per club per
  season. 362,739 passes in EPL 25/26 (955 a match), 18,137 per club; as a
  flat integer array against key lists the biggest club is 859 KB, 245 KB
  gzipped. Raw streams stay gitignored; this is a derived view.
- **Frame checked, not assumed** (the skill's rule): shots average x = 85.7
  home and 85.8 away, clearances 14.5 and 14.3, corners x = 99.5 on both
  flanks — so every event is in the ACTING TEAM's attacking direction and
  `toX`/`toZ` apply unchanged. Confirmed again on the built payload: the
  first Arsenal pass of the season starts at scene (−0.1, 0.1), the centre
  spot, and goes backwards. A kickoff.
- **What the third dimension is spent on: whether the ball left the ground.**
  Opta flags Chipped / Longball / Cross / HeadPass, 23.7% of passes. A 40m
  ball along the floor and a 40m diagonal over the top are different actions
  that a flat map draws identically — so lofted passes arc (height ∝ length,
  capped at 8.5m) and ground passes stay down.
- **Ribbons, not lines.** `linewidth` is silently ignored on every platform
  that matters, so a line-based pass map is a cobweb that vanishes at any
  angle but straight down. One merged geometry, one draw call, per-vertex
  RGBA widening and brightening toward the target so direction reads without
  an arrowhead on every one of two thousand passes. Uniform segments per
  pass so a ray hit's `faceIndex` divides straight back to the pass index.
- **Receiver recovered, by inference** (user asked). `related_player_id` is
  set on 0% of passes, so the only route is the next event in the stream —
  measured, not hoped for: across 290,873 completed passes the next event is
  the same game, same team, different named player **99.1%** of the time,
  and is another Pass in 86% of those. The 0.9% lost are mostly an
  opponent's Challenge landing between the two. Sanity check on the built
  payload: Arsenal's top combinations are Gabriel↔Saliba at 330/327 —
  near-symmetric, which is the signature of a correct inference — then both
  centre-backs into Zubimendi and Rice. That is Arsenal's build-up.
  A real pass network falls out of this for free. Labelled as inferred in
  the UI; wrong where a deflection reaches a teammate, so it answers "where
  did the ball go", not "what was intended".
- **Aerial passes drop a shadow** (user). Straight down, not along the sun:
  a true shadow would sit four metres to one side at the top of a lofted
  ball and read as a second unrelated stroke. It still spreads and fades
  with height, so the flight can be read off the ground track alone — and
  ground passes get none, which is the signal. Separate geometry, out of
  raycasting, so a shadow is never the thing you clicked and the main mesh
  keeps uniform faces per pass for picking.
- ⚠️ **Assists are the INTENTIONAL subset.** `IntentionalGoalAssist` is 536
  against 1,045 goals; there is no plain `Assist` qualifier in this feed and
  `related_event_id` is set on 0% of passes, so a pass cannot be walked to
  the shot it created. Labelled as intentional rather than presented as all
  of them. `ShotAssist` (6,461 ≈ 69% of shots) is the solid one.
- 🐛 Fixed while building, and both were mine: the geometry was rebuilt every
  render (`sel ? [sel] : passes` outside the memo is a new array each time)
  and never disposed (`useMemo` returning a cleanup does not run one).
  Selection state in both views now carries the filter it was made under, so
  changing the filter drops it during render rather than in an effect —
  index 12 of "goals" is not index 12 of "big chances". `three/` now lints
  clean for the first time.

### The ground, not just the pitch (2026-09-20)

User: *"lets add some thing to make the pitch feel alive... something to
have depth here"*, then *"lights? like pratice arena?"*, then *"can we make
the grass as layer? it is now just color but no real texture."*

- **`Arena.tsx`** — hoardings, corner flags, dugouts + technical area,
  floodlight pylons. The point is not decoration: nothing in the old picture
  had a **known height**, so the scene flattened and could as easily have
  been a model on a table. A 1.5m flag, a 1m board, a 2.1m dugout and a 22m
  pylon give the eye four references it already knows. Sized against the
  DRAWN region, so half-pitch mode becomes a closed training arena rather
  than furniture floating past the edge of the grass.
- **`turf.tsx`** — grass generated on a canvas, not downloaded. One height
  field → a colour map and a **normal map** that agree with each other; the
  normal map is what makes the sun graze across the blades. Tiles seamlessly
  because the blades are written with wrapped indices.
- **Mowing stripes are now the real mechanism**: same grass rotated 180°, so
  one band returns the sun toward you and the next away. The stripes shift
  as the camera orbits — strong from the end, faint from the side — which is
  what they do in life. Band colours had to be pitched brighter: an 8-bit
  map can only darken what it multiplies.
- **New camera preset "from halfway"**, looking down the pitch at the goal
  (user request, for shot maps). The only seat with a direction in it, so
  seats became `{pos, target}` pairs rather than positions alone.
- **Camera tuner in the lab** (user: *"cause u cant see, let me set the
  default setting on my own"*). Fly the camera anywhere, press capture, and
  that becomes the seat for the current view AND mode. Saved to
  localStorage and read by **every** scene, so a seat tuned in the lab is
  immediately what the team and versus pages use; "copy code" emits the
  `FULL`/`HALF` literals so the tuning ends in a paste rather than living in
  one browser. The right answer to a loop where I cannot see the render.
- 🐛 **The grass repeated as an obvious grid.** 512px over a 5m tile is
  fourteen repeats across a pitch, and the colour map carried the
  low-frequency blotches — the only content coarse enough for the eye to
  match between tiles, so every repeat showed the same blotch in the same
  place. 1024 over 9m, and the patchiness moved almost entirely into the
  normals where it becomes lighting rather than pigment.
- 🐛 **Painted lines broke into dashes down the far end** — a depth-buffer
  precision problem, not antialiasing. `near: 0.1` with `far: 900` is a
  9000:1 range; at sixty metres one depth step was wider than the 1.2cm the
  paint sat above the turf, so which surface won was decided per pixel by
  rounding. Fixed with `near: 0.5`, a 3cm lift and `polygonOffset`.
- 🐛 Long dark streaks across the distance: the outer ground plane extends
  far beyond the shadow camera, where the lookup clamps to the border texel.
  It no longer receives shadows, and the hoardings no longer cast them.
- **Shot map moved from half a pitch to three quarters** (user: shots were
  being clipped). `half: boolean` became `portion: number` throughout —
  markings, goals, corner arcs and flags are drawn only when their end is
  actually on screen, and band count follows the length so a stripe stays
  ~10.5m whatever is displayed. Checked against the data first: of 9,524
  EPL 25/26 shots, **56 are behind halfway and 41 of those are own goals**,
  which Understat records at the SCORING side's own goal line — so they sit
  at the wrong end by construction and no amount of pitch places them.
  The furthest genuine attempt is z ≈ −21, comfortably inside 0.75.
- 🐛 Found while generalising: the half-pitch centre circle was drawn as
  `from 0 to π`, which after the ring's lay-flat rotation is the half
  BEHIND halfway — i.e. the half that is not there. It had been sitting on
  the run-off unnoticed.
- 🐛 **The wedge pointed at the wrong goal for own goals.** Understat files
  an own goal in the CONCEDING side's own shot list at their own goal line
  (Hincapié under Arsenal v Chelsea, x = 0.025, xG 0.000 on all 41). The
  target goal is now a property of the shot — `goalEndOf` — so the wedge,
  the distance, the angle, the goal-mouth ball and the shooter's-eye camera
  all measure to the goal the ball actually crossed, and the pitch extends
  to full when one is selected. Same switch is what a shots-faced panel
  beside shots-taken will need. **Open question for the user: own goals are
  goals the team CONCEDED, so arguably they belong only in the faced panel.**
- **Selection wedge is now graded, not flat.** A single opacity cannot work
  for a solid the camera sits inside: at the apex all three surfaces meet,
  so the value that looked right across the middle became a slab of neat
  colour exactly where the shooter's-eye camera stands. Per-vertex RGBA,
  0.04 at the ball opening to 0.22 at the mouth — reads as a beam thrown at
  the goal. (Alpha needs a FOUR-component colour attribute; three switches
  on `USE_COLOR_ALPHA` by itemSize and a 3-component one silently gives a
  uniform wedge back.)
- **Shot label is a dark chip edged in the outcome colour**, not shadowed
  white text. The old label hung in front of the wedge, which is painted in
  that same colour, and a soft dark shadow on a saturated field is no
  contrast at all — the name came out as a dark smudge on red.
- ✅ **Shot angle challenged by the user and verified correct.** Understat
  ships no angle or distance — only X, Y, xG, result, situation, shot type,
  player, assist — so both are ours, from `geometry()`. Checked against the
  closed form `2·atan(3.66/d)`: matches to two decimals at every distance
  (11m → 36.81°, 16.5m → 25.01°, 25m → 16.7°, 40m → 10.46°), and the edge
  cases hold (on the goal line 20m wide → 0.00°; 25m out but wide → 9.8°).
  The shot queried was Saka v Aston Villa 13' — 0.2m off centre, 25.2m,
  16.5°, xG 0.044. **Central and wide-angle are different things**: at 25m
  a 7.32m goal is a 16° slot, which is most of why the model gives it 0.04.
- 🐛 The distance label sat at the midpoint of the shot line — the same axis
  the ball's name chip and both default cameras are on — so it printed
  behind the name. Labels now go SIDEWAYS off the line rather than along it;
  angle on one side, distance on the other.
- **Orbit blocked below the ground** (user). I had argued the opposite —
  that constraining orbit protects readers from a problem they do not have —
  and was wrong: the turf, markings and run-off are single planes facing up,
  so from underneath they are not dark, they are ABSENT. Nets and hoardings
  floating over nothing. `maxPolarAngle` stops a hair short of a right angle
  so the camera never lands exactly level and leaves the grass one pixel
  thick. **The polar limit alone is not enough** — panning moves camera and
  target together, so a long downward drag walks both through the pitch at
  an unchanged angle; a frame clamp lifts the camera and the target by the
  same amount, which reads as the pan being undone. All fifteen presets and
  the shooter's-eye focus checked against the limit (worst is 82°).

## THREAD 1 of 4 — Player mental ranking ✅ SIGNED OFF (2026-09-17/18)

**Working rule (user, 2026-09-16): one thread at a time. Nothing else starts
until this one is signed off — "my eye will judge".** The agreed order is
(1) player mental ranking, ENG, all four seasons → (2) team mental ranking /
team zones → (3) roll out to the other leagues → (4) the predictor →
(5) visuals, which are NOT a tab: they become part of the match/player/team
pages. The Visualiser tab is agreed for removal, in thread 5.

### Position buckets — settled with the user, 2026-09-17

Nine buckets. Left and right POOL together (Mitoma is ranked against Salah);
side is a column and a filter, not a separate table.

    GK | FB (DR,DL) | CB (DC) | WB (DMR,DML) | DM (DMC) | CM (MC)
    AM (AMC) | WIDE (MR,ML,AMR,AML,FWR,FWL) | ST (FW)

- [x] **Roles read per MINUTE, not per match** (`services/mental/positions.py`).
      The `position` field only describes the opening XI. WhoScored's
      `formations` array carries a block per shape with minute ranges and a
      (horizontal, vertical) grid — horizontal 1 = RIGHT touchline, 9 = LEFT;
      vertical 0 = GK, 9 = centre-forward. The grid→Opta-code table is LEARNT
      from starting XIs and keyed by (shape, h, v): **100.00% of 16,720 slots
      resolve to one code**, so subs and mid-match switches can be labelled
      too. Validated: minutes reconcile to −0.06% vs the substitution-derived
      figures; side agrees with Opta's own code on **2,720/2,720** spells.
      Gotchas handled: 229 blocks have PERMUTED `formationSlots` (naive index
      alignment mislabels them), zero-length blocks when two subs share a
      minute, 241 blocks with 10 on the pitch (red cards).
- [x] Falls out free: **DCR vs DCL** (grid 3.5 vs 6.5, no coordinate
      inference needed) and the 3-4-2-1 double-"AMC" as one right- and one
      left-leaning inside forward — median gap 32.6 in mean-y, 84% of matches
      over 20. They are half-wide (Eze 68 vs a real left winger's 74), so
      they stay in **AM**, not WIDE.
- [x] Shape check the user called: wing-back XIs field **0.20** wide
      attackers, back-four XIs **1.92**; 90% of wing-back XIs field none at
      all, and push the creativity central instead (1.54 AMC vs 0.72). WB is
      therefore its own bucket, not folded into FB.
- [x] **Metrics split by role** (`services/mental/role_bank.py`). Rice's CM
      row is built from his 2,004 CM minutes only, his DM row from his 1,195
      DM minutes. **85 players qualified in 2+ buckets in 25/26** (Shaw FB
      54%/CB 46%, Bruno AM 54%/CM 46%, Bowen WIDE 85%/ST 15%), so a single
      row per player would have described the wrong footballer 85 times.
- [x] **The config = a per-bucket reliability gate** (`build_reliability.py`).
      Two tests per metric per bucket: `repeat` (season vs next season — is it
      a trait?) and `self` (odd vs even matches — can we measure it at all?).
      Several season pairs are STACKED, not averaged. Findings: `error_90`
      dead in all nine (−0.07 to 0.35); `giveaway_90`, built to replace it,
      repeats 0.67–0.82 in six; tackle SUCCESS rate is noise everywhere
      (−0.14 to 0.19) while tackle VOLUME holds 0.42–0.75; attacking-header
      win rate measurable ONLY for strikers (0.83). Presets were corrected
      to drop metrics the gate refuses for that bucket.
- [x] `MIN_FULL` set to 450, deliberately: at 900 three buckets return
      nothing. A noisier season estimate ATTENUATES rho, so the errors run
      toward refusing a real trait, never toward admitting a fake one.
- [x] Board rebuilt (`web/app/mental/MentalBoard.tsx`): config is a
      full-width SECTION (not a sidebar) that folds away, collapsible groups
      with subtotals, a hard **100-point weight budget** with over/under and
      "N ignored" indicators, a reliability dot per metric, side column,
      role-share column, and a season selector including **All seasons** —
      which pools the raw events of every season rather than averaging ranks.

### What "mental" means — four axes (user, 2026-09-17)

User's definition: **"how dependable the player is. does he do it good and
over time."** The board as built measures LEVEL only, which is why it read as
an intent-and-competing ranking. Four axes agreed:

1. **Level** — percentile on the weighted metrics. Built.
2. **Consistency** — his weighted score computed PER MATCH, then the share of
   matches at or above his bucket median. On the composite, not per metric,
   because a CB's one take-on a match cannot carry a hit rate. **Untested —
   next up, and now load-bearing.**
3. **Leverage / adversity** — ✗ **DEAD, see below.**
4. **Durability** — share of his team's available minutes + how steady his
   percentile is across seasons. Real once 23/24 lands.

### Shooting group added — it was simply missing (user caught it, 2026-09-17)

The bank had 41 metrics and not one of them was a shot; `accumulate()` did
not even look at a shot event. Nine added (`group: "shooting"`), penalties
excluded from every rate because they are converted four times in five and
would measure who the manager trusts from twelve yards. Gate results:

- **Shot SELECTION is one of the most stable traits in the bank.**
  `shot_box_pct` repeats at **0.81** for CB, 0.71 AM, 0.52 WIDE;
  `shot_dist` 0.76 CB, 0.74 AM. `shot_90` 0.71 DM, 0.64 FB/CM.
- **Finishing is not a trait.** `conversion_pct` 0.12 ST / 0.14 WIDE.
  `bigchance_conv_pct` for strikers is **−0.38** — negative, the man who
  buried them last season is if anything worse this season. Split-half says
  the same (−0.30), so it is not a measurement failure: there is nothing
  there. The "bottler" label does not survive contact with two seasons.
- Follow-on: `goal_90` repeats at only **0.20 for strikers**, because goals
  = shots × conversion and conversion is noise. A striker's shot selection
  predicts next season better than his goal tally does.
- For strikers the most repeatable shooting metric is `bigchance_shot_90`
  (0.54) — GETTING into big-chance positions is a habit, converting is not.
  Presets for AM/WIDE/ST rebuilt around that.

### ✗ NEGATIVE RESULT: behaviour under pressure is not measurable (2026-09-17)

- [x] **Leverage table built and KEPT** (`scripts/build_leverage.py` →
      `data/config/leverage.json`). 154,284 team-minutes. For every state
      (score diff, man diff, minutes left) the eventual result was recorded,
      giving `xpts`, then `leverage` = the move in xpts one goal would
      produce, rescaled so the average league event weighs 1.0. Level with
      5 min left = **2.25**, anything at 3-0 = **0.00**. Score DIFFERENCE,
      not scoreline: verified 0-0 / 1-1 / 2-2 are indistinguishable at
      matched time (1.25 / 1.27 / 1.33 xpts with 30 left).
- [x] Second table, **adversity** = 1 − xpts/3, because leverage is blind to
      red cards BY CONSTRUCTION: going a man down at 0-0 costs 0.35 xpts but
      barely changes the swing a goal produces. The two disagree — a goal
      down AND a man down with 30 left is leverage **0.72** / adversity
      **1.81**. Estimator note: the man effect must be fitted POOLED OVER
      TIME (n=577–1,135 per cell); cell-by-cell, 83 of 173 red-card cells
      fall under n=40 and the effect gets smoothed to nothing.
- [x] **Six pressure indices tested and REJECTED**
      (`scripts/experiment_pressure.py`): lev/adv × involvement, pass %,
      duel %. Cross-season: 34 measured, 1 over 0.40 (GK n=15 — a coin
      flip). Split-half within a season: 76 measured, 3 over 0.40 at
      n=22–30, scattered in sign. **It does not agree with ITSELF inside one
      season**, so there is no stable quantity to measure — a stronger
      result than cross-season failure, which could have meant "real but
      unstable". The spread was never there either: sd 0.02 on involvement,
      0.011 on passing, p10→p90 about 2%.
- Two structurally different attempts now agree: slicing ("while behind"
  ratios) gave 0.016, weighting gives the same nothing. Claim made: on these
  six measures, in this data, players do not differ measurably under
  pressure. Claim NOT made: that clutch does not exist in football.
- Consequence: the user's proposed tie-break for axis 2 vs axis 1 ("we'll
  know when he turns up") is unavailable. That call comes back to the user.
- The leverage table stays on disk — sound, and the team thread may want it
  for weighting match importance even though it cannot separate players.

### Axes: two of four survived, and the table is signed off (2026-09-18)

- [x] **Axis 1 Level** — the metric bank, 64 metrics, gated per bucket.
- [x] **Axis 4 Durability** — BOTH halves now:
      `availability_pct` (share of his club's minutes) plus a client-side
      FLOOR and SWING computed from the per-season views, with a "judge on
      his floor" slider blending the worst season into the ranking. Earns its
      place: the median player swings **28 percentile points** season to
      season and swing is near-independent of level (corr with mean −0.43 to
      +0.11), so it is new information rather than a restatement. van Dijk
      96/100/100 (swing 4), Saka 97/94/96 (4), Haaland 100/100/96 (4) against
      Elliot Anderson 86/75/40 (46) and Richarlison 94/98/73 (24).
- [x] ✗ **Axis 2 Consistency — REJECTED** (`scripts/build_consistency.py`).
      Per-match hit rate against the bucket median. It DOES repeat — 71% of
      212 measures at 0.40+, unlike the pressure axis — but it is a WORSE
      measure than the mean in **152 of 212** pairs (mean rho −0.141). Asking
      "did he clear the median this week" throws away by how much, and that
      was carrying the signal. Worst case `decisive_90` for CM: 0.80 as a
      mean, −0.08 as a hit rate, because decisive acts are rare so most weeks
      are a zero. Kept on disk, not shipped.
- [x] ✗ **Axis 3 Pressure — REJECTED**, see below.

### Score scale: re-percentiled (2026-09-18)

The raw composite is an average of percentiles, so its SIZE depends on how
many metrics carry weight, not on the player: the same centre-backs top out
at 79.4 on a five-metric config and 72.9 on a ten-metric one, with van Dijk
replacing Adarabioyo at the top. Reported as "honest, leave it" first — that
was wrong, the number reads absolute and is not. Now re-ranked within bucket
so 100 = the best player in that position on YOUR config, whatever its size,
with the underlying composite kept in the tooltip. Ceiling explanation: the
weighted metrics are mutually uncorrelated (mean pairwise +0.00, half the
pairs negative), so averaging k of them shrinks the spread by sqrt(k);
nobody is above the 80th percentile on more than 5-7 of 10-11 metrics.

**USER SIGNED OFF THE TABLE 2026-09-18** ("table looks good in my eyes").
Thread 1 closes when durability lands; thread 2 (team ranking) is next.

**Superseded:** test axis 2 (consistency) — same shape as what just
failed, so no better than even odds. Then axis 4. User's eye on the table.
23/24 arrives overnight (`PredictorEventPilot`, 01:00) plus the rest of
26/27 → then re-run `build_reliability.py` (try `--min-full 900`) and
`build_mental_web.py`. WB is thin at 8 players per season / 24 pooled.
`mental.json` is 5.2 MB.

## Done

- [x] Project revival spec written (`projectInfo.md`) — purpose, architecture, season handling, storage, output spec, stages
- [x] Zones system recovered from git history (full config @ `12f98ee`, service + prediction code @ `fc273d2`)
- [x] Scope decisions locked: backtest 24/25 + 25/26; all 5 leagues; no MW1 rush (target picks from ~MW3–4 of 2026/27)

## Stage 1 — Boot & hygiene ✅ (2026-08-07)

- [x] `core/config.py` boots without `.env` — Mongo/OpenAI/Admin fields now optional (legacy, unused)
- [x] Fixed `normalize_rank` NameError in `routes/plotting/plot.py` (now calls `TeamPlottingService.normalize_rank`)
- [x] Removed unreachable duplicate route in `routes/plotting/plot.py`; also `from openai import BaseModel` → `from pydantic import BaseModel` (drops openai dependency)
- [x] `/mental/vv/*` "shadowing" — **investigated, not a real bug** (4 path segments can't match the 3-segment team route); verified live: 200 OK. No change made.
- [x] `requirements.txt`: re-encoded UTF-16→UTF-8 AND rewritten from 100+-package global freeze to the 13 packages the code imports. `soccerdata` 1.8.6→**1.9.1** (1.8.6 doesn't support Python 3.13)
- [x] venv created (`.venv/`, Python 3.13 via `py` launcher) + deps installed
- [x] **Gate PASSED:** boots with no env vars; `/api/v2/leagues` → 5 leagues; mental dashboard 200 (~1MB payload); `/mental/vv/players` 200; fixed plot route 200; team stats 200

Notes: run server with repo root as CWD (`data/` paths are relative): `.venv\Scripts\python.exe main.py` → port 8080. Nothing committed to git yet (user's call when).

## Stage 2 — Fixtures & results ✅ (2026-08-07)

- [x] `services/fbref/fixtures/fixtures_service.py` — scrapes `read_schedule()`, normalizes rows (date, week, teams, parsed score, played flag, venue, referee, game_id), writes `data/fixtures/{league}/{season}.json`
- [x] `routes/fbref/fixtures/fixtures.py` — `POST /fixtures/{league}/{season}/build?refresh=`, `GET /fixtures/{league}/{season}?team=&played=&week=`, `GET /fixtures/{league}` (mounted in main.py under /api/v2)
- [x] `scripts/build_fixtures.py` — committed regeneration script (`--leagues --seasons --refresh`)
- [x] All 15 league-seasons built: 5 leagues × {2425, 2526, 2627}
- [x] **Gate PASSED:** EPL/La Liga/Serie A = 380 matches per season; Ligue 1/Bundesliga = 308 (306 + 2 relegation-playoff legs); 26/27 fixture lists on disk (0 played, as expected); spot-check: Liverpool 24/25 = P38 W25 D9 L4, 84 pts (matches real title record); Man Utd 1–0 Fulham opening match correct

Findings recorded:
- Outcome distributions confirm league rationale (24/25 + 25/26): Serie A draws 28.4%/26.1% (top), Ligue 1 home wins 46.4%/46.1%; nuance — EPL 25/26 drew 27.4% (above Serie A that season), La Liga 25/26 home wins 48.9% (league-highest). Pooled ranking by probability handles this naturally.
- Ligue 1 & Bundesliga files include 2 relegation-playoff legs (week is non-numeric for those); **stages 3–5 must filter to regular-season weeks only**.
- Ops note: fbref scrapes go through a Cloudflare-bypass (seleniumbase chromedriver, auto-downloaded on first run); full 15-file build ≈ 10–15 min; PowerShell background tasks with `*>` redirect misreport completion while python continues — use Bash watchers on output files instead.

## Stage 3 — Team stats + real xG ✅ (2026-08-07)

- [x] **CRITICAL FINDING: fbref lost its advanced data** (post data-provider change). Team & player tables reduced to `standard, keeper, shooting, playing_time, misc` — no xG, no defense/possession/passing/GCA tables. Legacy rich 24/25 data remains on disk (`data/league_init`, `data/players`) but is not reproducible for new seasons.
  - Verified 2026-08-07 after user challenge, at the value level: fbref's advanced pages still EXIST (full column skeletons, `data-stat` attrs present) but values are stripped retroactively for ALL seasons incl. 24/25. Structure-level probes are misleading — check values. `TeamStatsService` now also fetches the 6 advanced pages per league-season and keeps any non-null cells (auto-heals if fbref repopulates); NaN-filtering added so snapshots stay clean.
- [x] `services/fbref/team_stats/team_stats_service.py` — season aggregates for+against, snapshot-archived to `data/team_stats/{league}/{season}/{date}.json` + `latest.json`; 5 leagues × 2425+2526 built (20/18 teams each)
- [x] `services/understat/understat_service.py` — per-match real xG/npxG/PPDA/deep-completions/xPts, stored with fbref-normalized names at `data/understat/{league}/{season}.json`; 10 league-seasons built
- [x] Team-name mapping fbref↔Understat auto-learned via (date,score) voting (≥3 confirmations — naive learning got poisoned by Understat's stale dates for rescheduled matches) → `data/config/team_name_map.json` (committed, hand-editable)
- [x] Understat dates normalized to fbref fixture dates (Understat keeps originally-scheduled dates; join key = (home,away) pair, unique per season)
- [x] `scripts/build_team_data.py` — committed regeneration script (`--source fbref|understat|all`, `--refresh`)
- [x] **Gate PASSED:** aggregates on disk for all 10 league-seasons; Understat↔fbref join = **100.0%** on all 10 (requirement was ≥99%); zone-config coverage report at `data/reports/zone_stat_coverage.md`
- [x] Coverage verdict feeding Stage 4: **only 6 of 27 zone-config stat keys survive** (21 gone with fbref's advanced tables) → Stage 4 must redesign zone inputs around: fbref basics (Poss, SoT, Save%, TklW, Int, Crs, cards) + Understat per-match signals (xG, npxG, PPDA, deep completions) + player-level basics. The 12f98ee stat lists cannot be used as-is.

## Stage 3 addendum — shot events (2026-08-07)

- [x] Research confirmed (external sources): fbref lost Opta licence Jan 2026; no free like-for-like replacement exists; Understat = best free shot/xG source; Sofascore unofficial endpoints = possible v1.5 enrichment (dribbles, possession lost, box shots); WhoScored = full Opta events, brittle scraping, last resort.
- [x] `services/understat/shot_events_service.py` — per-shot x/y/xG/situation/**last_action** via Understat's `getMatchData` API (calls soccerdata's raw `_read_match`; the public reader drops lastAction). Incremental + resumable (per-match JSON cache + checkpoint saves every 50). Output: `data/understat/{league}/shots/{season}.json`, fbref-normalized names.
- [x] `scripts/build_shot_events.py` — committed backfill script; validated on 3 matches (last_action populated: Pass/Cross/Aerial/TakeOn/BallRecovery...)
- [ ] **25/26 backfill running** (detached process, ~1,750 matches ≈ 1h; log: `data/reports/shot_backfill_2526.log`) — verify counts when done
- [ ] 24/25 shot backfill: deferred — run overnight only if Stage 5 backtest shows early-25/26 weeks need prior-season zone profiles
- Zone diet locked for Stage 4: shot-location profiles + creation types (last_action) + punished turnovers + PPDA/deep + fbref basics + Understat player metrics

## Frontend (decided 2026-08-07)

- [x] **Decision: Option A** — dashboard served by this FastAPI app via Jinja2 templates (+ htmx/vanilla JS). No Flask, no separate client. v1 pages: weekly picks dashboard, graded ledger/history, zone-matchup detail per pick. Build lands after Stage 6 API exists.
- Note: when the predictor is ready, this repo will be **re-initialized as a fresh repo under a new project name** (user decision 2026-08-07).

## Stage 4 — Zones engine v2 (in progress, 2026-08-07)

- [x] `models/zones/zones_config.py` — skeleton restored from 12f98ee/fc273d2 (15 zones, position weights, matchups, importance, fallback map) + v2 signal defs (5-lane geometry for shot mapping, creation-action groups, turnover actions)
- [x] `services/zones/zones_engine.py` — rolling time-decayed window (default 38 matches, decay 0.985/match); att zones = lane xG production; def zones = mirrored-lane xG concession + punished-turnover pain (×1.5); mid zones = PPDA + deep-completion diff + cross-shot wide signal; fbref basics as small def modifier; league-percentile normalize + band-weight blend; persists `data/zones/{league}/{season}/{date}.json`
- [x] Code-path verified on partial data (20 teams, 15 zones each)
- [x] 25/26 shot backfill COMPLETE: 1,752 matches, 0 errors, all 5 leagues (`data/understat/*/shots/2526.json`)
- [x] **Sanity gate PASSED** (`scripts/report_zones_sanity.py` -> `data/reports/zones_sanity.md`): attack zones vs goals scored ρ=0.68–0.97; defense zones vs xGA ρ=0.98–0.99 (consistency); defense vs raw GA at/near its natural ceiling corr(xGA,GA) in every league; no dead zones; clean name joins. Two fixes from gate iterations: (1) dropped fbref TklW+Int "basics" from def band — correlates POSITIVELY with goals conceded (volume ≠ quality); (2) LANE_SHRINKAGE=0.35 anchors low-volume wide lanes toward overall team quality (unshrunk they ranked on noise).
- [x] MatchPredictionService v2 (`services/zones/match_prediction_service.py`) — zone matchups -> xG pair + advantage labels; constants deliberately uncalibrated (Stage 5 fits delta_coef/global_mult/base_xg; current raw outputs are meaningless magnitudes by design)
- [x] Understat player season stats stored for all 10 league-seasons (`data/understat/{league}/players/{season}.json`, ~5,500 players: xg, npxg, xa, key_passes, xg_chain, xg_buildup)
- [ ] Stage 4b: players component (needs 25/26 player scrape w/ surviving basics + Understat player xG metrics; band weights renormalize without it meanwhile)
- ⚠️ **HAZARD**: `FBRefPlayerService` writes `data/players/{league}/{team}.json` with NO season in the path — running a 25/26 player build would OVERWRITE the irreplaceable rich 24/25 player data (fbref no longer serves it). Make paths season-aware + migrate existing files BEFORE any new player scrape.

## Stage 5 — Probability layer + calibration + backtest (2026-08-07) — SPLIT VERDICT

Built:
- [x] `services/predictions/probability_service.py` — Poisson score grid + Dixon-Coles correction (rho param), outcome probs, top scorelines
- [x] `services/predictions/form_model.py` — walk-forward multiplicative xG strengths (decay 0.985, window 38, min 5 matches else league-avg priors + low-confidence flag)
- [x] `scripts/calibrate_model.py` — fit per-league home/away boosts + global rho on 24/25 walk-forward → `data/config/model_params.json`. Result: log-loss 0.979; rho=0 (DC correction unneeded on xG lambdas); home/away boost ratio ranks Ligue 1 highest home edge (1.30×) — user's league thesis recovered independently
- [x] `scripts/backtest_2526.py` — frozen-params walk-forward eval on 25/26 + pick simulation → `data/reports/backtest_2526.md` + full pick log json
- [x] `services/predictions/draw_model.py` — logistic draw classifier (8 features incl. rolling draw tendency, tempo, PPDA); trained on 4 seasons (21/22–24/25, n=6,180; extra Understat seasons backfilled for this)
- [x] Zone-evenness draw ranker experiment (walk-forward within 25/26)

**Gate results (25/26 out-of-sample, 38 weeks):**
- Overall model: log-loss 0.996 vs 1.074 base-rate predictor — real skill
- **HOME WINS: PASS.** Top-3 (EPL+Ligue 1): **67.5% hit rate vs 43.8% base (+23.8pp)**, well calibrated (predicted 66.5%), 11/38 perfect weeks
- **DRAWS: NO EDGE FOUND.** Top-4 (EPL+Serie A): Poisson-ranked 23.7%, classifier-ranked 27.0%, zone-evenness 27.4% — all ≈ base 26.4%; apparent per-rank effects are n=38 noise; Poisson P(draw) miscalibrated (inverted) in its top band. Consistent with the known hardness of draw prediction absent odds data.
- [x] **DECISION (user, 2026-08-07)**: draws SHIP as core product alongside home wins — draws are where the value is for the user. **Odds ingestion is OUT OF SCOPE permanently — user handles the odds/value side themselves; not our business.** Stage 6 ships both pick types: draws ranked by the 4-season classifier (best of the tested rankers), with zone-matchup breakdowns and honest probabilities attached; ledger grades both live.

## Stage 6 — Pick selector, API, ledger, run_weekly ✅ (2026-08-07)

- [x] `services/predictions/prediction_service.py` — upcoming-fixture predictions (form model on 2526+2627 history, preseason-tolerant), draw picks ranked by classifier (Poisson fallback), home picks by P(home); zone-matchup "why" from 2526 shot data (`ZONES_SOURCE_SEASON` switches to 2627 as it accrues); promoted/low-history teams excluded from picks via confidence flag
- [x] `services/predictions/ledger_service.py` — append-only `data/ledger/picks.jsonl`; commit is idempotent per (season, week, pick_type); grading fills outcomes from fixtures; summary computes live hit rates
- [x] `routes/predictions/predictions.py` under `/api/v2/predictions`: GET `/upcoming` (preview), POST `/commit`, POST `/grade`, GET `/ledger` — mounted in main.py
- [x] `scripts/run_weekly.py` — refresh (fixtures/understat/shots, non-fatal preseason) → grade → generate → commit → print picks
- [x] **Gate PASSED:** one command produced and committed the first real 2026/27 MW1 picks (4 draws: Parma-Cagliari, Bologna-Lazio, Everton-Palace, Forest-Leeds; 3 home wins: PSG 76%, Lens 69%, Man City 55%); API verified live (200s); double-commit correctly refused (added 0, skipped 7)

**v1 PIPELINE COMPLETE — stages 1–6 all gates passed.** Remaining before season: weekly run habit (manual or scheduled), frontend dashboard (Option A), repo re-init under new name.

## Frontend dashboard ✅ (2026-08-07)

- [x] Jinja2 + static CSS served by the FastAPI app (Option A; `jinja2` added to requirements). No JS frameworks; 10-min in-process cache on predictions.
- [x] `/dashboard` — this week's draw + home-win pick tables (probability meters, xG, confidence badges) + full per-league fixture probability tables with likely scorelines
- [x] `/dashboard/ledger` — hit-rate stat tiles per pick type + full graded/pending pick table (✓ HIT / ✗ MISS with icons — never color alone)
- [x] `/dashboard/match?league=&home=&away=` — 15-zone pitch matchup grid (home attacking left→right; each cell = home zone rating vs away mirrored-zone rating, CVD-safe blue↔red diverging tints with numeric Δ labels in every cell), plus probability/xG tiles
- [x] Verified live: all pages 200; PSG v Rennes grid shows 13 strong-advantage zones consistent with its 76% home probability
- Files: `templates/{base,picks,ledger,match}.html`, `static/style.css`, `routes/dashboard/dashboard.py`
- [x] Refinement (2026-08-08, user feedback): "likely scores" column showed the unconditional modal scoreline — reads as "everything 1-1" for even fixtures (mathematically right, perceptually wrong). Now shows most likely score **per outcome** (`modal_scores_by_outcome` in probability_service): `H 2-1 · D 1-1 · A 1-2`.
- [x] Refinement (2026-08-08, user feedback): three separate H/D/A % columns replaced with a **stacked probability bar** per fixture (blue home | gray draw | red away, favored segment saturated, % labels beneath with favorite bolded) — match tilt readable at a glance; even-bar rows = draw-ish fixtures.

## Improvement round (2026-08-08, in progress)

- [x] Mental permanently dropped (can't scale post-fbref) — player quality via Understat instead
- [x] **Stage 4b player layer LIVE**: `services/zones/player_layer.py` — per-team att/mid band quality from Understat player stats (npxG/90+xA/90 forwards; xGChain/90 mids; minutes-weighted, ≥450 min; position letters parsed from Understat strings). Wired into ZonesEngine (att 45% / mid 30% weights); def stays team-only (no defensive player metric exists in source). Sanity gate re-run: attack correlations improved (EPL 0.89→0.92, La Liga 0.68→0.73, Bundesliga +0.02), all leagues still pass. `include_players=False` flag reserved for walk-forward-clean calibration (player season stats are season-cumulative).
- [x] Zones page redesigned: real pitch look (field surface, halfway line, center circle, boxes), lane labels in cells, big Δ, component tooltips, att/mid/def band-summary table, per-1,000-matches sim framing on probability tiles
- [x] **Backtest page** added to dashboard (`/dashboard/backtest`): all 38 weeks of 25/26 picks with HIT/MISS, real xG, summary tiles
- [x] Accuracy numbers computed (user question): **overall outcome accuracy 51.9%** (876/1687; random 33%, always-home 44%, bookie-grade ~53-55%); stable 49–53% per league; exact modal scoreline 10.5% (normal for score prediction); product picks: home 2-of-3/week, draws ~1-of-4
- [x] 2425 shot backfill COMPLETE (1,750/1,752 matches; 2 Bundesliga pages failed — negligible)
- [x] **Zone-blend calibration DONE** (`scripts/calibrate_zone_blend.py` → `data/config/zone_blend.json`): λ_final = λ_form·exp(γ·zone_adv_std); γ fit on 24/25 walk-forward = **0.02 (tiny)**; frozen eval on 25/26: log-loss 1.00145 → 1.00114 (−0.0003). Verdict KEEP (doesn't degrade) and wired into prediction_service — but the honest finding: **zone matchups are predictively redundant with xG form** (built from the same shots). The lambda compression is TRUTH, not a bug — backtest calibration (predicted 66.5% vs actual 67.5%) proves wider spreads would be overconfidence. Zones' real value = explanation layer + zones-page product.
- [x] Final pre-season ledger reset (model evolved: context-retrained classifier + blend): MW1 draws now Parma-Cagliari 32.5%, Bologna-Lazio 32.4%, Everton-Palace 31.9%, **Nice-Lorient 31.3%**; homes PSG 77.6%, Lens 70.6%, City 55.6%; trixy 38.4% / 10.0% / **1.05%**

- [x] Backtest report + dashboard page regenerated under the SHIPPING config (user catch: page still showed 2-league pool): 5-league classifier-ranked draws = **28.9% vs pooled base 24.8% (+4.1pp)** — biggest draw edge measured, classifier beats Poisson ranking by +3.9pp at pool scale; ≥2/4 in 11 weeks, 3/4 ×2, 4/4 ×1; homes unchanged 67.5%. Backtest script now imports pool constants from prediction_service (single source of truth).

- [x] **Top-8 draw candidates view** (user request after trixy economics session): picks page now shows 8 ranked candidates — ranks 1-4 badged "ticket" (official, ledger-graded), 5-8 "alt" for price-based swaps — each with its **breakeven odds** (1/p) column so a line is takeable only when offered odds exceed it. Trixy tiles remain top-4-based. Strategy conclusions recorded: targets reset to reality (6 bonanzas/season impossible — needs 76% picks; sport ceiling ~32%), 26/27 = validation season, system EV swings −27%..+9% across the user's 2.65–3.15 odds band with the 4/4 week carrying ~40% of returns.

## Zones v3.5: functional midfield (2026-09-11, user challenge)

- [x] User challenged the single-midfield collapse. Truth defended: v2's five mid LANES were fake (all fed by team-level signals → provably identical per team; no free data resolves midfield laterally). Structure restored the honest way — **midfield split by FUNCTION: midProgress (deep completions for) / midPress (PPDA + turnover→shot xG won ×3) / midShield (deep allowed + turnover→shot xG gifted, inverted)**. Matchups: progression↔their screen, press↔their build-up, screen↔their build-up. 9 zones total.
- [x] Verified: gate PASSED; mid zones now genuinely differentiate (Lorient 35/15/52 — progresses OK, presses poorly, screens decently; PSG 100/100/96). Battle map center = 3 stacked duel pills (e.g. "press v their build-up · Δ -29.4 (15 v 44)"). Zone-blend recalibration for 9-zone scale running.
- [x] **Zone-blend recalibration on the 9-zone scale: KEEP** — fit 24/25 best gamma=0.02 (log-loss 0.97847 vs 0.97870 at 0), frozen 25/26 eval blended 1.00092 beats form-only 1.00145 (Δ −0.00053, n=1368) → `data/config/zone_blend.json` rewritten.
- [x] **Match-page fix pass (user bug report + screenshot)**: (1) band table scoped `table.bands` — compact width, numbers centred under centred headers (was full-width, right-aligned cells under centred heads); (2) overlapping absolute mid pills replaced — **midfield is now a real strip on the pitch**: battle map became a 3-column grid (flank | midfield | flank) with a dashed translucent "MIDFIELD" band and 3 cards in it: *home on the ball* (build-up v their press & screen), *midfield overall* (band verdict), *away on the ball*. Phase delta = build-up − mean(press, screen); wording "X will play through / edge on the ball / smothers their build-up". Verified Lorient-Toulouse: 35 v 36·44 even; overall 34 v 41.5 shared; Toulouse 44 v 15·52 = "Toulouse edge on the ball" (Lorient's 15th-pct press is the story).
- [x] **Auto "Bottom line" paragraph on every match page** (user request, modeled on a hand-written example): `_bottom_line()` composes plain-football prose from the same signals — midfield verdict with the WHY (band gap ≥10 = "should control midfield"; else on-ball phase asymmetry = "should have more of the ball"; cause clause picks opponent-won't-press / build-up-plays-through / wins-it-back-high), attack quality (blunt/mediocre/dangerous/outguns), flank danger spot (duel Δ≥25), finishing hot/cold from shot events, and the model lean (draw ≥30% = "profile of a draw candidate", fav ≥55%). Verified 3 branches: Lorient-Toulouse reproduces the example ("Toulouse should have more of the ball (41.5 v 34.0) — not because they're good, but because Lorient won't press them (press 15)... draw candidate (32%)"); PSG-Lorient dominance ("control midfield (98.7 v 34.0) — their build-up (100) should play through... danger spot PSG down their left (Δ+56.2)"); Hoffenheim-Stuttgart shared ("Two dangerous attacks, no midfield dominance either way, Stuttgart finishing hot").
- [x] **Shot maps shipped** (user request): 4 SVG half-pitch maps per match page (each team: shots taken / shots conceded, 26/27 season-to-date) rendered server-side from stored shot events — no JS libs, no new scraping. True 68×52.5m aspect (viewBox 272×210), goal at top, shooter's-left = screen-left (matches battle-map lane orientation), dot size = xG, gold = goal / blue = on target / gray = off, hover tooltip "player minute′ · xG · outcome", own goals excluded (coords describe the defender). `_team_shots()` cached per league. Verified Lorient-Toulouse: 4 maps, 169 dots, 11 goals with correct tooltips.
- [x] **WHOSCORED EVENT PILOT — verified and armed for tonight (2026-09-16)**: `scripts/build_whoscored_events.py` + `scripts/run_event_pilot.cmd`, one-off scheduled task **PredictorEventPilot at 01:00 on 2026-09-17** (EPL 24/25 + 25/26). Validated on a live daytime batch before trusting it unattended: **1,534 events/match, 37 event types, 30 columns**, player_id on 99%, coords on 100%, `goal_mouth_z` present (3D trajectories), cards present (man-count state). **Nothing is filtered — the full stream is stored.** Types include the ones that fill our worst holes: **Error** (explicit mistake attribution — dead on fbref since the Opta loss, alive here), **Challenge** (being beaten by a dribbler = the defensive mirror of TakeOn), **Dispossessed** (with coords), **FormationChange + Substitution** (in-match management, so a slice of the managerial edge is computable WITHOUT tenure data), KeeperSweeper/Claim/Punch/Smother (real GK actions, not the save% proxy). Speed is **10.6s/match, not the 29s first measured** (that sample was inflated by schedule-fetch overhead) → ~1h per season, ~2¼h for both. Parquet compresses to **~18 MB/season** (not the 338 MB projected from raw). Resumability proven by killing a run mid-flight: parquet intact, re-run reports "370 to fetch" and re-requests nothing. Politeness: each match fetched exactly once, batches of 10 with a pause, off-peak. Raw streams gitignored, never published — only derived metrics leave the machine. Ops caveats: laptop must stay on AC (sleep is never on AC, **10 min on battery**) and logged in (drives a real Chrome window).
- [x] **PUBLIC CLIENT BUILT — Next.js static site (2026-09-16, user: "one backend one repo, 1 client")**: `web/` — Next 16 / React 19 / Tailwind 4 / TypeScript / pnpm, `output: "export"` so `pnpm build` emits a **1.5 MB out/ folder** deployable to any static host: the Python pipeline writes JSON (`scripts/export_web.py` → data/web/), the client reads it at build time, **no server in production**. The FastAPI desktop app is untouched and stays the private betting tool. Three products + How it works in the nav. Typography: **Prosto One** (display/identity), **Montserrat** (everything read), **Genos** (held for the 3D viz) — self-hosted by next/font. Caught a real bug: naming the font variables `--font-display`/`--font-body` collided with the Tailwind theme tokens and produced a self-referencing CSS cycle that would have silently dropped the display face; renamed to `--ff-*` and verified in the compiled CSS. Windows pnpm snags fixed in committed config (`node-linker=hoisted`, `allowBuilds` in pnpm-workspace.yaml).
- [x] **PREDICTOR PAGE — three tabs, crests, clearer odds, per-league drill-down (2026-09-16, user feedback)**: Next round / Projected tables / Track record as sub-tabs (the stat bar moved off fixtures into the record where it belongs). Fixtures table gained column headers, padding, league+club crests, and **each 1/X/2 column now shows the percentage with its fair price directly beneath**, called outcome shaded — instead of two separate runs of numbers the reader had to align. Track record's competition cards are now **links to a per-league history** (`/predictor/history/[league]`, generateStaticParams so all five prerender): kickoff, fixture, H/D/A with the call bold, our scoreline, real result, our xG v real xG, verdict (called it / missed / exact score), pending rows included.
- [x] **PROJECTED TABLES — real per-league zones (2026-09-16, user: "every league has its own european places, relegation")**: fixed a real modelling error — the sim treated "bottom 3" as relegation for ALL leagues, but the 18-team leagues have a **play-off at 16th**. Simulator now exports each club's **full finishing distribution**, so zone questions are answered from `data/config/league_zones.json` (editable when allocations change) rather than from assumptions in code. Ligue 1 has its own shape (UCL 1-3, UCL-qualifying 4th, UEL 5, UECL 6, play-off 16, rel 17-18) and Angers now reads **16.6% play-off / 44.2% relegation** instead of one blurred number. Each row gained a **stacked outlook bar** (every simulated finish coloured by what that position wins or costs), Europe/Danger columns, and a "playing for" chip (Champions League 98% · Chasing Europe 65% · Fighting relegation 79%).
- [x] **"HOW IT WORKS" PAGE + target architecture on the record (2026-09-16)**: `/how-it-works`, split **Running today** (six stages shots→published call, the gate with one pass and one rejection, the limits) vs **Being built** (flow diagram + eight design-rule cards). Target architecture agreed with the user and recorded before the pilot: every event → **stamped with state at that minute (level/behind/ahead/a man down/late)** → PLAYER RANKING → **TEAM ZONES COMPUTE** (a zone is the players who occupy it) → team v team stats + **managerial edge (ranked from his own history, not inferred as a residual)** → predictor. Rules recorded: **controlled, not touched** (touches include deflections/miscontrols); intent reported as attempt rate AND success rate separately (attempts alone crown the wasteful); game state measured per minute-in-state against the player's OWN baseline (weak teams are behind constantly — raw "performance while losing" rewards being bad); **zone contributions fitted, not assumed** (the hand-set importance weights were an attribution workaround, but a flat sum is an equal guess — fitted channels came out +0.095 vs −0.03); **zones/mental fitted on the chance-quality baseline's RESIDUAL** so redundancy is excluded by arithmetic; opponent-adjusted with minimum samples. Confirmed the existing engine already does attack-vs-CONCEDED matchups with mirrored lanes (`_MIRROR_LANE`) — the user's "versus stats" instinct is the current design, events just raise its resolution from ~12 shots to ~1,431 actions.
- [x] **SIM OVER-CONFIDENCE FIXED — strength uncertainty added (2026-09-16, user: "champion probability isnt spread enough... find out why this is soo aggresive")**: user was right. The sim sampled outcomes from FIXED probabilities, modelling the randomness of RESULTS while treating our estimate of team STRENGTH as perfect truth. Measured it (scripts/experiment_title_spread.py, 25/26 projected from after GW4, n=96 teams): internal SD of final points **6.85** vs the actual RMSE of those projections **9.94** — the sim was **1.45x too confident**, unbiased (+0.14) but far too narrow. Real drift is huge: Nice projected 56.1 -> finished 32, Man Utd 48.4 -> 71, Liverpool 78.2 -> 60. FIX: each simulated season now draws a per-team strength error (STRENGTH_SD=0.53 log-odds, calibrated so simulated points SD = 9.82 vs the 9.94 target) which shifts the balance of every match that team plays, adding the CORRELATION across a team's fixtures that independent sampling lacked. Crucially the noise is **recentred per fixture** (`_recentred_ratio`, Gauss-Hermite + bisection): raw perturbation shrinks extremes toward 50/50 by Jensen (favourites lost ~1.7pp), which would have quietly contradicted the calibration the model is validated on — after recentring marginals hold to +/-0.001 and GOLD still reads 64.4% simulated vs 64.3% expected, P(profit) 49.7% at breakeven (EV-zero intact). Effect on the title race: **Arsenal 69.4 -> 58.6%**, City 28.6 -> 31.4%, Liverpool 0.4 -> 2.3%, Man Utd 0.7 -> 1.9%; top-4 spread widened (Man Utd 36 -> 58%, Chelsea 31 -> 51%) and relegation too (Spurs 30.4%). Simulator also now exports sd_pts per team.
- [x] **Full-season Monte Carlo simulation (2026-09-15, user: "run simulation for entire season")**: `scripts/simulate_season.py` — every one of the 1,558 remaining 26/27 fixtures priced by the live predictor (unified classifier-calibrated triplets, ratings frozen as of today), 10,000 season replays per league (vectorized numpy; runs <1 min), banked points from the 205 played matches, GD tiebreak with simplified win margins → `data/reports/season_sim_2627.json` (xPts, title/top-4/relegation %, median position; probability sums verified 100/400/300). Headlines: **Arsenal 69% title** (City 29%), **Barcelona 75%** (Real 25%), **Inter 66%** (Juve 12/Roma 13), **Bayern 79%**, **PSG 62%** despite 5 pts. Bold calls: Como 85% top-4; Man Utd 3rd on xPts (53% top-4); **Tottenham 36% relegation** (2 pts from 5); promoted Coventry/Málaga/Parma/Paderborn/Angers anchor the drop zones. Honest caveats in the report: no squad-evolution/injuries/transfers, far-future fixtures use today's ratings.
- [x] **Season sim ON the Table page + predicted scores (2026-09-15, user: "add projected to table... we want to see the scores it predicted")**: sim JSON now carries, per remaining fixture, the predictor's scoreline call (modal score of the argmax outcome — avoids the misleading unconditional 1-1) + probability triplet + xG; Table page renders per league (below the fair table): **Projected finish** (Now/xPts/Title/Top4/Releg., ≥20% title bold, ≥30% releg. red, <0.1% shown as —) and **Predicted scores** — every remaining round as a collapsible block (nearest round open), rows "Brentford **2-1** Chelsea · 1 · 38·30·31" with full tooltip (triplet, modal-score prob, xG). 1,558 calls: 971 home / 575 away / 12 draw (argmax-draw rarity law visible). `run_weekly` regenerates the sim daily (non-fatal step before backup) so the page tracks the season. Hit-rate question answered from history (first-prediction-stands, n=194 graded): outcome hit **51.0%** overall vs 47.4% avg stated confidence & 39.7% always-home baseline — Serie A 60.0%, Bundesliga 55.6%, La Liga 49.0%, EPL 47.5%, Ligue 1 44.4%; exact score 10.8% (Serie A 20.0%).
- [x] **Projection toggle + next-round-only scores (2026-09-15, user screenshot feedback)**: projected finish is no longer a separate table — a Table ⇄ Projected pill switch ON each league table (tiny vanilla JS, hidden attr); predicted scores trimmed to the NEXT round only, placed in the empty space under Players-to-watch (compact card: date · Home **2-1** Away · call chip · 38·30·31 triplet, full tooltip).
- [x] **DRAW-CALL RULE — the model's stated call now says draw (2026-09-15, user: "not counting draws is just wrong representation of football")**: pure argmax called draw 12/1,558 (0.8%) vs football's ~26% reality because draws cap at ~32-35% while win sides spread. New shared rule `call_outcome()` in probability_service: **call = draw once calibrated P(draw) ≥ DRAW_CALL_MIN=0.32** (the validated draw-ceiling zone), else argmax. Threshold picked by sweep on the 194 graded live rows: 0.32 costs **0.0pp accuracy (51.0%→51.0%)**, its draw calls hit 34.9% vs 26.8% base rate (precision above base = informative); 0.30 would cost 6.2pp. One source of truth: predict_fixtures now emits `call`; season sim (115/1,558 draw calls now, Spurs-Villa 32/33/35 → ✕ 1-1), match-page hero, and FUTURE history recordings all use it (old rows stand as recorded — first-prediction-stands; history explainer + X-call badge updated). Betting pipeline untouched (draw PICKS were always the ~32% pool; this is the representation layer).
- [x] **DRAW_CALL_MIN=0.32 CONFIRMED by big-sample sweep (2026-09-15, user: "should we change the threshold?")**: re-swept on the 25/26 GW5+ replay (n=1,560, shipping config): 0.32 is **+0.13pp vs pure argmax** (the free point on BOTH samples; live n=194 was ±0.0), 0.31 costs −0.51pp for 11.2% draw share, 0.30 −1.28pp for 17.4%, 0.29 −2.12pp for 26.0% (football-rate representation buys 2pp of wrongness); precision peaks in the 0.32-0.33 zone (31.7%/36.4% vs 26.1% base). DECISION: keep 0.32 — the page states the model's honest best call, it does not cosplay the league's draw frequency.
- [x] **GOLD betting model inside the season simulator (2026-09-15, user request)**: certified legs (GoldLedger criteria: normal confidence, home/away fav ≥ 0.55, breakeven 1/p, unit 10) resolved inside the SAME 10k sampled worlds as the standings → `gold` section in season_sim JSON: **485 certified bets** rest-of-season (avg p 0.645), at exact breakeven median +1₪ / P(profit) 50.3% (**EV=0 by construction — the sim proves the pot's edge can only come from odds above breakeven or realized>stated, which Gate A measures live**); margin ladder: +3% → median +146₪ (P 80.0%), +5% → +243₪ (91.5%), +8% → +389₪ (98.4%) on 4,850₪ total staked; breakeven pot dip median −109₪ / bad-run −328₪ (START_POT 1000 covers 3×); **Gate-A n=150 graded lands ~2026-12-12**. Volume honest-caveat: certifications assume today's ratings; count is robust, exact legs will drift. Not yet surfaced on Monkey page (held for sign-off — monkeys untouched rule). **Weekly lens added (user distinction: 64% of bets ≠ 64% of weeks)**: 33 betting weeks, ~14.7 GOLD legs/week — per-bet 64.5% (p5-p95 60.8-68.0) → **89.4% of weeks win the MAJORITY of their bets** (how it feels) → but green weeks at exact breakeven are a coin flip (**51.5%**), +3% margin 57.6%, +5% 60.6%, +8% 66.7% — while season P(profit) at +5% is 91.5%: thin weekly edge, compounding across weeks, is the honest shape of the product (gold.weekly in the report JSON).
- [x] **ZONES INTO THE PREDICTOR — Experiment A stage 1 PASSED (2026-09-15, user directive: "predictor must use zones, zones and mental are the core")**: the γ=0.02 scalar had compressed all 9 zone matchups into ONE number before fitting — that tested a compression, not the structure. `scripts/experiment_zone_channels.py`: 4 per-channel gammas (flank hole, central punch, progression-vs-screen, press-vs-buildup), fit 24/25 walk-forward (as-of-date zones, players excluded, n=1,368), FROZEN eval 25/26 (n=1,368): **channels 0.99903 vs shipping scalar 1.00093 vs form-only 1.00145 — beats the scalar by ~4× the scalar's own entire edge; fit AND eval improve (no overfit signature)**. Fitted gammas: progress **+0.095** (dominant — build-up through their screen; the v3.5 functional-midfield split is what made this extractable), central −0.05 / flank −0.03 (double-count corrections vs xG ratings), press 0.0 (already in ratings via turnover xG). Stage 2 full-stack gate PASSED (experiment_zone_channels_stack.py, 25/26 GW5+ n=1,560): channels vs shipping scalar — unified log-loss **1.00004 vs 1.00148**, acc 51.15 vs 51.03, draws top-4 31.62 = 31.62, GOLD 65.18% (n=537) vs 64.92% (n=533) → **SHIP-CHANNELS, WIRED LIVE**: channel_feats/channel_boosts in zones_engine (one implementation for prod+experiments), predict_fixtures channels mode (legacy scalar fallback), zone_blend.json v2 with full provenance. Live effect: Brentford-Chelsea 38.5/30.5/31.0→35.2/32.0/32.8 (call flips to ✕ 1-1). Honest record: NO-blend variant drew 33.09% top-4 (2 picks above both blends on n=136 — noise, logged, watch live). Season sim rerun: GOLD 477 certified, Gate-A ~Dec 13 — ship only if money metrics hold (rules.md #5). Mental door also legitimately reopen: the 08-08 "no mental in predictor" ruling was about the DEAD Opta system; dependability v2 recomputes weekly → Experiments B (squad dependability aggregates) + C (availability shock) queued for the international break, wired+frozen before Oct 7 booking or documented out.
- [x] **FIRST LIVE GOLD EVIDENCE + partial-settlement fix (2026-09-15)**: fixtures refreshed (results for Sep 13-14 had not been scraped, which is why nothing would grade) → **9/14 settled legs = 64.3% against a stated 63.6%** — the first live data point on the central claim, and it lands on the number. Tier detail (too small to read into, stated for honesty): upper half 6/7 = 85.7% vs said 68.6%, lower half 3/7 = 42.9% vs said 58.7% — the aggregate's accuracy is partly the halves cancelling. At breakeven the 14 legs returned 137.80₪ on 140₪ staked (−2.20₪), i.e. EV-zero behaving exactly as EV-zero. The 09-12 window stays PENDING on one late kickoff (Elche v Real Madrid, tonight) — windows grade atomically. BUG FIXED while checking: `GoldLedger.grade()` computed each settled leg then discarded the work unless the whole window completed (`if graded: _write`), so a 15-bet window straddling four days showed no progress and re-derived everything each run; now persists settled legs (`legs_resolved` in the return) and `summary()` carries a `settled` block (n / hits / realized / expected / pending_legs) which the Monkey page shows as the live line.
- [x] **BETTING MANDATE: the slip pot bets ONE instrument (2026-09-15, user sign-off "yes go")**: diagnosis — the pot had switched product between rounds (09-11 draws → 09-16 favourites) because `strategy_advisor` ranked every candidate by `p_profit`, which always crowns the highest-FREQUENCY shape. Enumerated proof over the live legs (all 16 outcomes, breakeven prices): favourites שיטה 2/4 = EV 0.00, P(profit) 64.3%, **best case +64₪ on a 60₪ stake, needs 3 of 4**; draws שיטה 2/4 = EV 0.00, P(profit) 39.7%, **best case +499₪, pays at 2 of 4** — identical EV, opposite skew, and the draw form pays at the threshold the product is actually played for. Favourite forms also duplicate GOLD's exposure. CHANGES: (1) pure-favourite candidates removed from the advisor entirely; primary is now FIXED by mandate (שיטה 2/4, or 2/3 on a thin board) with everything else demoted to price-driven alternatives — no weekly beauty contest; (2) slips carry a `mandate` stamp, `monkey()` reports `on_mandate` vs `off_mandate` blocks (pot balance stays whole — money staked is money staked; only the SCORE splits); existing rows stamped (09-11 draws, 09-16 favorites-experiment); (3) Monkey page = two labelled pots with their mandates written on them (Slip = the product, GOLD = measure-not-earn), off-mandate badge on the week row and on THE MOVE's booked slip. Live: draw-system record +227.67₪ ROI 379.5% (1/1), experiments 60₪ riding.
- [x] **Nav split: Betting | Model (2026-09-15, user sign-off)**: header nav is now two labeled groups with a divider — **Betting**: Picks / Ledger / Monkey 🐒 (money: what we bet, what it returned) | **Model**: Predictions / Table / History / Mental 🧠 / Backtest (what the model says and whether it is true). Reflects the architecture split (the seam already existed in the code: nothing above unified-probs touches money, nothing below computes a probability). Code-level split (model_core vs betting_service) still deferred to the repo re-init.
- [x] **Experiment C — availability shock: REJECTED on full-season evidence (2026-09-15)**: `scripts/experiment_availability.py`. HONEST CONSTRAINT stated up front: we scrape no lineup/injury feed, so the only leak-free version is RECENT absence state — core players (>=50% minutes share before the fixture) missing from the last match (shock1, mean 0.150) and from BOTH of the last two (shock2, mean 0.072 — rotation vs injury). Baseline = the SHIPPING model (zone channels included), protocol = within-season forward holdout (rosters only exist from 25/26): fit weeks 5-21 (n=767), frozen eval 22-38 (n=744). Two pre-specified parameterizations: **full** (own+opp free) fit own_s1=opp_s1=-0.08 — SAME sign both sides = it found a 'fewer goals tonight' effect, not a 'who wins' effect; **diff** (differential only, cannot move total goals). Eval: both IMPROVE out-of-sample log-loss (shipping 1.00810 -> full 1.00546 / diff 1.00387; the diff gain is ~2x what the zone channels shipped on) but both LOSE the draw money metric (top-4 33.82% -> 26.47% / 30.88%) and ~3-5 matches of accuracy. **Gate: REJECT-ALL.** First pass was under-powered (veto rested on 68 draw picks), so **24/25 rosters were backfilled** (1,750 matches, 0 errors, rebuilt from the Understat match JSONs the shots builder had already cached) and the experiment re-run at the standard zones passed: **fit 24/25 (n=1,510) → FROZEN eval 25/26 (n=1,511)**. Result: shipping eval-nll 1.00156 / acc 51.42% / draws top-4 31.06% / GOLD 64.71% (n=527) vs **full 1.00161 (WORSE out-of-sample) and diff 1.00109 (−0.0005, negligible)**, both losing draws (29.55%) and GOLD (63.6/63.2%). **Decisive diagnostic: the fitted coefficients do not replicate across seasons** — own_s1 flipped −0.08→+0.02 and opp_s1 −0.08→+0.12 between the within-season and cross-season fits. The first pass's log-loss "gain" was season-specific noise. WHY it fails (the useful part): the 38-match decayed xG window is ALREADY an availability-adjusted measure — those matches were played by the currently-available squad, so absence is largely priced in before the feature is added. The only part the window can't see is a man who played recently but is out TONIGHT, which needs a pre-match lineup/injury feed we do not scrape (data-acquisition question, not a modelling one). Does NOT refute "mental matters": Experiment B (squad dependability QUALITY, not presence) is a different hypothesis and still untested — needs as-of-date rankings in the mental engine (a build, not a script). Sample caches (data/reports/_availability_samples_{season}.json, gitignored) make future variants cost seconds.
- [x] **Match page: "our call" hero line + links renamed (2026-09-15)**: hero now states the call explicitly — `OUR CALL · 1 · Brentford win · 2-1 @ 39%` (chip + outcome + modal score + prob, ceiling-rule aware: Spurs-Villa renders `✕ Draw · 1-1 @ 33%`); "zones →" links renamed **"match stats →"** on picks + predictions pages (user: page is more than zones now).
- [x] **Gate-era expert defaults + fbref values LIVE (2026-09-15)**: fbref player backfill landed (misc/shooting/keeper, 10 league-seasons, name-join working) — with-skill re-default of all four recipes over the full 25-metric bank, family-aware, no presence metrics (gate handles it): DEF = tackles-won 18 / discipline 14 / interceptions 12 / clean sheets 12 / aerial 10 / big-games 10 / build-up 8 / crosses-that-arrive 6 / draws-fouls 5; MID = involvement-floor-led + killer balls 12 + two-way (tklw/int); ATT = delivery 18 / box 16 / big-games 14 / take-ons / aerial / killer balls; GK = REAL Save% 30 / clean sheets 22 / sweeper build-up 12 / discipline 8 (xG-proxy retired to bank). Boards: DEF Eric García/Pacho, MID **Pedri/Kimmich**, ATT **Kane/Haaland/Mbappé**, GK **Joan García/Svilar/Courtois** (real save% fixed the elite-defense keeper bias). Aerial-threat 'missing from bank' = false alarm: it is ENABLED in DEF+ATT recipes (cards live in one zone).
- [x] **Presence becomes a GATE, not a score (2026-09-15, user design call)**: eligibility = ≥60% of team minutes (recency-weighted, measured from first appearance for the CURRENT club — January signings qualify immediately), selectable on the board (40/50/60/70%); percentiles computed within the eligible pool; presence family (availability / minutes share / starter share / full-shift) retired from every recipe (auto-normalization redistributes); evidence shrinkage kept (within eligibles, 24 games ≠ 38). Pool 1,945→920 regulars; Dani Olmo (58%) gated out rather than scored down. Also this session: drag-and-drop config with categorized bank + per-bucket total bars; killer-balls/crosses-that-arrive creation metrics mined from shot-event assister data (Bruno Fernandes/Güler/Dembelé; Dimarco); full data inventory delivered (passing detail/miscontrols/errors: dead with Opta — per-player mistake attribution impossible free).
- [x] **Goalkeepers join the mental ranking (2026-09-15, user request; monkeys deliberately untouched)**: GK is a 4th role bucket with its OWN recipe (config page section 🧤) — new bank metrics **Shot-stopping** (goals prevented vs xG faced /90, from per-match defensive lines built off shot events; pre-shot-xG proxy caveat in desc) and **Clean sheets** (% of 60'+ apps conceding 0), plus reused avail/discipline/buildup90 (sweeper) / starter share. Defaults: stop 30 / avail 25 / CS 15 / disc 10 / buildup 10 / starter 10. Config auto-migrates (missing role seeds full defaults). 142 keepers qualified; face validity: #1 Svilar (+0.35 prevented/90, 50% CS), then Carnesecchi, Verbruggen, Joan Garcia. Board role filter + explainer updated.
- [x] **Ledger redesigned as the dash picks' own history (2026-09-15, user: 'make it look the same, performance over time')**: same three accented columns as the dashboard (✕ draws / 1 homes / 2 aways), each with lifetime rate (big number), hits/graded/committed, model's average stated probability (calibration on display), a **cumulative hit-rate sparkline** round-by-round, and picks grouped per round with per-round records (2/4 ✓ / 'in play'); grades on view; venue-note badge preserved. Live: draws 50.0% (4/8), homes 33.3% (2/6), away '—' awaiting its first October sample.
- [x] **Dashboard split: bets-only dash + Predictions browser + AWAY picks (2026-09-15, user redesign)**: (1) dashboard now = three bet columns (✕ draws ticket w/ collapsible alts 5–8 + hover why-chips, 1 home wins EPL+L1, NEW **2 away wins** all-leagues top-3) + trixy tiles + THE MOVE + watchlist; league round tables moved out. (2) NEW /dashboard/predictions: all 5 leagues' rounds with probbars/xG/likely scores/zones links, **league filter + round navigation** (« earlier = frozen first predictions graded vs results (48 verdict marks at shift−1), current, later » = live model view). (3) away picks wired through the whole chain: prediction_service (AWAY_LEAGUES=all, N_AWAY=3), ledger commit+venue-flip-safe grading+summary, history '2 pick' chips — first away set books with the October window (current round was committed pre-feature; round guard correctly refuses mid-round additions).
- [x] **Booked-round display + history draw visibility (2026-09-15, user: 'no draw predictions in history / duplication in best move / October matches?!')**: (1) BUG: after Monday's booking, the next-round rule made the dash leap past the LIVE bet to October — fixed with pending-span mode: while any bet is pending, the window IS the booked cycle's remaining span (09-15→09-20 restored, 57 fixtures), and THE MOVE renders the COMMITTED slip (frozen legs+scenarios from slips.jsonl) with a ✓ BOOKED badge instead of a fresh suggestion; Monkey's NEXT-MOVE preview yields whenever a pending slip exists (duplication gone). (2) October window (10-09→10-12) is REAL: zero fixtures in any league Sep 21→Oct 8 (international break) — after this round the next bet is genuinely Oct (books Oct 7). (3) History DOES contain draw predictions — argmax=draw is rare by law (needs ~34% draw beating both sides, e.g. Schalke-Elversberg 33/34/33) and was invisible (no bold): added yellow 'X call' badge (12 rows) + explainer updated. This week's live bet: שיטה 2/4 בתים — Bayern/City/Barcelona/Milan + 9 GOLD singles.
- [x] **Season-data policy settled by experiment (2026-09-13, user: 'move to this season only from GW5?')**: replayed 25/26 from GW5 (n=1,560, identical fixtures + shipping classifier): hard single-season cut vs rolling two-season window — draws top-4 **31.6% vs 33.1%** (worse on the money metric), outcome 50.5% vs 50.9%, GOLD tied 66.0/66.1%, homes better 69.6 vs 66.7. GATE: **keep the rolling decayed window for picks** (the 38-match window IS the gradual switch; near-wash proves it's already mostly current season by GW5). What DID change: **zones now blend both seasons** (ZonesEngine accepts season lists; shots+understat merged, understat gids globally unique; rolling window + decay age 25/26 out naturally; player layer pinned to LATEST season; ZONES_SOURCE_SEASON=[2526,2627]; battle-map label 25/26+26/27). Already current-season elsewhere: match facts/shot maps/pizza/shape/fair tables (2627), mental has the season toggle (both-weighted default + evidence shrinkage). scripts/experiment_single_season.py committed as the reusable gate.
- [x] **Banker mislabel + Monkey upcoming preview (2026-09-13, user: 'what does banker mean here?')**: pure-favorites forms (שיטה 2/4 בתים) had every leg labeled באנקר — wrong: a banker is a FIXED leg multiplied into every line, and that form has none; legs now role 'fav' ("X to win", no banker tag; the definition line in the advisor text keeps the correct usage). Monkey tab gained a NEXT MOVE preview box (form, window, lines, stake, P(profit), marks + 'books automatically on <date>') so the advised-but-not-yet-booked slip is visible during the guard period.
- [x] **Betting cadence enforced: next window = NEXT round only (2026-09-13, user: 'next window must be a different GW/round than the last bet')**: weekly_picks now excludes every fixture up to and including the last committed bet's final kickoff (`_last_bet_end` scans picks + slip legs + gold bets) — the dash no longer re-suggests a move mid-weekend; today it correctly shows the NEXT round set (window 09-16→09-20: Ligue 1/Serie A/EPL round 5, La Liga 6, Bundesliga 4). Commit guards tightened: 3-day re-commit gap + **never book a window opening >2 days out** (picks, slip AND gold — a premature 9-bet gold commit for 09-16 made 3 days early was caught by the verification run and pruned). Cadence now: round finishes → window flips to next round → daily run books it within 2 days of open.
- [x] **History vs Ledger reconciliation (2026-09-13, user: 'like we planned Paris FC to win?')**: not a grading bug — History grades the model's argmax outcome (Paris FC 38% → home call ✗) while the DRAW pick is a bet on the 32% market (0-0 → pick ✓, slip leg paid). UX fixed: History rows now carry a pick chip joined from the ledger (X/1 pick, green ✓ / red ✗ by BET result) + an explainer line ('✗ outcome, X pick ✓ is the strategy working, not a contradiction').
- [x] **ON-MOUNT REFRESH BROKEN + ROUND-DRIFT FIXES (2026-09-13, user: "it's not updating on mount")**: root cause = my Friday edit left run_weekly.py with an IndentationError (line 128) — every refresh since Friday noon (launcher 09:35, task 09:41) died at parse time. Fixed + py_compile now standard on touched scripts. Backlog run graded everything: **MONKEY'S FIRST SLIP: 3/4 draws hit (Lazio-Milan 2-2, Paris FC-Lyon 0-0, Lorient-Toulouse 2-2; Hoffenheim-Stuttgart 2-1 missed) = 3/6 lines, +227.67 NIS (+379%), pot 940->1,167**; draw ledger 4/8 (50%). Also caught+fixed the daily-run drift the backlog exposed: (1) **round-pure windows** — league cluster now keyed to fbref round NUMBER of the earliest upcoming fixture (date-clustering had merged La Liga Sunday leftovers with the Tue/Wed midweek round -> slip with Dep. A Coruna in TWO legs); (2) **team-dedupe in picks** (system math assumes independent legs); (3) **round guard**: LedgerService+SlipLedger refuse commits within 4 days of the last (one pick set / one slip per round — daily runs no longer re-bet mid-round leftovers; user: "make them one row, the form with the summary"); malformed 09-13 commits pruned (7 picks + 1 slip); (4) **history xG backfill** for understat lag (14 rows backfilled; Lazio-Milan xG pending understat publish); (5) **stale-data warning**: picks header goes red "STALE" when stamp >26h; (6) scheduled tasks got StartWhenAvailable + battery conditions removed (missed 09:00 fires on wake). All guards verified in a live run.
- [x] **Wide-layout attempt REVERTED (2026-09-12, user: table ruined)**: c670737 reverted in cb2be74 (progress entry went with it). What broke: the auto-fill league-table grid (600px min columns) squeezed 6-column round tables until fixture names and xG wrapped ("Atalanta v / Cagliari", "1.84 – / 1.0"). Lesson: league round tables need ~950px+ and stay full-width; any future layout work goes ONE component at a time with user sign-off.
- [x] **Mental: evidence correction (2026-09-12, user: '37 games vs 20 games should be treated accordingly')**: empirical-Bayes shrinkage — score = 50 + (raw−50)×n/(n+12), n = minutes÷90. 37 matches-worth keeps ~76% of deviation, 20 keeps ~62%, early-season 5 keeps ~29%. Effect verified: Orban (raw 82.0, evid 34.8) overtakes Groß (raw 84.0, evid 21.2) for #1; 26/27-only top score drops to 58.7 (honest early-season humility). Score tooltip shows raw + evidence + kept%; page explainer updated.
- [x] **Mental fix: per-team qualification (2026-09-12, user caught Bundesliga showing 2 teams)**: root cause — league-wide adaptive bar (floor 3) keyed to the MOST-played team hid every team one round behind (GER 26/27: 16 teams at 2 games, only Union Berlin + Schalke at 3 → whole league reduced to 2 teams). Fix: qualification per player from HIS OWN team's played count (60%, floor 2, cap 8). GER 26/27 now 18/18 teams, 149 players; 26/27 pool 560→958; both-view 1,655→1,795 (promoted-club players correctly judged on their short window). Page explainer updated.
- [x] **Mental: season toggle + expert recipes set (2026-09-12)**: filter bar gained Season (both weighted / 25-26 / 26-27); qualification adapts to the window (60% of most-played team's matches, floor 3, cap 8) so early-season views aren't empty — 26/27-only = 560 qualified (Aubameyang leads, small-sample flavor by design), 25/26 = 1,615, both = 1,655. Per-season cache keys; config save busts all views. Expert per-role recipes committed via skill reasoning (DEF: avail 22/discipline 16/big-games 14/buildup 10 — delivery OFF; MID: floor 15/consistency 12/buildup 10 — delivery OFF (noisy bonus); ATT: delivery 16 capped/box 14 (most stable attacker signal)/floor-xGxA 12): DEF top = Orban/Pacho/Akanji/Di Lorenzo/Guehi, MID = Groß/Yamal/Da Cunha/Nico Paz/Pedri, ATT = Kane/Haaland. Malen 3rd-ATT despite 51% big-game noted as the user's tuning dial.
- [x] **Mental v2: PER-ROLE recipes + bank of 19 (2026-09-12, user: "by position the algo needs to change; more options")**: config schema v2 — DEF/MID/ATT each carry their OWN component set + weights (data/config/mental_rank.json, auto-migrated; config page = 3 recipe tables, sticky save, per-role empty-recipe guard). Bank grew 14→19 with the mental family: **Big-game presence** (xGChain/90 vs top-6 opposition ÷ own norm, ≥3 apps else neutral — catches disappearing acts: Malen 51% vs Kane 134%), **Lives in the box** (in-box shots/90, pens excluded), **Shot selection** (xG/shot, ≥8 shots), **Set-piece threat**, **Final-ball delivery** (A v xA). Default recipes per role (DEF: avail/big-games/discipline/aerial-led; ATT: delivery/box/take-on-led; MID balanced). Scoring uses each player's role recipe over within-league+role tie-aware percentiles. Face validity: DEF top-5 Orban/Mainka/Akanji/Pacho/**Van Dijk**; MID Yamal/Nico Paz/**Groß**; ATT #1 **Harry Kane**. Round-trip verified (per-role save 303 + reset); config page opened for the user in an Edge app window.
- [x] **MENTAL RANKING REBORN (2026-09-12, user: "do we still have it?" + config-page + full-board requests)**: old mental system found intact (models/mental trait maps over fbref Opta columns + services/mental/mental_service.py + old EPL data — all in baseline) but **dead as a pipeline** (SCA/GCA/progressive/take-on/aerial columns stripped Jan 2026). Rebuilt as measured DEPENDABILITY on per-match Understat rosters: rosters schema v2 (per-player per-match xGChain/xGBuildup/xG/xA/KP/goals/cards/position) — 1,902 matches (2526 full + 2627) re-extracted from cache, 0 network, 0 errors. **Config-driven algorithm** (data/config/mental_rank.json, editable at /dashboard/mental/config): bank of 14 metrics — availability, minutes/starter share, involvement floor (25th-pct xGChain/90), consistency, end-product floor, quiet build-up, chance service, discipline, + the MENTAL family per user's philosophy ("manipulated ratios, not raw volume"): **Delivery (G v xG = xG-used)**, **Attacks his man** (TakeOn-preceded shots/90), **Aerial threat** (headed+aerial shots/90 — honest limit: defensive aerial duels don't exist free), **Plays the full shift**, **Travels well** (away xGChain vs own norm). Percentiles within league+role (DEF/MID/ATT, GK excluded, ties share rank), weighted blend, weights normalized. **Mental 🧠 tab**: full all-league board (1,655 qualified), filters league/team/position, crests, per-metric columns w/ hover docs. Face validity: **#1 = Federico Valverde**; Yamal takeon 0.55/90 + travels 114%. python-multipart added (Starlette form parsing). Save/reset round-trip verified; cache invalidates on save.
- [x] **IMPROVEMENTS WAVE 1 (2026-09-12, user: "do all")** — every item from the improvement map:
  - **GOLD singles paper track (Gate A instrument)**: `gold_ledger.py` — second pot (1000₪) betting EVERY certified ≥55% favorite (all 5 leagues) as a single at frozen breakeven; +EV at fair prices ⇔ realized > model p. Monkey tab section with realized-vs-expected + Gate A progress (needs n≥150 @ ≥62%). First window committed: 15 GOLD bets 2026-09-12 (incl. Real Madrid twice — compressed La Liga round, both legit). run_weekly grades+commits.
  - **Why-chips**: `DrawModel.explain()` (per-feature log-odds contributions vs training mean) → ▲/▼ chips on draw candidates + match hero ("evenly matched xG", "a point suits both", "someone must chase the win").
  - **Fair tables page** (/dashboard/table, nav "Table"): standings + xPTS + colored Luck delta per league (red = over-pointed/fade, green = owed points/value) + players-to-watch (xG+xA/90, ≥180 min).
  - **Promoted-team priors: KEEP** — measured on 28 promoted sides 24/25+25/26 (`measure_promoted_priors.py`): archetype 0.79× att / 1.21× def vs the old flat league-avg prior; blended with observed matches (prior=4 pseudo-matches), certification bar MIN_MATCHES 5→MIN_CERT 3. Frozen A/B (backtest_2526): draws 32.2%→**32.9%**, homes 68.4%→**69.3%**, calibration intact. Full recal chain re-run: zone blend KEEP (γ=0.02), 24/25 frozen re-confirms GOLD 65.7% (421/641), outcomes 53.4%.
  - **League terms in classifier: REJECT** (`experiment_league_terms.py`): 11s picks identical 32.2%, log-loss slightly worse (0.56264 v 0.56202) — pooled rolling features already carry league signal. Recorded null #3.
  - **All-league GOLD in advisor: already true** (bankers scan all_predictions across 5 leagues) — verified via gold commit spread.
  - **Ops**: monthly "PredictorRecal" scheduled task (1st, 08:00 → run_recal.cmd, logs to data/reports); crown-jewel backup step in run_weekly (ledger/history/slips/config → data/backups/state_*.zip, keep 10, gitignored); Telegram notifier `services/notify.py` (inert until data/config/telegram.json filled — .example committed, real file gitignored) posting window + draw picks + slip + GOLD count.
- [x] **BASELINE COMMIT `115effe`** (2026-09-12, user: "commit all this as new baseline"): 326 files — full predictor v1 (model, dashboard, accountability, ops, docs, skill) + all data incl. `data/fbref` (pre-Opta-loss scrape, NOT re-fetchable → deliberately versioned). Ignored: downloaded_files, static/pizzas (regenerable), .claude/settings.local.json + skill workspaces, data/reports logs + run stamp.
- [x] **Match-page redesign v2 (2026-09-12, user screenshots: black pizzas, mobile-ish layout, poor hero)**: ROOT CAUSE of "black pizza circles" + plain form letters + narrow column = **stale cached style.css** (new HTML, old stylesheet: SVG slices fell back to default black fill) → permanent fix: `?v={mtime}` cache-buster on style.css (asset_v Jinja global) + favicon link; pizza PNG urls carry their own mtime version. Redesign: (1) **hero header** — crest+name+form each side, center P(H/D/A) big numbers + probability bar + xG/likely-scores + league chip (replaces h2+tiles); (2) **team dossier columns** — one column per team (accented home blue/away orange): Season so far rows → percentile pizza → shot-map pair side by side → typical XI (answers "separate data by team"); (3) **pizza switched from hand-rolled SVG to mplsoccer PyPizza PNGs** (user suggestion; matplotlib already a dep) — disk-cached static/pizzas/<league>/<team>.png, auto-regenerated when older than last_weekly_run stamp; verified visually (Milan: screen 95 / xGA 79 / on-target 16); (4) **new stats**: clean sheets + blanks (fixtures), set-piece xG + % of chances (shot situations: FromCorner/SetPiece/DirectFreekick — Lazio 26% SP-heavy vs Milan 15%); (5) form letters now solid W green / D orange / L red chips; (6) wrap widened to 2200px. mplsoccer added to requirements.txt. Live 8080 restarted; user must hard-refresh once (Ctrl+F5) to escape the old cached CSS — every later change busts automatically.
- [x] **Identity + wide-screen + pizza pass (2026-09-12, user: logos, per-team separation, more stats, use the width)**: (1) **crests everywhere** — `scripts/fetch_team_logos.py` pulls team badges from TheSportsDB free API (98/98 after alias fixes: hyphens break its search — "Paris Saint Germain" unhyphenated; Monaco/Angers/Hamburg plain; Nottingham soccer club invisible to free search → crest verified visually and installed manually) + **5 competition crests** (fixed league ids, user mid-turn request) → static/logos/ + manifest.json; rate limit is ~30 req/min (1.2s tripped 429s → SLEEP_S 2.5 + 70s backoff-retry). Monogram-chip fallback so a missing crest never breaks. Match page: matchhead (crest v crest + league chip), crested fact/pizza/shape cards and shot-map team blocks; league crest chips in picks/ledger/history/backtest/slip tables via `league_crest` Jinja global. (2) **Per-team separation**: shot maps regrouped into two team blocks (taken+conceded pairs under a crested header), home/away accent borders (tc-home blue / tc-away orange) on every team card. (3) **Wide-screen**: .wrap/header max-width 1080→1720px (desktop app now). (4) **New stats**: fact cards gain Record (pts · PPG · **xPTS** from stored understat expected_points) + colored last-5 form letters; **9-slice team pizza** (league percentiles: attack xG/BIG/DEEP, shooting SHOTS/SOT%/CONV%, defending PRESS/xGA/SCREEN — DEEP=passing proxy, PPDA=tackling proxy, inverted slices flipped so longer=better; hover=value+percentile). Verified live: Toulouse 1 pt vs xPTS 5.2 (huge unluck flag), 12 crests/page, 18 slices, league chips ×14 on picks. Live 8080 restarted on new code.
- [x] **Desktop-app launcher shipped (2026-09-12, user: "double click on desktop, update on mount, updated every day")**: decision = NO Electron/pyinstaller rewrite — a launcher gives the app experience with zero rewrite. Pieces: (1) `scripts/launch_dashboard.ps1` — starts uvicorn on 127.0.0.1:8080 hidden if not listening (logs to data/reports/server.*.log), waits for the port, spawns background full refresh, opens dashboard in an **Edge --app window** (own window/taskbar icon, no browser chrome; falls back to default browser); (2) **"Football Predictor" Desktop shortcut** (runs the ps1 hidden; custom pitch-and-ball icon generated with Pillow → static/predictor.ico); (3) "update on mount" = run_weekly with NEW `--if-stale-hours 6` guard + success stamp `data/reports/last_weekly_run.txt` (launcher refreshes only if last full run >6h old; daily 09:00 PredictorWeekly task — verified alive, next run 09-13 — still runs unconditionally and writes the same stamp); (4) picks page headmeta now shows "data refreshed YYYY-MM-DD HH:MM" from the stamp. Verified live: launcher booted server (200), refresh started, app window opened.
- [x] **Heat zones + typical shape shipped; pass maps ruled out honestly** (user asked for pass map / heat zones / avg positions): (1) **heat zones** = xG-density wash (8×6 grid, opacity ∝ share of hottest cell) under the shot-map dots — free, from stored shots. (2) **"Typical shape"** = minutes-weighted role map: NEW `services/understat/rosters_service.py` extracts per-match lineup slots+minutes from the SAME cached Understat match JSONs the shots builder uses (`_read_match` returns `rostersData`; 146 matches built for 26/27, 0 network fetches, 0 errors); `scripts/build_rosters.py`; rosters step added to run_weekly; dashboard `_team_shape()` places top-11-by-minutes at modal slot coords (17 Understat codes → tactics-board XY, duplicate-slot spreading, suffix-aware surnames), full-pitch SVG, opacity=minutes share, honest UI label "lineup data, not tracking". (3) **Pass maps: impossible free** — pass-event coordinates were never free for live top-5 seasons (StatsBomb open data ≠ current seasons; WhoScored/Sofascore = unofficial blocked APIs); closest owned proxies: deep completions (midfield build-up rating) + shot lastAction. Verified live: 35 heat cells, 2 shape maps × 11 named dots (Mvogo…Cásseres fix for "Jr." suffix).
- [x] **Investor plan written** (`investor_plan.md` + `scripts/investor_projection.py` + `data/reports/investor_projection.json`): Monte Carlo 200k seasons/cell over p∈{25,29,32%} × odds∈{2.65,2.90,3.15} × {18,30} windows. Headline truths: flagship שיטה 2/4 is **−EV everywhere in the user's band at validated 29% skill** (−17% to −41%/window; breakeven odds 3.45); only ceiling-skill (32%) × top-band (3.15) is +EV (+1.6%, P(profit season) ≈ 47-51%); GOLD homes breakeven 1.52 = most investable vein; ruin risk material at 30 windows (up to 68% worst cell). Plan = price-gated thesis (bet only above breakeven, GOLD singles > 1.52, Monkey as public track record), risk register, decision gates (Gate A: live GOLD n≥150 ≥62%; Gate B: season Monkey ROI + measured ≥3.45-odds frequency). No stake advice, no odds ingestion — operator's domain, per rules. per team from stored 26/27 shot events — top scorer, top assists, goals v xG with hot/cold finishing note (mean-reversion warning), shots · on-target% · conversion%, games. Zero new scraping (player/assist/result were already in every stored shot). Verified: Makengo/Katseris (Lorient), Russell-Rowe/Gboho (Toulouse); both cold (2 from 4.1 xG / 2 from 6.6 xG). **Passing accuracy: impossible post-Opta** (stated in UI; deep completions = closest proxy, already the build-up rating). Shot-location detail beyond lanes = possible later (shot maps from stored x/y).

## Window redefined: per-league round clusters (2026-09-11, user caught 2-GW tables)

- [x] User caught two rounds mixed in one league table (Bundesliga showing Sep 11-13 AND Sep 18-19 "next window" rows). Root causes: (1) the lookahead preview polluted tables; (2) date-based global clustering merges rounds when any league (La Liga midweek) bridges the days continuously.
- [x] New definition — neither Mon-Sun nor fixed weekend: **each league's window = its own next ROUND cluster** (consecutive match days, gap ≥2 days breaks, span ≤3 days so Fri→Mon holds but back-to-back rounds never merge); the betting window = union of rounds starting within 2 days of the earliest. Lookahead removed — tables show only the current round. Verified: window 09-11→09-14, all 5 leagues exactly one round each, Sep-16 La Liga leak evicted from the ticket.

## Home-win forms enter the advisor (2026-09-10, user challenge)

- [x] User challenged the draws-only focus ("model specializes in home wins — doesn't make sense"): historically homes were excluded by the user's own Aug-8 instruction (homes = context only). Now the advisor evaluates **home-favorite structures every window**: שיטה 2/4 בתים, 3/4, and the 4-fold acca on the top-4 certified favorites, ranked by the same exact P(profit) engine. Bankers list widened 3→4.
- [x] This window's verdict unchanged (draws 2/4 at 38.5% beats homes at 26.5% — only ONE true GOLD home exists this week; Inter 77% + three ~55%). On a 3-4-GOLD week (65% each), homes 2/4 reaches P(3+ of 4) ≈ 56% and will be crowned automatically. Homes 2/4 also shows its character: 93.1% cash-something frequency, small payouts (pairs ~2.2-3.3x).
- Note for the money conversation: favorite-longshot bias means books price favorites closest to fair — the homes edge likely converts to real money best; the ledger/monkey will show it.

## Automation + slip detail + notation fix (2026-09-10)

- [x] **Weekly run automated**: `scripts/run_weekly.cmd` + Windows Scheduled Task "PredictorWeekly" (daily 09:00, next run 09-11) — grades land the morning after matches; window/idempotence dedupes make daily runs safe. Logs to `data/reports/run_weekly_latest.log`.
- [x] **Clickable slip detail** (`/dashboard/monkey/slip?window=`): the original frozen slip card with per-leg results (score, ✓/✗, fair price, prob) + line-by-line table (every combination, fair-odds product, WON/lost/pending, return). Monkey week rows link to it. Monkey tiles fixed: ROI/net computed on GRADED slips only; pending stakes shown as "in play".
- [x] Notation collision fixed (user: "form is 2/4 — there cannot be 4/4"): scenario rows renamed from "4/4" (reads as a line type in Winner language) to "4 of 4 hit — all of them!" with caption clarifying rows count marked games landing, not line types; math unchanged (all 4 marks hitting = all 6 pair-lines win).

## Slip ledger + Monkey tab (2026-09-10)

- [x] `services/predictions/slip_ledger.py` (user request): every advised slip frozen at commit (structure, k, lines, legs with marks/probs/breakevens), one per window (drift-proof dedupe), graded line-by-line when all legs resolve (tolerant venue-flip matching); returns computed at breakeven prices frozen at commit, **10₪/line** (user default).
- [x] **🐒 Monkey tab** (`/dashboard/monkey`): bot bankroll from **1,000₪ start** — pot/net/ROI/peak tiles, week-by-week table (form, legs with ✓/✗ marks + hover scores, hits, lines won, return, net, pot-after). Wired into run_weekly (grade slips + commit slip). Seeded: window 2026-09-11 שיטה 2/4, 60₪ staked, pot 940₪ pending.
- Note: monkey returns are fair-price structural results; real Winner odds shift actuals — labeled on the page.

## Strategy advisor — "this week's best move" (2026-09-10)

- [x] `services/predictions/strategy_advisor.py` + picks-page section (user request): plain-words weekly recommendation over the **Winner form catalog** (יאנקי/שיטה 2/4/לאקי 15/טריקסי/פטנט + **באנקר** × system structures — structures only, never odds). Computes: draw-board strength (top-4 avg vs ~32% ceiling), best certified banker across ALL leagues (GOLD ≥65% = "real banker" → recommends באנקר+שיטה 2/4; 55-65% = minimum-grade → plain Yankee; none → pure draw forms; thin board → Trixi top-3 or sit out), P(any return)/P(big week) per form via exact hit-distribution math. Always ends with the breakeven-vs-price discipline reminder; stakes/odds stay the user's.
- [x] First live output found a banker the pick tables never surface: Inter v Udinese 77% GOLD (Serie A — outside HOME_LEAGUES) → week's recommendation: banker × 2/4 draws, ~30% boosted-return chance; Yankee as steady alternative.
- [x] User corrected the form mechanics (their real Winner slip): banker counts as a 5TH SELECTION → **שיטה 2/5 = 10 lines** (not banker×2/4=6), and **2 hits = 1 line ≈ half the form back = partial refund, not a win**. Advisor rebuilt on exact 2^N scenario enumeration at breakeven prices: slip now shows a hit-scenario table (chance / lines won / ~% of form back / lost–refund–PROFIT) — this window: 2/5 hits 37.5%→51% back, profit starts at 3 hits (24%→188%), **P(PROFIT) 32%**, P(any cash) 69%. Slip header shows P(PROFIT) prominently.
- [x] **User challenged 2/5 as "not the right move" — CORRECT; advisor logic rebuilt to choose by exact P(PROFIT)** across all shapes incl. the user's 2-banker and 3-banker proposals. Verdict (this window, fair prices): draws-only שיטה 2/4 = 38.5% profit-weeks (profit from 2 hits); every banker added LOWERS it monotonically (1B/2-5: 31.9% · 2B/2-6: 25.8% · 3B/3-7: 19.8%) while raising cash-back frequency (2/6: 88.6% — the "feels safe, profits less" trap). Bankers reframed as a PRICE tool (upgrade only when book prices banker above fair). Slip now recommends 2/4 draws-only; comparison table ranks all shapes by P(PROFIT).
- [x] Banker-source question (user: "wins picker isn't Inter — focus leagues?"): explained picks-list (EPL+Ligue 1, league-EDGE product) vs banker (single leg, raw probability, all-league scan). Season gold-by-league so far: Serie A 7/8, EPL 4/5, La Liga 7/9, **Ligue 1 2/7** — small samples but the all-league banker scan is supported; restricting to home-pick leagues would have forced 55% Liverpool over 77% Inter.
- [x] Ops note: git-bash `kill %1` does NOT kill detached Windows pythons — test servers must be stopped by PORT (PowerShell Get-NetTCPConnection→Stop-Process); two phantom-500 hunts caused by stale 8081 zombies.
- [x] Redesign after user feedback ("what's the bottom line? which games? fix RTL"): section now leads with a **Winner-style slip card** (yellow form look) — THE MOVE title, 5 concrete legs with marks (banker row highlighted, mark 1/2 + "באנקר X to win"; draw rows mark X) each with league/kickoff/prob/breakeven, a "how the form works" footer; comparison table collapsed into details; Hebrew wrapped in `<bdi>` for correct bidi.

## 65% goal session: tiers + opponent adjustment + second season (2026-09-10)

- [x] User goal "65%+ outcome": honest math delivered — impossible across all fixtures (draws are 25% of outcomes and never the argmax; bookmaker closing lines ~54-56%); **the 65%+ vein exists as the confident tier**.
- [x] **Confidence tiers shipped**: GOLD (fav ≥55%) / SILVER (45-55%) / coin-flip, badged on picks + history; per-tier accuracy tile on History (target line 65%+). Live 26/27 gold: 66.7% (22/33).
- [x] **Opponent-adjusted ratings (strength of schedule): built, calibrated, REJECTED** — frozen 25/26 got worse (log-loss 0.9959→0.9969, draws 32.2→30.3, homes flat). Balanced round-robins self-average schedule strength. `OPP_ADJUST_ITERS=0` with the finding documented in code; per-date ratings memoization kept (~5× faster backtests). Second sophisticated upgrade rejected by the gate — model is at its information ceiling.
- [x] **Second out-of-sample season (user request)**: `scripts/backtest_season.py --eval 2425` — params fit on 23/24, classifier trained ≤23/24, walk-forward eval on 24/25. Results: outcome 53.8%, **GOLD 66.2% (415/627 — tier thesis REPLICATES)**, home picks 62.3% (+18.5pp; 11 perfect weeks), draws 29.6% (+4.8pp — draw edge replicates). Backtest page now shows both seasons.
- [x] Two-season truth: home picks 62-68% (~65 avg), draws +5-7pp over base, GOLD 65-66% everywhere incl. live. 25/26 numbers reproduced bit-for-bit after revert (pipeline determinism check). Chain runner: `scripts/run_recal_chain.py`.
- [x] Draws remain THE betting product (user asked): outcome-accuracy work sharpens the context layer + lambdas feeding the draw classifier; strategy unchanged.

## History backfilled to season start (2026-09-10)

- [x] `scripts/backfill_history.py` — all 146 played 26/27 fixtures reconstructed **walk-forward** (strictly-prior data, frozen params) and graded; rows marked `retro` (badge in UI) to stay distinguishable from live-recorded predictions forever.
- [x] **Season-to-date scorecard: outcome 55.5%** (81/146; above the 51.9% backtest ref), **exact score 11.0%** (ref ~10.5%), xG ±0.20 both teams 8.6%, **⭐ PERFECT ×2** (Betis 1-0 Sociedad: predicted 1-0 & xG 1.76-1.04 vs real 1.70-1.14; Parma 0-1 Cagliari: predicted 0-1 & xG 0.99-1.14 vs real 1.03-1.26 — the MW1 draw pick that missed as a draw was a near-perfect match model). Per league: Serie A 20/30, La Liga 22/41, EPL 16/30, Bundesliga 10/18, Ligue 1 13/27.

## Zones page v2 + watchlist + History tab (2026-09-10, later)

- [x] **Mirroring proven correct empirically** (user challenged twice): winger shot-side test — Salah/Saka (right) mean y≈0.38-0.40 in BOTH home & away, Kvaratskhelia (left) ≈0.54 → Understat y is per-shooter (no home/away flip), low-y = shooter's right; engine geometry validated.
- [x] **Zones page redesigned as a BATTLE MAP** (user: "bad bento grid — what does the user learn?"): 6 duels (3 flank strips × 2 attacking halves) + midfield pill; each duel = "X attack left v Y defend right", one attack-v-defence number pair, plain-word verdict ("should create here" / "shuts this down" / "even"), color = favored TEAM (blue home / red away, same language as probbars); headline names each side's biggest threat. Replaces the mirror-label cell grid entirely.
- [x] **Watchlist on picks page**: low-confidence fixtures with ticket-grade P(draw) (e.g. promoted-team games like Union Berlin-Schalke 37%) now shown with probabilities + breakevens, badged uncertified, never auto-picked or ledger-graded (user caught them being hidden entirely).
- [x] **HISTORY TAB** (user request): `services/predictions/history_service.py` + `/dashboard/history` — EVERY predicted fixture recorded at prediction time (first prediction stands; idempotent), graded vs actual score AND actual Understat xG: ✓ outcome / 💯 exact score / xG hit (both teams ±0.20) / **⭐ PERFECT (score+xG)**; summary tiles with backtest reference rates; wired into run_weekly (record + grade steps). Seeded with the 85 GW4-window predictions (pending). Recording began 2026-09-10 — earlier GWs have no stored snapshots.

## First live cycle + zones v3 (2026-09-10)

- [x] **MW1 GRADED (first live week): draws 1/4** (Nice-Lorient 0-0 HIT; Parma 0-1, Bologna 0-1, Everton 2-0 — two misses one goal away), **homes 2/3** (Lens 5-2, City 2-1 HIT; PSG drew 2-2 — see venue flip below). User's Yankee: 1/4 → −110₪ (the modal week, ~40%).
- [x] EPL draws by GW so far: 1, 3, **6/10 (GW3!)** — user's observation confirmed. Windows 2-3 were never committed (no weekly run executed) — **schedule the weekly run** to stop missing windows.
- [x] Bug: **Understat league-page cache served stale preseason data** (shape (3,0), KeyError 'home_team') → refresh flags added (UnderstatService/ShotEventsService bypass league-page cache mid-season, per-match cache kept); run_weekly now also refreshes name maps + player stats. 26/27 rebuilt: 146 matches, ~1,950 players, 146 shot files, 0 errors.
- [x] Bug: **fbref renamed PSG → "Paris SG" and flipped the Rennes fixture's venue post-commit** → FBREF_TEAM_ALIASES (canonical "PSG") applied at fixture normalize + stored-file repair; ledger grading gained tolerant fallbacks (reversed venue; same-date single-name match) with hit judged from OUR pick's perspective; PSG row graded MISS (predicted winner drew).
- [x] **ZONES v3 REDESIGN** (user spotted left=right clone cells): root causes — (1) lane shrinkage anchored to 5-lane TOTAL (5x too strong, erased lanes; interim fix anchored to mean lane), then the deeper truth: (2) **Understat shot y spans only ~0.24-0.85 — true wide lanes get ~2 shots/season**; the 3x5 grid was unsupportable. v3 = **3 lanes x def/att + single midfield-control zone (7 zones)**, lane bounds fitted to 44k real shots (y<0.42 R 25% / 0.42-0.58 C 48% / ≥0.58 L 27%); mid per-flank pretense dropped honestly. Dashboard pitch now 3x3 with spanning mid cell + "↔ their right" mirror labels (user's alignment ask). Sanity gate PASSED; lanes now genuinely differentiated & asymmetric (e.g. Lorient def L 70.6 vs R 41.2).
- [x] Zone-blend recalibrated for v3: gamma=0.02, eval delta −0.00037 (KEEP; still tiny by evidence).
- [x] Stale GW4 picks (auto-committed on broken understat data) pruned pre-kickoff; **GW4 window (Sep 11-15) re-committed on the fresh stack**: draws Lazio-Milan 32.6%, Paris FC-Lyon 32.3%, Lorient-Toulouse 32.1%, Hoffenheim-Stuttgart 31.3% (trixy 38.5%/10.0%/1.06%); homes Liverpool 55.4%, Villa 45.4%, Le Havre 44.6%. Note: fresh GW1-3 form ejected Utd-City from the stale board's ticket.
- [x] First 26/27 team-stats snapshot archived (weekly walk-forward history begins)

## Season-start upgrades round 2 (2026-08-20, user QA session)

- [x] **Weekend-based selection replaces gameweek-based** (user: league rounds drift — Serie A can be on R2 while EPL is R1): picks pool = ALL unplayed fixtures in [earliest kickoff, +4 days] regardless of round; league tables show +4 more days tagged "next window"; WINDOW_DAYS=4 (a midweek opener keeps Sunday/Monday reachable). `weekly_picks(start=None)`; routes take `?start=YYYY-MM-DD`.
- [x] **Ledger dedupe made drift-proof** (window label shifts as early games get played → double-commit bug caught in verification, 7 spurious rows removed, original slip restored): a pick type is "taken" when pending picks of that type have kickoffs inside the new window.
- [x] **Unified outcome probabilities** (user caught bar D=27% vs ticket 34.8% for same fixture): official triplet everywhere = classifier-calibrated P(draw) + Poisson H:A ratio rescaled (`unified_probs`). Backtest validation: log-loss 0.9964→0.9959, home picks 67.5%→**68.4%** (+24.7pp), draws unchanged. Poisson triplet kept as `probabilities_poisson` internally.
- [x] Bold-team UX rule (user): bold = predicted winner only; draw-predicted = nobody bold (league tables via macro; ledger/backtest by pick_type; home-pick table keeps bold-home semantics).

## Season-start upgrades (2026-08-20)

- [x] **Draw model upgraded to 11-season training** (1415–2425, n=17,134; Understat backfilled 7 more seasons): frozen 25/26 pick hit rate **28.9% → 32.2% (+7.4pp over base)**, calibration intact (predicted 31.9%). Robustness: 10-season variant scored 28.0%/32.9% on two held-out seasons. GBM tried and rejected (26-30%, overfits). Experiment harness: `scripts/experiment_draw_models.py`.
- [x] Real Winner slip analyzed (user's MW1 Yankee, 11 lines ×10₪): legs priced 2.90–3.30 vs our breakevens → form EV ≈ −1.1% (near-fair; two legs +EV). Season sims: 18 forms ≈ EV −19₪ / median −383₪ / 36% positive seasons / 18% bonanza chance; 24 forms similar EV, wider spread.
- [x] **Betting-window filter** (user caught Valencia Aug-25 occupying a weekend ticket slot): picks pool restricted to [earliest kickoff, +3 days]; out-of-window fixtures badged "next window" in league tables. MW1 ticket = Nice/Everton/Parma/Bologna = user's placed slip.
- Weekly run on 2026-08-20 confirmed: no matches played yet anywhere except La Liga (6); ledger pending; understat/shots 2627 will start filling after this weekend.

## Strategy revealed + trixy support (2026-08-08)

- **User's real product: Israeli Winner trixy — 4 draw picks per GW; 2/4 money back, 3/4 great, 4/4 bonanza. Home wins = context only, not bets.** Optimization target is the weekly hit distribution, not per-pick rate.
- [x] Backtested trixy distribution on 25/26: EPL+Serie A pool → ≥2/4 in 10 weeks, 3/4 ×1, 4/4 ×0. **ALL-5-league pool → ≥2/4 in 12 weeks, 3/4 ×2, 4/4 ×1.** Selective week-timing shows no edge. Honest 4/4 expectation ≈ once per 2–4 seasons (P≈0.6–0.8%/week; p⁴ scaling makes per-pick prob the key lever).
- [x] **Trixy outlook tiles** on picks page: P(≥2/4), P(≥3/4), P(4/4) per week (Poisson-binomial over the 4 picks; MW1 2627: 34.0% / 8.0% / 0.76%)
- [x] Draw pool switched to ALL 5 leagues (user approved 2026-08-08); ledger reset pre-season (user instruction) and MW1 re-committed under the new pool: draws Parma-Cagliari, Bologna-Lazio, Everton-Palace, Union Berlin-Frankfurt; homes PSG, Lens, Man City; trixy outlook 34.5%/8.2%/0.79%
- [x] Week-clustering analysis (user question "why didn't we catch 4+ draw weeks"): ≥4-draw weeks exist ~1 in 4 weeks per league (Serie A most, 10-11/38) but overdispersion ≈ 1.0 across all ten league-seasons → drawish weeks are pure random clumping, not predictable; phase patterns flip between seasons (no stable late-season effect). Only lever = per-pick probability (ceiling ~32%).
- [x] Context-features draw experiment — **NULL RESULT** (2026-08-08): added ppg_gap / season_frac / mutual_comfort (walk-forward standings state) to the classifier; model assigned them near-zero coefficients (±0.001–0.04), out-of-sample trixy 28.9% vs 29.6% (noise). Consistent with overdispersion≈1.0 finding. Features kept in the trained model (self-neutralized, harmless). Draw signal sources now exhausted except zone-blend (pending).

## Next up

- [ ] **Change the player model's appearance** (user, 2026-09-20 — parked
      deliberately, not forgotten). The kit recolouring works and the
      regions are right; what is left is how the figure itself LOOKS. Open
      questions when it comes back round: a different model, or this one
      posed/proportioned differently; whether a stylised figure reads better
      than a photoreal one at thirty pixels; whether the face and hair
      should be neutralised so eleven clones stop being visibly the same
      man. Everything needed is already in place — `Figure` in
      `Formation3D.tsx` is the single swap point, `scripts/optimise-model.sh`
      takes any download down to web weight, and
      `scripts/build_kit_regions.py` re-derives the shirt/shorts/socks map
      for whatever mesh replaces it.
- [ ] ⚠️ **CC-BY attribution for the player model is still missing** —
      title, author and source URL into `web/app/lib/credits.ts`. The lab
      prints a visible warning while it is absent, and publishing without it
      is a licence breach rather than an oversight. **Blocks going public.**
- [ ] **Zones, refactored** — the user has an idea for these now that the
      pitch is better. The density surface built for player territory is
      the same machinery, so most of the work is already done.
- [ ] **Make the web responsive — BEFORE LAUNCH** (user, 2026-09-20). Built
      desktop-first throughout and never checked narrow. Known suspects:
      the predictor table is ten columns inside `overflow-x-auto`, so on a
      phone it is a horizontal scroll of numbers with no frozen team column;
      the league pill row wraps but the `2xl:grid-cols-2` visual pairs on the
      match page collapse to one full-width canvas each, which makes that
      page very tall; every `<PitchScene>` takes a fixed pixel `height`, so a
      420px canvas on a 375px-wide phone is a letterbox; the 3D labels are
      screen-space and sized for desktop. Decide per view whether the answer
      is reflow, a card layout, or simply not offering the 3D on small
      screens.
- [ ] Monday night: scrape the other four leagues' events, then rebuild
      passes/kits/plots for them and retest the predictor on ~1,750 fixtures.

## Deployment — open, to discuss (raised 2026-09-20)

**User's shape:** the server stays local, the web gets "injected". That is
exactly what `output: "export"` already produces — `run_daily.py` at 09:00
writes `data/web/*.json`, `pnpm build` turns it into a static `out/`, and
only `out/` ever leaves the machine. The scrapers, the parquets and every
credential stay here. This also keeps the standing rule intact by
construction: raw WhoScored streams are gitignored and never published, only
derived metrics.

**Measured, because it changes the answer and tonight's scrape changes it
again:**

| | files | size |
|---|---:|---:|
| `out/` today (EPL events only) | 493 | 70 MB |
| of which pass maps (20 teams × 4 seasons) | 80 | 45 MB |
| after tonight (+76 team-seasons × 3) | ~720 | **~200 MB** |

Pass maps are 573 KB each and dominate everything else. They are fetched per
team on demand, so **no visitor ever downloads 200 MB** — it is a hosting
cost, not a page-weight one. File count stays trivial for any host; total
size is the thing to decide against.

**To decide:** where `out/` goes (a static host, or served from here), how it
gets there after the 09:00 run, and whether the pass payloads get trimmed —
573 KB per team-season is a lot of precision for a picture, and a quantised
or filtered export would cut it hard if hosting size turns out to matter.

## Backlog (post-v1)

- [x] ~~Mental-model tie-breaker~~ **DROPPED permanently (user, 2026-08-08)**: mental scores can't be computed for new seasons (inputs died with fbref's advanced data) — "no mental if cannot scale". Player quality now comes from Understat metrics instead.
- [ ] Per-GW "Best XI that will thrive" — reframed post-mental: 11 players best positioned to over-perform that gameweek (Understat player quality × zone-matchup advantages) — user request 2026-08-07
- [ ] Odds ingestion + value detection
- [ ] Away-win picks / extra leagues

## Known issues (not blocking current stage)

- README.md describes a deleted 2025 layout — superseded by `projectInfo.md`
- Dockerfile only copies `main.py`; port mismatch (8000 vs 8080)
- `data/league_init/` + `data/players/` are season 2425 (stale; replaced in stages 3–4)
- Empty placeholder files: `utils/*.py`, `services/ranking/league_service.py` (orphans, nothing imports them)
- `services/transfermarket/player_info_service.py` orphaned (needs playwright; source of `profile_img`/`foot` fields)
