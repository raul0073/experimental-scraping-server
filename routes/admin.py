from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, Depends
from dotenv import load_dotenv
import os
load_dotenv()
from services.rating.optimizer import ConfigOptimizer

router = APIRouter(
    tags=["optimizer"]
)

# Simple admin key fetched from environment
ADMIN_KEY = os.getenv("ADMIN_KEY")


def verify_admin_key(
    x_admin_key: str = Header(..., alias="X-ADMIN-KEY")
) -> bool:
    """
    Dependency to verify a simple admin API key.
    Clients must include 'X-ADMIN-KEY' header matching ADMIN_KEY.
    """
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    return True


@router.post("/run")
async def trigger_optimizer(
    background_tasks: BackgroundTasks,
    _admin: bool = Depends(verify_admin_key)
):
    """
    Trigger the nightly AI zone optimization process manually.
    Secured via simple admin key in header.
    Runs in background to prevent request blocking.
    """
    try:
        background_tasks.add_task(ConfigOptimizer.run_ai_zone_config_nightly)
        return {"status": "scheduled"}
    except Exception as e:
        raise HTTPException(500, f"Failed to schedule optimizer: {e}")
