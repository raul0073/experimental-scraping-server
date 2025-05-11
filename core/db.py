# app/core/db.py
import os, logging
from pymongo import MongoClient
from pymongo.collection import Collection
from fastapi import HTTPException
from pydantic import BaseSettings

class Settings(BaseSettings):
    mongodb_uri: str
    db_name: str
    class Config:
        env_file = ".env"

settings = Settings()

def get_mongo_client() -> MongoClient:
    try:
        client = MongoClient(settings.mongodb_uri)
        logging.info("🔗 MongoDB connected")
        return client
    except Exception as e:
        logging.error(f"MongoDB connection error: {e}")
        raise HTTPException(500, "Could not connect to MongoDB")

def get_collection(col_name: str) -> Collection:
    client = get_mongo_client()
    return client[settings.db_name][col_name]
