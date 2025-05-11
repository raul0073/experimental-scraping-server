import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List

class SoccerDataUtils:

    @staticmethod
    def rename_columns(df: pd.DataFrame, label_map: Dict[str, str]) -> pd.DataFrame:
        """
        Renames both base and _rank columns using the label_map.
        """
        new_cols = {}
        for col in df.columns:
            if col.endswith("_rank"):
                base = col[:-5]
                if base in label_map:
                    new_cols[col] = f"{label_map[base]}_rank"
                else:
                    new_cols[col] = col
            else:
                new_cols[col] = label_map.get(col, col)

        return df.rename(columns=new_cols)

    @staticmethod
    def add_rankings(df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds rankings for each numeric stat column based on performance.
        Skips identity or string columns like player, team, pos, etc.
        """
        identity_cols = {"player", "team", "pos", "nation", "born", "age", "league", "season", "url"}

        for stat_column in df.columns:
            if (
                stat_column.lower() in identity_cols
                or stat_column.endswith("_rank")
                or not pd.api.types.is_numeric_dtype(df[stat_column])
            ):
                continue
            try:
                df[stat_column] = df[stat_column].replace([np.inf, -np.inf], np.nan).fillna(0)
                df[f"{stat_column}_rank"] = df[stat_column].rank(method='min', ascending=False).astype(int)
            except Exception as e:
                logging.warning(f"Could not rank column '{stat_column}': {e}")

        return df

    @staticmethod
    def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        Flattens multi-index columns (if present) into single-level columns.
        """
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(col).strip('_') for col in df.columns.values]
        return df

    @staticmethod
    def format_player_stats_for_display(player_stats: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Converts a player stats DataFrame into a list of {label, val, rank} dicts for UI display.
        """
        result = []
        skip_keys = {"player", "team", "league", "season", "url", "born", "nation", "pos", "age"}

        for index, row in player_stats.iterrows():
            row_result = []
            for key, val in row.items():
                if key in skip_keys or key.endswith("_rank"):
                    continue
                rank_key = f"{key}_rank"
                rank_val = row.get(rank_key)
                row_result.append({
                    "label": key,
                    "val": val,
                    "rank": rank_val
                })
            result.append(row_result)

        return result

    @staticmethod
    def format_team_stats_for_display(team_stats: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Converts a team stats DataFrame into a list of {label, val, rank} dicts for UI display.
        """
        if isinstance(team_stats, list):
            if team_stats:
                team_stats = team_stats[0]  
            else:
                return []
            
            
        result = []
        skip_keys = {"team", "league", "season", "url"}

        for index, row in team_stats.iterrows():
            row_result = []
            for key, val in row.items():
                if key in skip_keys or key.endswith("_rank"):
                    continue
                rank_key = f"{key}_rank"
                rank_val = row.get(rank_key)
                row_result.append({
                    "label": key,
                    "val": val,
                    "rank": rank_val
                })
            result.append(row_result)

        return result

    @staticmethod
    def prefix_stat_columns(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        new_cols = {}
        for col in df.columns:
            if col not in ["player", "team"]:  # don't prefix cols
                new_cols[col] = f"{prefix}_{col}"
        return df.rename(columns=new_cols)