"""Every shot, with its xG, per club — the payload a shot map draws.

Understat carries what WhoScored's event stream does not: an xG for each
individual attempt, plus the situation, the shot type and who laid it on.
That is the difference between a map of where shots were taken and a map of
what they were worth, and it is the whole reason a shot map is interesting.

PACKED, not written longhand. A club takes about five hundred shots a
season; as objects with named fields that is 40 KB a club-season of the
words "situation" and "MissedShots". As rows of numbers against a key list
it is a fifth of that, and the page unpacks it in one pass.

Understat's frame: x and y both 0-1 over a 105 by 68 pitch, x = 1 at the
goal being attacked. Penalties sit at exactly (0.885, 0.500) in every match
on file, which confirms both axes. Which touchline y = 0 means is NOT
settled by the data — right-footed and left-footed shooters have almost
identical mean y (0.500 against 0.510) — so if a finished map looks
mirrored, that is the thing to flip.

Writes data/web/shots/{league}/{season}.json

Usage: .venv/Scripts/python.exe scripts/build_shot_web.py
"""
import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "understat"
OUT = ROOT / "data" / "web" / "shots"
PUB = ROOT / "web" / "public" / "data" / "shots"

RESULTS = ["Goal", "SavedShot", "MissedShots", "BlockedShot",
           "ShotOnPost", "OwnGoal"]

# WHERE IN THE GOAL IT WENT. Understat has the xG and no placement;
# WhoScored has the placement on 100% of its shots and no xG. Joining them
# is the only way to have both, and it is worth the trouble: a goal drawn
# where it actually crossed the line is the one thing that makes a net in a
# 3D scene do any work.
#
# Opta's goal-mouth frame, read off the data rather than assumed: goals
# never leave y 45.4-54.6 or z 0.6-36.1, shots off the post reach y 44.5 and
# z 41.8, and misses spill to y 30-71 and z 100. So the posts stand at
# y = 45.2 and 54.8 and the bar at z = 38.
POST_Y = (45.2, 54.8)
BAR_Z = 38.0
GOAL_M = 7.32
BAR_M = 2.44
SITUATIONS = ["OpenPlay", "FromCorner", "SetPiece", "DirectFreekick",
              "Penalty"]
FEET = ["RightFoot", "LeftFoot", "Head", "OtherBodyPart"]
KEYS = ["x", "y", "xg", "result", "situation", "foot", "minute",
        "player", "assist", "opponent", "home", "gx", "gz"]


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


# LOWERCASING IS NOT ENOUGH TO MATCH A NAME ACROSS TWO FEEDS.
# "Odegaard".lower() is "odegaard" and "Odegaard".lower() with the Norwegian
# slashed O is "ødegaard", and those are simply different strings — so
# every one of Martin Odegaard's shots lost its placement while the club
# around him sat at 81%. One player at exactly 0% is the shape of a name
# mismatch, never of a flaky join.
#
# Accented letters decompose under NFKD and the marks can then be dropped,
# but the ones below have no canonical decomposition at all: they are
# separate letters in their own alphabets, so they need naming.
_LETTERS = str.maketrans({
    "ø": "o", "Ø": "o",      # o-slash   Odegaard, Hojlund
    "đ": "d", "Đ": "d",      # d-stroke  Dordevic
    "ł": "l", "Ł": "l",      # l-stroke  Blaszczykowski
    "ð": "d", "Ð": "d",      # eth
    "þ": "th", "Þ": "th",    # thorn
    "ı": "i",                     # dotless i (Turkish)
    "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe",
    "ß": "ss",
})


def fold(name: str) -> str:
    """A name reduced to plain ASCII letters, for comparing across feeds."""
    s = unicodedata.normalize("NFKD", name or "").translate(_LETTERS)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def surname(name: str) -> str:
    parts = (name or "").strip().split()
    return fold(parts[-1]) if parts else ""


def placement(league: str, season: str) -> dict:
    """(date, minute, surname) -> where the ball crossed the goal line.

    Matched on the surname rather than the full name: the two feeds disagree
    on about one name in eight — "Andy Robertson" against "Andrew Robertson",
    "Amad Diallo" against "Amad Diallo Traore" — and a surname plus a minute
    inside the same fixture is specific enough that a wrong pairing would
    need two players of the same surname shooting in the same minute.

    Returns metres in the goal's own frame: across from the centre, and
    height off the ground.
    """
    import pandas as pd
    from services.mental.positions import load_match

    raw = ROOT / "data" / "whoscored" / league / f"{season}_stamped.parquet"
    if not raw.exists():
        return {}
    df = pd.read_parquet(raw, columns=["game_id", "type", "player", "minute",
                                       "goal_mouth_y", "goal_mouth_z"])
    df = df[df["type"].isin(["Goal", "SavedShot", "MissedShots",
                             "ShotOnPost"])]
    dates = {}
    for gid in df["game_id"].unique():
        doc = load_match(league, season, gid)
        if doc:
            kick = doc.get("startTime") or doc.get("startDate") or ""
            dates[int(gid)] = kick[:10]

    out = {}
    span = POST_Y[1] - POST_Y[0]
    for r in df.dropna(subset=["goal_mouth_y", "goal_mouth_z"]).itertuples(
            index=False):
        date = dates.get(int(r.game_id))
        if not date:
            continue
        gx = ((float(r.goal_mouth_y) - 50.0) / span) * GOAL_M
        gz = (float(r.goal_mouth_z) / BAR_Z) * BAR_M
        out[(date, int(r.minute), surname(r.player))] = (round(gx, 3),
                                                         round(gz, 3))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", action="append", dest="seasons")
    args = ap.parse_args()
    lk = slug(args.league)
    folder = SRC / args.league / "shots"
    seasons = args.seasons or sorted(
        p.stem for p in folder.glob("*.json") if p.stem.isdigit())

    for season in seasons:
        path = folder / f"{season}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        place = placement(args.league, season)
        per = defaultdict(list)
        names: dict = {}
        opponents: dict = {}
        hit = miss = 0

        def idx(store: dict, value: str) -> int:
            if not value:
                return -1
            if value not in store:
                store[value] = len(store)
            return store[value]

        for match in d["matches"].values():
            home, away = match["home_team"], match["away_team"]
            date = str(match.get("date") or "")[:10]
            for s in match.get("shots") or []:
                team = home if s["side"] == "h" else away
                other = away if s["side"] == "h" else home
                # the minute can differ by one between the two feeds
                sn = surname(s.get("player") or "")
                got = None
                for dm in (0, -1, 1):
                    got = place.get((date, int(s["minute"]) + dm, sn))
                    if got:
                        break
                # A GOAL THAT LANDED OUTSIDE THE FRAME IS A BAD JOIN, not a
                # miracle. Surname plus minute is specific enough almost
                # always, but a player who shoots, sees it blocked and scores
                # the rebound inside the same minute can pick up the wrong
                # one of his own attempts. One in 955 did. A miss outside the
                # frame is perfectly real, so this only guards goals.
                if got and s["result"] == "Goal":
                    if abs(got[0]) > GOAL_M / 2 or not 0 <= got[1] <= BAR_M:
                        got = None
                if got:
                    hit += 1
                else:
                    miss += 1
                per[team].append([
                    round(float(s["x"]), 4),
                    round(float(s["y"]), 4),
                    round(float(s["xg"]), 4),
                    RESULTS.index(s["result"]) if s["result"] in RESULTS else -1,
                    SITUATIONS.index(s["situation"])
                    if s["situation"] in SITUATIONS else -1,
                    FEET.index(s["shot_type"]) if s["shot_type"] in FEET else -1,
                    int(s["minute"]),
                    idx(names, s.get("player") or ""),
                    idx(names, s.get("assist_player") or ""),
                    idx(opponents, other),
                    1 if s["side"] == "h" else 0,
                    got[0] if got else None,
                    got[1] if got else None,
                ])

        payload = {
            "league": args.league, "season": season,
            "keys": KEYS, "results": RESULTS, "situations": SITUATIONS,
            "feet": FEET,
            "players": [n for n, _i in sorted(names.items(),
                                              key=lambda kv: kv[1])],
            "opponents": [n for n, _i in sorted(opponents.items(),
                                                key=lambda kv: kv[1])],
            "teams": {t: rows for t, rows in sorted(per.items())},
        }
        for root in (OUT, PUB):
            (root / lk).mkdir(parents=True, exist_ok=True)
            (root / lk / f"{season}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        kb = (OUT / lk / f"{season}.json").stat().st_size // 1024
        tot = sum(len(v) for v in per.values())
        goals = sum(1 for v in per.values() for r in v if r[3] == 0)
        gplaced = sum(1 for v in per.values()
                      for r in v if r[3] == 0 and r[11] is not None)
        print(f"  {season}: {len(per)} clubs, {tot} shots, {goals} goals, "
              f"{kb} KB")
        print(f"      placement joined for {hit} of {hit + miss} shots "
              f"({100 * hit / max(hit + miss, 1):.0f}%), "
              f"{gplaced} of {goals} goals ({100 * gplaced / max(goals, 1):.0f}%)")

    print()
    print(f"-> {OUT / lk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
