"use client";

import { Crumbs } from "../components/Crumbs";
import { Tabs, useTab } from "../components/Tabs";
import { Monkey } from "./Monkey";
import { Picks } from "./Picks";
import { Record } from "./Record";

/** THE BETTING WORKBENCH — three questions about the same model.
 *
 *  Picks is what it says this round. Track record is every call it has ever
 *  committed and how those turned out. Monkey is the only one of the three
 *  that can embarrass anybody: a bankroll that actually followed the advice,
 *  from a 1000 start, graded at the fair prices frozen when each slip was
 *  recommended. A page that shows the first two without the third is a
 *  tipping page; the third is what makes the other two worth reading.
 *
 *  Development only, and the guard is in layout.tsx rather than here — that
 *  file explains why a message in a component would not have been enough.
 *
 *  WHICH TAB IS OPEN LIVES IN THE URL, through the same `useTab` the rest of
 *  the site uses. Three fetches hang off these tabs and a reload that dumps
 *  the reader back on the first one re-runs the wrong one.
 */
const TABS = ["picks", "record", "monkey"] as const;
type Tab = (typeof TABS)[number];

/** Spelled out rather than built with the `Record` utility type, which the
 *  Record tab's own name would sit uncomfortably close to in this file. */
const LABELS: { [K in Tab]: string } = {
  picks: "picks",
  record: "track record",
  monkey: "monkey",
};

export default function BettingPage() {
  const [tab, setTab] = useTab<Tab>("tab", TABS);

  return (
    <div>
      <Crumbs trail={[{ label: "Betting" }]} />

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-display text-[24px] tracking-[0.01em]">Betting</h1>
        <span className="text-[11px] uppercase tracking-wider text-ink-3">
          development only
        </span>
      </div>

      {/* WHAT THIS IS, AND WHAT IT IS NOT. Said once, at the top, in the
          register the rest of the site uses: the numbers are the model's own
          and the page does not pretend to know more than they do. */}
      <p className="mt-3 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        Every figure on these three tabs is the model&apos;s own arithmetic: a
        probability, and the <strong className="font-semibold">fair price</strong>{" "}
        that probability implies — 1/p, the price at which a bet is a coin flip
        with no edge in either direction.{" "}
        <strong className="font-semibold">No bookmaker&apos;s odds are fetched,
        shown or compared against anywhere here</strong>, so nothing on this page
        can tell you a bet is good value; that comparison is yours to make
        against the prices you are actually offered. What it can do is keep an
        honest account — what was said before kickoff, what happened, and what a
        bankroll that followed the advice would be worth now, losing rounds
        included. It is a workbench for reading one model, not advice to stake
        money.
      </p>
      <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
        None of this is published. The route is never emitted into the public
        site, and the numbers come from the local API on :8080 rather than from
        anything the site ships — so start <span className="num">main.py</span>{" "}
        before expecting a tab to fill.
      </p>

      <div className="mt-5">
        <Tabs tabs={TABS} value={tab} onChange={setTab} labels={LABELS} />
      </div>

      <div className="mt-6">
        {tab === "picks" && <Picks />}
        {tab === "record" && <Record />}
        {tab === "monkey" && <Monkey />}
      </div>
    </div>
  );
}
