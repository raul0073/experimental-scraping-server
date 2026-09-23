"""Run the daily update by hand, from the site.

WHY THIS EXISTS. The 09:00 scheduled task keeps missing — the machine is
asleep, or the window passes, or a run dies halfway — and the failure is
silent: the site keeps serving whatever it last had, looking exactly as it
does when everything is fine. A button that says UPDATE ALL TO TODAY, next
to a line saying when the data was actually generated, turns a silent
staleness into something you can see and fix in one click.

LOCALHOST ONLY, DELIBERATELY. This endpoint executes a script. The API
binds 0.0.0.0 and allows every CORS origin, so without a guard it would be
a remote command trigger for anyone on the network. The check is on the
socket's peer address, which cannot be spoofed by a header the way
X-Forwarded-For can.

ONE AT A TIME. run_daily rewrites the same payloads the site reads; two of
them interleaved would produce a round.json from one run and a record.json
from another. A second request while one is running is refused, not queued.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from services.data_ready import ALL_LEAGUES, readiness, ready_leagues

router = APIRouter(tags=["Admin"])

ROOT = Path(__file__).resolve().parent.parent.parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
SCRIPT = str(ROOT / "scripts" / "run_daily.py")
DAILY_LOG = ROOT / "data" / "reports" / "daily.log"
RUN_LOG = ROOT / "data" / "reports" / "daily_manual.log"
ROUND = ROOT / "data" / "web" / "round.json"

# THE BUTTON IS THE DAILY. Same script, same league rule, same season — it
# is the 09:00 job run on demand, not a second code path that can drift from
# it. The leagues come from services/data_ready.py, so today that is England
# and the day La Liga's history lands it becomes England and La Liga, with
# nothing here to remember to change.
SEASON = "2627"
HISTORY = ROOT / "data" / "web" / "history.json"


def _fixtures(league: str) -> Path:
    return ROOT / "data" / "fixtures" / league / f"{SEASON}.json"


def _events(league: str) -> Path:
    return ROOT / "data" / "whoscored" / league / f"{SEASON}_stamped.parquet"

LOCAL = {"127.0.0.1", "::1", "localhost"}

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_started: datetime | None = None
_finished: datetime | None = None
_returncode: int | None = None


def _require_local(request: Request) -> None:
    host = (request.client.host if request.client else "") or ""
    if host not in LOCAL:
        raise HTTPException(status_code=403, detail="localhost only")


def _running() -> bool:
    return _proc is not None and _proc.poll() is None


def _watch(p: subprocess.Popen) -> None:
    """Record how it ended, so the UI can say so rather than just going quiet."""
    global _finished, _returncode
    p.wait()
    _returncode = p.returncode
    _finished = datetime.now()


def _last_scheduled_run() -> str | None:
    """The last line run_daily appends — '<when>  n/m ok[ failed: ...]'."""
    try:
        lines = [l for l in DAILY_LOG.read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        return lines[-1] if lines else None
    except Exception:
        return None


def _data_generated() -> str | None:
    """When the payload the SITE is serving was built. This is the number
    that matters — a run that succeeded but was never exported leaves this
    stale, and that is exactly the failure worth surfacing."""
    try:
        return json.loads(ROUND.read_text(encoding="utf-8")).get("generated")
    except Exception:
        return None


def _stale_league(league: str) -> dict:
    """What, if anything, is out of date for ONE league — WITHOUT touching
    the network.

    The button has to be able to say "everything is up to date" honestly, and
    it cannot do that by scraping first: that is the thing it is deciding
    whether to do. So every check below reads only what is already on disk
    and compares it against the clock.

    A fixture counts as due once its kickoff is three hours past, the same
    margin the event fetcher uses to decide a match has finished.
    """
    now = datetime.now()
    reasons: list[str] = []

    played: list[dict] = []
    try:
        fx = json.loads(_fixtures(league).read_text(encoding="utf-8"))["matches"]
    except Exception:
        return {"stale": True, "reasons": ["no fixture file on disk"],
                "checks": {}}

    due = 0
    for m in fx:
        # `time` is "20:00 (22:00)" — kickoff plus a bracketed alternative
        # timezone — so only the first five characters are a clock.
        clock = (m.get("time") or "00:00")[:5]
        try:
            when = datetime.fromisoformat(f"{m['date']}T{clock}")
        except Exception:
            try:
                when = datetime.fromisoformat(m["date"])   # date alone
            except Exception:
                continue
        if (now - when).total_seconds() < 3 * 3600:
            continue                       # not finished yet — nothing owed
        due += 1
        if m.get("home_goals") is None:
            continue                       # result not fetched
        played.append(m)

    # 1. results: kicked off, finished, and we still have no score
    missing_results = due - len(played)
    if missing_results > 0:
        reasons.append(f"{missing_results} finished fixture(s) with no result")

    # 2. events: a played match whose events we have never fetched
    ev = None
    try:
        import pandas as pd
        ev = int(pd.read_parquet(_events(league), columns=["game_id"])["game_id"].nunique())
    except Exception:
        ev = 0
    if ev < len(played):
        reasons.append(f"events for {len(played) - ev} played match(es)")

    # 3. the published payload is older than the newest result it should show
    generated = _data_generated()
    newest = max((m["date"] for m in played), default=None)
    if generated and newest and generated[:10] < newest[:10]:
        reasons.append(f"site shows {generated[:10]}, newest result is {newest}")

    # 4. anything still pending in the graded record whose match has finished
    try:
        h = json.loads(HISTORY.read_text(encoding="utf-8"))
        lg = (h.get("leagues") or {}).get(league) or {}
        pending = sum(1 for r in (lg.get("rows") or [])
                      if r.get("status") != "graded"
                      and r.get("kickoff", "")[:10] <= now.strftime("%Y-%m-%d"))
        if pending:
            reasons.append(f"{pending} finished fixture(s) ungraded")
    except Exception:
        pass

    return {
        "stale": bool(reasons),
        "reasons": reasons,
        "checks": {"fixtures_due": due, "results_on_disk": len(played),
                   "events_stored": ev, "site_generated": generated,
                   "newest_result": newest},
    }


def _stale() -> dict:
    """Aggregated across every league the daily would actually build.

    Reasons are prefixed with the league so "events for 10 played match(es)"
    cannot be read as applying to all of them — the whole point of this
    panel is that one league updating is visibly different from five."""
    leagues = ready_leagues()
    per = {lg: _stale_league(lg) for lg in leagues}
    reasons = [f"{lg.split('-')[-1]}: {r}"
               for lg, d in per.items() for r in d["reasons"]]
    return {
        "stale": any(d["stale"] for d in per.values()),
        "reasons": reasons,
        "leagues": leagues,
        "waiting": [lg for lg in ALL_LEAGUES if lg not in leagues],
        "readiness": readiness(),
        "checks": (per[leagues[0]]["checks"] if len(leagues) == 1 else {}),
        "per_league": per,
    }


EVENTS_SCRIPT = str(ROOT / "scripts" / "build_whoscored_events.py")
STAMP_SCRIPT = str(ROOT / "scripts" / "stamp_event_state.py")
SEASONS = ["2324", "2425", "2526", "2627"]


def _season_rows(league: str) -> list:
    """Per season: what is on disk, raw and stamped.

    The two counts are shown separately on purpose. Nothing downstream reads
    the raw parquet — a season with 380 raw and 0 stamped is invisible to the
    ratings, and that gap has already cost a morning once.
    """
    import pandas as pd
    rows = []
    for s in SEASONS:
        raw = ROOT / "data" / "whoscored" / league / f"{s}.parquet"
        stamped = ROOT / "data" / "whoscored" / league / f"{s}_stamped.parquet"
        def count(p):
            try:
                return int(pd.read_parquet(p, columns=["game_id"])["game_id"].nunique())
            except Exception:
                return 0
        def when(p):
            try:
                return datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")
            except Exception:
                return None
        rows.append({"season": s, "raw": count(raw), "stamped": count(stamped),
                     "raw_at": when(raw), "stamped_at": when(stamped)})
    return rows


@router.get("/api/v2/admin/leagues")
async def leagues(request: Request) -> dict:
    """Everything the panel shows: where each league stands, per season."""
    _require_local(request)
    ready = ready_leagues()
    rd = readiness()
    out = []
    for lg in ALL_LEAGUES:
        seasons = _season_rows(lg)
        played = fixtures_total = 0
        try:
            fx = json.loads(_fixtures(lg).read_text(encoding="utf-8"))
            fixtures_total = fx.get("match_count") or len(fx.get("matches") or [])
            played = fx.get("played_count") or 0
        except Exception:
            pass
        out.append({
            "league": lg,
            "short": lg.split("-")[-1],
            "ready": lg in ready,
            "missing_seasons": rd[lg]["missing"],
            "in_daily": lg in ready,
            "fixtures_total": fixtures_total,
            "played_this_season": played,
            "seasons": seasons,
            "stale": _stale_league(lg) if lg in ready else None,
        })
    return {"leagues": out, "ready": ready, "running": _running(),
            "today": datetime.now().strftime("%Y-%m-%d"),
            "site_generated": _data_generated()}


SCRAPE_LOG = ROOT / "data" / "reports" / "scrape.log"


def _tail(n: int = 40) -> list[str]:
    try:
        return RUN_LOG.read_text(encoding="utf-8",
                                 errors="replace").splitlines()[-n:]
    except Exception:
        return []


@router.get("/api/v2/admin/scrapelog")
async def scrapelog(request: Request, lines: int = 120) -> dict:
    """The fetch log, whoever started the job.

    🐛 THE PANEL USED TO SHOW ONLY daily_manual.log, which admin.py writes
    when IT spawns a job — so a run started from a terminal, or by the
    scheduled task, left the panel showing an empty box while work was
    happening. Anything that fetches now appends to scrape.log, and this
    reads that file directly, so the panel sees every run regardless of who
    started it.
    """
    _require_local(request)
    try:
        text = SCRAPE_LOG.read_text(encoding="utf-8", errors="replace")
        rows = text.splitlines()[-max(1, min(lines, 500)):]
    except Exception:
        rows = []
    try:
        mtime = datetime.fromtimestamp(
            SCRAPE_LOG.stat().st_mtime).isoformat(timespec="seconds")
    except Exception:
        mtime = None
    # Any python actually fetching right now, whoever launched it.
    busy = _running()
    return {"lines": rows, "modified": mtime, "running": busy,
            "path": str(SCRAPE_LOG)}


@router.get("/api/v2/admin/status")
async def status(request: Request) -> dict:
    _require_local(request)
    return {
        "leagues": ready_leagues(),
        "stale": _stale(),
        "running": _running(),
        "started": _started.isoformat(timespec="seconds") if _started else None,
        "finished": (_finished.isoformat(timespec="seconds")
                     if _finished and not _running() else None),
        "returncode": None if _running() else _returncode,
        "last_run": _last_scheduled_run(),
        "data_generated": _data_generated(),
        "today": datetime.now().strftime("%Y-%m-%d"),
        "tail": _tail(),
    }


def _spawn(argv: list, label: str) -> dict:
    """Start one job, detached, with its output where the panel can read it."""
    global _proc, _started, _finished, _returncode
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    fh = RUN_LOG.open("w", encoding="utf-8")
    fh.write(f"{label}\nstarted {datetime.now():%Y-%m-%d %H:%M:%S}\n"
             f"$ {' '.join(argv[1:])}\n\n")
    fh.flush()
    _proc = subprocess.Popen(
        argv, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT,
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                       if sys.platform == "win32" else 0),
    )
    _started, _finished, _returncode = datetime.now(), None, None
    threading.Thread(target=_watch, args=(_proc,), daemon=True).start()
    return {"started": _started.isoformat(timespec="seconds"), "running": True,
            "label": label, "command": argv[1:]}


@router.post("/api/v2/admin/league/{action}")
async def league_job(action: str, request: Request, league: str,
                     season: str | None = None,
                     until: str | None = None) -> dict:
    """Per-league control, so nothing runs that was not explicitly asked for.

      daily   the full pipeline for ONE league — sources, events, stamp,
              ratings, grade, predict, simulate, export
      events  fetch that league's events only, optionally bounded by
              --until, for bringing history forward in controlled chunks
      stamp   rebuild the stamped parquet from raw already on disk (no
              network at all)
    """
    _require_local(request)
    if league not in ALL_LEAGUES:
        raise HTTPException(status_code=400, detail=f"unknown league {league}")
    with _lock:
        if _running():
            raise HTTPException(status_code=409, detail="a job is already running")

        if action == "daily":
            return _spawn([PY, "-u", SCRIPT, "--league", league],
                          f"daily · {league}")
        if action == "events":
            argv = [PY, "-u", EVENTS_SCRIPT, "--league", league,
                    "--seasons", *(([season] if season else SEASONS))]
            if until:
                argv += ["--until", until]
            scope = season or "all seasons"
            return _spawn(argv, f"events · {league} · {scope}"
                                + (f" · until {until}" if until else ""))
        if action == "stamp":
            return _spawn([PY, "-u", STAMP_SCRIPT, "--league", league],
                          f"stamp · {league}")
    raise HTTPException(status_code=400, detail=f"unknown action {action}")


@router.post("/api/v2/admin/update")
async def update(request: Request, force: bool = False) -> dict:
    """Start a full daily update for England. Returns immediately; poll /status.

    Does NOTHING and says so when there is nothing to fetch — the check is
    entirely local, so answering "up to date" costs no requests. ?force=1
    overrides, for when the payload needs rebuilding from data already held.
    """
    _require_local(request)
    global _proc, _started, _finished, _returncode

    with _lock:
        if _running():
            raise HTTPException(status_code=409,
                                detail="an update is already running")

        state = _stale()
        if not state["leagues"]:
            return {"running": False, "up_to_date": True,
                    "message": "No league has enough event history yet",
                    "leagues": [], "checks": {}}
        if not state["stale"] and not force:
            names = ", ".join(lg.split("-")[-1] for lg in state["leagues"])
            return {"running": False, "up_to_date": True,
                    "message": f"Everything is up to date ({names})",
                    "leagues": state["leagues"], "checks": state["checks"]}

        # --league per ready league. NEVER bare: run_daily with no --league
        # would build whatever it decides is ready, and this endpoint should
        # run exactly what it just told the user it would.
        league_args = []
        for lg in state["leagues"]:
            league_args += ["--league", lg]
        RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
        fh = RUN_LOG.open("w", encoding="utf-8")
        fh.write(f"manual update started {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        fh.flush()
        # --league IS NOT OPTIONAL HERE. Without it run_daily loops all five
        # leagues, which is both the wrong phase and the reason an "England
        # only" run once spent eleven minutes before reaching England.
        _proc = subprocess.Popen(
            [PY, "-u", SCRIPT, *league_args], cwd=str(ROOT),
            stdout=fh, stderr=subprocess.STDOUT,
            # detach enough that closing the API does not kill a half-written
            # rebuild; CREATE_NEW_PROCESS_GROUP is Windows' way of saying so
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if sys.platform == "win32" else 0),
        )
        _started, _finished, _returncode = datetime.now(), None, None
        threading.Thread(target=_watch, args=(_proc,), daemon=True).start()

    return {"started": _started.isoformat(timespec="seconds"), "running": True}
