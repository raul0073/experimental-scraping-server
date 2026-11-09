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
import math
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


ZONES_CFG = ROOT / "data" / "config" / "league_zones.json"
FIXTURES = ROOT / "data" / "fixtures"
HISTORY = ROOT / "data" / "history" / "predictions.jsonl"


def graded_week(league: str, season: str, week: int) -> list:
    """This round's fixtures that have ALREADY been played, with what we said
    about them beforehand.

    🐛 THE ROUND USED TO EMPTY ITSELF AS THE WEEKEND WENT ON. The season sim
    holds only UNPLAYED fixtures, so on Sunday morning Saturday's matches had
    simply gone — the page showed four fixtures of a ten-fixture round and no
    trace of what had happened in the other six. A site whose whole claim is
    "what it expects, what happened, and what it learned" cannot drop the
    middle one the moment it becomes checkable.

    The prediction was recorded when it was made, so it is read back out of
    the history log rather than re-derived — which also means the page shows
    what we ACTUALLY said at the time, not what the model would say now with
    the result in hand.
    """
    if not HISTORY.exists():
        return []
    out = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get("league") != league or str(r.get("season")) != season
                or r.get("week") != week or r.get("status") != "graded"):
            continue
        p = r.get("probabilities") or {}
        if not p:
            continue
        out.append({
            "date": (r.get("kickoff") or "")[:10],
            "home": r.get("home"), "away": r.get("away"),
            "p": {k: round(100 * float(p.get(k, 0)), 1) for k in ("home", "draw", "away")},
            "fair": {k: fair(float(p.get(k, 0))) for k in ("home", "draw", "away")},
            "call": r.get("pred_outcome"),
            "score": r.get("pred_score") or "",
            "xg": [round(float(x), 2) for x in (r.get("pred_xg") or [0, 0])],
            "played": r.get("score"),
            "outcome": r.get("outcome"),
        })
    return out


def results_for(league: str, season: str) -> dict:
    """What actually happened, keyed by (date, home, away).

    🐛 THE ROUND USED TO SHIP ONLY THE PREDICTED SCORELINE, in a column the
    page headed "Score". On a Sunday, looking at Saturday's fixtures, that
    reads as the result — so the site showed "1-1" for a match that finished
    3-0 and quietly hid its own miss. A model that publishes what it expects
    and never what happened is the exact thing this project says it is not.

    The results are already on disk in the fixtures file the weekly refresh
    writes; nothing needed scraping, only joining.
    """
    f = FIXTURES / league / f"{season}.json"
    if not f.exists():
        return {}
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(rows, dict):
        rows = rows.get("matches") or list(rows.values())
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        h, a = r.get("home_goals"), r.get("away_goals")
        if h is None or a is None:
            continue
        key = (str(r.get("date") or ""), str(r.get("home_team") or ""),
               str(r.get("away_team") or ""))
        out[key] = (int(h), int(a))
    return out


def zone_probs(p_pos: list, zones: list) -> dict:
    """Probability of finishing in each configured zone, from the simulated
    position distribution. Anything not covered by a zone is mid-table."""
    out = {}
    claimed = 0.0
    for z in zones:
        # p_pos is 0-indexed by position-1
        share = sum(p_pos[z["from"] - 1: z["to"]])
        out[z["key"]] = round(share, 1)
        claimed += share
    out["mid"] = round(max(0.0, 100.0 - claimed), 1)
    return out


def result_fields(res) -> dict:
    """The actual score and whether the call survived it. Absent entirely
    when a match has not been played, so the client can tell "0-0" from
    "not yet"."""
    if not res:
        return {}
    h, a = res
    return {"played": f"{h}-{a}",
            "outcome": "home" if h > a else "away" if a > h else "draw"}


def export_round() -> dict:
    sim = json.loads(SIM.read_text(encoding="utf-8"))
    crests = crest_index()
    cfg = json.loads(ZONES_CFG.read_text(encoding="utf-8")) if ZONES_CFG.exists() else {}
    zones_by_league = cfg.get("leagues", {})
    out = {"generated": date.today().isoformat(), "season": sim.get("season"),
           "as_of": sim.get("as_of"), "crests": crests, "leagues": {}}
    season = str(sim.get("season") or "")
    for league, blob in sim.get("leagues", {}).items():
        played = results_for(league, season)
        fixtures = blob.get("fixtures") or []
        if not fixtures:
            continue
        # 🐛 THE NEXT ROUND IS THE SOONEST ONE, NOT THE LOWEST-NUMBERED.
        #
        # This was min(week) over everything still unplayed, which breaks the
        # moment a single fixture is postponed out of its matchweek. La Liga
        # round 6 finished on 17 September except for Levante v Athletic
        # Club, moved to 21 October — so `min` kept returning 6 and the
        # predictor showed a round that was over, spanning "09-03 -> 10-21",
        # while round 8 on 9 October was the one anybody actually wanted.
        # Spanish reschedules make this routine, not exotic.
        #
        # Ordering by DATE picks the round that kicks off next and leaves the
        # straggler inside whichever round it belongs to. The fixture list
        # here is already only the unplayed ones, so the earliest date in it
        # is by definition the next match to be played.
        soonest = min(fixtures, key=lambda f: (f["date"] or "9999", f["week"]))
        week = soonest["week"]
        rnd = [f for f in fixtures if f["week"] == week]
        done = graded_week(league, season, week)
        out["leagues"][league] = {
            "week": week,
            "start": min((f["date"] or "" for f in rnd + done), default=""),
            "end": max((f["date"] or "" for f in rnd + done), default=""),
            "fixtures": sorted(
                [{
                    "date": f["date"], "home": f["home"], "away": f["away"],
                    "p": {"home": f["p_home"], "draw": f["p_draw"], "away": f["p_away"]},
                    "fair": {"home": fair(f["p_home"] / 100), "draw": fair(f["p_draw"] / 100),
                             "away": fair(f["p_away"] / 100)},
                    "call": f["call"], "score": f["score"],
                    "xg": [f["xg_h"], f["xg_a"]],
                    **result_fields(played.get((f["date"], f["home"], f["away"]))),
                } for f in rnd] + graded_week(league, season, week),
                key=lambda f: (f.get("date") or "", f.get("home") or ""),
            ),
            "zones": zones_by_league.get(league, {}).get("zones", []),
            "projection": [
                {"team": r["team"], "played_pts": r["pts_now"], "exp_pts": r["exp_pts"],
                 "title": r["p_title"], "med_pos": r.get("med_pos"),
                 "zone": zone_probs(r.get("p_pos") or [],
                                    zones_by_league.get(league, {}).get("zones", []))}
                for r in blob.get("table", [])],
        }
    out["zones_note"] = (cfg.get("_note") or "").split(" EDIT THIS")[0]
    return out


OUTCOMES = ("home", "draw", "away")


def _scores(rows: list, probs_of) -> dict | None:
    """Proper scoring rules for a set of graded rows. `probs_of(row)` returns
    the triplet to score, so the same function scores the model and any
    baseline.

    WHY THESE AND NOT HIT RATE. A hit rate rewards calling the favourite and
    says nothing about whether 46% meant 46%. Log loss and Brier punish a
    confident miss more than a hesitant one, which is the property a
    probability has to have to be worth publishing — and they are the only
    numbers on which a model can be compared with another forecaster."""
    n = len(rows)
    if not n:
        return None
    ll = br = 0.0
    for r in rows:
        p = probs_of(r)
        o = r["outcome"]
        ll += -math.log(max(min(p[o], 1 - 1e-9), 1e-9))
        br += sum((p[k] - (1.0 if k == o else 0.0)) ** 2 for k in OUTCOMES)
    return {"logloss": round(ll / n, 4), "brier": round(br / n, 4)}


def _calibration(rows: list, min_n: int = 5) -> list:
    """Buckets of the model's stated probability for the outcome it CALLED:
    what it said on average against how often the call landed."""
    buckets = defaultdict(lambda: {"n": 0, "hit": 0, "said": 0.0})
    for r in rows:
        p = r["probabilities"][r["pred_outcome"]]
        key = f"{int(p * 10) * 10}-{int(p * 10) * 10 + 10}%"
        buckets[key]["n"] += 1
        buckets[key]["hit"] += bool(r.get("outcome_hit"))
        buckets[key]["said"] += p
    return [
        {"bucket": k, "n": v["n"],
         "said": round(v["said"] / v["n"] * 100, 1),
         "landed": round(v["hit"] / v["n"] * 100, 1)}
        for k, v in sorted(buckets.items()) if v["n"] >= min_n]


def _levels(rows: list) -> list:
    """Per outcome, the mean stated probability against the share that
    happened, over EVERY row (not only the calls). The call buckets above
    cannot show a bias in one outcome's level — a draw priced four points
    too high across the board hides inside "said 45%, landed 50%" — and that
    is exactly the bias that would make every fair price wrong."""
    n = len(rows)
    out = []
    for k in OUTCOMES:
        said = sum(r["probabilities"][k] for r in rows) / n
        got = sum(1 for r in rows if r["outcome"] == k) / n
        se = math.sqrt(got * (1 - got) / n) if n else 0.0
        out.append({"outcome": k, "n": n,
                    "said": round(said * 100, 1), "landed": round(got * 100, 1),
                    "gap": round((said - got) * 100, 1),
                    "se": round(se * 100, 1)})
    return out


def _summary(rows: list) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "hit_rate": None, "said_avg": None, "exact_score": None,
                "scores": None}
    return {
        "n": n,
        "hit_rate": round(sum(1 for r in rows if r.get("outcome_hit")) / n * 100, 1),
        "said_avg": round(sum(r["probabilities"][r["pred_outcome"]] for r in rows) / n * 100, 1),
        "exact_score": round(sum(1 for r in rows if r.get("score_hit")) / n * 100, 1),
        "scores": _scores(rows, lambda r: r["probabilities"]),
    }


def export_record() -> dict:
    """The track record: what was said, what landed, and how that scores.

    LIVE AND RECONSTRUCTED ARE REPORTED APART. Rows with `retro: true` were
    rebuilt walk-forward on 2026-09-10 for the rounds played before the
    full-round record existed (the first three or four rounds of each
    league). The method only used data available before each kickoff, but
    the rows were written after the results were known, by code that had
    seen them — and a reader cannot verify the difference. So the headline
    figures and the calibration are LIVE rows only (committed before
    kickoff), and the reconstructed rounds are shown separately with their
    own numbers. The picks ledger was pre-committed from week one; it is the
    full-round record that started late.

    BASELINES, so the scores mean something. Uniform (a third each) is what
    knowing nothing scores. Base rate (this season's home/draw/away shares
    over the same rows) is what knowing only "home sides win more" scores —
    an in-sample baseline, flattering to the baseline, which is the honest
    direction to be unfair in."""
    rows = [json.loads(l) for l in HIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    graded = [r for r in rows if r.get("status") == "graded" and r.get("outcome") in OUTCOMES]
    live = [r for r in graded if not r.get("retro")]
    retro = [r for r in graded if r.get("retro")]

    uniform = {k: 1 / 3 for k in OUTCOMES}
    n_live = len(live)
    base = ({k: sum(1 for r in live if r["outcome"] == k) / n_live for k in OUTCOMES}
            if n_live else uniform)

    by_league = {}
    for lg in sorted({r["league"] for r in graded}):
        lg_live = [r for r in live if r["league"] == lg]
        lg_retro = [r for r in retro if r["league"] == lg]
        s = _summary(lg_live)
        by_league[lg] = {
            "n": s["n"], "hit_rate": s["hit_rate"],
            "logloss": s["scores"]["logloss"] if s["scores"] else None,
            "n_reconstructed": len(lg_retro),
            "reconstructed_rounds": ([min(r["week"] for r in lg_retro),
                                      max(r["week"] for r in lg_retro)]
                                     if lg_retro else None),
        }

    live_s = _summary(live)
    retro_s = _summary(retro)
    return {
        "generated": date.today().isoformat(),
        # ---- headline = LIVE rows. Keys kept from the old payload so every
        # page that read them now reads the pre-committed figure.
        "graded": live_s["n"],
        "hit_rate": live_s["hit_rate"],
        "said_avg": live_s["said_avg"],
        "exact_score": live_s["exact_score"],
        "by_league": by_league,
        "calibration": _calibration(live),
        "levels": _levels(live) if live else [],
        "scoring": {
            "model": live_s["scores"],
            "base_rate": _scores(live, lambda r: base),
            "uniform": _scores(live, lambda r: uniform),
            "base_rates": {k: round(v * 100, 1) for k, v in base.items()},
        } if live else None,
        "live_since": min((r["recorded_at"][:10] for r in live), default=None),
        # The goal environment the model priced against what was scored. A
        # Poisson grid turns every goal it fails to expect straight into
        # draw probability, so this is the first place to look when the
        # draw level drifts — before anyone reaches for a correction.
        "goals": {
            "expected": round(sum(sum(r["pred_xg"]) for r in live) / n_live, 2),
            "actual": round(sum(sum(int(x) for x in r["score"].split("-"))
                                for r in live) / n_live, 2),
        } if n_live else None,
        # ---- the reconstructed rounds, apart
        "reconstructed": {
            **retro_s,
            "recorded_on": min((r["recorded_at"][:10] for r in retro), default=None),
            "kickoffs": ([min(r["kickoff"] for r in retro), max(r["kickoff"] for r in retro)]
                         if retro else None),
            "calibration": _calibration(retro),
        },
        # ---- everything together, for anyone who wants the old number
        "all": _summary(graded),
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
            # carried per row so the drill-down can mark a reconstructed
            # fixture where it sits, not only count it in a footnote
            "retro": bool(r.get("retro")),
            "recorded": r["recorded_at"][:10],
        })
    for e in leagues.values():
        e["rows"].sort(key=lambda x: (x["kickoff"], x["home"]), reverse=True)
        graded = [x for x in e["rows"] if x["status"] == "graded"]
        live = [x for x in graded if not x["retro"]]
        e["graded"] = len(live)
        e["hits"] = sum(1 for x in live if x["outcome_hit"])
        e["exact"] = sum(1 for x in live if x["score_hit"])
        e["reconstructed"] = len(graded) - len(live)
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
