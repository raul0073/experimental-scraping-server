"""Do these metrics REPEAT? The first test the benchmark has to pass.

A dependability rating that does not persist from one season to the next is
measuring luck, not character — the same replication test that killed the
availability experiment. So: compute each candidate metric for every player
in 24/25 and again in 25/26, and correlate a player's first season against
his second.

    high correlation  -> a stable trait, worth ranking on
    near zero         -> noise wearing a metric's name

Exposure is handled the way the design demands: rates are per 90 minutes
ACTUALLY on the pitch, and state metrics are per 90 minutes spent in that
state, compared against the player's own overall rate. A losing team
produces more events, so raw counts by state are contaminated before you
start (measured: 29.4% of events happen while behind against 26.6% ahead).

Usage: .venv/Scripts/python.exe scripts/experiment_persistence.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
MIN_MINUTES = 900          # ten full matches in BOTH seasons
DUELS = ("Aerial", "Tackle", "Challenge")


def player_minutes(match: pd.DataFrame) -> dict:
    """Minutes each player was on the pitch, from the substitution events.
    A player with no substitution event who appears at all played the full
    match; the match's own last minute is the finish, so added time counts."""
    end = int(match["minute"].max())
    on, off = {}, {}
    for r in match[match["type"] == "SubstitutionOn"].itertuples(index=False):
        on[r.player] = int(r.minute)
    for r in match[match["type"] == "SubstitutionOff"].itertuples(index=False):
        off[r.player] = int(r.minute)
    out = {}
    for player in match["player"].dropna().unique():
        start = on.get(player, 0)
        finish = off.get(player, end)
        out[player] = (start, max(finish, start), finish - start)
    return out


def state_segments(match: pd.DataFrame) -> dict:
    """For each team, the minute ranges it spent behind / level / ahead.
    Derived from the stamped events themselves so it cannot drift from the
    stamping: consecutive events sharing a state define the segment."""
    segs = defaultdict(list)
    for team, g in match.groupby("team"):
        g = g.sort_values("minute")
        cur, start = None, 0
        for r in g.itertuples(index=False):
            if r.score_state != cur:
                if cur is not None:
                    segs[team].append((start, int(r.minute), cur))
                cur, start = r.score_state, int(r.minute)
        if cur is not None:
            segs[team].append((start, int(g["minute"].max()), cur))
    return segs


def overlap(a: tuple, b: tuple) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def season_table(path: Path, half: str | None = None) -> pd.DataFrame:
    """half='odd'/'even' splits the season's matches for a RELIABILITY check:
    a metric that will not agree with itself inside one season cannot be
    expected to agree across two, and the failure is measurement noise
    rather than the absence of a trait."""
    df = pd.read_parquet(path)
    if half:
        gids = sorted(df["game_id"].unique())
        keep = {g for i, g in enumerate(gids) if (i % 2 == 0) == (half == "even")}
        df = df[df["game_id"].isin(keep)]
    rows = defaultdict(lambda: defaultdict(float))

    for _, match in df.groupby("game_id", sort=False):
        mins = player_minutes(match)
        segs = state_segments(match)
        team_of = match.dropna(subset=["player"]).groupby("player")["team"].first()

        for player, (start, finish, played) in mins.items():
            if played <= 0:
                continue
            r = rows[player]
            r["minutes"] += played
            team = team_of.get(player)
            for s_start, s_end, state in segs.get(team, []):
                r[f"min_{state}"] += overlap((start, finish), (s_start, s_end))

        ev = match.dropna(subset=["player"])
        for player, g in ev.groupby("player"):
            r = rows[player]
            succ = g["outcome_type"] == "Successful"
            r["takeon_att"] += int((g["type"] == "TakeOn").sum())
            r["takeon_ok"] += int(((g["type"] == "TakeOn") & succ).sum())
            r["duel_att"] += int(g["type"].isin(DUELS).sum())
            r["duel_ok"] += int((g["type"].isin(DUELS) & succ).sum())
            r["aerial_att"] += int((g["type"] == "Aerial").sum())
            r["aerial_ok"] += int(((g["type"] == "Aerial") & succ).sum())
            r["pass_att"] += int((g["type"] == "Pass").sum())
            r["pass_ok"] += int(((g["type"] == "Pass") & succ).sum())
            r["recovery"] += int((g["type"] == "BallRecovery").sum())
            r["dispossessed"] += int((g["type"] == "Dispossessed").sum())
            r["foul"] += int((g["type"] == "Foul").sum())
            r["error"] += int((g["type"] == "Error").sum())
            # the question this project exists for: did he still go at his
            # man while his team was losing?
            behind = g["score_state"] == "behind"
            r["takeon_att_behind"] += int(((g["type"] == "TakeOn") & behind).sum())
            r["duel_att_behind"] += int((g["type"].isin(DUELS) & behind).sum())
            r["pass_att_behind"] += int(((g["type"] == "Pass") & behind).sum())
            r["pass_ok_behind"] += int(((g["type"] == "Pass") & behind & succ).sum())

    out = []
    for player, r in rows.items():
        mins = r["minutes"]
        if mins < MIN_MINUTES:
            continue
        per90 = lambda k: r[k] / mins * 90                      # noqa: E731
        pct = lambda a, b: (r[a] / r[b] * 100) if r[b] else np.nan  # noqa: E731
        mb = r.get("min_behind", 0.0)
        row = {
            "player": player, "minutes": mins,
            "takeon_90": per90("takeon_att"),
            "takeon_pct": pct("takeon_ok", "takeon_att"),
            "duel_90": per90("duel_att"),
            "duel_pct": pct("duel_ok", "duel_att"),
            "aerial_pct": pct("aerial_ok", "aerial_att"),
            "pass_90": per90("pass_att"),
            "pass_pct": pct("pass_ok", "pass_att"),
            "recovery_90": per90("recovery"),
            "dispossessed_90": per90("dispossessed"),
            "foul_90": per90("foul"),
            "error_90": per90("error"),
        }
        # INTENT UNDER PRESSURE: his rate while behind, relative to his own
        # overall rate. Above 1 = he goes at them more when losing.
        if mb >= 180:
            row["takeon_behind_idx"] = (
                (r["takeon_att_behind"] / mb * 90) / row["takeon_90"]
                if row["takeon_90"] > 0 else np.nan)
            row["duel_behind_idx"] = (
                (r["duel_att_behind"] / mb * 90) / row["duel_90"]
                if row["duel_90"] > 0 else np.nan)
            row["pass_pct_behind_idx"] = (
                (r["pass_ok_behind"] / r["pass_att_behind"] * 100) / row["pass_pct"]
                if r["pass_att_behind"] and row["pass_pct"] else np.nan)
            row["min_behind"] = mb
        out.append(row)
    return pd.DataFrame(out).set_index("player")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--seasons", nargs=2, default=["2425", "2526"])
    ap.add_argument("--split-half", metavar="SEASON", default=None,
                    help="reliability check: correlate a season's odd matches "
                         "against its even ones. A metric that cannot agree "
                         "with itself inside one season is too noisy to "
                         "measure, which is different from the trait not "
                         "existing.")
    args = ap.parse_args()

    if args.split_half:
        global MIN_MINUTES
        MIN_MINUTES = 450                       # each half holds ~19 matches
        p = RAW / args.league / f"{args.split_half}_stamped.parquet"
        odd, even = season_table(p, "odd"), season_table(p, "even")
        shared = odd.index.intersection(even.index)
        print(f"split-half within {args.split_half}: {len(shared)} players\n")
        print(f"{'metric':<22}{'n':>5}{'rho':>9}   reliability")
        print("-" * 60)
        out = []
        for m in odd.columns:
            if m in ("minutes", "min_behind") or m not in even.columns:
                continue
            x, y = odd.loc[shared, m], even.loc[shared, m]
            ok = x.notna() & y.notna()
            if ok.sum() < 30:
                continue
            rho = float(x[ok].rank().corr(y[ok].rank()))
            verdict = ("measurable" if rho >= 0.6 else
                       "marginal" if rho >= 0.4 else
                       "TOO NOISY TO MEASURE")
            out.append({"metric": m, "n": int(ok.sum()), "rho": round(rho, 3)})
            print(f"{m:<22}{int(ok.sum()):>5}{rho:>9.3f}   {verdict}")
        path = ROOT / "data" / "reports" / "experiment_reliability.json"
        path.write_text(json.dumps(
            {"league": args.league, "season": args.split_half,
             "min_minutes": MIN_MINUTES, "results": out}, indent=2),
            encoding="utf-8")
        print(f"\n-> {path}")
        return 0

    tables = {}
    for s in args.seasons:
        p = RAW / args.league / f"{s}_stamped.parquet"
        if not p.exists():
            print(f"missing {p} — run scripts/stamp_event_state.py first")
            return 1
        tables[s] = season_table(p)
        print(f"{s}: {len(tables[s])} players with {MIN_MINUTES}+ minutes")

    a, b = (tables[s] for s in args.seasons)
    shared = a.index.intersection(b.index)
    print(f"\nplayers in BOTH seasons: {len(shared)}\n")

    metrics = [c for c in a.columns if c not in ("minutes", "min_behind")]
    results = []
    for m in metrics:
        if m not in b.columns:
            continue
        x, y = a.loc[shared, m], b.loc[shared, m]
        ok = x.notna() & y.notna()
        n = int(ok.sum())
        if n < 30:
            results.append({"metric": m, "n": n, "rho": None})
            continue
        rho = x[ok].rank().corr(y[ok].rank())      # Spearman
        results.append({"metric": m, "n": n, "rho": round(float(rho), 3)})

    results.sort(key=lambda r: (r["rho"] is None, -(r["rho"] or 0)))
    print(f"{'metric':<22}{'n':>5}{'rho':>8}   persistence")
    print("-" * 60)
    for r in results:
        if r["rho"] is None:
            print(f"{r['metric']:<22}{r['n']:>5}{'--':>8}   too few players")
            continue
        rho = r["rho"]
        verdict = ("STRONG — a real trait" if rho >= 0.6 else
                   "moderate" if rho >= 0.4 else
                   "weak" if rho >= 0.25 else
                   "NOISE — does not repeat")
        print(f"{r['metric']:<22}{r['n']:>5}{rho:>8.3f}   {verdict}")

    out = ROOT / "data" / "reports" / "experiment_persistence.json"
    out.write_text(json.dumps({
        "league": args.league, "seasons": args.seasons,
        "min_minutes": MIN_MINUTES, "shared_players": len(shared),
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
