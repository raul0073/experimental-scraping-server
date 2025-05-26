import os
import requests
from fastapi import APIRouter
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

@router.get("/ping")
async def ping():
    return {"status": "alive"}

def ping_self():
    try:
        url = os.getenv("HOST_URL")
        if url:
            requests.get(f"{url}/ping")
        else:
            print("HOST_URL not set in environment.")
    except Exception as e:
        print(f"Ping failed: {e}")

