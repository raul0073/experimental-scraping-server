# WhoScored ↔ Understat join spec and Understat xG shape

Repo: `C:/prog/projects/experimental/experimental-scraping-server` (read-only; nothing modified). All numbers below come from scripts under `C:/Users/Admin/AppData/Local/Temp/claude/fcdfae52b650c7ae/cb07a0cd-4394-4298-b97c-9c5672eb52e1/scratchpad/` (`p1_understat.py`, `p1b_understat_nulls.py`, `p3_fixtures.py`, `p5_parquet.py`, `p5b_ws_teams.py`, `p5d_overlap_ordered.py`, `p5e_hull.py`, `p6_laliga_bad.py`, `p7_status.py`), run with `.venv/Scripts/python.exe -I` and `sys.stdout.reconfigure(encoding="utf-8")` (note: `-I` ignores `PYTHONIOENCODING`, so set encoding in-script).

## 0. One-paragraph answer

Understat match files already carry **fbref-canonical team names and the fbref fixture date** (the writer `services/understat/understat_service.py` remaps Understat raw names through `data/config/team_name_map.json` and overrides `date` with the fixtures date for the same ordered `(home_team, away_team)` pair). WhoScored event parquets carry WhoScored *short* names in `team` and WhoScored *long* names in the `game` label; neither is canonical and **no WhoScored→canonical map exists in the repo** (the only join code, `build_whoscored_events.py`, joins by *counts*, not names). The reliable join key is **ordered (canonical home, canonical away) within a season**, with WhoScored home/away orientation taken from the soccerdata match-doc cache `~/soccerdata/data/WhoScored/events/<league>_<season>/<game_id>.json` (`home.name`, `away.name`, `startTime`, `ftScore`), plus a 29-entry WS-short→canonical map (given in §2.3, learned by date+score voting, 100% coverage for 2526/2627). With that, 2526 joins 100% in all five leagues (1752/1752, dates and scores agree exactly) and 2627 joins every Understat match (431/431) — the 119 WhoScored-only games are simply after Understat's last date 2026-10-31, plus 4 La Liga non-FT docs.

---

## 1. Understat files — `data/understat/<league>/<season>.json`

### 1.1 File schema (identical across all 13 seasons × 5 leagues)

Top level: `{"league": str, "season": "YYyy", "match_count": int, "matches": [...]}`. Subfolders `players/`, `rosters/`, `shots/` exist alongside (not match-level xG).

Match record — **17 keys, present on every row, every season** (`missing_keys={}` for all 65 files):

| key | type | source column (soccerdata `read_team_match_stats`) | notes |
|---|---|---|---|
| `date` | `"YYYY-MM-DD"` | fbref fixtures date for the `(home_team, away_team)` pair, else Understat date | **sort/cutoff key for the whole stack** |
| `understat_date` | `"YYYY-MM-DD"` | `date` | raw Understat date; not read by any model |
| `home_team`, `away_team` | str | `home_team`/`away_team` → `team_name_map` | canonical (fbref) spelling |
| `home_goals`, `away_goals` | int | | |
| `home_xg`, `away_xg` | float | `home_xg`/`away_xg` | |
| `home_npxg`, `away_npxg` | float | `home_np_xg`/`away_np_xg` | |
| `home_ppda`, `away_ppda` | float | `home_ppda`/`away_ppda` | **2 rows None in history** (FRA 1617 ×1, GER 2425 ×1) |
| `home_deep`, `away_deep` | int | `*_deep_completions` | |
| `home_xpts`, `away_xpts` | float | `*_expected_points` | |
| `understat_game_id` | int | `game_id` | Understat global match id (e.g. 31267) |

Sample (EPL 2627, last played):
```json
{"date": "2026-10-31", "understat_date": "2026-10-31", "home_team": "Aston Villa", "away_team": "Fulham",
 "home_goals": 1, "away_goals": 1, "home_xg": 2.24562, "away_xg": 2.76757, "home_npxg": 1.48445, "away_npxg": 2.76757,
 "home_ppda": 29.454545454545453, "away_ppda": 12.095238095238095, "home_deep": 1, "away_deep": 13,
 "home_xpts": 1.0117, "away_xpts": 1.7551, "understat_game_id": 31267}
```
Files contain **only played matches** (0 unplayed rows anywhere; every row has non-None xG).

### 1.2 Seasons present and counts

All five leagues: `1415 … 2627` (13 files each). Counts: EPL/ESP/ITA 380 per full season; GER 306; FRA 380 through 2223, 306 from 2324 (18 teams), **FRA 1920 = 279** (COVID-truncated).

### 1.3 2627 state (Understat dark since 2026-11-01)

| league | 2627 rows | first | **last `understat_date`** | last `date` |
|---|---|---|---|---|
| ENG-Premier League | 88 | 2026-08-21 | 2026-10-31 | 2026-10-31 |
| ESP-La Liga | 104 | 2026-08-15 | 2026-10-31 | 2026-10-31 |
| FRA-Ligue 1 | 76 | 2026-08-21 | 2026-10-31 | **2027-03-06** (see trap below) |
| GER-Bundesliga | 70 | 2026-08-28 | 2026-10-31 | 2026-10-31 |
| ITA-Serie A | 93 | 2026-08-22 | 2026-10-31 | 2026-10-31 |

**Trap — FRA 2627 `understat_game_id` 31948**: Understat lists `PSG` home vs `Rennes` away on 2026-08-23 (2-2), but fbref/WhoScored have **Rennes home** that day (`'2026-08-23 Rennes-Paris SG'`); the pair-based fixture override therefore stamped `date = 2027-03-06` (the return leg). This row sits in the *future* for every `m["date"] < cutoff` filter in the stack and will be excluded until March 2027, and would then be counted with flipped home/away. `date != understat_date` counts overall: ESP 2526 ×1, FRA 2526 ×8, FRA 2627 ×3 (incl. 31948), GER 2425 ×1, ITA 2425 ×1 — the others are legitimate ±1-day reschedule corrections.

---

## 2. Team-name mapping

### 2.1 Three spelling systems in play

| system | where | example (EPL / GER) |
|---|---|---|
| **canonical = fbref** (after `FBREF_TEAM_ALIASES = {"Paris SG": "PSG"}` in `services/fbref/fixtures/fixtures_service.py:21`) | `data/fixtures/*`, `data/understat/*` (post-map), predictions, history, zones | `Manchester Utd`, `Nottingham`, `Hull City` / `Bayern Munich`, `Köln`, `Gladbach` |
| **Understat raw** | only inside `UnderstatService.build()` before mapping | `Manchester United`, `Nottingham Forest`, `Hull` / `Bayern Munich`, `FC Cologne`, `Borussia M.Gladbach` |
| **WhoScored short** | parquet `team` column; cache `home.name`/`away.name` | `Man Utd`, `Nottingham Forest`, `Hull` / `Bayern`, `FC Koln`, `Borussia M.Gladbach` |
| **WhoScored long** | parquet `game` label `"YYYY-MM-DD Home-Away"` (from `ws.read_schedule()`) | `Manchester United`, `Hull` / `Bayern Munich`, `FC Koln` |

### 2.2 Existing maps and what they map

- **`data/config/team_name_map.json`** — direction **Understat raw → canonical**, keyed by league. Used by `load_name_map()` in `services/understat/understat_service.py:191` and applied in `build()` (`name_map.get(home_raw, home_raw)`, line 53) and `build_players()`. Learned by `UnderstatService.learn_name_map()` (line 129): votes `(date, home_goals, away_goals)` collisions between Understat and fbref fixtures, requires ≥3 votes, merges via `merge_name_map()`. **Do not apply it to WhoScored names** — e.g. it maps `"Verona"→"Hellas Verona"` and `"Nottingham Forest"→"Nottingham"` which coincidentally fit WS, but `"Manchester United"→"Manchester Utd"` is Understat-raw/WS-long, while WS-short says `"Man Utd"`; `"FC Cologne"` vs WS `"FC Koln"`; `"RasenBallsport Leipzig"` vs WS `"RBL"`.
- **`data/config/market_team_names.json`** — football-data.co.uk → canonical (market odds only; `services/market/football_data.assert_names` fails loudly on unmapped). Not relevant to WS/Understat.
- **`services/understat/*`**: no other maps. `rosters_service.py`, `shot_events_service.py` use the same `load_name_map`.
- **`scripts/build_whoscored_events.py`**: **no name join at all.** It decides what to fetch by *counting*: `fbref_played()` (line 67) reads fixtures `played_count`; `schedule_for()` (line 82) caches `ws.read_schedule()[["game_id","date"]]` to `data/whoscored/_schedules/<league>_<season>_<YYYYMMDD>.parquet`; `played_ids()` (line 167) picks WhoScored numeric ids by date ≤ now-3h. Nothing maps WS names to fixtures.
- **`scripts/stamp_event_state.py`**: `verify()` (line 105) checks the reconstructed score against the cache JSON `d["home"]["name"]`, `d["ftScore"]` — explicitly "because the cache uses the same team names as the events — no name mapping".
- **`scripts/build_team_web.py`**: `per_match()` (line 164) groups the stamped parquet by `game_id` and labels rows with WS `team`; it never joins to Understat or fixtures by name (`crest_map()`/`_tokens()` only fuzzy-match crest filenames). Serving layer `build_injury_web.align()` has a token-prefix fuzzy matcher (WS preview long names → WS short names) — not canonical either.
- **`services/zones/*`**: `zones_engine._collect_team_matches` joins Understat shots to Understat matches on `(date, home_team, away_team)` — both already canonical; no WS involvement. `player_layer.py` reads `data/understat/.../players`.
- Experiments: `scripts/experiment_predictor_stack_epl.py:70` has a hand map "Understat names → WhoScored names. Only four differ in the Premier League" (EPL-only, one-off); `experiment_layered.py:142` comments "layers are keyed on WhoScored names; the stack speaks Understat".

### 2.3 Map to use for WhoScored → canonical (not in repo; learned here, 100% coverage of 2526+2627)

Learned in `p5d_overlap_ordered.py` by voting `(startTime[:10], ftScore)` against Understat `(date|understat_date, home_goals, away_goals)` with exactly one candidate, ≥3 votes. Identity entries omitted; everything not listed is spelled identically.

```json
{
 "ENG-Premier League": {"Nottingham Forest": "Nottingham", "Hull": "Hull City", "Coventry": "Coventry City",
   "Man City": "Manchester City", "Man Utd": "Manchester Utd", "Ipswich": "Ipswich Town", "Leeds": "Leeds United"},
 "ESP-La Liga": {"Atletico": "Atlético Madrid", "Real Oviedo": "Oviedo", "Deportivo Alaves": "Alavés",
   "Racing Santander": "Racing Sant", "Malaga": "Málaga", "Deportivo": "Dep. A Coruña"},
 "FRA-Ligue 1": {},
 "GER-Bundesliga": {"Hamburg": "Hamburger SV", "Borussia Dortmund": "Dortmund", "FC Koln": "Köln", "Schalke": "Schalke 04",
   "RBL": "RB Leipzig", "Borussia M.Gladbach": "Gladbach", "FC Heidenheim": "Heidenheim", "Eintracht Frankfurt": "Frankfurt",
   "Paderborn": "Paderborn 07", "St. Pauli": "St Pauli", "Bayern": "Bayern Munich", "Mainz": "Mainz 05"},
 "ITA-Serie A": {"Parma Calcio 1913": "Parma", "Verona": "Hellas Verona", "AC Milan": "Milan"}
}
```
Teams present only in 2526 (relegated) that are identical in both: Burnley, West Ham, Wolves, Girona, Mallorca, Metz, Nantes, Wolfsburg, Cremonese, Pisa. WS-short → WS-long (label) differences, in case you parse the `game` label instead: EPL `Man City→Manchester City`, `Man Utd→Manchester United`; ESP `Atletico→Atletico Madrid`, `Deportivo→Deportivo de A Coruna`; FRA `PSG→Paris Saint-Germain` (hyphen inside a name — do not split the label on `-`); GER `Hamburg→Hamburger SV`, `Stuttgart→VfB Stuttgart`, `Schalke→Schalke 04`, `RBL→RB Leipzig`, `Leverkusen→Bayer Leverkusen`, `Bayern→Bayern Munich`, `Mainz→Mainz 05`.

Five differing-spelling examples per league (Understat raw → canonical ← WhoScored short):

| league | Understat raw | canonical | WhoScored short |
|---|---|---|---|
| ENG | Manchester United / Nottingham Forest / Wolverhampton Wanderers / Hull / Leeds | Manchester Utd / Nottingham / Wolves / Hull City / Leeds United | Man Utd / Nottingham Forest / Wolves / Hull / Leeds |
| ESP | Atletico Madrid / Alaves / Deportivo La Coruna / Real Oviedo / Malaga | Atlético Madrid / Alavés / Dep. A Coruña / Oviedo / Málaga | Atletico / Deportivo Alaves / Deportivo / Real Oviedo / Malaga |
| ITA | AC Milan / Verona / Parma Calcio 1913 (only 3 differ) | Milan / Hellas Verona / Parma | AC Milan / Verona / Parma Calcio 1913 |
| GER | Bayer Leverkusen / FC Cologne / RasenBallsport Leipzig / Borussia M.Gladbach / St. Pauli | Leverkusen / Köln / RB Leipzig / Gladbach / St Pauli | Leverkusen / FC Koln / RBL / Borussia M.Gladbach / St. Pauli |
| FRA | Paris Saint Germain / Saint-Etienne (only 2 in map) | PSG / Saint-Étienne | PSG (short) = canonical; all 20 WS short names identical to canonical |

---

## 3. Fixtures — `data/fixtures/<league>/2627.json`

Writer: `services/fbref/fixtures/fixtures_service.py` (`FixturesService.build()` ← soccerdata `FBref.read_schedule()`), driven by `scripts/build_fixtures.py`. Top level `{"league","season","match_count","played_count","matches"}`; full schedule including unplayed (EPL 380 rows/110 played; ESP 380/130; FRA 306/99; GER 306/90; ITA 380/120 as of 2026-11-25).

Row keys (11, all rows): `date` (ISO), `time` (`"20:00 (22:00)"`), `week` (int), `home_team`, `away_team` (fbref spelling after `FBREF_TEAM_ALIASES`), `home_goals`/`away_goals` (int or None), `played` (bool = goals not None), `venue`, `referee`, `game_id`.

```json
{"date": "2026-08-21", "time": "20:00 (22:00)", "week": 1, "home_team": "Arsenal", "away_team": "Coventry City",
 "home_goals": 3, "away_goals": 0, "played": true, "venue": "Emirates Stadium", "referee": "Thomas Bramall",
 "game_id": "2026-08-21 Arsenal-Coventry City"}
```

**`game_id` is NOT WhoScored-compatible.** It is fbref's `game` string (`_clean_str(row.get("game"))`, line 95), form `"YYYY-MM-DD Home-Away"` using *un-aliased* fbref names (FRA: `"2026-08-23 Rennes-Paris SG"` while `home_team` is `"PSG"`). WhoScored `game_id` is Opta's numeric match id (e.g. `1983546`), and WhoScored's own `game` label uses WS long names (`"2026-08-21 Arsenal-Coventry"`). Nothing in `build_whoscored_events.py`/`stamp_event_state.py` stamps a WhoScored id onto fixtures or vice versa.

Team spelling convention: **fbref** (= canonical = Understat-file spelling). Verified: 2627 fixtures team set equals the Understat 2627 team set in all five leagues.

---

## 4. How the prediction stack consumes Understat

All consumers load via `UnderstatService.load(league, season)` → the dict above, then iterate `data["matches"]`.

| consumer | keys read | filter / None handling |
|---|---|---|
| `services/predictions/form_model.py` `FormModel.__init__` (l.38-54) | `date`, `home_team`, `away_team`, `home_xg`, `away_xg` | concatenates seasons, `rows.sort(key=m["date"])`, keeps `m.get("home_xg") is not None`; `ratings_before(date)` breaks at `m["date"] >= date` (strings compared, so `date` must be ISO and **sorted**). Does not read goals. |
| `services/predictions/draw_model.py` `rolling_stats` (l.47) | `date`, `home_team`, `away_team`, `home_goals`, `away_goals`, `home_ppda`, `away_ppda` | skips `home_goals is None`; ppda via `.get`, `None` tolerated (falls back to 10.0 when no ppda at all). `season_context` (l.80): `date`, teams, goals (None → skipped). `train` (l.137): `home_goals is None` → skip; needs `FormModel` ratings with `n >= MIN_MATCHES`. |
| `services/predictions/history_service.py` `grade` (l.79) | `home_team`, `away_team`, `home_xg`, `away_xg` | builds `xg_res[(league, home, away)] = (home_xg, away_xg)` for `home_xg is not None`; score comes from **fixtures**, not Understat; tries flipped pair; `real_xg`/`xg_hit` stay None and are backfilled on later passes (`need_xg`). Key = canonical names from the recorded prediction. |
| `scripts/build_process_elo.py` `matches_from_understat` (l.178) | `date`, `home_team`, `away_team`, `home_goals`, `away_goals`, `home_xg`, `away_xg`, `understat_game_id` | skips rows where goals or xg None; `int()`/`float()` casts; `game_id = m.get("understat_game_id")` (None allowed); `kick = str(m["date"])[:10]`. |
| `services/predictions/form_sheet.py` `_timeline` (l.28) | all + injects `"season": s`; reads `date`, teams, goals (`int()` cast) | skips `home_goals is None` |
| `services/predictions/prediction_service.py` (l.217-224) | passes `season_matches` to `DrawModel.rolling_stats/season_context` → same keys as draw_model | |
| `services/zones/zones_engine.py` `_collect_team_matches` (l.158) | `date`, `home_team`, `away_team`, `home_ppda`/`away_ppda`, `home_deep`/`away_deep` | keyed `(date, home_team, away_team)` against shot files; `.get` → None tolerated |

**Contract for an Understat-shaped row** (minimum for every consumer to accept it):

- Required non-None: `date` (ISO `YYYY-MM-DD`, sortable, must equal the fixtures date for the ordered pair to join zones/history), `home_team`, `away_team` (canonical fbref spelling).
- Needed for a row to *count*: `home_xg`, `away_xg` (float; None → silently dropped by form_model, history, process_elo) and `home_goals`, `away_goals` (int; None → dropped by draw_model, form_sheet, process_elo, zones context).
- May be None: `home_ppda`, `away_ppda`, `home_deep`, `away_deep`, `understat_game_id`.
- Never read by the stack (safe to fill with None/omit, but present in every real file): `understat_date`, `home_npxg`, `away_npxg`, `home_xpts`, `away_xpts`. Note `history_service`/`form_model` use `m.get("home_xg")` but `draw_model`/`form_sheet` use `m["home_goals"]` (KeyError if absent) — carry all 17 keys to be safe.

---

## 5. Overlap WhoScored ↔ Understat (2526, 2627)

### 5.1 WhoScored side

Stamped parquet `data/whoscored/<league>/<season>_stamped.parquet` (39 columns: `league, season, game, game_id, period, minute, second, expanded_minute, type, outcome_type, team_id, team, player_id, player, x, y, end_x, end_y, goal_mouth_y, goal_mouth_z, blocked_x, blocked_y, qualifiers(list<struct>), is_touch, is_shot, is_goal, card_type, event_id, related_event_id, related_player_id, index, team_goals, opp_goals, score_diff, score_state, man_diff, man_state, phase`; the last 7 are the stamp). `game_id` dtype is `int64` in most files but **`float64` in EPL 2627 and ESP 2627** (cast with `int()`). Home/away orientation and final score are **not** in the parquet columns; take them from the cache doc (`d["home"]["name"]`, `d["away"]["name"]`, `d["startTime"]`, `d["ftScore"]` e.g. `"3 : 0"`, `d["statusCode"]`, `d["elapsed"]`). Cache coverage: 100% of parquet game_ids have a doc in all 10 league-seasons.

Reconstructing the score from the parquet alone (`max(team_goals)` per team) was **unreliable** — it disagreed with Understat on ~45% of 2526 rows in a first pass; use `ftScore` or `stamp_event_state._final_from()` (own-goal aware).

### 5.2 Join recipe that ran (`p5d_overlap_ordered.py`)

```python
w = {"date": d["startTime"][:10], "home": d["home"]["name"], "away": d["away"]["name"], hg, ag from d["ftScore"]}
key = (WS2CANON.get(w["home"], w["home"]), WS2CANON.get(w["away"], w["away"]))   # map from §2.3
m = {(m["home_team"], m["away_team"]): m for m in understat[season]["matches"]}.get(key)
```

### 5.3 Results

| league | season | WS games | US matches | **in both** | ws.startTime == us.`date` | == `understat_date` | == fixtures.date | score agrees | WS-only | US-only |
|---|---|---|---|---|---|---|---|---|---|---|
| ENG | 2526 | 380 | 380 | 380 | 380 | 380 | 380 | 380 | 0 | 0 |
| ENG | 2627 | 110 | 88 | 88 | 88 | 88 | 88 | 88 | 22 (2026-11-01..11-23) | 0 |
| ESP | 2526 | 380 | 380 | 380 | 380 | 379 | 380 | 380 | 0 | 0 |
| ESP | 2627 | 130 | 104 | 104 | 104 | 104 | 104 | 101 | 26 (10-10, 11-01..11-23) | 0 |
| FRA | 2526 | 306 | 306 | 306 | 306 | 298 | 306 | 306 | 0 | 0 |
| FRA | 2627 | 99 | 76 | 75 | 75 | 73 | 75 | 75 | 24 (08-23 Rennes-PSG + 11-01..11-22) | 1 (gid 31948, §1.3) |
| GER | 2526 | 306 | 306 | 306 | 306 | 306 | 306 | 306 | 0 | 0 |
| GER | 2627 | 90 | 70 | 70 | 70 | 70 | 70 | 70 | 20 (11-01..11-22) | 0 |
| ITA | 2526 | 380 | 380 | 380 | 380 | 380 | 380 | 380 | 0 | 0 |
| ITA | 2627 | 120 | 93 | 93 | 93 | 93 | 93 | 93 | 27 (11-01..11-23) | 0 |

Dates: WhoScored `startTime[:10]` agrees with Understat `date` (the fbref-overridden one) on **100%** of joined rows; it disagrees with raw `understat_date` on 1 (ESP 2526) + 8 (FRA 2526) + 2 (FRA 2627) rows — so join on `date`, not `understat_date`. The parquet `game` label date equals `startTime[:10]` on every row.

WS-only games are all **after Understat's last date 2026-10-31**, except these ESP 2627 anomalies (`p7_status.py`, all other 2526/2627 docs are `statusCode 6`, elapsed `FT`/`FIN`):

| game_id | match | statusCode / elapsed | events in parquet | note |
|---|---|---|---|---|
| 1994150 | 2026-09-20 Atletico-Real Madrid | 3 / `81'` | 1290 | truncated live doc; WS score 2:0 vs Understat/fixtures 2-1 (**the 3 "score mismatches"**) |
| 1994152 | 2026-09-20 Deportivo-Real Betis | 1 / `''` | 2 | pre-match doc, `score="vs"`, only 2 FormationSet rows |
| 1994158 | 2026-09-20 Villarreal-Levante | 1 / `''` | 2 | same |
| 1994172 | 2026-10-10 Rayo Vallecano-Athletic Club | 5 / `Abd` | 230 | abandoned; replayed 2026-12-09 per fixtures (0-0), Understat has no row |

Recommendation for the calibration set: accept a WhoScored match only when the cache doc has `statusCode == 6` (and optionally `events >= ~1000`; medians 1486-1606/game, non-anomalous minimum 410), then join on ordered canonical pair within season, verify `ftScore == (home_goals, away_goals)` as a guard. That yields 1752 matched 2526 matches and 430 matched 2627 matches (431 minus the Rennes-PSG flip) across the five leagues, each with Understat `home_xg/away_xg/npxg/ppda/deep/xpts` per side.