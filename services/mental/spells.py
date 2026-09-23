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
import unicodedata
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


def _canonical_names(names: List[str]) -> List[str]:
    """One man, one name — before anything decides he has been replaced.

    🐛 WHOSCORED WRITES SOME MANAGERS TWO WAYS, AND THE DIFFERENCE READS AS A
    SACKING. Spanish double surnames are where it bites: the same man appears
    as "Marcelino García" and "Marcelino García Toral", "Luis García" and
    "Luis García Plaza", "Álvaro Arbeloa" and "Álvaro Arbeloa Coca". Every
    one of those became a change of manager, so Marcelino's 101 matches at
    Villarreal shipped as a 66-match spell and a 35-match spell — each shrunk
    toward 50 on partial evidence, and the man listed twice in one table.

    It was found by a style experiment, not by this module, and the way it
    was found is the point: a FAKE Flick-to-Flick "change" at Barcelona was
    registering a significant style shift at p=0.010. That is the strongest
    evidence a manager-change study could produce for a manager who never
    left. Any analysis keyed on a change of name inherits this.

    The test is a subset of NAME TOKENS within one club's own timeline. A
    club fielding two different managers whose full names are a subset of one
    another is not something that happens; the same man recorded with and
    without his second surname is something that happens constantly. The
    longest spelling wins, because it is the one that identifies him.
    """
    def toks(n: str) -> list:
        flat = unicodedata.normalize("NFKD", n.lower().replace("-", " "))
        flat = "".join(c for c in flat if not unicodedata.combining(c))
        return flat.split()

    # Runs, because the second rule below needs to know what followed what.
    runs: List[str] = []
    for n in names:
        if not runs or runs[-1] != n:
            runs.append(n)

    canon = {n: n for n in dict.fromkeys(names)}

    def link(a: str, b: str) -> None:
        """Keep the longer spelling — it is the one that identifies him."""
        full, part = (a, b) if len(toks(a)) >= len(toks(b)) else (b, a)
        for k, v in canon.items():
            if v == canon[part] or k == part:
                canon[k] = canon[full]
        canon[part] = canon[full]

    for i, a in enumerate(runs):
        for j in range(i + 1, len(runs)):
            b = runs[j]
            ta, tb = set(toks(a)), set(toks(b))
            if not ta or not tb or canon[a] == canon[b]:
                continue
            # 0. IDENTICAL ONCE ACCENTS ARE FOLDED — "Eric Roy" and "Éric
            #    Roy" at Brest, which the feed alternated between and which
            #    split one 102-match tenure into 34 and 68. Two different men
            #    at one club whose names differ only by a diacritic do not
            #    exist. This was originally a `continue`, skipping the very
            #    case with the least doubt in it.
            if ta == tb:
                link(a, b)
                continue
            # 1. One spelling contains the other: "Marcelino García" inside
            #    "Marcelino García Toral". Safe anywhere in the timeline — a
            #    club does not field two men whose names nest like that.
            if ta <= tb or tb <= ta:
                link(a, b)
                continue
            # 2. Same surname AND the two runs are ADJACENT: "Hans-Dieter
            #    Flick" handing over to "Hansi Flick", "Miguel Ángel Sánchez"
            #    to "Míchel Sánchez" (Míchel IS Miguel Ángel). Adjacency is
            #    what makes this safe — two different managers sharing a
            #    surname at one club is possible across four seasons, but one
            #    succeeding the other immediately is not, it is a feed that
            #    changed its mind about how to spell him.
            if j == i + 1 and toks(a)[-1] == toks(b)[-1]:
                link(a, b)
    return [canon[n] for n in names]


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


def build(league: str, seasons: List[str],
          absorb_short: bool = True) -> List[Spell]:
    """Stitched manager spells. `absorb_short=False` keeps interior short
    reigns as spells of their own.

    WHY THAT IS A CHOICE AND NOT A SETTING. Absorption is right when the unit
    is A TEAM: a ranking of sides wants stable units, and eight matches under
    a man who was sacked is not a side worth rating separately.

    It is wrong when the unit is A MANAGER. _absorb_short relabels an interior
    short run with its longer neighbour, so a manager sacked after eight games
    does not merely go unranked — he DISAPPEARS, and his eight matches are
    credited to whoever came before or after. For a manager ranking that is
    not a missing row, it is a wrong one in someone else's name.

    (Only interior runs are touched; the first and last are protected, so a
    manager appointed weeks ago is never absorbed. _absorb_blips still runs
    either way — a name that appears for two matches bracketed by the same
    manager is a stand-in, not a reign, whatever the unit is.)

    Small samples are then handled where they should be: by shrinking a short
    spell's score toward neutral, which says "we do not know yet" instead of
    "this did not happen"."""
    out: List[Spell] = []
    for team, rows in _match_managers(league, seasons).items():
        names = _absorb_blips(_canonical_names([m for *_r, m in rows]))
        if absorb_short:
            names = _absorb_short(names)
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
