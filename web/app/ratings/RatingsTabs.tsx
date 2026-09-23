"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { Crumbs } from "../components/Crumbs";
import { PlayerBoard } from "./PlayerBoard";
import { RatingsData } from "./RatingsData";
import { EloTable } from "./EloTable";
import { TeamBoard } from "./TeamBoard";

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
  const [tab, setTab] = useState<"players" | "teams">("players");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t === "teams" || t === "players") setTab(t);
  }, []);
  const pick = (t: "players" | "teams") => {
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
        {(["players", "teams"] as const).map((t) => (
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

      {tab === "players" ? (
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
      ) : (
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
    </div>
    </RatingsData>
  );
}
