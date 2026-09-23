"use client";

import { ShotView } from "../components/three/ShotView";
import { TeamHead } from "./TeamHead";

/** The chances in this fixture, as two matchups rather than two toggles.
 *
 *  🐛 THE FIRST VERSION ASKED THE READER TO DO THE WORK. It showed both
 *  sides' attempts and put "shots they face" behind a tab, so comparing an
 *  attack with the defence it is about meant flipping between two states and
 *  holding the first in your head. That is the same mistake as drawing one
 *  undirected pass line: the information was there and the picture refused
 *  to make the comparison.
 *
 *  So the pairing IS the layout. One row per phase — this side's attempts
 *  beside what the other side concedes — which is the same shape the zone
 *  maps use, and for the same reason. No tabs.
 *
 *  BOTH HALVES ARE DRAWN IN THE SHOOTER'S OWN ATTACKING FRAME. "Where does
 *  Villa get got at from" is a question about where the attacker stood, and
 *  mirroring it into Villa's half would answer a different question while
 *  looking identical — the mirror trap that had this project drawing every
 *  winger on the wrong flank for weeks.
 */
function Phase({
  attack, defend, season,
}: {
  attack: string; defend: string; season: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <TeamHead team={attack} />
        <span className="text-[14px] font-semibold text-ink">attacking</span>
      </div>
      <p className="mt-0.5 text-[12px] leading-relaxed text-ink-3">
        Their attempts, against every attempt {defend} have faced this
        season — the same patch of pitch, from both ends of the question.
      </p>
      <div className="mt-2.5 grid gap-5 2xl:grid-cols-2">
        <div>
          <TeamHead
            team={attack}
            note="took"
            size={16}
            className="text-[12px] font-semibold text-ink-2"
          />
          <ShotView team={attack} season={season} side="taken" height={400} compact />
        </div>
        <div>
          <TeamHead
            team={defend}
            note="conceded from"
            size={16}
            className="text-[12px] font-semibold text-ink-2"
          />
          <ShotView team={defend} season={season} side="faced" height={400} compact />
        </div>
      </div>
    </div>
  );
}

export function MatchShots({
  home, away, season,
}: {
  home: string; away: string; season: string;
}) {
  return (
    <section className="mt-8">
      <h2 className="text-[16px] font-semibold">The chances</h2>
      <p className="mt-1 max-w-4xl text-[12.5px] leading-relaxed text-ink-2">
        Area is xG — a 0.40 chance covers four times the ground of a 0.10
        one, which is the honest way to draw it — and colour is what became
        of it. Click a shot to stand behind the shooter and see the goal he
        actually had.
      </p>
      <div className="mt-3 space-y-6">
        <Phase attack={home} defend={away} season={season} />
        <Phase attack={away} defend={home} season={season} />
      </div>
    </section>
  );
}
