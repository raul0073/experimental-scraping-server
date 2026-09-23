"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

/** How old the data is, and — in development — a button to fix it.
 *
 *  THE FAILURE THIS EXISTS FOR IS SILENT. When the 09:00 task does not run
 *  (machine asleep, window missed, a step died halfway) the site carries on
 *  serving whatever it last had, and looks exactly as it does when
 *  everything is fine. A page that once showed a round four days older than
 *  the results printed beside it did not say so anywhere. So the age of the
 *  data is now stated on the page that depends on it, in every environment.
 *
 *  TWO CLOCKS, AND THE GAP BETWEEN THEM IS THE POINT. `generated` is baked
 *  into this page at build time; `data_generated` is read live from the API.
 *  If the pipeline ran but the site was never rebuilt, those disagree — the
 *  data on disk is current and the page in front of you is not. That is a
 *  real and otherwise invisible state, so it gets its own message rather
 *  than being averaged away.
 *
 *  THE BUTTON IS DEVELOPMENT-ONLY and the endpoint refuses anything that is
 *  not localhost, because it starts a subprocess. Two guards rather than
 *  one: the build must not ship it, and the server must not honour it.
 */
const API = "http://127.0.0.1:8080/api/v2/admin";
const DEV = process.env.NODE_ENV === "development";

type Stale = {
  stale: boolean;
  reasons: string[];
  checks: Record<string, unknown>;
};

type Status = {
  league: string;
  stale: Stale;
  running: boolean;
  started: string | null;
  finished: string | null;
  returncode: number | null;
  last_run: string | null;
  data_generated: string | null;
  today: string;
  tail: string[];
};

/** Whole days between two YYYY-MM-DD strings. */
function daysOld(from: string | null, today: string): number | null {
  if (!from) return null;
  const a = Date.parse(`${from.slice(0, 10)}T00:00:00Z`);
  const b = Date.parse(`${today.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((b - a) / 86_400_000);
}

export function Freshness({ generated }: { generated?: string }) {
  const router = useRouter();
  const [st, setSt] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const poll = useCallback(async () => {
    if (!DEV) return;
    try {
      const r = await fetch(`${API}/status`, { cache: "no-store" });
      if (r.ok) setSt(await r.json());
    } catch {
      /* API not running — the static line below still tells the truth */
    }
  }, []);

  useEffect(() => {
    poll();
  }, [poll]);

  /** While a run is in flight, poll often enough to feel live; otherwise
   *  leave the dev server alone. */
  useEffect(() => {
    if (!DEV || !st?.running) return;
    const t = setInterval(poll, 3000);
    return () => clearInterval(t);
  }, [st?.running, poll]);

  /** WHEN THE JOB FINISHES, RELOAD THE PAGE'S DATA.
   *
   *  round.json is read on the server per request, so the numbers above are
   *  never stale on a fresh render — but nothing tells React to re-render
   *  just because a file changed on disk. Without this, a successful update
   *  leaves the old table on screen and the only clue is that the button
   *  went quiet, which is indistinguishable from nothing having happened.
   *  router.refresh() re-runs the server components and swaps the data in
   *  without losing scroll position or client state. */
  const wasRunning = useRef(false);
  useEffect(() => {
    if (!DEV) return;
    if (wasRunning.current && !st?.running) router.refresh();
    wasRunning.current = !!st?.running;
  }, [st?.running, router]);

  const [note, setNote] = useState<string | null>(null);

  const start = async () => {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const r = await fetch(`${API}/update`, { method: "POST" });
      const body = await r.json().catch(() => null);
      if (!r.ok) {
        setErr(body?.detail ?? `HTTP ${r.status}`);
      } else if (body?.up_to_date) {
        // It checked and did NOT run. Saying so is the point — a button that
        // silently does nothing is indistinguishable from a broken one.
        setNote(body.message ?? "Everything is up to date");
      } else {
        setOpen(true);
      }
      await poll();
    } catch {
      setErr("API not reachable on :8080 — is main.py running?");
    } finally {
      setBusy(false);
    }
  };

  // The page's own age, from the payload compiled into it.
  const today = st?.today ?? new Date().toISOString().slice(0, 10);
  const age = daysOld(generated ?? null, today);
  const stale = age !== null && age >= 2;

  // The pipeline may have run without the site being rebuilt.
  const behind =
    st?.data_generated && generated && st.data_generated.slice(0, 10) !== generated.slice(0, 10);

  if (!generated && !DEV) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px]">
      {generated && (
        <span className={stale ? "font-medium text-bad" : "text-ink-3"}>
          Data from <span className="num">{generated.slice(0, 10)}</span>
          {age !== null && age > 0 && (
            <> — {age} day{age === 1 ? "" : "s"} old</>
          )}
        </span>
      )}

      {DEV && behind && (
        <span className="rounded border border-[#e4d49a] bg-[#faf0cd] px-1.5 py-0.5 text-[11px] text-[#6b5606]">
          pipeline has <span className="num">{st!.data_generated!.slice(0, 10)}</span> — rebuild the site to pick it up
        </span>
      )}

      {DEV && (
        <>
          <button
            onClick={start}
            disabled={busy || st?.running}
            className={`cursor-pointer rounded-full border px-3 py-1 text-[11.5px] font-medium transition-colors disabled:cursor-default disabled:opacity-55 ${
              st?.stale?.stale
                ? "border-home bg-[#e9f1f8] text-[#1c5b8a] hover:border-[#1c5b8a]"
                : "border-line bg-card text-ink-2 hover:border-ink-3 hover:text-ink"
            }`}
          >
            {st?.running ? "Updating…" : busy ? "Starting…" : "Update all to today"}
          </button>

          {/* WHAT IS ACTUALLY OUT OF DATE, before you click. The check reads
              only local files, so it costs nothing and can be shown always. */}
          {!st?.running && st?.stale && (
            st.stale.stale ? (
              <span className="text-[11px] text-[#6b5606]">
                {st.stale.reasons.join(" · ")}
              </span>
            ) : (
              <span className="text-[11px] text-good">
                England up to date
              </span>
            )
          )}

          {note && <span className="text-[11px] text-good">{note}</span>}

          {st?.running && st.started && (
            <span className="num text-[11px] text-ink-3">
              since {st.started.slice(11, 16)}
            </span>
          )}
          {!st?.running && st?.returncode !== null && st?.returncode !== undefined && (
            <span
              className={`text-[11px] ${st.returncode === 0 ? "text-good" : "text-bad"}`}
            >
              {st.returncode === 0 ? "last run ok" : `last run exited ${st.returncode}`}
            </span>
          )}
          {err && <span className="text-[11px] text-bad">{err}</span>}

          {st && (st.tail?.length ?? 0) > 0 && (
            <button
              onClick={() => setOpen((v) => !v)}
              className="cursor-pointer text-[11px] text-ink-3 underline underline-offset-2"
            >
              {open ? "hide log" : "log"}
            </button>
          )}
        </>
      )}

      {DEV && open && st?.tail?.length ? (
        <pre className="num mt-1 max-h-56 w-full overflow-auto rounded-lg border border-line bg-[#fafbfc] p-2.5 text-[11px] leading-relaxed text-ink-2">
          {st.tail.join("\n")}
        </pre>
      ) : null}
    </div>
  );
}
