IMPORTANT_STATS = {
    "passing": {
        "GK": [
            "Total Pass Completion %",
            "Long Pass Completion %",
            "Total Passes Attempted",
            "Passes to Final Third",
            "Progressive Passes",
        ],
        "CB": [
            "Total Passes Completed",
            "Total Pass Completion %",
            "Long Passes Attempted",
            "Long Pass Completion %",
            "Progressive Passes",
            "Passes to Final Third",
        ],
        "FB": [
            "Short Pass Completion %",
            "Medium Pass Completion %",
            "Crosses into Penalty Area",
            "Passes into Penalty Area",
            "Progressive Passes",
        ],
        "CDM": [
            "Total Passes Completed",
            "Total Pass Completion %",
            "Key Passes",
            "Progressive Passes",
            "Passes to Final Third",
            "Assists",
            "Expected Assists (xA)",
        ],
        "MC": [
            "Total Passes Completed",
            "Total Pass Completion %",
            "Key Passes",
            "Assists",
            "Expected Assists (xA)",
            "Progressive Passes",
            "Passes to Final Third",
        ],
        "AMC": [
            "Total Passes Completed",
            "Total Pass Completion %",
            "Key Passes",
            "Assists",
            "Expected Assists (xA)",
            "Progressive Passes",
            "Passes to Final Third",
        ],
        "AW": [
            "Assists",
            "Key Passes",
            "Expected Assists (xA)",
            "Crosses into Penalty Area",
            "Passes into Penalty Area",
        ],
        "WB": [
            "Assists",
            "Key Passes",
            "Expected Assists (xA)",
            "Crosses into Penalty Area",
            "Passes into Penalty Area",
        ],
        "CF": [
            "Assists",
            "Expected Assists (xA)",
            "Key Passes",
            "Passes into Penalty Area",
        ],
    }
}

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

#     "GK": {
#         "pros": {
#             "keeper": ["Penalties Saved"],
#             "standard": ["Clean Sheets"],
#             "passing": ["Pass Completion %"]
#         },
#         "cons": {
#             "keeper" : ["adv_Penalties Allowed", "adv_Corner Kick Goals Allowed"],
#              "misc" : ["Fouls Committed", "Red Cards"]
#              },
        
#         "important": {
#             "keeper": ["Save Percentage", "Wins"]
#         }
#     },
#     "DEF": {
#         "pros": {
#             "defense": ["Tackles + Interceptions", "Blocks", "Challenge Tackle Success %"],
#             "misc": ["Aerial Duels Win %"],
#             "passing": ["Progressive Passes", "Total Pass Completion %", "types_Switches"]
#         },
#         "cons": {
#             "defense" : ["Errors Leading to Shot"],
#             "possession" : ["Dispossessed", "Miscontrols"],
#             "misc" : ["Fouls Committed", "Red Cards"]
#             },
#         "important": {
#             "defense": ["Tackles in Defensive Third", "Tackles Won"]
#         }
#     },
#     "MID": {
#         "pros": {
#             "passing": ["Key Passes", "Expected Assists (xA)", "Progressive Passes"],
#             "standard": ["Assists"],
#             "possession": ["Progressive Carries"]
#         },
#         "cons": {},
#         "important": {
#             "passing": ["Key Passes"]
#         }
#     },
#     "FWD": {
#         "pros": {
#             "standard": ["Goals", "Expected Goals (xG)", "Assists"],
#             "possession": ["Carries into Penalty Area"],
#             "goal_shot_creation": ["Shot-Creating Actions"]
#         },
#         "cons": {},
#         "important": {
#             "standard": ["Goals"]
#         }
#     }
# }