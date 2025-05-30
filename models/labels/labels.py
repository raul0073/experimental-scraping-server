# label mappings for different stat types from fbref soccer data stats. config to readable labels.
LABELS_CONFIG = {
    "standard": {
        # Playing Time
        "Playing Time_MP": "Matches Played",
        "Playing Time_Starts": "Starts",
        "Playing Time_Min": "Minutes Played",
        "Playing Time_90s": "90s Played",
        # Performance
        "Performance_Gls": "Goals",
        "Performance_Ast": "Assists",
        "Performance_G+A": "Goals + Assists",
        "Performance_G-PK": "Non-Penalty Goals",
        "Performance_PK": "Penalty Goals",
        "Performance_PKatt": "Penalty Attempts",
        "Performance_CrdY": "Yellow Cards",
        "Performance_CrdR": "Red Cards",
        # Expected
        "Expected_xG": "Expected Goals (xG)",
        "Expected_npxG": "Non-Penalty xG",
        "Expected_xAG": "Expected Assisted Goals (xAG)",
        "Expected_npxG+xAG": "Non-Penalty xG + xAG",
        # Progression
        "Progression_PrgC": "Progressive Carries",
        "Progression_PrgP": "Progressive Passes",
        "Progression_PrgR": "Progressive Passes Receivied",
        # Per 90 Minutes
        "Per 90 Minutes_Gls": "Goals / 90",
        "Per 90 Minutes_Ast": "Assists / 90",
        "Per 90 Minutes_G+A": "Goals + Assists / 90",
        "Per 90 Minutes_G-PK": "Non-Penalty Goals / 90",
        "Per 90 Minutes_G+A-PK": "Non-Penalty G+A / 90",
        "Per 90 Minutes_xG": "xG / 90",
        "Per 90 Minutes_xAG": "xAG / 90",
        "Per 90 Minutes_xG+xAG": "xG + xAG / 90",
        "Per 90 Minutes_npxG": "Non-Penalty xG / 90",
        "Per 90 Minutes_npxG+xAG": "Non-Penalty xG + xAG / 90",
    },
    "passing": {
        "TotDist": "Total Pass Distance",
        "PrgDist": "Progressive Pass Distance",
        "PrgP": "Progressive Passes",
        "Ast": "Assists",
        "Total_Cmp": "Total Passes Completed",
        "Total_Att": "Total Passes Attempted",
        "Total_Cmp%": "Total Pass Completion %",
        "Total_TotDist": "Total Pass Distance",
        "Total_PrgDist": "Total Progressive Distance",
        "xAG": "Expected Assisted Goals",
        "Expected_xA": "Expected Assists (xA)",
        "Expected_A-xAG": "Assists minus xAG",
        "KP": "Key Passes",
        "1/3": "Passes to Final Third",
        "PPA": "Passes into Penalty Area",
        "CrsPA": "Crosses into Penalty Area",
        "Short_Cmp": "Short Passes Completed",
        "Short_Att": "Short Passes Attempted",
        "Short_Cmp%": "Short Pass Completion %",
        "Medium_Cmp": "Medium Passes Completed",
        "Medium_Att": "Medium Passes Attempted",
        "Medium_Cmp%": "Medium Pass Completion %",
        "Long_Cmp": "Long Passes Completed",
        "Long_Att": "Long Passes Attempted",
        "Long_Cmp%": "Long Pass Completion %",
    },
    "shooting": {
        "Standard_Gls": "Goals",
        "Standard_Sh/90": "Shots per 90",
        "Standard_SoT/90": "Shots on Target per 90",
        "Standard_Sh": "Shots",
        "Standard_SoT": "Shots on Target",
        "Standard_SoT%": "Shot Accuracy %",
        "Standard_G/Sh": "Goals per Shot",
        "Standard_G/SoT": "Goals per Shot on Target",
        "Standard_Dist": "Average Shot Distance",
        "Standard_FK": "Free Kick Shots",
        "Standard_PK": "Penalty Kicks",
        "Standard_PKatt": "Penalty Kick Attempts",
        "Expected_xG": "Expected Goals (xG)",
        "Expected_npxG": "Non-Penalty xG",
        "Expected_npxG/Sh": "Non-Penalty xG per Shot",
        "Expected_G-xG": "Goals minus xG",
        "Expected_np:G-xG": "Non-Penalty Goals minus xG",
    },
    "defense": {
        "Tackles_Tkl": "Tackles",
        "Tackles_TklW": "Tackles Won",
        "Tackles_Def 3rd": "Tackles in Defensive Third",
        "Tackles_Mid 3rd": "Tackles in Middle Third",
        "Tackles_Att 3rd": "Tackles in Attacking Third",
        "Challenges_Tkl": "Challenges - Tackles",
        "Challenges_Att": "Challenges Attempted",
        "Challenges_Tkl%": "Challenge Tackle Success %",
        "Challenges_Lost": "Challenges Lost",
        "Blocks_Blocks": "Shots/Passes Blocked",
        "Blocks_Sh": "Shots Blocked",
        "Blocks_Pass": "Passes Blocked",
        "Int": "Interceptions",
        "Tkl+Int": "Tackles + Interceptions",
        "Clr": "Clearances",
        "Err": "Errors Leading to Shot",
    },
    "possession": {
        "Touches_Touches": "Touches (All)",
        "Touches_Def Pen": "Touches in Defensive Penalty Area",
        "Touches_Def 3rd": "Touches in Defensive Third",
        "Touches_Mid 3rd": "Touches in Middle Third",
        "Touches_Att 3rd": "Touches in Attacking Third",
        "Touches_Att Pen": "Touches in Attacking Penalty Area",
        "Touches_Live": "Open-Play Touches",
        "Take-Ons_Att": "Take-Ons Attempted",
        "Take-Ons_Succ": "Take-Ons Successful",
        "Take-Ons_Succ%": "Take-On Success %",
        "Take-Ons_Tkld": "Take-Ons Tackled",
        "Take-Ons_Tkld%": "Tackled on Take-On %",
        "Carries_Carries": "Carries",
        "Carries_TotDist": "Total Carry Distance",
        "Carries_PrgDist": "Progressive Carry Distance",
        "Carries_PrgC": "Progressive Carries",
        "Carries_1/3": "Carries into Final Third",
        "Carries_CPA": "Carries into Penalty Area",
        "Carries_Mis": "Miscontrols",
        "Carries_Dis": "Dispossessed",
        "Receiving_Rec": "Passes Received",
        "Receiving_PrgR": "Progressive Passes Received",
    },
    "passing_types": {
        "Att": "Total Passes Attempted",
        # Pass Types
        "Pass Types_Live": "Open-Play Passes",
        "Pass Types_Dead": "Dead-Ball Passes",
        "Pass Types_FK": "Free Kick Passes",
        "Pass Types_TB": "Through Balls",
        "Pass Types_Sw": "Switches",
        "Pass Types_Crs": "Crosses",
        "Pass Types_TI": "Throw-Ins",
        "Pass Types_CK": "Corner Kicks",
        # Corner Kick Directions
        "Corner Kicks_In": "Inswinging Corners",
        "Corner Kicks_Out": "Outswinging Corners",
        "Corner Kicks_Str": "Straight Corners",
        # Outcomes
        "Outcomes_Cmp": "Passes Completed",
        "Outcomes_Off": "Passes Offside",
        "Outcomes_Blocks": "Passes Blocked",
    },
    "goal_shot_creation": {
        "SCA_SCA": "Shot-Creating Actions",
        "SCA_SCA90": "Shot-Creating Actions / 90",
        # Shot-Creating Action Types
        "SCA Types_PassLive": "SCA via Open-Play Pass",
        "SCA Types_PassDead": "SCA via Dead-Ball Pass",
        "SCA Types_TO": "SCA via Take-On",
        "SCA Types_Sh": "SCA via Shot",
        "SCA Types_Fld": "SCA via Foul Drawn",
        "SCA Types_Def": "SCA via Defensive Action",
        # Goal-Creating Actions (GCA)
        "GCA_GCA": "Goal-Creating Actions",
        "GCA_GCA90": "Goal-Creating Actions / 90",
        # Goal-Creating Action Types
        "GCA Types_PassLive": "GCA via Open-Play Pass",
        "GCA Types_PassDead": "GCA via Dead-Ball Pass",
        "GCA Types_TO": "GCA via Take-On",
        "GCA Types_Sh": "GCA via Shot",
        "GCA Types_Fld": "GCA via Foul Drawn",
        "GCA Types_Def": "GCA via Defensive Action",
    },
    "keeper": {
        # Playing Time
        "Playing Time_MP": "Matches Played",
        "Playing Time_Starts": "Starts",
        "Playing Time_Min": "Minutes Played",
        "Playing Time_90s": "90s Played",
        # Performance
        "Performance_GA": "Goals Against",
        "Performance_GA90": "Goals Against / 90",
        "Performance_SoTA": "Shots on Target Against",
        "Performance_Saves": "Saves",
        "Performance_Save%": "Save Percentage",
        "Performance_W": "Wins",
        "Performance_D": "Draws",
        "Performance_L": "Losses",
        "Performance_CS": "Clean Sheets",
        "Performance_CS%": "Clean Sheet Percentage",
        # Penalty Kicks
        "Penalty Kicks_PKatt": "Penalties Faced",
        "Penalty Kicks_PKA": "Penalties Allowed",
        "Penalty Kicks_PKsv": "Penalties Saved",
        "Penalty Kicks_PKm": "Penalties Missed",
        "Penalty Kicks_Save%": "Penalty Save Percentage",
    },
    "keeper_adv": {
        # Goals Conceded Details
        "Goals_GA": "Goals Against",
        "Goals_PKA": "Penalties Allowed",
        "Goals_FK": "Free Kick Goals Allowed",
        "Goals_CK": "Corner Kick Goals Allowed",
        "Goals_OG": "Own Goals Conceded",
        # Expected Goals on Target (Post-Shot xG)
        "Expected_PSxG": "Post-Shot Expected Goals (PSxG)",
        "Expected_PSxG/SoT": "PSxG per Shot on Target",
        "Expected_PSxG+/-": "PSxG Difference (Saved vs. Expected)",
        "Expected_/90": "PSxG Difference per 90",
        # Launching Distribution
        "Launched_Cmp": "Launched Passes Completed",
        "Launched_Att": "Launched Passes Attempted",
        "Launched_Cmp%": "Launched Pass Completion %",
        # Passing
        "Passes_Att (GK)": "Passes Attempted (GK)",
        "Passes_Thr": "Throws Attempted",
        "Passes_Launch%": "Passes Launched %",
        "Passes_AvgLen": "Average Pass Length",
        # Goal Kicks
        "Goal Kicks_Att": "Goal Kicks Attempted",
        "Goal Kicks_Launch%": "Goal Kicks Launched %",
        "Goal Kicks_AvgLen": "Average Goal Kick Length",
        # Crosses
        "Crosses_Opp": "Crosses Faced",
        "Crosses_Stp": "Crosses Stopped",
        "Crosses_Stp%": "Cross Stop Percentage",
        # Sweeper Keeper Actions
        "Sweeper_#OPA": "Keeper Defensive Actions Outside Box",
        "Sweeper_#OPA/90": "Keeper Defensive Actions per 90",
        "Sweeper_AvgDist": "Average Distance of Defensive Actions",
    },
    "misc": {
        # Card and Discipline Stats
        "Performance_CrdY": "Yellow Cards",
        "Performance_CrdR": "Red Cards",
        "Performance_2CrdY": "Second Yellow Cards",
        # Fouls and Free Kicks
        "Performance_Fls": "Fouls Committed",
        "Performance_Fld": "Fouls Suffered",
        "Performance_Off": "Offside Calls",
        "Performance_Crs": "Crosses Attempted",
        # Defensive Contributions
        "Performance_Int": "Interceptions",
        "Performance_TklW": "Tackles Won",
        "Performance_PKwon": "Penalties Won",
        "Performance_PKcon": "Penalties Conceded",
        "Performance_OG": "Own Goals Conceded",
        "Performance_Recov": "Ball Recoveries",
        # Aerial Duels
        "Aerial Duels_Won": "Aerial Duels Won",
        "Aerial Duels_Lost": "Aerial Duels Lost",
        "Aerial Duels_Won%": "Aerial Duels Win %",
    },
    "playing_time": {
        # Overall Playing Time Stats
        "Playing Time_MP": "Matches Played",
        "Playing Time_Min": "Minutes Played",
        "Playing Time_Mn/MP": "Minutes per Match",
        "Playing Time_Min%": "Minutes Played Percentage",
        "Playing Time_90s": "90-Minute Equivalent Matches",
        # Starts and Substitutions
        "Starts_Starts": "Matches Started",
        "Starts_Mn/Start": "Minutes per Start",
        "Starts_Compl": "Completed Starts",
        "Subs_Subs": "Substitutions Made",
        "Subs_Mn/Sub": "Minutes per Substitution",
        "Subs_unSub": "Substitutions Not Made",
        # Team Success Metrics
        "Team Success_PPM": "Points per Match",
        "Team Success_onG": "Goals Scored with",
        "Team Success_onGA": "Goals Against with",
        "Team Success_+/-": "Goal Difference with",
        "Team Success_+/-90": "Goal Difference per 90 Minutes with",
        "Team Success_On-Off": "Goal Difference When On/Off",
        "Team Success (xG)_onxG": "xG with Player",
        "Team Success (xG)_onxGA": "xG Against with Player",
        "Team Success (xG)_xG+/-": "xG Difference with Player",
        "Team Success (xG)_xG+/-90": "xG Difference per 90 Minutes with",
        "Team Success (xG)_On-Off": "xG Difference When On/Off",
    },
}
