from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, List, Optional

from models.stats_aware.stats_aware import SCORE_CONFIG


class UserConfigModel(BaseModel):
    zone_config: Optional[Dict[str, dict]] = Field(default_factory=dict)
    zone_scalers: Optional[Dict[str, Dict[str, float]]] = Field(default_factory=dict)
    zone_players: Optional[Dict[str, List[str]]] = Field(default_factory=dict)


class ScoreWeightsModel(BaseModel):
    pros: float = 1.0
    cons: float = -1.0
    important: float = 2.0


class PlayerConfigModel(BaseModel):
    score_config: Dict[str, Dict[str, Dict[str, List[str]]]]
    score_weights: ScoreWeightsModel = Field(default_factory=ScoreWeightsModel)


class UserModel(BaseModel):
    id: str = Field(alias="_id")
    zones_config: UserConfigModel
    players_config: PlayerConfigModel = Field(default_factory=PlayerConfigModel)
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class UserModelInit(BaseModel):
    user_id: str
    zones_config: UserConfigModel

class UserPlayerConfig(BaseModel):
    user_id: str
    players_config:PlayerConfigModel
    
class UserAnalyzeTeam(BaseModel):
    user_id: str
    team_name: str
