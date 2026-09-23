"""What has CHANGED that the team's history does not know yet.

A side's recent xG already contains its players, its manager's selection and
its style — which is why every extra input bolted alongside it adds nothing.
The history is not wrong. It is just OUT OF DATE whenever the team that
produced it is not the team about to play.

So this builds corrections, and every one of them is ZERO when nothing has
changed. On an ordinary fixture the layered model is the shipped model,
exactly. It can only differ where the squad or the manager has moved.

TWO CORRECTIONS, both walk-forward, both observable:

  MISSING     regulars who are not in today's twenty. Derived from the
              matchday squad itself — WhoScored lists the eleven and the
              nine subs, so a man who has been playing and is not among the
              twenty was unavailable. That works for EVERY match on disk,
              which the injury scrape cannot do: previews are only collected
              for fixtures still ahead.

  NEW MANAGER how much of the rating window predates the current tenure. A
              side three games into a new manager is being rated almost
              entirely on his predecessor's football. Expressed as the SHARE
              of the window that is stale, which is 0 for a settled manager
              and approaches 1 the day after an appointment.

Both are in units the model can use directly: `missing` is the rating value
of the absentees, scaled so a full-strength side is 0.

Writes data/reports/change_layers.json — one row per team-match.

Usage: .venv/Scripts/python.exe scripts/build_change_layers.py
"""
import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from services.mental.positions import load_match
from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.spells import build as build_spells

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "reports" / "change_layers.json"
MENTAL = ROOT / "data" / "web" / "mental"

# How far back "recently playing" looks. Six matches is about six weeks —
# long enough that a rotation player is not called a regular, short enough
# that a man who lost his place in September is not still counted in March.
WINDOW = 6
# A player has to have been getting this share of the window's minutes to
# count as a regular whose absence means anything.
REGULAR = 0.45
# The rating window the shipped FormModel uses, for judging how much of it
# predates a new manager. Keep in sync with services/predictions/form_model.py
FORM_WINDOW = 38


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def player_ratings(lk: str) -> dict:
    """(season, name) -> percentile in his position, from the PREVIOUS
    season wherever possible.

    Rating a missing player on the season he is missing FROM is circular:
    he has few minutes precisely because he is injured, so he scores badly
    and his absence looks cheap. His last full season is what a side has
    actually lost."""
    from build_manager_edge import PLAYER_W

    meta = json.loads((MENTAL / lk / "meta.json").read_text(encoding="utf-8"))
    ix = {k: i for i, k in enumerate(meta["metric_keys"])}
    rel = meta.get("reliability", {})
    per = {}
    for path in sorted((MENTAL / lk).glob("2*.json")):
        season = path.stem
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
        by_b = defaultdict(list)
        for j, b in enumerate(v["p"]):
            by_b[b].append(j)
        pct = [50.0] * len(raw)
        for b, idxs in by_b.items():
            order = sorted(idxs, key=lambda j: raw[j])
            n = len(order)
            for rank, j in enumerate(order):
                pct[j] = rank / (n - 1) * 100 if n > 1 else 50.0
        best = {}
        for j, nm in enumerate(v["n"]):
            if nm not in best or v["m"][j] > best[nm][1]:
                best[nm] = (pct[j], v["m"][j])
        per[season] = {nm: p for nm, (p, _m) in best.items()}
    return per


def squad_of(doc: dict, side: str) -> set:
    """The twenty named for this match — eleven plus the bench."""
    return {p.get("name") for p in (doc.get(side) or {}).get("players", [])
            if p.get("name")}


def minutes_of(doc: dict, side: str) -> dict:
    """Who actually played, and roughly how long."""
    out = {}
    for p in (doc.get(side) or {}).get("players", []):
        nm = p.get("name")
        if not nm:
            continue
        started = bool(p.get("isFirstEleven"))
        on = p.get("subbedInExpandedMinute")
        off = p.get("subbedOutExpandedMinute")
        if not started and on is None:
            continue                      # unused substitute
        start = 0 if started else int(on)
        end = int(off) if off is not None else 95
        out[nm] = max(0, end - start)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    args = ap.parse_args()
    lk = slug(args.league)
    seasons = seasons_on_disk(args.league)
    ratings = player_ratings(lk)
    order = sorted(ratings)
    prev_of = {s: (order[i - 1] if i else s) for i, s in enumerate(order)}

    spells = build_spells(args.league, seasons)
    spell_of, depth = {}, {}

    # every match, in kickoff order
    rows = []
    for season in seasons:
        df = pd.read_parquet(RAW / args.league / f"{season}_stamped.parquet",
                             columns=["game_id"])
        for gid in df["game_id"].unique():
            doc = load_match(args.league, season, gid)
            if doc is None:
                continue
            kick = doc.get("startTime") or doc.get("startDate") or ""
            h = (doc.get("home") or {}).get("name")
            a = (doc.get("away") or {}).get("name")
            if not kick or not h or not a:
                continue
            rows.append({"season": season, "game_id": int(gid), "kick": kick,
                         "home": h, "away": a, "doc": doc})
    rows.sort(key=lambda r: r["kick"])
    print(f"{len(rows)} matches")

    for sp in spells:
        games = sorted(sp.games,
                       key=lambda g: next((r["kick"] for r in rows
                                           if r["game_id"] == g), ""))
        for i, g in enumerate(games):
            spell_of[(sp.team, g)] = sp.key
            depth[(sp.team, g)] = i

    recent: dict = defaultdict(lambda: deque(maxlen=WINDOW))
    out = []
    for r in rows:
        rate = ratings.get(prev_of.get(r["season"], r["season"]), {})
        rec = {}
        for side, team in (("home", r["home"]), ("away", r["away"])):
            hist = recent[team]
            # who has been a regular over the window
            played = defaultdict(int)
            for m in hist:
                for nm, mins in m.items():
                    played[nm] += mins
            avail = 95 * len(hist) if hist else 0
            regulars = {nm: mins for nm, mins in played.items()
                        if avail and mins / avail >= REGULAR}
            squad = squad_of(r["doc"], side)
            # MISSING: a regular who is not among today's twenty. Valued at
            # his rating above replacement, weighted by how much he had been
            # playing, and divided by eleven so a whole side of absentees
            # would be a full unit.
            gone = 0.0
            names = []
            for nm, mins in regulars.items():
                if nm in squad:
                    continue
                v = rate.get(nm)
                if v is None:
                    continue
                share = mins / avail if avail else 0
                gone += max(0.0, v - 50) / 50 * share / 11
                names.append(nm)
            d = depth.get((team, r["game_id"]))
            # NEW MANAGER: the share of the rating window that predates the
            # current tenure. Zero once he has been there a full window.
            stale = 1.0 if d is None else max(0.0, 1 - d / FORM_WINDOW)
            rec[side] = {"missing": round(gone, 5), "n_missing": len(names),
                         "who": names[:5], "stale": round(stale, 4),
                         "depth": d}
        out.append({
            "season": r["season"], "game_id": r["game_id"],
            "date": r["kick"][:10], "home": r["home"], "away": r["away"],
            "h": rec["home"], "a": rec["away"],
        })
        # only NOW does this match join the history
        for side, team in (("home", r["home"]), ("away", r["away"])):
            recent[team].append(minutes_of(r["doc"], side))

    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    miss = [o for o in out if o["h"]["n_missing"] or o["a"]["n_missing"]]
    fresh = [o for o in out
             if (o["h"]["depth"] or 99) < 10 or (o["a"]["depth"] or 99) < 10]
    print(f"-> {OUT}")
    print(f"   {len(miss)} of {len(out)} fixtures have a missing regular "
          f"({100 * len(miss) / len(out):.0f}%)")
    print(f"   {len(fresh)} have a side under 10 matches into a tenure "
          f"({100 * len(fresh) / len(out):.0f}%)")
    big = sorted(out, key=lambda o: -(o["h"]["missing"] + o["a"]["missing"]))[:5]
    print("   biggest absences:")
    for o in big:
        side = o["h"] if o["h"]["missing"] >= o["a"]["missing"] else o["a"]
        who = ", ".join(side["who"][:3])
        print(f"     {o['date']}  {o['home']} v {o['away']}  "
              f"{side['missing']:.3f}  {who}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
