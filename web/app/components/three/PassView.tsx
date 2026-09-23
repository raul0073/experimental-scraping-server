"use client";

import { useEffect, useMemo, useState } from "react";

import { PitchScene, defaultCam, type ViewName } from "./PitchScene";
import {
  BIT, CLASSES, PassCloud, classOf, lengthOf, type Pass,
} from "./PassCloud";

/** A club's passes, filterable by player and by what became of them. */

type Payload = {
  club: string;
  matches: number;
  passes: number;
  stride: number;
  players: string[];
  opponents: string[];
  rows: number[];
};

const DATA = "/data/passes/eng-premier-league";

/** EVERY PASS ON SCREEN IS NOT A PASS MAP, IT IS A CARPET. A club plays
 *  about 18,000 a season; past a few thousand ribbons the picture is a solid
 *  block of colour that answers no question, and the honest response is to
 *  say so rather than to render it and let the reader think they are seeing
 *  something. The filters below are the feature, not a convenience. */
const CAP = 4000;

const FILTERS = [
  { key: "all", label: "All", hit: () => true },
  { key: "ok", label: "Completed", hit: (f: number) => !!(f & BIT.ok) },
  { key: "lost", label: "Lost", hit: (f: number) => !(f & BIT.ok) },
  { key: "key", label: "Led to a shot",
    hit: (f: number) => !!(f & (BIT.key | BIT.assist)) },
  { key: "air", label: "In the air", hit: (f: number) => !!(f & BIT.air) },
  { key: "cross", label: "Crosses", hit: (f: number) => !!(f & BIT.cross) },
  { key: "long", label: "Long balls", hit: (f: number) => !!(f & BIT.long) },
  { key: "through", label: "Through balls",
    hit: (f: number) => !!(f & BIT.through) },
  { key: "open", label: "Open play", hit: (f: number) => !(f & BIT.set) },
] as const;

function unpack(p: Payload): Pass[] {
  const out: Pass[] = [];
  const s = p.stride;
  for (let i = 0; i < p.rows.length; i += s) {
    out.push({
      sx: p.rows[i] / 10,
      sz: p.rows[i + 1] / 10,
      ex: p.rows[i + 2] / 10,
      ez: p.rows[i + 3] / 10,
      flags: p.rows[i + 4],
      player: p.players[p.rows[i + 5]] ?? "",
      minute: p.rows[i + 6],
      opponent: p.opponents[p.rows[i + 7]] ?? "",
      home: p.rows[i + 8] === 1,
      to: p.rows[i + 9] >= 0 ? p.players[p.rows[i + 9]] ?? "" : "",
    });
  }
  return out;
}

export function PassView({
  team, season = "2526", height = 520, tune = false, compact = false,
  scene = "passes",
}: {
  team: string; season?: string; height?: number; tune?: boolean;
  /** drop the side panel, for a match page where two of these sit beside
   *  each other. The FILTERS stay: a picture you cannot interrogate is a
   *  picture nobody trusts, and the filters are the feature here. */
  compact?: boolean;
  /** which camera this instance opens on — a match page and the lab are
   *  looking at the same component for different reasons. */
  scene?: string;
}) {
  const [filter, setFilter] = useState<string>("key");
  const [who, setWho] = useState("");
  const [to, setTo] = useState("");
  const [view, setView] = useState<ViewName>(() => defaultCam(scene, "overhead"));

  const slug = team.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const file = `${season}/${slug}`;

  /** STATE TAGGED WITH WHAT IT IS FOR, rather than cleared by an effect when
   *  the inputs change. Clearing it in an effect means one render showing
   *  the previous club's passes under the new club's name, then a second
   *  render to fix it; tagging it means the stale value is simply not
   *  matched and the right thing renders first time. */
  const [got, setGot] = useState<{ file: string; data: Payload | null }>({
    file: "", data: null,
  });

  useEffect(() => {
    let live = true;
    fetch(`${DATA}/${file}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => live && setGot({ file, data: d }))
      .catch(() => live && setGot({ file, data: null }));
    return () => {
      live = false;
    };
  }, [file]);

  const ready = got.file === file;
  const data = ready ? got.data : null;
  const missing = ready && !got.data;

  const all = useMemo(() => (data ? unpack(data) : []), [data]);

  const passers = useMemo(() => {
    const n = new Map<string, number>();
    for (const p of all) n.set(p.player, (n.get(p.player) ?? 0) + 1);
    return [...n.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);

  /** Who received it. With a passer chosen as well this is the question a
   *  pass map is actually for — not "where does Rice pass" but "where is
   *  Rice when he finds Saka", which is a different picture and a much
   *  smaller one. */
  const targets = useMemo(() => {
    const n = new Map<string, number>();
    for (const p of all) {
      if (!p.to) continue;
      if (who && p.player !== who) continue;
      n.set(p.to, (n.get(p.to) ?? 0) + 1);
    }
    return [...n.entries()].sort((a, b) => b[1] - a[1]);
  }, [all, who]);

  const matching = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter) ?? FILTERS[0];
    let out = all;
    if (who) out = out.filter((p) => p.player === who);
    if (to) out = out.filter((p) => p.to === to);
    return out.filter((p) => f.hit(p.flags));
  }, [all, filter, who, to]);

  // Trim from the FRONT, so what survives is the most recent run of matches
  // rather than an arbitrary slice of the season.
  const passes = useMemo(
    () => (matching.length > CAP ? matching.slice(matching.length - CAP) : matching),
    [matching],
  );
  const trimmed = matching.length - passes.length;

  /** The selection carries the filter it was made under, so changing the
   *  filter drops it without an effect — index 12 of "crosses" is not index
   *  12 of "long balls", and an effect to clear it costs a render showing
   *  the wrong pass highlighted. */
  const cut = `${file}|${filter}|${who}|${to}`;
  const [pick, setPick] = useState({ cut: "", i: -1 });
  const selected = pick.cut === cut ? pick.i : -1;
  const select = (i: number) => setPick({ cut, i });

  const sel = passes[selected];
  const done = matching.filter((p) => p.flags & BIT.ok).length;
  const air = matching.filter((p) => p.flags & BIT.air).length;
  const avg = matching.length
    ? matching.reduce((a, p) => a + lengthOf(p), 0) / matching.length
    : 0;

  if (missing) {
    return (
      <p className="rounded-xl border border-line bg-card p-4 text-[13px] text-ink-2">
        No pass data for {team} in {season}. Event streams are scraped per
        league; only the Premier League is on disk so far.
      </p>
    );
  }

  return (
    <div>
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
          onChange={(e) => {
            setWho(e.target.value);
            setTo("");
          }}
          className="rounded-md border border-line bg-card px-2 py-0.5 text-[12px]"
        >
          <option value="">from anyone</option>
          {passers.map(([n, c]) => (
            <option key={n} value={n}>{n} ({c})</option>
          ))}
        </select>
        <select
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="rounded-md border border-line bg-card px-2 py-0.5 text-[12px]"
        >
          <option value="">to anyone</option>
          {targets.map(([n, c]) => (
            <option key={n} value={n}>to {n} ({c})</option>
          ))}
        </select>
        <span className="ml-auto num text-[12.5px] text-ink-2">
          {matching.length.toLocaleString()} passes ·{" "}
          {matching.length ? Math.round((100 * done) / matching.length) : 0}%
          completed · {avg.toFixed(0)} m average
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-start gap-5">
        <div className="min-w-0 flex-1">
          <PitchScene
            height={height}
            view={view}
            onView={setView}
            tune={tune}
            scene={scene}
            legend={
              <span className="flex items-center gap-3 text-[11.5px] text-ink-3">
                {CLASSES.map((c) => (
                  <span key={c.key} className="flex items-center gap-1.5">
                    <span className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{ background: c.colour }} />
                    {c.label}
                  </span>
                ))}
              </span>
            }
            caption={
              sel ? (
                <span>
                  <b className="text-ink">{sel.player}</b>
                  {sel.to && <> → <b className="text-ink">{sel.to}</b></>} ·{" "}
                  {sel.minute}&apos;{" "}
                  {sel.home ? "v" : "away to"} {sel.opponent} —{" "}
                  {lengthOf(sel).toFixed(0)} m{" "}
                  {sel.flags & BIT.air ? "in the air" : "along the ground"},{" "}
                  {classOf(sel.flags).label}. Click again to come back out.
                </span>
              ) : (
                <span className="text-ink-3">
                  Each ribbon is one pass, widening and brightening toward
                  where it was aimed. Lofted passes arc; ground passes stay
                  down. Click one to isolate it.
                  {trimmed > 0 &&
                    ` Showing the last ${CAP.toLocaleString()} of
                     ${matching.length.toLocaleString()} — narrow the filter
                     to see the rest.`}
                </span>
              )
            }
          >
            <PassCloud
              passes={passes}
              selected={selected}
              onSelect={select}
            />
          </PitchScene>
        </div>

        {!compact && (
        <aside className="w-[260px] shrink-0 rounded-xl border border-line bg-card p-3.5 text-[12.5px] leading-relaxed text-ink-2">
          {sel ? (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                selected pass
              </div>
              <div className="mt-1 font-semibold text-ink">{sel.player}</div>
              <dl className="mt-2 space-y-1">
                <Row k="to" v={sel.to || "not resolved"} />
                <Row k="length" v={`${lengthOf(sel).toFixed(1)} m`} />
                <Row k="outcome" v={classOf(sel.flags).label} />
                <Row k="height"
                     v={sel.flags & BIT.air ? "lofted" : "along the ground"} />
                <Row k="type" v={kindOf(sel.flags)} />
                <Row k="when" v={`${sel.minute}'`} />
              </dl>
            </>
          ) : (
            <>
              <div className="text-[11px] uppercase tracking-wide text-ink-3">
                no pass selected
              </div>
              <p className="mt-1.5">
                <b className="text-ink">Height is the point.</b> Opta records
                whether a pass left the ground, so a forty-metre ball along
                the floor and a forty-metre diagonal over the top are drawn
                as the different actions they are — which is the one thing a
                flat pass map cannot show you. Lofted passes drop a shadow;
                the gap between ball and shadow is the height.
              </p>
              <p className="mt-2 text-[11.5px] text-ink-3">
                The receiver is <b>inferred</b> — the feed does not record
                one. A completed pass is credited to whichever teammate acts
                next, which resolves 99% of them and is wrong where an
                opponent gets between the two.
              </p>
              <dl className="mt-2.5 space-y-1">
                <Row k="in the air"
                     v={`${matching.length
                       ? Math.round((100 * air) / matching.length) : 0}%`} />
                <Row k="matches" v={String(data?.matches ?? "—")} />
                <Row k="on file" v={(data?.passes ?? 0).toLocaleString()} />
              </dl>
            </>
          )}
        </aside>
        )}
      </div>
    </div>
  );
}

function kindOf(f: number): string {
  const bits: string[] = [];
  if (f & BIT.cross) bits.push("cross");
  if (f & BIT.through) bits.push("through ball");
  if (f & BIT.long) bits.push("long ball");
  if (f & BIT.head) bits.push("header");
  if (f & BIT.set) bits.push("set piece");
  if (f & BIT.big) bits.push("big chance");
  return bits.length ? bits.join(", ") : "open play";
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-3">{k}</dt>
      <dd className="num text-ink">{v}</dd>
    </div>
  );
}
