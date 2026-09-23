import type { MetadataRoute } from "next";

import teamIndex from "../public/data/team/index.json";

/** THE SITEMAP, GENERATED FROM WHAT WAS ACTUALLY BUILT.
 *
 *  A hand-written list is a list that goes stale the first time a route is
 *  added, and this site's largest section — one page per club — is generated
 *  from a payload rather than written by hand. So the club pages are read
 *  from the same index the pages themselves are generated from: if a league
 *  is not built, its clubs are not in the sitemap, which is correct, because
 *  those pages do not exist.
 *
 *  `output: "export"` turns this into a static sitemap.xml at build time.
 *  Nothing here runs in production.
 *
 *  Deliberately absent: /admin (404s in production), /lab (a component
 *  workbench), and /predictor (a redirect stub that carries noindex).
 */
const SITE = "https://predictorous.com";

/** Must match the slug the team pages are generated under — see
 *  generateStaticParams in app/team/[slug]/page.tsx. */
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

type LeagueRef = { key: string; label: string };

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const fixed: MetadataRoute.Sitemap = [
    // The front page IS the predictor, so it carries the highest weight.
    { url: SITE, lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/ratings`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/how-it-works`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE}/predictor/history`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITE}/predictor/projected`, lastModified: now, changeFrequency: "daily", priority: 0.7 },
    // The graveyard of rejected experiments. Low priority, but it is the page
    // that most distinguishes this site from every other prediction site, so
    // it does not get left out.
    { url: `${SITE}/rejected`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE}/versus`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
  ];

  const leagues = ((teamIndex as { leagues?: LeagueRef[] }).leagues ?? []).map(
    (l) => ({
      url: `${SITE}/predictor/history/${l.key}`,
      lastModified: now,
      changeFrequency: "daily" as const,
      priority: 0.6,
    }),
  );

  return [...fixed, ...leagues];
}
