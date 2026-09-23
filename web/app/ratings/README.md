# `/ratings` — players and sides

What they **do**, measured from ~1,500 events a match. Not what they are like.

## The claim, and the claim it is not

This page was called *Mental* and the name was the problem: it promised
psychology and delivered event metrics, so every reader arrived asking what
was being claimed. It is a **capability profile** — how good are they, broken
down into what "good" means for the job each of them actually has.

Two rules the page enforces on itself:

1. **A metric that cannot reproduce itself from one season to the next is
   measuring luck.** Those are marked red and ignored by default. You can
   switch that off; the colour stays.
2. **Style is never scored.** Going long is not worse than playing out, and
   high tempo is neither good nor bad. Only *quality* carries weight.

## Files

```
page.tsx          route shell — the h1 and the standing claim
RatingsTabs.tsx   players/teams switch; owns the per-tab intro copy
RatingsData.tsx   the data layer: index, league choice, view fetching,
                  and the React context both boards read
PlayerBoard.tsx   the players table
TeamBoard.tsx     the sides table
EloTable.tsx      the process-Elo standing, shown under the teams tab
teamScore.ts      team scoring maths, shared with the match page
scoreUi.tsx       the visual grammar both boards share
```

`scoreUi.tsx` exists because the two boards each carried their own copy of
the colour ramp and the score ring — same algorithm, same SVG, differing
only in a constant — and the team copy had already drifted, inlining the
palette as anonymous arrays and losing the paragraph explaining the scale.
One copy, one explanation.

## Where the work happens

**Python computes the expensive half at build time.** For each player it
derives a percentile per metric *within his position bucket*, and ships
those. The browser only ever takes a weighted average of numbers that are
already comparable. It never touches raw events and never re-derives a
percentile from per-90 values.

That is why moving a weight slider is free: ~5,600 rows × ~10 weighted
metrics plus a few sorts, single-digit milliseconds, no network.

It is also the reason the pooled **All leagues** view cannot rank across
leagues — see below.

## Two things that look like bugs and are not

**Scores are re-ranked within the bucket, not shown raw.** A raw weighted
mean of percentiles depends on *how many* metrics you gave weight to: the
same centre-backs top out at 79 on a five-metric config and 73 on a
ten-metric one. Re-ranking removes that dependency, so 100 always means
"best centre-back on *your* config", whatever size the config is.

**The "All leagues" view does not claim a European ranking.** Every
percentile is computed *within* a league, and the opponent adjustment behind
it is within-league too — conceding four shots to Manchester City and four
to Sheffield United stop counting the same, but only against sides in the
same competition. Neither can cross a league boundary. Claiming a 90 in one
beats an 88 in another would mean assuming the five leagues are equally
strong, which is false and is the entire reason league coefficients exist.

What it *does* answer: **who is most outstanding relative to the league they
actually play in.** The page says so in amber whenever it is pooled.

## The config is editable, deliberately

Visitors re-weight what counts as good, inside a 100-point budget. That is
the page's whole argument — *not who is best, who does the things you decide
matter*. A fixed ranking is an opinion; a configurable one invites
disagreement and shows its working.

Weights do not persist. A refresh returns to the defaults, and every default
clears the reliability gate.

## Data it reads

```
/data/mental/index.json              which leagues have been built
/data/mental/{league}/meta.json      metrics, buckets, reliability gate
/data/mental/{league}/{view}.json    one file per season + `total`
/data/team/{league}/…                the same shape for sides
```

Written by `scripts/build_mental_web.py` and `scripts/build_team_web.py`.
A league appears here only once `services/data_ready.py` considers it ready
— complete stamped event seasons, not merely present ones.
