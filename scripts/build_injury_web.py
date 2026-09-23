"""Who is out, and what they are worth.

`scrape_injuries.py` collects the absentees WhoScored names on each upcoming
match preview. That is a list of names; this turns it into a quantity, by
joining each name to the rating the player layer already gives him.

RATED OFF THE LAST COMPLETE SEASON, not this one. A player who has been
injured since August has almost no minutes this season, so the current
payload either does not carry him or carries a percentile built on ninety
minutes — and the whole point is to value the man who is missing. His last
full season is the best estimate of what a side has lost.

About 40% of named absentees cannot be rated at all, and that is a limit
rather than a bug: they are summer signings and fringe players with no
Premier League history, so there is no basis on which to value them. They
are carried in the list, marked unrated, and contribute nothing to the total
— which understates a loss rather than inventing one.

Writes data/web/team/{league}/injuries.json

    {"<team>": {"fixture": "...", "date": "...",
                "out": [{player, reason, status, bucket, rating, minutes}]}}

Usage: .venv/Scripts/python.exe scripts/build_injury_web.py
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
INJ = ROOT / "data" / "injuries"
MENTAL = ROOT / "data" / "web" / "mental"
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"

SEASON = "2627"
# Weights mirror PLAYER_W in build_manager_edge.py, which mirrors PRESETS in
# MentalData.tsx. Used only to value an absence; the site itself re-rates
# everything on whatever the reader has set.
from build_manager_edge import PLAYER_W                     # noqa: E402


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def _tokens(name: str) -> list:
    drop = ("fc", "afc", "cf")
    # "utd" is not a prefix of "united" and "united" is not a prefix of
    # "utd", so the prefix rule alone cannot join WhoScored's "Manchester
    # United" to the event feed's "Man Utd" — the one club it failed on.
    # Everything else the abbreviation rule covers ("man"/"manchester") is
    # already a prefix and needs nothing.
    same = {"utd": "united"}
    return [same.get(w, w)
            for w in "".join(c if c.isalnum() else " " for c in name.lower()).split()
            if w not in drop]


def align(src: set, dst: set) -> dict:
    """Preview names -> team-layer names. WhoScored's preview pages say
    "Manchester United" where the event feed says "Man Utd", so a club's
    absentees would land under a key nothing on the site ever looks up. Same
    token rule as the crest matcher: every word of the shorter name must
    prefix a word of the longer, and an ambiguous match is dropped rather
    than guessed — "Man Utd" reaches "Manchester Utd" but cannot reach
    "Manchester City", because utd prefixes nothing there."""
    def fits(short, long):
        used = set()
        for w in short:
            hit = next((i for i, v in enumerate(long)
                        if i not in used and (v.startswith(w) or w.startswith(v))),
                       None)
            if hit is None:
                return False
            used.add(hit)
        return True

    out = {}
    for a in src:
        if a in dst:
            out[a] = a
            continue
        ta = _tokens(a)
        hits = [b for b in dst if fits(ta, _tokens(b)) or fits(_tokens(b), ta)]
        if len(hits) == 1:
            out[a] = hits[0]
    return out


def ratings(lk: str, season: str) -> dict:
    """player name -> (bucket, percentile in his position, minutes)."""
    meta = json.loads((MENTAL / lk / "meta.json").read_text(encoding="utf-8"))
    keys = meta["metric_keys"]
    ix = {k: i for i, k in enumerate(keys)}
    rel = meta.get("reliability", {})
    path = MENTAL / lk / f"{season}.json"
    if not path.exists():
        return {}
    v = json.loads(path.read_text(encoding="utf-8"))

    raw = []
    for j, bucket in enumerate(v["p"]):
        w = PLAYER_W.get(bucket, {})
        qa = v["qa"][j]
        s = used = 0.0
        for k, weight in w.items():
            if k not in ix:
                continue
            r = (rel.get(k) or {}).get(bucket)
            if r is not None and r.get("rho", 1) < 0.4:
                continue
            val = qa[ix[k]]
            s += (50.0 if val is None else float(val)) * weight
            used += weight
        raw.append(s / used if used else 50.0)

    # percentile inside each position, as the site does
    by_b: dict = {}
    for j, b in enumerate(v["p"]):
        by_b.setdefault(b, []).append(j)
    pct = [50.0] * len(raw)
    for b, idxs in by_b.items():
        order = sorted(idxs, key=lambda j: raw[j])
        n = len(order)
        for rank, j in enumerate(order):
            pct[j] = rank / (n - 1) * 100 if n > 1 else 50.0

    out = {}
    for j, name in enumerate(v["n"]):
        # a player ranked in two positions is kept at the one he played most
        if name not in out or v["m"][j] > out[name][2]:
            out[name] = (v["p"][j], round(pct[j], 1), int(v["m"][j]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--season", default=SEASON)
    ap.add_argument("--rate-season", default=None,
                    help="which season's ratings to value absences with; "
                         "defaults to the last COMPLETE one")
    args = ap.parse_args()
    lk = slug(args.league)

    path = INJ / args.league.replace("/", "-") / f"{args.season}.json"
    if not path.exists():
        print(f"no injury file at {path} — run scrape_injuries.py first")
        return 1
    fixtures = json.loads(path.read_text(encoding="utf-8"))

    rate_season = args.rate_season
    if rate_season is None:
        have = sorted(p.stem for p in (MENTAL / lk).glob("2*.json"))
        done = [s for s in have if s != args.season]
        rate_season = done[-1] if done else args.season
    rated = ratings(lk, rate_season)
    print(f"valuing absences on {rate_season} ratings ({len(rated)} players)")

    # newest fixture per team wins: the latest preview is the current news
    per: dict = {}
    for gid, f in fixtures.items():
        for team in (f.get("home"), f.get("away")):
            if not team:
                continue
            got = per.get(team)
            if got and got["date"] >= f["date"]:
                continue
            per[team] = {
                "fixture": f"{f.get('home')} v {f.get('away')}",
                "date": f["date"],
                "out": [],
            }
    for gid, f in fixtures.items():
        for m in f.get("missing", []):
            team = m.get("team")
            if team not in per or per[team]["date"] != f["date"]:
                continue
            got = rated.get(m.get("player") or "")
            per[team]["out"].append({
                "player": m.get("player"),
                "reason": m.get("reason"),
                "status": m.get("status"),
                "bucket": got[0] if got else None,
                "rating": got[1] if got else None,
                "minutes": got[2] if got else None,
            })

    # rename onto the team layer's spelling before anything ships
    club = json.loads(
        (OUT / lk / "club_season.json").read_text(encoding="utf-8"))
    known = {r["team"] for r in club}
    names = align(set(per), known)
    missed = sorted(set(per) - set(names))
    if missed:
        print(f"  unmatched club names, dropped: {', '.join(missed)}")
    per = {names[k]: v for k, v in per.items() if k in names}
    for d in per.values():
        for x in d["out"]:
            if x.get("team") in names:
                x["team"] = names[x["team"]]

    for team, d in per.items():
        d["out"].sort(key=lambda x: -(x["rating"] or -1))
        d["n_out"] = sum(1 for x in d["out"] if x["status"] == "Out")
        d["n_doubt"] = sum(1 for x in d["out"] if x["status"] != "Out")
        d["rated"] = sum(1 for x in d["out"] if x["rating"] is not None)

    for root in (OUT, PUB):
        (root / lk).mkdir(parents=True, exist_ok=True)
        (root / lk / "injuries.json").write_text(
            json.dumps({"rated_on": rate_season, "teams": per},
                       ensure_ascii=False), encoding="utf-8")

    tot = sum(len(d["out"]) for d in per.values())
    hit = sum(d["rated"] for d in per.values())
    print(f"-> injuries.json  {len(per)} clubs, {tot} absentees, "
          f"{hit} of them rated ({100 * hit / max(tot, 1):.0f}%)")
    worst = sorted(per.items(),
                   key=lambda kv: -sum(x["rating"] or 0 for x in kv[1]["out"]))[:4]
    for team, d in worst:
        named = ", ".join(f"{x['player']} {x['rating']:.0f}"
                          for x in d["out"][:3] if x["rating"] is not None)
        print(f"   {team:<20}{d['n_out']} out, {d['n_doubt']} doubtful   {named}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
