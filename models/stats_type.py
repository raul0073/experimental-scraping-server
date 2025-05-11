from enum import Enum
from typing import Optional, Type
from pydantic import BaseModel, Field, model_serializer
from typing import Optional




class StatsOptions(str, Enum):
    STANDARD = "standard"
    KEEPER = "keeper"
    KEEPER_ADVANCED = "keeper_adv"
    SHOOTING = "shooting"
    PASSING = "passing"
    PASSING_TYPES = "passing_types"
    GOAL_SHOT_CREATION = "goal_shot_creation"
    DEFENSE = "defense"
    POSSESSION = "possession"
    PLAYING_TIME = "playing_time"
    MISCELLANEOUS = "misc"



    @property
    def description(self) -> str:
        descriptions = {
            self.STANDARD: "Basic player stats like goals, assists, cards",
            self.KEEPER: "Basic goalkeeper stats",
            self.KEEPER_ADVANCED: "Advanced goalkeeper metrics",
            self.SHOOTING: "Shooting accuracy, power, efficiency",
            self.PASSING: "Overall passing metrics",
            self.PASSING_TYPES: "Different types of passes (crosses, long balls)",
            self.GOAL_SHOT_CREATION: "Creating shots and goals opportunities",
            self.DEFENSE: "Defensive actions (tackles, interceptions)",
            self.POSSESSION: "Ball possession metrics",
            self.PLAYING_TIME: "Minutes played, matches started",
            self.MISCELLANEOUS: "Other stats (aerial duels, fouls, etc.)",
        }
        return descriptions[self]



class BaseStat(BaseModel):
    team: str = Field(alias="Team")
    players_used: Optional[int] = Field(alias="players_used_")
    games_played: Optional[float] = Field(alias="90s_")


class PassingStats(BaseStat):
    total_completed: Optional[int] = Field(alias="Total_Cmp")
    total_attempted: Optional[int] = Field(alias="Total_Att")
    total_accuracy: Optional[float] = Field(alias="Total_Cmp%")
    
    short_completed: Optional[int] = Field(alias="Short_Cmp")
    short_attempted: Optional[int] = Field(alias="Short_Att")
    short_accuracy: Optional[float] = Field(alias="Short_Cmp%")
    
    medium_completed: Optional[int] = Field(alias="Medium_Cmp")
    medium_attempted: Optional[int] = Field(alias="Medium_Att")
    medium_accuracy: Optional[float] = Field(alias="Medium_Cmp%")
    
    long_completed: Optional[int] = Field(alias="Long_Cmp")
    long_attempted: Optional[int] = Field(alias="Long_Att")
    long_accuracy: Optional[float] = Field(alias="Long_Cmp%")
    
    assists: Optional[int] = Field(alias="Ast_")
    expected_assists: Optional[float] = Field(alias="xAG_")
    key_passes: Optional[int] = Field(alias="KP_")
    passes_final_third: Optional[int] = Field(alias="1/3_")
    passes_penalty_area: Optional[int] = Field(alias="PPA_")
    progressive_passes: Optional[int] = Field(alias="PrgP_")
    @model_serializer(mode="plain")
    def serialize(self):
        return {
            "Total Completed": self.total_completed,
            "Total Attempted": self.total_attempted,
            "Total Accuracy %": self.total_accuracy,
            "Short Completed": self.short_completed,
            "Short Attempted": self.short_attempted,
            "Short Accuracy %": self.short_accuracy,
            "Medium Completed": self.medium_completed,
            "Medium Attempted": self.medium_attempted,
            "Medium Accuracy %": self.medium_accuracy,
            "Long Completed": self.long_completed,
            "Long Attempted": self.long_attempted,
            "Long Accuracy %": self.long_accuracy,
            "Assists": self.assists,
            "Expected Assists": self.expected_assists,
            "Key Passes": self.key_passes,
            "Passes into Final Third": self.passes_final_third,
            "Passes into Penalty Area": self.passes_penalty_area,
            "Progressive Passes": self.progressive_passes,
            "Team": self.team,
            "Players Used": self.players_used,
            "Games Played": self.games_played
        }
class StandardStats(BaseStat):
    goals: Optional[int] = Field(alias="Gls")
    assists: Optional[int] = Field(alias="Ast")
    goals_plus_assists: Optional[int] = Field(alias="G+A")
    non_penalty_goals: Optional[int] = Field(alias="npxG")
    shots: Optional[int] = Field(alias="Sh")
    shots_on_target: Optional[int] = Field(alias="SoT")
    yellow_cards: Optional[int] = Field(alias="CrdY")
    red_cards: Optional[int] = Field(alias="CrdR")
class KeeperStats(BaseStat):
    games_goalkeeper: Optional[int] = Field(alias="GA")
    goals_against: Optional[int] = Field(alias="GA")
    shots_on_target_against: Optional[int] = Field(alias="SoTA")
    saves: Optional[int] = Field(alias="Saves")
    save_percentage: Optional[float] = Field(alias="Save%")
    clean_sheets: Optional[int] = Field(alias="CS")
    clean_sheet_percentage: Optional[float] = Field(alias="CS%")
class KeeperAdvancedStats(BaseStat):
    goals_against: Optional[int] = Field(alias="GA")
    post_shot_xg: Optional[float] = Field(alias="PSxG")
    psxg_minus_goals: Optional[float] = Field(alias="PSxG+/-")
    psxg_per_shot_on_target: Optional[float] = Field(alias="PSxG/SoT")
    crosses_stopped_percentage: Optional[float] = Field(alias="Cmp%")
    defensive_actions_outside_penalty_area: Optional[int] = Field(alias="AvgDist")
class ShootingStats(BaseStat):
    shots: Optional[int] = Field(alias="Sh")
    shots_on_target: Optional[int] = Field(alias="SoT")
    shots_on_target_pct: Optional[float] = Field(alias="SoT%")
    goals: Optional[int] = Field(alias="Gls")
    average_shot_distance: Optional[float] = Field(alias="Dist")
    shots_free_kicks: Optional[int] = Field(alias="FK")
    penalties_scored: Optional[int] = Field(alias="PK")
    penalties_attempted: Optional[int] = Field(alias="PKatt")
    xg: Optional[float] = Field(alias="xG")
    npxg: Optional[float] = Field(alias="npxG")
class PassingTypesStats(BaseStat):
    passes_live: Optional[int] = Field(alias="Live")
    passes_dead: Optional[int] = Field(alias="Dead")
    free_kick_passes: Optional[int] = Field(alias="FK")
    through_balls: Optional[int] = Field(alias="TB")
    passes_pressured: Optional[int] = Field(alias="Press")
    switches: Optional[int] = Field(alias="Sw")
    crosses: Optional[int] = Field(alias="Crs")
    corner_kicks: Optional[int] = Field(alias="CK")
    inswinging_corners: Optional[int] = Field(alias="In")
    outswinging_corners: Optional[int] = Field(alias="Out")
    straight_corners: Optional[int] = Field(alias="Str")
class GoalAndShotCreationStats(BaseStat):
    shot_creating_actions: Optional[int] = Field(alias="SCA")
    shot_creating_actions_live: Optional[int] = Field(alias="SCA_Live")
    shot_creating_actions_dead: Optional[int] = Field(alias="SCA_Dead")
    shot_creating_actions_dribbles: Optional[int] = Field(alias="SCA_Drib")
    shot_creating_actions_fouls: Optional[int] = Field(alias="SCA_Fld")
    shot_creating_actions_defense: Optional[int] = Field(alias="SCA_Def")

    goal_creating_actions: Optional[int] = Field(alias="GCA")
    goal_creating_actions_live: Optional[int] = Field(alias="GCA_Live")
    goal_creating_actions_dead: Optional[int] = Field(alias="GCA_Dead")
    goal_creating_actions_dribbles: Optional[int] = Field(alias="GCA_Drib")
    goal_creating_actions_fouls: Optional[int] = Field(alias="GCA_Fld")
    goal_creating_actions_defense: Optional[int] = Field(alias="GCA_Def")
class DefenseStats(BaseStat):
    tackles: Optional[int] = Field(alias="Tkl")
    tackles_won: Optional[int] = Field(alias="TklW")
    tackles_defensive_third: Optional[int] = Field(alias="Def 3rd")
    tackles_middle_third: Optional[int] = Field(alias="Mid 3rd")
    tackles_attacking_third: Optional[int] = Field(alias="Att 3rd")
    blocks: Optional[int] = Field(alias="Blocks")
    interceptions: Optional[int] = Field(alias="Int")
    clearances: Optional[int] = Field(alias="Clr")
    errors: Optional[int] = Field(alias="Err")
class PossessionStats(BaseStat):
    touches: Optional[int] = Field(alias="Touches")
    touches_def_3rd: Optional[int] = Field(alias="Def 3rd")
    touches_mid_3rd: Optional[int] = Field(alias="Mid 3rd")
    touches_att_3rd: Optional[int] = Field(alias="Att 3rd")
    carries: Optional[int] = Field(alias="Carries")
    progressive_carries: Optional[int] = Field(alias="PrgC")
    dribbles_completed: Optional[int] = Field(alias="Succ")
    dribbles_attempted: Optional[int] = Field(alias="Att")
    players_dribbled_past: Optional[int] = Field(alias="Past")
    dispossessed: Optional[int] = Field(alias="Dis")
    miscontrols: Optional[int] = Field(alias="Mis")
class PlayingTimeStats(BaseStat):
    minutes_90s: Optional[float] = Field(alias="90s")
    starts: Optional[int] = Field(alias="Starts")
    minutes: Optional[int] = Field(alias="Min")
    full_matches: Optional[int] = Field(alias="Complete")
    substituted_on: Optional[int] = Field(alias="Subs")
    substituted_off: Optional[int] = Field(alias="Off")
class MiscellaneousStats(BaseStat):
    cards_yellow: Optional[int] = Field(alias="CrdY")
    cards_red: Optional[int] = Field(alias="CrdR")
    fouls: Optional[int] = Field(alias="Fls")
    fouled: Optional[int] = Field(alias="Fld")
    offsides: Optional[int] = Field(alias="Off")
    aerials_won: Optional[int] = Field(alias="Won")
    aerials_lost: Optional[int] = Field(alias="Lost")
    penalties_won: Optional[int] = Field(alias="PKwon")
    penalties_conceded: Optional[int] = Field(alias="PKcon")
    own_goals: Optional[int] = Field(alias="OG")

STAT_TYPE_CLASS_MAP: dict[str, Type[BaseModel]] = {
    "standard": StandardStats,
    "keeper": KeeperStats,
    "keeper_adv": KeeperAdvancedStats,
    "shooting": ShootingStats,
    "passing": PassingStats,
    "passing_types": PassingTypesStats,
    "goal_shot_creation": GoalAndShotCreationStats,
    "defense": DefenseStats,
    "possession": PossessionStats,
    "playing_time": PlayingTimeStats,
    "misc": MiscellaneousStats,
}