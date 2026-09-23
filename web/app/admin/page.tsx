"use client";

import { useCallback, useEffect, useState } from "react";

/** Where the data actually stands, per league, with the controls next to it.
 *
 *  WHY THIS PAGE EXISTS. Every scrape so far has been a black box: a job
 *  starts, the terminal goes quiet for eleven minutes, and the only way to
 *  find out what it fetched is to read file timestamps afterwards. Twice
 *  that silence hid a job doing work nobody asked for — five leagues when
 *  one was wanted, a whole season when four matches were missing.
 *
 *  So the rule here is: nothing runs that was not named, and what each
 *  button will do is visible before it is pressed. Every action is scoped to
 *  ONE league, the log is on screen while it runs, and the season table
 *  shows raw against stamped — because nothing downstream reads the raw
 *  parquet, and a season with 380 raw and 0 stamped is invisible to the
 *  ratings while looking perfectly healthy on disk.
 *
 *  DEVELOPMENT ONLY, and the API refuses anything that is not localhost.
 *  Two guards, because this page starts processes.
 */
const API = "http://127.0.0.1:8080/api/v2/admin";
const DEV = process.env.NODE_ENV === "development";

type SeasonRow = {
  season: string;
  raw: number;
  stamped: number;
  raw_at: string | null;
  stamped_at: string | null;
};

type LeagueRow = {
  league: string;
  short: string;
  ready: boolean;
  in_daily: boolean;
  missing_seasons: string[];
  fixtures_total: number;
  played_this_season: number;
  seasons: SeasonRow[];
  stale: { stale: boolean; reasons: string[] } | null;
};

type Data = {
  leagues: LeagueRow[];
  ready: string[];
  running: boolean;
  today: string;
  site_generated: string | null;
};

type Job = {
  running: boolean;
  started: string | null;
  returncode: number | null;
  tail: string[];
};

function Cell({ s }: { s: SeasonRow }) {
  if (!s.raw && !s.stamped) {
    return <span className="text-ink-3">—</span>;
  }
  // Raw without stamped is the failure mode worth shouting about: the data
  // is on disk and nothing can see it.
  const gap = s.raw > s.stamped;
  return (
    <span className={gap ? "text-bad" : "text-ink"} title={s.stamped_at ?? ""}>
      {s.stamped}
      {gap && <span className="text-[10px]"> /{s.raw} raw</span>}
    </span>
  );
}

export default function AdminPage() {
  const [d, setD] = useState<Data | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [scrape, setScrape] = useState<{
    lines: string[];
    modified: string | null;
    running: boolean;
  } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [season, setSeason] = useState<Record<string, string>>({});
  const [until, setUntil] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [a, b, c] = await Promise.all([
        fetch(`${API}/leagues`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API}/status`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${API}/scrapelog`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setD(a);
      setJob(b);
      setScrape(c);
      setErr(null);
    } catch {
      setErr("API not reachable on :8080 — is main.py running?");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** POLL ALWAYS, not only when THIS page started something.
   *
   *  The scrape log is written by whoever is fetching — a terminal run, the
   *  scheduled task, or this panel — so the panel has to keep looking even
   *  when it did not press the button itself. Polling only on `job.running`
   *  is exactly why this box sat empty while work was happening. Two
   *  seconds while a fetch is in flight, ten when the log is quiet. */
  const live = !!job?.running || !!scrape?.running;
  useEffect(() => {
    const t = setInterval(load, live ? 2000 : 10000);
    return () => clearInterval(t);
  }, [live, load]);

  const post = async (path: string) => {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${API}${path}`, { method: "POST" });
      const body = await r.json().catch(() => null);
      if (!r.ok) setErr(body?.detail ?? `HTTP ${r.status}`);
      await load();
    } catch {
      setErr("API not reachable on :8080");
    } finally {
      setBusy(false);
    }
  };

  if (!DEV) {
    return (
      <p className="text-[13.5px] text-ink-2">
        The admin panel runs in development only.
      </p>
    );
  }

  const disabled = busy || !!job?.running;
  const btn =
    "cursor-pointer rounded-full border px-2.5 py-0.5 text-[11px] transition-colors disabled:cursor-default disabled:opacity-45";

  return (
    <div>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="font-display text-[24px] tracking-[0.01em]">Data</h1>
        <div className="num flex items-center gap-3 text-[12px] text-ink-3">
          <span>today {d?.today}</span>
          <span>site {d?.site_generated ?? "—"}</span>
          <button
            onClick={load}
            className="cursor-pointer text-home underline underline-offset-2"
          >
            refresh
          </button>
        </div>
      </div>

      <p className="mt-2 max-w-3xl text-[12.5px] leading-relaxed text-ink-2">
        Every action here is scoped to one league and starts nothing else. The
        season columns show <b>stamped</b> match counts — the file the ratings
        actually read. A red <span className="num">n /m raw</span> means events
        are on disk but unstamped, so nothing downstream can see them.
      </p>

      {err && (
        <p className="mt-3 rounded-lg border border-[#eec4ab] bg-[#fae5d9] px-3 py-2 text-[12px] text-[#a34a22]">
          {err}
        </p>
      )}

      <div className="mt-4 overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-[#f7f8f9] text-[11px] uppercase tracking-wider text-ink-3">
              <th className="py-2 pl-4 pr-3 text-left font-semibold">League</th>
              <th className="px-2 py-2 text-center font-semibold">In daily</th>
              <th className="px-2 py-2 text-center font-semibold">23/24</th>
              <th className="px-2 py-2 text-center font-semibold">24/25</th>
              <th className="px-2 py-2 text-center font-semibold">25/26</th>
              <th className="px-2 py-2 text-center font-semibold">26/27</th>
              <th className="px-3 py-2 text-left font-semibold">Status</th>
              <th className="py-2 pl-3 pr-4 text-left font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {d?.leagues.map((l) => (
              <tr key={l.league} className="border-t border-line align-top">
                <td className="whitespace-nowrap py-2.5 pl-4 pr-3">
                  <div className="font-medium">{l.short}</div>
                  <div className="num text-[11px] text-ink-3">
                    {l.played_this_season}/{l.fixtures_total} played
                  </div>
                </td>
                <td className="px-2 py-2.5 text-center">
                  {l.in_daily ? (
                    <span className="text-good">✓</span>
                  ) : (
                    <span className="text-ink-3" title={`needs ${l.missing_seasons.join(", ")}`}>
                      —
                    </span>
                  )}
                </td>
                {l.seasons.map((s) => (
                  <td key={s.season} className="num px-2 py-2.5 text-center">
                    <Cell s={s} />
                  </td>
                ))}
                <td className="px-3 py-2.5 text-[11.5px]">
                  {!l.ready ? (
                    <span className="text-ink-3">
                      waiting on {l.missing_seasons.join(", ")}
                    </span>
                  ) : l.stale?.stale ? (
                    <span className="text-[#6b5606]">
                      {l.stale.reasons.join(" · ")}
                    </span>
                  ) : (
                    <span className="text-good">up to date</span>
                  )}
                </td>
                <td className="py-2.5 pl-3 pr-4">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      disabled={disabled}
                      onClick={() =>
                        post(`/league/daily?league=${encodeURIComponent(l.league)}`)
                      }
                      className={`${btn} border-home bg-[#e9f1f8] text-[#1c5b8a]`}
                      title="Full pipeline for this league: sources, events, stamp, ratings, grade, predict, simulate, export"
                    >
                      Update to today
                    </button>

                    <select
                      value={season[l.league] ?? ""}
                      onChange={(e) =>
                        setSeason({ ...season, [l.league]: e.target.value })
                      }
                      className="rounded border border-line bg-card px-1.5 py-0.5 text-[11px]"
                    >
                      <option value="">all seasons</option>
                      {l.seasons.map((s) => (
                        <option key={s.season} value={s.season}>
                          {s.season}
                        </option>
                      ))}
                    </select>

                    <input
                      type="date"
                      value={until[l.league] ?? ""}
                      onChange={(e) =>
                        setUntil({ ...until, [l.league]: e.target.value })
                      }
                      className="num rounded border border-line bg-card px-1.5 py-0.5 text-[11px]"
                      title="Only fetch matches played on or before this date"
                    />

                    <button
                      disabled={disabled}
                      onClick={() => {
                        const q = new URLSearchParams({ league: l.league });
                        if (season[l.league]) q.set("season", season[l.league]);
                        if (until[l.league]) q.set("until", until[l.league]);
                        post(`/league/events?${q}`);
                      }}
                      className={`${btn} border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink`}
                      title="Fetch events only, for the chosen season and date bound"
                    >
                      Fetch events
                    </button>

                    <button
                      disabled={disabled}
                      onClick={() =>
                        post(`/league/stamp?league=${encodeURIComponent(l.league)}`)
                      }
                      className={`${btn} border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink`}
                      title="Rebuild the stamped parquet from raw already on disk — no network"
                    >
                      Stamp
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* THE FETCH LOG — every network call, whoever started it. This is the
          box that was empty while work was happening, because it used to
          read only what this panel itself had spawned. */}
      <div className="mt-5 rounded-xl border border-line bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-ink-3">
            Scrape log
          </h2>
          {scrape?.running && (
            <span className="flex items-center gap-1.5 text-[12px] text-[#1c5b8a]">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[#1c5b8a]" />
              fetching
            </span>
          )}
          <span className="num ml-auto text-[11px] text-ink-3">
            {scrape?.modified ? `updated ${scrape.modified.slice(11, 19)}` : "no activity yet"}
          </span>
        </div>
        <pre className="num mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-[#fafbfc] p-2.5 text-[11px] leading-relaxed text-ink-2">
          {scrape?.lines?.length
            ? scrape.lines.join("\n")
            : "nothing fetched yet"}
        </pre>
      </div>

      <div className="mt-5 rounded-xl border border-line bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-ink-3">
            Job
          </h2>
          {job?.running ? (
            <span className="num text-[12px] text-[#1c5b8a]">
              running since {job.started?.slice(11, 16)}
            </span>
          ) : job?.returncode !== null && job?.returncode !== undefined ? (
            <span
              className={`text-[12px] ${job.returncode === 0 ? "text-good" : "text-bad"}`}
            >
              {job.returncode === 0 ? "finished ok" : `exited ${job.returncode}`}
            </span>
          ) : (
            <span className="text-[12px] text-ink-3">idle</span>
          )}
        </div>
        <pre className="num mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-[#fafbfc] p-2.5 text-[11px] leading-relaxed text-ink-2">
          {job?.tail?.length ? job.tail.join("\n") : "no output yet"}
        </pre>
      </div>
    </div>
  );
}
