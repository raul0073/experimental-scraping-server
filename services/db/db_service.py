from datetime import datetime
import logging
import time
from typing import List, Optional
from core.db import mongo_collection
from models.team import TeamModel

class DBService:
    TEAM_COLLECTION = "teams"
    BENCHMARK_COLLECTION = "benchmarks"
    
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
        start = time.perf_counter()
        with mongo_collection(cls.TEAM_COLLECTION) as col:
            logging.info("Querying MongoDB...")
            raw_docs = list(col.find())  # force evaluation
            logging.info(f"Mongo returned {len(raw_docs)} docs in {time.perf_counter() - start:.2f}s")

        start = time.perf_counter()
        teams = [TeamModel(**doc) for doc in raw_docs]
        logging.info(f"Pydantic parsing took {time.perf_counter() - start:.2f}s")

        return teams
    
    
    @classmethod
    def save_benchmarks(cls, benchmark_data: dict) -> None:
        with mongo_collection(cls.BENCHMARK_COLLECTION) as col:
            col.replace_one(
                {"_id": "player_benchmarks"},
                {"_id": "player_benchmarks", "data": benchmark_data},
                upsert=True
            )

    @classmethod
    def get_benchmarks(cls, pos: Optional[str] = None) -> dict:
        with mongo_collection(cls.BENCHMARK_COLLECTION) as col:
            doc = col.find_one({"_id": "player_benchmarks"})
            data = doc.get("data", {}) if doc else {}

            if pos:
                return data.get(pos.upper(), {})  # Always uppercase!
            return data