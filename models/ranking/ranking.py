LOWER_IS_BETTER = {
    "defense:Err",
    "misc:Carries - Mis",
    "misc:Carries - Dis",
    "defense:Challenges - Lost",
    "misc:Performance - CrdY",
    "misc:Performance - CrdR",
    "misc:Performance - 2CrdY",
    "misc:Performance - Fls",
    "misc:Performance - Off",
    "misc:Performance - OG",
    "misc:Aerial Duels - Lost",
    "possession:Take-Ons - Tkld%",
    "passing_types:Outcomes - Off",
    "passing_types:Outcomes - Blocks",  # this one might not be truly "bad" — verify usage
}


ROLE_RANK_MAPPING = {
    "GK": {
        "keeper:Performance - Save%": 0.35,
        "keeper:Penalty Kicks - Save%": 0.10,
        "keeper:Performance - CS%": 0.10,
        "keeper:Performance - CS": 0.05,
        "passing:Total - Cmp%": 0.10,
        "passing_types:Pass Types - Live": 0.05,
        "passing_types:Outcomes - Cmp": 0.05,
        "keeper:Performance - Err": -0.05,
        "keeper_adv:Performance - PSxG+/-": 0.10,
        "keeper_adv:Crosses - Stp%": 0.05,
        "keeper_adv:Crosses - Stp": 0.05,
        "keeper_adv:Sweeper - #OPA/90": 0.10,
    },

"CB": {
    # Core Defensive Reliability
    "defense:Tkl+Int": 0.20,
    "defense:Clr": 0.15,
    "defense:Blocks - Blocks": 0.10,

    # Duel Quality — Not Volume
    "misc:Aerial Duels - Won%": 0.10,   # ↓ from 0.20

    # Discipline & Stability
    "defense:Err": -0.10,
    "Performance - 2CrdY": -0.05,
    "standard:Performance - CrdR": -0.05,

    # Ball Progression
    "passing:Total - Cmp%": 0.05,
    "passing:Total - PrgDist": 0.05,
    "possession:Carries - PrgDist": 0.05,

    # Goal Threat (Light Bonus)
    "shooting:Expected - xG": 0.025,
    "goal_shot_creation:SCA - SCA90": 0.025,
},

    "FB": {
        "defense:Tackles - Tkl": 0.15,
        "defense:Interceptions - Int": 0.10,
        "defense:Blocks - Blocks": 0.10,
        "defense:Clearances - Clr": 0.05,
        "possession:Carries - Prog": 0.10,
        "passing:Pass Types - Prog": 0.10,
        "passing:Total - Cmp%": 0.10,
        "passing_types:Pass Types - Crs": 0.05,
        "passing_types:Pass Types - Cmp%": 0.05,
        "misc:Performance - Fls": -0.05,
        "misc:Performance - CrdY": -0.05,
        "misc:Carries - Dis": -0.05,
        "misc:Carries - Mis": -0.05,
    },

    "DM": {
        "defense:Tackles - Tkl": 0.15,
        "defense:Interceptions - Int": 0.15,
        "defense:Tkl+Int": 0.05,
        "defense:Err": -0.05,
        "passing:Total - Cmp%": 0.10,
        "passing:Total - PrgDist": 0.05,
        "passing:Short - Cmp%": 0.05,
        "passing:Medium - Cmp%": 0.05,
        "passing_types:Pass Types - Sw": 0.05,
        "possession:Carries - PrgDist": 0.05,
        "misc:Performance - Fls": -0.05,
        "misc:Performance - CrdY": -0.05,
    },

"CM": {
    # Defensive Contribution
    "defense:Tackles - Tkl": 0.10,
    "defense:Interceptions - Int": 0.05,

    # Ball Circulation (security & progression)
    "passing:Total - Cmp%": 0.05,
    "passing:Medium - Cmp%": 0.05,
    "passing:Long - Cmp%": 0.05,
    "passing:Total - PrgDist": 0.05,

    # Attacking Link (chance creation)
    "passing:KP": 0.10,  # ↑
    "goal_shot_creation:SCA - SCA90": 0.10,
    "goal_shot_creation:GCA - GCA90": 0.05,

    # Progressive Carrying
    "possession:Carries - PrgDist": 0.05,
    "possession:Carries - PrgC": 0.05,

    # Penalties
    "misc:Performance - Fls": -0.05,
    "misc:Performance - CrdY": -0.05,
},

"AM": {
    # 🎯 Elite playmaking and creation
    "goal_shot_creation:SCA - SCA90": 0.15,
    "goal_shot_creation:GCA - GCA90": 0.10,
    "passing:KP": 0.10,
    "passing:Expected - xAG": 0.05,
    "passing:Expected - xA": 0.05,

    # 📦 Threatening passes and territory gain
    "passing:1/3": 0.05,
    "passing:PPA": 0.05,
    "passing:Pass Types - TB": 0.05,
    "passing:Total - PrgDist": 0.05,
    "passing:Total - Cmp%": 0.05,

    # 🏃‍♂️ Progressive carrying
    "possession:Carries - PrgDist": 0.05,
    "possession:Carries - PrgC": 0.05,

    # ❌ Mental/composure penalties
    "misc:Carries - Dis": -0.05,
    "misc:Carries - Mis": -0.05,
    "defense:Err": -0.05,
    "misc:Performance - CrdY": -0.05,
},

"W": {
    # Attacking Initiative
    "possession:Take-Ons - Att": 0.10,  # NEW: boldness to attempt
    "possession:Take-Ons - Succ": 0.10,
    "possession:Carries - PrgC": 0.10,
    "possession:Carries - 1/3": 0.10,

    # Service & Vision
    "passing_types:Pass Types - Crs": 0.05,
    "passing:KP": 0.05,

    # Direct Creation
    "goal_shot_creation:SCA - SCA90": 0.10,
    "goal_shot_creation:GCA - GCA90": 0.05,

    # Goal Threat
    "shooting:Standard - SoT/90": 0.05,
    "shooting:Expected - xG": 0.025,   # NEW: added goal instinct

    # Penalties
    "misc:Carries - Dis": -0.05,
    "misc:Carries - Mis": -0.05,
    "misc:Performance - CrdY": -0.05,
},
"CF": {
  "shooting:Standard - SoT/90": 0.10,
  "shooting:Standard - G/Sh": 0.10,
  "shooting:Per 90 Minutes - npxG": 0.10,
  "shooting:Per 90 Minutes - Gls": 0.10,
  "passing:KP": 0.05,
  "goal_shot_creation:SCA - SCA90": 0.05,
  "misc:Carries - Dis": -0.02,
  "misc:Performance - Off": -0.02,
  "misc:Performance - CrdY": -0.01
}
}

# ZONES_ROLES_WEIGHTS = {
#     "GK": 1.0,
#     "DL": 1.5,
#     "DC": 2.0
# }


# roles to ranking mapping:
ROLE_BASE_MAP = {
    "LCB": "CB",
    "RCB": "CB",
    "CB": "CB",

    "LB": "FB",
    "RB": "FB",
    "LWB": "FB",
    "RWB": "FB",
    "FB": "FB",
    
    "CDM": "DM",
    "CM": "CM",
    "CAM": "AM",
    "AM": "AM",
    "LM": "W",
    "RM": "W",
    "LW": "W",
    "RW": "W",
    "W": "W",

    "CF": "CF",
    "ST": "CF",

    "GK": "GK",
}