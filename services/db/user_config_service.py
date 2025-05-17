from datetime import datetime
from typing import Dict, List, Optional
from core.db import mongo_collection
from models.users.user import PlayerConfigModel, UserConfigModel, UserModel
from models.zones.zones_config import ZONE_CONFIG, ZONE_SCALERS, ZonesConfig


class UserConfigService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def load(self) -> dict:
        with mongo_collection("users") as col:
            user = col.find_one({"_id": self.user_id})
            if not user:
                return {}
            return user

    def save(
        self,
        zone_config: Optional[Dict[str, dict]],
        zone_scalers: Optional[Dict[str, float]],
        zone_players: Optional[Dict[str, List[str]]],
        optimizer: Optional[bool] = False
    ) -> None:
        config = UserConfigModel(
            zone_config=zone_config or {},
            zone_scalers=zone_scalers or {},
            zone_players=zone_players or {}
        )
        if optimizer:
            user_id = "ai_default" 
        else:
            user_id = self.user_id
            
        now = datetime.now()
        user = UserModel(
            _id=user_id,
            zones_config=config,
            created_at=now,
            updated_at=now
        )

        with mongo_collection("users") as col:
            col.update_one({"_id": user_id}, {"$set": user.model_dump(by_alias=True)}, upsert=True)


    @staticmethod
    def get_user_config(user_id: str) -> dict:
        """Return user's zone config + scalers or default if not found"""
        with mongo_collection("users") as col:
            doc = col.find_one({"_id": user_id})
            return doc.get("zones_config", {}) if doc else {
                "zone_config": ZONE_CONFIG,
                "zone_scalers": ZONE_SCALERS,
            }
            
    @staticmethod
    def get_config(key: str) -> ZonesConfig:
        with mongo_collection("users") as col:
            doc = col.find_one({"_id": key})
            if not doc or "zones_config" not in doc:
                return ZonesConfig()  # default empty
        # zones_config is stored under that field
        return ZonesConfig.model_validate(doc["zones_config"])
    
    
    def savePlayerConfig(self, player_cfg: PlayerConfigModel) -> None:
        now = datetime.now()
        with mongo_collection("users") as col:
            col.update_one(
                {"_id": self.user_id},
                {
                    "$set": {
                        "players_config": player_cfg.model_dump(),
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                    upsert=True,
            )