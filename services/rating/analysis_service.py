import logging
from models.team import TeamModel
from models.zones.zones_config import ZONE_CONFIG, ZONE_SCALERS
from services.db.db_service import DBService
from services.rating.bestXI_service import BestXIService
from services.rating.zones_service import ZoneService


class TeamAnalysisService:
    @staticmethod
    def analyze(team: TeamModel, user_config: dict) -> TeamModel:
        zone_config = user_config.get("zone_config", {})
        zone_scalers   = user_config.get("zone_scalers", {})

        best_11, formation = BestXIService().run(team)

        zone_service = ZoneService(data_service=None)
        zones = zone_service.compute_all_zones(
            players=team.players,
            team_stats=team.stats,
            team_stats_against=team.stats_against,
            zone_config=zone_config,
            zone_scalers=zone_scalers,
        )
        
        updated_team = team.model_copy(update={
            "best_11": best_11,
            "formation": formation,
            "zones": zones
        })

        updated = DBService.update_team(updated_team)
        logging.info(updated)
        return updated_team