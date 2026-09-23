"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { Crumbs } from "../components/Crumbs";
import { ManagerBoard } from "./ManagerBoard";
import { PlayerBoard } from "./PlayerBoard";
import { RatingsData } from "./RatingsData";
import { EloTable } from "./EloTable";
import { TeamBoard } from "./TeamBoard";

/** Three views of one question, so one tab rather than three pages —
 *  managers included, because a manager ranking is not a separate subject
 *  from a team one. It is the same football asked about a different unit, and
 *  the reader arrives at it from the same place. */
type Tab = "players" | "teams" | "managers";
const TABS: Tab[] = ["players", "teams", "managers"];

/** Players and teams are two views of one question, so they live under one
 *  tab rather than two. The intro changes with the view because they are
 *  genuinely different claims: a player is judged on what he does at his own
 *  job, a team on how well it does the things it chooses to do.
 *
 *  Which view is showing lives in the URL as well as in state, so a team page
 *  can link BACK to the teams table rather than dropping the reader on the
 *  players one. Read once on mount and written with replaceState — a Next
 *  navigation would remount the boards and throw away the loaded payload, and
 *  a static export has no server to ask anyway. */
export function RatingsTabs() {
  const [tab, setTab] = useState<Tab>("players");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    if ((TABS as string[]).includes(t ?? "")) setTab(t as Tab);
  }, []);
  const pick = (t: Tab) => {
    setTab(t);
    const u = new URL(window.location.href);
    if (t === "players") u.searchParams.delete("tab");
    else u.searchParams.set("tab", t);
    window.history.replaceState(null, "", u);
  };
  return (
    <RatingsData>
    <div>
      <Crumbs trail={[{ label: "Ratings" }]} />
      <div className="flex gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => pick(t)}
            className={`rounded-full border px-4 py-1 text-[13px] font-medium capitalize transition-colors ${
              tab === t
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "players" && (
        <>
          <p className="mt-4 max-w-3xl text-[13.5px] text-ink-2">
            Not who is best — who does the things you decide matter. Every
            metric is measured from Opta event streams, and{" "}
            <strong className="font-semibold">you set the recipe</strong>: what
            counts as mental for a centre-back is not what counts for a winger,
            and it is not for a model to decide.
          </p>
          <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
            One rule the page enforces: a metric that cannot reproduce itself
            from one season to the next is measuring luck, not character. Those
            are marked in red and ignored by default — you can switch that off,
            but the colour stays.{" "}
            <Link
              href="/how-it-works"
              className="text-home underline underline-offset-2"
            >
              How these are measured
            </Link>
            .
          </p>
          <div className="mt-6">
            <PlayerBoard />
          </div>
        </>
      )}
      {tab === "teams" && (
        <>
          <p className="mt-4 max-w-3xl text-[13.5px] text-ink-2">
            The same idea asked of a side, with two things kept apart on
            purpose. <strong className="font-semibold">Style</strong> is how a
            team plays and is never scored — going long is not worse than
            playing out, and high tempo is neither good nor bad.{" "}
            <strong className="font-semibold">Quality</strong> is how well it
            goes, and it is the only thing weighted.
          </p>
          <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
            Every quality number is opponent-adjusted across the whole league,
            so conceding four shots to Manchester City and four to Sheffield
            United stop counting the same. Click a club to see it broken down
            by manager — the cut the predictor will read, because what matters
            for Saturday is this side under this manager.{" "}
            <Link
              href="/how-it-works"
              className="text-home underline underline-offset-2"
            >
              How these are measured
            </Link>
            .
          </p>
          <div className="mt-6">
            <TeamBoard />
          </div>
          <div className="mt-10">
            <EloTable />
          </div>
        </>
      )}
      {tab === "managers" && (
        <>
          {/* THE CLAIM, AND THE CLAIM IT IS NOT. A manager ranking is the
              easiest page on a football site to make dishonest, because a
              manager's results are mostly his squad's. So it states its
              limits on the way in. */}
          <p className="mt-4 max-w-3xl text-[13.5px] text-ink-2">
            One row per spell — a manager at a club, stitched from the man
            named on each match. The score covers only things a manager
            demonstrably decides: what the opponent gets once his side is in
            front, what his side does once it is behind, what changed over the
            interval, what the bench did, and what he gives away.{" "}
            <strong className="font-semibold">You set the weights.</strong>
          </p>
          <p className="mt-2 max-w-3xl text-[12.5px] text-ink-3">
            Two rules it holds itself to. A short spell is <em>shrunk</em>,
            never excluded — four matches cannot tell a good manager from a
            lucky fortnight, so its score is pulled toward average and the
            table says by how much. And style is never scored: pressing high
            is not better than sitting off, and the moment a table ranks it,
            it has started asserting that one way of playing is correct.{" "}
            <Link
              href="/how-it-works"
              className="text-home underline underline-offset-2"
            >
              How these are measured
            </Link>
            .
          </p>
          <div className="mt-6">
            <ManagerBoard />
          </div>
        </>
      )}
    </div>
    </RatingsData>
  );
}
