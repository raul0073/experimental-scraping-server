import fs from "node:fs";
import path from "node:path";

import { TeamPage } from "./TeamPage";

/** The site is a static export, so every club gets a real page built at
 *  compile time.
 *
 *  From the UNION of the pooled table and the per-season one, not from the
 *  pooled table alone. A club promoted this summer has four matches, which is
 *  under the floor that keeps one-season sides out of an all-time table, so
 *  it has no pooled row — and with `output: export` a route that was never
 *  generated is not a soft 404, it is a build-time error and a dead link.
 *  Coventry and Hull were both linked from the board and neither had a page.
 */
function clubs(): { slug: string; team: string }[] {
  const dir = path.join(
    process.cwd(),
    "public",
    "data",
    "team",
    "eng-premier-league",
  );
  const read = (f: string) =>
    JSON.parse(fs.readFileSync(path.join(dir, f), "utf-8")) as {
      team: string;
    }[];
  const names = new Set<string>();
  for (const f of ["club.json", "club_season.json"]) {
    for (const r of read(f)) if (r.team) names.add(r.team);
  }
  return [...names]
    .sort()
    .map((team) => ({ slug: slugify(team), team }));
}

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function generateStaticParams() {
  return clubs().map((c) => ({ slug: c.slug }));
}

export default async function Page({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const club = clubs().find((c) => c.slug === slug);
  return <TeamPage slug={slug} team={club?.team ?? slug} />;
}
