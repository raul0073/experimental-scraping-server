from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from services.fbref.fixtures.fixtures_service import FixturesService
from services.understat.understat_service import UnderstatService

log = logging.getLogger(__name__)

HISTORY_PATH = Path("data/history/predictions.jsonl")
XG_TOL = 0.20  # a predicted xG "hits" when within +/- this of the real xG, both teams


class HistoryService:
    """Full prediction history — every fixture we ever predicted, graded
    against the actual score AND the actual xG. The self-honesty tab: the
    FIRST prediction recorded for a fixture stands forever (re-predictions
    with fresher data never overwrite it)."""

    @staticmethod
    def _read() -> List[Dict[str, Any]]:
        if not HISTORY_PATH.exists():
            return []
        return [json.loads(l) for l in
                HISTORY_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    @staticmethod
    def _write(rows: List[Dict[str, Any]]) -> None:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_PATH.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        tmp.replace(HISTORY_PATH)

    # ------------------------------------------------ record

    @classmethod
    def record(cls, weekly: Dict[str, Any], retro: bool = False) -> Dict[str, int]:
        """retro=True marks rows reconstructed walk-forward after the fact
        (season backfill) — same methodology, but honestly distinguishable
        from predictions recorded before kickoff."""
        rows = cls._read()
        seen = {(r["season"], r["league"], r["home"], r["away"]) for r in rows}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        added = 0
        for league, preds in (weekly.get("all_predictions") or {}).items():
            for p in preds:
                key = (p["season"], league, p["home"], p["away"])
                if key in seen:
                    continue
                seen.add(key)
                pred_outcome = max(p["probabilities"], key=p["probabilities"].get)
                rows.append({
                    "recorded_at": now,
                    "retro": retro,
                    "season": p["season"], "league": league, "week": p["week"],
                    "kickoff": p["kickoff"], "home": p["home"], "away": p["away"],
                    "probabilities": p["probabilities"],
                    "pred_xg": [p["xg"][p["home"]], p["xg"][p["away"]]],
                    "pred_outcome": pred_outcome,
                    "pred_score": p["modal_scores"][pred_outcome][0],
                    "confidence": p["confidence"],
                    "status": "pending",
                })
                added += 1
        if added:
            cls._write(rows)
        return {"recorded": added, "total": len(rows)}

    # ------------------------------------------------ grade

    @classmethod
    def grade(cls) -> Dict[str, int]:
        rows = cls._read()
        pending = [r for r in rows if r["status"] == "pending"]
        if not pending:
            return {"graded": 0}

        fx_res: Dict[tuple, Dict] = {}
        xg_res: Dict[tuple, tuple] = {}
        for league, season in {(r["league"], r["season"]) for r in pending}:
            fx = FixturesService.load(league, season)
            if fx:
                for m in fx["matches"]:
                    if m["played"]:
                        fx_res[(league, m["home_team"], m["away_team"])] = m
            us = UnderstatService.load(league, season)
            if us:
                for m in us["matches"]:
                    if m.get("home_xg") is not None:
                        xg_res[(league, m["home_team"], m["away_team"])] = (
                            m["home_xg"], m["away_xg"])

        graded = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in pending:
            key = (r["league"], r["home"], r["away"])
            m = fx_res.get(key)
            flipped = False
            if not m:
                m = fx_res.get((r["league"], r["away"], r["home"]))
                flipped = m is not None
            if not m:
                continue
            hg, ag = (m["away_goals"], m["home_goals"]) if flipped else \
                     (m["home_goals"], m["away_goals"])
            outcome = "home" if hg > ag else "away" if ag > hg else "draw"
            r["status"] = "graded"
            r["graded_at"] = now
            r["score"] = f"{hg}-{ag}"
            r["outcome"] = outcome
            r["outcome_hit"] = outcome == r["pred_outcome"]
            r["score_hit"] = r["pred_score"] == r["score"]

            xg = xg_res.get(key)
            if not xg and flipped:
                pair = xg_res.get((r["league"], r["away"], r["home"]))
                xg = (pair[1], pair[0]) if pair else None
            if xg:
                r["real_xg"] = [round(xg[0], 2), round(xg[1], 2)]
                r["xg_hit"] = (abs(r["pred_xg"][0] - xg[0]) <= XG_TOL
                               and abs(r["pred_xg"][1] - xg[1]) <= XG_TOL)
            else:
                r["real_xg"] = None
                r["xg_hit"] = None
            r["perfect"] = bool(r["score_hit"] and r["xg_hit"])
            graded += 1
        if graded:
            cls._write(rows)
        return {"graded": graded, "still_pending": len(pending) - graded}

    # ------------------------------------------------ summary

    @classmethod
    def summary(cls) -> Dict[str, Any]:
        rows = cls._read()
        g = [r for r in rows if r["status"] == "graded"]
        xg_g = [r for r in g if r["xg_hit"] is not None]
        def rate(n, d):
            return round(n / d, 3) if d else None
        return {
            "recorded": len(rows), "graded": len(g),
            "outcome_hits": sum(r["outcome_hit"] for r in g),
            "outcome_rate": rate(sum(r["outcome_hit"] for r in g), len(g)),
            "score_hits": sum(r["score_hit"] for r in g),
            "score_rate": rate(sum(r["score_hit"] for r in g), len(g)),
            "xg_hits": sum(bool(r["xg_hit"]) for r in xg_g),
            "xg_rate": rate(sum(bool(r["xg_hit"]) for r in xg_g), len(xg_g)),
            "perfect": sum(r["perfect"] for r in g),
        }

    @classmethod
    def entries(cls) -> List[Dict[str, Any]]:
        return sorted(cls._read(), key=lambda r: (r["kickoff"] or "", r["league"]),
                      reverse=True)
