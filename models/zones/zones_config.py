from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from models.players import PlayerModel

class ZoneBreakdownEntry(BaseModel):
    score: float
    raw: float
    pros: List[str]
    cons: List[str]
    weight: float

class ZonePlayerContribution(BaseModel):
    name: str
    rating: float
    minutes: float
    position_weight: float

class ZonePlayerBreakdown(BaseModel):
    score: float
    raw: float
    weight: float
    contributions: List[ZonePlayerContribution]

class ZoneBreakdown(BaseModel):
    team: ZoneBreakdownEntry
    against: ZoneBreakdownEntry
    players: ZonePlayerBreakdown

class ZoneData(BaseModel):
    label: str
    rating: float
    breakdown: ZoneBreakdown
    
    
    
class ZoneConfig(BaseModel):
    label: str
    positions: Dict[str, float]
    pros: Dict[str, Dict[str, List[str]]]
    cons: Dict[str, Dict[str, List[str]]]
class ZonesConfig(BaseModel):
    zone_config: Dict[str, ZoneConfig] = Field(default_factory=dict)
    zone_scalers: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    zone_players: Dict[str, List[str]]  = Field(default_factory=dict)
    




    
    
ZONE_SCALERS: Dict[str, Dict[str, float]] = {
            "defCentral": {
                "Tkl+Int": 0.3,
                "Blocks_Sh": 0.3,
                "Tackles_Def 3rd": 0.4,
                "Crosses_Stp": 0.6,
                "Outcomes_Off": 0.4,
                "Take-Ons_Tkld": 0.5,
                "SCA Types_PassLive": 0.1,
                "Tackles in Defensive Third": 0.4,
                "Shots Blocked": 0.3,
                "Tackles + Interceptions": 0.2,
                "Save Percentage": 0.3,
                "Passes Offside": 0.2,
                "Errors Leading to Shot": 0.2,
                "Penalty Attempts": 0.1,
                "Shots on Target": 0.2,
                "Touches in Defensive Penalty Area": 0.2,
                "Penalty Save Percentage": 0.1,
                "Goal-Creating Actions / 90": 0.2,
                "Shot-Creating Actions / 90": 0.2,
                "Through Balls": 0.2,
                "Touches in Attacking Penalty Area": 0.4,
                "Touches in Attacking Third": 0.1,
                "Challenge Tackle Success %": 0.1,
                "Clearances": 0.1,
                "Miscontrols": 0.1,
                "Dispossessed": 0.1,
                "Expected Assists (xA)": 0.1,
                "Penalties Faced": 0.1,
                "Shots on Target per 90": 0.3,
                "SCA via Take-On": 0.2
            },
            "defLeftWide": {
                "Tackles in Defensive Third": 0.4,
                "Interceptions": 0.3,
                "Clearances": 0.3,
                "Shots Blocked": 0.3,
                "Miscontrols": 0.3,
                "Dispossessed": 0.3,
                "Passes Offside": 0.3,
                "Non-Penalty xG + xAG / 90": 0.3,
                "Take-On Success %": 0.3,
                "SCA via Take-On": 0.3
            },
            "defLeftHalf": {
                "Blocks": 0.2,
                "Tackles Won": 0.2,
                "Clearances": 0.2,
                "Tackles + Interceptions": 0.2,
                "Blocked Passes": 0.2,
                "Progressive Passes": 0.2,
                "Passes into Final Third": 0.2,
                "Long Passes Completed": 0.2,
                "Pass Completion %": 0.2,
                "Touches_Def 3rd": 0.2,
                "Carries": 0.2,
                "Progressive Carries": 0.2,
                "Carries into Final Third": 0.1,
                "Progressive Passes Received": 0.1,
                "Dribbles Completed": 0.2,
                "Take-Ons": 0.2,
                "xG": 0.2,
                "Shot-Creating Actions": 0.2,
                "Passes Blocked": 0.2
            },
            "defRightHalf": {
                "Blocks": 0.2,
                "Interceptions": 0.2,
                "Tackles Won": 0.2,
                "Progressive Passes": 0.2,
                "Touches_Def 3rd": 0.2,
                "Progressive Passes Received": 0.2,
                "Carries into Final Third": 0.2,
                "Shots on Target": 0.2,
                "Passes Blocked": 0.2
            },
            "defRightWide": {
                "Tackles in Defensive Third": 0.2,
                "Blocks": 0.2,
                "Interceptions": 0.2,
                "Progressive Passes": 0.2,
                "Passes into Final Third": 0.2,
                "Carries": 0.2,
                "Touches_Def 3rd": 0.2,
                "Progressive Passes Received": 0.2,
                "Dribbles Completed": 0.2,
                "Carries into Final Third": 0.2,
                "xG": 0.2
            },
            "midLeftWide": {
                "PrgP": 0.2,
                "KP": 0.2,
                "Carries_PrgC": 0.2,
                "SCA_SCA": 0.2
            },
            "midLeftHalf": {
                "PrgP": 0.2,
                "Touches_Mid 3rd": 0.2,
                "Int": 0.2
            },
            "midCentral": {
                "PrgP": 0.2,
                "KP": 0.2,
                "Touches_Mid 3rd": 0.2,
                "Int": 0.2
            },
            "midRightHalf": {
                "PrgP": 0.2,
                "Touches_Mid 3rd": 0.2,
                "Int": 0.2
            },
            "midRightWide": {
                "PrgP": 0.2,
                "KP": 0.2,
                "Carries_PrgC": 0.2,
                "SCA_SCA": 0.2
            },
            "attLeftWide": {
                "Expected_xG": 0.2,
                "SCA_SCA": 0.2,
                "PPA": 0.2
            },
            "attLeftHalf": {
                "Expected_npxG": 0.2,
                "GCA_GCA": 0.2,
                "PrgP": 0.2
            },
            "attCentral": {
                "Expected_xG": 0.2,
                "Expected_npxG": 0.2,
                "SCA_SCA": 0.2,
                "GCA_GCA": 0.2,
                "PPA": 0.2,
                "PrgP": 0.2
            },
            "attRightHalf": {
                "Expected_npxG": 0.2,
                "GCA_GCA": 0.2,
                "PrgP": 0.2
            },
            "attRightWide": {
                "Expected_xG": 0.2,
                "SCA_SCA": 0.2,
                "PPA": 0.2
            }
}

ZONE_CONFIG =  {
            "defLeftWide": {
                "label": "Defensive Left Wing",
                "positions": {
                    "LB": 0.45,
                    "LWB": 0.45,
                    "LW": 0.1
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "defLeftHalf": {
                "label": "Defensive Left Channel",
                "positions": {
                    "LB": 0.3,
                    "LCB": 0.6,
                    "CB": 0.6,
                    "CDM": 0.1
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "defCentral": {
                "label": "Defensive Central Area",
                "positions": {
                    "CB": 0.4,
                    "LCB": 0.4,
                    "LDM": 0.1,
                    "CDM": 0.2,
                    "GK": 0.2,
                    "RCB": 0.4,
                    "RDM": 0.1
                },
                "pros": {
                    "team": {
                        "defense": [
                            "Tackles in Defensive Third",
                            "Shots Blocked",
                            "Tackles + Interceptions",
                            "Clearances",
                            "Challenge Tackle Success %"
                        ],
                        "keeper": [
                            "Save Percentage"
                        ]
                    },
                    "against": {
                        "possession": [
                            "Miscontrols",
                            "Dispossessed"
                        ],
                        "passing_types": [
                            "Passes Offside"
                        ]
                    }
                },
                "cons": {
                    "team": {
                        "defense": [
                            "Errors Leading to Shot"
                        ],
                        "standard": [
                            "Penalty Attempts"
                        ],
                        "passing": [
                            "Expected Assists (xA)"
                        ],
                        "shooting": [
                            "Shots on Target"
                        ],
                        "possession": [
                            "Touches in Defensive Penalty Area",
                            "Touches in Attacking Third"
                        ],
                        "passing_types": [
                            "Through Balls"
                        ],
                        "keeper": [
                            "Penalties Faced"
                        ]
                    },
                    "against": {
                        "shooting": [
                            "Shots on Target per 90"
                        ],
                        "goal_shot_creation": [
                            "Shot-Creating Actions / 90",
                            "Goal-Creating Actions / 90",
                            "SCA via Take-On"
                        ],
                        "keeper": [
                            "Penalty Save Percentage"
                        ],
                        "possession": [
                            "Touches in Attacking Penalty Area"
                        ]
                    }
                }
            },
            "defRightHalf": {
                "label": "Defensive Right Channel",
                "positions": {
                    "RB": 0.3,
                    "RCB": 0.6,
                    "CB": 0.6,
                    "CDM": 0.1
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "defRightWide": {
                "label": "Defensive Right Wing",
                "positions": {
                    "RB": 0.6,
                    "RWB": 0.3,
                    "RW": 0.1
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "midLeftWide": {
                "label": "Middle Third Left Wing",
                "positions": {
                    "LW": 0.5,
                    "LWB": 0.3,
                    "LM": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "midLeftHalf": {
                "label": "Middle Third Left Channel",
                "positions": {
                    "CM": 0.5,
                    "CDM": 0.3,
                    "LB": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "midCentral": {
                "label": "Middle Third Central Area",
                "positions": {
                    "CM": 0.4,
                    "CDM": 0.4,
                    "CAM": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "midRightHalf": {
                "label": "Middle Third Right Channel",
                "positions": {
                    "CM": 0.5,
                    "CDM": 0.3,
                    "RB": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "midRightWide": {
                "label": "Middle Third Right Wing",
                "positions": {
                    "RW": 0.5,
                    "RWB": 0.3,
                    "RM": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "attLeftWide": {
                "label": "Attacking Left Wing",
                "positions": {
                    "LW": 0.6,
                    "CAM": 0.2,
                    "ST": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "attLeftHalf": {
                "label": "Attacking Left Channel",
                "positions": {
                    "CAM": 0.4,
                    "LW": 0.3,
                    "ST": 0.3
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "attCentral": {
                "label": "Attacking Central Area",
                "positions": {
                    "CAM": 0.3,
                    "ST": 0.4,
                    "CF": 0.3
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "attRightHalf": {
                "label": "Attacking Right Channel",
                "positions": {
                    "CAM": 0.4,
                    "RW": 0.3,
                    "ST": 0.3
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            },
            "attRightWide": {
                "label": "Attacking Right Wing",
                "positions": {
                    "RW": 0.6,
                    "CAM": 0.2,
                    "ST": 0.2
                },
                "pros": {
                    "team": {},
                    "against": {}
                },
                "cons": {
                    "team": {},
                    "against": {}
                }
            }
}
        


POSITIONS_FALLBACK_MAP = {
    # Fullbacks and Wingbacks
    "LB": "LWB", "LWB": "LM", "LM": "LB",
    "RB": "RWB", "RWB": "RM", "RM": "RB",

    # Center Backs
    "LCB": "CB", "RCB": "CB", "CB": "LCB",

    # Defensive Midfield
    "CDM": "CM", "DM": "CM", "LDM": "CDM", "RDM": "CDM",

    # Central Midfield
    "CM": "CDM", "LCM": "CM", "RCM": "CM",

    # Attacking Midfield
    "CAM": "CM", "AM": "CM",

    # Wide Midfielders
    "LW": "LM", "LM": "LW", "RW": "RM", "RM": "RW",

    # Strikers
    "CF": "ST", "ST": "CF", "STR": "ST", "STL": "ST",

    # Goalkeeper
    "GK": "GK"
}