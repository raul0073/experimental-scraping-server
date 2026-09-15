from __future__ import annotations
import json
import logging
import unicodedata
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name

log = logging.getLogger(__name__)

DATA_DIR = Path("data/fbref_players")

# the fbref player tables that SURVIVED the Opta licence loss (verified at
# value level 2026-09-15 after the user challenged the "all dead" claim:
# misc/shooting/keeper are 100% populated for 25/26 AND 26/27; the advanced
# tables — passing, possession, defense detail, GCA — remain stripped)
_MISC = {"crdy": ("Performance", "CrdY"), "crdr": ("Performance", "CrdR"),
         "fls": ("Performance", "Fls"), "fld": ("Performance", "Fld"),
         "off": ("Performance", "Off"), "crs": ("Performance", "Crs"),
         "int": ("Performance", "Int"), "tklw": ("Performance", "TklW"),
         "og": ("Performance", "OG")}
_SHOOT = {"gls": ("Standard", "Gls"), "sh": ("Standard", "Sh"),
          "sot": ("Standard", "SoT")}
_KEEP = {"ga": ("Performance", "GA"), "sota": ("Performance", "SoTA"),
         "saves": ("Performance", "Saves"), "save_pct": ("Performance", "Save%"),
         "cs": ("Performance", "CS")}


def norm_name(name: str) -> str:
    """Accent-stripped lowercase key for fbref<->understat player joins."""
    s = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


class FbrefPlayerStatsService:
    """Season-aggregate per-player counting stats from fbref's surviving
    tables. Rate metrics only (per 90 via the 90s column) — per-match
    texture still comes from Understat."""

    def __init__(self, league: str, season: str):
        self.league = league
        self.season = season

    def build(self) -> Dict[str, Any]:
        import soccerdata as sd
        warnings.filterwarnings("ignore")
        fb = sd.FBref(leagues=[self.league], seasons=[self.season])
        players: Dict[str, Dict[str, Any]] = {}

        def rows_of(df):
            df = df.reset_index()
            for _, r in df.iterrows():
                yield r

        def numf(r, col):
            try:
                v = r.get(col)
                v = v.iloc[0] if hasattr(v, "iloc") else v
                return float(v) if v == v and v is not None else 0.0
            except (TypeError, ValueError, KeyError):
                return 0.0

        for stat_type, fields in (("misc", _MISC), ("shooting", _SHOOT),
                                  ("keeper", _KEEP)):
            try:
                df = fb.read_player_season_stats(stat_type=stat_type)
            except Exception as e:
                log.warning("%s %s %s failed: %s", self.league, self.season,
                            stat_type, e)
                continue
            for r in rows_of(df):
                name = str(r.get(("player", "")) if ("player", "") in r.index
                           else r.get("player", "")).strip()
                team = str(r.get(("team", "")) if ("team", "") in r.index
                           else r.get("team", "")).strip()
                if not name or name == "nan":
                    continue
                p = players.setdefault(name, {"team": team, "n90s": 0.0})
                p["team"] = team
                n90 = 0.0
                for cand in (("Playing Time", "90s"), ("90s", "")):
                    n90 = max(n90, numf(r, cand))
                if n90:
                    p["n90s"] = max(p["n90s"], n90)
                for key, col in fields.items():
                    p[key] = numf(r, col)

        payload = {"league": self.league, "season": self.season,
                   "player_count": len(players), "players": players}
        _atomic_write_json(self.out_path(self.league, self.season), payload)
        return {"ok": True, "league": self.league, "season": self.season,
                "players": len(players)}

    @staticmethod
    def out_path(league: str, season: str) -> Path:
        return DATA_DIR / _safe_name(league) / f"{season}.json"

    @classmethod
    def load(cls, league: str, season: str) -> Optional[Dict[str, Any]]:
        p = cls.out_path(league, season)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
