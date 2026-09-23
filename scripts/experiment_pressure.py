"""Does a player's behaviour under pressure REPEAT? The gate for axis 3.

The earlier attempt sliced the season — his take-ons while behind over his
take-ons overall — and returned 0.016, which was not football saying nothing
is there. It was a ratio of two small noisy numbers. A winger logs about
fifteen take-ons while behind in a season.

This weights instead of slicing. Every event keeps its place in the sample
and carries the weight of the moment it happened in, from data/config/
leverage.json. Two different weights, because they are two different
questions and they disagree:

    leverage    how much the result hangs on this moment. Level with five
                minutes left is 2.25; anything at 3-0 is zero.
    adversity   how bad the position is. A goal down AND a man down with
                half an hour left is 1.81 — while its LEVERAGE is 0.72,
                because that match is mostly gone already.

Six candidate indices, each his weighted figure over his own flat figure, so
1.00 means he behaves identically whatever the state:

    lev_involve / adv_involve     does he get on the ball when it matters?
                                  Measured against his own team's events
                                  while he was on the pitch, so a player is
                                  not credited for a side that spent the
                                  season chasing games.
    lev_pass_pct / adv_pass_pct   does his passing hold up?
    lev_duel_pct / adv_duel_pct   does he still win it?

Then the same gate every metric faced: his season against his next season,
within his position bucket. An index that does not repeat is not a trait of
the footballer and has no business in a ranking.

Usage: .venv/Scripts/python.exe scripts/experiment_pressure.py
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.positions import BUCKET_ORDER, load_match, match_roles
from services.mental.role_bank import RAW, _event_buckets, seasons_on_disk

ROOT = Path(__file__).resolve().parent.parent
LEV = ROOT / "data" / "config" / "leverage.json"
OUT = ROOT / "data" / "reports" / "experiment_pressure.json"
MIN_EVENTS = 600       # in the role, in a season
MIN_PLAYERS = 15
DUELS = ("Aerial", "Tackle", "Challenge")

INDICES = ["lev_involve", "adv_involve", "lev_pass_pct", "adv_pass_pct",
           "lev_duel_pct", "adv_duel_pct"]


def weight_lookup(table: dict, cap_d: int, cap_m: int, bin_t: int):
    """(score_diff, man_diff, minutes_left) -> weight, vectorised."""
    def look(diff, men, left):
        d = np.clip(np.nan_to_num(diff), -cap_d, cap_d).astype(int)
        m = np.clip(np.nan_to_num(men), -cap_m, cap_m).astype(int)
        t = np.clip((np.nan_to_num(left) // bin_t) * bin_t, 0, 95).astype(int)
        return np.array([table.get(f"{a}|{b}|{c}", 1.0)
                         for a, b, c in zip(d, m, t)], dtype=float)
    return look


def season_table(league: str, season: str, lev_cfg: dict,
                 half: str | None = None, min_events: int | None = None
                 ) -> pd.DataFrame:
    look_lev = weight_lookup(lev_cfg["leverage"], lev_cfg["diff_cap"],
                             lev_cfg["men_cap"], lev_cfg["time_bin"])
    look_adv = weight_lookup(lev_cfg["adversity"], lev_cfg["diff_cap"],
                             lev_cfg["men_cap"], lev_cfg["time_bin"])
    acc = defaultdict(lambda: defaultdict(float))
    floor = MIN_EVENTS if min_events is None else min_events
    df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
    if half:
        gids = sorted(df["game_id"].unique())
        keep = {g for i, g in enumerate(gids)
                if (i % 2 == 0) == (half == "even")}
        df = df[df["game_id"].isin(keep)]

    for gid, match in df.groupby("game_id", sort=False):
        doc = load_match(league, season, gid)
        if doc is None:
            continue
        roles = match_roles(doc)
        end = float(match["expanded_minute"].max())
        m = match.dropna(subset=["player_id"]).copy()
        if m.empty:
            continue
        left = end - m["expanded_minute"].to_numpy(float)
        m["w_lev"] = look_lev(m["score_diff"].to_numpy(),
                              m["man_diff"].to_numpy(), left)
        m["w_adv"] = look_adv(m["score_diff"].to_numpy(),
                              m["man_diff"].to_numpy(), left)
        m["bucket"] = _event_buckets(match, roles).reindex(m.index)
        m = m.dropna(subset=["bucket"])
        if m.empty:
            continue

        # the team's own average while each man was on the pitch, so his
        # index measures HIM and not the kind of matches his side played
        team_cum = {}
        for team, g in m.groupby("team"):
            g = g.sort_values("expanded_minute")
            mins = g["expanded_minute"].to_numpy(float)
            team_cum[team] = (
                mins,
                np.concatenate([[0.0], np.cumsum(g["w_lev"].to_numpy())]),
                np.concatenate([[0.0], np.cumsum(g["w_adv"].to_numpy())]),
            )
        name_of = m.groupby("player_id")["player"].first()
        team_of = m.groupby("player_id")["team"].first()

        for pid, spells in roles.items():
            name, team = name_of.get(pid), team_of.get(pid)
            if name is None or team not in team_cum:
                continue
            mins, cl, ca = team_cum[team]
            for s in spells:
                lo = int(np.searchsorted(mins, s["start"], "left"))
                hi = int(np.searchsorted(mins, s["end"], "left"))
                if hi <= lo:
                    continue
                a = acc[(name, s["bucket"])]
                a["team_n"] += hi - lo
                a["team_lev"] += cl[hi] - cl[lo]
                a["team_adv"] += ca[hi] - ca[lo]

        ok = (m["outcome_type"] == "Successful").to_numpy()
        is_pass = (m["type"] == "Pass").to_numpy()
        is_duel = m["type"].isin(DUELS).to_numpy()
        wl, wa = m["w_lev"].to_numpy(), m["w_adv"].to_numpy()
        for (player, bucket), idx in m.groupby(["player", "bucket"]).groups.items():
            sel = m.index.get_indexer(idx)
            a = acc[(player, bucket)]
            a["n"] += len(sel)
            a["lev"] += wl[sel].sum()
            a["adv"] += wa[sel].sum()
            p, d = is_pass[sel], is_duel[sel]
            a["pass_n"] += p.sum()
            a["pass_ok"] += (p & ok[sel]).sum()
            a["pass_wl"] += wl[sel][p].sum()
            a["pass_wl_ok"] += wl[sel][p & ok[sel]].sum()
            a["pass_wa"] += wa[sel][p].sum()
            a["pass_wa_ok"] += wa[sel][p & ok[sel]].sum()
            a["duel_n"] += d.sum()
            a["duel_ok"] += (d & ok[sel]).sum()
            a["duel_wl"] += wl[sel][d].sum()
            a["duel_wl_ok"] += wl[sel][d & ok[sel]].sum()
            a["duel_wa"] += wa[sel][d].sum()
            a["duel_wa_ok"] += wa[sel][d & ok[sel]].sum()

    rows = []
    for (player, bucket), a in acc.items():
        if a["n"] < floor or a["team_n"] < floor:
            continue
        def ratio(w_ok, w_all, flat_ok, flat_all, floor=60):
            if flat_all < floor or not w_all or not flat_ok:
                return np.nan
            return (w_ok / w_all) / (flat_ok / flat_all)
        rows.append({
            "player": player, "bucket": bucket, "n": a["n"],
            "lev_involve": (a["lev"] / a["n"]) / (a["team_lev"] / a["team_n"]),
            "adv_involve": (a["adv"] / a["n"]) / (a["team_adv"] / a["team_n"]),
            "lev_pass_pct": ratio(a["pass_wl_ok"], a["pass_wl"], a["pass_ok"], a["pass_n"]),
            "adv_pass_pct": ratio(a["pass_wa_ok"], a["pass_wa"], a["pass_ok"], a["pass_n"]),
            "lev_duel_pct": ratio(a["duel_wl_ok"], a["duel_wl"], a["duel_ok"], a["duel_n"], 40),
            "adv_duel_pct": ratio(a["duel_wa_ok"], a["duel_wa"], a["duel_ok"], a["duel_n"], 40),
        })
    return pd.DataFrame(rows).set_index(["player", "bucket"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--split-half", action="store_true",
                    help="CAN we measure it? A season's odd matches against "
                         "its even ones. If an index will not agree with "
                         "itself inside one season, its failure to repeat "
                         "across two says nothing about football.")
    args = ap.parse_args()
    if not LEV.exists():
        print("no leverage table — run scripts/build_leverage.py first")
        return 1
    cfg = json.loads(LEV.read_text(encoding="utf-8"))
    seasons = seasons_on_disk(args.league)
    if len(seasons) < 2:
        print(f"need two stamped seasons, found {seasons}")
        return 1

    tables, pairs = {}, []
    if args.split_half:
        for s in seasons:
            print(f"  {s} odd/even ...", flush=True)
            odd = season_table(args.league, s, cfg, "odd", 300)
            even = season_table(args.league, s, cfg, "even", 300)
            print(f"     {len(odd)} / {len(even)} player-roles with 300+ events")
            tables[s] = even
            pairs.append((f"{s} odd->even", odd, even))
    else:
        for s in seasons:
            print(f"  {s} ...", flush=True)
            tables[s] = season_table(args.league, s, cfg)
            print(f"     {len(tables[s])} player-roles with {MIN_EVENTS}+ events")
        pairs = [(f"{a}->{b}", tables[a], tables[b])
                 for a, b in zip(seasons, seasons[1:])]

    print("\nspread across players (is there anything to rank?)")
    last = tables[seasons[-1]]
    print(f"{'index':<14}{'mean':>8}{'sd':>8}{'p10':>8}{'p90':>8}")
    for k in INDICES:
        c = last[k].dropna()
        print(f"{k:<14}{c.mean():>8.3f}{c.std():>8.3f}"
              f"{c.quantile(.1):>8.3f}{c.quantile(.9):>8.3f}")

    results = []
    for label, a, b in pairs:
        shared = a.index.intersection(b.index)
        for bucket in BUCKET_ORDER:
            keys = [k for k in shared if k[1] == bucket]
            if len(keys) < MIN_PLAYERS:
                continue
            for k in INDICES:
                x, y = a.loc[keys, k], b.loc[keys, k]
                okm = x.notna() & y.notna()
                if int(okm.sum()) < MIN_PLAYERS:
                    continue
                rho = x[okm].rank().corr(y[okm].rank())
                if pd.isna(rho):
                    continue
                results.append({"pair": label, "bucket": bucket,
                                "index": k, "n": int(okm.sum()),
                                "rho": round(float(rho), 3)})

    print("\nCAN WE MEASURE IT? odd matches against even, within bucket"
          if args.split_half else
          "\nDOES IT REPEAT? season against next season, within bucket")
    print(f"{'':<14}", end="")
    for b in BUCKET_ORDER:
        print(f"{b:>7}", end="")
    print("\n" + "-" * (14 + 7 * len(BUCKET_ORDER)))
    for k in INDICES:
        print(f"{k:<14}", end="")
        for b in BUCKET_ORDER:
            hit = [r for r in results if r["index"] == k and r["bucket"] == b]
            print(f"{hit[0]['rho']:>7.2f}" if hit else f"{'--':>7}", end="")
        print()

    good = [r for r in results if r["rho"] >= 0.4]
    print(f"\nmeasured: {len(results)}   moderate or better (>=0.40): {len(good)}")
    if good:
        print("survivors:")
        for r in sorted(good, key=lambda r: -r["rho"]):
            print(f"   {r['index']:<14}{r['bucket']:<6}{r['rho']:>6.2f}  n={r['n']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"league": args.league, "seasons": seasons,
                               "min_events": MIN_EVENTS, "results": results},
                              indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
