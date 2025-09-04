import re
from typing import Dict, List
import pandas as pd
from soccerdata import FBref
from models.fbref.fbref_types import POSSIBLE_PLAYER_TABLES



def _norm_col(c: str) -> str:
    c = str(c)
    c = c.replace("%", "pct").replace("/", "_per_").replace("+", "_plus_")
    c = re.sub(r"[^\w]+", "_", c)
    c = re.sub(r"_+", "_", c).strip("_")
    return c.lower()

def _clean_df(df: pd.DataFrame, league: str, season: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]
    # normalize common id fields
    if "team" not in df.columns and "squad" in df.columns:
        df["team"] = df["squad"]
    if "competition" in df.columns and "league" not in df.columns:
        df["league"] = df["competition"]
    df["league"] = league
    df["season"] = season
    # standardize player key
    if "player" in df.columns:
        df["player"] = df["player"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    if "team" in df.columns:
        df["team"] = df["team"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    return df

def _available_tables(fb: FBref) -> List[str]:
    out = []
    for t in POSSIBLE_PLAYER_TABLES:
        # prefer generic reader signature: read_player_season_stats(stat_type=...)
        try:
            _ = fb.read_player_season_stats(stat_type=t)
            out.append(t)
            continue
        except AttributeError:
            pass
        # fallback to specific helpers some versions expose: read_players_{t}()
        try:
            _ = getattr(fb, f"read_players_{t}")()
            out.append(t)
        except AttributeError:
            # not available in this lib version
            pass
    return out

def _read_table(fb: FBref, table: str) -> pd.DataFrame:
    try:
        df = fb.read_player_season_stats(stat_type=table)
    except AttributeError:
        df = getattr(fb, f"read_players_{table}")()
    return df

def _discover_teams(table_frames: Dict[str, pd.DataFrame]) -> list[str]:
    teams = set()
    debug = {}
    for tname, df in table_frames.items():
        debug[tname] = list(df.columns)
        # prefer normalized 'team', fallback to 'squad' if cleaner missed it
        if "team" in df.columns:
            teams.update(df["team"].dropna().astype(str))
        elif "squad" in df.columns:
            teams.update(df["squad"].dropna().astype(str))
    if not teams:
        raise RuntimeError(f"No teams found in any table. Columns by table: {debug}")
    return sorted({t.strip() for t in teams})




