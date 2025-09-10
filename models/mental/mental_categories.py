TEAM_MENTAL_MAPPING = {
    "Defending Quality" : [
    {"stat_type": "defense", "key": "Challenges_Tkl%"},            # Expected goals
        {"stat_type": "defense", "key": "Int"},      # Non-penalty goals + xAG
        {"stat_type": "defense", "key": "Clr"},          # Expected assisted goals
        {"stat_type": "defense", "key": "Blocks_Blocks"} ,     
        {"stat_type": "misc", "key": "Aerial Duels_Won%"},      
        {"stat_type": "misc", "key": "Performance_Recov"} ,     
        {"stat_type": "possession", "key": "Touches_Def Pen"}      
    ],
    "Decision Making": [
        {"stat_type": "shooting", "key": "Expected_xG"},            # Expected goals
        {"stat_type": "standard", "key": "Expected_npxG+xAG"},      # Non-penalty goals + xAG
        {"stat_type": "passing", "key": "Expected_A-xAG"},          # Expected assisted goals
        {"stat_type": "standard", "key": "Performance_Gls"},        # Goals scored
        {"stat_type": "passing", "key": "Total_Cmp%"}               # Total pass completion %
    ],
    "Initiative / Proactivity": [
        {"stat_type": "passing", "key": "PPA"},                     # Passes into penalty area
        {"stat_type": "passing", "key": "1/3"},                     # Passes to final third
        {"stat_type": "possession", "key": "Receiving_PrgR"},       # Progressive passes received
        {"stat_type": "possession", "key": "Touches_Live"}          # Open-play touches
    ],
    "Penetration / Creativity": [
        {"stat_type": "goal_shot_creation", "key": "SCA_SCA90"},    # Shot-creating actions / 90
        {"stat_type": "goal_shot_creation", "key": "GCA_GCA90"},    # Goal-creating actions / 90
        {"stat_type": "passing", "key": "KP"},                      # Key passes
        {"stat_type": "possession", "key": "Take-Ons_Succ%"},       # Successful dribbles
        {"stat_type": "possession", "key": "Touches_Att Pen"},      # Touches in attacking penalty area
        {"stat_type": "possession", "key": "Carries_CPA"}           # Carries into penalty area
    ],
    "Composure / Efficiency": [
        {"stat_type": "shooting", "key": "Standard_SoT%"},          # Shot accuracy %
        {"stat_type": "shooting", "key": "Standard_G/SoT"},         # Goals per shot on target
        {"stat_type": "shooting", "key": "Expected_G-xG"},          # Goals minus xG
        {"stat_type": "shooting", "key": "Expected_np:G-xG"}        # Non-penalty goals minus xG
    ],
    "Discipline / Risk Management": [
        {"stat_type": "standard", "key": "Performance_CrdY"},       # Yellow cards
        {"stat_type": "standard", "key": "Performance_CrdR"},       # Red cards
        {"stat_type": "defense", "key": "Err"},                     # Errors leading to shot
        {"stat_type": "misc", "key": "Performance_Off"},            # Offsides
        {"stat_type": "misc", "key": "Performance_2CrdY"},          # Second yellow cards
        {"stat_type": "misc", "key": "Performance_PKcon"},          # Penalties conceded
        {"stat_type": "possession", "key": "Carries_Dis"}           # Dispossessions
    ],
    "Team Influence / Control": [
        {"stat_type": "possession", "key": "Carries_PrgC"},         # Progressive carries
        {"stat_type": "possession", "key": "Receiving_PrgR"},       # Progressive passes received
        {"stat_type": "passing", "key": "PrgP"},                    # Progressive passes
        {"stat_type": "passing", "key": "Total_PrgDist"},           # Progressive pass distance
        {"stat_type": "goal_shot_creation", "key": "SCA Types_PassLive"} # SCA via open-play pass
    ]
}
