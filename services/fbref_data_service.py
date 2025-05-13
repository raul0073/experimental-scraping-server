import logging
from typing import Any, Dict, List
from fastapi import HTTPException
import numpy as np
import pandas as pd
from soccerdata import FBref
from models.labels.labels import LABELS_CONFIG
from models.stats_type import StatsOptions, TeamStatBlock, TeamStatsToFetchInit
from services.utils import SoccerDataUtils


class SoccerDataService:
    def __init__(self, league: str, season: str):
        """Initialize with dynamic league and season"""
        self.league = league
        self.season = season
        self.fbref = FBref(leagues=self.league, seasons=self.season)
        logging.info(
            f"SoccerDataService initialized with: {self.league} / {self.season}"
        )

    def get_team_stats(
        self, team: str, stats_type: StatsOptions, against: bool
    ) -> List[Dict[str, Any]]:
        """Fetch and process team stats."""
        try:
            if not team or not stats_type:
                raise ValueError("Team name and stats type are required.")

            # Fetch the team stats from FBref as DataFrame
            teams_data = self.fbref.read_team_season_stats(
                stat_type=stats_type, opponent_stats=against
            )

            if teams_data.empty:
                raise ValueError(
                    f"No data found for {team} with stats type: {stats_type}."
                )

            # Flatten multi-index columns if necessary
            teams_data = teams_data.reset_index()
            teams_data = SoccerDataUtils.flatten_columns(teams_data)

            # Add rankings for the entire dataset first
            teams_data = SoccerDataUtils.add_rankings(teams_data)

            # Now filter for the specified team
            teams_data["team"] = teams_data["team"].astype(str).str.strip()

            team_data = teams_data[
                teams_data["team"].str.lower() == team.lower().strip()
            ]
            if stats_type in LABELS_CONFIG:
                team_data = SoccerDataUtils.rename_columns(
                    team_data, LABELS_CONFIG[stats_type]
                )

            if team_data.empty:
                raise ValueError(f"No stats found for team '{team}'.")

            # Return the formatted team stats for UI display
            return SoccerDataUtils.format_team_stats_for_display(team_data)

        except ValueError as ve:
            logging.error(f"Value error: {ve}")
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            logging.error(f"Error fetching {team} stats: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error fetching {team} stats: {str(e)}"
            )

    def get_player_stats_df(
        self, team: str, stats_type: str, player_name: str
    ) -> List[Dict[str, Any]]:
        """Fetch and process player stats."""
        try:
            if not team or not stats_type or not player_name:
                raise ValueError("Team, stats_type, and player_name are all required.")

            # Fetch player stats from FBref as DataFrame
            df = self.fbref.read_player_season_stats(stat_type=stats_type)
            if df.empty:
                raise ValueError(f"No data found for stats type '{stats_type}'.")
            df = df.copy()
            df = df.reset_index()
            df = SoccerDataUtils.flatten_columns(df)

            # Clean up and filter data
            df["player"] = df["player"].astype(str).str.strip()
            df["team"] = df["team"].astype(str).str.strip()

            # Convert numeric columns to appropriate types (if needed)
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

            # Replace NaN values in numeric columns with 0 (or other values as needed)
            df[numeric_cols] = df[numeric_cols].fillna(0)

            # Handle string columns (replace NaN with empty string if needed)
            string_cols = df.select_dtypes(include=[object, "string"]).columns
            df[string_cols] = df[string_cols].fillna("")
            # Filter by team
            team_df = df[df["team"].str.lower() == team.lower().strip()]
            if team_df.empty:
                raise ValueError(
                    f"No stats found for player '{player_name}' in team '{team}'."
                )

            # Rename columns if the stats_type is valid
            if stats_type in LABELS_CONFIG:
                team_df = SoccerDataUtils.rename_columns(
                    team_df, LABELS_CONFIG[stats_type]
                )
            else:
                raise ValueError(f"Unsupported stats_type '{stats_type}'.")

            # Add rankings to all player stats
            team_df = SoccerDataUtils.add_rankings(team_df)

            # Filter for the specific player
            player_df = team_df[
                team_df["player"]
                .str.lower()
                .str.contains(player_name.lower().strip(), na=False)
            ]
            if player_df.empty:
                raise ValueError(
                    f"No stats found for player '{player_name}' in team '{team}'."
                )

            # Format the stats for display and return as a list of dictionaries
            return SoccerDataUtils.format_player_stats_for_display(player_df)

        except Exception as e:
            raise RuntimeError(f"Error retrieving player stats: {e}")

    def get_all_player_stats(self, team: str) -> pd.DataFrame:
        """Fetch and merge all relevant player stats for a given team."""
        try:
            all_dfs = []

            for stat_type in StatsOptions:
                df = self.fbref.read_player_season_stats(stat_type=stat_type.value)

                if df.empty:
                    continue
                df = df.copy()
                df = df.reset_index()
                df = SoccerDataUtils.flatten_columns(df)

                df["player"] = df["player"].astype(str).str.strip()
                df["team"] = df["team"].astype(str).str.strip()

                team_df = df[df["team"].str.lower() == team.lower().strip()]
                if team_df.empty:
                    continue

                # Add rankings
                team_df = SoccerDataUtils.add_rankings(team_df)

                # Rename columns if LABELS exist
                if stat_type.value in LABELS_CONFIG:
                    team_df = SoccerDataUtils.rename_columns(
                        team_df, LABELS_CONFIG[stat_type.value]
                    )

                # Prefix stat type columns to avoid conflicts
                team_df = SoccerDataUtils.prefix_stat_columns(team_df, stat_type.value)

                all_dfs.append(team_df)

            if not all_dfs:
                raise ValueError(f"No player stats found for team '{team}'.")

            # Merge all stat type DataFrames on 'player' and 'team'
            merged_df = all_dfs[0]
            for df in all_dfs[1:]:
                merged_df = pd.merge(merged_df, df, on=["player", "team"], how="outer")

            # Clean merged_df
            for col in merged_df.columns:
                if pd.api.types.is_numeric_dtype(merged_df[col]):
                    merged_df[col] = (
                        merged_df[col].replace([np.inf, -np.inf], np.nan).fillna(0)
                    )
                elif pd.api.types.is_string_dtype(merged_df[col]):
                    merged_df[col] = merged_df[col].fillna("")

            merged_df = merged_df[merged_df["playing_time_Minutes Played"] >= 180]
            return merged_df

        except Exception as e:
            raise RuntimeError(f"Failed to get all player stats: {str(e)}")

    def get_team_stats_by_type(
        self, team: str, stats_type: TeamStatsToFetchInit, against: bool
    ) -> List[Dict[str, Any]]:
        """Fetch & format ONE team‐stats table for a single StatsOptions."""
        if not team or not stats_type:
            raise ValueError("Team name and stats type are required.")

        df = self.fbref.read_team_season_stats(
            stat_type=stats_type, opponent_stats=against
        )
        print(f"df against: {against}: {df.head()}")
        if df.empty:
            raise ValueError(f"No data found for {team} with stats type: {stats_type}.")
        
        df = df.copy()
        df = df.reset_index()
        df = SoccerDataUtils.flatten_columns(df)
        df = SoccerDataUtils.add_rankings(df)

        # filter to our team
        df["team"] = df["team"].astype(str).str.strip()
        if against:
            df["team"] = df["team"].str.replace(r"^vs\s+", "", regex=True)

        team_df = df[df["team"].str.lower() == team.lower().strip()]

        if stats_type.value in LABELS_CONFIG:
            team_df = SoccerDataUtils.rename_columns(
                team_df, LABELS_CONFIG[stats_type.value]
            )

        if team_df.empty:
            raise ValueError(f"No stats found for team '{team}' ({stats_type}).")

        return SoccerDataUtils.format_team_stats_for_display(team_df)

    def get_all_team_stats(
        self, team: str, against: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of { stat_type, rows } for every StatsOptions.
        """
        result: List[Dict[str, Any]] = []
        errors: Dict[str, str] = {}

        for opt in TeamStatsToFetchInit:
            try:
                rows = self.get_team_stats_by_type(team, opt, against)

                # 🔧 fix nested list issue
                if len(rows) == 1 and isinstance(rows[0], list):
                    rows = rows[0]

                result.append({"stat_type": opt.value, "rows": rows})
            except Exception as e:
                logging.warning(f"[get_all_team_stats] {opt.value} failed: {e}")
                errors[opt.value] = str(e)

        if not result:
            detail = "; ".join(f"{k}: {v}" for k, v in errors.items())
            raise HTTPException(
                status_code=500,
                detail=f"No team stats could be fetched. Errors: {detail}"
            )
        
        # result = SoccerDataService.convert_team_stats_to_dict_format(result)
        return result

    def get_all_team_stat_types(self) -> List[str]:
        """
        Return every StatsOptions.value so the caller can know which
        tables exist (e.g. "standard", "passing", "keeper_adv", etc.).
        """
        return [opt.value for opt in StatsOptions]
    

    def convert_team_stats_to_dict_format(stats: List[TeamStatBlock]) -> Dict[str, List[Dict[str, Any]]]:
        return {block.stat_type: block.rows for block in stats}