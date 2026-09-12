# Zone-config stat coverage vs post-2025 data reality

Recovered zone config (commit 12f98ee) requires the stats below.
fbref lost advanced data (defense/possession/passing/GCA tables, xG) — status per key:

## All required keys across zones

| required stat | status |
|---|---|
| Blocked Passes | ❌ GONE (no fbref/Understat equivalent) |
| Blocks | ❌ GONE (no fbref/Understat equivalent) |
| Carries | ❌ GONE (no fbref/Understat equivalent) |
| Carries into Final Third | ❌ GONE (no fbref/Understat equivalent) |
| Carries into Penalty Area | ❌ GONE (no fbref/Understat equivalent) |
| Clearances | ❌ GONE (no fbref/Understat equivalent) |
| Dispossessed | ❌ GONE (no fbref/Understat equivalent) |
| Dribbles Completed | ❌ GONE (no fbref/Understat equivalent) |
| Expected_PSxG | ❌ GONE (no fbref/Understat equivalent) |
| Interceptions | ✅ misc: Performance - Int |
| Long Passes Completed | ❌ GONE (no fbref/Understat equivalent) |
| Miscontrols | ❌ GONE (no fbref/Understat equivalent) |
| Pass Completion % | ❌ GONE (no fbref/Understat equivalent) |
| Passes into Final Third | ❌ GONE (no fbref/Understat equivalent) |
| Progressive Carries | ❌ GONE (no fbref/Understat equivalent) |
| Progressive Passes | ❌ GONE (no fbref/Understat equivalent) |
| Progressive Passes Received | ❌ GONE (no fbref/Understat equivalent) |
| Save Percentage | ✅ keeper: Performance - Save% |
| Shot-Creating Actions | ❌ GONE (no fbref/Understat equivalent) |
| Shots on Target | ✅ shooting: Standard - SoT |
| Tackles + Interceptions | ✅ misc: TklW + Int (derivable) |
| Tackles Won | ✅ misc: Performance - TklW |
| Tackles in Defensive Third | ❌ GONE (no fbref/Understat equivalent) |
| Take-Ons | ❌ GONE (no fbref/Understat equivalent) |
| Tkl+Int | ❌ GONE (no fbref/Understat equivalent) |
| Touches_Def 3rd | ❌ GONE (no fbref/Understat equivalent) |
| xG | ✅ UNDERSTAT: xg (per match, aggregatable) |

**6 mappable / 21 gone** of 27 distinct keys.

## Available now

### fbref team tables (for + against): standard, keeper, shooting, playing_time, misc

- **standard**: players_used, Age, Poss, Playing Time - MP, Playing Time - Starts, Playing Time - Min, Playing Time - 90s, Performance - Gls, Performance - Ast, Performance - G+A, Performance - G-PK, Performance - PK, Performance - PKatt, Performance - CrdY, Performance - CrdR, Per 90 Minutes - Gls, Per 90 Minutes - Ast, Per 90 Minutes - G+A, Per 90 Minutes - G-PK, Per 90 Minutes - G+A-PK
- **keeper**: players_used, Playing Time - MP, Playing Time - Starts, Playing Time - Min, Playing Time - 90s, Performance - GA, Performance - GA90, Performance - SoTA, Performance - Saves, Performance - Save%, Performance - W, Performance - D, Performance - L, Performance - CS, Performance - CS%, Penalty Kicks - PKatt, Penalty Kicks - PKA, Penalty Kicks - PKsv, Penalty Kicks - PKm, Penalty Kicks - Save%
- **shooting**: players_used, 90s, Standard - Gls, Standard - Sh, Standard - SoT, Standard - SoT%, Standard - Sh/90, Standard - SoT/90, Standard - G/Sh, Standard - G/SoT, Standard - PK, Standard - PKatt
- **playing_time**: players_used, Age, Playing Time - MP, Playing Time - Min, Playing Time - Mn/MP, Playing Time - Min%, Playing Time - 90s, Starts - Starts, Starts - Mn/Start, Starts - Compl, Subs - Subs, Subs - Mn/Sub, Subs - unSub, Team Success - PPM, Team Success - onG, Team Success - onGA, Team Success - +/-, Team Success - +/-90
- **misc**: players_used, 90s, Performance - CrdY, Performance - CrdR, Performance - 2CrdY, Performance - Fls, Performance - Fld, Performance - Off, Performance - Crs, Performance - Int, Performance - TklW, Performance - PKwon, Performance - PKcon, Performance - OG

### Understat (per match, per team, walk-forward)

- xg, npxg, ppda (pressing intensity), deep completions, xpts, goals

### Legacy on disk (rich fbref, season 2425 only)

- data/league_init (11 stat types incl. defense/possession/passing/GCA) and data/players — usable for 24/25 backtest only, not reproducible for new seasons.