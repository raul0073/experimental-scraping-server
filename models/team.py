from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from models.players import PlayerModel
from models.zones.zones_config import ZoneData

class TeamInitPayload(BaseModel):
    name: str
    slug: str
    logo: str | None = None
    league: str
    season: str
    
    
class TeamModel(BaseModel):
    name: str
    league: str
    season: str
    slug: str
    logo: Optional[str]
    formation: Optional[str] = ""
    stats: List[List[Dict[str, Any]]] 
    players: List[PlayerModel]
    best_11: List[PlayerModel]
    zones: Optional[Dict[str, ZoneData]] = None