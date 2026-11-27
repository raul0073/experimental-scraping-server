from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from typing import Any, Dict, List

from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.windows import VOID_NOTE, stale_floor

log = logging.getLogger(__name__)

GOLD_PATH = Path("data/slips/gold.jsonl")
UNIT = 10.0
START_POT = 1000.0
GOLD_P = 0.55
# THE GOLD POT BETS ONE ACCUMULATOR A WEEK (user decision 2026-11-27).
# Singles at fair prices were the calibration test wearing a bankroll; the
# user's money goes on accumulators, so the pot now does too. Eight seasons
# walk-forward (scripts/experiment_accumulators.py, 292 weeks): a 4-fold of
# the strongest calls at >= 55% lands 3.1 of 4 legs and the whole ticket
# 36% of weeks against 27% stated; from five legs the return at book turns
# negative and the losing run doubles. Four is the cap, two the floor.
ACCA_N = 4
ACCA_MIN = 2


def legs_of(row):
    """A row's legs whichever shape it has: singles (bets) before 2026-11-27,
    one accumulator (legs) after. Both grade and both count."""
    return row.get("legs") or row.get("bets") or []


class GoldLedger:
    """Gate-A instrument: a second paper pot that bets EVERY certified GOLD
    favorite (any league, model p >= 0.55, normal confidence) as a single at
    its frozen breakeven price (1/p).

    At breakeven prices ROI > 0 exactly when realized accuracy beats the
    model's stated probability — so this pot directly measures whether the
    'GOLD realizes 65-67%' claim holds live, which is what Gate A of the
    investor plan needs (n >= 150 at >= 62%).
    """

    @staticmethod
    def _read() -> List[Dict[str, Any]]:
        if not GOLD_PATH.exists():
            return []
        return [json.loads(l) for l in
                GOLD_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def _write(rows: List[Dict[str, Any]]) -> None:
        GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = GOLD_PATH.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        tmp.replace(GOLD_PATH)

    # ------------------------------------------------ commit

    MAX_DAYS_AHEAD = 2  # never book a window opening further out than this

    @classmethod
    def commit(cls, weekly: Dict[str, Any]) -> Dict[str, Any]:
        win = weekly.get("window") or {}
        # A LIVE BOOKED ROUND IS NEVER COMMITTED AGAIN. While any bet under a
        # round is pending, weekly_picks serves that round back and names it
        # in "booked"; its window.start is then the earliest kickoff booked
        # under it, which is not always the round's key (2026-10-29: key
        # 10-29, earliest kickoff 10-30). Comparing the key against the span
        # start let the gold ledger book the same round twice. The booked
        # key is the identity; if it is set there is nothing new to commit.
        booked = weekly.get("booked")
        if booked:
            return {"committed": 0, "reason": f"window {booked} is live and booked"}
        if not win.get("start"):
            return {"committed": 0, "reason": "no window"}
        from datetime import datetime as _dt, timezone as _tz
        lead_d = (_dt.fromisoformat(win["start"]).date()
                  - _dt.now(_tz.utc).date()).days
        if lead_d > cls.MAX_DAYS_AHEAD:
            return {"committed": 0,
                    "reason": f"window opens in {lead_d}d (> {cls.MAX_DAYS_AHEAD})"}
        rows = cls._read()
        # ONE SET OF GOLD BETS PER WINDOW, PENDING OR NOT — same reasoning as
        # slips and picks: the old check required a PENDING row, so a fully
        # graded window could be booked again.
        if any(r.get("window") == win["start"] for r in rows):
            return {"committed": 0,
                    "reason": f"window {win['start']} already has gold bets"}

        acca = weekly.get("acca") or {}
        legs_in = [l for l in acca.get("legs") or [] if not l.get("score")]
        if len(legs_in) < ACCA_MIN:
            return {"committed": 0,
                    "reason": f"only {len(legs_in)} qualifying leg(s) (< {ACCA_MIN})"}
        legs = []
        for l in legs_in[:ACCA_N]:
            side = l["pick_type"]
            prob = float(l["pick_prob"])
            legs.append({
                "league_full": l["league"], "league": l["league"].split("-")[1],
                "home": l["home"], "away": l["away"],
                "fixture": f"{l['home']} v {l['away']}",
                "team": l["home"] if side == "home" else l["away"] if side == "away" else "draw",
                "side": side, "prob": round(prob, 4), "breakeven": round(1 / prob, 3),
                "kickoff": l["kickoff"],
            })
        fair = 1.0
        p_all = 1.0
        for l in legs:
            fair *= l["breakeven"]
            p_all *= l["prob"]
        rows.append({
            "committed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "season": weekly["season"], "window": win["start"],
            "type": "acca", "unit": UNIT, "stake": UNIT,
            "legs": legs, "fair": round(fair, 3), "p_all": round(p_all, 4),
            "status": "pending",
        })
        cls._write(rows)
        return {"committed": 1, "window": win["start"], "legs": len(legs), "fair": round(fair, 2)}

    # ------------------------------------------------ grade

    @classmethod
    def grade(cls) -> Dict[str, int]:
        rows = cls._read()
        pending = [r for r in rows if r["status"] == "pending"]
        if not pending:
            return {"graded": 0}
        books: Dict[tuple, Dict] = {}
        for r in pending:
            for b in legs_of(r):
                key = (b["league_full"], r["season"])
                if key not in books:
                    fx = FixturesService.load(*key)
                    books[key] = {}
                    if fx:
                        for m in fx["matches"]:
                            if m["played"]:
                                books[key][(m["home_team"], m["away_team"])] = m
        graded = 0
        resolved_now = 0   # legs settled this pass, even in unfinished windows
        floor = stale_floor()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in pending:
            all_resolved = True
            for b in legs_of(r):
                if "hit" in b:
                    continue
                book = books.get((b["league_full"], r["season"]), {})
                m = book.get((b["home"], b["away"]))
                flipped = False
                if not m:
                    m = book.get((b["away"], b["home"]))
                    flipped = m is not None
                if not m:
                    # Same rule as the slips: a bet nothing will ever match
                    # is void at 1.00 once the grace period has passed, so
                    # the window grades and the stake comes back.
                    if b.get("kickoff") and b["kickoff"] < floor:
                        b["void"] = True
                        b["hit"] = True
                        b["breakeven"] = 1.0
                        b["note"] = VOID_NOTE
                        resolved_now += 1
                        continue
                    all_resolved = False
                    continue
                hg, ag = (m["away_goals"], m["home_goals"]) if flipped else \
                         (m["home_goals"], m["away_goals"])
                winner = b["home"] if hg > ag else b["away"] if ag > hg else None
                b["score"] = f"{hg}-{ag}"
                b["hit"] = (winner is None) if b["side"] == "draw" else winner == b["team"]
                resolved_now += 1
            if not all_resolved:
                continue
            legs = legs_of(r)
            hits = sum(1 for b in legs if b["hit"])
            if r.get("type") == "acca":
                # one line: every leg must land, and it pays the product of
                # the frozen breakevens; a void leg is 1.00 and drops out
                gross = r["unit"] * float(np.prod([b["breakeven"] for b in legs])) if hits == len(legs) else 0.0
            else:
                gross = sum(r["unit"] * b["breakeven"] for b in legs if b["hit"])
            r["status"] = "graded"
            r["graded_at"] = now
            r["hits"] = hits
            r["gross_return"] = round(gross, 2)
            r["net"] = round(gross - r["stake"], 2)
            graded += 1
        # persist settled legs even when their window is not finished — a
        # window grades atomically, but throwing away resolved legs meant
        # re-deriving them every run and showing no progress until the last
        # kickoff landed (15-bet windows can straddle four days)
        if graded or resolved_now:
            cls._write(rows)
        return {"graded": graded, "still_pending": len(pending) - graded,
                "legs_resolved": resolved_now}

    # ------------------------------------------------ summary (Gate A)

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        rows = sorted(cls._read(), key=lambda r: r["window"])
        pot = START_POT
        staked = returned = 0.0
        weeks = []
        for r in rows:
            entry = {**r}
            pot -= r["stake"]
            staked += r["stake"]
            if r["status"] == "graded":
                pot += r["gross_return"]
                returned += r["gross_return"]
            entry["pot_after"] = round(pot, 2)
            weeks.append(entry)
        graded_bets = [b for r in rows if r["status"] == "graded" and r.get("type") != "acca" for b in r["bets"]]
        tickets = [r for r in rows if r.get("type") == "acca"]
        t_graded = [r for r in tickets if r["status"] == "graded"]
        t_landed = sum(1 for r in t_graded if r["hits"] == len(r["legs"]))
        t_legs = [b for r in t_graded for b in r["legs"]]
        n = len(graded_bets)
        hits = sum(1 for b in graded_bets if b["hit"])
        exp_hits = sum(b["prob"] for b in graded_bets)
        # live view: every settled leg, including those in windows still
        # waiting on a late kickoff (the money is decided, the row isn't)
        settled = [b for r in rows for b in legs_of(r) if "hit" in b]
        s_hits = sum(1 for b in settled if b["hit"])
        s_exp = sum(b["prob"] for b in settled)
        pend_legs = sum(1 for r in rows for b in legs_of(r) if "hit" not in b)
        staked_graded = sum(r["stake"] for r in rows if r["status"] == "graded")
        return {
            "start_pot": START_POT, "pot": round(pot, 2),
            "staked": round(staked, 2), "returned": round(returned, 2),
            "in_play": round(sum(r["stake"] for r in rows if r["status"] == "pending"), 2),
            "net": round(returned - staked_graded, 2),
            "roi": round((returned - staked_graded) / staked_graded, 4) if staked_graded else None,
            "bets_graded": n, "hits": hits,
            "realized": round(hits / n, 4) if n else None,
            "expected": round(exp_hits / n, 4) if n else None,
            "settled": {"n": len(settled), "hits": s_hits, "pending_legs": pend_legs,
                        "realized": round(s_hits / len(settled), 4) if settled else None,
                        "expected": round(s_exp / len(settled), 4) if settled else None},
            "gate_a": {"target_n": 150, "target_acc": 0.62,
                       "on_track": (hits / n >= 0.62) if n else None},
            # the accumulator book: one ticket a week since 2026-11-27
            "tickets": {
                "n": len(tickets), "graded": len(t_graded), "landed": t_landed,
                "landed_rate": round(t_landed / len(t_graded), 4) if t_graded else None,
                "expected_rate": round(sum(r["p_all"] for r in t_graded) / len(t_graded), 4) if t_graded else None,
                "legs_graded": len(t_legs), "legs_landed": sum(1 for b in t_legs if b["hit"]),
                "legs_expected": round(sum(b["prob"] for b in t_legs), 2),
                "staked": round(sum(r["stake"] for r in t_graded), 2),
                "returned": round(sum(r["gross_return"] for r in t_graded), 2),
                "cap": ACCA_N, "floor": GOLD_P,
            },
            "weeks": list(reversed(weeks)),
        }
