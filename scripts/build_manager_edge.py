"""Manager edge — the gap between the squad a manager has and what it does.

Two quantities the site already computes, set against each other:

  SQUAD      the players he picks, each percentiled inside his own position
             on the weights set on the players tab, weighted by the minutes
             he actually gave him
  COLLECTIVE what the side produces on the pitch, from team events,
             opponent-adjusted

  EDGE = COLLECTIVE - SQUAD

Positive means the eleven is worth more than the sum of its parts. That is
the claim, and it is a big one, so this script also tests it (see GATE).

WHAT SHIPS is the minutes, not the rating. A player's rating depends on the
weights the reader sets, which live in the browser — so the build sends
minutes per (player, position) per manager, and the page does the weighting.
It also means the edge moves when the reader moves a slider, which is right:
it is their definition of a good player being tested, not ours.

Writes web/public/data/team/{league}/manager.json
      data/reports/manager_edge.json   (the gate)

Usage: .venv/Scripts/python.exe scripts/build_manager_edge.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.positions import load_match, match_roles
from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.spells import build as build_spells

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"
MENTAL = ROOT / "data" / "web" / "mental"
REPORT = ROOT / "data" / "reports" / "manager_edge.json"

MIN_MINUTES = 200      # below this a player is a cameo, not a selection
# A part-played season is not a season. The same rule the points gate in
# build_reliability.py uses, and for the same reason: with 26/27 four matches
# old, Arsenal "over-achieved by 1.35 points a game" and Fulham "under-
# achieved by 1.22", which is a description of four afternoons.
MIN_SEASON_MATCHES = 20


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


# --------------------------------------------------------------------------
# minutes, per manager
# --------------------------------------------------------------------------

def spell_minutes(league: str, seasons: list, spells: list) -> dict:
    """spell key -> season -> "name|bucket" -> minutes under that manager."""
    owner = {}
    for sp in spells:
        for g in sp.games:
            owner[(sp.team, g)] = sp.key

    mins: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for season in seasons:
        df = pd.read_parquet(
            RAW / league / f"{season}_stamped.parquet",
            columns=["game_id", "team", "player", "player_id"],
        )
        for gid, match in df.groupby("game_id", sort=False):
            doc = load_match(league, season, gid)
            if doc is None:
                continue
            roles = match_roles(doc)
            # playerId -> (name, team) from the events themselves, which is
            # the same mapping the rest of the pipeline uses
            who = {}
            for r in match.dropna(subset=["player", "player_id"]).itertuples(
                    index=False):
                who[int(r.player_id)] = (r.player, r.team)
            for pid, played in roles.items():
                got = who.get(int(pid))
                if not got:
                    continue
                name, team = got
                key = owner.get((team, int(gid)))
                if not key:
                    continue
                for s in played:
                    dur = s["end"] - s["start"]
                    if dur > 0:
                        mins[key][season][f"{name}|{s['bucket']}"] += dur
        print(f"  minutes {season}", flush=True)
    return mins


# --------------------------------------------------------------------------
# the gate: is the edge the MANAGER, or is it the club?
# --------------------------------------------------------------------------

# Mirrors PRESETS in web/app/mental/MentalData.tsx and PRESET in
# web/app/teams/teamScore.ts. Used ONLY by the gate below — nothing that
# ships reads these, because the page uses whatever the reader has set. If
# the defaults over there change, this test is measuring the old ones.
PLAYER_W = {
    "GK": {"claim_90": 16, "conceded_90": 14, "catch_pct": 14, "pass_pct": 12,
           "prog_pass_90": 12, "sweeper_90": 12, "card_90": 8,
           "final_third_90": 12},
    "FB": {"giveaway_90": 14, "ground_duel_90": 12, "takeon_90": 11,
           "cross_90": 10, "recovery_90": 9, "miscontrol_90": 8,
           "interception_90": 8, "touch_box_90": 8, "dispossessed_90": 7,
           "pass_pct": 7, "foul_90": 6},
    "CB": {"aerial_90": 13, "ground_duel_90": 12, "giveaway_90": 12,
           "aerial_def_pct": 11, "clearance_90": 10, "dribbled_past_90": 10,
           "tackle_90": 10, "foul_90": 8, "press_height": 7,
           "availability_pct": 7},
    "WB": {"takeon_90": 14, "cross_90": 13, "ground_duel_90": 12,
           "dispossessed_90": 12, "touch_box_90": 11, "foul_90": 10,
           "availability_pct": 10, "prog_pass_90": 9, "pass_pct": 9},
    "DM": {"aerial_def_90": 13, "giveaway_90": 12, "prog_pass_90": 12,
           "pass_pct": 11, "recovery_90": 11, "takeon_90": 10,
           "miscontrol_90": 9, "dispossessed_90": 6, "foul_90": 6,
           "clearance_90": 6, "final_third_90": 4},
    "CM": {"decisive_90": 12, "giveaway_90": 12, "ground_duel_90": 11,
           "prog_pass_90": 11, "tackle_90": 10, "aerial_def_90": 9,
           "dribbled_past_90": 9, "takeon_90": 8, "foul_90": 7,
           "dispossessed_90": 6, "keypass_90": 5},
    "AM": {"decisive_90": 12, "takeon_90": 11, "dribbled_past_90": 11,
           "keypass_90": 10, "prog_pass_90": 10, "ground_duel_90": 9,
           "foul_90": 9, "miscontrol_90": 8, "giveaway_90": 7, "goal_90": 7,
           "shot_box_pct": 6},
    "WIDE": {"takeon_90": 14, "touch_box_90": 12, "dispossessed_90": 12,
             "giveaway_90": 11, "ground_duel_90": 10, "bigchance_shot_90": 9,
             "fouled_90": 8, "cross_90": 7, "foul_90": 6, "miscontrol_90": 6,
             "final_third_90": 5},
    "ST": {"aerial_att_90": 13, "decisive_90": 11, "bigchance_shot_90": 11,
           "miscontrol_90": 11, "giveaway_90": 10, "ground_duel_90": 10,
           "aerial_att_pct": 9, "card_90": 7, "touch_box_90": 7, "foul_90": 6,
           "fouled_90": 5},
}
TEAM_W = {
    "box_entry_op_90": 14, "shot_op_90": 12, "bigchance_op_90": 10,
    "prog_pass_90": 8, "f3_entry_90": 6,
    "box_entry_con_op_90": 15, "shot_con_op_90": 13, "bigchance_con_op_90": 12,
    "sp_shot_con_90": 6, "sp_shot_90": 4,
}


def _pct(values: list) -> list:
    """Rank to 0-100, ties broken by order. Same shape as the web's."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [50.0] * len(values)
    n = len(values)
    for rank, i in enumerate(order):
        out[i] = (rank / (n - 1) * 100) if n > 1 else 50.0
    return out


def squad_by_club_season(league: str, seasons: list) -> dict:
    """(team, season) -> squad rating, on the shipped default weights."""
    lk = slug(league)
    meta = json.loads((MENTAL / lk / "meta.json").read_text(encoding="utf-8"))
    keys = meta["metric_keys"]
    rel = meta.get("reliability", {})
    ix = {k: i for i, k in enumerate(keys)}
    out = {}
    for season in seasons:
        path = MENTAL / lk / f"{season}.json"
        if not path.exists():
            continue
        v = json.loads(path.read_text(encoding="utf-8"))
        raw, buckets = [], v["p"]
        for j, bucket in enumerate(buckets):
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
        # percentile INSIDE each bucket, exactly as the page does
        pct = [50.0] * len(raw)
        by_b = defaultdict(list)
        for j, b in enumerate(buckets):
            by_b[b].append(j)
        for b, idxs in by_b.items():
            ranked = _pct([raw[j] for j in idxs])
            for j, p in zip(idxs, ranked):
                pct[j] = p
        # minutes-weighted, per club
        num = defaultdict(float)
        den = defaultdict(float)
        for j, team in enumerate(v["t"]):
            m = v["m"][j]
            num[team] += pct[j] * m
            den[team] += m
        for team in num:
            if den[team]:
                out[(team, season)] = num[team] / den[team]
    return out


def collective_by_club_season(league: str) -> tuple:
    """(team, season) -> the Overall score, and -> points per match."""
    lk = slug(league)
    meta = json.loads((OUT / lk / "meta.json").read_text(encoding="utf-8"))
    rows = json.loads((OUT / lk / "club_season.json").read_text(encoding="utf-8"))
    by_metric = {m["key"]: m for m in meta["metrics"]}
    pts = {(r["team"], r["season"]): r.get("pts") for r in rows
           if (r.get("matches") or 0) >= MIN_SEASON_MATCHES}
    out = {}
    for season in sorted({r["season"] for r in rows}):
        pool = [r for r in rows if r["season"] == season
                and (r.get("matches") or 0) >= MIN_SEASON_MATCHES]
        if not pool:
            continue
        pct = {}
        for key, m in by_metric.items():
            col = f"{key}_adj" if f"{key}_adj" in pool[0] else key
            vals = [(i, r.get(col)) for i, r in enumerate(pool)
                    if isinstance(r.get(col), (int, float))]
            if not vals:
                continue
            ranked = _pct([v for _i, v in vals])
            pct[key] = {
                pool[i]["team"]: (100 - p if m["invert"] else p)
                for (i, _v), p in zip(vals, ranked)
            }
        for r in pool:
            s = used = 0.0
            for k, w in TEAM_W.items():
                s += pct.get(k, {}).get(r["team"], 50.0) * w
                used += w
            out[(r["team"], season)] = s / used if used else 50.0
    return out, pts


def gate(league: str, seasons: list, spells: list) -> dict:
    """Is the edge the MANAGER, or is it just the club?

    The obvious test — does edge predict points — proves nothing: the
    collective score is built from process metrics that already predict
    points at 0.78, so edge inherits that whoever is in charge.

    The test that bites: a club's edge from one season to the next, split by
    whether the manager changed in between. If the edge belongs to the man,
    it should jump when he is replaced and hold when he is not. If it belongs
    to the club — the recruitment, the ownership, the stadium — it holds
    either way and the whole idea is misnamed.
    """
    squad = squad_by_club_season(league, seasons)
    coll, pts = collective_by_club_season(league)
    # which manager ran most of a club's season
    ran = defaultdict(lambda: defaultdict(int))
    for sp in spells:
        for season in sp.seasons:
            ran[(sp.team, season)][sp.manager] += 1
    boss = {k: max(v.items(), key=lambda kv: kv[1])[0] for k, v in ran.items()}

    # BOTH AXES RANKED AMONG THE SAME CLUBS, in the same season, before they
    # are subtracted. Taken raw they are not on one scale: a squad rating is
    # a percentile among PLAYERS and lands between 35 and 70, while the
    # collective score is a percentile among CLUBS and runs 4 to 91. The
    # difference of the two was then mostly the difference in spread — Man
    # City +29.7 and Luton -38.3, which is a list of good and bad teams
    # wearing a new label, not a list of over- and under-achievers.
    edge = {}
    for season in seasons:
        keys = [k for k in squad if k[1] == season and k in coll]
        if len(keys) < 4:
            continue
        sp = _pct([squad[k] for k in keys])
        cp = _pct([coll[k] for k in keys])
        for k, a, b in zip(keys, sp, cp):
            edge[k] = b - a
    same, changed = [], []
    for (team, season) in list(edge):
        i = seasons.index(season) if season in seasons else -1
        if i <= 0:
            continue
        prev = (team, seasons[i - 1])
        if prev not in edge:
            continue
        # a 4-match season is not a season
        move = abs(edge[(team, season)] - edge[prev])
        if boss.get((team, season)) == boss.get(prev):
            same.append(move)
        else:
            changed.append(move)

    def stat(xs):
        return {"n": len(xs),
                "mean": round(float(np.mean(xs)), 2) if xs else None,
                "median": round(float(np.median(xs)), 2) if xs else None}

    # Does the gap between the two groups survive shuffling? With 22 and 29
    # observations, two medians that differ by a third could easily be the
    # luck of which club-seasons landed where, and saying "it moves more when
    # the manager changes" without checking that is how a finding gets made
    # out of nothing.
    p_value = None
    if same and changed:
        obs = float(np.median(changed) - np.median(same))
        pool = np.array(same + changed)
        rng = np.random.default_rng(0)
        hits = 0
        for _ in range(20000):
            rng.shuffle(pool)
            a, b = pool[:len(same)], pool[len(same):]
            if float(np.median(b) - np.median(a)) >= obs:
                hits += 1
        p_value = round(hits / 20000, 4)

    # And the repeat test the rest of the site uses: does a manager's edge in
    # one season say anything about his edge in the next?
    pairs = [(edge[(t, seasons[i - 1])], edge[(t, s)])
             for (t, s) in edge
             for i in [seasons.index(s) if s in seasons else -1]
             if i > 0 and (t, seasons[i - 1]) in edge
             and boss.get((t, s)) == boss.get((t, seasons[i - 1]))]
    repeat = (round(float(np.corrcoef([a for a, _b in pairs],
                                      [b for _a, b in pairs])[0, 1]), 3)
              if len(pairs) > 2 else None)

    vals = list(edge.values())
    rows = [{"team": t, "season": s, "squad": round(squad[(t, s)], 1),
             "collective": round(coll[(t, s)], 1), "pts": pts.get((t, s)),
             "edge": round(e, 1), "manager": boss.get((t, s))}
            for (t, s), e in edge.items()]

    # THE DIAGNOSTIC THAT DECIDES WHAT THIS IS. If a big negative edge is
    # under-achievement it should cost points. If it does not, the edge is
    # measuring a style the metric set does not reward — Brentford build
    # their whole method on set pieces and long throws, and the collective
    # score is nine-tenths open play.
    have = [r for r in rows if isinstance(r["pts"], (int, float))]

    # SECOND DEFINITION, because the first one fails below and the failure
    # says what to try instead. "Collective minus squad" compares a squad
    # against a PROCESS score, and the process score is nine-tenths open
    # play — so a side built on set pieces and long throws reads as
    # under-achieving whatever it wins. Ask the question against the thing
    # that actually matters instead: given these players, how many POINTS
    # should this side have taken, and how many did it take?
    surplus = {}
    if len(have) > 4:
        x = np.array([r["squad"] for r in have])
        y = np.array([r["pts"] for r in have])
        slope, icept = np.polyfit(x, y, 1)
        for r in have:
            r["expected_pts"] = round(float(slope * r["squad"] + icept), 2)
            r["surplus"] = round(float(r["pts"] - r["expected_pts"]), 2)
            surplus[(r["team"], r["season"])] = r["surplus"]
    edge_pts = (round(float(np.corrcoef([r["edge"] for r in have],
                                        [r["pts"] for r in have])[0, 1]), 3)
                if len(have) > 2 else None)
    squad_pts = (round(float(np.corrcoef([r["squad"] for r in have],
                                         [r["pts"] for r in have])[0, 1]), 3)
                 if len(have) > 2 else None)
    coll_pts = (round(float(np.corrcoef([r["collective"] for r in have],
                                        [r["pts"] for r in have])[0, 1]), 3)
                if len(have) > 2 else None)
    # the same two tests, run on the second definition
    s_same, s_changed = [], []
    for (team, season) in list(surplus):
        i = seasons.index(season) if season in seasons else -1
        if i <= 0:
            continue
        prev = (team, seasons[i - 1])
        if prev not in surplus:
            continue
        move = abs(surplus[(team, season)] - surplus[prev])
        (s_same if boss.get((team, season)) == boss.get(prev)
         else s_changed).append(move)
    s_pairs = [(surplus[(t, seasons[seasons.index(s) - 1])], surplus[(t, s)])
               for (t, s) in surplus
               if s in seasons and seasons.index(s) > 0
               and (t, seasons[seasons.index(s) - 1]) in surplus
               and boss.get((t, s)) == boss.get((t, seasons[seasons.index(s) - 1]))]
    s_repeat = (round(float(np.corrcoef([a for a, _b in s_pairs],
                                        [b for _a, b in s_pairs])[0, 1]), 3)
                if len(s_pairs) > 2 else None)

    return {
        "verdict": (
            "DEFINITION 1 (collective minus squad) REJECTED: it correlates "
            "0.17 with points, and its extremes are a list of playing styles "
            "rather than of over-achievers — Brentford bottom on 1.47 points "
            "a game, Bournemouth top on 1.26 — because the collective score "
            "is nine-tenths open play and some sides build on set pieces. "
            "DEFINITION 2 (points minus points the squad predicts) KEPT but "
            "NOT ATTRIBUTED TO THE MANAGER: it repeats at 0.50 season to "
            "season and its extremes are recognisable (Emery's Villa and "
            "Nuno's Forest over, Kompany's Burnley and Maresca's Chelsea "
            "under), but it moves NO MORE when a club changes manager (0.27) "
            "than when it keeps one (0.29). On 12 manager changes in four "
            "seasons of one league there is no evidence the gap belongs to "
            "the man rather than to the club."
        ),
        "edge_vs_points_r": edge_pts,
        "surplus": {
            "what": "points taken minus points expected from squad rating",
            "same_manager": stat(s_same),
            "manager_changed": stat(s_changed),
            "repeats_same_manager": s_repeat,
            "repeat_n": len(s_pairs),
            "top": sorted(
                (r for r in have if "surplus" in r),
                key=lambda r: -r["surplus"])[:8],
            "bottom": sorted(
                (r for r in have if "surplus" in r),
                key=lambda r: r["surplus"])[:8],
        },
        "squad_vs_points_r": squad_pts,
        "collective_vs_points_r": coll_pts,
        "n_club_seasons": len(edge),
        "edge_spread": round(float(np.std(vals)), 2) if vals else None,
        "same_manager": stat(same),
        "manager_changed": stat(changed),
        "p_value": p_value,
        "repeats_same_manager": repeat,
        "repeat_n": len(pairs),
        "squad_vs_collective_r": round(float(np.corrcoef(
            [squad[k] for k in edge], [coll[k] for k in edge])[0, 1]), 3)
        if len(edge) > 2 else None,
        "top": sorted(rows, key=lambda d: -d["edge"])[:8],
        "bottom": sorted(rows, key=lambda d: d["edge"])[:8],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--gate-only", action="store_true",
                    help="re-run the test without rebuilding the minutes, "
                         "which is the slow half")
    args = ap.parse_args()
    seasons = seasons_on_disk(args.league)
    lk = slug(args.league)
    print(f"seasons: {', '.join(seasons)}")

    spells = build_spells(args.league, seasons)
    if args.gate_only:
        report = gate(args.league, seasons, spells)
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                          encoding="utf-8")
        show(report)
        return 0
    mins = spell_minutes(args.league, seasons, spells)

    payload = []
    for sp in spells:
        per = mins.get(sp.key, {})
        trimmed = {
            season: {k: round(v) for k, v in row.items() if v >= MIN_MINUTES}
            for season, row in per.items()
        }
        payload.append({
            "spell": sp.key,
            "team": sp.team,
            "manager": sp.manager,
            "start": sp.start[:10],
            "end": sp.end[:10],
            "matches": sp.matches,
            "seasons": sp.seasons,
            "short": sp.short,
            "minutes": {s: r for s, r in trimmed.items() if r},
        })

    for root in (OUT, PUB):
        (root / lk).mkdir(parents=True, exist_ok=True)
        (root / lk / "manager.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = gate(args.league, seasons, spells)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                      encoding="utf-8")

    kb = (OUT / lk / "manager.json").stat().st_size // 1024
    print()
    print(f"-> manager.json  {len(payload)} spells, {kb} KB")
    show(report)
    return 0


def show(report: dict) -> None:
    print()
    print("GATE — does the edge move when the manager does?")
    print(f"  club-seasons               {report['n_club_seasons']}")
    print(f"  spread of edge (sd)        {report['edge_spread']}")
    print(f"  squad vs collective  r =   {report['squad_vs_collective_r']}")
    s, c = report["same_manager"], report["manager_changed"]
    print(f"  same manager, year to year  n={s['n']:<3} median move {s['median']}")
    print(f"  manager changed             n={c['n']:<3} median move {c['median']}")
    print(f"  p (shuffle test)           {report['p_value']}")
    print(f"  repeats, same manager      r = {report['repeats_same_manager']} "
          f"(n={report['repeat_n']})")
    print()
    print("  against POINTS per match")
    print(f"    squad       r = {report['squad_vs_points_r']}")
    print(f"    collective  r = {report['collective_vs_points_r']}")
    print(f"    edge        r = {report['edge_vs_points_r']}")

    def rows(label, key):
        print(f"  {label}")
        for d in report[key][:5]:
            p = d["pts"]
            print(f"    {d['team']:<18}{d['season']}  squad {d['squad']:>5}  "
                  f"collective {d['collective']:>5}  edge {d['edge']:>+6}  "
                  f"pts {p if p is None else round(p, 2):>5}  {d['manager']}")
    print()
    rows("biggest edge", "top")
    rows("smallest edge", "bottom")

    s = report["surplus"]
    print()
    print("SECOND DEFINITION — points taken minus points the squad predicts")
    a, b = s["same_manager"], s["manager_changed"]
    print(f"  same manager, year to year  n={a['n']:<3} median move {a['median']}")
    print(f"  manager changed             n={b['n']:<3} median move {b['median']}")
    print(f"  repeats, same manager       r = {s['repeats_same_manager']} "
          f"(n={s['repeat_n']})")
    for label, key in (("over-achieved", "top"), ("under-achieved", "bottom")):
        print(f"  {label}")
        for d in s[key][:5]:
            print(f"    {d['team']:<18}{d['season']}  squad {d['squad']:>5}  "
                  f"expected {d['expected_pts']:>5}  actual {d['pts']:>5}  "
                  f"{d['surplus']:>+6}  {d['manager']}")


if __name__ == "__main__":
    raise SystemExit(main())
