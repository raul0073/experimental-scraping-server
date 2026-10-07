import { notFound } from "next/navigation";

/** The betting section does not exist in a production build.
 *
 *  THIS IS THE ONE RULE THE SECTION CANNOT GET WRONG. A public page that
 *  lists forms, stakes and a bankroll is a tipping page, whatever the words
 *  on it say — and this is a workbench for one person reading his own model.
 *
 *  A component-level "development only" message would not do it. The page
 *  would still be emitted as betting.html into out/, still ship its
 *  JavaScript, and the route's own name would still announce what the site
 *  keeps behind it. Calling notFound() here means the segment is never
 *  emitted at all: no HTML, no chunk, no entry in the export manifest. There
 *  is nothing to find and nothing to guess at.
 *
 *  The other half of the rule lives in api.ts: every figure is fetched from
 *  the local API at request time, so no betting payload is ever written into
 *  web/public/data, which is copied wholesale into the published site.
 *
 *  In development this is a pass-through and the section behaves normally.
 */
export default function BettingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  if (process.env.NODE_ENV !== "development") notFound();
  return <>{children}</>;
}
