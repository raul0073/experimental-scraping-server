from typing import Dict, List, Optional
from pydantic import BaseModel

from models.players import PlayerModel


class ZoneData(BaseModel):
    label: str
    rating: float
    players: List[dict]
    breakdown: Dict[str, float]


ZONE_CONFIG = {
    "defLeftWide": {
        "label": "Defensive Left Wing",
        "positions": {"LB": 0.45, "LWB": 0.45, "LW": 0.1},
        "pros": {
            "team": {
                "defense": [
                    "Tackles in Defensive Third",
                    "Interceptions",
                    "Blocks",
                    "Clearances",
                ],
                "passing": ["Progressive Passes", "Passes into Final Third"],
            },
            "against": {"possession": ["Miscontrols", "Dispossessed"]},
        },
        "cons": {
            "against": {
                "possession": ["Dribbles Completed", "Carries into Final Third"],
                "shooting": ["xG", "Shots on Target"],
            }
        },
    },
    "defLeftHalf": {
        "label": "Defensive Left Channel",
        "positions": {"LB": 0.3, "LCB": 0.6, "CB": 0.6, "CDM": 0.1},
        "pros": {
            "team": {
                "defense": [
                    "Blocks",
                    "Tackles Won",
                    "Clearances",
                    "Tackles + Interceptions",
                    "Blocked Passes",
                ],
                "passing": [
                    "Progressive Passes",
                    "Passes into Final Third",
                    "Long Passes Completed",
                    "Pass Completion %",
                ],
                "possession": [
                    "Touches_Def 3rd",
                    "Carries",
                    "Progressive Carries",
                    "Carries into Final Third",
                ],
            }
        },
        "cons": {
            "against": {
                "possession": [
                    "Progressive Passes Received",
                    "Carries into Final Third",
                    "Dribbles Completed",
                    "Take-Ons",
                ],
                "shooting": [
                    "xG",
                    "Shot-Creating Actions",
                ],
            }
        },
    },
    "defCentral": {
        "label": "Defensive Central Area",
        "positions": {"CB": 0.5, "LCB": 0.5, "LDM": 0.3, "CDM": 0.3, "GK": 0.2},
        "pros": {
            "team": {
                "defense": ["Tkl+Int", "Blocks", "Clearances"],
                "keeper": ["Save Percentage"],
                "keeper_adv": ["Expected_PSxG"],
            }
        },
        "cons": {
            "against": {
                "shooting": ["xG", "Shots on Target"],
                "possession": ["Carries into Penalty Area"],
            }
        },
    },
    "defRightHalf": {
        "label": "Defensive Right Channel",
        "positions": {"RB": 0.3, "RCB": 0.6, "CB": 0.6, "CDM": 0.1},
        "pros": {
            "team": {
                "defense": ["Blocks", "Interceptions", "Tackles Won"],
                "passing": ["Progressive Passes"],
                "possession": ["Touches_Def 3rd"],
            }
        },
        "cons": {
            "against": {
                "possession": [
                    "Progressive Passes Received",
                    "Carries into Final Third",
                ],
                "shooting": ["Shots on Target"],
            }
        },
    },
    "defRightWide": {
        "label": "Defensive Right Wing",
        "positions": {"RB": 0.6, "RWB": 0.3, "RW": 0.1},
        "pros": {
            "team": {
                "defense": ["Tackles in Defensive Third", "Blocks", "Interceptions"],
                "passing": ["Progressive Passes", "Passes into Final Third"],
                "possession": ["Carries", "Touches_Def 3rd"],
            }
        },
        "cons": {
            "against": {
                "possession": [
                    "Progressive Passes Received",
                    "Dribbles Completed",
                    "Carries into Final Third",
                ],
                "shooting": ["xG"],
            }
        },
    },
    # 🧠 MIDDLE THIRD
    "midLeftWide": {
        "label": "Middle Third Left Wing",
        "positions": {"LW": 0.5, "LWB": 0.3, "LM": 0.2},
        "stat_types": {
            "passing": {"weight": 0.4, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.4, "keys": {"Carries_PrgC": 1.0}},
            "goal_shot_creation": {"weight": 0.2, "keys": {"SCA_SCA": 1.0}},
        },
    },
    "midLeftHalf": {
        "label": "Middle Third Left Channel",
        "positions": {"CM": 0.5, "CDM": 0.3, "LB": 0.2},
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}},
        },
    },
    "midCentral": {
        "label": "Middle Third Central Area",
        "positions": {"CM": 0.4, "CDM": 0.4, "CAM": 0.2},
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}},
        },
    },
    "midRightHalf": {
        "label": "Middle Third Right Channel",
        "positions": {"CM": 0.5, "CDM": 0.3, "RB": 0.2},
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}},
        },
    },
    "midRightWide": {
        "label": "Middle Third Right Wing",
        "positions": {"RW": 0.5, "RWB": 0.3, "RM": 0.2},
        "stat_types": {
            "passing": {"weight": 0.4, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.4, "keys": {"Carries_PrgC": 1.0}},
            "goal_shot_creation": {"weight": 0.2, "keys": {"SCA_SCA": 1.0}},
        },
    },
    # 🎯 ATTACKING THIRD
    "attLeftWide": {
        "label": "Attacking Left Wing",
        "positions": {"LW": 0.6, "CAM": 0.2, "ST": 0.2},
        "stat_types": {
            "shooting": {"weight": 0.5, "keys": {"Expected_xG": 1.0}},
            "goal_shot_creation": {"weight": 0.3, "keys": {"SCA_SCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PPA": 1.0}},
        },
    },
    "attLeftHalf": {
        "label": "Attacking Left Channel",
        "positions": {"CAM": 0.4, "LW": 0.3, "ST": 0.3},
        "stat_types": {
            "shooting": {"weight": 0.4, "keys": {"Expected_npxG": 1.0}},
            "goal_shot_creation": {"weight": 0.4, "keys": {"GCA_GCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}},
        },
    },
    "attCentral": {
        "label": "Attacking Central Area",
        "positions": {"CAM": 0.3, "ST": 0.4, "CF": 0.3},
        "stat_types": {
            "shooting": {
                "weight": 0.5,
                "keys": {"Expected_xG": 0.6, "Expected_npxG": 0.4},
            },
            "goal_shot_creation": {
                "weight": 0.3,
                "keys": {"SCA_SCA": 0.4, "GCA_GCA": 0.6},
            },
            "passing": {"weight": 0.2, "keys": {"PPA": 0.5, "PrgP": 0.5}},
        },
    },
    "attRightHalf": {
        "label": "Attacking Right Channel",
        "positions": {"CAM": 0.4, "RW": 0.3, "ST": 0.3},
        "stat_types": {
            "shooting": {"weight": 0.4, "keys": {"Expected_npxG": 1.0}},
            "goal_shot_creation": {"weight": 0.4, "keys": {"GCA_GCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}},
        },
    },
    "attRightWide": {
        "label": "Attacking Right Wing",
        "positions": {"RW": 0.6, "CAM": 0.2, "ST": 0.2},
        "stat_types": {
            "shooting": {"weight": 0.5, "keys": {"Expected_xG": 1.0}},
            "goal_shot_creation": {"weight": 0.3, "keys": {"SCA_SCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PPA": 1.0}},
        },
    },
}


POSITIONS_FALLBACK_MAP = {
    # Fullbacks and Wingbacks
    "LB": "LWB",
    "LWB": "LB",
    "RB": "RWB",
    "RWB": "RB",
    # Center Backs
    "LCB": "CB",
    "RCB": "CB",
    "CB": "RCB",  # Default fallback for generic CB is one specific side
    # Defensive Midfield
    "CDM": "CM",
    "DM": "CM",
    # Central Midfield
    "CM": "CDM",
    "LCM": "CM",
    "RCM": "CM",
    # Attacking Midfield
    "CAM": "CM",
    "AM": "CM",
    # Wide Midfielders
    "LM": "LW",
    "RM": "RW",
    # Wingers
    "LW": "LM",
    "RW": "RM",
    # Strikers
    "CF": "ST",
    "ST": "CF",
    # Goalkeeper
    "GK": "GK",  # No fallback for keeper
}
