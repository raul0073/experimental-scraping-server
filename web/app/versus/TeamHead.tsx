"use client";

import { useEffect, useState } from "react";

import { Crest } from "../components/Crest";
import { matchTeam } from "../lib/teamName";

/** A club's name with its badge, for every heading on a match page.
 *
 *  A page about two sides that writes their names as plain text makes the
 *  reader do the matching: four sections down, "When Brighton have it" and
 *  "Arsenal took" are two strings that have to be read and placed. A badge
 *  is recognised before it is read, and this page repeats the same two clubs
 *  eight or nine times — so it is the difference between a page you scan and
 *  a page you parse.
 *
 *  THE CREST INDEX IS KEYED BY THE TEAM LAYER'S SPELLING, which is not the
 *  round export's. "Manchester Utd" against "Man Utd" again — so the lookup
 *  goes through the same resolver the fixture join uses rather than a second
 *  rule that would drift from it. A club with no badge simply gets none.
 */
const META = "/data/team/eng-premier-league/meta.json";

let CACHE: Record<string, string> | null = null;

export function useCrests(): Record<string, string> {
  const [crests, setCrests] = useState<Record<string, string>>(CACHE ?? {});
  useEffect(() => {
    if (CACHE) return;
    let live = true;
    fetch(META)
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => {
        CACHE = (m?.crests as Record<string, string>) ?? {};
        if (live) setCrests(CACHE);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return crests;
}

export function crestFor(
  crests: Record<string, string>,
  team: string,
): string | undefined {
  if (crests[team]) return crests[team];
  const key = matchTeam(team, Object.keys(crests));
  return key ? crests[key] : undefined;
}

export function TeamHead({
  team, note, size = 20, className = "text-[14px] font-semibold text-ink",
}: {
  team: string;
  note?: string;
  size?: number;
  className?: string;
}) {
  const crests = useCrests();
  return (
    <h3 className="flex flex-wrap items-center gap-2">
      <Crest src={crestFor(crests, team)} alt="" size={size} />
      <span className={className}>{team}</span>
      {note && (
        <span className="num text-[11.5px] font-normal text-ink-3">{note}</span>
      )}
    </h3>
  );
}
