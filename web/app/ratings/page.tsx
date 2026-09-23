import { RatingsTabs } from "./RatingsTabs";

/** 🏷️ RENAMED FROM "MENTAL", AND THE NAME WAS THE PROBLEM.
 *
 *  A "mental ranking" promises psychology and delivers event metrics, so
 *  every reader — including the one who commissioned it — arrives asking
 *  what it is claiming and does not get a clean answer. The same correction
 *  was already made for the team layer, in the user's own words: it is NOT a
 *  temperament measure, it is a CAPABILITY PROFILE — how good are they,
 *  broken down into what good means. This applies it to the player side and
 *  to the route.
 *
 *  Nothing about the measurement changed. What changed is that the page no
 *  longer claims to have measured a mind.
 */
export const metadata = {
  title: "Ratings — Predictorous",
  description:
    "What players and sides actually do, measured from event streams.",
};

export default function RatingsPage() {
  return (
    <div>
      <h1 className="font-display text-[24px] tracking-[0.01em]">
        Players and sides
      </h1>
      <p className="mt-1.5 max-w-3xl text-[13.5px] leading-relaxed text-ink-2">
        What they do, measured from roughly fifteen hundred events a match —
        not what they are like. A capability profile, broken down into what
        good means for the job each of them actually has.
      </p>
      <div className="mt-4">
        <RatingsTabs />
      </div>
    </div>
  );
}
