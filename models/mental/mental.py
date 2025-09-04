ROLE_AWARE_MENTAL_TRAIT_MAPPING = {
    # === Goalkeeper Mental Traits ===
    "GK": {
        "Resilience": [
            "keeper:Performance - Save%",
            "keeper_adv:Expected - PSxG+/-",
        ],
        "BoxControl": [
            "keeper_adv:Crosses - Stp%",
            "keeper_adv:Sweeper - #OPA/90",
        ],
        "FocusErrors": [
            "defense:Err",
            "keeper_adv:Goals - OG",
        ],
    },

    # === Center Back ===
"CB": {
#  Reads game, cuts lanes, presses high with timing
"Initiative": [
"defense:Tkl+Int",
"defense:Blocks - Sh",
"misc:Performance - Recov",
],
#  Avoids unnecessary fouls or cards
"Discipline": [
"misc:Performance - CrdR",
"misc:Performance - 2CrdY",

],
# Dominates aerially and clears danger
"AerialPresence": [
"misc:Aerial Duels - Won%",
"defense:Clearances - Clr",
],
#  Avoids being beat or mistiming duels
"ErrorAvoidance": [
"defense:Challenges - Lost",
"defense:Err",
],
#  Threat on set-pieces or corners
"GoalThreat": [
"goal_shot_creation:SCA - SCA90",
"shooting:Expected - xG",
]
},

    # === Full Back ===
    "FB": {
        "Bravery": [
            "possession:Carries - PrgC",
            "passing:Pass Types - Crs",
        ],
        "Responsibility": [
            "defense:Tackles - Tkl",
            "defense:Interceptions - Int",
        ],
        "Discipline": [
            "misc:Performance - CrdR",
            "misc:Performance - Fls",
        ],
    },

    # === Defensive Midfielder ===
    "DM": {
        "Anticipation": [
            "defense:Interceptions - Int",
            "defense:Tackles - Mid 3rd",
            "misc:Performance - Recov"
        ],
        
        "Poise": [
            "passing:Total - Cmp%",
            "passing:Medium - Cmp%",
        ],
        "Discipline": [
            "misc:Performance - CrdR",
            "misc:Performance - Fls",
        ],
    },

    # === Central Midfielder ===
    "CM": {
        "Provider": [
            "goal_shot_creation:SCA - SCA",
            "passing:PrgP",
        ],
        "Work Rate" : [
            "defense:Err",
              "defense:Tackles - Mid 3rd",
            "defense:Tackles - TklW",
        ],
        "Composure": [
            "misc:Carries - Mis",
            "misc:Carries - Dis",
        ],
    },

    # === Attacking Midfielder ===
    "AM": {
        "Creativity": [
            "goal_shot_creation:GCA - GCA",
            "passing:Pass Types - TB",
            "passing:KP",
            "passing:xAG",
        ],
        "Impulsiveness": [
            "misc:Performance - Off",
            "misc:Carries - Dis",
        ],
        "Composure": [
            "misc:Carries - Mis",
            "misc:Carries - Dis",
            "passing:Total - Cmp%",
            
        ],
    },

    # === Winger ===
    "W": {
        "Explusive": [
            "possession:Carries - PrgC",
            "possession:Take-Ons - Att",
            "possession:Take-Ons - Tkld%",
            "passing_types:Pass Types - Crs",
            
        ],
        "Composure": [
            "misc:Carries - Mis",
            "misc:Carries - Dis",
        ],
        "Confidence": [
            "goal_shot_creation:GCA - GCA",
            "passing:Pass Types - Prog",
        ],
    },

    # === Center Forward ===
    "CF": {
        "Instinct": [
            "shooting:Standard - SoT/90",
            "possession:Receiving - PrgR",
        ],
        "ColdBlooded": [
            "shooting:Expected - G-xG",
            "shooting:Standard - G/SoT",
        ],
        "Creativity": [
            "goal_shot_creation:SCA - SCA90",
            "passing:KP",
        ],
        "Duels": [
            "misc:Aerial Duels - Won%",
            "misc:Performance - Recov",
        ],
        "Discipline": [
            "misc:Performance - Off",
            "misc:Performance - CrdY",
        ],
    },

    # empty fallback (used in normalizer)
    "ALL": {
        "playing_time": "Team Success - +/-90"
        },
}
