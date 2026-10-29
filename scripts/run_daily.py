"""Everything the site knows, brought up to date. Once a day, 09:00.

WHY DAILY AND NOT WEEKLY. The weekly run was built around a betting week:
scrape on the Monday, commit picks, wait. That leaves the public site stale
for six days out of seven — and it showed. Results for Saturday's matches
sat on disk from the fixtures refresh while `round.json` was four days old,
so the site displayed a PREDICTED scoreline in a column a reader takes for
the result, and hid its own misses by never updating.

It also means a scrape is never large. Every source here is incremental:
fixtures refresh in place, Understat fetches only what is new, the event
scraper asks for matches it does not already have in the parquet. A daily
cadence keeps each of those to a handful of matches. A weekly or monthly one
turns the same work into a long unattended job that has to be nursed — which
is the position this project kept finding itself in.

ORDER MATTERS, and it is one direction only:

    1. sources      fixtures, Understat, events, rosters, injuries
    2. grading      what happened to what we already said
    3. derived      ratings, team scores, Elo, zones, reliability
    4. payloads     the JSON the static site reads
    5. picks        the week's tickets, committed once per window

Nothing downstream is rebuilt before the thing it reads from. Every step is
non-fatal on purpose: a single source being down should cost that source's
freshness, not the whole day's update, and the summary at the end says which
ones missed rather than the run dying at the first 502.

    .venv/Scripts/python.exe scripts/run_daily.py
    .venv/Scripts/python.exe scripts/run_daily.py --no-scrape   # rebuild only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # before the services import below
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")

# ---------------------------------------------------------------------------
# TEXT ENCODING — READ THIS BEFORE CHANGING IT.
#
# This machine's locale is cp1255 (Hebrew). cp1255 encodes Hebrew perfectly
# and CANNOT encode n-tilde, o-umlaut, e-acute or a-grave — which is to say
# it cannot encode the team names of four of the five leagues this pipeline
# builds. Python picks the locale encoding for stdout, so the moment any step
# printed "Koln" with its umlaut, or "Atletico" with its accent, the print
# itself raised UnicodeEncodeError.
#
# In run() that exception escaped from inside the `for line in p.stdout` loop
# — BEFORE the "-> ok / FAILED" line — so the step was recorded as ERROR and
# abandoned with no outcome printed and the child left mid-fetch. On
# 2026-10-12 that was `sources` and all five `events` steps: six steps with
# no result line in the log, a WhoScored event store three weeks stale for
# England, Spain and Germany, and every rating, payload and page after them
# computed on events from September. The daily appeared to run fine and
# published stale data, every single day.
#
# Two fixes, because one is not enough:
#   1. this process writes utf-8 and never dies on a character;
#   2. CHILD_ENV forces the same on every child, so a step cannot die the
#      way the parent just stopped dying.
# errors="replace" is deliberate: a mangled character in a log line must
# never be able to abort a scrape again.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):       # not a reconfigurable stream
        pass

CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

LOG = ROOT / "data" / "reports" / "daily.log"

# The season a daily run is allowed to touch. Anything older is history and
# history is fetched deliberately, never as a side effect of the morning job.
SEASON = "2627"

# WHICH LEAGUES — DERIVED FROM DISK, NOT LISTED HERE.
# A daily run covers the leagues whose event history is actually present, and
# that set grows by itself as the backfill lands. Hardcoding it meant the
# run tried to build ratings for four leagues with no events, publishing a
# table of 50s; and the correction — pinning it to England — would have had
# to be remembered and undone by hand on the day La Liga became usable.
# services/data_ready.py holds the single definition of "ready".
from services.data_ready import ALL_LEAGUES, readiness, ready_leagues  # noqa: E402

# The daily's own marker. run_weekly has one (last_weekly_run.txt) but writes
# it at the END of a full run, which --sources-only returns before reaching —
# so the daily has never had a record of when it last ran.
DAILY_STAMP = ROOT / "data" / "reports" / "last_daily_run.txt"


def football_window(leagues: list) -> tuple:
    """(most recent kickoff, next kickoff) across `leagues`.

    Read from the CACHED fixture lists, never the network — the entire point
    is to decide whether a network round trip is worth making, so paying for
    one to find out would defeat it.

    Dates are ISO, so plain string comparison orders them correctly and no
    parsing is needed for a question that only cares about the day.
    """
    from services.fbref.fixtures.fixtures_service import FixturesService

    today = datetime.now().strftime("%Y-%m-%d")
    past, future = [], []
    for lg in leagues:
        fx = FixturesService.load(lg, SEASON)
        if not fx:
            continue
        for m in fx.get("matches", []):
            d = (m.get("date") or "")[:10]
            if d:
                (past if d <= today else future).append(d)
    return (max(past) if past else None, min(future) if future else None)


def idle_check(leagues: list) -> tuple:
    """SUPERSEDED by stale_leagues() — kept for reference, not called.

    It compared the newest fixture DATE against the date of the last run, so
    "football has happened" meant "a kickoff time has passed" rather than "a
    match finished and we have not ingested it". Both failure modes are
    written up in stale_leagues(); the short version is that `>=` on dates
    means a run on the same day as the last kickoff disables the gate until
    the next one, so three dead days each cost a full hour.

    (original intent below)

    (idle, why). Idle = no fixture has kicked off since the last run.

    WHY THIS IS DERIVED AND NOT A CALENDAR. International breaks are the
    obvious case, but they are not the only one: midweek gaps, winter breaks,
    the end of a season and the weeks before the next one all leave the job
    fetching nothing and rebuilding ratings that cannot have moved. A list of
    break dates would cover one of those, go stale every season, and need a
    human to remember it. The fixture list already knows, for every league,
    and it is on disk.

    THE COMPARISON IS DELIBERATELY CONSERVATIVE — day granularity, and it
    skips only when the newest fixture is STRICTLY older than the day we last
    ran. A run this morning with matches tonight shares a date, so that case
    falls through and the job runs. The cost of being wrong that way is one
    wasted pass; the cost of being wrong the other way is a site a day stale
    with nothing in the log to say why.
    """
    last_kick, next_kick = football_window(leagues)
    if not last_kick or not DAILY_STAMP.exists():
        return False, ""
    try:
        mark = json.loads(DAILY_STAMP.read_text(encoding="utf-8"))
        last_run = str(mark.get("at", ""))[:10]
        was_ready = set(mark.get("leagues") or [])
    except (OSError, ValueError):
        return False, ""                       # unreadable marker: just run
    if not last_run or last_kick >= last_run:
        return False, ""

    # 🐛 THE GATE WOULD HAVE STRANDED A LEAGUE IT HAD JUST ADMITTED.
    # The backfill stamp runs BEFORE this check, by design — that is what
    # lets a league whose events finally landed become ready without a human
    # noticing. But a league becoming ready is not "football happened", so
    # the idle test passed and every build that would have put it on the site
    # was skipped. Serie A and Ligue 1 would have sat at ready, forever, one
    # step from being visible, through an international break nobody was
    # watching. A change in the ready set IS work, whether or not a ball was
    # kicked.
    if set(leagues) != was_ready:
        return False, ""
    ahead = ""
    if next_kick:
        try:
            gap = (datetime.fromisoformat(next_kick).date()
                   - datetime.now().date()).days
            ahead = f", next kickoff {next_kick} ({gap}d away)"
        except ValueError:
            ahead = f", next kickoff {next_kick}"
    return True, (f"last match {last_kick}, last run {last_run}{ahead}")

done: list[tuple[str, str, float]] = []


# ---------------------------------------------------------------------------
# RESUMING AFTER AN INTERRUPTION.
#
# A run is ~100 minutes and it is a child process: closing the session, a
# reboot or a Ctrl-C kills it wherever it happens to be. The DATA it had
# already written survives - sources refresh in place, the event scraper
# writes every ten matches, payloads are per-league files - but the
# ORCHESTRATION restarted from the top, so a resume paid 32 minutes for a
# `sources` step that had succeeded an hour earlier. On 2026-10-25 a run died
# after sources and three of five event steps; all of that was still on disk
# and all of it would have been redone.
#
# So every step that succeeds records itself against today's date, and a
# later run skips what is already done. The file is keyed by date, so
# tomorrow starts clean and there is no cleanup step to forget.
#
# TWO STEPS IGNORE IT, DELIBERATELY. "grade + predict + simulate" and
# "export web" read everything the steps before them produced, so re-running
# them is both cheap and the entire point of resuming - a resume that skipped
# the export would leave the new data unpublished.
STEP_LOG = ROOT / "data" / "reports" / "daily_steps.json"
ALWAYS_RERUN = ("grade + predict + simulate", "export web")
_done_today: dict = {}
_ignore_step_log = False


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def step_log_load() -> dict:
    """{label: seconds} for steps that already succeeded TODAY."""
    try:
        d = json.loads(STEP_LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return (d.get("done") or {}) if d.get("date") == _today() else {}


def step_log_mark(label: str, secs: float) -> None:
    try:
        d = json.loads(STEP_LOG.read_text(encoding="utf-8"))
        if d.get("date") != _today():
            d = {"date": _today(), "done": {}}
    except (OSError, ValueError):
        d = {"date": _today(), "done": {}}
    d.setdefault("done", {})[label] = round(secs, 1)
    try:
        STEP_LOG.parent.mkdir(parents=True, exist_ok=True)
        STEP_LOG.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except OSError:
        pass                      # a lost marker costs a redo, never a crash


DRIVER_NAMES = {"uc_driver.exe", "chromedriver.exe", "chromedriver"}

# A step that prints nothing for this long is stuck, not slow. Measured
# 2026-10-29 across every publish log: the longest healthy silence between
# two timestamped lines was 1m40s (sources, 10-26), and no step other than
# sources has ever run past ten minutes in total. Twenty minutes is twelve
# times clear of a healthy step and a tenth of the afternoon the 10-29 stall
# cost. The 2-hour wall stays as the absolute ceiling.
STALL_SECS = 20 * 60
POLL_SECS = 30
STEP_WALL_SECS = 7200


def kill_tree(p: subprocess.Popen) -> None:
    """Kill a step and everything it started.

    `Popen.kill()` is TerminateProcess on the child alone; a hung step's
    own children (a driver, a browser, a helper python) would outlive it,
    and the first thing an orphan does is hold a handle we need back.
    """
    try:
        import psutil
        procs = psutil.Process(p.pid).children(recursive=True)
    except Exception:  # noqa: BLE001 - psutil missing or child already gone
        procs = []
    for proc in procs:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    try:
        p.kill()
    except Exception:  # noqa: BLE001
        pass
    try:
        p.wait(timeout=30)
    except Exception:  # noqa: BLE001
        pass


def reap_orphan_drivers(since: float) -> None:
    """Kill browser drivers a finished step left behind.

    Scoped tightly, because the user's own Chrome is on this machine: only
    driver binaries (or a HEADLESS chrome) started after `since`, whose
    parent process no longer exists. A driver another live process owns is
    not ours to touch. Best effort: anything here that fails is logged
    and the run moves on.
    """
    try:
        import psutil
    except ImportError:
        return
    for proc in psutil.process_iter(["name", "create_time", "ppid", "cmdline"]):
        try:
            info = proc.info
            name = (info["name"] or "").lower()
            cmd = info["cmdline"] or []
            headless = name == "chrome.exe" and any("--headless" in a for a in cmd)
            if name not in DRIVER_NAMES and not headless:
                continue
            if (info["create_time"] or 0) < since:
                continue
            if psutil.pid_exists(info["ppid"] or 0):
                continue
            proc.kill()
            print(f"    -> reaped orphan {name} (pid {proc.pid})", flush=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception as e:  # noqa: BLE001
            try:
                print(f"    -> reaper: {e}", flush=True)
            except (UnicodeError, OSError):
                pass


def run(label: str, args: list[str], optional: bool = False) -> bool:
    """One step. Never fatal: a source that is down costs that source.

    `optional` MARKS a step, it does not excuse it. The parameter was
    declared here and never read once, which reads as "these failures are
    tolerated" to anyone scanning the call sites — and the five `events`
    steps carry it. They are among the most important steps in the file. So
    it now labels the step in the summary and leaves the exit code alone: a
    step that did not run is news whether or not somebody once expected it
    to be flaky.

    🐛 THIS USED TO USE capture_output=True AND THROW THE OUTPUT AWAY unless
    the step failed. So a run that spent eleven minutes fetching wrote
    nothing anywhere: the admin panel showed an empty box, the terminal went
    silent, and the only way to find out what had been fetched was to read
    file timestamps afterwards. Twice that silence hid a job doing work
    nobody had asked for.

    Now every line is echoed as it arrives — the panel tails this same
    stream — while the last few lines are still kept for the failure
    summary. Live visibility and a useful error message are not a trade.
    """
    if (label in _done_today and label not in ALWAYS_RERUN
            and not _ignore_step_log):
        print()
        print(f"--- {label}", flush=True)
        print(f"    -> skipped: already succeeded today in "
              f"{_done_today[label]}s", flush=True)
        done.append((label, "ok (done earlier today)", 0.0))
        return True

    tag = "" if not optional else " (optional)"
    for attempt in (1, 2):
        t0 = time.time()
        print(f"\n--- {label}" + (" (retry)" if attempt == 2 else ""), flush=True)
        try:
            p = subprocess.Popen(
                [PY, "-u", *args], cwd=ROOT, env=CHILD_ENV,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
            )
            last = deque(maxlen=4)
            seen = [t0]        # when the step last said anything
            quiet = [0.0]      # its longest silence, for the summary

            def pump() -> None:
                for line in p.stdout:              # streams; never buffers
                    now = time.time()
                    quiet[0] = max(quiet[0], now - seen[0])
                    seen[0] = now
                    line = line.rstrip()
                    if line.strip():
                        # NEVER let echoing a line kill the step. The
                        # streams are reconfigured to utf-8 above, which is
                        # the real fix; this is the guarantee. A character
                        # we cannot print is worth losing a log line over,
                        # never a scrape.
                        try:
                            print(f"    {line}", flush=True)
                        except (UnicodeError, OSError):
                            pass
                        last.append(line)

            # The echo runs on its own thread so THIS thread waits on the
            # process, not on the pipe. On 2026-10-29 the injuries step
            # exited at 15:21 and the run sat on `for line in p.stdout`
            # until 17:32, because an orphaned uc_driver.exe the scraper had
            # spawned still held the write end of the pipe: no EOF, no next
            # step, and the 2-hour timeout never got its turn. Waiting on
            # the process means a leaked handle costs a few log lines, not
            # the day - and polling lets a silent step be caught too.
            reader = threading.Thread(target=pump, daemon=True)
            reader.start()
            stalled = False
            while True:
                try:
                    p.wait(timeout=POLL_SECS)
                    break
                except subprocess.TimeoutExpired:
                    now = time.time()
                    if now - t0 > STEP_WALL_SECS:
                        raise
                    if now - seen[0] > STALL_SECS:
                        stalled = True
                        kill_tree(p)
                        break
            reap_orphan_drivers(t0)
            reader.join(timeout=5)
            secs = time.time() - t0
            quiet[0] = max(quiet[0], time.time() - seen[0])
            qnote = f" (quiet max {quiet[0]:.0f}s)"
            if stalled:
                print(f"    -> STALLED: no output for {STALL_SECS // 60} min, "
                      f"killed after {secs:.0f}s", flush=True)
                if attempt == 1:
                    print("    -> retrying once", flush=True)
                    continue
                done.append((label, f"STALLED{tag} twice, no output for "
                                    f"{STALL_SECS // 60} min", secs))
                return False
            ok = p.returncode == 0
            note = "" if ok else f" {' | '.join(last)}"[:200]
            done.append((label, "ok" if ok else f"FAILED{tag}{note}", secs))
            if ok:
                step_log_mark(label, secs)
            print(f"    -> {'ok' if ok else 'FAILED'} in {secs:.1f}s{qnote}",
                  flush=True)
            return ok
        except subprocess.TimeoutExpired:
            # Two hours is not "slow", it is stuck. Leaving it alive would
            # have it racing the next step for the same files.
            kill_tree(p)
            reap_orphan_drivers(t0)
            done.append((label, f"TIMED OUT{tag}", time.time() - t0))
            try:
                print(f"    -> TIMED OUT after {STEP_WALL_SECS // 60} min, "
                      "killed", flush=True)
            except (UnicodeError, OSError):
                pass
            return False
        except Exception as e:  # noqa: BLE001 - a broken step is data, not a crash
            # A step that lands here printed NO outcome line, which is how
            # six of them hid on 2026-10-12 - see the encoding note at the
            # top of this file. Say so on the spot, so the live log shows
            # the gap rather than leaving the next label to imply the last
            # step passed.
            done.append((label, f"ERROR {e}", time.time() - t0))
            try:
                print(f"    -> ERROR {e}", flush=True)
            except (UnicodeError, OSError):
                pass
            return False
    return False


def script(name: str) -> list[str]:
    return [str(ROOT / "scripts" / name)]


def stale_seasons(league: str) -> list:
    """Seasons whose stamped copy is missing or older than the raw events.

    Stamping rewrites a whole season — about 48s — so doing every league
    every morning would be sixteen minutes of work to re-derive files that
    have not changed. Comparing mtimes makes the common case free and still
    catches the two that matter: a season the backfill has just fetched, and
    the current season the daily has just added matches to."""
    d = ROOT / "data" / "whoscored" / league
    if not d.exists():
        return []
    out = []
    for raw in sorted(d.glob("*.parquet")):
        if raw.stem.endswith("_stamped"):
            continue
        stamped = d / f"{raw.stem}_stamped.parquet"
        if (not stamped.exists()
                or stamped.stat().st_mtime < raw.stat().st_mtime):
            out.append(raw.stem)
    return out


def _slug(league: str) -> str:
    return league.lower().replace(" ", "-").replace("--", "-")


def league_state(league: str) -> dict:
    """What this league looks like ON DISK. Three numbers, zero requests.

        played   matches fbref's cached fixture list says were played
        events   matches whose events we actually hold
        overdue  fixtures whose date has passed and are STILL marked unplayed

    `overdue` IS THE ONE THAT NOTICES THE OUTSIDE WORLD, and leaving it out
    was a real bug in the first version of this gate. `played` and `events`
    are both read from our own disk, so if the fixture cache is stale the two
    agree with each other and with the marker, and the gate concludes
    "nothing new" — forever. On 2026-10-23 that skipped all five leagues
    after a full week of football, because the cache had not been refreshed
    since the 16th and therefore did not know the 17th-19th had been played.

    The old date-based gate got this part right for a reason worth keeping: a
    SCHEDULE is known in advance, so a kickoff that has passed is visible
    offline even when the result is not. Counting fixtures that are overdue
    and still unplayed asks "has football happened that we have not caught
    up with" without a single request.

    Day granularity, so a match kicking off today is not overdue until
    tomorrow — the cost of being late by a run is one stale afternoon; the
    cost of being early is thrashing every fixture day.
    """
    from datetime import date as _date
    from services.fbref.fixtures.fixtures_service import FixturesService
    played = overdue = 0
    today = _date.today().isoformat()
    try:
        fx = FixturesService.load(league, SEASON)
        for m in (fx["matches"] if fx else []):
            if m.get("played"):
                played += 1
            elif m.get("date") and m["date"] < today:
                overdue += 1
    except Exception:                                      # noqa: BLE001
        pass
    events = 0
    try:
        import pandas as pd
        pq = ROOT / "data" / "whoscored" / league / f"{SEASON}.parquet"
        if pq.exists():
            events = int(pd.read_parquet(pq, columns=["game_id"])["game_id"]
                         .nunique())
    except Exception:                                      # noqa: BLE001
        pass
    return {"played": played, "events": events, "overdue": overdue}


def stale_leagues(leagues: list, mark: dict | None) -> dict:
    """{league: why} for the leagues with work to do. Everything else is
    skipped — per league, not all-or-nothing.

    THE OLD GATE ASKED THE WRONG QUESTION. idle_check compared the newest
    fixture DATE against the date we last ran, so "football has happened"
    meant "a kickoff time has passed", not "a match finished and we have not
    ingested it". Two ways that went wrong, both observed:

      2026-10-16  last_kick 10-16 >= last_run 10-12 -> not idle. Fixtures
                  were SCHEDULED that evening; none had been played. The run
                  spent 26 min in `sources` and ~8 more re-reading five
                  ten-page WhoScored schedules to find four leftover matches
                  from the 12th.
      2026-10-13  last_kick 10-12 >= last_run 10-12 -> not idle. A run on the
                  same DATE as the last kickoff disabled the gate until the
                  next one, so three dead days each cost a full hour.

    Counting what is on disk against what fbref says was played answers the
    real question for free, and answers it per league, so a quiet league
    costs nothing while a busy one is still rebuilt in full.

    THE RETRY TRAP, AND WHY THE MARKER STORES COUNTS. A match WhoScored never
    publishes events for would leave played > events forever, marking its
    league stale on every future run — the old gate's permanent-outage bug
    wearing different clothes. So the test is not "is there a gap" but "has
    the gap CHANGED since we last ran": the marker records each league's
    (played, events) pair after the work, and an unchanged pair means we
    already tried and there is nothing new to try. A newly played match moves
    `played` and the league goes stale again on its own.
    """
    prev = (mark or {}).get("state") or {}
    out: dict = {}
    for lg in leagues:
        now = league_state(lg)
        was = prev.get(lg)
        if not (ROOT / "data" / "web" / "team" / _slug(lg)).exists():
            out[lg] = "no team payload on disk"
        elif was is None:
            out[lg] = f"no record from a previous run ({now['played']} played)"
        elif now != was:
            bits = [f"{k} {was.get(k, '?')}->{now[k]}"
                    for k in ("played", "events", "overdue")
                    if was.get(k) != now[k]]
            out[lg] = ", ".join(bits) or "state changed"
    return out


def stamp_pass(label: str, leagues: list) -> None:
    """Bring every stamped file level with its raw events."""
    for lg in leagues:
        todo = stale_seasons(lg)
        if todo:
            run(f"stamp {label} {lg} [{','.join(todo)}]",
                script("stamp_event_state.py")
                + ["--league", lg, "--seasons", *todo],
                optional=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-scrape", action="store_true",
                    help="rebuild everything from what is already on disk")
    ap.add_argument("--league", action="append", dest="leagues", default=None,
                    help="restrict to these leagues (repeatable); "
                         "default is every league with enough event history")
    ap.add_argument("--force", action="store_true",
                    help="run the full job even if no football has been "
                         "played since the last run")
    ap.add_argument("--plan", action="store_true",
                    help="print what this run WOULD do, then exit. Costs "
                         "nothing: the decision is read off disk")
    args = ap.parse_args()

    # WHAT ALREADY SUCCEEDED TODAY. A resume skips it; --force ignores the
    # log and does everything again.
    global _done_today, _ignore_step_log
    _ignore_step_log = args.force
    _done_today = {} if args.force else step_log_load()
    if _done_today:
        mins = sum(_done_today.values()) / 60
        print(f"  resuming: {len(_done_today)} step(s) already succeeded "
              f"today ({mins:.0f} min of work kept)")

    # 🐛 READINESS COULD NEVER RESOLVE ITSELF.
    #
    # Nothing downstream reads {season}.parquet — everything reads the
    # STAMPED copy — and is_ready() asks which stamped files exist. But
    # stamping only ran for leagues already in `leagues`, i.e. already
    # ready. So a league the backfill had fetched completely stayed
    # invisible forever: La Liga and the Bundesliga sat with every season
    # they needed on disk and could not enter the daily, because entering
    # required the very files that only running the daily would create.
    #
    # Stamping is local, costs about 48s a season and touches nothing but
    # its own output, so it runs for EVERY league with raw events — not
    # just the built ones. Readiness is then decided after, on the files
    # that now exist.
    # --plan must cost nothing, and stamping is work. Readiness is then read
    # from whatever is already stamped, which is what a plan should reflect.
    if not args.plan:
        stamp_pass("backfill", args.leagues or ALL_LEAGUES)

    leagues = args.leagues or ready_leagues()
    if not leagues:
        print("no league has enough event history yet — nothing to build")
        return 1

    # Say which leagues are in and which are waiting, every run. A job that
    # silently covers one league of five looks identical to one covering all
    # of them, and that ambiguity has cost a morning already.
    if not args.leagues:
        for lg, d in readiness().items():
            mark = "  build" if d["ready"] else "  skip "
            why = "" if d["ready"] else f" (needs {', '.join(d['missing'])})"
            print(f"{mark} {lg}{why}")
        print(f"  -> {len(leagues)} of {len(ALL_LEAGUES)} leagues\n")

    # ---- 0. IS THERE ANYTHING TO DO? -------------------------------------
    # In an international break the job used to run in full: five schedule
    # fetches (~10 month pages each), a fetch loop that asked for nothing,
    # and a complete rebuild of ratings, Elo and every payload — all to
    # reproduce yesterday's numbers exactly, because no match had been played.
    #
    # Idle does NOT mean do nothing. Two things genuinely move while the
    # football is stopped, and both feed what the site shows: players get
    # injured on international duty, and kickoff times get moved. So the
    # cheap half still runs and the expensive half — everything that can
    # only change when a match is played — is skipped.
    try:
        mark = json.loads(DAILY_STAMP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        mark = None

    # A league joining the build is work even though no ball was kicked —
    # the same case the old gate had to be taught, kept here deliberately.
    joined = set(leagues) - set((mark or {}).get("leagues") or [])

    if args.force:
        work = {lg: "--force" for lg in leagues}
    else:
        work = stale_leagues(leagues, mark)
        for lg in joined:
            work.setdefault(lg, "newly ready for building")

    fresh = [lg for lg in leagues if lg in work]
    quiet = [lg for lg in leagues if lg not in work]
    idle = not fresh

    print()
    print("  what needs doing, measured on disk:")
    for lg in leagues:
        if lg in work:
            print(f"    WORK  {lg:<22} {work[lg]}")
        else:
            print(f"    skip  {lg:<22} nothing new since the last run")
    if quiet:
        print()
        print(f"  {len(quiet)} league(s) skipped: no sources, no events, "
              f"no rebuild.")
        print("  Injuries still refresh for EVERY league - players get "
              "hurt on")
        print("  international duty, and that is not a match result.")
    if idle:
        print()
        print("  NOTHING PLAYED ANYWHERE since the last run. Skipping "
              "sources,")
        print("  events, stamping, ratings, Elo, mental, shots, passes "
              "and managers.")
        print("  Still running: injuries, grading, predictions, export.")
    print()

    if args.plan:
        # The whole point of deciding from disk is that the decision can be
        # inspected without paying for it. A gate nobody can check is a gate
        # nobody trusts — and the last one was wrong for weeks.
        print(f"  --plan: would run {len(fresh)} league(s) in full, "
              f"skip {len(quiet)}, and nothing else happened.")
        return 0

    started = datetime.now()
    print(f"daily update  {started:%Y-%m-%d %H:%M}")

    # ---- 1. sources ONLY -------------------------------------------------
    if not args.no_scrape:
        # run_weekly already knows how to refresh fixtures, Understat, shots,
        # rosters and injuries. It is reused rather than reimplemented so
        # there is one definition of what a source refresh means.
        #
        # 🐛 THIS USED TO BE THE WHOLE OF run_weekly, GRADING AND PREDICTING
        # INCLUDED, AND IT RAN BEFORE THE RATINGS WERE REBUILT. So the
        # published triplet — which since 2026-09-20 blends the Elo arm —
        # was priced every morning from an Elo table that had not yet seen
        # last night's results. A day of lag, hidden inside the job whose
        # entire purpose is not being a day behind.
        #
        # Sources now stop here; grading, prediction and the season
        # simulation happen in step 3, after the ratings are refitted.
        # 🐛 --league MUST BE FORWARDED. Without it run_weekly looped all
        # five leagues and rebuilt fixtures, the Understat name map,
        # Understat, players, shots, rosters, fbref players and injuries for
        # every one — forty source builds, several forcing refresh=True — to
        # pick up the handful of English matches played yesterday. An
        # "England only" daily spent over ten minutes in this single step.
        # ONLY THE LEAGUES WITH SOMETHING NEW. Each league here is eight
        # source builds, several rate-limited: soccerdata sleeps 7s before
        # every fbref request and 5-10s before every WhoScored one. A league
        # with nothing new is minutes of sleeping to be told what we knew.
        if fresh:
            league_args = []
            for lg in fresh:
                league_args += ["--league", lg]
            run("sources", script("run_weekly.py")
                + ["--sources-only"] + league_args)

        # INJURIES ARE NOT A MATCH RESULT, so they refresh for every league
        # including the quiet ones: they concern UPCOMING fixtures, they move
        # during international breaks, and the site shows them. Only the
        # leagues `sources` skipped need this; the others just did it.
        if quiet:
            inj_args = []
            for lg in quiet:
                inj_args += ["--league", lg]
            run("injuries (quiet leagues)",
                script("scrape_injuries.py") + inj_args, optional=True)
        # Skipped when idle: the scraper would ask each league for matches it
        # already has and be told there are none — after paying for the
        # schedule pages that establish it.
        for lg in fresh:
            # INCREMENTAL BY DESIGN: the event scraper reads the parquet it
            # already has and asks only for matches missing from it, so a
            # daily run fetches a handful and a skipped week fetches that
            # week. Nothing here re-downloads a season.
            # --seasons IS EXPLICIT SO THIS CAN NEVER BECOME A BACKFILL.
            # The script's default was once two past seasons, which meant a
            # league with no history on disk turned the "daily update" into
            # a 2,744-match job. A daily run fetches the season we are in,
            # and only the fixtures inside it that have been played.
            run(f"events {lg}",
                script("build_whoscored_events.py")
                + ["--league", lg, "--seasons", SEASON],
                optional=True)

    # ---- 1b. STAMP AGAIN, for what the fetch above just added -------------
    # The first pass ran before readiness was decided, because it had to:
    # nothing reads the raw parquet, is_ready() asks which STAMPED files
    # exist, and stamping used to run only for leagues already ready — so a
    # league the backfill had fetched completely could never enter. La Liga
    # and the Bundesliga sat with every season they needed on disk and stayed
    # invisible. This second pass is the cheap one: only the current season
    # has moved, and stale_seasons() skips everything else by mtime.
    if fresh:
        stamp_pass("today", fresh)

    # ---- 2. RATINGS, rebuilt on what was just fetched ---------------------
    # Everything the predictor reads must be refitted before it runs: the
    # form/team layer, the injuries it deducts, and the Elo arm that now
    # owns P(draw) in the published triplet.
    for lg in leagues:
        # The injury payload is the ONE thing here that moves without a match
        # being played — an international-duty injury is exactly the case —
        # so it is rebuilt even when idle. The other three are functions of
        # match events and cannot have changed.
        if lg in work:
            run(f"team web {lg}", script("build_team_web.py") + ["--league", lg])
            run(f"team plots {lg}", script("build_team_plots.py") + ["--league", lg])
            run(f"form {lg}", script("build_team_form.py") + ["--league", lg])
        run(f"injuries web {lg}", script("build_injury_web.py") + ["--league", lg])

    # 🐛 THIS WAS build_process_elo.py PER LEAGUE, AND IT ONLY EVER WORKED
    # BECAUSE THE DAILY RUN HAD ONLY EVER BEEN GIVEN ONE LEAGUE. That
    # script's default loader reads data/whoscored/{league}/{season}_stamped
    # .parquet, so four of the five steps would have died with KeyError
    # 'kick' — an empty frame — the first time this ran across all five.
    #
    # build_elo_all.py is the shipping path: it fits each league separately
    # from UNDERSTAT xG, which exists for thirteen seasons of all five
    # leagues, so it needs no event stream and about 4,500 matches a league
    # instead of 380. One call covers every league, which is also why it
    # sits outside the loop — its report and params file are written whole,
    # and calling it per league would have each run overwrite the last.
    if fresh:
        run("elo (all leagues)", script("build_elo_all.py"))
        run("reliability", script("build_reliability.py"))
    # PER LEAGUE. build_mental_web takes one league at a time and defaults to
    # England, so calling it bare built only England however many leagues
    # were ready — the players board had no way to show anything else.
    for lg in fresh:
        run(f"mental web {lg}",
            script("build_mental_web.py") + ["--league", lg],
            optional=True)

    # ---- 3. grade, predict, simulate — ON TODAY'S RATINGS -----------------
    # The second half of run_weekly, run now that step 2 has refitted
    # everything it depends on. In order: the ledger and history are graded
    # against last night's results (the TRACK RECORD), the predictor prices
    # the coming round from the ratings above (the PREDICTOR), and the
    # season is re-simulated from those prices (the PROJECTED TABLE).
    # --no-refresh always: step 1 has already fetched, and with --no-scrape
    # there is deliberately nothing to fetch. Either way this half must not
    # go back to the network.
    run("grade + predict + simulate",
        script("run_weekly.py") + ["--no-refresh"])

    # ---- 4. payloads the static site reads -------------------------------
    # Shot maps, pass maps and kits are all derived from match events, so an
    # idle day cannot change any of them. export_web below still runs: the
    # predictions and the injury payload above have moved, and it is the step
    # that puts them where the site reads from.
    for lg in fresh:
        run(f"shots web {lg}", script("build_shot_web.py") + ["--league", lg])
        run(f"passes {lg}", script("build_pass_web.py") + ["--league", lg])
        # MANAGERS: a payload, not a rating. Nothing downstream reads it —
        # the predictor never sees a manager score — so it belongs here with
        # the other things the site reads and NOT in step 2, where being
        # early would only mean being early. Its inputs are the stamped
        # events (step 1b) and Understat shots (step 1), both already done.
        #
        # PER LEAGUE, and skipped when idle, for the same reason shots and
        # passes are: a spell is built out of match events, so with no match
        # played every metric in the table is arithmetically identical to
        # yesterday's. The only field that would move is `generated`, a
        # date stamp carrying no information, and rebuilding five leagues of
        # spells to change five date strings is exactly the work the gate
        # exists to stop.
        run(f"managers {lg}",
            script("build_manager_web.py") + ["--league", lg],
            optional=True)
    if fresh:
        run("kits", script("build_kits.py"))

    # LAST, because it reads the season sim and the graded history that the
    # steps above have just refreshed. Exporting first was how round.json
    # ended up four days older than the results sitting beside it.
    run("export web", script("export_web.py"))

    # ---- summary ---------------------------------------------------------
    # WHY THE FAILURE LIST SHOUTS. The exit code has always been right and
    # daily.log has recorded every failure since September — and none of it
    # surfaced. The run ended on a tidy "38/51 steps ok" that reads like a
    # pass, with thirteen "!!" lines scrolled off above it, and the data went
    # stale for weeks. A partial run is not a pass and must not look like one.
    bad = [d for d in done if d[1] != "ok"]
    print(f"\n{len(done) - len(bad)}/{len(done)} steps ok "
          f"in {(datetime.now() - started).total_seconds() / 60:.1f} min")
    for label, status, secs in done:
        mark = "  " if status == "ok" else "!!"
        print(f"{mark} {label:<34} {status:<28} {secs:5.1f}s")

    if bad:
        W = 70
        print()
        print("=" * W)
        print(f"  {len(bad)} OF {len(done)} STEPS DID NOT RUN".center(W))
        print("=" * W)
        for label, status, _ in bad:
            print(f"  !! {label:<34} {status[:30]}")
        print()
        print("  The site still serves the last good answer for whatever")
        print("  missed, so nothing looks wrong on screen — which is exactly")
        print("  why this needs reading. The run marker was NOT written, so")
        print("  the next run redoes this work rather than skipping it.")
        print("=" * W)
    else:
        print()
        print(f"  all {len(done)} steps ok - marker written")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{started:%Y-%m-%d %H:%M}  "
                 f"{len(done) - len(bad)}/{len(done)} ok"
                 + ("" if not bad else "  failed: " + ", ".join(b[0] for b in bad))
                 + "\n")

    # THE MARKER IS WRITTEN ONLY ON A CLEAN RUN, and that is the whole safety
    # of the idle gate. If a step failed, the next run must not be able to
    # conclude "nothing has happened since last time" and skip the very work
    # that just broke — an idle gate that inherits a failed run turns one bad
    # morning into a permanent, silent outage.
    if not bad:
        DAILY_STAMP.parent.mkdir(parents=True, exist_ok=True)
        DAILY_STAMP.write_text(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            # Recorded so the next run can tell "nothing happened" from
            # "a league joined" — see stale_leagues.
            "leagues": sorted(leagues),
            # AND the per-league counts the next run compares against. These
            # are read AFTER the work, so an unchanged pair next time means
            # "we already tried and there is nothing new" rather than "there
            # is a gap" — which is what stops a match WhoScored never
            # publishes from marking its league stale forever.
            "state": {lg: league_state(lg) for lg in leagues},
        }, indent=2), encoding="utf-8")

    # A failed step is news, not a crash: the site still has yesterday's
    # answer for whatever missed, and the exit code says somebody should look.
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
