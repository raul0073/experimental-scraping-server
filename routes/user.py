from fastapi import APIRouter, Body, HTTPException
from models.users.user import PlayerConfigModel, UserZonesConfigInit, UserPlayerConfig
from services.db.user_config_service import UserConfigService

router = APIRouter()


@router.get("/config")
def get_user_config(user_id: str):
    return UserConfigService(user_id).load()


@router.post("/zones-config")
def save_user_config(payload: UserZonesConfigInit = Body(...)):
    if not payload.user_id:
        raise HTTPException(400, detail="Missing user_id")

    service = UserConfigService(payload.user_id)
    service.update_zone_config(
        zone_config=payload.zones_config.zone_config,
        zone_scalers=payload.zones_config.zone_scalers,
        zone_players=payload.zones_config.zone_players,
    )

    return {"status": "ok"}


@router.post("/players-config")
def save_player_config(payload: UserPlayerConfig = Body(...)):

    if not payload.user_id:
        raise HTTPException(400, detail="Missing user_id")
    service = UserConfigService(payload.user_id)
    service.savePlayerConfig(payload.players_config)
    
    return {"status": "ok"}

