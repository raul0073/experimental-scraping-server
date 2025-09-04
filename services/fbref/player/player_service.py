from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from soccerdata import FBref

from models.fbref.fbref_types import IDENTITY_COLS, POSSIBLE_PLAYER_TABLES
from services.fbref.league.fbref_utils import (
    _atomic_write_json,
    _safe_name,
    _sanitize,
    _sanitize_value,
)

log = logging.getLogger(__name__)


class FBRefPlayerService:
    def __init__(self, league: str, season: str):
        self.league = league
        self.season = season
        self.fbref = FBref(leagues=[league], seasons=[season])
        self.base_dir = Path("data/players") / _safe_name(league)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        log.info("FBRefPlayerService initialized for %s / %s", league, season)

    def build_team_jsons(self):
        table_frames = self._load_all_stat_tables()
        teams = self._get_all_teams()

        saved = 0
        for team in teams:
            players = self._build_team_players(team, table_frames)
            self._merge_keeper_stats(players, table_frames, team)

            if not players:
                log.warning("No players for team: %s", team)
                continue

            team_data = {
                "league": self.league,
                "season": self.season,
                "team": team,
                "players": players,
            }

            out = self.base_dir / f"{_safe_name(team)}.json"
            _atomic_write_json(out, _sanitize(team_data))
            log.info("Saved %d players → %s", len(players), out)
            saved += 1

        return {"ok": True, "teams_written": saved}

    def _load_all_stat_tables(self) -> Dict[str, pd.DataFrame]:
        frames = {}
        for stat in POSSIBLE_PLAYER_TABLES:
            try:
                df = self.fbref.read_player_season_stats(stat_type=stat)
                if df is None or df.empty:
                    continue

                df = df.reset_index()
                df = self._flatten_columns(df)
                df = df.loc[:, ~df.columns.duplicated()]

                frames[stat] = df
                log.info("Loaded %s: shape=%s", stat, df.shape)
            except Exception as e:
                log.warning("Failed stat %s: %s", stat, e)
        return frames

    def _get_all_teams(self) -> List[str]:
        df = self.fbref.read_team_season_stats(stat_type="standard", opponent_stats=False)
        if df is None or df.empty:
            raise RuntimeError("No team data loaded from FBref.")

        if isinstance(df.index, pd.MultiIndex) and "team" in df.index.names:
            return sorted(df.index.get_level_values("team").unique().tolist())

        raise RuntimeError(f"Team index names: {df.index.names}; columns: {df.columns}")

    def _build_team_players(self, team: str, table_frames: Dict[str, pd.DataFrame]) -> List[Dict]:
        players: Dict[str, Dict] = {}

        for stat, df in table_frames.items():
            if stat in ("keeper", "keeper_adv"):
                continue  # handled separately

            team_col = "team" if "team" in df.columns else "squad"
            if team_col not in df.columns or "player" not in df.columns:
                log.warning(f"Skipping {stat} — missing team/player col")
                continue

            team_df = df[df[team_col].str.casefold() == team.casefold()]

            for _, row in team_df.iterrows():
                name_raw = row.get("player")
                name = (
                    name_raw.item()
                    if hasattr(name_raw, "item")
                    else str(name_raw).split("\n")[0].strip()
                )
                if not name:
                    continue

                rec = players.setdefault(
                    name,
                    {
                        "name": name,
                        "age": _sanitize_value(row.get("age")),
                        "position": row.get("pos"),
                        "stats": {},
                    },
                )

                rec["stats"][stat] = {
                    str(k): self._safe_json_value(v)
                    for k, v in row.items()
                    if k not in IDENTITY_COLS
                }

        return list(players.values())

    def _merge_keeper_stats(self, players: List[Dict], table_frames: Dict[str, pd.DataFrame], team: str):
        keeper_data = {}
        for stat in ("keeper", "keeper_adv"):
            df = table_frames.get(stat)
            if df is None or df.empty:
                continue

            df = self._flatten_columns(df)
            df = df[df.get("team", df.get("squad", "")).str.casefold() == team.casefold()]

            for _, row in df.iterrows():
                name_raw = row.get("player")
                name = (
                    name_raw.item()
                    if hasattr(name_raw, "item")
                    else str(name_raw).split("\n")[0].strip()
                )
                if not name:
                    continue

                keeper_data.setdefault(name, {})[stat] = {
                    str(k): self._safe_json_value(v)
                    for k, v in row.items()
                    if k not in IDENTITY_COLS
                }

        for player in players:
            pos = player.get("position")
            if pos is not None and isinstance(pos, str) and pos == "GK":
                pdata = keeper_data.get(player["name"])
                if pdata:
                    player["stats"].update(pdata)

    @staticmethod
    def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" - ".join(str(p).strip() for p in col if p) for col in df.columns]
        else:
            df.columns = [str(c) for c in df.columns]
        return df

    @staticmethod
    def _safe_json_value(v: Any) -> Any:
        return _sanitize_value(v)