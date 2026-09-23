"""Per-club drawing material: shots, average positions, pass networks.

Everything else in the team layer collapses to one number per cut. These
three cannot — a shot map needs the shots, not their mean — so they get
their own file per club, fetched only by the page that draws them.

SHOTS are stored ONCE and TAGGED with their season and manager spell rather
than duplicated into every cut. A club takes about two thousand shots across
four seasons; copying them into a pooled cut, four season cuts and three
spell cuts would be eight copies of the same afternoon. The page filters.

POSITIONS and PASSES are aggregates, so they are stored per cut — but only
for cuts with enough football in them to mean anything.

Writes data/web/team/{league}/plots/{club}.json and the served copy.

Usage: .venv/Scripts/python.exe scripts/build_team_plots.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from services.mental.plots import match_plots, merge, new_acc, pack
from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.spells import build as build_spells

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"
MIN_MATCHES = 4        # below this a pass network is a rumour

# A shot as five numbers instead of nine named fields. Written as objects the
# 27 clubs came to 8.5 MB, and almost none of it was the shots: every one
# carried its manager's full spell key ("Nottingham Forest|Nuno Espírito
# Santo|1770062") and its own copy of the words x, y, g, t, b, s, p, h. The
# flags fold into one bitmask, season and spell become indexes into lists the
# file already ships, and the same information lands in a twentieth of the
# space. Same trick as the mental payload, same reason.
SHOT_KEYS = ["x", "y", "f", "sn", "sp", "who"]
FLAGS = ["g", "t", "b", "s", "p", "h"]       # bit 0 = goal, 1 = on target, …


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def league_key(league: str) -> str:
    return slug(league)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    args = ap.parse_args()
    seasons = seasons_on_disk(args.league)
    print(f"seasons: {', '.join(seasons)}")

    spells = build_spells(args.league, seasons)
    spell_of = {}
    for sp in spells:
        for g in sp.games:
            spell_of[(sp.team, g)] = sp.key
    # per club, the spells in order, so a shot can carry an index not a key
    spell_ix = defaultdict(dict)
    for sp in spells:
        spell_ix[sp.team][sp.key] = len(spell_ix[sp.team])
    season_ix = {s: i for i, s in enumerate(seasons)}
    # names indexed per club, for the same reason the spell key is: a squad
    # of thirty names written out on two thousand shots is most of the file
    who_ix = defaultdict(dict)

    def row(shot: dict, season: str, key: str, team: str) -> list:
        flags = sum(1 << i for i, f in enumerate(FLAGS) if shot[f])
        who = shot.get("who") or ""
        if who and who not in who_ix[team]:
            who_ix[team][who] = len(who_ix[team])
        return [round(shot["x"]), round(shot["y"]), flags,
                season_ix[season], spell_ix[team].get(key, -1),
                who_ix[team].get(who, -1)]

    # shots kept flat and tagged; positions and passes accumulated per cut
    shots = defaultdict(list)
    faced = defaultdict(list)
    accs = defaultdict(new_acc)
    counts = defaultdict(int)

    for season in seasons:
        df = pd.read_parquet(RAW / args.league / f"{season}_stamped.parquet")
        for gid, m in df.groupby("game_id", sort=False):
            per = match_plots(m)
            for team, part in per.items():
                sp = spell_of.get((team, int(gid)), "")
                for s in part["shots"]:
                    shots[team].append(row(s, season, sp, team))
                for s in part["faced"]:
                    faced[team].append(row(s, season, sp, team))
                for cut in (f"{team}|all", f"{team}|{season}",
                            *( [f"{team}|{sp}"] if sp else [] )):
                    merge(accs[cut], part)
                    counts[cut] += 1
        print(f"  {season}", flush=True)

    lk = league_key(args.league)
    by_club = defaultdict(dict)
    for cut, acc in accs.items():
        team = cut.split("|")[0]
        if counts[cut] < MIN_MATCHES:
            continue
        p = pack(acc, counts[cut])
        by_club[team][cut.split("|", 1)[1]] = {
            "matches": p["matches"],
            "positions": p["positions"],
            "passes": p["passes"],
            "passes_checked": p["passes_checked"],
            "passes_resolved": p["passes_resolved"],
        }

    for root in (OUT, PUB):
        folder = root / lk / "plots"
        folder.mkdir(parents=True, exist_ok=True)
        for team, cuts in by_club.items():
            payload = {
                "team": team,
                "seasons": seasons,
                "shot_keys": SHOT_KEYS,
                "shot_flags": FLAGS,
                "shooters": [n for n, _i in sorted(
                    who_ix[team].items(), key=lambda kv: kv[1])],
                "spells": [
                    {"key": sp.key, "manager": sp.manager,
                     "start": sp.start[:10], "matches": sp.matches}
                    for sp in spells if sp.team == team
                ],
                "shots": shots.get(team, []),
                "faced": faced.get(team, []),
                "cuts": cuts,
            }
            (folder / f"{slug(team)}.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    sizes = sorted(
        ((f.stat().st_size // 1024, f.name)
         for f in (OUT / lk / "plots").glob("*.json")), reverse=True)
    total = sum(s for s, _n in sizes)
    print()
    print(f"-> {OUT / lk / 'plots'}   {len(sizes)} clubs, {total} KB total")
    for kb, name in sizes[:3]:
        print(f"   {name:<28}{kb:>5} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
