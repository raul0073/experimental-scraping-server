/** Joining one feed's club names to another's.
 *
 *  🐛 THE FIXTURE LINKS RESOLVED FOR FOUR OF TEN MATCHES. The weekly round
 *  export and the team layer are written from different feeds and do not
 *  agree on names, in both directions at once:
 *
 *      round.json          team layer
 *      Coventry City       Coventry          (round is longer)
 *      Hull City           Hull
 *      Ipswich Town        Ipswich
 *      Leeds United        Leeds
 *      Nottingham          Nottingham Forest (round is SHORTER)
 *      Manchester City     Man City          (abbreviated)
 *      Manchester Utd      Man Utd
 *
 *  So neither "is a prefix of" nor "starts with" in one direction is enough,
 *  and an exact match covers thirteen of twenty.
 *
 *  THIS IS A PORT, NOT A NEW IDEA. `scripts/build_injury_web.py` already
 *  solved exactly this to land absentees on the right club, and inventing a
 *  second rule here would mean two rules that drift apart and a club that
 *  joins on one page and not the other. Same tokens, same prefix test, same
 *  refusal to guess when two candidates fit.
 */

/** "utd" is not a prefix of "united" and "united" is not a prefix of "utd",
 *  so the prefix rule alone cannot join "Manchester Utd" to "Man Utd" — the
 *  one club it fails on. Everything else the abbreviation covers
 *  (man/manchester) is already a prefix and needs nothing. */
const SAME: Record<string, string> = { utd: "united" };
const DROP = new Set(["fc", "afc", "cf"]);

function tokens(name: string): string[] {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .filter((w) => w && !DROP.has(w))
    .map((w) => SAME[w] ?? w);
}

/** Every word of the shorter name must prefix a DISTINCT word of the longer.
 *  Distinct matters: without it "Leeds Leeds" would fit anything starting
 *  with Leeds twice over. */
function fits(short: string[], long: string[]): boolean {
  const used = new Set<number>();
  for (const w of short) {
    const hit = long.findIndex(
      (v, i) => !used.has(i) && (v.startsWith(w) || w.startsWith(v)),
    );
    if (hit < 0) return false;
    used.add(hit);
  }
  return true;
}

/** The one club in `candidates` that `name` means, or null.
 *
 *  AN AMBIGUOUS MATCH IS DROPPED RATHER THAN GUESSED. "Man Utd" reaches
 *  "Manchester Utd" and cannot reach "Manchester City", because utd prefixes
 *  nothing there — but a bare "Manchester" would fit both, and silently
 *  picking one is how a page ends up quietly showing the wrong club.
 */
export function matchTeam(name: string, candidates: string[]): string | null {
  if (!name) return null;
  if (candidates.includes(name)) return name;
  const a = tokens(name);
  const hits = candidates.filter((b) => {
    const t = tokens(b);
    return fits(a, t) || fits(t, a);
  });
  return hits.length === 1 ? hits[0] : null;
}
