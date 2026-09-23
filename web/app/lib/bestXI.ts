/** The best eleven a squad can put out — as a TEAM, not as a leaderboard.
 *
 *  Taking the eleven highest-rated players is not a team. A club whose
 *  centre-backs all rate well would field five of them and no striker, and
 *  the picture would say nothing about what they could actually put on the
 *  pitch. So the eleven is built against a SHAPE: a formation names how many
 *  players it wants in each position, and every slot must be filled.
 *
 *  Several shapes are tried and the best TOTAL wins, which means the shape is
 *  an output rather than an assumption. A side with two good wing-backs and
 *  three centre-backs comes out in a back three because that is what its
 *  players are, and a side with two strikers and no winger comes out 4-4-2.
 *
 *  A player can hold only one slot, and a player who is ranked in two
 *  positions — Rice as a CM and as a DM — is considered for both but used
 *  once, at whichever the shape needs more.
 *
 *  FILLED IN TWO PASSES, because greedy alone gets this wrong and the way it
 *  gets it wrong is invisible. Liverpool field no centre-midfielder at all —
 *  Gravenberch, Mac Allister, Jones and Szoboszlai all rank as DMs — and
 *  Szoboszlai qualifies in four positions, Wirtz in two. Taking the best
 *  player for each slot in turn let the wide and holding slots take both of
 *  the only two attacking midfielders, and the shape came out a man short
 *  with no way to notice it had been avoidable.
 *
 *  So: a greedy pass by rating, then AUGMENTING PATHS for whatever is left
 *  over. An empty slot asks a player it wants whether his current slot could
 *  be filled by somebody else, recursively — the standard bipartite matching
 *  step. That guarantees the most slots that CAN be filled are filled, which
 *  is the constraint that matters; among those the rating is greedy rather
 *  than provably optimal, and starting from the rating-ordered pass keeps it
 *  close.
 */
import type { Player } from "../ratings/RatingsData";

export type Slot = {
  /** which bucket fills it */
  bucket: string;
  /** where to draw it: Opta x (0 own goal -> 100 theirs), y (0 right -> 100 left) */
  x: number;
  y: number;
};

export type Formation = { name: string; slots: Slot[] };

/** Shapes that clubs in these leagues actually play. Coordinates are where
 *  the position sits on the pitch, so the eleven can be drawn as a team
 *  sheet rather than listed. */
export const FORMATIONS: Formation[] = [
  {
    name: "4-3-3",
    slots: [
      { bucket: "GK", x: 8, y: 50 },
      { bucket: "FB", x: 30, y: 15 }, { bucket: "CB", x: 24, y: 38 },
      { bucket: "CB", x: 24, y: 62 }, { bucket: "FB", x: 30, y: 85 },
      { bucket: "DM", x: 44, y: 50 },
      { bucket: "CM", x: 55, y: 30 }, { bucket: "CM", x: 55, y: 70 },
      { bucket: "WIDE", x: 76, y: 15 }, { bucket: "ST", x: 82, y: 50 },
      { bucket: "WIDE", x: 76, y: 85 },
    ],
  },
  {
    name: "4-2-3-1",
    slots: [
      { bucket: "GK", x: 8, y: 50 },
      { bucket: "FB", x: 30, y: 15 }, { bucket: "CB", x: 24, y: 38 },
      { bucket: "CB", x: 24, y: 62 }, { bucket: "FB", x: 30, y: 85 },
      { bucket: "DM", x: 44, y: 38 }, { bucket: "DM", x: 44, y: 62 },
      { bucket: "WIDE", x: 68, y: 15 }, { bucket: "AM", x: 66, y: 50 },
      { bucket: "WIDE", x: 68, y: 85 },
      { bucket: "ST", x: 84, y: 50 },
    ],
  },
  {
    name: "4-4-2",
    slots: [
      { bucket: "GK", x: 8, y: 50 },
      { bucket: "FB", x: 30, y: 15 }, { bucket: "CB", x: 24, y: 38 },
      { bucket: "CB", x: 24, y: 62 }, { bucket: "FB", x: 30, y: 85 },
      { bucket: "WIDE", x: 55, y: 15 }, { bucket: "CM", x: 50, y: 38 },
      { bucket: "CM", x: 50, y: 62 }, { bucket: "WIDE", x: 55, y: 85 },
      { bucket: "ST", x: 80, y: 38 }, { bucket: "ST", x: 80, y: 62 },
    ],
  },
  {
    name: "3-4-2-1",
    slots: [
      { bucket: "GK", x: 8, y: 50 },
      { bucket: "CB", x: 24, y: 28 }, { bucket: "CB", x: 22, y: 50 },
      { bucket: "CB", x: 24, y: 72 },
      { bucket: "WB", x: 52, y: 10 }, { bucket: "CM", x: 46, y: 38 },
      { bucket: "CM", x: 46, y: 62 }, { bucket: "WB", x: 52, y: 90 },
      { bucket: "AM", x: 70, y: 32 }, { bucket: "AM", x: 70, y: 68 },
      { bucket: "ST", x: 84, y: 50 },
    ],
  },
  {
    name: "3-5-2",
    slots: [
      { bucket: "GK", x: 8, y: 50 },
      { bucket: "CB", x: 24, y: 28 }, { bucket: "CB", x: 22, y: 50 },
      { bucket: "CB", x: 24, y: 72 },
      { bucket: "WB", x: 54, y: 10 }, { bucket: "DM", x: 44, y: 50 },
      { bucket: "CM", x: 56, y: 33 }, { bucket: "CM", x: 56, y: 67 },
      { bucket: "WB", x: 54, y: 90 },
      { bucket: "ST", x: 82, y: 38 }, { bucket: "ST", x: 82, y: 62 },
    ],
  },
];

export type Picked = { slot: Slot; player: Player; v: number };
export type XI = {
  formation: string;
  picked: Picked[];
  /** mean rating of the eleven */
  rating: number;
  /** slots nobody could fill — a squad with no recognised wing-back */
  unfilled: number;
  /** the share-of-period bar this eleven was picked at, so the page can say
   *  when it had to reach past the regulars to field one */
  minShare?: number;
};

/** Enough football in the role to be picked on it, as a SHARE of the period
 *  rather than a count of minutes. A player with one afternoon at right-back
 *  can land anywhere in a percentile and would otherwise walk into the side.
 *
 *  Share, not minutes, because a fixed 270-minute floor is a different bar in
 *  a four-match season than in a thirty-eight-match one: on the current
 *  season it left Arsenal with ten qualifying players, one short, and the
 *  whole eleven silently disappeared off the page. The bar relaxes rather
 *  than breaks — a side is always shown the best it can field, with the
 *  thinner basis stated. */
const SHARE_STEPS = [35, 20, 10, 0];

function fill(
  formation: Formation,
  pool: { p: Player; v: number }[],
): XI {
  const byBucket = new Map<string, { p: Player; v: number }[]>();
  for (const e of pool) {
    const list = byBucket.get(e.p.p) ?? [];
    list.push(e);
    byBucket.set(e.p.p, list);
  }
  for (const list of byBucket.values()) list.sort((a, b) => b.v - a.v);

  const slots = formation.slots;
  /** slot index -> the player in it; and the reverse */
  const at = new Map<number, { p: Player; v: number }>();
  const owner = new Map<string, number>();

  // PASS ONE — greedy, best rating first, so the strong assignments are made
  // before anything has to compromise.
  const scarcity = new Map<string, number>();
  for (const s of slots) scarcity.set(s.bucket, (scarcity.get(s.bucket) ?? 0) + 1);
  const order = slots
    .map((s, i) => i)
    .sort((a, b) => {
      const ca = (byBucket.get(slots[a].bucket)?.length ?? 0)
        / (scarcity.get(slots[a].bucket) ?? 1);
      const cb = (byBucket.get(slots[b].bucket)?.length ?? 0)
        / (scarcity.get(slots[b].bucket) ?? 1);
      return ca - cb;
    });
  for (const i of order) {
    const cand = (byBucket.get(slots[i].bucket) ?? [])
      .find((e) => !owner.has(e.p.n));
    if (!cand) continue;
    at.set(i, cand);
    owner.set(cand.p.n, i);
  }

  // PASS TWO — augmenting paths for whatever is still empty. An empty slot
  // asks each player it could use whether HIS slot can be refilled by someone
  // else, and so on down. This is the step plain greedy cannot do, and the
  // one that gets Liverpool their attacking midfielder back.
  const augment = (slot: number, seen: Set<string>): boolean => {
    for (const cand of byBucket.get(slots[slot].bucket) ?? []) {
      if (seen.has(cand.p.n)) continue;
      seen.add(cand.p.n);
      const held = owner.get(cand.p.n);
      if (held === undefined || augment(held, seen)) {
        at.set(slot, cand);
        owner.set(cand.p.n, slot);
        return true;
      }
    }
    return false;
  };
  for (let i = 0; i < slots.length; i++) {
    if (!at.has(i)) augment(i, new Set());
  }

  const picked: Picked[] = [];
  let unfilled = 0;
  for (let i = 0; i < slots.length; i++) {
    const got = at.get(i);
    if (!got) unfilled += 1;
    else picked.push({ slot: slots[i], player: got.p, v: got.v });
  }
  const rating = picked.length
    ? picked.reduce((a, e) => a + e.v, 0) / picked.length
    : 0;
  return { formation: formation.name, picked, rating, unfilled };
}

/**
 * @param all   every player in the league for this period, already rated
 * @param team  the club to pick from
 * @param rate  a player's percentile inside his own position
 */
export function bestXI(
  all: Player[],
  team: string,
  rate: (p: Player) => number,
): XI | null {
  const mine = all.filter((p) => p.t === team);
  if (!mine.length) return null;

  // Step the bar down until a whole eleven appears. Stopping at the first
  // threshold that works keeps the strictest basis that still produces a
  // team, instead of either a hole or a page with nothing on it.
  let best: XI | null = null;
  let share = SHARE_STEPS[SHARE_STEPS.length - 1];
  for (const step of SHARE_STEPS) {
    const pool = mine
      .filter((p) => p.rs >= step)
      .map((p) => ({ p, v: rate(p) }));
    if (pool.length < 11) continue;
    const tries = FORMATIONS.map((f) => fill(f, pool));
    // An unfilled slot disqualifies a shape before a low score does: a back
    // three with two centre-backs is not a worse shape, it is not that shape.
    const whole = tries.filter((x) => x.unfilled === 0);
    const pick = (whole.length ? whole : tries).sort(
      (a, b) => a.unfilled - b.unfilled || b.rating - a.rating,
    )[0];
    if (!pick) continue;
    best = pick;
    share = step;
    if (pick.unfilled === 0) break;
  }
  return best ? { ...best, minShare: share } : null;
}
