import type { MetadataRoute } from "next";

/** robots.txt, generated at build time into the static export.
 *
 *  The two disallowed paths are not secrets — /admin already returns a 404 in
 *  production and /lab is a component workbench — they are simply not pages
 *  anyone searching for football should be given. Saying so here also keeps
 *  them out of the crawl budget for a site whose real content is the
 *  predictor, the ratings and the record.
 *
 *  /data is the payload directory the pages fetch from. It is derived metrics
 *  only — no raw event stream ever reaches it — but a crawler indexing a few
 *  hundred JSON files serves nobody, so it is excluded too.
 */
const SITE = "https://predictorous.com";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/admin", "/lab", "/data/"],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
