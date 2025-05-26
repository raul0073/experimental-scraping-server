from datetime import datetime
import os
import requests
from fastapi import APIRouter, Response
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()

@router.get("/ping")
async def ping():
    print(f"[UPTIME] GET /ping at {datetime.now().isoformat()}")
    return {"status": "alive"}

@router.head("/ping")
async def ping_head():
    print(f"[UPTIME] HEAD /ping at {datetime.now().isoformat()}")
    return Response(status_code=200)

@router.get("/ping/")
async def ping_slash():
    print(f"[UPTIME] GET /ping/ at {datetime.now().isoformat()}")
    return {"status": "alive"}