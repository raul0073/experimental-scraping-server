"""The pipeline's own contracts, checked in seconds, on COPIES of the ledgers.

    .venv/Scripts/python.exe scripts/selfcheck.py            # every case
    .venv/Scripts/python.exe scripts/selfcheck.py -k window  # a subset

WHY THIS EXISTS. A daily run is 60-100 minutes and it was the test harness:
three pipeline changes on 2026-10-23, two of them wrong, each needing a full
run to disprove, and the user found both. Every case here is a bug that
actually happened (progress.md, "NEXT UP: scripts/selfcheck.py"), reduced to
a fixture that fails in milliseconds.

TWO THINGS IT MUST NOT DO: touch the network, or write to the real ledgers.
Every service locates its files with a path RELATIVE TO THE WORKING
DIRECTORY (data/ledger/picks.jsonl, data/fixtures/...), so each case runs
inside a temp directory holding copies, and the module constants that are
anchored to the repo root (run_daily.ROOT, publish.PUB) are pointed at the
same temp directory for the duration of the case. main() hashes the real
ledgers before and after and refuses to pass if one moved — a test that can
corrupt picks.jsonl is worse than no test.

publish.py runs this as STAGE 0, before anything is updated or deployed.
tests/test_selfcheck.py runs the same CASES under pytest; the logic lives
here, once.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SOCCERDATA_LOGLEVEL", "WARNING")   # soccerdata chatters at import
logging.disable(logging.WARNING)                           # services log expected misses

for _stream in (sys.stdout, sys.stderr):                   # cp1255 console, see publish.py
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SEASON = "2627"
LEAGUES = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A",
           "GER-Bundesliga", "FRA-Ligue 1"]
TODAY = date.today()

# The real ledgers. Read once, copied into every sandbox, never written.
REAL_LEDGERS = [
    ROOT / "data" / "history" / "predictions.jsonl",
    ROOT / "data" / "ledger" / "picks.jsonl",
    ROOT / "data" / "slips" / "slips.jsonl",
    ROOT / "data" / "slips" / "gold.jsonl",
]


def _load_script(name: str):
    """scripts/ is not a package; load run_daily / publish by path."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_daily = _load_script("run_daily")
publish = _load_script("publish")

from services.predictions.gold_ledger import GoldLedger            # noqa: E402
from services.predictions.history_service import HistoryService    # noqa: E402
from services.predictions.ledger_service import LedgerService      # noqa: E402
from services.predictions.prediction_service import PredictionService  # noqa: E402
from services.predictions.slip_ledger import SlipLedger            # noqa: E402


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def slug(league: str) -> str:
    return league.lower().replace(" ", "-")


# ---------------------------------------------------------------------------
# the sandbox
# ---------------------------------------------------------------------------
class Sandbox:
    """A temp directory that IS the working directory for one case.

    Holds copies of the four ledgers and the current-season fixture and
    Understat caches, plus the directories the gate looks for. Module
    constants anchored to the repo root are re-pointed here and restored on
    exit, so a case can call the production code unmodified."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="selfcheck-"))
        self._cwd = os.getcwd()
        self._patches: List[tuple] = []

    # -- paths inside the sandbox
    @property
    def data(self) -> Path:
        return self.root / "data"

    def fixtures_path(self, league: str) -> Path:
        return self.data / "fixtures" / league / f"{SEASON}.json"

    def __enter__(self) -> "Sandbox":
        for src in REAL_LEDGERS:
            dst = self.root / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copyfile(src, dst)
        for lg in LEAGUES:
            for layer in ("fixtures", "understat"):
                src = ROOT / "data" / layer / lg / f"{SEASON}.json"
                if src.exists():
                    dst = self.root / src.relative_to(ROOT)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
            (self.data / "web" / "team" / slug(lg)).mkdir(parents=True, exist_ok=True)
        (self.data / "reports").mkdir(parents=True, exist_ok=True)
        os.chdir(self.root)
        # run_daily: the gate reads ROOT/data/..., the runner writes STEP_LOG
        self.patch(run_daily, "ROOT", self.root)
        self.patch(run_daily, "STEP_LOG", self.data / "reports" / "daily_steps.json")
        self.patch(run_daily, "DAILY_STAMP", self.data / "reports" / "last_daily_run.txt")
        self.patch(run_daily, "LOG", self.data / "reports" / "daily.log")
        self.patch(run_daily, "_done_today", {})
        self.patch(run_daily, "_ignore_step_log", False)
        run_daily.done.clear()
        # publish: the payload gate reads PUB and asks data_ready for leagues
        self.patch(publish, "PUB", self.root / "pub")
        self.patch(publish, "ROOT", self.root)
        self.patch(publish, "ready_leagues", lambda: list(LEAGUES))
        return self

    def __exit__(self, *exc) -> None:
        os.chdir(self._cwd)
        for mod, name, old in reversed(self._patches):
            setattr(mod, name, old)
        run_daily.done.clear()
        shutil.rmtree(self.root, ignore_errors=True)

    def patch(self, mod, name: str, value) -> None:
        self._patches.append((mod, name, getattr(mod, name)))
        setattr(mod, name, value)

    # -- writers
    def write_jsonl(self, rel: str, rows: List[Dict]) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
        return p

    def read_jsonl(self, rel: str) -> List[Dict]:
        p = self.root / rel
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def write_fixtures(self, league: str, matches: List[Dict]) -> None:
        p = self.fixtures_path(league)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "league": league, "season": SEASON, "match_count": len(matches),
            "played_count": sum(1 for m in matches if m["played"]),
            "matches": matches}, ensure_ascii=False), encoding="utf-8")

    def write_understat(self, league: str, matches: List[Dict]) -> None:
        p = self.data / "understat" / league / f"{SEASON}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"league": league, "season": SEASON,
                                 "match_count": len(matches), "matches": matches}),
                     encoding="utf-8")

    def write_events_parquet(self, league: str, game_ids: List[str]) -> None:
        """What league_state counts as `events`: distinct game_id in the raw
        WhoScored parquet."""
        import pandas as pd
        p = self.data / "whoscored" / league / f"{SEASON}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"game_id": game_ids, "x": range(len(game_ids))}).to_parquet(p)

    def empty_ledgers(self) -> None:
        for rel in LEDGER_FILES.values():
            self.write_jsonl(rel, [])


LEDGER_FILES = {
    "picks": "data/ledger/picks.jsonl",
    "slips": "data/slips/slips.jsonl",
    "gold": "data/slips/gold.jsonl",
    "history": "data/history/predictions.jsonl",
}


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------
def fixture(day: str, week: int, home: str, away: str,
            score: Optional[tuple] = None) -> Dict[str, Any]:
    hg, ag = score if score else (None, None)
    return {"date": day, "time": "20:00", "week": week, "home_team": home,
            "away_team": away, "home_goals": hg, "away_goals": ag,
            "played": score is not None, "venue": None, "referee": None,
            "game_id": f"{day} {home}-{away}"}


def pick_row(window: str, pick_type: str, rank: int, league: str, home: str,
             away: str, kickoff: str, status: str = "pending",
             committed_days_ago: int = 1, week: int = 2) -> Dict[str, Any]:
    probs = {"home": 0.4, "draw": 0.3, "away": 0.3}
    r = {"committed_at": ago(committed_days_ago), "season": SEASON, "window": window,
         "week": week, "pick_type": pick_type, "rank": rank, "league": league,
         "home": home, "away": away, "kickoff": kickoff, "pick_prob": probs[pick_type],
         "probabilities": probs, "xg": {home: 1.2, away: 1.0}, "status": status}
    if status == "graded":
        r.update(graded_at=ago(committed_days_ago - 1), score="1-1", outcome="draw",
                 hit=pick_type == "draw")
    return r


def slip_leg(league: str, home: str, away: str, kickoff: str, prob: float = 0.32,
             role: str = "draw", team: Optional[str] = None) -> Dict[str, Any]:
    leg = {"role": role, "mark": "X" if role == "draw" else "1",
           "fixture": f"{home} v {away}", "home": home, "away": away,
           "league_full": league, "league": league.split("-")[1], "kickoff": kickoff,
           "prob": prob, "breakeven": round(1 / prob, 2)}
    if team:
        leg["team"] = team
    return leg


def slip_row(window: str, legs: List[Dict], k, status: str = "pending",
             committed_days_ago: int = 1) -> Dict[str, Any]:
    sizes = [k] if isinstance(k, int) else list(k)
    lines = sum(len(list(combinations(range(len(legs)), j))) for j in sizes)
    r = {"committed_at": ago(committed_days_ago), "season": SEASON, "window": window,
         "title_he": "שיטה", "title_en": f"system {k}", "k": k, "lines": lines,
         "unit": 10.0, "stake": round(lines * 10.0, 2), "p_profit": 0.3,
         "legs": legs, "mandate": "draws", "status": status}
    if status == "graded":
        r.update(graded_at=ago(committed_days_ago - 1), hits=0, lines_won=0,
                 gross_return=0.0, net=-r["stake"])
    return r


def gold_bet(league: str, home: str, away: str, team: str, kickoff: str,
             prob: float = 0.6) -> Dict[str, Any]:
    return {"league_full": league, "league": league.split("-")[1], "home": home,
            "away": away, "fixture": f"{home} v {away}", "team": team,
            "side": "home" if team == home else "away", "prob": prob,
            "breakeven": round(1 / prob, 3), "kickoff": kickoff}


def gold_row(window: str, bets: List[Dict], status: str = "pending",
             committed_days_ago: int = 1) -> Dict[str, Any]:
    r = {"committed_at": ago(committed_days_ago), "season": SEASON, "window": window,
         "unit": 10.0, "stake": round(len(bets) * 10.0, 2), "bets": bets, "status": status}
    if status == "graded":
        r.update(graded_at=ago(committed_days_ago - 1), hits=0, gross_return=0.0,
                 net=-r["stake"])
    return r


def history_row(league: str, home: str, away: str, kickoff: str,
                pred: str = "home", score: str = "1-0") -> Dict[str, Any]:
    return {"recorded_at": ago(3), "retro": False, "season": SEASON, "league": league,
            "week": 1, "kickoff": kickoff, "home": home, "away": away,
            "probabilities": {"home": 0.45, "draw": 0.28, "away": 0.27},
            "pred_xg": [1.4, 1.0], "pred_outcome": pred, "pred_score": score,
            "confidence": "normal", "status": "pending"}


# ---------------------------------------------------------------------------
# a synthetic season for the window and guard cases
# ---------------------------------------------------------------------------
def teams(league: str) -> List[str]:
    code = league.split("-")[0]
    return [f"{code} Team {i}" for i in range(1, 7)]


# one round = three fixtures; the pairings rotate so no team repeats a round
ROUND_PAIRS = {1: [(0, 1), (2, 3), (4, 5)],
               2: [(1, 2), (3, 4), (5, 0)],
               3: [(0, 3), (1, 4), (2, 5)]}
# played rounds carry these scores: fixture 0 a home win, 1 and 2 draws
ROUND_SCORES = [(2, 0), (1, 1), (0, 0)]

W2_FUTURE = (1, 1, 2)      # week-2 kickoffs, days from today, per fixture
W2_PLAYED = (-3, -3, -2)
W2_HALF = (-1, 1, 1)
W3_DAYS = (8, 8, 9)


def synthetic_season(sb: Sandbox, week2=W2_FUTURE) -> Dict[str, Any]:
    """Five leagues, three rounds, written to the sandbox fixture cache.
    Week 1 is history, week 2 is the round under test, week 3 the one after.
    Returns the week-2 window key and the span of each round."""
    for lg in LEAGUES:
        t = teams(lg)
        ms = []
        for i, (h, a) in enumerate(ROUND_PAIRS[1]):
            ms.append(fixture(d(-7), 1, t[h], t[a], ROUND_SCORES[i]))
        for i, (h, a) in enumerate(ROUND_PAIRS[2]):
            day = week2[i]
            ms.append(fixture(d(day), 2, t[h], t[a],
                              ROUND_SCORES[i] if day < 0 else None))
        for i, (h, a) in enumerate(ROUND_PAIRS[3]):
            ms.append(fixture(d(W3_DAYS[i]), 3, t[h], t[a]))
        sb.write_fixtures(lg, ms)
    return {"w2": d(min(week2)), "w2_end": d(max(week2)),
            "w3": d(min(W3_DAYS)), "w1": d(-7)}


def week1_ledgers(sb: Sandbox) -> None:
    """Graded week-1 bets, committed long enough ago that the round guards
    (MIN_ROUND_GAP_DAYS) do not interfere with a fresh commit."""
    picks, legs, bets = [], [], []
    for lg in LEAGUES:
        t = teams(lg)
        picks.append(pick_row(d(-7), "draw", len(picks) + 1, lg, t[2], t[3], d(-7),
                              status="graded", committed_days_ago=9, week=1))
        legs.append(slip_leg(lg, t[4], t[5], d(-7)))
        bets.append(gold_bet(lg, t[0], t[1], t[0], d(-7)))
    sb.write_jsonl(LEDGER_FILES["picks"], picks)
    sb.write_jsonl(LEDGER_FILES["slips"], [slip_row(d(-7), legs[:4], [2], "graded", 9)])
    sb.write_jsonl(LEDGER_FILES["gold"], [gold_row(d(-7), bets, "graded", 9)])
    sb.write_jsonl(LEDGER_FILES["history"], [])


class FakePricer(PredictionService):
    """PredictionService with the model cut out. Every method that chooses,
    books and serves a window is inherited unchanged; only predict_fixtures
    is replaced by a deterministic pricer, so a window case needs no fitted
    model, no event store and no network. `salt` reorders the draw ranking
    between calls, which is how a case proves a booked round is SERVED from
    the ledger rather than quietly re-ranked."""

    def __init__(self) -> None:          # the real one loads params + the draw model
        self.salt = 0

    # fixtures 0 and 1 of a round are GOLD favourites (>= 0.55), fixture 2
    # is the draw candidate; a half-played round plays fixture 0 first
    HOME = [0.60, 0.56, 0.36]
    DRAW = [0.20, 0.30, 0.33]

    def predict_fixtures(self, league: str, fixtures: List[Dict]) -> List[Dict[str, Any]]:
        j = LEAGUES.index(league)
        out = []
        t = teams(league)
        for m in fixtures:
            pairs = ROUND_PAIRS.get(m["week"], ROUND_PAIRS[1])
            i = next((k for k, (h, _) in enumerate(pairs) if t[h] == m["home_team"]), 0)
            draw_i = (2 - i) if self.salt else i   # salt swaps the draw order
            home = round(self.HOME[i] + 0.01 * j, 4)
            draw = round(self.DRAW[draw_i] - 0.004 * j, 4)
            probs = {"home": home, "draw": draw, "away": round(1 - home - draw, 4)}
            call = "draw" if draw >= 0.31 else max(probs, key=probs.get)
            out.append({
                "tier": "gold" if home >= 0.55 else "silver", "league": league,
                "season": SEASON, "week": m["week"], "kickoff": m["date"],
                "home": m["home_team"], "away": m["away_team"],
                "xg": {m["home_team"]: 1.4, m["away_team"]: 1.0},
                "probabilities": probs, "probabilities_ship": probs,
                "probabilities_elo": None, "call": call, "probabilities_poisson": probs,
                "p_draw_classifier": draw, "draw_drivers": None,
                "top_scorelines": [("1-0", 0.12), ("1-1", 0.11), ("2-1", 0.09)],
                "modal_scores": {"home": ("1-0", 0.12), "draw": ("1-1", 0.11),
                                 "away": ("0-1", 0.08)},
                "confidence": "normal", "why": None,
            })
        return out


def identity(p: Dict) -> tuple:
    """The part of a pick the user's betting form depends on."""
    return (p["home"], p["away"], p["league"], p["kickoff"], p.get("rank"),
            p.get("pick_type"), p.get("pick_prob"), json.dumps(p["probabilities"], sort_keys=True))


def slip_identity(strategy: Optional[Dict]) -> Any:
    s = (strategy or {}).get("slip")
    if not s:
        return None
    return (s["title_he"], s["k"], s["lines"],
            tuple((l["home"], l["away"], l["mark"], l["prob"], l["breakeven"]) for l in s["legs"]))


# ---------------------------------------------------------------------------
# the case registry
# ---------------------------------------------------------------------------
@dataclass
class Case:
    group: str
    name: str
    fn: Callable[[Sandbox], Optional[str]]
    known_bug: Optional[str] = None      # set when the case documents a live pipeline bug

    @property
    def id(self) -> str:
        return f"{self.group}: {self.name}"


CASES: List[Case] = []


def case(group: str, name: str, known_bug: Optional[str] = None):
    def deco(fn):
        CASES.append(Case(group, name, fn, known_bug))
        return fn
    return deco


def check(cond: bool, why: str) -> None:
    if not cond:
        raise AssertionError(why)


# ===========================================================================
# 1. THE GATE  (run_daily.league_state / stale_leagues)
# ===========================================================================
GATE_LG = "ENG-Premier League"


def gate_fixtures(sb: Sandbox, played: int, overdue: int = 0, future: int = 3) -> None:
    t = teams(GATE_LG) + [f"ENG Team {i}" for i in range(7, 20)]
    ms, n = [], 0
    for _ in range(played):
        ms.append(fixture(d(-10), 1, t[n], t[n + 1], (1, 0))); n += 2
    for _ in range(overdue):
        ms.append(fixture(d(-1), 2, t[n], t[n + 1])); n += 2
    for _ in range(future):
        ms.append(fixture(d(3), 3, t[n], t[n + 1])); n += 2
    sb.write_fixtures(GATE_LG, ms)


def marker(**state) -> Dict:
    return {"at": ago(1), "leagues": [GATE_LG], "state": {GATE_LG: state}}


@case("gate", "fresh cache, nothing played -> 0 stale")
def gate_fresh(sb):
    gate_fixtures(sb, played=3)
    sb.write_events_parquet(GATE_LG, ["g1", "g2", "g3"])
    now = run_daily.league_state(GATE_LG)
    check(now == {"played": 3, "events": 3, "overdue": 0}, f"league_state read {now}")
    stale = run_daily.stale_leagues([GATE_LG], marker(**now))
    check(stale == {}, f"a league with nothing new was marked stale: {stale}")
    return "0 stale"


@case("gate", "stale cache with overdue fixtures -> stale")
def gate_overdue(sb):
    # 2026-10-23: played and events both come from OUR disk, so a fixture
    # cache nobody had refreshed agreed with the marker and all five leagues
    # were skipped after a week of football. `overdue` is the only count that
    # looks at the outside world (a kickoff date that has passed).
    gate_fixtures(sb, played=3, overdue=2)
    sb.write_events_parquet(GATE_LG, ["g1", "g2", "g3"])
    stale = run_daily.stale_leagues([GATE_LG], marker(played=3, events=3, overdue=0))
    check(GATE_LG in stale, "two fixtures are past their date and still unplayed, gate said idle")
    check("overdue" in stale[GATE_LG], f"reason should name overdue: {stale[GATE_LG]!r}")
    return stale[GATE_LG]


@case("gate", "event gap -> stale")
def gate_event_gap(sb):
    gate_fixtures(sb, played=5)
    sb.write_events_parquet(GATE_LG, ["g1", "g2", "g3"])
    stale = run_daily.stale_leagues([GATE_LG], marker(played=3, events=3, overdue=0))
    check(GATE_LG in stale, "played moved 3->5 with events at 3, gate said idle")
    check("played" in stale[GATE_LG], f"reason should name played: {stale[GATE_LG]!r}")
    return stale[GATE_LG]


@case("gate", "gap already attempted -> NOT stale (no thrash)")
def gate_no_thrash(sb):
    # A match WhoScored never publishes leaves played > events forever. The
    # marker stores the counts AFTER the work, so an unchanged pair means
    # "already tried", not "there is a gap".
    gate_fixtures(sb, played=5)
    sb.write_events_parquet(GATE_LG, ["g1", "g2", "g3"])
    stale = run_daily.stale_leagues([GATE_LG], marker(played=5, events=3, overdue=0))
    check(stale == {}, f"an unchanged gap re-marked the league stale: {stale}")
    return "played 5, events 3, unchanged -> idle"


@case("gate", "newly ready league -> stale")
def gate_newly_ready(sb):
    gate_fixtures(sb, played=3)
    stale = run_daily.stale_leagues([GATE_LG], {"at": ago(1), "leagues": [], "state": {}})
    check(GATE_LG in stale, "a league with no record from a previous run was skipped")
    stale_none = run_daily.stale_leagues([GATE_LG], None)
    check(GATE_LG in stale_none, "with no marker at all the league was skipped")
    return stale[GATE_LG]


# ===========================================================================
# 2. GRADING  (picks, slips, gold, history)
# ===========================================================================
GR_LG = "ITA-Serie A"


def graded_round(sb: Sandbox) -> List[str]:
    """Four played fixtures: three draws and one home win, kicked off yesterday."""
    t = teams(GR_LG) + ["ITA Team 7", "ITA Team 8"]
    ms = [fixture(d(-1), 5, t[0], t[1], (1, 1)), fixture(d(-1), 5, t[2], t[3], (0, 0)),
          fixture(d(-1), 5, t[4], t[5], (2, 2)), fixture(d(-1), 5, t[6], t[7], (3, 1))]
    sb.write_fixtures(GR_LG, ms)
    return t


def four_legs(t: List[str]) -> List[Dict]:
    return [slip_leg(GR_LG, t[0], t[1], d(-1), 0.32), slip_leg(GR_LG, t[2], t[3], d(-1), 0.31),
            slip_leg(GR_LG, t[4], t[5], d(-1), 0.30), slip_leg(GR_LG, t[6], t[7], d(-1), 0.29)]


@case("grading", "a slip whose k is a LIST grades")
def grade_slip_list_k(sb):
    # 2026-10-23: `k` became [2,3,4] for a Yankee, combinations() wanted an
    # int, the TypeError was caught as "WARN grade slips" and every slip
    # stayed pending for a fortnight (see slip_ledger.grade).
    t = graded_round(sb)
    sb.write_jsonl(LEDGER_FILES["slips"], [slip_row(d(-1), four_legs(t), [2, 3, 4])])
    res = SlipLedger.grade()
    row = sb.read_jsonl(LEDGER_FILES["slips"])[0]
    check(res.get("graded") == 1 and row["status"] == "graded", f"slip not graded: {res}")
    check(row["hits"] == 3, f"3 of 4 legs drew, hits={row['hits']}")
    # 3 hits on a Yankee: C(3,2)+C(3,3) = 4 lines of 11
    check(row["lines_won"] == 4, f"Yankee with 3 hits pays 4 lines, got {row['lines_won']}")
    return f"k=[2,3,4]: hits 3, lines_won 4, net {row['net']}"


@case("grading", "a slip whose k is an int still grades")
def grade_slip_int_k(sb):
    t = graded_round(sb)
    sb.write_jsonl(LEDGER_FILES["slips"], [slip_row(d(-1), four_legs(t), 2)])
    res = SlipLedger.grade()
    row = sb.read_jsonl(LEDGER_FILES["slips"])[0]
    check(res.get("graded") == 1 and row["status"] == "graded", f"slip not graded: {res}")
    check(row["lines_won"] == 3, f"system 2/4 with 3 hits pays C(3,2)=3 lines, got {row['lines_won']}")
    return f"k=2: hits {row['hits']}, lines_won 3"


@case("grading", "picks grade, hit judged from our pick's side")
def grade_picks(sb):
    t = graded_round(sb)
    rows = [pick_row(d(-1), "draw", 1, GR_LG, t[0], t[1], d(-1)),       # 1-1 -> hit
            pick_row(d(-1), "home", 1, GR_LG, t[6], t[7], d(-1)),       # 3-1 -> hit
            pick_row(d(-1), "away", 1, GR_LG, t[6], t[7], d(-1)),       # 3-1 -> miss
            # venue flipped after commit: fbref lists t[3] at home. Our pick
            # says "t[2] wins at home"; the fixture is 0-0, so it is a miss
            # and must still GRADE rather than hang.
            pick_row(d(-1), "home", 2, GR_LG, t[3], t[2], d(-1))]
    sb.write_jsonl(LEDGER_FILES["picks"], rows)
    res = LedgerService.grade()
    got = sb.read_jsonl(LEDGER_FILES["picks"])
    check(res.get("graded") == 4, f"4 picks on played fixtures, graded {res}")
    hits = [r["hit"] for r in got]
    check(hits == [True, True, False, False], f"hits {hits}")
    check("fallback" in got[3].get("note", ""), "flipped venue should be noted on the row")
    return "4 graded, hits [T,T,F,F], flipped venue noted"


@case("grading", "gold rows grade; settled legs persist before the window closes")
def grade_gold(sb):
    t = graded_round(sb)
    done = gold_row(d(-1), [gold_bet(GR_LG, t[6], t[7], t[6], d(-1)),     # 3-1 -> hit
                            gold_bet(GR_LG, t[0], t[1], t[0], d(-1))])    # 1-1 -> miss
    open_ = gold_row(d(-1), [gold_bet(GR_LG, t[6], t[7], t[7], d(-1)),    # settled, miss
                             gold_bet(GR_LG, "ITA Team 9", "ITA Team 10", "ITA Team 9", d(2))])
    sb.write_jsonl(LEDGER_FILES["gold"], [done, open_])
    res = GoldLedger.grade()
    a, b = sb.read_jsonl(LEDGER_FILES["gold"])
    check(a["status"] == "graded" and a["hits"] == 1, f"finished window not graded: {a.get('status')} {res}")
    check(b["status"] == "pending", "a window with an unplayed leg must stay pending")
    check(b["bets"][0].get("hit") is False, "the settled leg of a pending window was not persisted")
    return f"graded {res['graded']}, legs_resolved {res['legs_resolved']}"


@case("grading", "history rows grade against score and xG")
def grade_history(sb):
    t = graded_round(sb)
    sb.write_understat(GR_LG, [{"date": d(-1), "home_team": t[6], "away_team": t[7],
                                "home_xg": 1.5, "away_xg": 1.1}])
    sb.write_jsonl(LEDGER_FILES["history"], [
        history_row(GR_LG, t[6], t[7], d(-1), "home", "3-1"),   # perfect call and score
        history_row(GR_LG, t[0], t[1], d(-1), "home", "1-0"),   # 1-1: miss, no xG yet
        history_row(GR_LG, "ITA Team 9", "ITA Team 10", d(2)),  # not played: pending
    ])
    res = HistoryService.grade()
    a, b, c = sb.read_jsonl(LEDGER_FILES["history"])
    check(res.get("graded") == 2, f"two rows had results, graded {res}")
    check(a["outcome_hit"] and a["score_hit"] and a["xg_hit"] and a["perfect"],
          f"row with the right call, score and xG not marked perfect: {a}")
    check(b["status"] == "graded" and not b["outcome_hit"] and b["real_xg"] is None,
          f"miss without xG mis-graded: {b}")
    check(c["status"] == "pending", "an unplayed fixture was graded")
    return "2 graded (1 perfect), 1 pending"


@case("grading", "real ledgers (copies): every pending row with results reaches graded")
def grade_real_copies(sb):
    """The regression the 10-23 freeze would have tripped: run all four
    graders on today's ledgers and look for a pending row whose fixture
    fbref says was played."""
    def played_book(league):
        p = sb.fixtures_path(league)
        if not p.exists():
            return {}
        return {(m["home_team"], m["away_team"]): m
                for m in json.loads(p.read_text(encoding="utf-8"))["matches"] if m["played"]}

    books: Dict[str, Dict] = {}

    def resolved(league, home, away):
        b = books.setdefault(league, played_book(league))
        return (home, away) in b or (away, home) in b

    for grader in (LedgerService.grade, SlipLedger.grade, GoldLedger.grade, HistoryService.grade):
        grader()                                     # must not raise — the 10-23 TypeError
    stuck = []
    for r in sb.read_jsonl(LEDGER_FILES["picks"]):
        if r["status"] == "pending" and resolved(r["league"], r["home"], r["away"]):
            stuck.append(f"pick {r['home']} v {r['away']}")
    for r in sb.read_jsonl(LEDGER_FILES["history"]):
        if r["status"] == "pending" and resolved(r["league"], r["home"], r["away"]):
            stuck.append(f"history {r['home']} v {r['away']}")
    for r in sb.read_jsonl(LEDGER_FILES["slips"]):
        if r["status"] == "pending" and all(resolved(l["league_full"], l["home"], l["away"])
                                            for l in r["legs"]):
            stuck.append(f"slip {r['window']}")
    for r in sb.read_jsonl(LEDGER_FILES["gold"]):
        if r["status"] == "pending" and all(resolved(b["league_full"], b["home"], b["away"])
                                            for b in r["bets"]):
            stuck.append(f"gold {r['window']}")
    check(not stuck, f"{len(stuck)} resolved row(s) still pending: {stuck[:4]}")
    n = {k: len(sb.read_jsonl(v)) for k, v in LEDGER_FILES.items()}
    pend = {k: sum(1 for r in sb.read_jsonl(v) if r["status"] == "pending")
            for k, v in LEDGER_FILES.items()}
    return f"rows {n}, pending (unplayed) {pend}"


# ===========================================================================
# 3. THE WINDOW CONTRACT  (_pending_window / weekly_picks)
# ===========================================================================
@case("window", "booked window -> two consecutive calls return IDENTICAL picks and slip")
def window_booked_identical(sb):
    # 2026-10-11: mid-gameweek the dashboard re-ranked the four games left
    # and showed a different slip than the Winner form the user was holding.
    # The ledger rows ARE the round while any bet under it is pending.
    synthetic_season(sb)
    week1_ledgers(sb)
    ps = FakePricer()
    fresh = ps.weekly_picks()
    check(fresh["booked"] is None, f"nothing is booked yet, got booked={fresh['booked']}")
    for ledger in (LedgerService, SlipLedger, GoldLedger):
        res = ledger.commit(fresh)
        check(res.get("added", res.get("committed")), f"{ledger.__name__}.commit refused: {res}")
    first = ps.weekly_picks()
    ps.salt = 1                        # the model now ranks the draws differently...
    second = ps.weekly_picks()
    check(first["booked"] == second["booked"] == fresh["window"]["start"],
          f"booked should be {fresh['window']['start']}, got {first['booked']} / {second['booked']}")
    for key in ("draw_picks", "home_win_picks", "away_win_picks"):
        a, b = [identity(p) for p in first[key]], [identity(p) for p in second[key]]
        check(a == b and a, f"{key} changed between two calls on a booked round")
        committed = [identity(p) for p in fresh[key]]
        check([x[:4] for x in a] == [x[:4] for x in committed], f"{key} differ from what was committed")
    check(slip_identity(first["strategy"]) == slip_identity(second["strategy"]) is not None,
          "the slip changed between two calls on a booked round")
    # ...and the salt really would have changed a fresh ranking: the test can fail
    ps2 = FakePricer(); ps2.salt = 1
    sb.empty_ledgers()
    check([identity(p)[:2] for p in ps2.weekly_picks()["draw_picks"]]
          != [identity(p)[:2] for p in fresh["draw_picks"]], "salt did not change the fresh ranking")
    return f"booked {first['booked']}, {len(first['draw_picks'])} draws served twice"


@case("window", "fully graded -> window advances to the next round")
def window_advances(sb):
    s = synthetic_season(sb, W2_PLAYED)
    week1_ledgers(sb)
    t = {lg: teams(lg) for lg in LEAGUES}
    picks = sb.read_jsonl(LEDGER_FILES["picks"])
    picks += [pick_row(s["w2"], "draw", i + 1, lg, t[lg][3], t[lg][4], s["w2_end"], "graded", 4)
              for i, lg in enumerate(LEAGUES[:4])]
    sb.write_jsonl(LEDGER_FILES["picks"], picks)
    slips = sb.read_jsonl(LEDGER_FILES["slips"])
    slips.append(slip_row(s["w2"], [slip_leg(lg, t[lg][3], t[lg][4], s["w2_end"]) for lg in LEAGUES[:4]],
                          [2], "graded", 4))
    sb.write_jsonl(LEDGER_FILES["slips"], slips)
    gold = sb.read_jsonl(LEDGER_FILES["gold"])
    gold.append(gold_row(s["w2"], [gold_bet(lg, t[lg][1], t[lg][2], t[lg][1], s["w2"]) for lg in LEAGUES],
                         "graded", 4))
    sb.write_jsonl(LEDGER_FILES["gold"], gold)

    check(PredictionService._pending_window() is None, "every row is graded yet a window is live")
    w = FakePricer().weekly_picks()
    check(w["booked"] is None, f"graded round still served as booked {w['booked']}")
    check(w["window"]["start"] == s["w3"], f"window should open at {s['w3']}, got {w['window']}")
    early = [p for ps in w["all_predictions"].values() for p in ps if p["kickoff"] <= s["w2_end"]]
    check(not early, f"{len(early)} fixture(s) from the graded round still on the board")
    check(w["draw_picks"] and w["strategy"], "the next round produced no picks or slip")
    return f"advanced to {w['window']['start']}..{w['window']['end']}"


@case("window", "no pick, banker or gold bet on a fixture carrying a score")
def window_no_scored_bets(sb):
    # A live round keeps its played fixtures on the board so it stays whole,
    # which means every ranking downstream can now be handed a known result.
    s = synthetic_season(sb, W2_HALF)
    week1_ledgers(sb)
    t = {lg: teams(lg) for lg in LEAGUES}
    # only a GOLD row is pending under the round, so weekly_picks takes the
    # booked path with no committed picks to serve and re-ranks the slate;
    # its bets span the Friday game (played) and the Sunday ones (not yet)
    gold = sb.read_jsonl(LEDGER_FILES["gold"])
    gold.append(gold_row(s["w2"], [b for lg in LEAGUES for b in (
        gold_bet(lg, t[lg][1], t[lg][2], t[lg][1], s["w2"]),
        gold_bet(lg, t[lg][5], t[lg][0], t[lg][5], s["w2_end"]))]))
    sb.write_jsonl(LEDGER_FILES["gold"], gold)
    w = FakePricer().weekly_picks()
    check(w["booked"] == s["w2"], f"expected the half-played round to be live, got {w['booked']}")
    scored = [p for ps in w["all_predictions"].values() for p in ps if p.get("score")]
    check(len(scored) == len(LEAGUES), f"the slate should carry {len(LEAGUES)} results, has {len(scored)}")
    for key in ("draw_picks", "home_win_picks", "away_win_picks", "draw_watchlist"):
        bad = [f"{p['home']} v {p['away']}" for p in w[key] if p.get("score")]
        check(not bad, f"{key} contains a played fixture: {bad}")
    st = w["strategy"] or {}
    results = {(p["home"], p["away"]) for p in scored}
    if st.get("banker"):
        check((st["banker"]["home"], st["banker"]["away"]) not in results, "banker is a played fixture")
    for l in (st.get("slip") or {}).get("legs", []):
        check((l["home"], l["away"]) not in results, f"slip leg {l['fixture']} already has a score")
    # the gold guard itself (gold_ledger.commit skips p["score"]): hand it a
    # weekly whose slate carries results and a window nothing is booked under
    sb.write_jsonl(LEDGER_FILES["gold"], [])
    fake = {**w, "booked": None, "window": {"start": d(1), "end": d(1)}}
    res = GoldLedger.commit(fake)
    check(res.get("committed") == 1, f"gold commit on a half-played slate refused: {res}")
    bets = sb.read_jsonl(LEDGER_FILES["gold"])[0]["bets"]
    check(len(bets) == len(LEAGUES), f"expected one unplayed GOLD favourite per league, got {len(bets)}")
    check(all((b["home"], b["away"]) not in results for b in bets),
          "gold booked a fixture whose result it already knew")
    return f"{len(scored)} results on the board, none bet; gold took the {len(bets)} unplayed favourites"


@case("window", "a pending row that can never resolve does not freeze the window forever")
def window_never_freezes(sb):
    # Fixed 2026-11-09: `_pending_window` ignores a round whose last kickoff
    # is more than WINDOW_GRACE_DAYS old, and the graders void the row with
    # a note (services/predictions/windows.py). This case found the bug.
    # 10-07 to 10-23: one slip that could not grade kept its window "live",
    # weekly_picks served that round for a fortnight and every commit was
    # refused. A row whose fixture no longer exists (abandoned, renamed) is
    # the same trap without the TypeError.
    s = synthetic_season(sb, W2_PLAYED)
    week1_ledgers(sb)
    picks = sb.read_jsonl(LEDGER_FILES["picks"])
    picks.append(pick_row(d(-30), "draw", 1, "ESP-La Liga", "Ghost FC", "Phantom United",
                          d(-30), committed_days_ago=31))
    sb.write_jsonl(LEDGER_FILES["picks"], picks)
    LedgerService.grade()                                  # the daily grades first
    row = sb.read_jsonl(LEDGER_FILES["picks"])[-1]
    w = FakePricer().weekly_picks()
    check(w["booked"] != d(-30),
          f"a pick from {d(-30)} on a fixture that does not exist (still {row['status']}) "
          f"holds the window: booked={w['booked']}, window={w['window']}")
    check(w["window"]["start"] >= TODAY.isoformat(),
          f"window opened in the past: {w['window']}")
    return f"stale row released, window {w['window']['start']}"


# ===========================================================================
# 4. COMMIT GUARDS
# ===========================================================================
def fake_weekly(window_start: str, booked: Optional[str] = None) -> Dict[str, Any]:
    """A weekly dict with everything the three commits read, no model."""
    t = {lg: teams(lg) for lg in LEAGUES}
    draws = [{**pick_row(window_start, "draw", i + 1, lg, t[lg][1], t[lg][2], window_start), "week": 2}
             for i, lg in enumerate(LEAGUES[:4])]
    homes = [{**pick_row(window_start, "home", i + 1, lg, t[lg][3], t[lg][4], window_start), "week": 2}
             for i, lg in enumerate(["ENG-Premier League", "FRA-Ligue 1"])]
    for p in draws + homes:
        p.pop("committed_at"); p.pop("status"); p.pop("window")
    legs = [slip_leg(p["league"], p["home"], p["away"], window_start) for p in draws]
    preds = {lg: [{"home": t[lg][5], "away": t[lg][0], "kickoff": window_start, "in_window": True,
                   "confidence": "normal", "probabilities": {"home": 0.62, "draw": 0.2, "away": 0.18},
                   "season": SEASON, "week": 2, "league": lg, "xg": {}, "tier": "gold",
                   "modal_scores": {"home": ("2-0", 0.1), "draw": ("1-1", 0.1), "away": ("0-1", 0.05)},
                   "call": "home"}] for lg in LEAGUES}
    return {"season": SEASON, "window": {"start": window_start, "end": window_start},
            "booked": booked, "draw_picks": draws, "home_win_picks": homes, "away_win_picks": [],
            "all_predictions": preds,
            "strategy": {"slip": {"title_he": "שיטה 2/4", "title_en": "system 2/4", "k": [2],
                                  "lines": 6, "legs": legs, "p_profit": 0.35, "mandate": None}}}


def counts(sb: Sandbox) -> Dict[str, int]:
    return {k: len(sb.read_jsonl(v)) for k, v in LEDGER_FILES.items() if k != "history"}


def seeded_ledgers(sb: Sandbox, window: str, status: str = "graded") -> None:
    t = teams("GER-Bundesliga")
    sb.write_jsonl(LEDGER_FILES["picks"], [pick_row(window, "draw", 1, "GER-Bundesliga", t[0], t[1],
                                                    window, status, committed_days_ago=10)])
    sb.write_jsonl(LEDGER_FILES["slips"], [slip_row(window, [slip_leg("GER-Bundesliga", t[0], t[1], window)],
                                                    [1], status, committed_days_ago=10)])
    sb.write_jsonl(LEDGER_FILES["gold"], [gold_row(window, [gold_bet("GER-Bundesliga", t[2], t[3], t[2], window)],
                                                   status, committed_days_ago=10)])


@case("guards", "a window already in the ledger is refused on all three")
def guards_refuse_existing(sb):
    # The old per-type check only saw PENDING rows, so a window whose rows had
    # graded could be booked again — with the live round serving its committed
    # rows back, the second booking would have been a copy with results in it.
    # Seeded rows are GRADED on purpose.
    win = d(1)
    seeded_ledgers(sb, win, "graded")
    before = counts(sb)
    out = {}
    for name, ledger in (("picks", LedgerService), ("slips", SlipLedger), ("gold", GoldLedger)):
        res = ledger.commit(fake_weekly(win))
        out[name] = res.get("reason", "")
        check(not res.get("added") and not res.get("committed"), f"{name} accepted a booked window: {res}")
        check("already" in out[name], f"{name} refused for the wrong reason: {res}")
    check(counts(sb) == before, f"rows grew on refusal: {before} -> {counts(sb)}")
    return "; ".join(f"{k}: {v}" for k, v in out.items())


@case("guards", "a genuinely new window is accepted")
def guards_accept_new(sb):
    seeded_ledgers(sb, d(-10), "graded")
    before = counts(sb)
    res_p = LedgerService.commit(fake_weekly(d(1)))
    res_s = SlipLedger.commit(fake_weekly(d(1)))
    res_g = GoldLedger.commit(fake_weekly(d(1)))
    check(res_p.get("added") == 6, f"picks: expected 6 added, got {res_p}")
    check(res_s.get("committed") == 1, f"slip refused: {res_s}")
    check(res_g.get("committed") == 1 and res_g.get("bets") == 5, f"gold refused or short: {res_g}")
    after = counts(sb)
    check(after == {"picks": before["picks"] + 6, "slips": before["slips"] + 1,
                    "gold": before["gold"] + 1}, f"row counts {before} -> {after}")
    check(all(r.get("window") == d(1) for r in sb.read_jsonl(LEDGER_FILES["picks"])[1:]),
          "committed picks do not carry the window key")
    return f"picks +6, slip +1, gold +1 (5 bets) under {d(1)}"


@case("guards", "row counts do not grow on a refused commit (live booked round)")
def guards_booked_counts(sb):
    # 2026-10-29: window.start (earliest kickoff, 10-30) was compared against
    # the round key (10-29) and the gold ledger booked the same round twice.
    # The `booked` key is the identity; set, there is nothing to commit.
    seeded_ledgers(sb, d(-1), "pending")
    before = counts(sb)
    for name, ledger in (("picks", LedgerService), ("slips", SlipLedger), ("gold", GoldLedger)):
        res = ledger.commit(fake_weekly(d(1), booked=d(-1)))
        check("booked" in res.get("reason", ""), f"{name} did not refuse the live round: {res}")
    check(counts(sb) == before, f"rows grew on a refused commit: {before} -> {counts(sb)}")
    return f"counts unchanged {before}"


# ===========================================================================
# 5. THE PAYLOAD GATE  (publish.check)
# ===========================================================================
def payload(sb: Sandbox, drop: Optional[tuple] = None, round_fx: Optional[List[Dict]] = None) -> None:
    pub = publish.PUB
    for layer in ("team", "mental", "managers"):
        keys = [publish.slug(lg) for lg in LEAGUES]
        if drop and drop[0] == layer:
            keys.remove(publish.slug(drop[1]))
        (pub / layer).mkdir(parents=True, exist_ok=True)
        (pub / layer / "index.json").write_text(json.dumps({"leagues": [{"key": k} for k in keys]}),
                                                encoding="utf-8")
    fx = round_fx if round_fx is not None else [
        {"home": "A", "away": "B", "home_p": 0.45, "draw_p": 0.27, "away_p": 0.28}]
    (pub / "round.json").write_text(json.dumps({"leagues": {"eng": {"fixtures": fx}}}), encoding="utf-8")
    (pub / "team" / "eng-premier-league").mkdir(parents=True, exist_ok=True)
    (pub / "team" / "eng-premier-league" / "elo.json").write_text("x" * 1000, encoding="utf-8")


@case("payload", "a sane payload passes the gate")
def payload_ok(sb):
    payload(sb)
    bad = publish.check(publish.sizes_before())
    check(bad == [], f"gate complained about a sane payload: {bad}")
    return "no complaints"


@case("payload", "every ready league in all three indexes")
def payload_missing_league(sb):
    # three builders write these indexes and each has at some point written
    # the file whole, deleting the other leagues — a site missing four fifths
    # of its content that looks normal until you open the dropdown
    payload(sb, drop=("mental", "ITA-Serie A"))
    bad = publish.check(publish.sizes_before())
    check(any("mental/index.json is missing ita-serie-a" in b for b in bad), f"missing league not caught: {bad}")
    return bad[0]


@case("payload", "round H/D/A sums to 1")
def payload_hda(sb):
    payload(sb, round_fx=[{"home": "A", "away": "B", "home_p": 0.5, "draw_p": 0.3, "away_p": 0.3},
                          {"home": "C", "away": "D", "home_p": 0.4, "draw_p": 0.3, "away_p": 0.3}])
    bad = publish.check(publish.sizes_before())
    check(any("1 fixture(s) whose H/D/A does not sum to 1" in b for b in bad), f"bad triplet not caught: {bad}")
    payload(sb, round_fx=[])
    bad = publish.check(publish.sizes_before())
    check(any("no fixtures" in b for b in bad), f"empty round not caught: {bad}")
    return "1 of 2 fixtures flagged; empty round flagged"


@case("payload", "no payload shrank past SHRINK_LIMIT, none empty")
def payload_shrink(sb):
    payload(sb)
    before = publish.sizes_before()
    rel = str(Path("team") / "eng-premier-league" / "elo.json")
    before[rel] = int(1000 / publish.SHRINK_LIMIT) + 10     # it used to be bigger than the limit allows
    (publish.PUB / "mental" / "empty.json").write_text("", encoding="utf-8")
    bad = publish.check(before)
    check(any("elo.json shrank" in b for b in bad), f"shrink not caught: {bad}")
    check(any("empty.json is empty" in b for b in bad), f"empty file not caught: {bad}")
    before[rel] = 1000
    check(publish.check(before) == [str(Path('mental') / 'empty.json') + " is empty"],
          "an unchanged payload was reported as shrunk")
    return "shrink and empty both flagged"


# ===========================================================================
# 6. THE STEP RUNNER  (run_daily.run)
# ===========================================================================
def child_script(sb: Sandbox, body: str) -> Path:
    p = sb.root / "child.py"
    p.write_text(body, encoding="utf-8")
    return p


def run_step(label: str, script: Path) -> tuple:
    """run_daily.run with its live echo captured; (ok, seconds, echoed)."""
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        ok = run_daily.run(label, [str(script)])
    return ok, time.time() - t0, buf.getvalue()


@case("runner", "a child that exits leaving a grandchild on its stdout pipe returns in seconds")
def runner_orphaned_pipe(sb):
    # 2026-10-29: the injuries step exited at 15:21 and the run sat on
    # `for line in p.stdout` until 17:32 because an orphaned uc_driver.exe
    # still held the write end of the pipe. run() must wait on the PROCESS.
    hold = 40
    script = child_script(sb, f"""
import subprocess, sys, pathlib
g = subprocess.Popen([sys.executable, "-c", "import time; time.sleep({hold})"],
                     stdout=sys.stdout, stderr=sys.stderr, close_fds=False)
pathlib.Path(r"{sb.root / 'grandchild.pid'}").write_text(str(g.pid))
print("child done, grandchild", g.pid, "holds the pipe", flush=True)
""")
    try:
        ok, secs, out = run_step("probe orphan", script)
    finally:
        try:
            pid = int((sb.root / "grandchild.pid").read_text())
            subprocess.call(["taskkill", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL) if os.name == "nt" else os.kill(pid, 9)
        except (OSError, ValueError):
            pass
    check(ok, f"the step exited 0 and was reported as failed:\n{out}")
    check(secs < hold / 2, f"run() took {secs:.0f}s: it waited on the pipe, not the process")
    check("child done" in out, "the child's output line was lost")
    return f"returned in {secs:.1f}s with a grandchild holding the pipe for {hold}s"


@case("runner", "a non-zero exit is FAILED with the last lines")
def runner_failed(sb):
    script = child_script(sb, 'print("fetching"); print("boom: 502 from fbref"); raise SystemExit(3)')
    ok, secs, out = run_step("probe fail", script)
    check(not ok, "exit 3 was reported ok")
    label, status, _ = run_daily.done[-1]
    check(label == "probe fail" and status.startswith("FAILED"), f"summary row: {status!r}")
    check("boom: 502" in status, f"last lines missing from the summary: {status!r}")
    check(not run_daily.STEP_LOG.exists(), "a failed step was marked done in the step log")
    return status


@case("runner", "a zero exit marks the step log")
def runner_ok(sb):
    # 2026-10-25: a run died after sources and three event steps; all of it
    # was on disk and all of it would have been redone. A step that succeeds
    # records itself against today so a resume can skip it.
    script = child_script(sb, 'print("done")')
    ok, secs, out = run_step("probe ok", script)
    check(ok, f"exit 0 reported as failure:\n{out}")
    check(run_daily.done[-1][1] == "ok", f"summary row: {run_daily.done[-1]}")
    log = json.loads(run_daily.STEP_LOG.read_text(encoding="utf-8"))
    check(log.get("date") == run_daily._today() and "probe ok" in log.get("done", {}),
          f"step log not marked: {log}")
    return f"step log {run_daily.STEP_LOG.name}: {list(log['done'])}"


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------
def run_case(c: Case) -> tuple:
    """(passed, reason) for one case in a fresh sandbox."""
    try:
        with Sandbox() as sb:
            note = c.fn(sb)
        return True, note or ""
    except AssertionError as e:
        return False, str(e)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def ledger_digest() -> Dict[str, str]:
    out = {}
    for p in REAL_LEDGERS:
        out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing"
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-k", default="", help="only cases whose id contains this")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    cases = [c for c in CASES if args.k.lower() in c.id.lower()]
    if args.list:
        for c in cases:
            print(c.id)
        return 0

    before = ledger_digest()
    t0 = time.time()
    failed = 0
    width = max(len(c.id) for c in cases) if cases else 0
    for c in cases:
        ok, why = run_case(c)
        failed += not ok
        why = why.replace("\n", " | ")
        print(f"{'PASS' if ok else 'FAIL'}  {c.id:<{width}}  {why}", flush=True)
    if ledger_digest() != before:
        failed += 1
        print("FAIL  selfcheck touched a real ledger — this must never happen", flush=True)
    secs = time.time() - t0
    print(f"\n{len(cases) - failed}/{len(cases)} passed in {secs:.1f}s"
          + ("" if not failed else f" — {failed} FAILED; publish must not proceed"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
