"""Where a player actually played — per minute, not per match.

The obvious source is the `position` field on each player in the match
cache, but it only ever describes the STARTING eleven's opening shape. It
says nothing about a substitute, and nothing about a player who starts at
DMC and is pushed to MC on the hour. Ranking a player on all his minutes
under one label mixes two jobs and the number stops meaning anything.

WhoScored carries something better. Each team has a `formations` array, one
block per shape, each with a minute range, the shape's name, and a grid of
(horizontal, vertical) cells with the players occupying them:

    0'-63'   4231
    63'-75'  4231   two substitutions
    75'-85'  433    the manager changed shape
    85'-96'  433

The grid is a coordinate system, not a label: horizontal runs 1 at the RIGHT
touchline to 9 at the LEFT, vertical 0 at the goalkeeper to 9 at the centre
forward. Nothing publishes what each cell means, so the mapping is read out
of the data — for a starting block we know both the cell AND the player's
Opta code, which gives the translation table for free. Keyed by
(shape, horizontal, vertical) it resolves every one of 16,720 starting slots
to a single code with no ambiguity, so it can then be applied to the blocks
where no label exists at all.

Two things fall out that the label alone could not give:

  * a centre-back's SIDE. Both are "DC", but a back four puts them at
    horizontal 3.5 and 6.5 — right-of-centre and left-of-centre, exactly.
  * the 3-4-2-1 double "AMC", which the grid places at 3.5 and 6.5, one
    leaning each way. They are inside forwards, not two central tens.

Buckets pool the two sides together: a left winger and a right winger are
asked for the same things, so they belong in the same ranking with the side
kept as a label. Nine buckets, and a player appears in every one where he
has the minutes — Rice is ranked as a CM on his CM minutes and as a DM on
his DM minutes, and neither number is contaminated by the other.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

CACHE = Path.home() / "soccerdata" / "data" / "WhoScored" / "events"
ROOT = Path(__file__).resolve().parent.parent.parent
TABLE_PATH = ROOT / "data" / "config" / "formation_grid.json"

# Opta code -> bucket. Left and right pool together: the job is the same and
# a bigger pool makes a steadier percentile. Side is carried separately.
BUCKET_OF: Dict[str, str] = {
    "GK": "GK",
    "DR": "FB", "DL": "FB",
    "DC": "CB",
    "DMR": "WB", "DML": "WB",
    "DMC": "DM",
    "MC": "CM",
    "AMC": "AM",
    "MR": "WIDE", "ML": "WIDE",
    "AMR": "WIDE", "AML": "WIDE",
    "FWR": "WIDE", "FWL": "WIDE",
    "FW": "ST",
}

BUCKET_ORDER = ["GK", "FB", "CB", "WB", "DM", "CM", "AM", "WIDE", "ST"]

# What a table column says. The key stays WIDE, because it is what every
# data file on disk already contains, but a reader never sees the key:
# "WIDE" on its own names no position, it reads as an adjective that has
# lost its noun. "AW" is built the same way as the two beside it — DM is
# defensive midfield, AM attacking midfield, AW attacking winger — so the
# column decodes itself from its neighbours. "WNG" did not: it was an
# abbreviation of a word nobody had been shown.
BUCKET_SHORT = {
    "GK": "GK", "FB": "FB", "CB": "CB", "WB": "WB", "DM": "DM",
    "CM": "CM", "AM": "AM", "WIDE": "AW", "ST": "ST",
}

BUCKET_LABEL = {
    "GK": "Goalkeeper", "FB": "Full-back", "CB": "Centre-back",
    "WB": "Wing-back", "DM": "Defensive midfield", "CM": "Central midfield",
    "AM": "Attacking midfield", "WIDE": "Attacking winger", "ST": "Striker",
}

BUCKET_DESC = {
    "GK": "The goalkeeper.",
    "FB": "The full-backs of a back four — DR and DL.",
    "CB": "Centre-backs, whether in a two or a three.",
    "WB": "Wing-backs. The widest players on the pitch, wider than a winger "
          "and a line deeper — their team almost never fields a winger at "
          "all. The smallest pool on the site at 36, so read the "
          "percentiles as noisier here than elsewhere.",
    "DM": "The holding midfielder, in front of the defence.",
    "CM": "Central midfield proper, in the middle band.",
    "AM": "The creator behind the striker — including the two inside "
          "forwards of a 3-4-2-1, who lean left and right but work the "
          "half-space rather than the touchline.",
    "WIDE": "Attacking wingers. MR/ML, AMR/AML and FWR/FWL are one job under "
            "three formation labels — Salah is AMR in a 4-2-3-1 and FWR in a "
            "4-3-3 — so they are ranked together, with the side kept as a "
            "label rather than as a separate pool.",
    "ST": "The central striker.",
}

SIDE_LABEL = {"R": "right", "L": "left", "C": "centre"}


def side_of(horizontal: float) -> str:
    """Which side of the pitch the grid cell sits on.
    horizontal: 1 = right touchline, 5 = centre, 9 = left touchline."""
    if horizontal < 4.75:
        return "R"
    if horizontal > 5.25:
        return "L"
    return "C"


# --------------------------------------------------------------------------
# the grid -> code translation table, learnt from the starting elevens
# --------------------------------------------------------------------------

def _slot_cells(block: dict) -> List[Tuple[int, dict]]:
    """(playerId, cell) for everyone ON THE PITCH in this formation block.

    `formationSlots` gives each squad member's slot number, 0 for the bench.
    It is usually the identity ordering but is permuted in 229 of 7,132
    blocks, so it has to be honoured rather than assumed."""
    ids = block.get("playerIds") or []
    slots = block.get("formationSlots") or []
    cells = block.get("formationPositions") or []
    out = []
    for i, slot in enumerate(slots):
        if not slot or i >= len(ids) or slot > len(cells):
            continue
        out.append((ids[i], cells[slot - 1]))
    return out


def build_code_table(folders: List[Path] | None = None) -> Dict[str, str]:
    """Learn (shape, horizontal, vertical) -> Opta code from starting XIs.

    The grid is a WhoScored-wide convention rather than a league-specific
    one, so every cached folder contributes and rarer shapes get covered."""
    counts: Dict[str, Counter] = defaultdict(Counter)
    for folder in (folders if folders is not None else sorted(CACHE.glob("*"))):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict):     # a failed fetch cached as null
                continue
            for side in ("home", "away"):
                blob = d.get(side) or {}
                blocks = blob.get("formations") or []
                if not blocks:
                    continue
                first = blocks[0]
                code_of = {p.get("playerId"): p.get("position")
                           for p in blob.get("players") or []}
                shape = first.get("formationName")
                for pid, cell in _slot_cells(first):
                    code = code_of.get(pid)
                    if not code or code == "Sub":
                        continue
                    key = f"{shape}|{cell['horizontal']}|{cell['vertical']}"
                    counts[key][code] += 1
    return {k: c.most_common(1)[0][0] for k, c in counts.items()}


@lru_cache(maxsize=1)
def code_table() -> Dict[str, str]:
    """The translation table, cached on disk so it is built once."""
    if TABLE_PATH.exists():
        return json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    table = build_code_table()
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TABLE_PATH.write_text(json.dumps(table, indent=0, sort_keys=True),
                          encoding="utf-8")
    return table


# --------------------------------------------------------------------------
# per-match roles
# --------------------------------------------------------------------------

class Spell(dict):
    """One continuous stretch in one role: start, end, code, bucket, side."""


def match_roles(doc: dict) -> Dict[int, List[Spell]]:
    """playerId -> the spells he played, in expanded-minute terms.

    Consecutive blocks in the same role are merged, so a player who is
    unaffected by a substitution keeps one unbroken spell."""
    table = code_table()
    out: Dict[int, List[Spell]] = defaultdict(list)
    for side in ("home", "away"):
        blob = doc.get(side) or {}
        for block in blob.get("formations") or []:
            shape = block.get("formationName")
            start = block.get("startMinuteExpanded")
            end = block.get("endMinuteExpanded")
            if start is None or end is None or end <= start:
                continue
            for pid, cell in _slot_cells(block):
                code = table.get(f"{shape}|{cell['horizontal']}|{cell['vertical']}")
                if not code:
                    continue
                bucket = BUCKET_OF.get(code)
                if not bucket:
                    continue
                spells = out[pid]
                if spells and spells[-1]["code"] == code and \
                        spells[-1]["end"] == start:
                    spells[-1]["end"] = end
                    continue
                spells.append(Spell(start=start, end=end, code=code,
                                    bucket=bucket, side=side_of(cell["horizontal"])))
    return dict(out)


def load_match(league: str, season: str, game_id: Any) -> dict | None:
    path = CACHE / f"{league}_{season}" / f"{int(game_id)}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None
