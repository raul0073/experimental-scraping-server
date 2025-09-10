ROLE_AWARE_MENTAL_TRAIT_MAPPING = {
    # === Goalkeeper (GK) ===
     "GK": {
        # Measures ability to make saves and handle pressure
        "Resilience": [
            "keeper:Performance_Save%",        # Positive: high save %
            "keeper_adv:Expected - PSxG+/-",   # Positive: saves vs expected
        ],
        # Measures command of the box, aerials, sweeping outside box
        "Box Control": [
            "keeper_adv:Crosses_Stp%",         # Positive: cross stop %
            "keeper_adv:Sweeper_#OPA/90",      # Positive: defensive actions outside box per 90
            "keeper_adv:Sweeper_AvgDist",      # Positive: covers distance with sweeper actions
        ],
        # Measures mistakes and negative outcomes
        "Decision Errors": [
            "defense:Err",                      # Negative: errors leading to shots
            "keeper_adv:Goals_GA",              # Negative: goals conceded
            "keeper_adv:Goals_OG",              # Negative: own goals conceded
            "keeper:Performance_PKatt",         # Neutral/negative: penalty attempts faced (optional weight)
        ],
        # Optional discipline: yellow/red cards affecting reliability
        "Discipline": [
            "misc:Performance_CrdY",
            "misc:Performance_CrdR",
             "misc:Performance - 2CrdY"
        ],
    },

    # === Center-Back (CB) ===
    "CB": {
    # Defensive actions: tackles, interceptions, blocks, recoveries
    "Defensive Intelligence": [
        "defense:Tkl+Int",                  # Positive: tackles + interceptions
        "defense:Blocks_Sh",                # Positive: blocks shots
        "misc:Performance_Recov",           # Positive: recoveries
    ],
    # Ability to dominate aerial duels and clear danger
    "Aerial Dominance": [
        "misc:Aerial Duels_Won%",           # Positive: aerial duels won %
        "defense:Clr",                       # Positive: clearances
    ],
    # Build-up and passing vision: includes mistakes to penalize poor decisions
    "Build-Up Vision": [
        "passing:PrgP",                      # Positive: progressive passes
        "passing:Total_Cmp%",                # Positive: overall passing accuracy
        "misc:Performance_Off",              # Negative: dispossessions / misplays
        "possession:Carries_Dis",            # Negative: dispossessed
        "possession:Carries_Mis",            # Negative: miscontrols
    ],
    # Errors: mistakes that lead to danger
    "Decision Errors": [
        "defense:Err",                        # Negative: errors leading to shots
        "keeper_adv:Goals_OG",                # Negative: own goals conceded
    ],
    # Discipline: fouls, cards
    "Discipline": [
        "misc:Performance_CrdY",             # Yellow cards
        "misc:Performance_CrdR",             # Red cards
        "misc:Performance_2CrdY",            # Second yellow
        "misc:Performance_Fls",               # Fouls committed
    ],
    # Set-piece threat: for scoring/contributing in corners
    "Set-Piece Threat": [
        "goal_shot_creation:SCA_SCA90",       # Positive: shot-creating actions per 90
        "shooting:Expected_xG",               # Positive: expected goals (threat)
    ],
},

    # === Full-Back (FB) ===
    "FB": {
    # Defensive awareness: tackles, interceptions, positioning
    "Defensive Responsibility": [
        "defense:Tackles_Tkl",
        "defense:Interceptions_Int",
        "misc:Performance_Recov",
    ],
    # Aerial presence and clearances (lighter than CB)
    "Aerial & Clearing": [
        "misc:Aerial Duels_Won%",
        "defense:Clr",
    ],
    # Build-up and forward passes + progressive carries
    "Build-Up Vision": [
        "passing:PrgP",
        "passing:Total_Cmp%",
        "possession:Carries_PrgC",
        "possession:Carries_Mis",
    ],
    # Mistakes / errors leading to danger
    "Errors": [
        "defense:Err",
        "misc:Performance_Off",
        "possession:Carries_Dis",
    ],
    # Discipline: fouls & cards
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
    ],
    # Attacking contributions: crosses, progressive actions
    "Attacking Contribution": [
        "passing:Pass Types_Crs",
        "possession:Carries_PrgC",
        "goal_shot_creation:SCA_SCA90",
    ],
},

    # === Defensive Midfielder (DM) ===
    "DM": {
    # Defensive awareness: interceptions, tackles in middle/defensive 3rd
    "Defensive Intelligence": [
        "defense:Interceptions_Int",
        "defense:Tackles_Mid 3rd",
        "defense:Tackles_Def 3rd",
        "misc:Performance_Recov",
    ],
    # Ball distribution / build-up: progressive passes, completion
    "Build-Up Vision": [
        "passing:PrgP",
        "passing:Total_Cmp%",
        "passing:Medium_Cmp%",
        "possession:Receiving_PrgR",
        "possession:Carries_PrgC",
        "possession:Carries_Mis",
    ],
    # Mistakes / errors
    "Errors": [
        "defense:Err",
        "possession:Carries_Dis",
        "misc:Performance_Off",
    ],
    # Discipline: fouls & cards
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
    ],
    # Positional awareness / recovery: ball recoveries, interceptions, reading game
    "Positioning & Recovery": [
        "misc:Performance_Recov",
        "defense:Interceptions_Int",
        "defense:Tackles_Mid 3rd",
    ],
    # Attacking contribution: key passes, progressive passes received, short assists
    "Attacking Contribution": [
        "passing:KP",
        "passing:PrgP",
        "goal_shot_creation:SCA_SCA90",
        "possession:Carries_PrgC",
    ],
},

    # === Central Midfielder (CM) ===
    "CM": {
    # Defensive awareness: tackles, interceptions, errors
    "Defensive Intelligence": [
        "defense:Tackles_Mid 3rd",
        "defense:Tackles_TklW",
        "defense:Interceptions_Int",
        "defense:Err",
    ],
    # Build-Up Vision: progressive passes, pass completion, receiving
    "Build-Up Vision": [
        "passing:PrgP",
        "passing:Total_Cmp%",
        "passing:Medium_Cmp%",
        "passing_types:Pass Types_Sw",
        "possession:Receiving_PrgR",
        "possession:Carries_PrgC",
        "possession:Carries_Mis",
    ],
    # Mistakes / errors
    "Errors": [
        "possession:Carries_Dis",
        "misc:Performance_Off",
        "defense:Err",
    ],
    # Discipline: fouls & cards
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
    ],
    # Positional awareness / recovery: ball recoveries, interceptions
    "Positioning & Recovery": [
        "misc:Performance_Recov",
        "defense:Interceptions_Int",
        "defense:Tackles_Mid 3rd",
    ],
    # Attacking Contribution: key passes, progressive passes, SCA
    "Attacking Contribution": [
        "passing:KP",
        "passing:PrgP",
        "goal_shot_creation:SCA_SCA90",
        "possession:Carries_PrgC",
        "goal_shot_creation:GCA_GCA90",
    ],
},

    # === Attacking Midfielder (AM) ===
    "AM": {
    # Creativity & Playmaking: key passes, xAG, through balls
    "Creativity & Playmaking": [
        "passing:KP",
        "passing:Pass Types_TB",
        "passing:xAG",
        "goal_shot_creation:GCA_GCA90",
        "goal_shot_creation:SCA_SCA90",
    ],
    # Build-Up & Progressive Play: progressive passes and carries
    "Build-Up & Progression": [
        "passing:PrgP",
        "possession:Receiving_PrgR",
        "possession:Carries_PrgC",
        "possession:Carries_TotDist",
    ],
    # Errors / Miscontrols: dispossessions, miscontrols, failed passes
    "Errors": [
        "possession:Carries_Mis",
        "possession:Carries_Dis",
        "misc:Performance_Off",
    ],
    # Discipline: cards, fouls, offside
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
        "misc:Performance_Off",
    ],
    # Positional Awareness / Recovery: interceptions, recoveries
    "Positioning & Recovery": [
        "misc:Performance_Recov",
        "defense:Interceptions_Int",
        "defense:Tackles_Mid 3rd",
    ],
    # Attacking Output: SCA, GCA, expected goals/assists, shot contribution
    "Attacking Output": [
        "goal_shot_creation:SCA_SCA90",
        "goal_shot_creation:GCA_GCA90",
        "shooting:Expected_xG",
        "passing:PrgP",
    ],
},

    # === Winger (W) ===
    "W": {
    # Explosiveness & Dribbling: progressive carries, take-ons, successful take-ons
    "Explosiveness & Dribbling": [
        "possession:Carries_PrgC",
        "possession:Carries_TotDist",
        "possession:Take-Ons_Att",
        "possession:Take-Ons_Succ",
        "possession:Take-Ons_Succ%",
    ],
    # Chance Creation & Crossing: SCA, crosses, key passes
    "Chance Creation & Crossing": [
        "passing:Pass Types_Crs",
        "goal_shot_creation:SCA_SCA90",
        "goal_shot_creation:GCA_GCA90",
        "passing:KP",
    ],
    # Finishing & Conversion: xG, goals per shot, shot quality
    "Finishing & Conversion": [
        "shooting:Expected_xG",
        "shooting:Standard_G/SoT",
        "shooting:Standard_SoT/90",
        "shooting:Standard_Gls",
    ],
    # Errors / Miscontrols: dispossessions, miscontrols, offside
    "Errors": [
        "possession:Carries_Mis",
        "possession:Carries_Dis",
        "misc:Performance_Off",
    ],
    # Discipline: cards, fouls
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
    ],
    # Positional Awareness / Recovery: interceptions, recoveries
    "Positioning & Recovery": [
        "misc:Performance_Recov",
        "defense:Interceptions_Int",
        "defense:Tackles_Mid 3rd",
    ],
},

    # === Center Forward (CF) ===
    "CF": {
    # Finishing & Conversion: goals, xG, shot efficiency
    "Finishing & Conversion": [
        "shooting:Standard_Gls",
        "shooting:Expected_xG",
        "shooting:Standard_G/SoT",
        "shooting:Standard_SoT/90",
    ],
    # Shot Selection & Composure: SoT%, G-xG
    "Shot Selection & Composure": [
        "shooting:Standard_SoT%",
        "shooting:Expected_G-xG",
        "shooting:Expected_np:G-xG",
    ],
    # Creativity & Assists: SCA, GCA, key passes
    "Creativity & Assists": [
        "goal_shot_creation:SCA_SCA90",
        "goal_shot_creation:GCA_GCA90",
        "passing:KP",
        "passing:xAG",
    ],
    # Duels & Physical Dominance: aerials, recoveries
    "Duels & Physical Dominance": [
        "misc:Aerial Duels_Won%",
        "misc:Aerial Duels_Won",
        "misc:Performance_Recov",
    ],
    # Errors / Miscontrols: dispossessions, miscontrols, offside
    "Errors": [
        "possession:Carries_Mis",
        "possession:Carries_Dis",
        "misc:Performance_Off",
    ],
    # Discipline: cards, fouls
    "Discipline": [
        "misc:Performance_CrdY",
        "misc:Performance_CrdR",
        "misc:Performance_2CrdY",
        "misc:Performance_Fls",
    ],
},

    # === Global fallback ===
       "ALL": {
        "playing_time": "Team Success - +/-90"
        },
}

 