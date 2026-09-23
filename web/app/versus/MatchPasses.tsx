"use client";

import { PassView } from "../components/three/PassView";
import { TeamHead } from "./TeamHead";

/** How each side moves the ball, side by side.
 *
 *  THE SAME COMPONENT THE LAB TESTED, with the side panel off and the
 *  filters kept. The filters are not a convenience here — a club plays
 *  about 18,000 passes a season and every one on screen is a carpet, not a
 *  map. Which subset you ask for IS the question: crosses for one side
 *  against long balls for the other is a different fixture from two teams
 *  playing through the thirds.
 *
 *  It opens on "led to a shot" for the same reason. That is roughly 350
 *  passes rather than nineteen thousand, it is the subset a preview
 *  actually cares about, and it is legible at half the page width.
 *
 *  What only the 3D version can say: Opta records whether a pass LEFT THE
 *  GROUND, so a forty-metre ball along the floor and a forty-metre diagonal
 *  over the top are drawn as the different actions they are. Lofted passes
 *  arc and drop a shadow; the gap between ball and shadow is the height.
 */
export function MatchPasses({
  home, away, season,
}: {
  home: string; away: string; season: string;
}) {
  return (
    <section className="mt-8">
      <h2 className="text-[16px] font-semibold">How they move it</h2>
      <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
        Every pass this season, filtered to the ones that led to a shot —
        change the filter or pick a player to ask something else. Each ribbon
        widens and brightens toward where the ball was aimed, so direction
        reads without an arrowhead on every one of them, and passes that left
        the ground arc above their own shadow.
      </p>
      <div className="mt-3 grid gap-6 2xl:grid-cols-2">
        {[home, away].map((t) => (
          <div key={t}>
            <TeamHead team={t} />
            <div className="mt-1.5">
              <PassView
                team={t}
                season={season}
                height={420}
                compact
                scene="match-passes"
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
