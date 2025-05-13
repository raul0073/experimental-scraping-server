from contextlib import contextmanager
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongodb_uri = os.getenv("MONGODB_URI")
db_name = os.getenv("DB_NAME")

if not mongodb_uri or not db_name:
    raise RuntimeError("❌ MONGODB_URI or DB_NAME is not set in .env")

def get_mongo_client() -> MongoClient:
    return MongoClient(mongodb_uri)

@contextmanager
def mongo_collection(col_name: str):
    client = get_mongo_client()
    try:
        db = client[db_name]
        yield db[col_name]
    finally:
        client.close()
