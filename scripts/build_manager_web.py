"""Build the manager layer: one ranked table of spells per league.

A spell is a club under one man. It is the only unit that survives contact
with the data — a club is not one team for four seasons, and a season is not
one manager — and services/mental/spells.py stitches it out of WhoScored's
per-match `managerName`. This builder asks services/managers/metrics.py for
each spell's metric values, hands them to services/managers/ranking.py to be
percentiled within the league and shrunk on matches, and writes the payload
the page reads.

What is shipped is derived numbers only: no event ever leaves data/ for
web/. Percentiles are computed WITHIN one league and never across five,
because the feed is the same in all of them and the football is not.

Writes data/web/managers/{league-slug}.json and the copy the site serves,
merging that league's entry into the index.json of BOTH roots.

Usage:
    .venv/Scripts/python.exe scripts/build_manager_web.py
    .venv/Scripts/python.exe scripts/build_manager_web.py --league "ENG-Premier League"
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.managers import ranking                          # noqa: E402
from services.mental.role_bank import seasons_on_disk          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# 🐛 THIS USED TO WRITE ONLY INTO web/public, WHICH IS GITIGNORED.
# web/.gitignore ignores /public/data, so the whole manager layer lived in
# one untracked folder on one machine: a clean checkout had the page, the
# contract and no data behind either, and the board came up empty with
# nothing in the repo to say it had ever been built. Every other builder here
# dual-writes — data/web is committed, web/public/data is the regenerable
# copy the dev server and the static export read — so this one does too.
OUT = ROOT / "data" / "web" / "managers"
PUB = ROOT / "web" / "public" / "data" / "managers"

# The board opens on leagues[0], so this order decides the default league.
# England first, the same order every other index in this repo uses.
LEAGUE_ORDER = ["eng-premier-league", "esp-la-liga", "ita-serie-a",
                "ger-bundesliga", "fra-ligue-1"]


def league_key(league: str) -> str:
    """'ENG-Premier League' -> 'eng-premier-league'."""
    return "".join(c if c.isalnum() else "-" for c in league.lower()).strip("-")


def merge_index(root: Path, mine: list) -> list:
    """This league's entry folded into whatever the index already lists.

    Each run builds ONE league but the index describes all of them, so the
    file has to be READ BEFORE IT IS WRITTEN or the other four vanish. Three
    builders in this repo have already shipped that exact bug — the ratings
    index, elo_params.json and the mental index — and each time the symptom
    was the same: the page reads leagues[0], so building La Liga last made
    every board open on La Liga. Merge, and keep a deterministic order."""
    seen: dict = {}
    try:
        for e in json.loads((root / "index.json").read_text(encoding="utf-8"))["leagues"]:
            seen[e["key"]] = e
    except Exception:
        pass                      # no index yet, or unreadable — start fresh
    for e in mine:
        seen[e["key"]] = e        # this run's entry is the authoritative one
    return sorted(seen.values(),
                  key=lambda e: (LEAGUE_ORDER.index(e["key"])
                                 if e["key"] in LEAGUE_ORDER else 99,
                                 e["key"]))


def coverage(payload: dict) -> list:
    """Metrics that came back null for every single spell.

    A metric that cannot be computed from what is on disk is published as
    null and SAID SO here, rather than quietly replaced by something that
    looked close enough."""
    rows = payload["managers"]
    out = []
    for m in payload["metrics"]:
        have = sum(1 for r in rows if r["raw"].get(m["key"]) is not None)
        out.append((m["key"], have, len(rows)))
    return out


def show(payload: dict, n: int = 5) -> None:
    """Top and bottom of the table, with the shrinkage on show.

    matches, score_raw, kept and score in the same row on purpose: the whole
    point of reporting all four is that a reader can see a four-match
    caretaker's 78 being pulled back to 59 and know why."""
    rows = [r for r in payload["managers"] if r["score"] is not None]
    print(f"\n   {len(rows)} scored spells of {len(payload['managers'])}"
          f"   ({payload['league']})")
    head = f"   {'':>3} {'manager':<22}{'team':<18}{'mch':>4}{'raw':>7}" \
           f"{'kept':>7}{'score':>7}"
    print(f"\n{head}\n   {'-' * (len(head) - 3)}")

    def line(i, r):
        print(f"   {i:>3} {r['manager'][:21]:<22}{r['team'][:17]:<18}"
              f"{r['matches']:>4}{r['score_raw']:>7.1f}"
              f"{r['kept'] * 100:>6.0f}%{r['score']:>7.1f}")

    if len(rows) <= 2 * n:
        for i, r in enumerate(rows, 1):
            line(i, r)
    else:
        for i, r in enumerate(rows[:n], 1):
            line(i, r)
        print(f"   {'...':>3}")
        for i, r in enumerate(rows[-n:], len(rows) - n + 1):
            line(i, r)

    missing = [(k, h, t) for k, h, t in coverage(payload) if h == 0]
    if missing:
        print("\n   NOT COMPUTABLE — published as null, not substituted:")
        for k, _h, _t in missing:
            print(f"     ! {k}")
    thin = [(k, h, t) for k, h, t in coverage(payload) if 0 < h < t]
    if thin:
        print("\n   partial coverage (the rest score a neutral 50):")
        for k, h, t in thin:
            print(f"       {k:<24}{h:>4}/{t} spells")


def main() -> int:
    # Manager names are not ASCII — Hürzeler, Guardiola's opposite number in
    # half of Europe — and a Windows console on a non-UTF-8 code page kills
    # the whole run at the print, after all the work is done. The launchers
    # in scripts/ already set PYTHONIOENCODING=utf-8; this covers a direct
    # invocation that did not.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError, ValueError):
        pass

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", action="append", default=None,
                    help="repeatable; default is all five")
    ap.add_argument("--season", action="append", default=None,
                    help="repeatable, e.g. 2526; default is every season "
                         "on disk for that league")
    ap.add_argument("--top", type=int, default=5,
                    help="how many rows to print from each end")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print, write nothing")
    args = ap.parse_args()

    leagues = args.league or ranking.LEAGUES
    components = ranking.load_config()
    scored = ranking.scored_components(components)
    w_sum = sum(c["weight"] for c in scored) or 1
    print(f"score = {len(scored)} directional metrics: " + ", ".join(
        f"{c['key']} {c['weight'] / w_sum * 100:.0f}%" for c in scored))

    for league in leagues:
        seasons = args.season or seasons_on_disk(league)
        if not seasons:
            print(f"!! {league}: no stamped events on disk, skipped")
            continue
        lk = league_key(league)
        print(f"\n== {league}  ({', '.join(seasons)})")
        payload = ranking.build_payload(league, seasons, components=components)
        if not payload["managers"]:
            print("!! no spells found, skipped")
            continue
        show(payload, args.top)
        if args.dry_run:
            continue
        blob = json.dumps(payload, ensure_ascii=False)
        for root in (OUT, PUB):
            root.mkdir(parents=True, exist_ok=True)
            # 🐛 NEVER write this file whole. Read, replace one entry, write
            # back — see merge_index. Merged SEPARATELY PER ROOT, because the
            # two indexes are two files that can legitimately disagree: the
            # tracked one starts empty on a clean checkout while the served
            # one may already list four leagues from an earlier run. Merging
            # once and writing the same result to both would push whichever
            # root was thinner over the other and delete leagues again.
            (root / "index.json").write_text(
                json.dumps({"leagues": merge_index(
                    root, [{"key": lk, "label": league}])},
                    ensure_ascii=False),
                encoding="utf-8")
            (root / f"{lk}.json").write_text(blob, encoding="utf-8")
        out = OUT / f"{lk}.json"
        print(f"\n-> {out}  ({out.stat().st_size // 1024} KB)")
        print(f"   {PUB / (lk + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
