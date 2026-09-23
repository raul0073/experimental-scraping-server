"""Recent form — the last handful of results, per club.

The team layer is all rates and percentiles, and none of it answers the first
thing anyone asks about a side: how are they going? That is five letters, and
it is not derivable from anything already shipped — the per-match results are
in the event cache and nowhere in the web payload.

Ordered by KICKOFF, never by game id. Ids rise across seasons but not within
one: 23/24's span a range of 74,000 against 24/25's 379, so a season sorted
by id is in an arbitrary order and "the last five" would be five matches
chosen at random.

Writes web/public/data/team/{league}/form.json

Usage: .venv/Scripts/python.exe scripts/build_team_form.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.mental.positions import CACHE

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"
KEEP = 10          # the page shows five; ten leaves room to change its mind


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    args = ap.parse_args()
    lk = slug(args.league)

    per = defaultdict(lambda: defaultdict(list))
    seasons = sorted(p.name.split("_")[-1] for p in CACHE.glob(f"{args.league}_*")
                     if p.is_dir())
    for season in seasons:
        folder = CACHE / f"{args.league}_{season}"
        for path in sorted(folder.glob("*.json")):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            h, a = d.get("home") or {}, d.get("away") or {}
            hn, an = h.get("name"), a.get("name")
            hg = (h.get("scores") or {}).get("fulltime")
            ag = (a.get("scores") or {}).get("fulltime")
            kick = d.get("startTime") or d.get("startDate") or ""
            if not hn or not an or hg is None or ag is None or not kick:
                continue
            for team, opp, gf, ga, home in ((hn, an, hg, ag, True),
                                            (an, hn, ag, hg, False)):
                per[team][season].append({
                    "d": kick[:10],
                    "o": opp,
                    "h": 1 if home else 0,
                    "gf": int(gf),
                    "ga": int(ga),
                    "r": "W" if gf > ga else ("L" if gf < ga else "D"),
                })
        print(f"  {season}", flush=True)

    out = {}
    for team, by_season in per.items():
        rows = {}
        for season, games in by_season.items():
            games.sort(key=lambda g: g["d"])
            rows[season] = games[-KEEP:]
        # "all seasons" is the tail of the most recent one, which is what
        # anybody means by form regardless of the period they are looking at
        latest = max(rows)
        rows["all"] = rows[latest]
        out[team] = rows

    for root in (OUT, PUB):
        (root / lk).mkdir(parents=True, exist_ok=True)
        (root / lk / "form.json").write_text(
            json.dumps(out, ensure_ascii=False), encoding="utf-8")
    kb = (OUT / lk / "form.json").stat().st_size // 1024
    print()
    print(f"-> form.json  {len(out)} clubs, {kb} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
