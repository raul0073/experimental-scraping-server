# `/managers` — the manager ranking

Two halves, kept apart on purpose. One is scored, on **your** weights. The
other is never scored at all.

## The claim, and the claim it is not

A manager ranking is the easiest page on a football site to make dishonest,
because a manager's results are mostly his squad's. This one scores only the
things he demonstrably decides — what the opponent gets once his side is in
front, what his side does once it is behind, what changed over the interval,
what the bench did, what he gives away — and shows everything else as a
**fingerprint** that carries no verdict.

Three rules the page enforces on itself:

1. **A short spell is shrunk, never excluded.** Four matches cannot tell a
   good manager from a lucky fortnight, so the score is pulled toward 50 by
   `matches / (matches + 8)` and the table prints both numbers and the
   fraction kept. A caretaker at 52 must be visibly 52 *for want of evidence*.
2. **Style is never scored.** Pressing high is not better than sitting off.
   The fingerprint has no sliders, no totals, and no good/bad colour — the two
   colours in it are the two managers being compared, nothing more.
3. **Percentiles are within one league.** There is no pooled view and there
   should not be one: the event feed is the same across Europe, the football
   is not.

## Files

```
page.tsx          route shell — the h1 and the standing claim
ManagerBoard.tsx  the data layer: index, league choice, payload, weights,
                  scoring, sorting, and the A/B selection
RankTable.tsx     the ranking — a table on a laptop, cards on a phone
Fingerprint.tsx   the radar and the percentile strip, for two managers
WeightEditor.tsx  the reader's config, inside a 100-point budget
weights.ts        the localStorage store, via useSyncExternalStore
contract.ts       payload types, the scoring maths, labels, defaults
Hint.tsx          a help popover that cannot push a phone screen sideways
sample.ts         invented rows, reachable only from the empty state
```

## Where the work happens

**Python computes the expensive half at build time.** Per metric, per manager
spell, a percentile *within the league*, with the opponent adjustment already
fitted across the whole league-season. The browser only ever takes a weighted
mean of numbers that are already comparable, then shrinks it. It never touches
an event and never re-derives a percentile.

That is why moving a weight is free, and why re-weighting needs no rebuild.

## The one contract detail to get right

**`pct` is the percentile of the raw value, UNFLIPPED.** Direction is applied
in the browser, by `orient()` in `contract.ts`, from the metric's own `invert`
flag. That is why `invert` is in the payload at all — if Python flipped the
percentile before shipping it, this page would flip it a second time and the
four inverted metrics would score backwards.

If that ever has to change, change `orient` and nothing else.

## Data it reads

```
/data/managers/index.json          which leagues have been built
/data/managers/{league}.json       metrics + one row per manager spell
/data/team/{league}/meta.json      badges only; a failure here costs nothing
```

`index.json` is the same shape as `/data/team/index.json` —
`{"leagues":[{"key","label"}]}` — and the builder **merges** into it rather
than overwriting, which is a bug three separate builders in this repo have
already shipped once each.

Until those files exist the page shows a real empty state, with a button that
draws the layout from invented numbers behind a banner saying so. That sample
is never a fallback for a payload that failed to load.

## Two things that look like bugs and are not

**The score on screen is not the `score` in the payload.** The payload's
`score` was computed with the pipeline's own weights; the ring shows *yours*.
Where shrinkage moved a row, hovering the arrow beside it gives the raw
figure, the shrinkage, and the published value for comparison.

**Scores are not re-ranked within the pool.** The player board re-ranks so
that 100 always means "best on your config" whatever its size. This one does
not, deliberately: re-ranking would undo the visible effect of shrinkage and
put a four-match caretaker back at the top of the table.

## Responsiveness

Usable at 375px with no horizontal page scroll, which took two specific
decisions. The fourteen-column table is `hidden sm:block` and a card list
takes its place on a phone — a table that wide is not made usable by letting
the reader swipe it. And the help popovers are anchored to their **row**
(`inset-x-0`) rather than to their icon: the site's shared `Info` is a fixed
288px box that, anchored to an icon sitting 130px into a narrow row, runs off
a 375px screen by about ninety and takes the whole document sideways with it.
`Info` is still used unchanged in the table headers, where there is room.
