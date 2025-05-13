
SCORE_CONFIG_WEIGHTS = {
    "pros": 1.0,
    "cons": -1.0,
    "important": 2.0,
}

SCORE_CONFIG = {
    "GK": {
        "pros": {
            "keeper": ["Penalties Saved", "Crosses Stopped %", "Clean Sheet %"],
            "keeper_adv": ["Launch %"],
            "passing": ["Pass Completion %"],
           
        },
        "cons": {
            "keeper": ["Own Goals", "Defensive Errors"],
            "misc": ["Fouls Committed", "Red Cards"]
        },
        "important": {
            "keeper": ["Save Percentage"],
            "standard": ["Clean Sheets"]
        }
    },
    "DEF": {
        "pros": {
            "defense": [
                "Tackles + Interceptions", "Blocks", "Clearances", "Challenge Tackle Success %"
            ],
            "misc": ["Aerial Duels Win %"],
            "passing": ["Progressive Passes", "Total Pass Completion %", "types_Switches"],
            "possession": ["Touches in Attacking Penalty Area"]
        },
        "cons": {
            "defense": ["Errors Leading to Shot", "Own Goals"],
            "possession": ["Dispossessed", "Miscontrols"],
            "misc": ["Fouls Committed", "Red Cards"]
        },
        "important": {
            "defense": ["Tackles in Defensive Third", "Tackles Won", "Blocks"],
            "standard": ["Goals"]
        }
    },
    "MID": {
        "pros": {
            "passing": [
                "Pass Completion %",
                "Progressive Passes", "Passes into Final Third", "types_Switches", "types_Through Balls"
            ],
            "possession": [
                "Progressive Carries", "Carries into Final Third", "Touches (All)", "Touches in Attacking Penalty Area"
            ],
            "standard": ["Assists", "xG", "Goals"],
        },
        "cons": {
            "possession": ["Dispossessed", "Miscontrols"],
            "misc": ["Yellow Cards", "Fouls Committed"]
        },
        "important": {
            "goal": [
                "shot_creation_Shot-Creating Actions"
            ],
            "passing": ["Key Passes", "Expected Assists (xA)"],
            "possession": ["Carries into Penalty Area"]
        }
    },
    "FWD": {
        "pros": {
            "standard": ["Goals", "Expected Goals (xG)", "Assists", "xAG / 90"],
            "possession": ["Carries into Penalty Area", "Progressive Carries"],
            "shooting": ["Shots per 90", "Shot Accuracy %"],
            "goal": [
                "shot_creation_Shot-Creating Actions", "shot_creation_SCA via Take-On"
            ]
        },
        "cons": {
            "shooting": ["Big Chances Missed"],
            "possession": ["Dispossessed", "Miscontrols"],
            "misc": ["Fouls Committed", "Offsides"]
        },
        "important": {
            "standard": ["Goals", "xG"],
            "shooting": ["Shot Accuracy %"],
            "goal": ["shot_creation_Goal-Creating Actions / 90"]
        }
    }
}
