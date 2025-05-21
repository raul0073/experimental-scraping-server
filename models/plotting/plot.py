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
    pizza_metrics: List[ChartMetric]
    radar_metrics: List[ChartMetric]