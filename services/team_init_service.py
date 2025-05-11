from typing import Any, Dict, List

import pandas as pd
from models.players import PlayerModel
from models.stats_type import StatsOptions
from models.team import TeamInitPayload, TeamModel
from services.ai_service import AIService
from services.bestXI_service import BestXIService
from services.fbref_data_service import SoccerDataService
from services.zones_service import ZoneService

class TeamDataService:

    @staticmethod
    def init_team(payload: TeamModel) -> TeamModel:
        sds = SoccerDataService(league=payload.league, season=payload.season)
        
        team_stats = sds.get_team_stats(team=payload.name, stats_type=StatsOptions.STANDARD, against=False)
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
            players=players,
            best_11=[],
        )

        # BestXIService
        best_11, formation = BestXIService().run(intermediate_team_model)
            
        players = AIService.complete_player_details(players)
        
        zones = ZoneService().compute_all_zones(players, team_stats)

        return TeamModel(
            name=payload.name,
            slug=payload.slug,
            logo=payload.logo,
            league=payload.league,
            season=payload.season,
            stats=team_stats,
            players=players,
            best_11=best_11,
            formation=formation,
            zones=zones
        )
