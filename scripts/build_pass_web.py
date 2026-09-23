"""Every pass a club played, packed small enough to draw in a browser.

WHY THE RAW STREAM CANNOT JUST BE SHIPPED. A league season is 362,739
passes across 380 matches — 955 a match, which is why passing is the one
event type where the volume is the whole design problem. Written as objects
with named fields and full player names on every row, one club's season is
several megabytes. As a flat array of small integers against key lists the
file already carries, it is a fraction of that and the page unpacks it in a
single pass.

The raw event stream itself never leaves the machine (it is gitignored, and
hundreds of MB); this is a derived, published view of it.

FRAME. WhoScored records every event in the ACTING TEAM'S attacking
direction, which is the one thing that has to be true for any of this to
mean anything, so it was checked rather than assumed: shots average x = 85.7
for the home side and 85.8 for the away side, clearances 14.5 and 14.3,
corners sit at x = 99.5 on both flanks. So x = 100 is always the goal the
passer is attacking, and `toX` / `toZ` in the client apply unchanged.

Writes data/web/passes/{league}/{season}/{club}.json and the served copy.

Usage: .venv/Scripts/python.exe scripts/build_pass_web.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
OUT = ROOT / "data" / "web" / "passes"
PUB = ROOT / "web" / "public" / "data" / "passes"

# ONE BIT PER THING WORTH FILTERING ON, because a pass carries a dozen
# properties and a dozen columns of "true"/"false" is most of the file.
BITS = {
    "ok": 1,        # completed
    "air": 2,       # left the ground — the only thing 3D can say that 2D cannot
    "cross": 4,
    "through": 8,
    "key": 16,      # led to a shot
    "assist": 32,   # led to a goal
    "set": 64,      # a restart, not open play
    "long": 128,
    "big": 256,     # big chance created
    "head": 512,
}

# A PASS THAT LEFT THE GROUND. This is the judgement the whole visual rests
# on, so it is drawn from Opta's own qualifiers rather than guessed from
# length: a 40m ball along the floor and a 40m diagonal over the top are
# different actions and the flat map cannot tell them apart.
#   Chipped  — lifted deliberately
#   Longball — Opta's long, lofted delivery
#   Cross    — into the box from wide, almost always in the air
#   HeadPass — played with the head, so the ball was already up
AERIAL = {"Chipped", "Longball", "Cross", "HeadPass"}
SET_PIECE = {"ThrowIn", "CornerTaken", "FreekickTaken", "GoalKick",
             "KeeperThrow", "IndirectFreekickTaken", "ThrowinSetPiece",
             "SetPiece"}
# Counted across the whole 25/26 stream rather than assumed from a sample:
# ShotAssist 6,461, IntentionalAssist 4,480, IntentionalGoalAssist 536,
# BigChanceCreated 1,157. There is no plain "Assist" or "GoalAssist"
# qualifier in this feed, and `related_event_id` is set on 0% of passes, so
# there is no way to walk from a pass to the shot it created.
#
# 536 against 1,045 goals is a little over half, and that is what the
# qualifier MEANS — an assist Opta judged intentional. Deflections, miscued
# crosses and scuffed shots that fall kindly are assists in a table and are
# not flagged here. The label says "intentional" for that reason rather than
# quietly presenting half the assists in the league as all of them.
KEY = {"KeyPass", "ShotAssist", "IntentionalAssist"}
ASSIST = {"IntentionalGoalAssist"}

KEYS = ["x", "y", "ex", "ey", "flags", "player", "minute", "opponent", "home",
        "to"]
STRIDE = len(KEYS)

# WHO RECEIVED IT IS NOT RECORDED. `related_player_id` is set on 0% of
# passes in this feed, so the only route is the next event in the stream —
# if a completed pass is followed by a teammate doing something, that
# teammate had the ball.
#
# Measured rather than hoped for: across 290,873 completed passes in EPL
# 25/26 the next event is the same game, the same team and a different named
# player **99.1%** of the time, and it is another Pass in 86% of those, which
# is exactly the shape of possession moving on. The 0.9% that fail are
# mostly an opponent's Challenge landing between the two, where the receiver
# is genuinely ambiguous.
#
# It is still an INFERENCE and the client says so. A pass that reaches a
# teammate who is immediately fouled attributes to him correctly; one that
# deflects off a defender to a teammate attributes to the teammate, which is
# right for a pass map and wrong for a passing network. Good enough for
# "where did the ball go", not evidence of intent.


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def qnames(q) -> set[str]:
    """The qualifier display names on one event.

    They arrive as an array of {"type": {"displayName": ...}, "value": ...},
    which is why this cannot be a vectorised column operation.
    """
    if q is None:
        return set()
    out = set()
    for d in q:
        if not isinstance(d, dict):
            continue
        t = d.get("type")
        if isinstance(t, dict):
            t = t.get("displayName")
        if isinstance(t, str):
            out.add(t)
    return out


def home_side(game: str, teams: tuple[str, ...]) -> str | None:
    """Which of the two is at home, read off the fixture string.

    Split on the hyphen and a French club ends the season playing itself:
    "Saint-Etienne-Lyon" has three parts and no way to tell which two are
    the names. Testing each known team as a PREFIX has no such problem.
    """
    rest = game.split(" ", 1)[1] if " " in game else game
    for t in teams:
        if rest.startswith(t + "-"):
            return t
    return None


def build(df: pd.DataFrame) -> dict[str, dict]:
    """All of one season's passes, grouped by the club that played them."""
    # Chronological, STABLY, so events inside the same second keep the order
    # the feed gave them — that order is the only thing telling us who got
    # the ball next.
    seq = df.sort_values(["game_id", "period", "expanded_minute", "second"],
                         kind="stable").reset_index(drop=True)
    seq = seq.assign(
        r_game=seq["game_id"].shift(-1),
        r_team=seq["team"].shift(-1),
        r_player=seq["player"].shift(-1),
    )
    ps = seq[seq["type"] == "Pass"]
    ps = ps.dropna(subset=["x", "y", "end_x", "end_y", "player"])

    opponent: dict[tuple[int, str], str] = {}
    at_home: dict[tuple[int, str], bool] = {}
    for gid, m in df.groupby("game_id", sort=False):
        sides = tuple(m["team"].dropna().unique())
        if len(sides) != 2:
            continue
        h = home_side(str(m["game"].iloc[0]), sides)
        for t in sides:
            other = sides[0] if sides[1] == t else sides[1]
            opponent[(gid, t)] = other
            at_home[(gid, t)] = (h == t) if h else False

    rows: dict[str, list[int]] = defaultdict(list)
    players: dict[str, dict[str, int]] = defaultdict(dict)
    opps: dict[str, dict[str, int]] = defaultdict(dict)
    games: dict[str, set] = defaultdict(set)
    tally: dict[str, int] = defaultdict(int)

    for r in ps.itertuples(index=False):
        q = qnames(r.qualifiers)
        flags = 0
        if r.outcome_type == "Successful":
            flags |= BITS["ok"]
        if q & AERIAL:
            flags |= BITS["air"]
        if "Cross" in q:
            flags |= BITS["cross"]
        if "Throughball" in q:
            flags |= BITS["through"]
        if q & KEY:
            flags |= BITS["key"]
        if q & ASSIST:
            flags |= BITS["assist"]
        if q & SET_PIECE:
            flags |= BITS["set"]
        if "Longball" in q:
            flags |= BITS["long"]
        if "BigChanceCreated" in q:
            flags |= BITS["big"]
        if "HeadPass" in q:
            flags |= BITS["head"]

        team = r.team
        who = players[team].setdefault(r.player, len(players[team]))

        # only a completed pass HAS a receiver; -1 is "nobody, or nobody we
        # can name", and the client draws that as unknown rather than blank
        to = -1
        if (flags & BITS["ok"] and isinstance(r.r_player, str)
                and r.r_game == r.game_id and r.r_team == team
                and r.r_player != r.player):
            to = players[team].setdefault(r.r_player, len(players[team]))
            tally[f"{team}|to"] += 1

        opp_name = opponent.get((r.game_id, team), "")
        opp = opps[team].setdefault(opp_name, len(opps[team]))
        games[team].add(r.game_id)
        for name, bit in BITS.items():
            if flags & bit:
                tally[f"{team}|{name}"] += 1

        # Opta units x10: a tenth of a unit is about 10cm, which is finer
        # than the source is honest to, and it keeps every value a short
        # integer rather than a decimal with three characters of noise.
        rows[team].extend((
            round(r.x * 10), round(r.y * 10),
            round(r.end_x * 10), round(r.end_y * 10),
            flags, who, int(r.expanded_minute), opp,
            1 if at_home.get((r.game_id, team)) else 0,
            to,
        ))

    out = {}
    for team, flat in rows.items():
        names = sorted(players[team], key=players[team].get)
        opp_names = sorted(opps[team], key=opps[team].get)
        out[team] = {
            "club": team,
            "matches": len(games[team]),
            "passes": len(flat) // STRIDE,
            "keys": KEYS,
            "stride": STRIDE,
            "bits": BITS,
            "players": names,
            "opponents": opp_names,
            "rows": flat,
        }
    return out, tally


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default=None, help="one season, or all on disk")
    args = ap.parse_args()

    folder = RAW / args.league
    seasons = ([args.season] if args.season else
               sorted(p.stem for p in folder.glob("*.parquet")
                      if not p.stem.endswith("_stamped")))
    if not seasons:
        print(f"no event parquet under {folder}")
        return 1

    lk = slug(args.league)
    for season in seasons:
        path = folder / f"{season}.parquet"
        if not path.exists():
            print(f"  {season}: no parquet, skipped")
            continue
        df = pd.read_parquet(path)
        per, tally = build(df)

        total = 0
        for root in (OUT, PUB):
            d = root / lk / season
            d.mkdir(parents=True, exist_ok=True)
            for team, payload in per.items():
                f = d / f"{slug(team)}.json"
                f.write_text(json.dumps(payload, ensure_ascii=False),
                             encoding="utf-8")
                if root is OUT:
                    total += f.stat().st_size
        n = sum(p["passes"] for p in per.values())
        big = max(per.values(), key=lambda p: p["passes"])
        print(f"  {season}: {len(per)} clubs, {n:,} passes, "
              f"{total // 1024} KB total, "
              f"biggest {slug(big['club'])} "
              f"{(OUT / lk / season / (slug(big['club']) + '.json')).stat().st_size // 1024} KB")
        share = defaultdict(int)
        for k, v in tally.items():
            share[k.split("|")[1]] += v
        pct = {k: f"{100 * v / n:.1f}%" for k, v in sorted(share.items())}
        print(f"      {pct}")

    print(f"\n-> {OUT / lk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
