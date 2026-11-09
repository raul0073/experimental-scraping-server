"""Bookmaker closing odds from football-data.co.uk, as a BENCHMARK.

WHY A BOOKMAKER AT ALL. The closing price at a sharp book is the best public
forecast of a football match there is: by kickoff it has absorbed every
model, every injury rumour and every professional's money. A model that
cannot be told apart from it is doing very well; one that beats it is
extraordinary and should be doubted first. So the odds here are never shown
beside an unplayed fixture and never turned into a tip — they are the yard
stick the published probabilities are measured against, after the fact.

WHAT THIS MODULE DOES. Download one CSV per league-season (cached under
data/market/raw), read it with pandas only, map the site's team names onto
the project's canonical ones through an EXPLICIT table, and strip the
bookmaker's margin so three prices become three probabilities.

Two margin methods are implemented because they disagree in a known way:
proportional normalisation spreads the overround evenly, Shin's method
loads more of it onto the longshot, which is where books actually hide it
(the favourite-longshot bias). The report measures both; the site uses
normalisation unless Shin is clearly better, because it is the one a reader
can redo in their head.

The downloads are untrusted data. Nothing here executes anything from them:
pandas reads a text file, a handful of columns are picked by name, the
rest is dropped.
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from io import StringIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT / "data" / "market" / "raw"
NAME_MAP_PATH = ROOT / "data" / "config" / "market_team_names.json"
SOURCE = "football-data.co.uk"
URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"

# football-data's division codes for the five leagues the model prices.
CODES = {
    "ENG-Premier League": "E0",
    "ESP-La Liga": "SP1",
    "ITA-Serie A": "I1",
    "GER-Bundesliga": "D1",
    "FRA-Ligue 1": "F1",
}

# Which odds columns to try, in order. Pinnacle closing is the sharpest
# number on the sheet and the one the whole benchmark is about; it only
# appears from 2019/20, so older seasons fall back to Pinnacle's opening
# price and, failing that, the market average. Every row records which one
# it got, and the report counts them, so a season scored on weaker odds says
# so rather than passing for a closing-line comparison.
ODDS_COLUMNS = (
    ("pinnacle_closing", ("PSCH", "PSCD", "PSCA")),
    ("pinnacle", ("PSH", "PSD", "PSA")),
    # football-data dropped Pinnacle in January 2026. The sheet still carries
    # a CLOSING market average (AvgC*), which is the right fallback: it is the
    # same moment in time as a closing line, only a softer book. The opening
    # average is last resort.
    ("average_closing", ("AvgCH", "AvgCD", "AvgCA")),
    ("average", ("AvgH", "AvgD", "AvgA")),
)

OUTCOMES = ("home", "draw", "away")


# ---------------------------------------------------------------------------
# download + cache
# ---------------------------------------------------------------------------
def raw_path(league: str, season: str) -> Path:
    return RAW_DIR / league / f"{season}.csv"


def download(league: str, season: str, refresh: bool = False,
             max_age_hours: float | None = None) -> Path:
    """Fetch one league-season CSV unless a fresh enough copy is cached.

    `max_age_hours` lets the caller re-fetch a season that is still being
    played (new rows every weekend) while leaving finished seasons alone —
    a 2018/19 file cannot change, and the site does not deserve 45 requests
    a morning for data that will not move."""
    path = raw_path(league, season)
    if path.exists() and not refresh:
        if max_age_hours is None:
            return path
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h < max_age_hours:
            return path
    url = URL.format(season=season, code=CODES[league])
    req = urllib.request.Request(url, headers={"User-Agent": "predictorous-benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:     # noqa: S310 - fixed host
        body = resp.read()
    # A 200 with an HTML error page is the usual failure mode of a static
    # host; refuse to cache anything that does not look like the CSV.
    # Newer files open with a UTF-8 BOM; older ones do not. Either is fine.
    head = body[:200].decode("utf-8-sig", errors="replace")
    if not head.startswith("Div,"):
        raise RuntimeError(f"{url}: response is not the expected CSV "
                           f"(starts {head[:40]!r})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------
def _parse_dates(s: pd.Series) -> pd.Series:
    """dd/mm/yyyy, with dd/mm/yy in the older files. Both are day-first."""
    out = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    short = out.isna() & s.notna()
    if short.any():
        out[short] = pd.to_datetime(s[short], format="%d/%m/%y", errors="coerce")
    return out


def load_name_map() -> dict:
    if not NAME_MAP_PATH.exists():
        return {}
    return json.loads(NAME_MAP_PATH.read_text(encoding="utf-8"))


def parse(league: str, season: str, name_map: dict | None = None) -> pd.DataFrame:
    """One tidy frame per league-season: date, home, away (canonical names),
    goals, result, the three decimal odds and which column supplied them.

    Rows with no usable odds triplet are dropped — a benchmark cannot score
    a fixture the market did not price — and rows the site has not yet
    filled in (future fixtures on the current-season sheet) are dropped
    because they have no result. The odds of an unplayed match never leave
    this function."""
    path = raw_path(league, season)
    # Recent files are UTF-8 with a BOM, the pre-2021 ones are latin-1. Try
    # the strict one first so a BOM never ends up glued to "Div".
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam"])
    df = df[df["HomeTeam"].astype(str).str.strip() != ""]

    out = pd.DataFrame({
        "date": _parse_dates(df["Date"].astype(str)).dt.strftime("%Y-%m-%d"),
        "home_fd": df["HomeTeam"].astype(str).str.strip(),
        "away_fd": df["AwayTeam"].astype(str).str.strip(),
        "fthg": pd.to_numeric(df.get("FTHG"), errors="coerce"),
        "ftag": pd.to_numeric(df.get("FTAG"), errors="coerce"),
    })

    odds = pd.DataFrame(index=df.index, columns=["o_home", "o_draw", "o_away"], dtype=float)
    used = pd.Series([None] * len(df), index=df.index, dtype=object)
    for label, cols in ODDS_COLUMNS:
        if not all(c in df.columns for c in cols):
            continue
        trip = df[list(cols)].apply(pd.to_numeric, errors="coerce")
        ok = used.isna() & trip.notna().all(axis=1) & (trip > 1.0).all(axis=1)
        odds.loc[ok, ["o_home", "o_draw", "o_away"]] = trip.loc[ok].to_numpy()
        used[ok] = label
    out = pd.concat([out, odds], axis=1)
    out["odds_column"] = used

    out = out.dropna(subset=["date", "fthg", "ftag", "o_home"])
    out["fthg"] = out["fthg"].astype(int)
    out["ftag"] = out["ftag"].astype(int)
    out["result"] = np.where(out["fthg"] > out["ftag"], "home",
                             np.where(out["fthg"] < out["ftag"], "away", "draw"))

    mapping = (name_map if name_map is not None else load_name_map()).get(league, {})
    out["home"] = out["home_fd"].map(lambda n: mapping.get(n, n))
    out["away"] = out["away_fd"].map(lambda n: mapping.get(n, n))
    out["league"] = league
    out["season"] = season
    return out.reset_index(drop=True)


def assert_names(frame: pd.DataFrame, canonical: Iterable[str], league: str,
                 season: str) -> None:
    """Every mapped name must be one the project knows. No fuzzy matching:
    'Nott'm Forest' silently becoming 'Nottingham' once is a convenience,
    and 'Man City' silently becoming 'Manchester Utd' once is a season of
    wrong numbers. The table is edited by hand and this is what makes it
    safe to trust."""
    known = set(canonical)
    seen = set(frame["home"]) | set(frame["away"])
    missing = sorted(seen - known)
    if missing:
        raw = sorted(set(frame.loc[frame["home"].isin(missing), "home_fd"])
                     | set(frame.loc[frame["away"].isin(missing), "away_fd"]))
        raise ValueError(
            f"{league} {season}: {len(missing)} football-data team name(s) "
            f"do not map to a canonical name: {raw}. Add them to "
            f"{NAME_MAP_PATH.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# margin removal
# ---------------------------------------------------------------------------
def normalise(o_home: float, o_draw: float, o_away: float) -> dict:
    """Proportional: p_i = (1/o_i) / sum(1/o_j). The overround is spread in
    proportion to each price, which is the simplest defensible answer and
    the one most quoted figures use."""
    inv = np.array([1.0 / o_home, 1.0 / o_draw, 1.0 / o_away])
    p = inv / inv.sum()
    return dict(zip(OUTCOMES, (float(x) for x in p)))


def shin(o_home: float, o_draw: float, o_away: float, tol: float = 1e-10) -> dict:
    """Shin (1993): the book sets prices against a share z of insider money,
    so the margin sits disproportionately on the longshots. Solve for the z
    that makes the de-margined probabilities sum to one.

        p_i = (sqrt(z^2 + 4 (1 - z) pi_i^2 / S) - z) / (2 (1 - z))

    with pi_i = 1/o_i and S = sum(pi). A fair book (S = 1) gives z = 0 and
    p = pi exactly. Solved by bisection on z in [0, S - 1]; the function is
    monotone there so this always converges."""
    pi = np.array([1.0 / o_home, 1.0 / o_draw, 1.0 / o_away])
    S = pi.sum()
    if S <= 1.0 + 1e-12:
        p = pi / S
        return dict(zip(OUTCOMES, (float(x) for x in p)))

    def probs(z: float) -> np.ndarray:
        return (np.sqrt(z * z + 4.0 * (1.0 - z) * pi * pi / S) - z) / (2.0 * (1.0 - z))

    lo, hi = 0.0, min(S - 1.0, 0.999)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if probs(mid).sum() > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    p = probs(0.5 * (lo + hi))
    p = p / p.sum()                      # remove the last 1e-10 of drift
    return dict(zip(OUTCOMES, (float(x) for x in p)))


def add_probabilities(frame: pd.DataFrame) -> pd.DataFrame:
    """Both de-margined triplets and the overround, per row."""
    f = frame.copy()
    norm = [normalise(h, d, a) for h, d, a in zip(f["o_home"], f["o_draw"], f["o_away"])]
    sh = [shin(h, d, a) for h, d, a in zip(f["o_home"], f["o_draw"], f["o_away"])]
    for k in OUTCOMES:
        f[f"norm_{k}"] = [p[k] for p in norm]
        f[f"shin_{k}"] = [p[k] for p in sh]
    f["overround"] = 1.0 / f["o_home"] + 1.0 / f["o_draw"] + 1.0 / f["o_away"] - 1.0
    return f


def log_loss(p: float) -> float:
    return -math.log(max(p, 1e-9))
