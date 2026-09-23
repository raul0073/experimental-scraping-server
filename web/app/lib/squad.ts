/** Team mental — the players a club has — in ONE place.
 *
 *  The team page and the versus page both need it and it is not a small
 *  calculation: every player percentiled inside his own position on the
 *  reader's weights, then weighted by the minutes he played there. Two copies
 *  would drift the moment one of them learned something the other did not,
 *  and a club would score 61 on one page and 58 on the next.
 */
import type { Player } from "../ratings/RatingsData";
import { POS_ORDER } from "./positions";

export type Rel = Record<string, Record<string, { rho: number }>> | undefined;

export type SquadGroup = {
  bucket: string;
  minutes: number;
  score: number | undefined;
  players: { p: Player; v: number }[];
};

export type Squad = {
  rating: number;
  byBucket: SquadGroup[];
  weak: SquadGroup | undefined;
  n: number;
  /** bucket -> rating, for a position-by-position comparison */
  at: Record<string, number>;
};

/** A position a club barely fields is a shape, not a hole: Liverpool have no
 *  wing-backs and should not be marked down for it. */
const FIELDED = 0.04;

export function scorePlayer(
  p: Player,
  allWeights: Record<string, Record<string, number>>,
  reliability: Rel,
): number {
  let s = 0;
  let used = 0;
  for (const [k, w] of Object.entries(allWeights[p.p] ?? {})) {
    if (w <= 0) continue;
    const r = reliability?.[k]?.[p.p];
    if (r !== undefined && r.rho < 0.4) continue;
    s += (p.qa[k] ?? 50) * w;
    used += w;
  }
  return used ? s / used : 50;
}

/** Percentile every player inside his own bucket, across the WHOLE league —
 *  then keep this club's. Ranking within the club would make every side have
 *  a best and worst player and say nothing about the league. */
export function buildSquad(
  all: Player[],
  team: string,
  allWeights: Record<string, Record<string, number>>,
  reliability: Rel,
): Squad {
  const pct = new Map<Player, number>();
  const byB: Record<string, Player[]> = {};
  for (const p of all) (byB[p.p] ??= []).push(p);
  for (const list of Object.values(byB)) {
    const sorted = list
      .map((p) => ({ p, v: scorePlayer(p, allWeights, reliability) }))
      .sort((a, b) => a.v - b.v);
    sorted.forEach((e, i) =>
      pct.set(e.p, sorted.length > 1 ? (i / (sorted.length - 1)) * 100 : 50),
    );
  }
  const mine = all
    .filter((p) => p.t === team)
    .map((p) => ({ p, v: pct.get(p) ?? 50 }));
  const den = mine.reduce((a, e) => a + e.p.m, 0);
  const byBucket = POS_ORDER.map((bucket) => {
    const inB = mine.filter((e) => e.p.p === bucket);
    const d = inB.reduce((a, e) => a + e.p.m, 0);
    return {
      bucket,
      minutes: d,
      score: d ? inB.reduce((a, e) => a + e.v * e.p.m, 0) / d : undefined,
      players: inB.sort((a, b) => b.v - a.v),
    };
  }).filter((g) => g.minutes >= den * FIELDED);
  const at: Record<string, number> = {};
  for (const g of byBucket) if (g.score !== undefined) at[g.bucket] = g.score;
  return {
    rating: den ? mine.reduce((a, e) => a + e.v * e.p.m, 0) / den : 50,
    byBucket,
    weak: [...byBucket].sort((a, b) => (a.score ?? 99) - (b.score ?? 99))[0],
    n: mine.length,
    at,
  };
}
