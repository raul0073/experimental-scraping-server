from typing import Dict
from pydantic import BaseModel


class ZoneData(BaseModel):
    label: str
    players: Dict[str, float]  
    team: Dict[str, float]     
    rating: float  

ZONE_CONFIG = {
    # 🛡️ DEFENSIVE THIRD
    "defLeftWide": {
        "label": "Defensive Left Wing",
        "positions": { "LB": 0.6, "LWB": 0.3, "LW": 0.1 },
        "stat_types": {
            "defense": {"weight": 0.7, "keys": {"Tackles in Defensive Third": 0.5, "Tackles Won": 0.25, "Interceptions": 0.2}},
            "passing": {"weight": 0.3, "keys": {"Total Pass Completion %": 0.7, "Progressive Passes": 0.3}},
        }
    },
    "defLeftHalf": {
        "label": "Defensive Left Channel",
        "positions": { "LB": 0.4, "CB": 0.3, "CDM": 0.3 },
        "stat_types": {
            "defense": {"weight": 0.6, "keys": {"Blocks_Blocks": 0.5, "Int": 0.5}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.2, "keys": {"Touches_Def 3rd": 1.0}}
        }
    },
    "defCentral": {
        "label": "Defensive Central Area",
        "positions": { "CB": 0.5, "CDM": 0.3, "GK": 0.2 },
        "stat_types": {
            "defense": {"weight": 0.5, "keys": {"Tkl+Int": 1.0}},
            "keeper": {"weight": 0.3, "keys": {"Performance_Save%": 1.0}},
            "keeper_adv": {"weight": 0.2, "keys": {"Expected_PSxG": 1.0}}
        }
    },
    "defRightHalf": {
        "label": "Defensive Right Channel",
        "positions": { "RB": 0.4, "CB": 0.3, "CDM": 0.3 },
        "stat_types": {
            "defense": {"weight": 0.6, "keys": {"Blocks_Blocks": 0.5, "Int": 0.5}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.2, "keys": {"Touches_Def 3rd": 1.0}}
        }
    },
    "defRightWide": {
        "label": "Defensive Right Wing",
        "positions": { "RB": 0.6, "RWB": 0.3, "RW": 0.1 },
        "stat_types": {
            "defense": {"weight": 0.5, "keys": {"Tackles_Def 3rd": 1.0}},
            "passing": {"weight": 0.3, "keys": {"PrgP": 0.7, "PPA": 0.3}},
            "possession": {"weight": 0.2, "keys": {"Carries_Carries": 1.0}}
        }
    },

    # 🧠 MIDDLE THIRD
    "midLeftWide": {
        "label": "Middle Third Left Wing",
        "positions": { "LW": 0.5, "LWB": 0.3, "LM": 0.2 },
        "stat_types": {
            "passing": {"weight": 0.4, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.4, "keys": {"Carries_PrgC": 1.0}},
            "goal_shot_creation": {"weight": 0.2, "keys": {"SCA_SCA": 1.0}}
        }
    },
    "midLeftHalf": {
        "label": "Middle Third Left Channel",
        "positions": { "CM": 0.5, "CDM": 0.3, "LB": 0.2 },
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}}
        }
    },
    "midCentral": {
        "label": "Middle Third Central Area",
        "positions": { "CM": 0.4, "CDM": 0.4, "CAM": 0.2 },
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}}
        }
    },
    "midRightHalf": {
        "label": "Middle Third Right Channel",
        "positions": { "CM": 0.5, "CDM": 0.3, "RB": 0.2 },
        "stat_types": {
            "passing": {"weight": 0.5, "keys": {"PrgP": 1.0}},
            "possession": {"weight": 0.3, "keys": {"Touches_Mid 3rd": 1.0}},
            "defense": {"weight": 0.2, "keys": {"Int": 1.0}}
        }
    },
    "midRightWide": {
        "label": "Middle Third Right Wing",
        "positions": { "RW": 0.5, "RWB": 0.3, "RM": 0.2 },
        "stat_types": {
            "passing": {"weight": 0.4, "keys": {"PrgP": 0.6, "KP": 0.4}},
            "possession": {"weight": 0.4, "keys": {"Carries_PrgC": 1.0}},
            "goal_shot_creation": {"weight": 0.2, "keys": {"SCA_SCA": 1.0}}
        }
    },

    # 🎯 ATTACKING THIRD
    "attLeftWide": {
        "label": "Attacking Left Wing",
        "positions": { "LW": 0.6, "CAM": 0.2, "ST": 0.2 },
        "stat_types": {
            "shooting": {"weight": 0.5, "keys": {"Expected_xG": 1.0}},
            "goal_shot_creation": {"weight": 0.3, "keys": {"SCA_SCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PPA": 1.0}}
        }
    },
    "attLeftHalf": {
        "label": "Attacking Left Channel",
        "positions": { "CAM": 0.4, "LW": 0.3, "ST": 0.3 },
        "stat_types": {
            "shooting": {"weight": 0.4, "keys": {"Expected_npxG": 1.0}},
            "goal_shot_creation": {"weight": 0.4, "keys": {"GCA_GCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}}
        }
    },
    "attCentral": {
        "label": "Attacking Central Area",
        "positions": { "CAM": 0.3, "ST": 0.4, "CF": 0.3 },
        "stat_types": {
            "shooting": {"weight": 0.5, "keys": {"Expected_xG": 0.6, "Expected_npxG": 0.4}},
            "goal_shot_creation": {"weight": 0.3, "keys": {"SCA_SCA": 0.4, "GCA_GCA": 0.6}},
            "passing": {"weight": 0.2, "keys": {"PPA": 0.5, "PrgP": 0.5}}
        }
    },
    "attRightHalf": {
        "label": "Attacking Right Channel",
        "positions": { "CAM": 0.4, "RW": 0.3, "ST": 0.3 },
        "stat_types": {
            "shooting": {"weight": 0.4, "keys": {"Expected_npxG": 1.0}},
            "goal_shot_creation": {"weight": 0.4, "keys": {"GCA_GCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PrgP": 1.0}}
        }
    },
    "attRightWide": {
        "label": "Attacking Right Wing",
        "positions": { "RW": 0.6, "CAM": 0.2, "ST": 0.2 },
        "stat_types": {
            "shooting": {"weight": 0.5, "keys": {"Expected_xG": 1.0}},
            "goal_shot_creation": {"weight": 0.3, "keys": {"SCA_SCA": 1.0}},
            "passing": {"weight": 0.2, "keys": {"PPA": 1.0}}
        }
    }
}
