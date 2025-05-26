from typing import Any, Dict, List

import pandas as pd
from models.players import PlayerModel
from models.stats_type import StatsOptions
from models.team import TeamInitPayload, TeamModel
from services.ai.ai_service import AIService
from services.db.db_service import DBService
from services.rating.bestXI_service import BestXIService
from services.fbref.fbref_data_service import SoccerDataService
from services.rating.zones_service import ZoneService

class TeamDataService:

    @staticmethod
    def init_team(payload: TeamModel) -> TeamModel:
        
        sds = SoccerDataService(league=payload.league, season=payload.season)
        team_stats = sds.get_all_team_stats(team=payload.name, against=False)
        team_stats_against = sds.get_all_team_stats(team=payload.name, against=True)
        player_df = sds.get_all_player_stats(team=payload.name)
        players = [PlayerModel.from_df_row(row) for _, row in player_df.iterrows()]


        # intermediate model to pass into BestXIService
        intermediate_team_model = TeamModel(
            name=payload.name,
            slug=payload.slug,
            logo=payload.logo,
            league=payload.league,
            season=payload.season,
            stats=team_stats,
            stats_against=team_stats_against,
            players=players,
            best_11=[],
        )

        players = AIService.complete_player_details(players)
        DBService.save_team(intermediate_team_model) 
        
        # return intermediate_team_model
        best_11, formation = BestXIService().run(intermediate_team_model)
        def is_empty_or_zero(stat_blocks: list[dict]) -> bool:
            flat = {}
            for block in stat_blocks:
                for row in block.get("rows", []):
                    if isinstance(row.get("val"), (int, float)):
                        flat[row["label"]] = row["val"]
            return all(v == 0 for v in flat.values()) or len(flat) == 0
        
        if is_empty_or_zero(team_stats) and is_empty_or_zero(team_stats_against):
            print("[ZoneGuard] Skipping zone computation: all stats zero")
            zones = {}
        else:
            zones = ZoneService(sds).compute_all_zones(players, team_stats, team_stats_against)
        
        return TeamModel(
            name=payload.name,
            slug=payload.slug,
            logo=payload.logo,
            league=payload.league,
            season=payload.season,
            stats=team_stats,
            stats_against=team_stats_against,
            players=players,
            best_11=best_11,
            formation=formation,
            zones=zones
        )
