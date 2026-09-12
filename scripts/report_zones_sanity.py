"""Stage 4 sanity gate: build zone profiles for all leagues and check them
against reality (goals scored/conceded, xG) from the same season.

Usage (from repo root):
    .venv\\Scripts\\python.exe scripts\\report_zones_sanity.py --season 2526
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.zones.zones_engine import ZonesEngine

ATT_ZONES = ["attLeft", "attCentral", "attRight"]
DEF_ZONES = ["defLeft", "defCentral", "defRight"]


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2526")
    args = ap.parse_args()

    lines = [f"# Zones sanity report — season {args.season}", ""]
    problems = []

    for league in LEAGUE_NAME_MAP:
        z = ZonesEngine(league, args.season).build(persist=True)
        teams = z["teams"]

        fx = FixturesService.load(league, args.season)
        gf, ga = {}, {}
        for m in fx["matches"]:
            if not m["played"] or not isinstance(m["week"], int):
                continue
            gf[m["home_team"]] = gf.get(m["home_team"], 0) + m["home_goals"]
            gf[m["away_team"]] = gf.get(m["away_team"], 0) + m["away_goals"]
            ga[m["home_team"]] = ga.get(m["home_team"], 0) + m["away_goals"]
            ga[m["away_team"]] = ga.get(m["away_team"], 0) + m["home_goals"]

        # xGA — the honest target for a defense rating built to exclude
        # keeper performance and finishing luck; corr(xGA, GA) is the ceiling
        # any xG-based defense score can reach against raw goals conceded.
        import json as _json
        from pathlib import Path as _Path
        us = _json.loads(_Path(f"data/understat/{league}/{args.season}.json").read_text(encoding="utf-8"))
        xga = {}
        for m in us["matches"]:
            xga[m["home_team"]] = xga.get(m["home_team"], 0) + (m["away_xg"] or 0)
            xga[m["away_team"]] = xga.get(m["away_team"], 0) + (m["home_xg"] or 0)

        # aggregate the way the predictor consumes zones: importance-weighted
        from models.zones.zones_config import ZONE_IMPORTANCE
        att_score = {t: sum(teams[t][zz]["rating"] * ZONE_IMPORTANCE[zz] for zz in ATT_ZONES) for t in teams}
        def_score = {t: sum(teams[t][zz]["rating"] * ZONE_IMPORTANCE[zz] for zz in DEF_ZONES) for t in teams}

        common = [t for t in att_score if t in gf]
        rho_att = spearman([att_score[t] for t in common], [gf[t] for t in common])
        rho_def = spearman([def_score[t] for t in common], [-ga[t] for t in common])
        rho_def_xga = spearman([def_score[t] for t in common], [-xga[t] for t in common])
        ceiling = spearman([xga[t] for t in common], [ga[t] for t in common])

        top_att = sorted(att_score, key=att_score.get, reverse=True)[:5]
        top_def = sorted(def_score, key=def_score.get, reverse=True)[:5]
        top_scorers = sorted(gf, key=gf.get, reverse=True)[:5]
        best_defenses = sorted(ga, key=ga.get)[:5]

        dead = []
        for zz in teams[next(iter(teams))]:
            vals = {round(teams[t][zz]["rating"], 1) for t in teams}
            if len(vals) <= 2:
                dead.append(zz)

        missing_join = [t for t in att_score if t not in gf]

        lines += [
            f"## {league}",
            "",
            f"- teams rated: {len(teams)}; unjoined vs fixtures: {missing_join or 'none'}",
            f"- Spearman(attack zones, goals scored): **{rho_att:.2f}**",
            f"- Spearman(defense zones, xGA prevented): **{rho_def_xga:.2f}** (consistency check)",
            f"- Spearman(defense zones, goals prevented): **{rho_def:.2f}** (ceiling = corr(xGA,GA) = {ceiling:.2f})",
            f"- top-5 attack zones: {', '.join(top_att)}",
            f"- top-5 actual scorers: {', '.join(top_scorers)}",
            f"- top-5 defense zones: {', '.join(top_def)}",
            f"- top-5 actual defenses (fewest conceded): {', '.join(best_defenses)}",
            f"- dead zones (<=2 distinct ratings): {dead or 'none'}",
            "",
        ]
        if rho_att < 0.6:
            problems.append(f"{league}: weak attack correlation {rho_att:.2f}")
        if rho_def_xga < 0.85:
            problems.append(f"{league}: defense zones inconsistent with xGA {rho_def_xga:.2f}")
        if rho_def < 0.75 * ceiling:
            problems.append(f"{league}: defense vs GA {rho_def:.2f} below 75% of ceiling {ceiling:.2f}")
        if dead:
            problems.append(f"{league}: dead zones {dead}")
        if missing_join:
            problems.append(f"{league}: name join gaps {missing_join}")

    lines += ["## Verdict", ""]
    if problems:
        lines += ["GATE ISSUES:"] + [f"- {p}" for p in problems]
    else:
        lines += ["GATE PASSED: all leagues correlate with reality, no dead zones, clean name joins."]

    out = Path("data/reports/zones_sanity.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[-6:]))
    print(f"\nreport -> {out}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
