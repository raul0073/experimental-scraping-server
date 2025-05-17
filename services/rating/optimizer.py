# ai/optimizer/ai_zone_optimizer.py
import time
import logging
from models.zones.zones_config import ZonesConfig
from services.db.db_service import DBService
from services.db.user_config_service import UserConfigService
from services.rating.bestXI_service import BestXIService
from services.rating.zones_service import ZoneService
from services.ai.ai_service import AIService

# Configure logging once
time.sleep(0)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigOptimizer:
    @staticmethod
    def run_ai_zone_config_nightly(
        team_delay: float = 3.0,
        post_aggregation_delay: float = 5.0
    ) -> None:
        """
        Nightly AI Zone Config Optimizer:
        1. Aggregate all teams' stored stats and players from DB.
        2. Flatten stats and invoke AI to optimize 'zone_scalers'.
        3. Persist updated 'ai_default' ZonesConfig.
        4. Recompute and save each team's best XI, formation, and zones with the new config.
        """
        logger.info("Starting nightly AI zone config optimization (aggregate-first)")

        # Step 0: load current default config
        raw_conf = UserConfigService.get_config("ai_default")
        try:
            current_config = (
                ZonesConfig.model_validate(raw_conf)
                if isinstance(raw_conf, dict) else raw_conf
            )
        except Exception as e:
            logger.error(f"Failed to parse ai_default config: {e}")
            return

        zone_cfg = current_config.zone_config
        zone_plr = current_config.zone_players

        # Step 1: collect stats and players from DB
        teams = DBService.get_all_teams()
        all_stats = []
        all_stats_against = []
        all_players = []
        total = len(teams)

        for idx, team in enumerate(teams, start=1):
            logger.info(f"[Collect {idx}/{total}] Team: {team.name}")
            try:
                all_stats.extend(team.stats)
                all_stats_against.extend(team.stats_against)
                all_players.extend(team.players)
            except Exception as e:
                logger.exception(f"Error collecting data for {team.name}: {e}")
            time.sleep(team_delay)

        # Step 2: optimize zone scalers via AI
        logger.info("Flattening stats and requesting AI scaler optimization...")
        time.sleep(post_aggregation_delay)
        flat_stats = AIService.flatten_stats(all_stats)
        flat_stats_against = AIService.flatten_stats(all_stats_against)

        try:
            new_scalers = AIService.optimize_zone_scalers(
                zone_config=zone_cfg,
                all_team_stats=flat_stats,
                all_team_stats_against=flat_stats_against,
                all_players=all_players,
            )
        except Exception:
            logger.exception("AI scaler optimization failed")
            return

        # Step 3: save updated ai_default config
        updated_config = ZonesConfig(
            zone_config=zone_cfg,
            zone_scalers=new_scalers,
            zone_players=zone_plr,
        )
        serializable_zone_config = {
        zid: (
        zcfg.model_dump()
        if hasattr(zcfg, "model_dump")
        else zcfg
        )
            for zid, zcfg in updated_config.zone_config.items()
        }
        UserConfigService.save(
            
            "ai_default",
            serializable_zone_config,
            updated_config.zone_scalers,
            updated_config.zone_players,
            optimizer=True
        )
        logger.info("ai_default config updated successfully")

        # Step 4: recompute teams with new config
        for idx, team in enumerate(teams, start=1):
            logger.info(f"[Recompute {idx}/{total}] Team: {team.name}")
            try:
                ts = team.stats
                tas = team.stats_against
                best11, form = BestXIService().run(team)
                for idx, team in enumerate(teams, start=1):
                    logger.info(f"[Recompute {idx}/{total}] Team: {team.name}")
                    raw_zone_cfg = {
                    zid: (zcfg.model_dump() if hasattr(zcfg, "model_dump") else zcfg)
                    for zid, zcfg in updated_config.zone_config.items()
                }
                zones = ZoneService(None).compute_all_zones(
                players=team.players,
                team_stats=team.stats,
                team_stats_against=team.stats_against,
                zone_config=raw_zone_cfg,
                zone_scalers=updated_config.zone_scalers,
            )
                updated_team = team.model_copy(
                    update={"best_11": best11, "formation": form, "zones": zones}
                )
                DBService.save_team(updated_team)
            except Exception as e:
                logger.exception(f"Error recomputing {team.name}: {e}")
            time.sleep(team_delay)

        logger.info("Nightly AI zone config optimization complete")
