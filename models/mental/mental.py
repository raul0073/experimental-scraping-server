ROLE_AWARE_MENTAL_TRAIT_MAPPING = {
    # === Goalkeeper (GK) ===
    "GK": {
        "Defensive Intelligence": [
            "keeper:Performance - Save%",        
            "keeper_adv:Expected - PSxG+/-",     
        ],
        "Build-Up Vision": [
            "passing:Total - Cmp%",              
            "passing:Short - Cmp%",              
            "passing:Medium - Cmp%",             
        ],
        "Decision-Making": [
            "defense:Err",                       
            "keeper_adv:Goals - GA",             
            "keeper_adv:Goals - OG",             
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
            "misc:Performance - 2CrdY",
        ],
        "Physical Presence": [
            "keeper_adv:Crosses - Stp%",         
            "keeper_adv:Sweeper - #OPA/90",      
            "keeper_adv:Sweeper - AvgDist",      
        ],
        "Creativity": [
            "passing:PrgP",                      
            "passing:Expected - xA", 
            "passing:PPA", 
        ],
        "Finishing & Conversion": [
            "keeper:Performance - CS%",
        ],
    },

    # === Center-Back (CB) ===
    "CB": {
        "Defensive Intelligence": [
            "defense:Tkl+Int",
            "defense:Blocks - Sh",
            "misc:Performance - Recov",
        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
            "possession:Carries - PrgC",
        ],
        "Decision-Making": [
            "defense:Err",
            "misc:Performance - OG",
            "possession:Carries - Mis",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
                        "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",
            "defense:Clr",
        ],
        "Aerial Presence": [
            "misc:Aerial Duels - Won%",
            "misc:Aerial Duels - Lost",
        ],
        "Creativity": [
            "passing_types:Pass Types - Sw",
            "goal_shot_creation:SCA - SCA90",
        ],
        "Finishing & Conversion": [
            "shooting:Expected - xG",
            "goal_shot_creation:GCA - GCA90",
        ],
    },

    # === Full-Back (FB) ===
    "FB": {
        "Defensive Intelligence": [
            "defense:Tackles - Mid 3rd",
            "defense:Challenges - Tkl%",
            "misc:Performance - Recov",
        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
        ],
        "Decision-Making": [
            "defense:Err",
            "misc:Performance - Off",
            "possession:Carries - Dis",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",
            "defense:Clr",
        ],
        "Creativity": [
            "passing_types:Pass Types - Crs",
            "possession:Take-Ons - Succ%",
            "goal_shot_creation:SCA - SCA90",
        ],
        "Finishing & Conversion": [
            "possession:Carries - 1/3",
            "shooting:Expected - xG",
            "shooting:Expected - xA",
        ],
    },

    # === Defensive Midfielder (DM) ===
    "DM": {
        "Defensive Intelligence": [
            "defense:Tkl+Int",
            "defense:Tackles - Mid 3rd",
            "defense:Tackles - Def 3rd",
            "misc:Performance - Recov",
        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Short - Cmp%",
            "passing:Medium - Cmp%",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
        ],
        "Decision-Making": [
            "defense:Err",
            "possession:Carries - Dis",
            "possession:Carries - Mis",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
                        "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",
            "defense:Challenges - Tkl%",
        ],
        "Creativity": [
            "passing:KP",
            "goal_shot_creation:SCA - SCA90",
            "passing:Expected - xA",
            
        ],
        "Finishing & Conversion": [
            "shooting:Expected - xG",
            "shooting:Standard - G/SoT",
        ],
    },

    # === Central Midfielder (CM) ===
    "CM": {
        "Defensive Intelligence": [
            "defense:Tkl+Int",
            "defense:Tackles - Mid 3rd",
            "defense:Challenges - Tkl%",
        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
            "passing_types:Pass Types - Sw",
            "possession:Receiving - PrgR",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
            "possession:Carries - TotDist",
            "possession:Carries - 1/3",
        ],
        "Decision-Making": [
            "defense:Err",
            "possession:Carries - Mis",
            "misc:Performance - Off",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
                        "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",

        ],
        "Creativity": [
            "passing:KP",
            "goal_shot_creation:SCA - SCA90",
            "goal_shot_creation:GCA - GCA90",
            "goal_shot_creation:GCA Types - PassLive",
        ],
        "Finishing & Conversion": [
            "standard:Per 90 Minutes - xG",
            "standard:Per 90 Minutes - xAG",
        ],
    },

    # === Attacking Midfielder (AM) ===
    "AM": {
        "Decision-Making": [
            "defense:Err",
            "possession:Carries - Mis",
            "misc:Performance - Off",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
            "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",
        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
            "possession:Take-Ons - Succ%",
            "possession:Carries into Final Third",
        ],
        "Creativity": [
            "passing:KP",
            "goal_shot_creation:SCA - SCA90",
            "goal_shot_creation:GCA - GCA90",
        ],
        "Finishing & Conversion": [
            "shooting:Expected - xG",
            "shooting:Expected - xAG",
        ],
    },

    # === Wingers (W) ===
    "W": {
        "Decision-Making": [
            "defense:Err",
            "possession:Carries - Mis",
            "misc:Performance - Off",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
                        "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",

        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
            "possession:Take-Ons - Succ%",
            "possession:Carries - CPA",
            "possession:Carries - 1/3",
             "possession:Carries - TotDist",
        ],
        "Creativity": [
            "passing:KP",
            "passing:Expected - xA",
            "goal_shot_creation:SCA - SCA90",
            "goal_shot_creation:GCA - GCA90",
        ],
        "Finishing & Conversion": [
            "shooting:Expected - xG",
            "shooting:Expected - npxG/Sh",
        ],
    },

    # === Forwards / Strikers (CF) ===
    "CF": {
        "Decision-Making": [
            "defense:Err",
            "possession:Carries - Mis",
            "misc:Performance - Off",
        ],
        "Discipline": [
            "misc:Performance - CrdY",
            "misc:Performance - CrdR",
                        "misc:Performance - 2CrdY",
            "misc:Performance - Fls",
        ],
        "Physical Presence": [
            "misc:Aerial Duels - Won%",

        ],
        "Build-Up Vision": [
            "passing:PrgP",
            "passing:Total - Cmp%",
        ],
        "Ball Progression": [
            "possession:Carries - PrgC",
            "possession:Take-Ons - Succ%",
            "possession:Carries - CPA",
                        "possession:Carries - TotDist",
        ],
        "Creativity": [
            "passing:KP",
            "goal_shot_creation:SCA - SCA90",
            "goal_shot_creation:GCA - GCA90",
        ],
        "Finishing & Conversion": [
            "shooting:Expected - xG",
            "shooting:Expected - npxG/Sh",
            "shooting:Expected - npxG",
        ],
    },
       # === Global fallback ===
       "ALL": {
        
        }
}