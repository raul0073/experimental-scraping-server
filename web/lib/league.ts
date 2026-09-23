/** League name helpers, with no filesystem attached.
 *
 *  WHY THESE LIVE APART FROM data.ts. That module opens the exported JSON
 *  with node:fs at import time, which is correct for a static site built at
 *  compile time — but it means any "use client" component that imports a
 *  VALUE from it drags node:fs into the browser bundle, and the build dies
 *  with "the chunking context does not support external modules". Types are
 *  erased so `import type` is always safe; functions are not.
 *
 *  The visible cost of not having this file: slugify is currently copied
 *  into three client components, and copies drift. Anything pure that both
 *  sides need belongs here, and data.ts re-exports it so server code can
 *  carry on importing from one place.
 */
export const slugify = (league: string) =>
  league.toLowerCase().replace(/[ _]/g, "-");

/** "ENG-Premier League" → "Premier League". */
export const leagueShort = (league: string) => league.split("-")[1] ?? league;
