"""Pitch-zone model — v3 (2026-09 redesign).

v2 ran a 3x5 grid, but Understat shot y-coordinates only span ~0.24-0.85:
true "wide" shot lanes get ~2 shots a season, so wide att/def zones carried no
signal (they collapsed to rank-of-season-total — the left=right clone bug the
user spotted). v3 is the grid the data can support:

    3 lanes x {defense, attack}  +  a single midfield-control zone  = 7 zones

Lane boundaries are fitted to the real distribution of 44k shots (25% / 48% /
27% mass): y < 0.42 RIGHT, 0.42-0.58 CENTRAL, >= 0.58 LEFT.

Coordinate conventions (Understat): x 0->own goal..1->opponent goal;
y across the pitch, LEFT = high y (fixed convention; mirroring keeps
matchups side-consistent).
"""
from typing import Dict, List, Tuple

# v3.5: midfield is split by FUNCTION, not lane — no free data resolves
# midfield laterally (v2's five mid lanes were provably identical per team),
# but progression, pressing and screening ARE separately measurable.
ZONES: List[str] = [
    "defLeft", "defCentral", "defRight",
    "midProgress", "midPress", "midShield",
    "attLeft", "attCentral", "attRight",
]

ZONE_LABELS: Dict[str, str] = {
    "defLeft": "Defensive Left", "defCentral": "Defensive Central",
    "defRight": "Defensive Right",
    "midProgress": "Midfield Progression", "midPress": "Midfield Press",
    "midShield": "Midfield Screen",
    "attLeft": "Attacking Left", "attCentral": "Attacking Central",
    "attRight": "Attacking Right",
}

# each of my zones -> the opponent zone it contests
ZONE_MATCHUPS: Dict[str, str] = {
    "attLeft": "defRight", "attCentral": "defCentral", "attRight": "defLeft",
    "midProgress": "midShield",   # my build-up vs their screen
    "midPress": "midProgress",    # my press vs their build-up
    "midShield": "midProgress",   # my screen vs their build-up
    "defLeft": "attRight", "defCentral": "attCentral", "defRight": "attLeft",
}

ZONE_IMPORTANCE: Dict[str, float] = {
    "attCentral": 1.4, "attLeft": 1.1, "attRight": 1.1,
    "midProgress": 1.0, "midPress": 0.9, "midShield": 0.9,
    "defCentral": 1.2, "defLeft": 0.8, "defRight": 0.8,
}

# ---------------------------------------------------------------- geometry

# fitted to the league-wide shot-y distribution (data/reports: p25=0.42,
# p75=0.588) — NOT the full pitch width, because shots don't happen there
LANES: List[Tuple[str, float, float]] = [
    ("Right", 0.00, 0.42),
    ("Central", 0.42, 0.58),
    ("Left", 0.58, 1.01),
]


def shot_lane(y: float) -> str:
    for lane, lo, hi in LANES:
        if lo <= y < hi:
            return lane
    return "Central"


# lastAction values grouped into creation channels
CREATION_ACTIONS: Dict[str, List[str]] = {
    "cross": ["Cross", "Aerial", "HeadPass"],
    "throughball": ["Throughball"],
    "takeon": ["TakeOn", "Dribble"],
}

# attacking team's lastAction that means the DEFENDING team lost the ball
TURNOVER_ACTIONS: List[str] = ["Interception", "Tackle", "BallRecovery", "Dispossessed"]
