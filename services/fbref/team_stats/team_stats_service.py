from __future__ import annotations
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from soccerdata import FBref

from services.fbref.league.fbref_utils import _atomic_write_json, _safe_name, _sanitize_value

log = logging.getLogger(__name__)

DATA_DIR = Path("data/team_stats")

# tables soccerdata 1.9.x still reads natively
TEAM_STAT_TYPES = ["standard", "keeper", "shooting", "playing_time", "misc"]

# tables fbref still publishes but soccerdata dropped — we fetch + parse these
# ourselves (fbref kept the raw action data after losing its xG provider;
# only the modeled metrics — xG/npxG/xAG/progressive — are truly gone).
ADVANCED_STAT_PAGES = {
    "defense": "defense",
    "possession": "possession",
    "passing": "passing",
    "passing_types": "passing_types",
    "goal_shot_creation": "gca",
    "keeper_adv": "keepersadv",
}
_TABLE_ID = {"goal_shot_creation": "gca"}  # page table ids that differ from our key

FBREF_COMPS = {
    "ENG-Premier League": (9, "Premier-League"),
    "ESP-La Liga": (12, "La-Liga"),
    "ITA-Serie A": (11, "Serie-A"),
    "GER-Bundesliga": (20, "Bundesliga"),
    "FRA-Ligue 1": (13, "Ligue-1"),
}


class TeamStatsService:
    """Season-aggregate team stats, for + against, snapshot-archived.

    Every build writes data/team_stats/{league}/{season}/{YYYY-MM-DD}.json and
    never overwrites older snapshots — over a live season this accumulates the
    true walk-forward history that fbref itself can't provide retroactively.
    `latest.json` is a convenience copy of the newest snapshot.
    """

    def __init__(self, league: str, season: str, refresh: bool = False):
        self.league = league
        self.season = season
        self.refresh = refresh
        self.fbref = FBref(leagues=[league], seasons=[season], no_cache=refresh)

    def build(self, snapshot_date: Optional[str] = None) -> Dict[str, Any]:
        snapshot_date = snapshot_date or date.today().isoformat()
        teams: Dict[str, Dict[str, Any]] = {}

        for stat_type in TEAM_STAT_TYPES:
            for against in (False, True):
                try:
                    df = self.fbref.read_team_season_stats(stat_type=stat_type, opponent_stats=against)
                except Exception as e:
                    log.warning("%s %s stat=%s against=%s failed: %s",
                                self.league, self.season, stat_type, against, e)
                    continue
                if df is None or df.empty:
                    continue
                df = df.reset_index()
                df = _flatten_columns(df)
                self._merge_rows(teams, df, stat_type, against, team_col="team")

        for stat_type in ADVANCED_STAT_PAGES:
            try:
                for against, df in self._read_advanced_tables(stat_type):
                    self._merge_rows(teams, df, stat_type, against, team_col="Squad")
            except Exception as e:
                log.warning("%s %s advanced stat=%s failed: %s",
                            self.league, self.season, stat_type, e)

        if not teams:
            raise RuntimeError(f"No team stats scraped for {self.league} {self.season}")

        payload = {
            "league": self.league,
            "season": self.season,
            "snapshot_date": snapshot_date,
            "team_count": len(teams),
            "stat_types": TEAM_STAT_TYPES + list(ADVANCED_STAT_PAGES),
            "teams": sorted(teams.values(), key=lambda t: t["team"]),
        }
        out_dir = DATA_DIR / _safe_name(self.league) / self.season
        _atomic_write_json(out_dir / f"{snapshot_date}.json", payload)
        _atomic_write_json(out_dir / "latest.json", payload)
        log.info("Saved %d teams x %d stat types (for+against) -> %s",
                 len(teams), len(TEAM_STAT_TYPES), out_dir / f"{snapshot_date}.json")
        return {
            "ok": True,
            "league": self.league,
            "season": self.season,
            "snapshot_date": snapshot_date,
            "team_count": len(teams),
        }

    # ---------- advanced tables (custom parser) ----------

    def _merge_rows(self, teams: Dict[str, Dict[str, Any]], df: pd.DataFrame,
                    stat_type: str, against: bool, team_col: str) -> None:
        for _, row in df.iterrows():
            team = str(row.get(team_col, "")).strip()
            # fbref labels opponent rows "vs <team>"
            team = team.removeprefix("vs ").strip()
            if not team or team.lower() == "nan":
                continue
            rec = teams.setdefault(team, {"team": team, "stats": {}, "against": {}})
            bucket = "against" if against else "stats"
            # fbref stripped advanced values retroactively (all seasons) but kept
            # the column skeletons — store only cells that actually hold data,
            # so if fbref ever repopulates, these buckets fill automatically.
            values = {
                str(k): _sanitize_value(v)
                for k, v in row.items()
                if str(k) not in ("league", "season", "team", "url", team_col, "# Pl")
            }
            # v == v filters float('nan') (nan != nan), which survives _sanitize_value
            values = {k: v for k, v in values.items() if v is not None and v == v}
            if values:
                rec[bucket][stat_type] = values

    def _read_advanced_tables(self, stat_type: str):
        """Fetch an fbref stats page soccerdata no longer parses and yield
        (against, squad_df) for the for/against squad tables on it."""
        import io

        comp_id, comp_slug = FBREF_COMPS[self.league]
        season_str = f"20{self.season[:2]}-20{self.season[2:]}"
        page = ADVANCED_STAT_PAGES[stat_type]
        url = (f"https://fbref.com/en/comps/{comp_id}/{season_str}/{page}/"
               f"{season_str}-{comp_slug}-Stats")
        filepath = self.fbref.data_dir / f"adv_{page}_{_safe_name(self.league)}_{self.season}.html"
        reader = self.fbref.get(url, filepath, no_cache=self.refresh)
        html = reader.read()
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="ignore")
        # fbref hides secondary tables inside HTML comments
        html = html.replace("<!--", "").replace("-->", "")

        table_id = _TABLE_ID.get(stat_type, stat_type)
        for against in (False, True):
            suffix = "against" if against else "for"
            try:
                dfs = pd.read_html(io.StringIO(html), attrs={"id": f"stats_squads_{table_id}_{suffix}"})
            except ValueError:
                log.warning("table stats_squads_%s_%s missing on %s", table_id, suffix, url)
                continue
            if not dfs:
                continue
            yield against, _flatten_columns(dfs[0])

    # ---------- disk access ----------

    @staticmethod
    def load_latest(league: str, season: str) -> Optional[Dict[str, Any]]:
        path = DATA_DIR / _safe_name(league) / season / "latest.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def snapshots(league: str, season: str) -> List[str]:
        base = DATA_DIR / _safe_name(league) / season
        if not base.exists():
            return []
        return sorted(p.stem for p in base.glob("*.json") if p.stem != "latest")


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            " - ".join(str(p).strip() for p in col if p and "Unnamed" not in str(p))
            for col in df.columns
        ]
    else:
        df.columns = [str(c) for c in df.columns]
    return df
