from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.fbref.fixtures.fixtures_service import FixturesService

log = logging.getLogger(__name__)

SLIPS_PATH = Path("data/slips/slips.jsonl")
UNIT = 10.0          # ₪ per line (user default)
START_POT = 1000.0   # the monkey's opening bankroll


class SlipLedger:
    """The monkey's book: every window, the advisor's recommended slip is
    'placed' at UNIT per line and graded line-by-line when all legs resolve.

    Returns are computed at each leg's BREAKEVEN (fair) price frozen at commit
    — the structural truth of the bet; real Winner odds shift actual returns
    around these numbers.
    """

    @staticmethod
    def _read() -> List[Dict[str, Any]]:
        if not SLIPS_PATH.exists():
            return []
        return [json.loads(l) for l in
                SLIPS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def _write(rows: List[Dict[str, Any]]) -> None:
        SLIPS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SLIPS_PATH.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        tmp.replace(SLIPS_PATH)

    # ------------------------------------------------ commit

    MIN_ROUND_GAP_DAYS = 3  # one slip per round — see LedgerService
    MAX_DAYS_AHEAD = 2      # never book a window opening further out than this

    @classmethod
    def commit(cls, weekly: Dict[str, Any]) -> Dict[str, Any]:
        strategy = weekly.get("strategy")
        win = weekly.get("window") or {}
        if not strategy or not strategy.get("slip") or not win.get("start"):
            return {"committed": 0, "reason": "no slip"}
        rows = cls._read()
        last = max((r["committed_at"] for r in rows), default=None)
        if last:
            age_d = (datetime.now(timezone.utc)
                     - datetime.fromisoformat(last)).total_seconds() / 86400
            if age_d < cls.MIN_ROUND_GAP_DAYS:
                return {"committed": 0,
                        "reason": f"round guard: last slip {age_d:.1f}d ago"}
        lead_d = (datetime.fromisoformat(win["start"]).date()
                  - datetime.now(timezone.utc).date()).days
        if lead_d > cls.MAX_DAYS_AHEAD:
            return {"committed": 0,
                    "reason": f"window opens in {lead_d}d (> {cls.MAX_DAYS_AHEAD})"}
        # one slip per window: skip when a pending slip has a leg kickoff
        # inside this window (drift-proof, same rule as the pick ledger)
        for r in rows:
            if r["status"] == "pending" and any(
                    win["start"] <= (l.get("kickoff") or "") <= win["end"]
                    for l in r["legs"]):
                return {"committed": 0, "reason": "window already has a pending slip"}
        s = strategy["slip"]
        rows.append({
            "committed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "season": weekly["season"], "window": win["start"],
            "title_he": s["title_he"], "title_en": s["title_en"],
            "k": s["k"], "lines": s["lines"], "unit": UNIT,
            "stake": round(s["lines"] * UNIT, 2),
            "p_profit": round(s.get("p_profit", 0), 4),
            "legs": s["legs"],
            "status": "pending",
        })
        cls._write(rows)
        return {"committed": 1, "window": win["start"], "form": s["title_he"],
                "stake": s["lines"] * UNIT}

    # ------------------------------------------------ grade

    @classmethod
    def grade(cls) -> Dict[str, int]:
        rows = cls._read()
        pending = [r for r in rows if r["status"] == "pending"]
        if not pending:
            return {"graded": 0}

        results: Dict[tuple, Dict] = {}
        for r in pending:
            for l in r["legs"]:
                key = (l["league_full"], r["season"])
                if key not in results:
                    fx = FixturesService.load(*key)
                    results[key] = {}
                    if fx:
                        for m in fx["matches"]:
                            if m["played"]:
                                results[key][(m["home_team"], m["away_team"])] = m

        graded = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in pending:
            all_resolved = True
            for l in r["legs"]:
                if "hit" in l:
                    continue
                book = results.get((l["league_full"], r["season"]), {})
                m = book.get((l["home"], l["away"]))
                flipped = False
                if not m:
                    m = book.get((l["away"], l["home"]))
                    flipped = m is not None
                if not m:
                    all_resolved = False
                    continue
                hg, ag = (m["away_goals"], m["home_goals"]) if flipped else \
                         (m["home_goals"], m["away_goals"])
                outcome = "home" if hg > ag else "away" if ag > hg else "draw"
                l["score"] = f"{hg}-{ag}"
                if l["role"] == "draw":
                    l["hit"] = outcome == "draw"
                else:
                    winner = l["home"] if outcome == "home" else \
                             l["away"] if outcome == "away" else None
                    l["hit"] = winner == l.get("team")
            if not all_resolved:
                continue

            hit_idx = [i for i, l in enumerate(r["legs"]) if l["hit"]]
            lines_won = 0
            gross = 0.0
            for combo in combinations(range(len(r["legs"])), r["k"]):
                if all(i in hit_idx for i in combo):
                    lines_won += 1
                    line = r["unit"]
                    for i in combo:
                        line *= r["legs"][i]["breakeven"]
                    gross += line
            r["status"] = "graded"
            r["graded_at"] = now
            r["hits"] = len(hit_idx)
            r["lines_won"] = lines_won
            r["gross_return"] = round(gross, 2)
            r["net"] = round(gross - r["stake"], 2)
            graded += 1
        if graded:
            cls._write(rows)
        return {"graded": graded, "still_pending": len(pending) - graded}

    # ------------------------------------------------ monkey summary

    @classmethod
    def monkey(cls) -> Dict[str, Any]:
        rows = sorted(cls._read(), key=lambda r: r["window"])
        pot = START_POT
        staked = returned = 0.0
        weeks = []
        peak = START_POT
        for r in rows:
            entry = {**r}
            pot -= r["stake"]
            staked += r["stake"]
            if r["status"] == "graded":
                pot += r["gross_return"]
                returned += r["gross_return"]
            entry["pot_after"] = round(pot, 2)
            peak = max(peak, pot)
            weeks.append(entry)
        graded = [r for r in rows if r["status"] == "graded"]
        staked_graded = sum(r["stake"] for r in graded)
        in_play = sum(r["stake"] for r in rows if r["status"] == "pending")
        return {
            "start_pot": START_POT, "pot": round(pot, 2),
            "staked": round(staked, 2), "returned": round(returned, 2),
            "in_play": round(in_play, 2),
            "net": round(returned - staked_graded, 2),
            "roi": round((returned - staked_graded) / staked_graded, 4) if staked_graded else None,
            "weeks_played": len(rows), "weeks_graded": len(graded),
            "profit_weeks": sum(1 for r in graded if r["net"] > 0),
            "peak": round(peak, 2),
            "weeks": list(reversed(weeks)),
        }

    @classmethod
    def slip_detail(cls, window: str) -> Optional[Dict[str, Any]]:
        """The original slip + its line-by-line breakdown at frozen prices."""
        rows = [r for r in cls._read() if r["window"] == window]
        if not rows:
            return None
        r = rows[0]
        lines = []
        for combo in combinations(range(len(r["legs"])), r["k"]):
            legs = [r["legs"][i] for i in combo]
            product = 1.0
            for l in legs:
                product *= l["breakeven"]
            resolved = all("hit" in l for l in legs)
            won = resolved and all(l["hit"] for l in legs)
            lines.append({
                "names": " + ".join(f"{l['mark']} {l['fixture']}" for l in legs),
                "product": round(product, 2),
                "stake": r["unit"],
                "won": won if resolved else None,
                "return": round(r["unit"] * product, 2) if won else 0.0,
            })
        lines.sort(key=lambda x: -x["return"])
        return {**r, "line_detail": lines}
