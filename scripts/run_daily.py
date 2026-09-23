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
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # before the services import below
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
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

done: list[tuple[str, str, float]] = []


def run(label: str, args: list[str], optional: bool = False) -> bool:
    """One step. Never fatal: a source that is down costs that source.

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
    t0 = time.time()
    print(f"\n--- {label}", flush=True)
    try:
        p = subprocess.Popen(
            [PY, "-u", *args], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
        last = deque(maxlen=4)
        for line in p.stdout:                      # streams; never buffers
            line = line.rstrip()
            if line.strip():
                print(f"    {line}", flush=True)
                last.append(line)
        p.wait(timeout=7200)
        ok = p.returncode == 0
        note = "" if ok else f" {' | '.join(last)}"[:200]
        secs = time.time() - t0
        done.append((label, "ok" if ok else f"FAILED{note}", secs))
        print(f"    -> {'ok' if ok else 'FAILED'} in {secs:.1f}s", flush=True)
        return ok
    except subprocess.TimeoutExpired:
        done.append((label, "TIMED OUT", time.time() - t0))
    except Exception as e:  # noqa: BLE001 - a broken step is data, not a crash
        done.append((label, f"ERROR {e}", time.time() - t0))
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
    args = ap.parse_args()

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
        league_args = []
        for lg in leagues:
            league_args += ["--league", lg]
        run("sources", script("run_weekly.py") + ["--sources-only"] + league_args)
        for lg in leagues:
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
    stamp_pass("today", leagues)

    # ---- 2. RATINGS, rebuilt on what was just fetched ---------------------
    # Everything the predictor reads must be refitted before it runs: the
    # form/team layer, the injuries it deducts, and the Elo arm that now
    # owns P(draw) in the published triplet.
    for lg in leagues:
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
    run("elo (all leagues)", script("build_elo_all.py"))

    run("reliability", script("build_reliability.py"))
    # PER LEAGUE. build_mental_web takes one league at a time and defaults to
    # England, so calling it bare built only England however many leagues
    # were ready — the players board had no way to show anything else.
    for lg in leagues:
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
    for lg in leagues:
        run(f"shots web {lg}", script("build_shot_web.py") + ["--league", lg])
        run(f"passes {lg}", script("build_pass_web.py") + ["--league", lg])
    run("kits", script("build_kits.py"))

    # LAST, because it reads the season sim and the graded history that the
    # steps above have just refreshed. Exporting first was how round.json
    # ended up four days older than the results sitting beside it.
    run("export web", script("export_web.py"))

    # ---- summary ---------------------------------------------------------
    bad = [d for d in done if d[1] != "ok"]
    print(f"\n{len(done) - len(bad)}/{len(done)} steps ok "
          f"in {(datetime.now() - started).total_seconds() / 60:.1f} min")
    for label, status, secs in done:
        mark = "  " if status == "ok" else "!!"
        print(f"{mark} {label:<34} {status:<28} {secs:5.1f}s")

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{started:%Y-%m-%d %H:%M}  "
                 f"{len(done) - len(bad)}/{len(done)} ok"
                 + ("" if not bad else "  failed: " + ", ".join(b[0] for b in bad))
                 + "\n")

    # A failed step is news, not a crash: the site still has yesterday's
    # answer for whatever missed, and the exit code says somebody should look.
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
