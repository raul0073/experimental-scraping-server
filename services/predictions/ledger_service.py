from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.fbref.fixtures.fixtures_service import FixturesService

log = logging.getLogger(__name__)

LEDGER_PATH = Path("data/ledger/picks.jsonl")


class LedgerService:
    """Append-only pick ledger — the honesty mechanism (rules.md #3).

    Picks are committed BEFORE results exist and never modified afterwards,
    except to fill in the graded outcome. A (season, week, pick_type) that is
    already committed can never be overwritten.
    """

    @staticmethod
    def _read() -> List[Dict[str, Any]]:
        if not LEDGER_PATH.exists():
            return []
        return [json.loads(line) for line in
                LEDGER_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _write(rows: List[Dict[str, Any]]) -> None:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = LEDGER_PATH.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        tmp.replace(LEDGER_PATH)

    # ------------------------------------------------ commit

    # window construction already guarantees the next window starts after the
    # last bet's final kickoff (prediction_service._last_bet_end); these are
    # belt-and-braces: no re-commit within 3 days, and never book a window
    # that opens more than 3 days out (the user places on Thursdays)
    MIN_ROUND_GAP_DAYS = 3
    MAX_DAYS_AHEAD = 2

    @classmethod
    def commit(cls, weekly: Dict[str, Any]) -> Dict[str, Any]:
        """Record this week's picks; refuses to double-commit a week."""
        rows = cls._read()
        added = skipped = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        win = weekly.get("window") or {}
        window, window_end = win.get("start"), win.get("end")

        last = max((r["committed_at"] for r in rows), default=None)
        if last:
            age_d = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(last)).total_seconds() / 86400
            if age_d < cls.MIN_ROUND_GAP_DAYS:
                return {"added": 0, "skipped_existing_weeks": 0,
                        "reason": f"round guard: last commit {age_d:.1f}d ago"}
        if window:
            lead_d = (datetime.fromisoformat(window).date()
                      - datetime.now(timezone.utc).date()).days
            if lead_d > cls.MAX_DAYS_AHEAD:
                return {"added": 0, "skipped_existing_weeks": 0,
                        "reason": f"window opens in {lead_d}d (> {cls.MAX_DAYS_AHEAD})"}

        # a window is "already committed" for a pick type when pending picks of
        # that type have kickoffs inside it — robust to the window label
        # drifting as early fixtures get played. Computed BEFORE appending.
        taken = {(r["season"], r["pick_type"]) for r in rows
                 if r["status"] == "pending" and window and window_end
                 and r.get("kickoff") and window <= r["kickoff"] <= window_end}

        for p in (weekly["draw_picks"] + weekly["home_win_picks"]
                  + weekly.get("away_win_picks", [])):
            if (p["season"], p["pick_type"]) in taken:
                skipped += 1
                continue
            rows.append({
                "committed_at": now,
                "season": p["season"],
                "window": window,
                "week": p["week"],
                "pick_type": p["pick_type"],
                "rank": p["rank"],
                "league": p["league"],
                "home": p["home"],
                "away": p["away"],
                "kickoff": p["kickoff"],
                "pick_prob": p["pick_prob"],
                "probabilities": p["probabilities"],
                "xg": p["xg"],
                "status": "pending",
            })
            added += 1
        if added:
            cls._write(rows)
        log.info("ledger commit: %d added, %d skipped (already committed)", added, skipped)
        return {"added": added, "skipped_existing_weeks": skipped}

    # ------------------------------------------------ grade

    @classmethod
    def grade(cls) -> Dict[str, Any]:
        rows = cls._read()
        pending = [r for r in rows if r["status"] == "pending"]
        if not pending:
            return {"graded": 0}

        results: Dict[tuple, Dict] = {}
        by_date: Dict[tuple, List[Dict]] = {}
        for league_season in {(r["league"], r["season"]) for r in pending}:
            fx = FixturesService.load(*league_season)
            if not fx:
                continue
            for m in fx["matches"]:
                if m["played"]:
                    results[(league_season[0], league_season[1],
                             m["home_team"], m["away_team"])] = m
                    by_date.setdefault((*league_season, m["date"]), []).append(m)

        graded = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in pending:
            # exact -> reversed venue (fbref sometimes flips home/away after
            # commit) -> same-date single-name match (fbref renames teams)
            m = results.get((r["league"], r["season"], r["home"], r["away"]))
            flipped = False
            if not m:
                m = results.get((r["league"], r["season"], r["away"], r["home"]))
                flipped = m is not None
            if not m and r.get("kickoff"):
                ours = {r["home"], r["away"]}
                cands = [c for c in by_date.get((r["league"], r["season"], r["kickoff"]), [])
                         if {c["home_team"], c["away_team"]} & ours]
                if len(cands) == 1:
                    m = cands[0]
                    flipped = m["home_team"] == r["away"] or m["away_team"] == r["home"]
            if not m:
                continue
            outcome = "home" if m["home_goals"] > m["away_goals"] else \
                      "away" if m["away_goals"] > m["home_goals"] else "draw"
            # hit is judged from OUR pick's perspective: a draw pick is
            # venue-agnostic; home/away picks mean "OUR home/away team wins"
            # even when fbref flipped the venue after commit
            our_home_won = outcome == ("away" if flipped else "home")
            our_away_won = outcome == ("home" if flipped else "away")
            r["status"] = "graded"
            r["graded_at"] = now
            r["score"] = f"{m['home_goals']}-{m['away_goals']}"
            r["outcome"] = outcome
            if flipped:
                r["note"] = f"graded via fallback (played as {m['home_team']} v {m['away_team']})"
            r["hit"] = (outcome == "draw") if r["pick_type"] == "draw" else \
                       our_home_won if r["pick_type"] == "home" else \
                       our_away_won if r["pick_type"] == "away" else outcome == r["pick_type"]
            graded += 1
        if graded:
            cls._write(rows)
        return {"graded": graded, "still_pending": len(pending) - graded}

    # ------------------------------------------------ summary

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        rows = cls._read()
        out: Dict[str, Any] = {"total_picks": len(rows), "by_type": {}}
        for pick_type in ("draw", "home", "away"):
            sub = [r for r in rows if r["pick_type"] == pick_type]
            graded = [r for r in sub if r["status"] == "graded"]
            hits = sum(1 for r in graded if r["hit"])
            out["by_type"][pick_type] = {
                "committed": len(sub),
                "graded": len(graded),
                "hits": hits,
                "hit_rate": round(hits / len(graded), 3) if graded else None,
                "avg_pick_prob": round(sum(r["pick_prob"] for r in graded) / len(graded), 3)
                if graded else None,
            }
        return out

    @classmethod
    def entries(cls, season: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = cls._read()
        if season:
            rows = [r for r in rows if r["season"] == season]
        return rows
