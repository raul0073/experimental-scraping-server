from datetime import datetime
from typing import List, Optional
from core.db import mongo_collection
from models.team import TeamModel

class DBService:
    TEAM_COLLECTION = "teams"

    @classmethod
    def save_team(cls, team: TeamModel) -> str:
        with mongo_collection(cls.TEAM_COLLECTION) as col:
            data = team.model_dump()
            data["_id"] = team.name  
            col.replace_one({"_id": team.name}, data, upsert=True)
            return team.name
        
    @staticmethod
    def update_team(team: TeamModel) -> str:
        with mongo_collection("teams") as col:
            col.update_one(
                {"name": team.name},
                {"$set": team.model_dump()},
                upsert=True
            )
            return team.name
        
    @classmethod
    def get_team_by_name(cls, name: str) -> TeamModel | None:
        with mongo_collection(cls.TEAM_COLLECTION) as col:
            doc = col.find_one({"_id": name})
            if doc:
                return TeamModel(**doc)
            return None

    @classmethod
    def get_team_by_slug(cls, slug: str) -> Optional[TeamModel]:
        with mongo_collection(cls.TEAM_COLLECTION) as col:
            data = col.find_one({"slug": slug})
            if data:
                return TeamModel(**data)
            return None
        
    @classmethod
    def get_all_teams(cls) -> List[TeamModel]:
        with mongo_collection(cls.TEAM_COLLECTION) as col:
            return [TeamModel(**doc) for doc in col.find()]