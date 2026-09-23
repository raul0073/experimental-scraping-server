import { Suspense } from "react";

import { getRound } from "@/lib/data";

import { VersusPage } from "./VersusPage";

/** THE FIXTURE PAGE.
 *
 *  It began as "one side against another, zone by zone" — a place you went
 *  to and picked two clubs. It is now where a fixture from the predictor
 *  opens, with the model's call at the top and the evidence underneath,
 *  because a probability published on its own is the least trustworthy
 *  thing on the site and this is the page that can show its working.
 *
 *  The two clubs can still be chosen by hand. That is how you look at a
 *  match that is not this weekend's, and it costs nothing to keep.
 *
 *  ROUND DATA ARRIVES AS A PROP, not as a fetch. The weekly export is read
 *  at BUILD time from data/web and is not served as a public asset, so a
 *  client component cannot go and get it — this server shell reads it once
 *  and hands it down, which is the same thing the predictor page does.
 */
export const metadata = {
  title: "Fixture — Predictorous",
  description:
    "One fixture: what the model expects, and the evidence underneath it.",
};

export default function Page() {
  /** THE SUSPENSE BOUNDARY IS NOT DECORATION. `useSearchParams` cannot be
   *  resolved while a page is being prerendered — there is no request — so
   *  Next refuses to build the route unless the part that reads it is
   *  wrapped, and the build fails with "Error occurred prerendering page".
   *  The shell around it still renders statically; only the half that wants
   *  to know which fixture you asked for waits. */
  return (
    <Suspense
      fallback={<p className="text-[13.5px] text-ink-2">Loading…</p>}
    >
      <VersusPage round={getRound()} />
    </Suspense>
  );
}
