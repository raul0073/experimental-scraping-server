# WhoScored shot events on disk — spec for a shot-level xG model

All facts below were measured on the files with `.venv/Scripts/python.exe` (pandas + pyarrow); nothing in the repo was modified. Scratch scripts: `C:\Users\Admin\AppData\Local\Temp\claude\fcdfae52b650c7ae\cb07a0cd-4394-4298-b97c-9c5672eb52e1\scratchpad\inspect_ws.py`, `inspect_ws2.py`, `inspect_ws3.py` (outputs `inspect_out*.txt` beside them).

## 0. Inventory

Path pattern: `C:/prog/projects/experimental/experimental-scraping-server/data/whoscored/<league>/<season>.parquet` (raw, 30 cols) and `<season>_stamped.parquet` (raw + 7 state columns, 37 cols). Use the **stamped** files: identical rows (minus a handful of null-`game_id` rows, see 0.1) plus score/man state.

| league | season | rows (stamped) | distinct game_id | note |
|---|---|---|---|---|
| ENG-Premier League | 2324 | 606,065 | 380 | |
| | 2425 | 579,473 | 380 | |
| | 2526 | 577,884 | 380 | |
| | 2627 | 169,878 | 110 | raw 169,881; `game_id` stored as double + null `index` col |
| ESP-La Liga | 2324 | 586,770 | 380 | |
| | 2425 | 572,998 | 380 | |
| | 2526 | 577,205 | 380 | |
| | 2627 | 197,159 | 130 | raw 197,180; double `game_id` + `index` col |
| ITA-Serie A | 2324 | 568,200 | 380 | |
| | 2425 | 556,652 | 380 | |
| | 2526 | 562,672 | 380 | |
| | 2627 | 187,178 | 120 | |
| GER-Bundesliga | 2324 | 492,738 | 306 | |
| | 2425 | 479,962 | 306 | |
| | 2526 | 478,270 | 306 | |
| | 2627 | 144,689 | 90 | |
| FRA-Ligue 1 | 2324 | 479,246 | 305 | one match of 306 missing; raw 479,255; double `game_id` + `index` col |
| | 2425 | 476,172 | 306 | |
| | 2526 | 467,318 | 306 | |
| | 2627 | 158,848 | 99 | |

Total: 20 league-seasons, 6,254 matches, 149,284 shots, 16,484 goals.

**0.1 Three irregular files** (ENG 2627, ESP 2627, FRA 2324): `game_id`, `minute`, `expanded_minute`, `team_id` are arrow `double` instead of `int64`, and an all-null `index` column exists. Cause: the raw file contains 3 / 21 / 9 rows with null `game_id` and null `team` (artefact of the batch-concat path in `scripts/build_whoscored_events.py::write_events`). `stamp_event_state.py` groups by `game_id`, so those rows are silently dropped in the stamped file (hence the row gaps); **zero shots are lost**. Spec: `df = df[df.game_id.notna()]; df["game_id"] = df.game_id.astype("int64")` and ignore `index`.

## 1. Schema

Arrow schema (identical in all 20 stamped files except the 4 double columns above):

```
league string | season string | game string | game_id int64 | period string
minute int64 | second double | expanded_minute int64
type string | outcome_type string
team_id int64 | team string | player_id double | player string
x double | y double | end_x double | end_y double
goal_mouth_y double | goal_mouth_z double | blocked_x double | blocked_y double
qualifiers list<struct<type: struct<displayName: string, value: int64>, value: string>>
is_touch bool | is_shot bool (nullable) | is_goal bool (nullable) | card_type string
event_id int64 | related_event_id int64 | related_player_id double
-- stamped only --
team_goals int64 | opp_goals int64 | score_diff int64 | score_state string
man_diff int64 | man_state string | phase string
```

Pandas dtypes after `pd.read_parquet`: `is_shot`/`is_goal` come back as **object** holding `None`/`True` (arrow bool with nulls: ENG 2526 `is_shot` = {None: 568,341, True: 9,543}); `event_id`/`related_event_id` are `Int64`; `qualifiers` is object holding a **numpy.ndarray of dicts** per row. Raw files all have `is_shot`/`is_goal` as arrow `bool` and `qualifiers` as the list-of-struct (none of the "stringified" corruption described in the script docstrings survives on disk).

**Which rows are shots.** `is_shot == True` is exactly `type ∈ {Goal, MissedShots, SavedShot, ShotOnPost}` (0 shot-type rows with `is_shot` false, 0 `is_goal` rows with `type != Goal`, 0 `type==Goal` without `is_shot`). ENG 2526: SavedShot 4,978 · MissedShots 3,309 · Goal 1,045 · ShotOnPost 211 = 9,543. `outcome_type` is **'Successful' on every shot row** (all four types) — it carries no information for shots; use `type` and qualifiers. `is_goal == True` ⇔ `type == 'Goal'` (own goals included). Shots occur only in `period ∈ {FirstHalf, SecondHalf}` (no ExtraTime/PenaltyShootout rows in league play); `is_touch` is True on every shot; `player_id` and `second` are never null on shots.

Full `type` vocabulary (ENG 2526 counts): Pass 362,739, BallRecovery 30,575, BallTouch 26,492, Aerial 24,008, Clearance 21,134, Foul 16,452, TakeOn 13,511, Tackle 12,670, CornerAwarded 7,598, Dispossessed 6,575, Interception 6,289, BlockedPass 5,626, Challenge 5,213, SavedShot 4,978, Save 4,899, KeeperPickup 4,424, MissedShots 3,309, SubstitutionOff/On 3,132 each, End 2,280, Card 1,532, Start 1,520, OffsideGiven/OffsidePass/OffsideProvoked 1,175 each, FormationChange 1,129, Goal 1,045, FormationSet 760, Claim 668, Error 650, ShieldBallOpp 540, Punch 494, KeeperSweeper 479, ShotOnPost 211, Smother 98, PenaltyFaced 92, GoodSkill 68, ChanceMissed 23, CrossNotClaimed 14.

**Time.** `minute` restarts at 45 in SecondHalf; `expanded_minute` = `minute` in FirstHalf and `minute` + first-half stoppage in SecondHalf (e.g. FirstHalf ran to 48' → SecondHalf 45' has `expanded_minute` 49; observed offsets 1..35). Shots with `minute >= 90`: ~7–8% (ENG 2526: 800). Events are **not stored chronologically** — sort by (period, minute, second) as `stamp_event_state.py` does.

**Keys.** `event_id` is unique within (`game_id`, `team_id`) only (0 dupes), **not** within `game_id` (232k dupes). `related_event_id` (== the `RelatedEventId` qualifier, 6,914/6,914) points to the **same team's** event with that `event_id`: on 300 sampled shots 284 → Pass, 6 MissedShots, 5 BallTouch, 2 Tackle, 1 Interception, 1 SavedShot — i.e. the assist/key pass (or rebound source); `related_player_id` equals that event's `player_id` (300/300) → the assister. `OppositeRelatedEvent` qualifier (value = event_id) points to the **opponent's `Save` event** (300/300 sampled), for both GK saves and outfield blocks.

## 2. Coordinates

Both teams are normalised to attack the goal at **x = 100, y = 50** (per-team mean shot x is 81.8–84.5 in every file; one game: Bournemouth mean x 87.7, Liverpool 85.7). Scale 0–100 on both axes. Penalties are recorded at a fixed **(88.5, 50.0)** (92/92 in ENG 2526) → 11.5 units ≈ 11 m, so x-units ≈ 1.05 m. `y` increases toward the **attacker's left**: `BoxLeft` shots have mean y 67.6, `BoxRight` 32.3; `LowLeft` placements have mean `goal_mouth_y` 53.0, `LowRight` 47.0.

Shot `x` (ENG 2526, n=9,543): min 0.5 (own goals), p1 68.7, p5 73.5, p25 80.6, med 87.2, p75 91.5, p95 96.4, p99 97.7, max 99.6. `y`: min 0.5, p5 31.3, p25 42.7, med 50.1, p75 58.6, p95 69.3, max 99.2. Excluding own goals, min x per file is 9.5–44.0 with only 2–27 non-OG shots per season at x<50 (long-range/odd codings; keep or clip). **Own goals are coded at the scorer's own end: x ∈ [0.4, 31.5] across all files** (ENG 2526: 0.5–18.4). They must be excluded from any xG fit.

`end_x`/`end_y`: **null on 100% of shot rows** (pass endpoints only).

`goal_mouth_y`/`goal_mouth_z` (from qualifiers `GoalMouthY`/`GoalMouthZ`, present on 100% of shots): where the ball crossed (or would cross) the goal line, y on the same 0–100 pitch-width axis, z = height 0–100. Empirically the goal frame is y ∈ [44.2, 55.8], crossbar z ≈ 38–42: Goals have `goal_mouth_y` ∈ [45.4, 54.6] and z ∈ [0.6, 36.1] (100% within); ShotOnPost y ∈ [44.2, 55.8], z ≤ 41.8; SavedShot y ∈ [45.3, 54.8], z ≤ 36.7; MissedShots y ∈ [0.2, 100], z ∈ [1.4, 100]. These are **post-shot outcomes — do not use as features in a pre-shot xG model** (leakage), but they are usable for a post-shot xG / shot-quality target.

`blocked_x`/`blocked_y` (qualifiers `BlockedX`/`BlockedY`): present on **all SavedShot** (4,978) and on 564/3,309 MissedShots; never on Goal or ShotOnPost. For SavedShot *with* `Blocked` qualifier (outfield block, 2,904): blocked_x mean 88.9 (58.3–100) = where the defender blocked. For SavedShot *without* `Blocked` (GK save, 2,074): blocked_x mean 98.0 = where the keeper met it. The 564 MissedShots with blocked_x carry `MissLeft`/`MissRight` (no `Blocked`), blocked_x mean 93.4 — an off-target ball whose path was recorded. Also post-shot; exclude from features.

Zone qualifiers (exactly one per shot): BoxCentre 3,564, OutOfBoxCentre 3,000, BoxLeft 840, BoxRight 771, SmallBoxCentre 580, SmallBoxLeft 264, SmallBoxRight 249, DeepBoxRight 97, DeepBoxLeft 81, ThirtyFivePlusCentre 35, OutOfBoxDeepLeft 22, OutOfBoxRight 14, OutOfBoxDeepRight 10, OutOfBoxLeft 10, ThirtyFivePlusLeft/Right 3 each (ENG 2526). `SixYardBlock` (427) is a block flag, not a zone. Separate `Zone` qualifier with a `value` is nearly constant ('Center' 9,469, Left 33, Right 26, Back 15) — useless.

## 3. Qualifiers

Cell = `numpy.ndarray` of dicts, each exactly `{'type': {'displayName': <str>, 'value': <int Opta code>}, 'value': <str or None>}` (114,949 dicts on ENG 2526 shots, all with both keys). Flag qualifiers have `value: None`; `GoalMouthY/Z`, `BlockedX/Y`, `RelatedEventId`, `OppositeRelatedEvent`, `Zone` carry string values (note `GoalMouthZ` appears as both `'19'` and `'19.0'` — cast to float). Raw example (a SavedShot):

```
[{'type': {'displayName': 'BlockedY', 'value': 147}, 'value': '52.0'},
 {'type': {'displayName': 'Zone', 'value': 56}, 'value': 'Center'},
 {'type': {'displayName': 'GoalMouthY', 'value': 102}, 'value': '52.9'},
 {'type': {'displayName': 'OutOfBoxCentre', 'value': 18}, 'value': None},
 {'type': {'displayName': 'RightFoot', 'value': 20}, 'value': None},
 {'type': {'displayName': 'IndividualPlay', 'value': 215}, 'value': None},
 {'type': {'displayName': 'OppositeRelatedEvent', 'value': 233}, 'value': '21'},
 {'type': {'displayName': 'BlockedX', 'value': 146}, 'value': '98.9'},
 {'type': {'displayName': 'LowLeft', 'value': 76}, 'value': None},
 {'type': {'displayName': 'GoalMouthZ', 'value': 103}, 'value': '3.2'},
 {'type': {'displayName': 'RelatedEventId', 'value': 55}, 'value': '41'},
 {'type': {'displayName': 'RegularPlay', 'value': 22}, 'value': None},
 {'type': {'displayName': 'Assisted', 'value': 29}, 'value': None}]
```

**Complete set of qualifier displayNames on shot rows, all 20 files (149,284 shots):**

| group | name: count |
|---|---|
| always | GoalMouthY 149,284 · GoalMouthZ 149,284 · Zone 149,284 |
| body part (exactly 1 per shot, 0 missing in any file) | RightFoot 73,248 · LeftFoot 48,886 · Head 26,551 · OtherBodyPart 599 |
| situation (exactly 1 per shot, 0 missing; OwnGoal is additive) | RegularPlay 96,052 · FromCorner 24,317 · FastBreak 10,087 · SetPiece 9,119 · DirectFreekick 4,254 · ThrowinSetPiece 3,685 · Penalty 1,770 |
| own goal marker | OwnGoal 486 (always co-occurs with a situation: ENG 2526 combos RegularPlay+OwnGoal 21, FromCorner+OwnGoal 12, SetPiece+OG 3, ThrowinSetPiece+OG 3, FastBreak+OG 1) |
| assist / creation | Assisted 110,880 (always with RelatedEventId 110,880) · IntentionalAssist 70,080 · IndividualPlay 56,784 · KeyPass 1,341 · BigChanceCreated 705 · IntentionalGoalAssist 13 |
| shot quality / technique | BigChance 26,678 · FirstTouch 74,734 · Volley 16,992 · OneOnOne 2,803 · DirectCorner 10 |
| zone (exactly 1) | BoxCentre 56,144 · OutOfBoxCentre 49,122 · BoxLeft 13,417 · BoxRight 12,620 · SmallBoxCentre 6,341 · SmallBoxLeft 3,258 · SmallBoxRight 3,094 · DeepBoxRight 1,773 · DeepBoxLeft 1,675 · ThirtyFivePlusCentre 781 · OutOfBoxDeepLeft 295 · OutOfBoxDeepRight 258 · OutOfBoxLeft 222 · OutOfBoxRight 162 · ThirtyFivePlusRight 68 · ThirtyFivePlusLeft 54 |
| post-shot (outcome) | BlockedX/BlockedY 84,976 · OppositeRelatedEvent 73,816 · StandingSave 73,077 · Blocked 41,254 · SixYardBlock 4,768 · SavedOffline 1,184 · placements LowCentre 41,680 · LowLeft 21,093 · LowRight 17,107 · MissLeft 11,711 · MissHigh 11,270 · MissRight 10,089 · HighRight 8,470 · HighLeft 7,899 · HighCentre 5,449 |
| linkage | RelatedEventId 110,880 · OppositeRelatedEvent 73,816 |

Notes: **Cross, ThroughBall, Chipped, Longball never appear on shot rows** — they are on the *pass* rows (ENG 2526 non-shot rows: Longball 48,241, Chipped 32,234, Cross 13,771, KeyPass 6,829, IntentionalAssist 4,498). To get assist type (cross/through-ball/cut-back) join the shot to its assist pass via (`game_id`, `team_id`, `event_id == related_event_id`). `StandingSave` exists only in 2324/2425 files (+213 in ITA 2526) and is absent in 2526/2627 — a feed change; don't use it. `Blocked` only occurs on `SavedShot`: SavedShot+Blocked (2,904) = blocked by an outfield player, SavedShot without Blocked (2,074) = goalkeeper save (Save events 4,899 ≈ sum). ShotOnPost carries MissHigh/MissLeft/MissRight.

**Parsing snippet (tested against the real files):**

```python
import pandas as pd
from pathlib import Path
ROOT = Path("C:/prog/projects/experimental/experimental-scraping-server")
BODY = ["Head", "LeftFoot", "RightFoot", "OtherBodyPart"]
SIT  = ["RegularPlay", "FromCorner", "SetPiece", "DirectFreekick", "Penalty", "FastBreak", "ThrowinSetPiece"]
FLAGS = ["OwnGoal", "Penalty", "BigChance", "Assisted", "IntentionalAssist", "KeyPass", "Volley",
         "FirstTouch", "IndividualPlay", "OneOnOne", "Blocked", "SavedOffline", "DirectCorner"]
ZONES = ("SmallBox", "DeepBox", "Box", "OutOfBox", "ThirtyFivePlus")

def qnames(q):            # q is a numpy array of {'type': {'displayName', 'value'}, 'value'} dicts
    return {d["type"]["displayName"] for d in q}
def qvalue(q, name):
    for d in q:
        if d["type"]["displayName"] == name:
            return d["value"]
    return None

def load_shots(league, season):
    df = pd.read_parquet(ROOT / "data" / "whoscored" / league / f"{season}_stamped.parquet")
    df = df[df["game_id"].notna()].copy()
    df["game_id"] = df["game_id"].astype("int64")          # 3 files store it as double
    for c in ("is_shot", "is_goal"):
        df[c] = df[c].fillna(False).astype(bool)             # arrow bool-with-nulls -> object(None/True)
    sh = df[df["is_shot"]].copy()
    sh["q"] = sh["qualifiers"].map(qnames)
    sh["body_part"] = sh["q"].map(lambda s: next((b for b in BODY if b in s), None))
    sh["situation"] = sh["q"].map(lambda s: next((b for b in SIT if b in s), None))
    sh["zone"] = sh["q"].map(lambda s: next((z for z in s if z.startswith(ZONES) and z != "SixYardBlock"), None))
    for f in FLAGS:
        sh[f] = sh["q"].map(lambda s, f=f: f in s)
    sh["gm_z"] = sh["qualifiers"].map(lambda q: qvalue(q, "GoalMouthZ")).astype(float)   # == goal_mouth_z
    sh["date"] = sh["game"].str[:10]
    sh["home_team_str"] = sh["game"].str[11:].str.split("-").str[0]   # soccerdata spelling; see §5 (PSG caveat)
    # assist pass: same team, event_id == related_event_id
    passes = df[df["type"] == "Pass"][["game_id", "team_id", "event_id", "qualifiers", "x", "y", "end_x", "end_y"]]
    passes = passes.rename(columns={"event_id": "related_event_id", "qualifiers": "assist_q",
                                    "x": "a_x", "y": "a_y", "end_x": "a_end_x", "end_y": "a_end_y"})
    sh = sh.merge(passes, on=["game_id", "team_id", "related_event_id"], how="left")
    sh["assist_q"] = sh["assist_q"].map(lambda q: qnames(q) if q is not None else set())
    for f in ["Cross", "ThroughBall", "Chipped", "Longball", "KeyPass", "IntentionalAssist", "BigChanceCreated"]:
        sh["assist_" + f] = sh["assist_q"].map(lambda s, f=f: f in s)
    return sh

sh = load_shots("ENG-Premier League", "2526")
model_rows = sh[~sh["OwnGoal"] & ~sh["Penalty"]]           # 9,411 rows, 928 goals (9.86%)
```

## 4. Own goals and penalties

- **Own goal** = `is_goal == True` row carrying the `OwnGoal` qualifier, `type == 'Goal'`, `team` = the *conceding* side (scorer's team), x near own goal (0.4–31.5). 0 OwnGoal qualifiers occur outside shot rows. Credit to the opponent for scores (`stamp_event_state.py` does this; its final-score check vs WhoScored `ftScore` validates it).
- **Penalty shot** = shot row with `Penalty` qualifier (situation slot; always x=88.5,y=50). Types ENG 2526: Goal 77, SavedShot 11, MissedShots 2, ShotOnPost 2 = 92. The `Penalty` qualifier also appears on non-shot rows: `Foul` (184 = both the fouled and the fouler rows), `PenaltyFaced` (92, one per penalty, the GK's team) and `Save` (11) — filter with `is_shot`. `PenaltyFaced` count == penalty shots (92 = 92).

| league | season | own goals | pens | pen goals | pen conv |
|---|---|---|---|---|---|
| ENG | 2324 | 49 | 107 | 96 | .897 |
| ENG | 2425 | 33 | 83 | 69 | .831 |
| ENG | 2526 | 40 | 92 | 77 | .837 |
| ENG | 2627 | 14 | 22 | 18 | .818 |
| ESP | 2324 | 28 | 107 | 80 | .748 |
| ESP | 2425 | 26 | 130 | 106 | .815 |
| ESP | 2526 | 24 | 134 | 104 | .776 |
| ESP | 2627 | 13 | 43 | 33 | .767 |
| ITA | 2324 | 24 | 131 | 102 | .779 |
| ITA | 2425 | 37 | 104 | 80 | .769 |
| ITA | 2526 | 22 | 106 | 81 | .764 |
| ITA | 2627 | 15 | 28 | 20 | .714 |
| GER | 2324 | 25 | 101 | 78 | .772 |
| GER | 2425 | 25 | 82 | 57 | .695 |
| GER | 2526 | 20 | 109 | 86 | .789 |
| GER | 2627 | 8 | 21 | 11 | .524 |
| FRA | 2324 | 22 | 105 | 85 | .810 |
| FRA | 2425 | 26 | 114 | 93 | .816 |
| FRA | 2526 | 27 | 111 | 78 | .703 |
| FRA | 2627 | 8 | 40 | 32 | .800 |

Totals: 486 own goals, 1,770 penalties (1,386 scored, 78.3%).

## 5. Per-match keys and joins

- `game_id`: WhoScored/Opta match id, 7-digit int (e.g. 1903117–1903496 for ENG 2526; 2627 ids ~1,980,000–1,996,000). Same id names the cached match JSON `~/soccerdata/data/WhoScored/events/<league>_<season>/<game_id>.json` (coverage 100% for all 20 league-seasons; ESP 2627 cache has 140 JSONs vs 130 in the parquet).
- `game`: soccerdata string **`"YYYY-MM-DD Home-Away"`**, one per `game_id` (380 == 380). Examples: `2025-08-15 Liverpool-Bournemouth`, `2026-08-21 Arsenal-Coventry`, `2026-08-28 Bayern Munich-VfB Stuttgart`, `2024-08-16 Le Havre-Paris Saint-Germain`. The date prefix equals the cache `startTime` date in **100% of 6,254 games**; the first-listed team is the home side (verified against cache `home.name` on every game: 0 genuine counterexamples; the only flagged one, `Paris Saint-Germain-Paris FC`, is a split artefact). **Caveat:** the team spellings inside `game` come from the WhoScored *schedule* page and differ from the `team` column (e.g. `Manchester City`/`Man City`, `Manchester United`/`Man Utd`, `Bayern Munich`/`Bayern`, `VfB Stuttgart`/`Stuttgart`, `Atletico Madrid`/`Atletico`, `Paris Saint-Germain`/`PSG`), and the hyphen inside `Paris Saint-Germain` makes a naive `split("-")` ambiguous for 11 of 99 FRA 2627 games. Prefer the cache JSON for home/away.
- **No kickoff date/time column exists in the parquet.** Derive from: (a) `game[:10]` (date, local); (b) cache JSON `startTime` (local kickoff, e.g. `2026-08-21T20:00:00`, matches fbref `time` "20:00 (22:00)" first value — UK time for ENG; for ESP `startTime` 18:30 vs fbref local 19:30, so it is **UK local, not venue local**), plus `home.name`, `home.teamId`, `away.*`, `ftScore` `'3 : 0'`, `venueName`, `referee`, `attendance`; (c) `data/whoscored/_schedules/<league>_<season>_<yyyymmdd>.parquet` with cols `game_id:int64, date:datetime64[ns, UTC]` (UTC kickoff; present for 2627 all five leagues and 2324–2526 for ESP/ITA/GER/FRA, **not** ENG 2324–2526; covers 100% of 2627 game_ids). `build_whoscored_events.py` maps fixtures→ids only via this schedule (`played_ids`: kickoff+3h ≤ now); it never touches the fbref fixture JSON except to count played matches (`fbref_played`).
- fbref fixtures `data/fixtures/<league>/2627.json`: dict `{league, season, match_count, played_count, matches:[...]}`; each match `{date:'2026-08-21', time:'20:00 (22:00)', week, home_team, away_team, home_goals, away_goals, played, venue, referee, game_id:'2026-08-21 Arsenal-Coventry City'}` — fbref's `game_id` is **a string "date Home-Away" in fbref spelling**, not the WhoScored int. Join on date + mapped team names (or via `services/managers/metrics.py::_team_bridge`, lines ~402–420, which maps clubs by Jaccard of fixture-date sets, never by name; `_pair_shots` ~425–450 pairs WhoScored shots to Understat shots in order / by minute, 98.3% exact on ENG 2425).

**`team` column spellings, 2627 (with WhoScored `team_id`) and the fbref 2627 equivalent where it differs:**

- ENG (20): Arsenal 13, Aston Villa 24, Bournemouth 183, Brentford 189, Brighton 211, Chelsea 15, Coventry 17 (fbref *Coventry City*), Crystal Palace 162, Everton 31, Fulham 170, Hull 214 (*Hull City*), Ipswich 165 (*Ipswich Town*), Leeds 19 (*Leeds United*), Liverpool 26, Man City 167 (*Manchester City*), Man Utd 32 (*Manchester Utd*), Newcastle 23, Nottingham Forest 174 (*Nottingham*), Sunderland 16, Tottenham 30.
- ESP (20): Athletic Club 53, Atletico 63 (*Atlético Madrid*), Barcelona 65, Celta Vigo 62, Deportivo 59 (*Dep. A Coruña*), Deportivo Alaves 60 (*Alavés*), Elche 833, Espanyol 70, Getafe 819, Levante 832, Malaga 69 (*Málaga*), Osasuna 131, Racing Santander 56 (*Racing Sant*), Rayo Vallecano 64, Real Betis 54, Real Madrid 52, Real Sociedad 68, Sevilla 67, Valencia 55, Villarreal 839.
- ITA (20): AC Milan 80 (*Milan*), Atalanta 300, Bologna 71, Cagliari 78, Como 1290, Fiorentina 73, Frosinone 2732, Genoa 278, Inter 75, Juventus 87, Lazio 77, Lecce 79, Monza 269, Napoli 276, Parma Calcio 1913 24341 (*Parma*), Roma 84, Sassuolo 2889, Torino 72, Udinese 86, Venezia 85.
- GER (18): Augsburg 1730, Bayern 37 (*Bayern Munich*), Borussia Dortmund 44 (*Dortmund*), Borussia M.Gladbach 134 (*Gladbach*), Eintracht Frankfurt 45 (*Frankfurt*), Elversberg 1134, FC Koln 282 (*Köln*), Freiburg 50, Hamburg 38 (*Hamburger SV*), Hoffenheim 1211, Leverkusen 36, Mainz 219 (*Mainz 05*), Paderborn 810 (*Paderborn 07*), RBL 7614 (*RB Leipzig*), Schalke 39 (*Schalke 04*), Stuttgart 41, Union Berlin 796, Werder Bremen 42.
- FRA (18): Angers 614, Auxerre 308, Brest 2332, Le Havre 217, Le Mans 611, Lens 309, Lille 607, Lorient 146, Lyon 228, Marseille 249, Monaco 248, Nice 613, PSG 304, Paris FC 2832, Rennes 313, Strasbourg 148, Toulouse 246, Troyes 229 — **identical to fbref**.

`team_id` ↔ `team` is 1:1 within a file and `team` equals the cache JSON `home.name`/`away.name` in 100% of games, so `team_id` is the stable key to map once.

## 6. Realistic counts (stamped files)

| league | season | games | shots | shots/g | goals | goals/g | goal rate | type split (Saved/Missed/Goal/Post) | shots ex OG+pen | goals ex | rate ex |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ENG | 2324 | 380 | 10,538 | 27.7 | 1,246 | 3.28 | .118 | 5526/3564/1246/202 | 10,382 | 1,101 | .106 |
| ENG | 2425 | 380 | 9,883 | 26.0 | 1,115 | 2.93 | .113 | 5213/3351/1115/204 | 9,767 | 1,013 | .104 |
| ENG | 2526 | 380 | 9,543 | 25.1 | 1,045 | 2.75 | .110 | 4978/3309/1045/211 | 9,411 | 928 | .099 |
| ENG | 2627 | 110 | 3,032 | 27.6 | 303 | 2.75 | .100 | 1547/1135/303/47 | 2,996 | 271 | .090 |
| ESP | 2324 | 380 | 9,335 | 24.6 | 1,005 | 2.64 | .108 | 4602/3538/1005/190 | 9,200 | 897 | .098 |
| ESP | 2425 | 380 | 9,065 | 23.9 | 995 | 2.62 | .110 | 4421/3489/995/160 | 8,909 | 863 | .097 |
| ESP | 2526 | 380 | 9,510 | 25.0 | 1,024 | 2.69 | .108 | 4767/3563/1024/156 | 9,352 | 896 | .096 |
| ESP | 2627 | 130 | 3,455 | 26.6 | 364 | 2.80 | .105 | 1693/1335/364/63 | 3,399 | 318 | .094 |
| ITA | 2324 | 380 | 9,725 | 25.6 | 992 | 2.61 | .102 | 4802/3730/992/201 | 9,570 | 866 | .090 |
| ITA | 2425 | 380 | 9,250 | 24.3 | 973 | 2.56 | .105 | 4641/3450/973/186 | 9,109 | 856 | .094 |
| ITA | 2526 | 380 | 9,381 | 24.7 | 922 | 2.43 | .098 | 4724/3556/922/179 | 9,253 | 819 | .089 |
| ITA | 2627 | 120 | 3,505 | 29.2 | 379 | 3.16 | .108 | 1710/1351/379/65 | 3,462 | 344 | .099 |
| GER | 2324 | 306 | 8,522 | 27.9 | 985 | 3.22 | .116 | 4281/3096/985/160 | 8,396 | 882 | .105 |
| GER | 2425 | 306 | 7,959 | 26.0 | 955 | 3.12 | .120 | 4058/2779/955/167 | 7,852 | 873 | .111 |
| GER | 2526 | 306 | 8,130 | 26.6 | 990 | 3.24 | .122 | 4079/2890/990/171 | 8,001 | 884 | .111 |
| GER | 2627 | 90 | 2,760 | 30.7 | 305 | 3.39 | .111 | 1400/1006/305/49 | 2,731 | 286 | .105 |
| FRA | 2324 | 305 | 7,794 | 25.6 | 820 | 2.69 | .105 | 4081/2747/820/146 | 7,667 | 713 | .093 |
| FRA | 2425 | 306 | 7,655 | 25.0 | 911 | 2.98 | .119 | 3964/2619/911/161 | 7,515 | 792 | .105 |
| FRA | 2526 | 306 | 7,618 | 24.9 | 863 | 2.82 | .113 | 3799/2807/863/149 | 7,480 | 758 | .101 |
| FRA | 2627 | 99 | 2,624 | 26.5 | 292 | 2.95 | .111 | 1273/1014/292/45 | 2,576 | 252 | .098 |

Aggregate: 149,284 shots, 16,484 goals (11.0%); excluding 486 own goals and 1,770 penalties: 147,028 shots, 14,612 goals (9.94%). Second half carries ~53% of shots (e.g. ENG 2526: 5,255 vs 4,288).

## 7. Modelling implications (facts to design from)

- Pre-shot features available on every shot with zero missingness: `x`, `y` (→ distance/angle to (100,50)), `body_part`, `situation`, `zone`, `BigChance`, `FirstTouch`, `Volley`, `OneOnOne`, `IndividualPlay`, `Assisted`/`IntentionalAssist`, `FastBreak`, score/man state and `phase` from stamping, plus assist-pass geometry and `Cross`/`ThroughBall`/`Chipped`/`Longball` via the `related_event_id` join (~74% of shots have an assist pass).
- Post-shot only (exclude from pre-shot xG, use for post-shot xG): `goal_mouth_y/z`, `blocked_x/y`, `Blocked`, `SixYardBlock`, `SavedOffline`, placement qualifiers, `OppositeRelatedEvent`, `type` itself.
- Exclude own goals (`OwnGoal`, x near 0) and model penalties as a constant (~0.78).
- Blocked shots are `SavedShot` + `Blocked`, not a separate type.
- Existing xG in the repo comes from Understat joined onto these rows (`services/managers/metrics.py`), which can serve as a benchmark target for the new model.