from typing import Any,  Dict, List, Optional
import pandas as pd
from pydantic import BaseModel


ALL_POSITIONS = [
    # Goalkeeper
    "GK",

    # Defenders
    "RB", "RWB", "CB", "LB", "LWB",

    # Midfielders
    "CDM", "CM", "CAM", "RM", "LM",

    # Forwards
    "RW", "LW", "CF", "ST", "SS"
]


class PlayerModel(BaseModel):
    id: str = ""
    name: str
    team: str
    position: str
    foot: Optional[str] = ""
    age: str
    nationality: str
    stats: Dict[str, Any]
    rating: float = 0.0
    role: Optional[str] = ""
    shirt_number: Optional[int] = None
    class Config:
        extra = "allow"
        
        
    @staticmethod
    def from_df_row(row) -> "PlayerModel":
        position = row.get("standard_pos", "")
        return PlayerModel(
            id=f"{row['player']}-{row['team']}",
            name=row["player"],
            team=row["team"],
            position=position,
            role=position,  # ✅ ensure role is always set
            age=row.get("standard_age", ""),
            nationality=row.get("standard_nation", ""),
            stats=PlayerModel.group_stats_by_type(row)
        )

    @staticmethod
    def group_stats_by_type(row: pd.Series) -> Dict[str, List[Dict[str, Any]]]:
        grouped_stats: Dict[str, List[Dict[str, Any]]] = {}
        for key, val in row.items():
            if "_" not in key or key.endswith("_rank"):
                continue

            stat_type, label = key.split("_", 1)
            rank_key = f"{key}_rank"
            rank = row.get(rank_key, None)

            if stat_type not in grouped_stats:
                grouped_stats[stat_type] = []

            grouped_stats[stat_type].append({
                "label": label,
                "val": val,
                "rank": rank
            })

        return grouped_stats

