from typing import List


POSSIBLE_PLAYER_TABLES: List[str] = ['standard', 'keeper', 'keeper_adv', 'shooting', 'passing', 'passing_types', 'goal_shot_creation', 'defense', 'possession', 'playing_time', 'misc']
IDENTITY_COLS = {
    "player", "team", "squad", "season", "league", "competition", "comp",
    "nation", "pos", "age", "born"
}
LEAGUE_NAME_MAP = {
    "ENG-Premier League": "English Premier League",
    "ESP-La Liga": "Spanish La Liga",
    "ITA-Serie A": "Italian Serie A",
    "GER-Bundesliga": "German Bundesliga",
    "FRA-Ligue 1": "French Ligue 1",
}