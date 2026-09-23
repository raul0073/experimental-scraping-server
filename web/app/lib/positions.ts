/** The nine position buckets, named the way a reader expects to find them.
 *
 *  The KEY stays "WIDE" — it is what the builders write and what every data
 *  file on disk contains, and renaming it would mean rebuilding all of them.
 *  What a reader sees is never the key. "WIDE" on its own names no position:
 *  it reads as an adjective that has lost its noun, which is exactly how it
 *  looked sitting above Saka and Eze.
 *
 *  "AW" is built like the two beside it — DM defensive midfield, AM attacking
 *  midfield, AW attacking winger — so the column decodes itself from its
 *  neighbours. An earlier attempt at "WNG" did not, and the first thing it
 *  was asked was what it meant.
 *
 *  Mirrors BUCKET_SHORT / BUCKET_LABEL in services/mental/positions.py. The
 *  mental index ships the same table, but the team layer does not, and a
 *  nine-row constant is cheaper to keep in both places than a fetch is —
 *  change one and change the other, then rebuild the mental payload.
 */
export const POS_SHORT: Record<string, string> = {
  GK: "GK", FB: "FB", CB: "CB", WB: "WB", DM: "DM",
  CM: "CM", AM: "AM", WIDE: "AW", ST: "ST",
};

export const POS_LABEL: Record<string, string> = {
  GK: "Goalkeeper", FB: "Full-back", CB: "Centre-back", WB: "Wing-back",
  DM: "Defensive midfield", CM: "Central midfield",
  AM: "Attacking midfield", WIDE: "Attacking winger", ST: "Striker",
};

export const POS_ORDER = ["GK", "FB", "CB", "WB", "DM", "CM", "AM", "WIDE", "ST"];

export const posShort = (b: string) => POS_SHORT[b] ?? b;
export const posLabel = (b: string) => POS_LABEL[b] ?? b;
