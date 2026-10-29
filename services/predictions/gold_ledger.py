from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from services.fbref.fixtures.fixtures_service import FixturesService

log = logging.getLogger(__name__)

GOLD_PATH = Path("data/slips/gold.jsonl")
UNIT = 10.0
START_POT = 1000.0
GOLD_P = 0.55


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

        bets = []
        for lg, preds in (weekly.get("all_predictions") or {}).items():
            for p in preds:
                if not p.get("in_window") or p["confidence"] != "normal":
                    continue
                # NEVER BET A FINISHED GAME. A live round keeps its played
                # fixtures on the board so the round stays whole as it
                # resolves, which means all_predictions can now hand this loop
                # a result it already knows. Backing it would be free money on
                # paper and a lie in the bankroll.
                if p.get("score"):
                    continue
                fav = max(p["probabilities"], key=p["probabilities"].get)
                prob = p["probabilities"][fav]
                if fav not in ("home", "away") or prob < GOLD_P:
                    continue
                team = p["home"] if fav == "home" else p["away"]
                bets.append({
                    "league_full": lg, "league": lg.split("-")[1],
                    "home": p["home"], "away": p["away"],
                    "fixture": f"{p['home']} v {p['away']}",
                    "team": team, "side": fav,
                    "prob": round(prob, 4),
                    "breakeven": round(1 / prob, 3),
                    "kickoff": p["kickoff"],
                })
        if not bets:
            return {"committed": 0, "reason": "no GOLD favorites this window"}
        rows.append({
            "committed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "season": weekly["season"], "window": win["start"],
            "unit": UNIT, "stake": round(len(bets) * UNIT, 2),
            "bets": bets, "status": "pending",
        })
        cls._write(rows)
        return {"committed": 1, "window": win["start"], "bets": len(bets)}

    # ------------------------------------------------ grade

    @classmethod
    def grade(cls) -> Dict[str, int]:
        rows = cls._read()
        pending = [r for r in rows if r["status"] == "pending"]
        if not pending:
            return {"graded": 0}
        books: Dict[tuple, Dict] = {}
        for r in pending:
            for b in r["bets"]:
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
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in pending:
            all_resolved = True
            for b in r["bets"]:
                if "hit" in b:
                    continue
                book = books.get((b["league_full"], r["season"]), {})
                m = book.get((b["home"], b["away"]))
                flipped = False
                if not m:
                    m = book.get((b["away"], b["home"]))
                    flipped = m is not None
                if not m:
                    all_resolved = False
                    continue
                hg, ag = (m["away_goals"], m["home_goals"]) if flipped else \
                         (m["home_goals"], m["away_goals"])
                winner = b["home"] if hg > ag else b["away"] if ag > hg else None
                b["score"] = f"{hg}-{ag}"
                b["hit"] = winner == b["team"]
                resolved_now += 1
            if not all_resolved:
                continue
            hits = sum(1 for b in r["bets"] if b["hit"])
            gross = sum(r["unit"] * b["breakeven"] for b in r["bets"] if b["hit"])
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
        graded_bets = [b for r in rows if r["status"] == "graded" for b in r["bets"]]
        n = len(graded_bets)
        hits = sum(1 for b in graded_bets if b["hit"])
        exp_hits = sum(b["prob"] for b in graded_bets)
        # live view: every settled leg, including those in windows still
        # waiting on a late kickoff (the money is decided, the row isn't)
        settled = [b for r in rows for b in r["bets"] if "hit" in b]
        s_hits = sum(1 for b in settled if b["hit"])
        s_exp = sum(b["prob"] for b in settled)
        pend_legs = sum(1 for r in rows for b in r["bets"] if "hit" not in b)
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
            "weeks": list(reversed(weeks)),
        }
