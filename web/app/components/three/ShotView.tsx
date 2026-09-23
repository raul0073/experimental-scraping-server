"use client";

import { useEffect, useMemo, useState } from "react";

import { matchTeam } from "../../lib/teamName";
import { PitchScene, defaultCam, type ViewName } from "./PitchScene";
import {
  RESULT_COLOUR, RESULT_LABEL, ShotCloud, corner, eyeOf, geometry, goalEndOf,
  goalZOf, shotX, shotZ,
  type Shot,
} from "./ShotCloud";

/** A club's shots, on three quarters of a pitch, with the geometry on click. */

type Payload = {
  keys: string[];
  results: string[];
  situations: string[];
  feet: string[];
  players: string[];
  opponents: string[];
  teams: Record<string, number[][]>;
};

const DATA = "/data/shots/eng-premier-league";

function unpack(p: Payload, rows: number[][]): Shot[] {
  return rows.map((r) => ({
    x: r[0], y: r[1], xg: r[2],
    result: p.results[r[3]] ?? "MissedShots",
    situation: p.situations[r[4]] ?? "OpenPlay",
    foot: p.feet[r[5]] ?? "",
    minute: r[6],
    player: p.players[r[7]] ?? "",
    assist: r[8] >= 0 ? p.players[r[8]] ?? "" : "",
    opponent: p.opponents[r[9]] ?? "",
    home: r[10] === 1,
    gx: typeof r[11] === "number" ? r[11] : null,
    gz: typeof r[12] === "number" ? r[12] : null,
  }));
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "Goal", label: "Goals" },
  { key: "big", label: "Big chances" },
  { key: "OpenPlay", label: "Open play" },
  { key: "set", label: "Set pieces" },
] as const;

export function ShotView({
  team, season = "2526", height = 520, tune = false, side = "taken",
  compact = false,
}: {
  team: string; season?: string; height?: number;
  /** show the camera tuner — lab only, see PitchScene */
  tune?: boolean;
  /** SHOTS THEY TOOK, OR SHOTS THEY FACED. Faced needs no new data: the
   *  league file already holds every club's attempts with the opponent on
   *  each row, so the shots against a side are just everyone else's rows
   *  filtered to them. They are drawn UNMIRRORED — in the shooter's own
   *  attacking frame — because the question is where the opposition got
   *  their chances from, not where they sat relative to this team's goal. */
  side?: "taken" | "faced";
  /** drop the filters and the side panel, for a match page where two of
   *  these sit beside each other */
  compact?: boolean;
}) {
  const [data, setData] = useState<Payload | null>(null);
  /** The selection carries the filter it was made under, so changing the
   *  filter drops it during render instead of in an effect — index 12 of
   *  "goals" is not index 12 of "big chances", and clearing it afterwards
   *  costs a render with the wrong shot lit up and the camera already
   *  flying to it. */
  const [pick, setPick] = useState({ cut: "", i: -1 });
  const [filter, setFilter] = useState<string>("all");
  /** WHICH OUTCOMES ARE ON SCREEN. Empty means all of them — the natural
   *  reading of an untouched legend, and it keeps "show everything" as the
   *  default without a separate reset control. Kept apart from `filter`
   *  because they answer different questions and compose: "set pieces that
   *  were saved" is a sentence the map should be able to draw. */
  const [outcomes, setOutcomes] = useState<Set<string>>(() => new Set());
  const [who, setWho] = useState("");
  const [view, setView] = useState<ViewName>(() => defaultCam("shots", "behind the goal"));
  /** Whether a click should drop the camera to the shooter's eye. On by
   *  default because that view IS the feature; a reader who wants to keep
   *  their own angle can switch it off and still get the wedge. */
  const [eye, setEye] = useState(true);

  useEffect(() => {
    let live = true;
    fetch(`${DATA}/${season}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => live && setData(d))
      .catch(() => live && setData(null));
    return () => {
      live = false;
    };
  }, [season]);

  /** 🐛 THIS PAYLOAD IS KEYED BY UNDERSTAT'S SPELLINGS, NOT THE CALLER'S.
   *
   *  `data.teams[team]` was an exact lookup, so every club whose name differs
   *  between sources silently rendered an empty pitch: Man City against
   *  "Manchester City", Man Utd against "Manchester Utd", Leeds against
   *  "Leeds United", Coventry against "Coventry City", Nottingham Forest
   *  against "Nottingham". Five clubs, no error, just nothing drawn — the
   *  same class of failure as the fixture links that resolved 4 of 10.
   *
   *  The resolver already exists and the crest lookup already uses it; this
   *  view simply was not going through it. Resolved ONCE per payload rather
   *  than per branch, so "shots taken" and "shots faced" cannot disagree
   *  about which club they are about. */
  const key = useMemo(() => {
    if (!data) return null;
    const names = Object.keys(data.teams);
    return names.includes(team) ? team : matchTeam(team, names) ?? null;
  }, [data, team]);

  const all = useMemo(() => {
    if (!data) return [];
    if (side === "taken") {
      return key && data.teams[key] ? unpack(data, data.teams[key]) : [];
    }
    // The opponents index is keyed the same way, so it needs the same
    // resolution — otherwise "faced" breaks for exactly the clubs "taken"
    // was just fixed for.
    const opp = data.opponents.includes(team)
      ? team
      : matchTeam(team, data.opponents) ?? team;
    const want = data.opponents.indexOf(opp);
    if (want < 0) return [];
    const rows: number[][] = [];
    for (const [club, list] of Object.entries(data.teams)) {
      if (club === key) continue;
      for (const r of list) if (r[9] === want) rows.push(r);
    }
    return unpack(data, rows);
  }, [data, team, side]);
  /** Who took how many, for the picker — most shots first, because that is
   *  the order anyone looks for a name in. */
  const takers = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of all) n.set(s.player, (n.get(s.player) ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);

  const shots = useMemo(() => {
    let out = all;
    if (who) out = out.filter((s) => s.player === who);
    if (filter === "big") out = out.filter((s) => s.xg >= 0.3);
    else if (filter === "set") out = out.filter((s) => s.situation !== "OpenPlay");
    else if (filter === "Goal") out = out.filter((s) => s.result === "Goal");
    else if (filter !== "all") out = out.filter((s) => s.situation === filter);
    if (outcomes.size) out = out.filter((s) => outcomes.has(s.result));
    return out;
  }, [all, filter, who, outcomes]);

  const cut = `${team}|${season}|${filter}|${who}|${[...outcomes].sort().join(",")}`;
  const selected = pick.cut === cut ? pick.i : -1;
  const select = (i: number) => setPick({ cut, i });

  const sel = shots[selected];
  const geo = sel ? geometry(shotX(sel.y), shotZ(sel.x), goalZOf(sel)) : null;
  const focus = sel && eye ? eyeOf(sel) : null;
  /** Three quarters is enough for every attempt on the far goal, but an own
   *  goal is scored into the near one — so when one is picked the pitch has
   *  to reach that end or the geometry points off the grass at nothing. */
  const portion = sel && goalEndOf(sel) === -1 ? 1 : 0.75;
  const goals = shots.filter((s) => s.result === "Goal").length;
  const xgSum = shots.reduce((a, s) => a + s.xg, 0);

  return (
    <div>
      {!compact && (
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-full border px-3 py-0.5 text-[12px] transition-colors ${
              filter === f.key
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3"
            }`}
          >
            {f.label}
          </button>
        ))}
        <select
          value={who}
          onChange={(e) => setWho(e.target.value)}
          className="rounded-md border border-line bg-card px-2 py-0.5 text-[12px]"
        >
          <option value="">every player</option>
          {takers.map(([n, c]) => (
            <option key={n} value={n}>{n} ({c})</option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-[12px] text-ink-2">
          <input type="checkbox" checked={eye}
                 onChange={(e) => setEye(e.target.checked)} />
          shooter&apos;s eye
        </label>
        <span className="ml-auto num text-[12.5px] text-ink-2">
          {shots.length} shots · {goals} goals ·{" "}
          {xgSum.toFixed(1)} xG
        </span>
      </div>
      )}

      <div className="mt-2 flex flex-wrap items-start gap-5">
        <div className="min-w-0 flex-1">
          <PitchScene
            // THREE QUARTERS, NOT A HALF. Shots from just inside a side's
            // own half are rare and are exactly the ones worth seeing; on a
            // half pitch they were drawn past the end of the grass.
            portion={portion}
            height={height}
            view={view}
            onView={setView}
            focus={focus}
            tune={tune}
            scene="shots"
            caption={
              sel ? (
                <span>
                  <b className="text-ink">{sel.player}</b> · {sel.minute}&apos;{" "}
                  {sel.home ? "v" : "away to"} {sel.opponent} —{" "}
                  {eye ? "you are standing six metres behind him. " : ""}
                  click the ball again to come back out
                </span>
              ) : (
                <span className="text-ink-3">
                  Click a shot to stand behind the shooter and see the goal he
                  actually had.
                </span>
              )
            }
            legend={
              /* THE LEGEND IS THE FILTER. It already named every outcome and
                 coloured it; making the same swatches clickable adds the
                 control without adding a row of chrome, and the thing you
                 point at to ask "which are the blocked ones" is the thing
                 that shows you. Dimmed means excluded, and with nothing
                 chosen everything is on. */
              <span className="flex flex-wrap items-center gap-2.5 text-[11px] text-ink-3">
                {["Goal", "SavedShot", "ShotOnPost", "BlockedShot",
                  "MissedShots"].map((r) => {
                  const on = !outcomes.size || outcomes.has(r);
                  const n = all.filter((s) => s.result === r).length;
                  return (
                    <button
                      key={r}
                      onClick={() =>
                        setOutcomes((prev) => {
                          const next = new Set(prev);
                          if (next.has(r)) next.delete(r);
                          else next.add(r);
                          // all five selected is the same as none: go back to
                          // the cheaper, clearer "everything" state
                          return next.size === 5 ? new Set() : next;
                        })
                      }
                      title={`${n} ${RESULT_LABEL[r]} — click to ${on ? "hide" : "show"}`}
                      className={`flex cursor-pointer items-center gap-1 rounded-full px-1.5 py-0.5 transition-opacity hover:bg-[#f2f4f6] ${
                        on ? "" : "opacity-35"
                      }`}
                    >
                      <span
                        className="inline-block h-2.5 w-2.5 rounded-full"
                        style={{ background: RESULT_COLOUR[r] }}
                      />
                      {RESULT_LABEL[r]}
                      <span className="num text-ink-3">{n}</span>
                    </button>
                  );
                })}
                {outcomes.size > 0 && (
                  <button
                    onClick={() => setOutcomes(new Set())}
                    className="cursor-pointer text-home underline underline-offset-2"
                  >
                    all
                  </button>
                )}
              </span>
            }
          >
            <ShotCloud
              shots={shots}
              selected={selected}
              onSelect={select}
            />
          </PitchScene>
        </div>

        {!compact && (
        <div className="w-[260px] shrink-0 rounded-xl border border-line bg-card p-4">
          {sel && geo ? (
            <>
              <div className="text-[11px] uppercase tracking-wider text-ink-3">
                the chance
              </div>
              <div className="mt-1 text-[15px] font-semibold">{sel.player}</div>
              <div className="text-[12.5px] text-ink-2">
                {sel.minute}&apos; {sel.home ? "v" : "away to"} {sel.opponent}
              </div>

              <div className="num mt-3 flex items-baseline gap-2">
                <span className="text-[30px] font-semibold leading-none">
                  {sel.xg.toFixed(2)}
                </span>
                <span className="text-[12px] text-ink-3">xG</span>
              </div>
              <div
                className="mt-1 inline-block rounded px-2 py-0.5 text-[11.5px] font-semibold text-white"
                style={{ background: RESULT_COLOUR[sel.result] }}
              >
                {RESULT_LABEL[sel.result] ?? sel.result}
              </div>

              <dl className="mt-3 space-y-1 text-[12.5px]">
                {[
                  ["distance", `${geo.dist.toFixed(1)} m`],
                  ["angle of goal", `${geo.deg.toFixed(1)}°`],
                  ["finished", sel.gx !== null && sel.gz !== null
                    ? corner(sel.gx, sel.gz) : "—"],
                  ["situation", sel.situation.replace(/([A-Z])/g, " $1").trim()],
                  ["with", sel.foot.replace(/([A-Z])/g, " $1").trim()],
                  ["assisted by", sel.assist || "—"],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="text-ink-3">{k}</dt>
                    <dd className="num text-right">{v}</dd>
                  </div>
                ))}
              </dl>

              <p className="mt-3 text-[11.5px] leading-relaxed text-ink-3">
                The wedge on the grass is the goal he could see from there.
                Distance and angle are most of what an xG model reads — the
                rest is the situation, the body part and who was in the way.
              </p>
            </>
          ) : (
            <>
              <div className="text-[11px] uppercase tracking-wider text-ink-3">
                no shot selected
              </div>
              <p className="mt-2 text-[12.5px] leading-relaxed text-ink-2">
                Every attempt is a disc on the grass. <b>Area</b> is xG — a
                0.40 chance covers four times the ground of a 0.10 one, which
                is the honest way to draw it. <b>Colour</b> is what happened.
              </p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-ink-2">
                Click one and the angle of goal available from that spot is
                drawn to both posts. That geometry is most of the xG, and it
                is the thing a flat map cannot show you.
              </p>
            </>
          )}
        </div>
        )}
      </div>
    </div>
  );
}
