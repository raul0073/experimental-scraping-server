"""The metric bank, split by the role a player was actually playing.

A player is not one thing. Rice played 2,004 minutes in central midfield and
1,195 in front of the back four; Luke Shaw split 54/46 between full-back and
centre-back. Folding either man's season into a single row under a single
label produces a number that describes nobody.

So every event and every minute is attributed to the role in force AT THAT
MINUTE — see services.mental.positions for how the role is read — and the
bank is keyed by (bucket, player). Rice appears in the central-midfield
ranking on his central-midfield minutes and in the defensive-midfield
ranking on his defensive-midfield minutes, and neither number borrows from
the other. 85 Premier League players qualified in more than one bucket in
25/26, so this is the normal case rather than an edge one.

Accumulators are kept per bucket and can be folded across seasons, which is
what the all-seasons view is built from: the pooled total is computed from
the raw events of every season at once, not by averaging season ranks.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from services.mental.event_metrics import (
    _qnames, accumulate, finalise, new_accumulator, possession_adjust,
)
from services.mental.positions import BUCKET_ORDER, load_match, match_roles

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "whoscored"
LEVERAGE = ROOT / "data" / "config" / "leverage.json"


@lru_cache(maxsize=1)
def _leverage() -> tuple:
    """The weight of each match state, from scripts/build_leverage.py.
    Absent, every moment weighs the same and the weighted decisive metric
    collapses onto the plain one, which is the honest fallback."""
    if not LEVERAGE.exists():
        return {}, 3, 1, 5
    cfg = json.loads(LEVERAGE.read_text(encoding="utf-8"))
    return (cfg.get("leverage", {}), cfg.get("diff_cap", 3),
            cfg.get("men_cap", 1), cfg.get("time_bin", 5))


def _leverage_column(match: pd.DataFrame) -> np.ndarray:
    table, cap_d, cap_m, bin_t = _leverage()
    if not table:
        return np.ones(len(match))
    end = float(match["expanded_minute"].max())
    d = np.clip(np.nan_to_num(match["score_diff"].to_numpy()), -cap_d, cap_d).astype(int)
    m = np.clip(np.nan_to_num(match["man_diff"].to_numpy()), -cap_m, cap_m).astype(int)
    left = end - np.nan_to_num(match["expanded_minute"].to_numpy(float))
    t = np.clip((left // bin_t) * bin_t, 0, 95).astype(int)
    return np.array([table.get(f"{a}|{b}|{c}", 1.0) for a, b, c in zip(d, m, t)])


class Store:
    """Per-bucket accumulators plus the bookkeeping the table needs."""

    def __init__(self) -> None:
        self.acc: Dict[str, dict] = {b: new_accumulator() for b in BUCKET_ORDER}
        self.minutes: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float))
        self.side: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
        self.team: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
        self.player_minutes: Dict[str, float] = defaultdict(float)
        # total minutes each club played, so availability has a denominator
        self.club_minutes: Dict[str, float] = defaultdict(float)
        # the LAST club each player turned out for, by match id. The club a
        # row is about and the club he plays for now are different questions
        # once a view spans three seasons.
        self.last_club: Dict[str, Tuple[int, str]] = {}
        self.matches = 0
        self.missing = 0

    def period_minutes(self) -> float:
        """The fullest programme any club played in this period — 38 matches
        for a finished season, four for one five rounds old, and the sum of
        them for the pooled view."""
        return max(self.club_minutes.values(), default=0.0)


def _event_buckets(match: pd.DataFrame, roles: dict) -> pd.Series:
    """Which role each event was performed in.

    A spell is found by the last one that had started by the event's expanded
    minute. Events outside every spell — stoppage time past the final block,
    or a stray event before kick-off — are clamped to the nearest spell
    rather than dropped, because they are the player's work either way."""
    out = pd.Series(index=match.index, dtype=object)
    ev = match.dropna(subset=["player_id"])
    for pid, g in ev.groupby("player_id"):
        spells = roles.get(int(pid))
        if not spells:
            continue
        starts = np.array([s["start"] for s in spells], dtype=float)
        idx = np.searchsorted(starts, g["expanded_minute"].to_numpy(float),
                              side="right") - 1
        idx = np.clip(idx, 0, len(spells) - 1)
        out.loc[g.index] = [spells[i]["bucket"] for i in idx]
    return out


def fold_match(match: pd.DataFrame, roles: dict, store: Store) -> None:
    """Add one match to the per-bucket accumulators."""
    name_of = (match.dropna(subset=["player_id"])
               .groupby("player_id")["player"].first())
    team_of = (match.dropna(subset=["player"])
               .groupby("player")["team"].first())

    # Possession exposure is banked here rather than inside accumulate(),
    # because the share has to be measured on the WHOLE match while the
    # events being accumulated are only one role's slice of it.
    touches = match[match["is_touch"] == True].groupby("team").size()  # noqa: E712
    share = (touches / (float(touches.sum()) or 1.0)).to_dict()

    # How much the match hung on each moment, attached to every event so the
    # decisive acts can be weighted by it downstream.
    match = match.assign(w_lev=_leverage_column(match))

    # Every minute both clubs played, so availability has a denominator.
    length = float(match["expanded_minute"].max())
    for side in match["team"].dropna().unique():
        store.club_minutes[side] += length

    # Goals CONCEDED, for the keeper's save percentage. A goal is scored by
    # the opponent, so it never appears on the keeper's own events and has to
    # be read off the match — credited by the minute, since a man who came on
    # at 70' did not concede the one in the 12th.
    #
    # An own goal is filed under the team of the player who put it in, so for
    # that one event the team on the row is the side CONCEDING rather than
    # the side scoring. Getting this backwards would hand each own goal to
    # the wrong keeper, twice.
    sides = list(match["team"].dropna().unique())
    conceded = []
    for r in match[match["type"] == "Goal"].itertuples(index=False):
        own = "OwnGoal" in _qnames(r.qualifiers)
        if own:
            by = r.team
        else:
            other = [s for s in sides if s != r.team]
            if not other:
                continue
            by = other[0]
        conceded.append((float(r.expanded_minute), by))

    gid = int(match["game_id"].iloc[0])
    for pid, spells in roles.items():
        name = name_of.get(pid)
        if name is None:
            continue
        club = team_of.get(name)
        if club is not None and store.last_club.get(name, (-1, ""))[0] < gid:
            store.last_club[name] = (gid, club)
        own = share.get(club, 0.5)
        for s in spells:
            played = s["end"] - s["start"]
            if played <= 0:
                continue
            b = s["bucket"]
            store.minutes[b][name] += played
            store.player_minutes[name] += played
            store.side[(b, name)][s["side"]] += played
            if team_of.get(name) is not None:
                store.team[(b, name)][team_of[name]] += played
            a = store.acc[b][name]
            a["own_poss_min"] += played * own
            a["opp_poss_min"] += played * (1.0 - own)
            team = team_of.get(name)
            if team is not None:
                a["conceded"] += sum(
                    1 for minute, by in conceded
                    if by == team and s["start"] <= minute < s["end"])

    buckets = _event_buckets(match, roles)
    for b, idx in buckets.dropna().groupby(buckets.dropna()).groups.items():
        accumulate(match.loc[idx], store.acc[b])
    store.matches += 1


def fold_season(league: str, season: str, *stores: Store,
                half: str | None = None) -> Store:
    """Fold a whole stamped season into every store given.

    Several stores because the all-seasons view is the pooled raw events of
    every season, so each match belongs both to its own season's store and to
    the running total, and reading the parquet twice to say so would be
    waste. `half` takes the odd- or even-numbered matches only, for the
    split-half reliability check."""
    df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
    if half:
        gids = sorted(df["game_id"].unique())
        keep = {g for i, g in enumerate(gids)
                if (i % 2 == 0) == (half == "even")}
        df = df[df["game_id"].isin(keep)]
    for gid, match in df.groupby("game_id", sort=False):
        doc = load_match(league, season, gid)
        if doc is None:
            for store in stores:
                store.missing += 1
            continue
        roles = match_roles(doc)
        for store in stores:
            fold_match(match, roles, store)
    return stores[0]


def _role_share(store: Store, bucket: str, name: str) -> float:
    """What share of the PERIOD's football he played in this role, 0-100.

    The denominator is the fullest programme any club played in the period,
    not the player's own club's. Using his club's made a Coventry keeper who
    played all four of their 26/27 matches score 95% and stand beside men
    with ten thousand minutes, because his club had only been in the league
    four weeks. The period is the thing being ranked, so the period is the
    thing to measure against."""
    avail = store.period_minutes()
    return (store.minutes[bucket][name] / avail * 100) if avail else 0.0


def _side_label(counter: Counter, mixed_below: float = 0.7) -> str:
    """Which side he played, or "RL" when he genuinely played both.

    Ndiaye spent 1,393 minutes on the right wing and 1,062 on the left;
    Semenyo 1,138 and 1,365. Calling either man simply right-sided or
    left-sided throws away the more interesting fact about him."""
    total = sum(counter.values())
    if not total:
        return "C"
    top, n = counter.most_common(1)[0]
    if n / total >= mixed_below or top == "C":
        return top
    others = [s for s, _ in counter.most_common() if s != top][:1]
    return top + (others[0] if others else "")


def banks(store: Store, min_minutes: int, adjust: bool = False,
          min_share: float = 0.0) -> Dict[str, pd.DataFrame]:
    """bucket -> the finished table for players who cleared the threshold
    IN THAT ROLE. Carries side, team and the share of his minutes spent
    there, so the page can say 'Rice — CM, 63% of his minutes'."""
    out: Dict[str, pd.DataFrame] = {}
    for b in BUCKET_ORDER:
        mins = dict(store.minutes[b])
        if min_share:
            # A share of the club's football, not a flat minute count. Three
            # seasons and five rounds of a new one cannot share a threshold:
            # 450 minutes is a fringe player over three years and more than
            # anyone has played in September.
            mins = {n: m for n, m in mins.items()
                    if _role_share(store, b, n) >= min_share}
        if not mins:
            continue
        bank = finalise(store.acc[b], mins, min_minutes)
        if bank.empty:
            continue
        if adjust:
            bank = possession_adjust(bank, store.acc[b])
        bank["bucket"] = b
        bank["side"] = [_side_label(store.side[(b, n)]) for n in bank.index]
        bank["team"] = [store.team[(b, n)].most_common(1)[0][0]
                        if store.team[(b, n)] else None for n in bank.index]
        bank["role_share"] = [round(_role_share(store, b, n), 1)
                              for n in bank.index]
        bank["availability_pct"] = [
            round(min(100.0, store.player_minutes[n]
                      / store.club_minutes[store.team[(b, n)].most_common(1)[0][0]] * 100), 1)
            if store.team[(b, n)] and store.club_minutes.get(
                store.team[(b, n)].most_common(1)[0][0]) else np.nan
            for n in bank.index]
        bank["share"] = [
            round(mins[n] / store.player_minutes[n] * 100)
            if store.player_minutes[n] else 100 for n in bank.index]
        out[b] = bank
    return out


def seasons_on_disk(league: str) -> list:
    return sorted(p.stem.replace("_stamped", "")
                  for p in (RAW / league).glob("*_stamped.parquet"))
