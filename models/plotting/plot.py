from typing import List, Optional
from pydantic import BaseModel, Field


class ChartMetric(BaseModel):
    key: str
    value: float
    category: str
    raw_key: str

    
class ChartRequest(BaseModel):
    player_name: str
    player_position: str
    stat_type: Optional[str] = None
    chart_type: str  # "radar" or "pizza"
    metrics: List[ChartMetric]