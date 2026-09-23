"""Raw per-spell manager metrics, straight off the stamped event stream.

    from services.managers.metrics import spell_metrics, METRIC_KEYS
    rows = spell_metrics("ENG-Premier League", ["2425"])

One row per manager spell, each carrying {"raw": {metric_key: value or None}}
for every key in METRIC_KEYS. Nothing here scores, percentiles or publishes —
it produces the numbers, and says None when the data cannot produce one.

EVERY ROW NAMES ITS SPELL, in `key`, and that is the only safe identity it
has. `manager` and `team` are NOT a key: a man who comes back to a club, or a
caretaker who does two separate stints, holds two spells at one ground. A
consumer that files these rows by (team, manager) collapses both onto one —
which is exactly what happened, and published the second spell's numbers
under the first spell's name while the second went out with every metric
null. Spell.key carries the first game id as well as the pair, so it
separates them; it is unique across the rows this module returns and that is
asserted below rather than assumed.

THE SPELL. services.mental.spells.build(..., absorb_short=False). The default
absorption relabels an interior run under ten matches with its longer
neighbour, which for a MANAGER ranking does not down-weight a sacked coach, it
deletes him and credits his matches to someone else. Short spells are kept and
flagged; the scorer shrinks them toward neutral.

WHERE xG COMES FROM, AND WHY. WhoScored events carry `is_shot` but no xG
value, and this repo's xG is Understat's, published per shot with a minute but
no link to the WhoScored feed. Of the three honest options — count shots, join
Understat, or return null — this module JOINS UNDERSTAT, because the join is
verifiable rather than assumed and the alternative (shot counts) would answer
a different question from the one the metric names:

  * team names are matched STRUCTURALLY, never by string similarity. Each
    WhoScored club is paired with the Understat club whose set of fixture
    DATES it shares (greedy best Jaccard). Measured over 24/25: worst pairing
    0.914, worst margin over the runner-up 0.348, all five leagues 1-to-1.
    Name similarity was tried first and is unsafe — it maps La Liga's
    "Atletico" onto "Athletic Club".
  * matches are then joined on the mapped club pair and the nearest date, and
    each WhoScored shot event is paired with an Understat shot of the same
    team by minute (in-order when the counts agree, else nearest unused, 3
    minutes of tolerance). Measured over ENG 24/25: 380/380 matches, 9,870 of
    9,883 shot events paired, 98.3% of them at exactly the same minute.
  * the 0.1% that do not pair contribute xG 0. Understat shot files exist from
    2425 onward only, so every xG metric is None for 2324.

Taking the state from the WhoScored event rather than from Understat is
deliberate: score_state/phase are already stamped and verified against
WhoScored's own ftScore by scripts/stamp_event_state.py, own goals included.

ATTACKING DIRECTION — verified, not assumed. x runs 0-100 toward the goal the
team in possession is attacking, for the team that owns the event. Measured on
ENG 24/25: Goal x=87.3, Save x=7.2, KeeperPickup x=6.3, Clearance x=13.1,
Tackle x=39.2. So press_height and tactical_foul_x are already in the frame
the contract wants and need no mirroring. A `Foul` is written TWICE, once for
each side, as exact mirrors (Unsuccessful x=54.9, Successful x=45.1, summing
to 100); the offending team's row is the Unsuccessful one, cross-checked by
the 85 fouls at x<16 inside the penalty-area width, which is the season's real
penalty count. Every foul counted here is a foul COMMITTED.

HOUSE RULES OBSERVED. Ratios aggregate as a ratio of sums across the spell's
matches, never the mean of per-match ratios. The one league-wide fit that the
contract requires — the game-state control under sub_impact — is fitted across
the WHOLE league-season before any spell is aggregated. No raw event stream
leaves this module, and no odds data is read anywhere.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from services.mental.spells import MIN_SPELL
from services.mental.spells import build as build_spells
from services.understat.shot_events_service import ShotEventsService

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "whoscored"

# ---------------------------------------------------------------- thresholds
FINAL_THIRD = 66.7        # own attacking frame
PRESS_LINE = 40.0         # our x >= 40 is the opponent's own 60% of the pitch
OPP_SIXTY = 60.0          # a pass at x < 60 is inside that team's own 60%
DIRECT_GAIN = 15.0        # end_x - x greater than this is a direct pass
SHORT_CORNER = 15.0       # CornerTaken Length below this is a short corner
SUB_WINDOW = 15.0         # minutes either side of the first substitution
MIN_WINDOW = 5.0          # a window shorter than this is not a measurement
MIN_STATE_MINUTES = 30.0  # below this a per-minute state rate is noise
MIN_CELL = 10             # league cells thinner than this fall back
REGAIN_CAP = 60.0         # an out-of-possession spell longer than this is a
                          # stoppage, not football: a goal and its restart, an
                          # injury, a long VAR check. Counting them would
                          # measure how often a side concedes rather than how
                          # quickly it presses.
REGAIN_FAST = 5.0         # the counterpress window, by convention
CORE_SHARE = 0.25         # a player on this share of available minutes is one
                          # the manager actually uses

DEF_TYPES = ("Tackle", "Interception", "Challenge", "BallRecovery")
SP_SITUATIONS = ("FromCorner", "SetPiece", "DirectFreekick")  # penalties out
PERIOD_ORDER = {"PreMatch": 0, "FirstHalf": 1, "SecondHalf": 2,
                "FirstPeriodOfExtraTime": 3, "SecondPeriodOfExtraTime": 4,
                "PenaltyShootout": 5, "PostGame": 6}
IN_PLAY = ("FirstHalf", "SecondHalf",
           "FirstPeriodOfExtraTime", "SecondPeriodOfExtraTime")
SUB_BANDS = ((0.0, 60.0), (60.0, 70.0), (70.0, 75.0),
             (75.0, 80.0), (80.0, 85.0), (85.0, 1e9))

# ------------------------------------------------------------------ the bank
# dimension groups the page; directional says whether the metric may enter a
# score at all; invert says lower is better. `nd` is how many decimals the raw
# value survives at — a per-minute xG rate needs more than a percentage.
METRICS: Dict[str, Dict[str, Any]] = {
    # ---- DIRECTIONAL: these, and only these, may be scored ----
    "set_piece_balance": {
        "label": "Set-piece balance", "dimension": "set-pieces",
        "directional": True, "invert": False, "unit": "xG/match", "nd": 4,
        "help": "Set-piece xG created minus set-piece xG conceded, per match. "
                "Understat situations FromCorner, SetPiece and DirectFreekick; "
                "penalties excluded, because a penalty is not a coached "
                "routine. Volume follows how many dead balls you win, which is "
                "an open-play property — read it beside corner_profile."},
    "sendings_off": {
        "label": "Sendings-off", "dimension": "discipline",
        "directional": True, "invert": True, "unit": "/match", "nd": 4,
        "help": "Red cards and second yellows per match. The one discipline "
                "number with an unambiguous right end, and the rarest thing "
                "here: 55 in a 380-match Premier League season, so the gap "
                "between two and five over a spell is mostly luck."},
    "lead_protection": {
        "label": "Lead protection", "dimension": "game-management",
        "directional": True, "invert": True, "unit": "opp xG/min", "nd": 5,
        "help": "Opponent xG per minute his side spends in front. Per minute "
                "AHEAD, not per match, so a team that leads often is not "
                "punished for it. Minutes ahead are not randomly assigned — "
                "good sides lead more, and against worse teams."},
    "deficit_response": {
        "label": "Deficit response", "dimension": "game-management",
        "directional": True, "invert": False, "unit": "xG/min", "nd": 5,
        "help": "Own xG per minute his side spends behind — how hard it "
                "actually goes after a game it is losing. A leading opponent "
                "drops off, which lifts everybody's number; the comparison is "
                "only meaningful against other sides in the same state."},
    "half_time_correction": {
        "label": "Half-time correction", "dimension": "game-management",
        "directional": True, "invert": False, "unit": "xG/match", "nd": 4,
        "help": "Second-half xG difference minus first-half xG difference, "
                "averaged over the spell's matches. Most of the raw effect is "
                "the opponent's behaviour rather than a team talk, and it is "
                "not restricted to matches he was losing at the break."},
    "sub_impact": {
        "label": "Substitution impact", "dimension": "substitutions",
        "directional": True, "invert": False, "unit": "xG/min", "nd": 5,
        "help": "Own-minus-opponent xG per minute in the 15 minutes after his "
                "first substitution, minus the 15 before, then minus the "
                "league's own figure for the same score state and the same "
                "minute band. Without that control the metric measures the "
                "clock: every side opens up after 70 minutes. It cannot "
                "remove the deeper bias, that a manager substitutes BECAUSE "
                "the game is going badly."},
    "self_inflicted": {
        "label": "Self-inflicted damage", "dimension": "discipline",
        "directional": True, "invert": True, "unit": "/match", "nd": 4,
        "help": "Opta Error events that led to a shot or a goal, per match. "
                "Every Error in the feed carries one of those two flags, so "
                "this is the error count. Known not to repeat well season to "
                "season — kept visible, not treated as a trait."},
    "card_rate": {
        "label": "Card rate", "dimension": "discipline",
        "directional": True, "invert": True, "unit": "/100 opp passes",
        "nd": 4,
        "help": "Cards per 100 opponent passes. Per match would be a "
                "possession artefact — a side with 35% of the ball defends "
                "twice as long. The feed cannot say WHY a card was shown, so "
                "this is cards per unit of defending, not indiscipline."},
    # ---- FINGERPRINT: displayed, never scored ----
    "press_height": {
        "label": "Press height", "dimension": "pressing",
        "directional": False, "invert": False, "unit": "x (0-100)", "nd": 2,
        "help": "Mean x of defensive actions — tackles, interceptions, "
                "challenges, ball recoveries and fouls committed — in the "
                "side's own attacking frame, so 100 is the opponent's goal. "
                "It is where actions HAPPENED, not where the team stood: a "
                "side camped in the opponent half scores high without "
                "pressing. Read it beside ppda."},
    "ppda": {
        "label": "PPDA", "dimension": "pressing",
        "directional": False, "invert": False, "unit": "passes/action",
        "nd": 3,
        "help": "Opponent passes inside their own 60% of the pitch, per own "
                "defensive action in that same 60%. Lower means a more "
                "aggressive press. Not the same number as Understat's PPDA "
                "and must never be pooled with it."},
    "pass_length": {
        "label": "Pass length", "dimension": "possession",
        "directional": False, "invert": False, "unit": "units", "nd": 2,
        "help": "Median of the Length qualifier over every pass in the spell "
                "(present on 100% of passes). Pooled across matches, because "
                "a distribution statistic is not a rate. Set-piece deliveries "
                "are included, so goal kicks and corners sit in the tail."},
    "directness": {
        "label": "Directness", "dimension": "possession",
        "directional": False, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of passes that gain more than 15 units of pitch — "
                "end_x minus x. A style choice, not a virtue: a table that "
                "ranks directness asserts that one way of playing football is "
                "correct."},
    "territory": {
        "label": "Territory", "dimension": "possession",
        "directional": False, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of the side's own touches taken in the final third "
                "(x >= 66.7). Where the team has the ball, not how much of "
                "it — a deep side with 60% possession can score low."},
    "fast_break": {
        "label": "Fast breaks", "dimension": "transition",
        "directional": False, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of the side's shots carrying Opta's FastBreak "
                "qualifier. League-wide this is about 7% of shots, so a spell "
                "with few shots carries a wide error bar."},
    "regain_time": {
        "label": "Time to win it back", "dimension": "pressing",
        "directional": True, "invert": True, "unit": "sec", "nd": 2,
        "help": "Mean seconds between losing the ball and having it again. "
                "Measured from possession runs — a run is consecutive events "
                "by one side — so it is the real out-of-possession spell, not "
                "a proxy like PPDA. Spells longer than "
                f"{int(REGAIN_CAP)}s are dropped: past that it is a stoppage, "
                "a restart or a goal celebration rather than football. NOT "
                "SCORED, and deliberately so — a fast regain is a high press, "
                "a slow one is a low block OR a side being outplayed, and "
                "this number cannot tell those last two apart."},
    "regain_5s": {
        "label": "Won back within 5s", "dimension": "pressing",
        "directional": True, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of losses won back inside five seconds — the "
                "counterpress. Cleaner than the mean above, because five "
                "seconds is short enough that it can only be a deliberate "
                "immediate press and not the slow decay of a low block. Read "
                "the two together: a side can be quick here and still slow on "
                "average, which is a press that either works at once or "
                "drops off."},
    "squad_used": {
        "label": "Players used", "dimension": "squad-use",
        "directional": True, "invert": False, "unit": "players", "nd": 2,
        "help": "How many players took at least "
                f"{int(CORE_SHARE * 100)}% of the minutes available across "
                "the spell — the size of the group he actually trusts, not "
                "the number who got on the pitch. Minutes concentration says "
                "the same thing as an index; this says it as a number of "
                "men, which is the version anyone can read."},
    "minutes_concentration": {
        "label": "Minutes concentration", "dimension": "squad-use",
        "directional": False, "invert": False, "unit": "HHI", "nd": 1,
        "help": "Herfindahl index of minutes across the squad, sum of squared "
                "player shares times 10,000, pooled over the spell. High is a "
                "settled eleven, low is rotation. It falls automatically for a "
                "manager with an injury crisis, which this cannot separate "
                "from choice."},
    "xi_churn": {
        "label": "XI churn", "dimension": "squad-use",
        "directional": False, "invert": False, "unit": "changes/match",
        "nd": 2,
        "help": "Mean number of starting-XI changes between consecutive league "
                "matches inside the spell. Midweek European and cup fixtures "
                "drive rotation and are not in this data at all, so a side in "
                "Europe reads as a rotator for reasons no one chose."},
    "first_sub_minute": {
        "label": "First substitution", "dimension": "substitutions",
        "directional": False, "invert": False, "unit": "min", "nd": 1,
        "help": "Median expanded minute of the side's first substitution. The "
                "median rather than the mean because injuries force early "
                "changes and would drag an average down."},
    "sub_intent": {
        "label": "Substitution intent", "dimension": "substitutions",
        "directional": False, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of substitutions where the incoming player's "
                "PlayerPosition differs from the outgoing player's — a change "
                "of shape rather than a like-for-like swap. Pairing is exact: "
                "3,207 of 3,207 on/off pairs resolve. The label is coarse "
                "(Defender / Midfielder / Forward / Goalkeeper), so a winger "
                "for a striker can read as like-for-like."},
    "shape_repertoire": {
        "label": "Shape repertoire", "dimension": "adaptation",
        "directional": False, "invert": False, "unit": "shapes", "nd": 0,
        "help": "Number of distinct starting formations used, from the "
                "TeamFormation qualifier on the pre-match FormationSet event. "
                "A COUNT, so it grows with the length of the spell — compare "
                "spells of similar length, or nothing. The parquet carries "
                "Opta's numeric shape code, not a name."},
    "shape_changes": {
        "label": "Shape changes", "dimension": "adaptation",
        "directional": False, "invert": False, "unit": "/match", "nd": 3,
        "help": "FormationChange events per match. Opta fires one on "
                "PERSONNEL changes too — a sampled double substitution kept "
                "the same TeamFormation code across it — so this is an upper "
                "bound on genuine restructuring, not a count of it."},
    "corner_profile": {
        "label": "Short corners", "dimension": "set-pieces",
        "directional": False, "invert": False, "unit": "%", "nd": 2,
        "help": "Share of corners played short, taken as a CornerTaken pass "
                "of Length under 15. About 8% league-wide — a clear coached "
                "choice, and one of the few routines fully visible in the "
                "feed."},
    "tactical_foul_x": {
        "label": "Foul height", "dimension": "discipline",
        "directional": False, "invert": False, "unit": "x (0-100)", "nd": 2,
        "help": "Mean x of fouls committed carrying Opta's Defensive "
                "qualifier, in the fouling side's own attacking frame. A "
                "counter-pressing side fouls high to stop the break; a deep "
                "block fouls near its own box. League mean is about 44. It "
                "moves with press height almost mechanically."},
}

METRIC_KEYS: List[str] = list(METRICS)
DIRECTIONAL_KEYS: List[str] = [k for k, m in METRICS.items() if m["directional"]]
FINGERPRINT_KEYS: List[str] = [k for k, m in METRICS.items() if not m["directional"]]
# metrics that cannot be produced without the Understat xG join
XG_KEYS = ("set_piece_balance", "lead_protection", "deficit_response",
           "half_time_correction", "sub_impact")


# ------------------------------------------------------------------ plumbing
def _q(qualifiers) -> Dict[str, Any]:
    """The repo idiom: qualifiers is a native Arrow list of structs, not JSON."""
    if qualifiers is None:
        return {}
    return {x["type"]["displayName"]: x["value"] for x in qualifiers}


def _flag(col: pd.Series) -> pd.Series:
    """is_shot / is_goal come back as object columns holding True or None, not
    as a boolean dtype. Comparing them to True happens to work today; this
    keeps working if the parquet is ever written with a nullable boolean,
    where the same comparison would leave NA in the mask."""
    if col.dtype == bool:
        return col
    out = col.eq(True)
    return out if out.dtype == bool else out.fillna(False).astype(bool)


def _ratio(num: float, den: float, scale: float = 1.0) -> Optional[float]:
    return (num / den) * scale if den else None


def _median_from_counter(counts: Counter) -> Optional[float]:
    total = sum(counts.values())
    if not total:
        return None
    half, run = total / 2.0, 0
    for value in sorted(counts):
        run += counts[value]
        if run >= half:
            return float(value)
    return None


def _band(minute: float) -> int:
    for i, (lo, hi) in enumerate(SUB_BANDS):
        if lo <= minute < hi:
            return i
    return len(SUB_BANDS) - 1


def _state_at(segments: List[Tuple[float, float, str]],
              minute: float) -> Optional[str]:
    for start, stop, state in segments:
        if start <= minute < stop:
            return state
    return segments[-1][2] if segments else None


def _blank() -> Dict[str, Any]:
    return {
        "has_xg": False, "matches": 1,
        "def_x_sum": 0.0, "def_n": 0, "def_high_n": 0,
        "pass_n": 0, "pass_end_n": 0, "direct_n": 0, "pass_own60_n": 0,
        "pass_len": Counter(), "corners": 0, "corner_short": 0,
        "touch_n": 0, "touch_f3_n": 0, "shot_n": 0, "shot_fb_n": 0,
        "cards": 0, "reds": 0, "errors": 0,
        "regain_sum": 0.0, "regain_n": 0, "regain_fast_n": 0,
        "tfoul_x_sum": 0.0, "tfoul_n": 0, "shape_changes": 0,
        "sub_pairs": 0, "sub_diff": 0, "first_sub": None,
        "minutes": {}, "xi": None, "shape": None,
        "min_state": Counter(), "segments": [],
        "xg_state": Counter(), "xg_half": Counter(), "sp_xg": 0.0,
        "shot_xg": [],
        # cross-filled from the opponent's record after both are built
        "opp_pass_n": 0, "opp_pass_own60_n": 0, "opp_sp_xg": 0.0,
        "opp_xg_state": Counter(), "opp_xg_half": Counter(), "opp_shot_xg": [],
        "ht_corr": None, "sub_delta": None, "sub_cell": None,
        "sub_impact": None,
    }


# --------------------------------------------------- the Understat xG bridge
def _team_bridge(ws_dates: Dict[str, set],
                 us_dates: Dict[str, set]) -> Dict[str, str]:
    """WhoScored club -> Understat club, matched on the set of fixture DATES.

    Never on the names. Greedy best Jaccard, each side used once. A club's
    38 dates are close to a fingerprint: measured across the five leagues in
    24/25 the worst true pair scored 0.914 and the worst margin over the
    runner-up was 0.348, while difflib on the names silently maps La Liga's
    "Atletico" onto "Athletic Club"."""
    scored = sorted(
        ((len(dw & du) / len(dw | du), w, u)
         for w, dw in ws_dates.items() for u, du in us_dates.items()),
        reverse=True)
    taken_w, taken_u, out = set(), set(), {}
    for score, w, u in scored:
        if w in taken_w or u in taken_u or score <= 0.0:
            continue
        taken_w.add(w)
        taken_u.add(u)
        out[w] = u
    return out


def _pair_shots(ws_shots: List[Tuple[Any, float]],
                us_shots: List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]:
    """WhoScored shot row index -> the Understat shot that is the same shot.

    In-order when the counts agree and every pair is within three minutes —
    the two feeds list the same shots in the same order — otherwise nearest
    unused minute. Measured on ENG 24/25: 9,870 of 9,883, 98.3% exact."""
    if len(ws_shots) == len(us_shots) and all(
            abs((u.get("minute") or 0) - m) <= 3
            for (_i, m), u in zip(ws_shots, us_shots)):
        return {i: u for (i, _m), u in zip(ws_shots, us_shots)}
    used = [False] * len(us_shots)
    out: Dict[Any, Dict[str, Any]] = {}
    for idx, minute in ws_shots:
        best, best_d = None, 99.0
        for k, u in enumerate(us_shots):
            if used[k]:
                continue
            d = abs((u.get("minute") or 0) - minute)
            if d < best_d:
                best, best_d = k, d
        if best is not None and best_d <= 3:
            used[best] = True
            out[idx] = us_shots[best]
    return out


def _understat_shots(league: str, season: str, inplay: pd.DataFrame,
                     shot_mask: pd.Series) -> Tuple[Dict[Any, Dict[str, Any]], set]:
    """(WhoScored shot row index -> Understat shot, the game ids that joined).

    Both are empty when the season has no Understat shot file (2324 has none),
    which is how the xG metrics end up None rather than wrong. A match that
    fails to join is reported in the second value rather than quietly scoring
    zero xG for both sides."""
    data = ShotEventsService.load(league, season)
    if not data or not data.get("matches"):
        return {}, set()

    games = inplay.groupby("game_id", sort=False).agg(
        date=("game", lambda s: str(s.iloc[0])[:10]))
    teams_of = inplay.groupby("game_id", sort=False)["team"].unique()

    ws_dates: Dict[str, set] = defaultdict(set)
    for gid, row in games.iterrows():
        for team in teams_of[gid]:
            ws_dates[team].add(row.date)
    us_dates: Dict[str, set] = defaultdict(set)
    by_pair: Dict[frozenset, list] = defaultdict(list)
    for match in data["matches"].values():
        us_dates[match["home_team"]].add(match["date"])
        us_dates[match["away_team"]].add(match["date"])
        by_pair[frozenset((match["home_team"], match["away_team"]))].append(match)
    bridge = _team_bridge(ws_dates, us_dates)

    shots_only = inplay[shot_mask]
    by_game = {gid: g for gid, g in shots_only.groupby("game_id", sort=False)}

    out: Dict[Any, Dict[str, Any]] = {}
    joined: set = set()
    for gid, row in games.iterrows():
        sides = list(teams_of[gid])
        if len(sides) != 2:
            continue
        candidates = by_pair.get(frozenset(bridge.get(t, t) for t in sides))
        if not candidates:
            continue
        match = min(candidates, key=lambda m: abs(
            (pd.Timestamp(m["date"]) - pd.Timestamp(row.date)).days))
        game = by_game.get(gid)
        if game is None:
            continue
        for team in sides:
            side = "h" if match["home_team"] == bridge.get(team, team) else "a"
            us_shots = sorted((s for s in match["shots"] if s.get("side") == side),
                              key=lambda s: s.get("minute") or 0)
            own = game[game["team"] == team]
            ws_shots = [(idx, float(m)) for idx, m in
                        zip(own.index, own["minute"].fillna(0.0))]
            out.update(_pair_shots(ws_shots, us_shots))
        joined.add(int(gid))
    return out, joined


# ----------------------------------------------------------- per league-season
def _starting_elevens(df: pd.DataFrame) -> Dict[Tuple[int, str], Tuple[tuple, Any]]:
    """(game_id, team) -> (starting XI player ids, starting shape code).

    FormationSet sits in the PreMatch period — exactly one per team-match —
    and carries InvolvedPlayers (20 ids) beside TeamPlayerFormation (slots
    1-11 then 0 for the bench), so the eleven is the ids whose slot is not 0."""
    out: Dict[Tuple[int, str], Tuple[tuple, Any]] = {}
    for row in df[df["type"] == "FormationSet"].itertuples(index=False):
        q = _q(row.qualifiers)
        ids = str(q.get("InvolvedPlayers") or "").split(",")
        slots = str(q.get("TeamPlayerFormation") or "").split(",")
        if len(ids) != len(slots):
            continue
        xi = []
        for pid, slot in zip(ids, slots):
            try:
                if int(slot.strip()) != 0:
                    xi.append(int(pid.strip()))
            except ValueError:
                continue
        key = (int(row.game_id), str(row.team))
        if key not in out:
            out[key] = (tuple(xi), q.get("TeamFormation"))
    return out


def _accumulate(rec: Dict[str, Any], g: pd.DataFrame, end: float,
                xi: Optional[tuple], shape: Any,
                xg_map: Dict[Any, Dict[str, Any]], has_xg: bool) -> None:
    """One team's half of one match, folded into its record."""
    types = g["type"]
    outcome = g["outcome_type"]
    x = g["x"]
    committed_foul = (types == "Foul") & (outcome == "Unsuccessful")

    # --- pressing: the five contract types, fouls COMMITTED only
    defensive = types.isin(DEF_TYPES) | committed_foul
    dx = x[defensive].dropna()
    rec["def_x_sum"] = float(dx.sum())
    rec["def_n"] = int(dx.size)
    rec["def_high_n"] = int((dx >= PRESS_LINE).sum())

    # --- passing
    passes = types == "Pass"
    px, pex = x[passes], g.loc[passes, "end_x"]
    rec["pass_n"] = int(passes.sum())
    have_end = px.notna() & pex.notna()
    rec["pass_end_n"] = int(have_end.sum())
    rec["direct_n"] = int(((pex - px) > DIRECT_GAIN)[have_end].sum())
    rec["pass_own60_n"] = int((px < OPP_SIXTY).sum())
    for qualifiers in g.loc[passes, "qualifiers"]:
        q = _q(qualifiers)
        raw_len = q.get("Length")
        length = None
        if raw_len is not None:
            try:
                length = float(raw_len)
            except (TypeError, ValueError):
                length = None
        if length is not None:
            rec["pass_len"][round(length, 1)] += 1
        if "CornerTaken" in q:
            rec["corners"] += 1
            if length is not None and length < SHORT_CORNER:
                rec["corner_short"] += 1

    # --- territory and transition. is_shot arrives as object/None rather than
    # a real boolean, so it is coerced rather than compared.
    touch_x = x[_flag(g["is_touch"])].dropna()
    rec["touch_n"] = int(touch_x.size)
    rec["touch_f3_n"] = int((touch_x >= FINAL_THIRD).sum())
    shots = _flag(g["is_shot"])
    rec["shot_n"] = int(shots.sum())
    rec["shot_fb_n"] = sum(1 for qq in g.loc[shots, "qualifiers"]
                           if "FastBreak" in _q(qq))

    # --- discipline
    cards = types == "Card"
    rec["cards"] = int(cards.sum())
    rec["reds"] = int(g.loc[cards, "card_type"].isin(("Red", "SecondYellow")).sum())
    rec["errors"] = sum(
        1 for qq in g.loc[types == "Error", "qualifiers"]
        if {"LeadingToAttempt", "LeadingToGoal"} & set(_q(qq)))
    tfoul = [float(v) for v, qq in zip(x[committed_foul],
                                       g.loc[committed_foul, "qualifiers"])
             if pd.notna(v) and "Defensive" in _q(qq)]
    rec["tfoul_x_sum"] = float(sum(tfoul))
    rec["tfoul_n"] = len(tfoul)
    rec["shape_changes"] = int((types == "FormationChange").sum())

    # --- substitutions. Pairing is via related_player_id, verified exact.
    on = g[types == "SubstitutionOn"]
    off = g[types == "SubstitutionOff"]
    if len(on):
        rec["first_sub"] = float(on["expanded_minute"].min())
    off_pos, off_min = {}, {}
    for row in off.itertuples(index=False):
        if pd.isna(row.player_id):
            continue
        off_pos[int(row.player_id)] = _q(row.qualifiers).get("PlayerPosition")
        off_min[int(row.player_id)] = float(row.expanded_minute)
    on_min = {}
    for row in on.itertuples(index=False):
        if pd.notna(row.player_id):
            on_min[int(row.player_id)] = float(row.expanded_minute)
        if pd.isna(row.related_player_id):
            continue
        came_on = _q(row.qualifiers).get("PlayerPosition")
        went_off = off_pos.get(int(row.related_player_id))
        if came_on and went_off:
            rec["sub_pairs"] += 1
            if came_on != went_off:
                rec["sub_diff"] += 1

    # --- minutes on the pitch, from the XI and the substitution clock
    rec["xi"] = xi
    rec["shape"] = shape
    for pid in (xi or ()):
        rec["minutes"][pid] = max(0.0, off_min.get(pid, end))
    for pid, came in on_min.items():
        rec["minutes"][pid] = max(0.0, off_min.get(pid, end) - came)

    # --- state segments, so a state rate has a real denominator
    states = g["score_state"].tolist()
    minutes = g["expanded_minute"].tolist()
    if states:
        cuts = [0] + [i for i in range(1, len(states)) if states[i] != states[i - 1]]
        for j, i in enumerate(cuts):
            start = 0.0 if j == 0 else float(minutes[i])
            stop = float(minutes[cuts[j + 1]]) if j + 1 < len(cuts) else float(end)
            span = max(0.0, stop - start)
            rec["segments"].append((start, stop, states[i]))
            rec["min_state"][states[i]] += span

    # --- xG, joined from Understat, stated by the WhoScored event it belongs to
    rec["has_xg"] = has_xg
    if not has_xg:
        return
    for idx, state, period, minute in zip(
            g.index[shots], g.loc[shots, "score_state"],
            g.loc[shots, "period"], g.loc[shots, "expanded_minute"]):
        shot = xg_map.get(idx)
        if shot is None:
            continue
        xg = float(shot.get("xg") or 0.0)
        rec["xg_state"][state] += xg
        rec["xg_half"]["1H" if period == "FirstHalf" else "2H"] += xg
        if shot.get("situation") in SP_SITUATIONS:
            rec["sp_xg"] += xg
        rec["shot_xg"].append((float(minute), xg))


def _season_records(league: str, season: str) -> Dict[Tuple[int, str], Dict[str, Any]]:
    """(game_id, team) -> raw counters for that team in that match."""
    path = RAW / league / f"{season}_stamped.parquet"
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    # game_id arrives as float in the part-season files and as int elsewhere;
    # everything downstream keys on it, so it is made one type here
    df["game_id"] = df["game_id"].astype("int64")
    df["_po"] = df["period"].map(PERIOD_ORDER).fillna(9).astype(int)
    df["_sec"] = df["second"].fillna(0.0)
    inplay = df[df["period"].isin(IN_PLAY)].sort_values(
        ["game_id", "_po", "minute", "_sec"], kind="stable")

    elevens = _starting_elevens(df)
    shot_mask = _flag(inplay["is_shot"])
    xg_map, joined = _understat_shots(league, season, inplay, shot_mask)
    match_end = inplay.groupby("game_id")["expanded_minute"].max().to_dict()

    records: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for (gid, team), g in inplay.groupby(["game_id", "team"], sort=False):
        gid, team = int(gid), str(team)
        rec = _blank()
        xi, shape = elevens.get((gid, team), (None, None))
        _accumulate(rec, g, float(match_end.get(gid, 0.0)), xi, shape,
                    xg_map, gid in joined)
        records[(gid, team)] = rec

    _regains(records, inplay)
    _cross_fill(records, inplay, match_end)
    _fit_sub_baseline(records)
    return records


def _regains(records: Dict[Tuple[int, str], Dict[str, Any]],
             inplay: pd.DataFrame) -> None:
    """How long each side spends without the ball, per spell of losing it.

    NEEDS BOTH SIDES AT ONCE, which is why it cannot live in _accumulate:
    that is handed one team's events, and a possession change is by
    definition a fact about two. The events are already sorted by
    (game, period, minute, second) upstream.

    A possession run is a maximal consecutive stretch of events by one side.
    The time a team is OUT of possession is then the gap between the end of
    one of its own runs and the start of its next — which is exactly the
    question, and needs no possession id in the feed to answer.

    Runs are cut at a period boundary. Half time is not a possession the
    other side is enjoying.
    """
    for gid, g in inplay.groupby("game_id", sort=False):
        gid = int(gid)
        secs = (g["expanded_minute"].astype(float) * 60.0
                + g["_sec"].astype(float)).to_numpy()
        teams = g["team"].to_numpy()
        pers = g["_po"].to_numpy()

        runs: List[List[Any]] = []          # [team, start, end, period]
        for i, tm in enumerate(teams):
            if tm is None or tm != tm:      # NaN team: a neutral event
                continue
            if runs and runs[-1][0] == tm and runs[-1][3] == pers[i]:
                runs[-1][2] = secs[i]
            else:
                runs.append([tm, secs[i], secs[i], pers[i]])

        seen: Dict[Any, Tuple[float, int]] = {}
        for tm, start, end, per in runs:
            prev = seen.get(tm)
            if prev is not None and prev[1] == per:
                gap = start - prev[0]
                rec = records.get((gid, str(tm)))
                if rec is not None and 0.0 <= gap <= REGAIN_CAP:
                    rec["regain_sum"] += gap
                    rec["regain_n"] += 1
                    if gap <= REGAIN_FAST:
                        rec["regain_fast_n"] += 1
            seen[tm] = (end, per)


def _cross_fill(records: Dict[Tuple[int, str], Dict[str, Any]],
                inplay: pd.DataFrame, match_end: Dict[int, float]) -> None:
    """Hand each record the opponent's half of the same match.

    PPDA, card_rate, set_piece_balance and every xG difference are two-sided,
    and a spell aggregation cannot reach across to the other team afterwards."""
    for gid, sides in inplay.groupby("game_id", sort=False)["team"].unique().items():
        if len(sides) != 2:
            continue
        gid = int(gid)
        a, b = records.get((gid, str(sides[0]))), records.get((gid, str(sides[1])))
        if a is None or b is None:
            continue
        for rec, opp in ((a, b), (b, a)):
            rec["opp_pass_n"] = opp["pass_n"]
            rec["opp_pass_own60_n"] = opp["pass_own60_n"]
            rec["opp_sp_xg"] = opp["sp_xg"]
            rec["opp_xg_state"] = opp["xg_state"]
            rec["opp_xg_half"] = opp["xg_half"]
            rec["opp_shot_xg"] = opp["shot_xg"]
            if rec["has_xg"]:
                rec["ht_corr"] = ((rec["xg_half"]["2H"] - opp["xg_half"]["2H"])
                                  - (rec["xg_half"]["1H"] - opp["xg_half"]["1H"]))
            _sub_window(rec, float(match_end.get(gid, 0.0)))


def _sub_window(rec: Dict[str, Any], end: float) -> None:
    """The raw before/after swing around the first substitution, and the cell
    the league baseline will be read from."""
    t = rec["first_sub"]
    if t is None or not rec["has_xg"]:
        return
    lo, hi = max(0.0, t - SUB_WINDOW), min(end, t + SUB_WINDOW)
    before_len, after_len = t - lo, hi - t
    if before_len < MIN_WINDOW or after_len < MIN_WINDOW:
        return

    def window(shots, a, b, closed_left):
        return sum(v for m, v in shots
                   if (a <= m < b if closed_left else a < m <= b))

    own_b = window(rec["shot_xg"], lo, t, True)
    opp_b = window(rec["opp_shot_xg"], lo, t, True)
    own_a = window(rec["shot_xg"], t, hi, False)
    opp_a = window(rec["opp_shot_xg"], t, hi, False)
    rec["sub_delta"] = ((own_a - opp_a) / after_len) - ((own_b - opp_b) / before_len)
    rec["sub_cell"] = (_state_at(rec["segments"], t), _band(t))


def _fit_sub_baseline(records: Dict[Tuple[int, str], Dict[str, Any]]) -> None:
    """Fit the game-state control ACROSS THE WHOLE LEAGUE-SEASON.

    A side one down at 70 minutes creates more xG whoever came on. Fitting
    this per spell would measure every manager against a different baseline,
    so the league's own before/after swing for that score_state in that minute
    band is subtracted. Thin cells fall back to the state, then to the league."""
    cell: Dict[tuple, List[float]] = defaultdict(list)
    state: Dict[Optional[str], List[float]] = defaultdict(list)
    whole: List[float] = []
    for rec in records.values():
        if rec["sub_delta"] is None:
            continue
        cell[rec["sub_cell"]].append(rec["sub_delta"])
        state[rec["sub_cell"][0]].append(rec["sub_delta"])
        whole.append(rec["sub_delta"])
    if not whole:
        return
    grand = sum(whole) / len(whole)
    for rec in records.values():
        if rec["sub_delta"] is None:
            continue
        here = cell[rec["sub_cell"]]
        same = state[rec["sub_cell"][0]]
        if len(here) >= MIN_CELL:
            base = sum(here) / len(here)
        elif len(same) >= MIN_CELL:
            base = sum(same) / len(same)
        else:
            base = grand
        rec["sub_impact"] = rec["sub_delta"] - base


# ------------------------------------------------------------- the spell fold
def _fold(recs: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Every metric for one spell. Ratios are a RATIO OF SUMS over the spell's
    matches, never a mean of per-match ratios: one low-denominator afternoon
    would otherwise decide the number."""
    n = len(recs)
    xg_recs = [r for r in recs if r["has_xg"]]
    n_xg = len(xg_recs)

    def total(key: str, rows=None) -> float:
        return float(sum(r[key] for r in (recs if rows is None else rows)))

    raw: Dict[str, Optional[float]] = {}

    # ---- directional ----
    raw["set_piece_balance"] = _ratio(
        total("sp_xg", xg_recs) - total("opp_sp_xg", xg_recs), n_xg)
    raw["sendings_off"] = _ratio(total("reds"), n)
    raw["self_inflicted"] = _ratio(total("errors"), n)
    raw["card_rate"] = _ratio(total("cards"), total("opp_pass_n"), 100.0)

    min_ahead = sum(r["min_state"]["ahead"] for r in xg_recs)
    opp_xg_we_ahead = sum(r["opp_xg_state"]["behind"] for r in xg_recs)
    raw["lead_protection"] = (_ratio(opp_xg_we_ahead, min_ahead)
                              if min_ahead >= MIN_STATE_MINUTES else None)
    min_behind = sum(r["min_state"]["behind"] for r in xg_recs)
    raw["deficit_response"] = (_ratio(sum(r["xg_state"]["behind"] for r in xg_recs),
                                      min_behind)
                               if min_behind >= MIN_STATE_MINUTES else None)

    ht = [r["ht_corr"] for r in xg_recs if r["ht_corr"] is not None]
    raw["half_time_correction"] = sum(ht) / len(ht) if ht else None
    impacts = [r["sub_impact"] for r in recs if r["sub_impact"] is not None]
    raw["sub_impact"] = sum(impacts) / len(impacts) if impacts else None

    # ---- fingerprint ----
    raw["press_height"] = _ratio(total("def_x_sum"), total("def_n"))
    raw["ppda"] = _ratio(total("opp_pass_own60_n"), total("def_high_n"))
    lengths = Counter()
    for r in recs:
        lengths.update(r["pass_len"])
    raw["pass_length"] = _median_from_counter(lengths)
    raw["directness"] = _ratio(total("direct_n"), total("pass_end_n"), 100.0)
    raw["territory"] = _ratio(total("touch_f3_n"), total("touch_n"), 100.0)
    raw["fast_break"] = _ratio(total("shot_fb_n"), total("shot_n"), 100.0)
    raw["corner_profile"] = _ratio(total("corner_short"), total("corners"), 100.0)
    raw["tactical_foul_x"] = _ratio(total("tfoul_x_sum"), total("tfoul_n"))
    raw["sub_intent"] = _ratio(total("sub_diff"), total("sub_pairs"), 100.0)
    raw["shape_changes"] = _ratio(total("shape_changes"), n)

    # RATIO OF SUMS, not the mean of per-match rates: a match with six
    # possession changes would otherwise weigh as much as one with ninety.
    raw["regain_time"] = _ratio(total("regain_sum"), total("regain_n"))
    raw["regain_5s"] = _ratio(total("regain_fast_n"), total("regain_n"), 100.0)

    minutes: Dict[int, float] = defaultdict(float)
    for r in recs:
        for pid, played in r["minutes"].items():
            minutes[pid] += played
    squad = sum(minutes.values())
    raw["minutes_concentration"] = (
        sum((m / squad) ** 2 for m in minutes.values()) * 10000.0
        if squad > 0 else None)
    # 🐛 THE DENOMINATOR IS ONE PLAYER'S MAXIMUM, NOT THE TEAM'S.
    # This first read 11 * 90 * matches — the whole team's minutes — and
    # compared one man against a quarter of it. Over 38 matches that asks for
    # 9,405 minutes from a player who can physically play 3,420, so the count
    # came out as 0 for every manager in the league and looked like a missing
    # feed rather than arithmetic. A SHARE needs the denominator its numerator
    # could actually reach.
    available = 90.0 * n if n else 0.0
    raw["squad_used"] = (
        float(sum(1 for m in minutes.values() if m >= available * CORE_SHARE))
        if available > 0 else None)

    shapes = {r["shape"] for r in recs if r["shape"] is not None}
    raw["shape_repertoire"] = float(len(shapes)) if shapes else None

    # consecutive matches only — the records arrive in the spell's own order
    churn, pairs = 0, 0
    for prev, here in zip(recs, recs[1:]):
        if prev["xi"] and here["xi"]:
            churn += 11 - len(set(prev["xi"]) & set(here["xi"]))
            pairs += 1
    raw["xi_churn"] = churn / pairs if pairs else None

    # the median, not the mean: injuries force early changes and would drag
    # an average down without saying anything about how he uses the bench
    first = [r["first_sub"] for r in recs if r["first_sub"] is not None]
    raw["first_sub_minute"] = statistics.median(first) if first else None

    out: Dict[str, Optional[float]] = {}
    for key in METRIC_KEYS:
        value = raw.get(key)
        if value is None:
            out[key] = None
            continue
        nd = METRICS[key]["nd"]
        out[key] = int(round(float(value))) if nd == 0 else round(float(value), nd)
    return out


@lru_cache(maxsize=8)
def _cached(league: str, seasons: tuple) -> List[Dict[str, Any]]:
    records: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for season in seasons:
        for key, rec in _season_records(league, season).items():
            records.setdefault(key, rec)

    spells = build_spells(league, list(seasons), absorb_short=False)
    rows: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    for spell in spells:
        # spell.games is in kickoff order, which is what xi_churn needs
        mine = [records[(gid, spell.team)] for gid in spell.games
                if (gid, spell.team) in records]
        if not mine:
            continue
        # 🐛 THE ROW IS ITS SPELL, NOT ITS (TEAM, MANAGER). Simon Rusk took
        # Southampton for one match and again for seven; without this field a
        # consumer had nothing else to file the two rows by, so the seven-match
        # spell's numbers were published on the one-match row and the
        # seven-match row shipped entirely null. The tell was a count of 0.5714
        # errors on a single match — an average over seven wearing one's name.
        row = {
            "key": spell.key,
            "manager": spell.manager,
            "team": spell.team,
            "matches": len(mine),
            "short": len(mine) < MIN_SPELL,
            "start": spell.start,
            "end": spell.end,
            "seasons": list(spell.seasons),
            "raw": _fold(mine),
        }
        clash = seen.get(row["key"])
        if clash is not None:
            # Spell.key ends in min(games) and two spells cannot share a game,
            # so this is unreachable unless the spell builder changes shape.
            # It is checked because the contract downstream is "one row, one
            # spell" — a silent duplicate here becomes a wrong published row.
            raise RuntimeError(
                f"two spells share key {row['key']!r}: "
                f"{clash['matches']} matches from {clash['start'][:10]} and "
                f"{row['matches']} from {row['start'][:10]}")
        seen[row["key"]] = row
        rows.append(row)
    rows.sort(key=lambda r: (r["team"], r["start"]))
    return rows


def spell_metrics(league: str, seasons: Sequence[str]) -> List[Dict[str, Any]]:
    """One row per manager spell in `league` over `seasons`.

        {"key", "manager", "team", "matches", "short", "start", "end",
         "seasons": [...], "raw": {metric_key: float or None}}

    `key` is the Spell's own key — "{team}|{manager}|{first game id}" — and is
    the row's identity. It is unique across the returned rows. (team, manager)
    is NOT: one manager can hold two spells at one club, and filing rows by
    the pair merges them.

    `matches` counts the spell's fixtures actually present in the event files,
    and `short` is measured against that rather than against the cache, so a
    spell is never described as longer than what was measured.

    Results are cached per (league, seasons); each caller is handed its own
    copy, so a builder that annotates a row cannot corrupt the next caller's."""
    return [{**row, "raw": dict(row["raw"]), "seasons": list(row["seasons"])}
            for row in _cached(league, tuple(seasons))]


if __name__ == "__main__":  # a quick eyeball, one league-season
    import sys

    lg = sys.argv[1] if len(sys.argv) > 1 else "ENG-Premier League"
    ss = sys.argv[2:] or ["2425"]
    for row in sorted(spell_metrics(lg, ss), key=lambda r: -r["matches"])[:8]:
        print(f"\n{row['manager']} ({row['team']}) {row['matches']} matches"
              f"{'  SHORT' if row['short'] else ''}")
        for key in METRIC_KEYS:
            print(f"   {key:22s} {row['raw'][key]}")
