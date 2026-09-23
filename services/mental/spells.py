"""Manager spells — the unit a team is ranked as.

A club is not one team for three seasons. Chelsea under two managers in a
season is two sides, and the predictor that eventually reads this layer cares
about what this team is doing NOW under this manager, not about a club's
three-year average. So the unit of a team ranking is the spell.

The raw data will not hand that over. WhoScored records `managerName` per
team per match, and taken literally it produces 159 "spells" across three
Premier League seasons with a MEDIAN LENGTH OF TWO MATCHES — because for some
fixtures it lists a caretaker or an assistant and then flips back. Burnley
alone yields Scott Parker / Michael Jackson / Scott Parker / Michael Jackson
at one match each, which is not four changes of manager.

Two rules fix it:

  * a run shorter than MIN_RUN that is BRACKETED by the same name on both
    sides is absorbed into it — a name that appears for two matches in the
    middle of someone's tenure is a stand-in, not a spell
  * what survives and still falls under MIN_SPELL is merged into the
    neighbour it is longest adjacent to, and marked `short: true`, so a
    genuine short reign is visible without being ranked on twelve matches

What comes out is stitched, contiguous, and covers every match: no fixture
belongs to nobody.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

CACHE = Path.home() / "soccerdata" / "data" / "WhoScored" / "events"

MIN_RUN = 3        # a blip this short inside a tenure is a stand-in
MIN_SPELL = 10     # below this a spell is carried, but not ranked alone


@dataclass
class Spell:
    team: str
    manager: str
    games: List[int] = field(default_factory=list)
    seasons: List[str] = field(default_factory=list)
    # first and last kickoff, because game ids are not chronological inside
    # a season and sorting spells by id puts tenures in the wrong order
    start: str = ""
    end: str = ""

    @property
    def key(self) -> str:
        return f"{self.team}|{self.manager}|{min(self.games)}"

    @property
    def matches(self) -> int:
        return len(self.games)

    @property
    def short(self) -> bool:
        """Too few matches to rate — but still the man in charge. A spell
        that has just begun is short and real at the same time."""
        return self.matches < MIN_SPELL


def _match_managers(league: str, seasons: List[str]) -> Dict[str, list]:
    """team -> [(kickoff, game_id, season, manager)], in CHRONOLOGICAL order.

    Ordered by kickoff, not by game id. Ids rise across seasons but not
    within one: 23/24's span a range of 74,000 against 24/25's 379, so
    sorting a season by id is arbitrary. Sorted that way, Palace appeared to
    hire Glasner mid-season, revert to Hodgson, and hire him again — which
    is not what happened, and would have split one spell into two."""
    per: Dict[str, list] = defaultdict(list)
    for season in seasons:
        folder = CACHE / f"{league}_{season}"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            for side in ("home", "away"):
                b = d.get(side) or {}
                team, mgr = b.get("name"), b.get("managerName")
                if team and mgr:
                    kick = d.get("startTime") or d.get("startDate") or ""
                    per[team].append((kick, int(path.stem), season, mgr))
    for team in per:
        per[team].sort()
    return dict(per)


def _absorb_blips(names: List[str]) -> List[str]:
    """Replace a short run that is bracketed by the same name on both sides.

    Run once per pass and repeated until stable, because absorbing one blip
    can bring two runs of the same name together and expose another."""
    while True:
        runs: List[List] = []
        for i, nm in enumerate(names):
            if runs and runs[-1][0] == nm:
                runs[-1][1].append(i)
            else:
                runs.append([nm, [i]])
        changed = False
        for j in range(1, len(runs) - 1):
            nm, idx = runs[j]
            if len(idx) < MIN_RUN and runs[j - 1][0] == runs[j + 1][0]:
                for i in idx:
                    names[i] = runs[j - 1][0]
                changed = True
        if not changed:
            return names


def _absorb_short(names: List[str]) -> List[str]:
    """Relabel any surviving run under MIN_SPELL with its longer neighbour.

    Done on the NAME SEQUENCE rather than by merging spell objects. Merging
    objects left the same manager holding two separate spells at one club —
    Glasner 76 and Glasner 13 at Palace, Dyche 53 and Dyche 11 at Everton —
    because absorbing a short run can bring two runs of the same name
    together and nothing went back to look. Rebuilding from the names after
    every pass makes that impossible: adjacent equal names are one run by
    definition."""
    while True:
        runs: List[List] = []
        for i, nm in enumerate(names):
            if runs and runs[-1][0] == nm:
                runs[-1][1].append(i)
            else:
                runs.append([nm, [i]])
        if len(runs) < 3:
            return names
        # INTERIOR runs only. A short run with a neighbour on each side is a
        # caretaker inside someone's tenure. A short run at either END is not:
        # the last one is a manager appointed weeks ago, who has few matches
        # BY DEFINITION, and absorbing it deleted him — Manchester City read
        # as Guardiola when Maresca had been in charge since August, and
        # Chelsea as Rosenior when it was Xabi Alonso. The first run is the
        # same case in reverse, a tenure already under way when our data
        # begins.
        interior = range(1, len(runs) - 1)
        j = min(interior, key=lambda k: len(runs[k][1]))
        if len(runs[j][1]) >= MIN_SPELL:
            return names
        left, right = runs[j - 1], runs[j + 1]
        pick = max(left, right, key=lambda r: len(r[1]))
        for i in runs[j][1]:
            names[i] = pick[0]


def build(league: str, seasons: List[str]) -> List[Spell]:
    out: List[Spell] = []
    for team, rows in _match_managers(league, seasons).items():
        names = _absorb_short(_absorb_blips([m for *_r, m in rows]))
        cur: Spell | None = None
        for (_kick, gid, season, _raw), nm in zip(rows, names):
            if cur is None or cur.manager != nm:
                cur = Spell(team=team, manager=nm, start=_kick)
                out.append(cur)
            cur.games.append(gid)
            cur.end = _kick
            if season not in cur.seasons:
                cur.seasons.append(season)
    return sorted(out, key=lambda s: (s.team, s.start))


@lru_cache(maxsize=8)
def spell_of(league: str, seasons: tuple) -> Dict[tuple, Spell]:
    """(team, game_id) -> the spell it belongs to."""
    out = {}
    for sp in build(league, list(seasons)):
        for g in sp.games:
            out[(sp.team, g)] = sp
    return out
