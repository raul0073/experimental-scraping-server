"""Build the Mental page's data: every player's metric bank, by role.

The website is a static export, so the CONFIG runs in the browser: this
exports each player's percentile on every metric (within his position
bucket), and the page multiplies those by whatever weights the reader sets.
No server, instant feedback.

A player appears once per ROLE, not once per season. Rice is in the
central-midfield table on his 2,004 central-midfield minutes and in the
defensive-midfield table on his 1,195 defensive-midfield minutes, each row
carrying the share of his season spent there. 85 Premier League players
qualified in more than one bucket in 25/26, so a single row per player would
have described the wrong footballer 85 times.

Two kinds of view are written:

    a season   that season's events alone
    total      every season pooled — the RAW EVENTS of all of them summed,
               not an average of season ranks, so a player with three
               seasons behind him is ranked on three seasons of evidence

Also exports, per metric per bucket, how well that metric REPEATS (from
build_reliability). The page uses it to stop anyone weighting a number that
cannot reproduce itself.

Writes data/web/mental.json and the copy the site serves.

Usage: .venv/Scripts/python.exe scripts/build_mental_web.py
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.mental.event_metrics import GROUP_LABEL, METRICS
from services.mental.positions import (
    BUCKET_DESC, BUCKET_LABEL, BUCKET_ORDER, BUCKET_SHORT, SIDE_LABEL,
)
from services.mental.role_bank import Store, banks, fold_season, seasons_on_disk
from build_team_web import crest_map                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "mental"
PUB = ROOT / "web" / "public" / "data" / "mental"
# A share of the club's available minutes IN THE ROLE, rather than a flat
# count. 450 minutes means "a fringe player" across three seasons and "more
# than anybody has played" five rounds into a new one, so one number cannot
# serve both. 13% is roughly where the old 450-minute bar sat over a full
# season, which keeps the qualifying pool about where it was.
MIN_SHARE = 13.0


# The board opens on leagues[0], so this order decides the default. England
# first because it is the league with the deepest event history behind it.
LEAGUE_ORDER = ["eng-premier-league", "esp-la-liga", "ita-serie-a",
                "ger-bundesliga", "fra-ligue-1"]


def merge_index(root: Path, mine: list) -> list:
    """This league folded into whatever the index already lists.

    Each run builds ONE league but the index describes all of them, so it
    must be read before it is written or the others disappear."""
    seen = {}
    try:
        for e in json.loads(
                (root / "index.json").read_text(encoding="utf-8"))["leagues"]:
            seen[e["key"]] = e
    except Exception:
        pass                      # no index yet, or unreadable — start fresh
    for e in mine:
        seen[e["key"]] = e        # this run's entry wins
    return sorted(seen.values(),
                  key=lambda e: (LEAGUE_ORDER.index(e["key"])
                                 if e["key"] in LEAGUE_ORDER else 99,
                                 e["key"]))


def league_key(league: str) -> str:
    """'ENG-Premier League' -> 'eng-premier-league'."""
    return "".join(c if c.isalnum() else "-" for c in league.lower()).strip("-")


def columnar(rows: list, keys: list) -> dict:
    """The same rows, stored down the columns instead of across the players.

    Written per player, every row repeats all 64 metric names four times over.
    That was 2.4 MB of key names in the pooled view alone — a fifth of the
    file — for text the reader never sees. Down the columns each name is
    written once, in the index, and the values line up against it by position.
    10.9 MB becomes 3.3 MB, and 1.4 MB gzipped becomes 0.9.

    Missing values stay null rather than being dropped, because position IS
    the key here: a hole has to keep its place in the line."""
    out = {f: [r.get(f) for r in rows]
           for f in ("n", "t", "tn", "p", "s", "m", "sh", "rs", "gone")}
    for blk in ("v", "q", "va", "qa"):
        out[blk] = [[r[blk].get(k) for k in keys] for r in rows]
    return out


def season_label(season: str) -> str:
    """'2425' -> '2024/25'."""
    return f"20{season[:2]}/{season[2:]}"


def percentiles(bank: pd.DataFrame) -> pd.DataFrame:
    """Percentile within the bucket, with inverted metrics flipped so 100 is
    always the good end. The bucket IS the comparison pool — that is the
    whole point of bucketing — so no further grouping happens here."""
    out = bank.copy()
    for key, meta in METRICS.items():
        if key not in bank.columns:
            continue
        pct = bank[key].rank(pct=True, na_option="keep") * 100
        if meta["invert"]:
            pct = 100 - pct
        out[f"p_{key}"] = pct.round(0)
    return out


def rows_for(store: Store, now: dict | None = None,
             in_league: set | None = None) -> list:
    """One row per (player, bucket) that cleared the minutes bar in the role.

    `now` maps a player to the club he last turned out for across ALL the
    data. A 23/24 row is about the club he played that season for, but a
    reader looking him up wants to know where he is now, and over three
    seasons those are often different clubs."""
    raw = banks(store, 0, min_share=MIN_SHARE)
    adj = banks(store, 0, adjust=True, min_share=MIN_SHARE)
    rows = []
    for bucket in BUCKET_ORDER:
        if bucket not in raw:
            continue
        b, a = percentiles(raw[bucket]), percentiles(adj[bucket])
        for name, r in b.iterrows():
            ar = a.loc[name]
            current = (now or {}).get(name)
            # STILL IN THE LEAGUE? The all-seasons view pools four seasons,
            # so it lists everyone who has ever cleared the minutes bar —
            # including players who left. A ranking of "who is best in the
            # Premier League" topped by men no longer in it is not a ranking
            # of anything, so each row says whether he has appeared this
            # season and the page can filter on it.
            row = {"n": name, "t": r["team"], "p": bucket, "s": r["side"],
                   **({"tn": current} if current and current != r["team"] else {}),
                   **({"gone": 1} if in_league is not None
                      and name not in in_league else {}),
                   "sh": int(r["share"]), "m": int(r["minutes"]),
                   "rs": round(float(r["role_share"]), 1),
                   "v": {}, "q": {}, "va": {}, "qa": {}}
            for key in METRICS:
                for src, vkey, qkey in ((r, "v", "q"), (ar, "va", "qa")):
                    val, pct = src.get(key), src.get(f"p_{key}")
                    if val is not None and not pd.isna(val):
                        row[vkey][key] = round(float(val), 2)
                    if pct is not None and not pd.isna(pct):
                        row[qkey][key] = int(pct)
            rows.append(row)
    return rows


def reliability() -> dict:
    """metric -> bucket -> {rho, n}, for both tests. Missing is not zero: a
    bucket with too few players is unmeasured, which the page must say rather
    than imply the metric failed."""
    path = ROOT / "data" / "reports" / "metric_reliability.json"
    if not path.exists():
        return {"repeat": {}, "self": {}}
    d = json.loads(path.read_text(encoding="utf-8"))
    return {"repeat": d.get("repeat", {}), "self": d.get("self", {})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    args = ap.parse_args()
    league = args.league
    seasons = seasons_on_disk(league)
    if not seasons:
        print("no stamped seasons — run scripts/stamp_event_state.py first")
        return 1

    total = Store()
    per_season = {}
    for season in seasons:
        store = Store()
        fold_season(league, season, store, total)
        per_season[season] = store
        print(f"folded {season}: {store.matches} matches", flush=True)

    rel = reliability()
    payload = {
        "league": league,
        "seasons": seasons,
        "min_share": MIN_SHARE,
        "period_minutes": {},
        "views": [],           # filled in below, once we know which have rows
        "buckets": [{"key": b, "label": BUCKET_LABEL[b],
                     "short": BUCKET_SHORT[b], "desc": BUCKET_DESC[b]}
                    for b in BUCKET_ORDER],
        "sides": SIDE_LABEL,
        "metric_groups": [{"key": k, "label": v} for k, v in GROUP_LABEL.items()],
        "metrics": [
            {"key": k, "label": m["label"], "unit": m["unit"],
             "group": m["group"], "invert": m["invert"], "desc": m["desc"]}
            for k, m in METRICS.items()
        ],
        "reliability": rel["repeat"],
        "self_reliability": rel["self"],
        "players": {},
    }

    views = {s: per_season[s] for s in seasons}
    if len(seasons) > 1:
        views["total"] = total
    now_club = {n: club for n, (_gid, club) in total.last_club.items()}

    # Everyone who has actually turned out in the season in progress. Taken
    # from the raw bank with NO minutes bar — a squad player with 40 minutes
    # is still in the league, and holding him to the same share threshold the
    # rankings use would wrongly mark him departed.
    current_season = seasons[-1] if seasons else None
    in_league = None
    if current_season and current_season in per_season:
        # player_minutes counts every appearance, however short — that is the
        # point: presence, not eligibility for the ranking.
        in_league = {n for n, mins in
                     per_season[current_season].player_minutes.items()
                     if mins > 0}
    if in_league:
        print(f"--   {len(in_league)} players have featured in {current_season}")

    for key, store in views.items():
        rows = rows_for(store, now_club, in_league)
        if not rows:
            # a season only a few rounds old has nobody over the minutes bar.
            # It still counts toward the pooled total and toward knowing which
            # club a player is at now, but offering an empty season in the
            # dropdown would just look broken.
            print(f"--   {key:<6}    0 rows   (part-played; kept out of the views)")
            continue
        payload["players"][key] = rows
        payload["period_minutes"][key] = round(store.period_minutes())
        by_bucket = {}
        for r in rows:
            by_bucket[r["p"]] = by_bucket.get(r["p"], 0) + 1
        counts = " ".join(f"{b}{by_bucket.get(b, 0)}" for b in BUCKET_ORDER)
        print(f"OK   {key:<6}{len(rows):>5} rows   {counts}")

    payload["views"] = (
        [{"key": "total", "label": "All seasons"}]
        if len(payload["players"]) > 1 else []
    ) + [{"key": s, "label": season_label(s)}
         for s in reversed(seasons) if s in payload["players"]]

    # Split into an index plus one file per view, so the page fetches the
    # ~0.3 MB it is showing rather than every season of every league at once.
    # Five leagues then costs five times the DISK and nothing extra on the
    # wire, which is the whole point.
    keys = [m["key"] for m in payload["metrics"]]
    lk = league_key(league)
    index = {k: payload[k] for k in
             ("league", "seasons", "min_share", "period_minutes", "views", "buckets", "sides",
              "metric_groups", "metrics", "reliability", "self_reliability")}
    index["metric_keys"] = keys
    # CLUB BADGES. Four hundred surnames is a wall of text; a badge is
    # recognised before a name is read. Reused from the team build rather
    # than matched again — the two naming schemes disagree ("Man Utd" against
    # "Manchester Utd.png") and a second matcher is a second thing to drift.
    index["crests"] = crest_map(
        league, {r["t"] for rows in payload["players"].values() for r in rows})
    index["leagues"] = [{"key": lk, "label": league}]

    for root in (OUT, PUB):
        folder = root / lk
        folder.mkdir(parents=True, exist_ok=True)
        # 🐛 THIS USED TO WRITE ONLY THE LEAGUE JUST BUILT, deleting the rest
        # — the third time that exact bug has appeared, after the ratings
        # index and elo_params.json. The board reads leagues[0], so building
        # La Liga would have made the PLAYERS page show La Liga instead of
        # the Premier League. Merge, ordered, so the default is stable.
        (root / "index.json").write_text(
            json.dumps({"leagues": merge_index(root, index["leagues"])},
                       ensure_ascii=False),
            encoding="utf-8")
        (folder / "meta.json").write_text(
            json.dumps(index, ensure_ascii=False), encoding="utf-8")
        for key, rows in payload["players"].items():
            (folder / f"{key}.json").write_text(
                json.dumps(columnar(rows, keys), ensure_ascii=False),
                encoding="utf-8")

    meta_kb = (OUT / lk / "meta.json").stat().st_size // 1024
    print()
    print(f"-> {OUT / lk}")
    print(f"   meta.json  {meta_kb:>5} KB   (metrics, buckets, the whole gate)")
    for key in payload["players"]:
        kb = (OUT / lk / f"{key}.json").stat().st_size // 1024
        print(f"   {key + '.json':<11}{kb:>5} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
