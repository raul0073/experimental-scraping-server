from typing import List, Optional
from pydantic import BaseModel, Field


class ChartMetric(BaseModel):
    key: str
    value: float
    category: str
    rawkey: str = Field(..., alias='rawKey')
    
    
class ChartRequest(BaseModel):
    player_name: str
    stat_type: Optional[str] = None
    chart_type: str  # "radar" or "pizza"
    metrics: List[ChartMetric]