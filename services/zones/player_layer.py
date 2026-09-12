from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

DATA_DIR = Path("data/understat")
MIN_MINUTES = 450

# how much a position letter contributes to each band's player pool
BAND_POSITION_WEIGHTS = {
    "att": {"F": 1.0, "M": 0.35},
    "mid": {"M": 1.0, "F": 0.25, "D": 0.25},
}


class PlayerLayer:
    """Per-team player-quality scores for the attack and midfield bands,
    from Understat player season stats (the reproducible post-Opta source).

    att quality = minutes-weighted (npxG/90 + xA/90) of forwards (+ some mid)
    mid quality = minutes-weighted xGChain/90 (build-up involvement)
    Defense has no meaningful player metric in this source — the def band
    stays team-signal only.
    """

    @staticmethod
    def team_band_scores(league: str, season: str) -> Optional[Dict[str, Dict[str, float]]]:
        path = DATA_DIR / league / "players" / f"{season}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))

        teams: Dict[str, Dict[str, list]] = {}
        for p in data["players"]:
            minutes = p.get("minutes") or 0
            if minutes < MIN_MINUTES:
                continue
            pos = str(p.get("position") or "")
            letters = {c for c in ("F", "M", "D") if c in pos} or ({"GK"} if "GK" in pos else set())
            if not letters:
                continue
            n90 = minutes / 90.0
            att_q = ((p.get("npxg") or 0) + (p.get("xa") or 0)) / n90
            mid_q = (p.get("xg_chain") or 0) / n90
            rec = teams.setdefault(p["team"], {"att": [], "mid": []})
            for band, weights in BAND_POSITION_WEIGHTS.items():
                w_pos = max((weights.get(c, 0.0) for c in letters), default=0.0)
                if w_pos > 0:
                    q = att_q if band == "att" else mid_q
                    rec[band].append((q, minutes * w_pos))

        out: Dict[str, Dict[str, float]] = {}
        for team, bands in teams.items():
            out[team] = {}
            for band, rows in bands.items():
                w_total = sum(w for _, w in rows)
                out[team][band] = (sum(q * w for q, w in rows) / w_total) if w_total else 0.0
        return out

    @staticmethod
    def latest_for(league: str, seasons: list[str]) -> Optional[Dict[str, Dict[str, float]]]:
        """First season (in given order) with player data on disk."""
        for season in seasons:
            scores = PlayerLayer.team_band_scores(league, season)
            if scores:
                return scores
        return None
