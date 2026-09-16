"""Export web-ready JSON artifacts for the Next.js client.

The public site is STATIC: the model runs here, writes JSON, and the client
reads it at build time. Nothing about the website needs a running Python
server — the data changes weekly, not per request.

Writes into data/web/:
    round.json   — the next round per league: probabilities, the model's
                   call, predicted score, and the FAIR PRICE of each outcome
                   (we publish what an outcome is worth, never what to bet)
    record.json  — the calibration record: what was said vs what landed

Usage: .venv/Scripts/python.exe scripts/export_web.py
"""
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web"
SIM = ROOT / "data" / "reports" / "season_sim_2627.json"
HIST = ROOT / "data" / "history" / "predictions.jsonl"
LOGOS_SRC = ROOT / "static" / "logos"
LOGOS_DST = ROOT / "web" / "public" / "logos"


def sync_logos() -> int:
    """Mirror crests into the client's public folder. They live in one place
    (static/logos, shared with the desktop app) and are copied rather than
    committed twice — web/public/logos is gitignored."""
    import shutil
    if not LOGOS_SRC.exists():
        return 0
    n = 0
    for src in LOGOS_SRC.rglob("*.png"):
        dst = LOGOS_DST / src.relative_to(LOGOS_SRC)
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def crest_index() -> dict:
    """team -> public URL, plus each league's own crest."""
    path = LOGOS_SRC / "manifest.json"
    teams: dict = {}
    if path.exists():
        for league, mapping in json.loads(path.read_text(encoding="utf-8")).items():
            for team, p in mapping.items():
                teams.setdefault(league, {})[team] = p.replace("/static/logos", "/logos")
    leagues = {}
    for p in (LOGOS_SRC / "leagues").glob("*.png"):
        leagues[p.stem] = f"/logos/leagues/{p.name}"
    return {"teams": teams, "leagues": leagues}


def fair(p: float) -> float:
    """What the outcome is worth. Above this price it is value; below it,
    it is not. We never see the reader's book — this is the whole service."""
    return round(1.0 / p, 2) if p > 0 else 0.0


def export_round() -> dict:
    sim = json.loads(SIM.read_text(encoding="utf-8"))
    crests = crest_index()
    out = {"generated": date.today().isoformat(), "season": sim.get("season"),
           "as_of": sim.get("as_of"), "crests": crests, "leagues": {}}
    for league, blob in sim.get("leagues", {}).items():
        fixtures = blob.get("fixtures") or []
        if not fixtures:
            continue
        week = min(f["week"] for f in fixtures)
        rnd = [f for f in fixtures if f["week"] == week]
        rnd.sort(key=lambda f: (f["date"] or "", f["home"]))
        out["leagues"][league] = {
            "week": week,
            "start": min((f["date"] or "" for f in rnd), default=""),
            "end": max((f["date"] or "" for f in rnd), default=""),
            "fixtures": [{
                "date": f["date"], "home": f["home"], "away": f["away"],
                "p": {"home": f["p_home"], "draw": f["p_draw"], "away": f["p_away"]},
                "fair": {"home": fair(f["p_home"] / 100), "draw": fair(f["p_draw"] / 100),
                         "away": fair(f["p_away"] / 100)},
                "call": f["call"], "score": f["score"],
                "xg": [f["xg_h"], f["xg_a"]],
            } for f in rnd],
            "projection": [
                {"team": r["team"], "played_pts": r["pts_now"], "exp_pts": r["exp_pts"],
                 "title": r["p_title"], "top4": r["p_top4"], "rel": r["p_rel"]}
                for r in blob.get("table", [])],
        }
    return out


def export_record() -> dict:
    """Calibration: the only claim worth publishing. Buckets say whether the
    stated probabilities are honest; raw hit rate alone is not evidence."""
    rows = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    graded = [r for r in rows if r.get("status") == "graded"]
    by_league = defaultdict(lambda: {"n": 0, "hit": 0})
    buckets = defaultdict(lambda: {"n": 0, "hit": 0, "said": 0.0})
    for r in graded:
        call = r["pred_outcome"]
        p = r["probabilities"][call]
        hit = bool(r.get("outcome_hit"))
        b = by_league[r["league"]]
        b["n"] += 1
        b["hit"] += hit
        key = f"{int(p * 10) * 10}-{int(p * 10) * 10 + 10}%"
        buckets[key]["n"] += 1
        buckets[key]["hit"] += hit
        buckets[key]["said"] += p
    n = len(graded)
    return {
        "generated": date.today().isoformat(),
        "graded": n,
        "hit_rate": round(sum(1 for r in graded if r.get("outcome_hit")) / n * 100, 1) if n else None,
        "said_avg": round(sum(r["probabilities"][r["pred_outcome"]] for r in graded) / n * 100, 1) if n else None,
        "exact_score": round(sum(1 for r in graded if r.get("score_hit")) / n * 100, 1) if n else None,
        "by_league": {lg: {"n": v["n"], "hit_rate": round(v["hit"] / v["n"] * 100, 1)}
                      for lg, v in sorted(by_league.items())},
        "calibration": [
            {"bucket": k, "n": v["n"],
             "said": round(v["said"] / v["n"] * 100, 1),
             "landed": round(v["hit"] / v["n"] * 100, 1)}
            for k, v in sorted(buckets.items()) if v["n"] >= 5],
    }


def slugify(league: str) -> str:
    return league.lower().replace(" ", "-").replace("_", "-")


def export_history() -> dict:
    """Every recorded prediction, per competition — the drill-down behind the
    track record. Pending rows are included so the page shows what is live,
    not only what is settled."""
    rows = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    crests = crest_index()
    leagues: dict = {}
    for r in rows:
        lg = r["league"]
        entry = leagues.setdefault(slugify(lg), {
            "name": lg, "crest": crests["leagues"].get(lg), "rows": [],
        })
        pr = r["probabilities"]
        entry["rows"].append({
            "kickoff": r["kickoff"], "home": r["home"], "away": r["away"],
            "p": {"home": round(pr["home"] * 100, 1), "draw": round(pr["draw"] * 100, 1),
                  "away": round(pr["away"] * 100, 1)},
            "call": r["pred_outcome"], "our_score": r["pred_score"],
            "our_xg": r.get("pred_xg"),
            "status": r["status"], "score": r.get("score"),
            "real_xg": r.get("real_xg"),
            "outcome_hit": r.get("outcome_hit"), "score_hit": r.get("score_hit"),
        })
    for e in leagues.values():
        e["rows"].sort(key=lambda x: (x["kickoff"], x["home"]), reverse=True)
        graded = [x for x in e["rows"] if x["status"] == "graded"]
        e["graded"] = len(graded)
        e["hits"] = sum(1 for x in graded if x["outcome_hit"])
        e["exact"] = sum(1 for x in graded if x["score_hit"])
        e["teams"] = crests["teams"].get(e["name"], {})
    return {"generated": date.today().isoformat(), "leagues": leagues}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"OK   logos synced ({sync_logos()} new/updated)")
    for name, builder in (("round", export_round), ("record", export_record),
                         ("history", export_history)):
        try:
            data = builder()
        except Exception as e:  # one bad artifact must not block the others
            print(f"WARN {name}: {e}")
            continue
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"OK   {name}.json ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
