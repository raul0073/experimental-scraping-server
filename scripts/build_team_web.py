"""Build the team layer: style and quality, per club, per season, per spell.

Measured per match (services.mental.team_metrics), opponent-adjusted once
across each season's whole league, then aggregated into every cut the site
needs. The cuts are not nested — a manager's spell can span three seasons
and a season can span three managers — which is exactly why the match is the
base grain and everything above it is a groupby.

    club                  the league table: one row per club, all we have
    club x season         a club in one year
    spell                 a club under one manager, for the team page and
                          for the predictor, which cares what this side is
                          doing now rather than what the club averaged

Gated by SPLIT-HALF — odd matches against even, within the cut. The
cross-season test that gated the player layer cannot work here: a manager's
spell has no next season, and only seventeen clubs appear in all three. The
split-half test is a fair substitute and we measured how fair: across the
406 metric/bucket pairs that had both, it correlates 0.73 with the
cross-season result, and a metric clearing 0.45 on it goes on to repeat 91%
of the time. A team also has 4,000 events per half-season to measure with.

Writes data/web/team/{league}/... and the copy the site serves.

Usage: .venv/Scripts/python.exe scripts/build_team_web.py [--gate]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict

import numpy as np
import pandas as pd

from services.mental.role_bank import RAW, seasons_on_disk
from services.mental.spells import build as build_spells
from services.mental.team_metrics import ADJUST, M, match_rows, opponent_adjust
from services.mental.zones import (
    ALL_KEYS as Z_KEYS, SHARE_KEYS, grid_meta, match_zones,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "team"
PUB = ROOT / "web" / "public" / "data" / "team"

# The board shows leagues[0], so this order decides which league the ratings
# page opens on. England first because that is the league with four seasons
# of events behind it; the rest follow in the order the site uses elsewhere.
LEAGUE_ORDER = ["eng-premier-league", "esp-la-liga", "ita-serie-a",
                "ger-bundesliga", "fra-ligue-1"]


def merge_index(root: Path, mine: list) -> list:
    """This league's entry folded into whatever the index already lists.

    Each run builds ONE league but the index describes ALL of them, so it
    has to be read before it is written or the other four disappear."""
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
# A share of the matches available in the cut, not a flat count: ten is a
# sensible bar for a finished season and impossible five rounds into a new
# one. The floor stops a club that played once from being ranked at all.
MIN_SHARE = 0.25
MIN_FLOOR = 3
KEYS = list(M)


# Only genuinely meaningless suffixes. "City" and "Utd" are NOT noise: they
# are the entire difference between the two Manchester clubs, and stripping
# them handed Manchester City's badge to Manchester United.
_CREST_NOISE = ("fc", "afc", "cf")


def _tokens(name: str) -> list:
    return [w for w in "".join(c if c.isalnum() else " " for c in name.lower()).split()
            if w not in _CREST_NOISE]


def crest_map(league: str, teams) -> dict:
    """team name -> the badge file we hold for it.

    `teams` IS AN ARGUMENT, not a module global. It used to be read from
    T_TEAMS, which only this file's main() assigned — so build_mental_web
    imported this function, called it, and got an empty dict with no error
    and no clue why every player row was missing its badge.

    The two naming schemes disagree: WhoScored says "Man Utd" where the badge
    is "Manchester Utd.png", "Leeds" against "Leeds United.png". Matched on
    tokens instead of aliases — every word of the shorter name has to be a
    prefix of a word in the longer one. "Man Utd" reaches "Manchester Utd"
    because man/manchester and utd/utd both hold; it cannot reach "Manchester
    City" because utd matches nothing there. A club with no badge gets no
    entry and the page shows none, never a broken image."""
    # Both spellings of the folder. Nottingham.png was sitting on its own in
    # "ENG-Premier_League" while every other badge was in "ENG-Premier
    # League", so Forest showed no crest anywhere on the site and the reason
    # was a space.
    root = ROOT / "web" / "public" / "logos"
    files = {}
    for name in (league, league.replace(" ", "_")):
        folder = root / name
        if folder.is_dir():
            for f in folder.glob("*.png"):
                files.setdefault(f.stem, f"/logos/{name}/{f.name}")
    if not files:
        return {}

    def fits(short: list, long: list) -> bool:
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
    for team in set(teams):
        if team in files:
            out[team] = files[team]
            continue
        tt = _tokens(team)
        hits = [
            url for stem, url in files.items()
            if fits(tt, _tokens(stem)) or fits(_tokens(stem), tt)
        ]
        # Ambiguity is a reason to show nothing, not to guess.
        if len(hits) == 1:
            out[team] = hits[0]
    missing = sorted(set(teams) - set(out))
    if missing:
        print(f"no badge for: {', '.join(missing)}")
    return out


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def league_key(league: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in league.lower()).strip("-")


def season_label(s: str) -> str:
    return f"20{s[:2]}/{s[2:]}"


def per_match(league: str, seasons: list) -> pd.DataFrame:
    """Every team-match, opponent-adjusted within its own season."""
    frames = []
    for season in seasons:
        df = pd.read_parquet(RAW / league / f"{season}_stamped.parquet")
        rows = []
        for gid, m in df.groupby("game_id", sort=False):
            zones = {z["team"]: z for z in match_zones(m)}
            for i, r in enumerate(match_rows(m)):
                r["game_id"] = int(gid)
                r["season"] = season
                r["home"] = i == 0
                # By the KEY LIST, not by guessing prefixes: a filter on
                # ("z_", "zs_", "zc_") silently dropped every zo_ and zoc_
                # column, so the chance-origin maps arrived empty.
                z = zones.get(r["team"], {})
                r.update({k: z[k] for k in Z_KEYS if k in z})
                rows.append(r)
        T = pd.DataFrame(rows)
        # Fitted per season: each is its own league, and a 23/24 baseline
        # says nothing about who Sunderland faced in 25/26.
        frames.append(opponent_adjust(T))
        print(f"  {season}: {len(T)} team-matches", flush=True)
    return pd.concat(frames, ignore_index=True)


def label_spells(T: pd.DataFrame, league: str, seasons: list) -> pd.DataFrame:
    spells = build_spells(league, seasons)
    by_game = {}
    for sp in spells:
        for g in sp.games:
            by_game[(sp.team, g)] = sp
    T = T.copy()
    T["spell"] = [by_game[(t, g)].key if (t, g) in by_game else None
                  for t, g in zip(T["team"], T["game_id"])]
    T["manager"] = [by_game[(t, g)].manager if (t, g) in by_game else None
                    for t, g in zip(T["team"], T["game_id"])]
    return T


def aggregate(T: pd.DataFrame, by: list, min_matches: int = MIN_FLOOR) -> pd.DataFrame:
    """Mean of the per-match values. Adjusted columns are already a team
    term plus the league mean, so averaging them keeps that meaning."""
    cols = (KEYS + [k for k in Z_KEYS if k in T.columns]
            + [f"{k}_adj" for k in ADJUST if f"{k}_adj" in T.columns])
    g = T.groupby(by, dropna=True)
    out = g[cols].mean(numeric_only=True)
    out["matches"] = g.size()
    return out[out["matches"] >= min_matches].reset_index()


def predicts_points(T: pd.DataFrame) -> dict:
    """Does the metric, measured on half a season, predict POINTS in the
    other half?

    Reliability is not enough for a layer that will feed a predictor: a
    metric can reproduce itself perfectly and still say nothing about
    results. This is the out-of-sample version — measured on one half of a
    team's season, scored against what it actually won in the other.

    It is what caught the defensive-volume trap. Tackles, interceptions and
    recoveries all repeat beautifully and all predict FEWER points, because a
    side doing a lot of them is a side without the ball. At player level
    tackle volume is a virtue; at team level it is a symptom."""
    # Only team-seasons long enough to halve. A part-played season gives two
    # matches a side, and twenty rows of two-match noise dragged this test
    # from -0.53 to -0.18 on conceding big chances — turning a real signal
    # into something the gate then threw away.
    T = T.sort_values(["season", "game_id"]).copy()
    played = T.groupby(["team", "season"])["game_id"].transform("size")
    T = T[played >= 20]
    # 🐛 AND IF NOTHING SURVIVES THAT FILTER, SAY SO RATHER THAN CRASHING.
    # A league whose only events are the season in progress has ~7 matches a
    # side, so the frame empties, the groupby yields no groups, and
    # pd.concat dies with "No objects to concatenate" — which took down the
    # whole team-web build for the four leagues that have no event history.
    # This function is a DIAGNOSTIC: "do these metrics predict points". Not
    # being answerable yet is a normal state early in a season, and must not
    # stop the rankings being published.
    if T.empty:
        return {}
    T["half"] = T.groupby(["team", "season"]).cumcount() % 2
    raw = [c for c in T.columns if not c.endswith("_adj")]
    a = pd.concat([opponent_adjust(g) for _s, g in T[T["half"] == 0][raw].groupby("season")],
                  ignore_index=True).groupby(["team", "season"]).mean(numeric_only=True)
    b = T[T["half"] == 1].groupby(["team", "season"])["pts"].mean()
    j = a.join(b, rsuffix="_out")
    out = {}
    for k in KEYS:
        col = f"{k}_adj" if f"{k}_adj" in j.columns else k
        if col not in j.columns:
            continue
        r = j[col].corr(j["pts"], method="spearman")
        if not pd.isna(r):
            out[k] = round(float(r), 3)
    return out


def split_half_gate(T: pd.DataFrame, by: list) -> list:
    """Odd matches against even, within each cut.

    The opponent adjustment is RE-FITTED inside each half. Fitted once over
    the whole season it produces a single number per team, constant across
    that team's matches — so both halves inherit the identical value and
    every metric scores exactly 1.00. That is arithmetic, not reliability.
    Refitting per half makes the two estimates independent, which is the
    only version of this test that means anything."""
    T = T.sort_values(["season", "game_id"]).copy()
    T["half"] = T.groupby(by).cumcount() % 2
    raw = [c for c in T.columns if not c.endswith("_adj")]
    halves = []
    for h in (0, 1):
        sub = T[T["half"] == h][raw]
        parts = [opponent_adjust(g) for _s, g in sub.groupby("season")]
        halves.append(aggregate(pd.concat(parts, ignore_index=True), by).set_index(by))
    a, b = halves
    res = []
    shared = a.index.intersection(b.index)
    for key in KEYS:
        col = f"{key}_adj" if f"{key}_adj" in a.columns else key
        if col not in a.columns or col not in b.columns:
            continue
        x, y = a.loc[shared, col], b.loc[shared, col]
        ok = x.notna() & y.notna()
        if int(ok.sum()) < 12:
            continue
        rho = x[ok].rank().corr(y[ok].rank())
        if pd.isna(rho):
            continue
        res.append({"metric": key, "kind": M[key]["kind"], "n": int(ok.sum()),
                    "rho": round(float(rho), 3)})
    return sorted(res, key=lambda r: -r["rho"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ENG-Premier League")
    ap.add_argument("--gate", action="store_true")
    args = ap.parse_args()
    on_disk = seasons_on_disk(args.league)
    seasons = list(on_disk)          # the current season included
    print(f"seasons: {', '.join(seasons)}")

    # Who is in the league RIGHT NOW. Taken from the latest season on disk
    # including a part-played one, because five rounds is more than enough to
    # know who was promoted. Without this the all-seasons table lists 25
    # clubs, five of which are in the Championship.
    current = sorted(pd.read_parquet(
        RAW / args.league / f"{on_disk[-1]}.parquet",
        columns=["team"])["team"].dropna().unique().tolist())
    print(f"currently in the league ({on_disk[-1]}): {len(current)} clubs")

    T = label_spells(per_match(args.league, seasons), args.league, seasons)
    print(f"total team-matches: {len(T):,}   spells: {T['spell'].nunique()}")

    if args.gate:
        for by, name in ((["team"], "club, all seasons"),
                         (["spell"], "manager spell")):
            res = split_half_gate(T, by)
            print(f"\nDOES IT HOLD UP? split-half within {name} "
                  f"({len(aggregate(T, by))} units)")
            print(f"{'metric':<22}{'kind':<9}{'n':>4}{'rho':>7}   verdict")
            print("-" * 62)
            for r in res:
                v = ("strong" if r["rho"] >= 0.6 else
                     "moderate" if r["rho"] >= 0.4 else
                     "weak" if r["rho"] >= 0.25 else "NOISE")
                print(f"{r['metric']:<22}{r['kind']:<9}{r['n']:>4}"
                      f"{r['rho']:>7.2f}   {v}")
            good = [r for r in res if r["rho"] >= 0.4]
            print(f"   {len(good)} of {len(res)} at 0.40+")
        return 0

    lk = league_key(args.league)
    # Each cut gets its own bar, because "enough football" means different
    # things. A season is judged against ITS OWN length — a quarter of 38 in a
    # finished season, a quarter of 4 five rounds into a new one — while a
    # spell is its own period and can only carry a flat floor, or Arteta's
    # 114 matches would set a bar no caretaker could clear.
    per_season = []
    for season, g in T.groupby("season"):
        played = g.groupby("team").size().max()
        per_season.append(aggregate(g, ["team", "season"],
                                    max(MIN_FLOOR, int(played * MIN_SHARE))))
    cuts = {
        "club": aggregate(T, ["team"], 10),
        "club_season": pd.concat(per_season, ignore_index=True),
        # 3, not 10: a manager appointed last month has few matches BY
        # DEFINITION, and dropping him means the page cannot name who is in
        # charge. Kept and flagged `short` instead, so the page can show him
        # while saying his numbers are not yet worth much.
        "spell": aggregate(T, ["spell", "team", "manager"], 3),
    }

    # WHEN each spell ran. Without it the client has no way to order them:
    # pandas groups alphabetically, so "the last row" was De Zerbi rather
    # than Hurzeler, and game ids cannot rescue it because they are not
    # chronological inside a season.
    when = {sp.key: (sp.start[:10], sp.end[:10])
            for sp in build_spells(args.league, seasons)}
    cuts["spell"]["start"] = cuts["spell"]["spell"].map(
        lambda k: when.get(k, ("", ""))[0])
    cuts["spell"]["end"] = cuts["spell"]["spell"].map(
        lambda k: when.get(k, ("", ""))[1])
    cuts["spell"]["short"] = cuts["spell"]["matches"] < 10
    cuts["spell"] = cuts["spell"].sort_values(["team", "start"])
    gate = {r["metric"]: r for r in split_half_gate(T, ["team", "season"])}
    pred = predicts_points(T)
    for k, v in pred.items():
        gate.setdefault(k, {"metric": k, "kind": M[k]["kind"]})["predicts"] = v
    # Dominance per cell is meaningless against a flat 50: your attacking
    # centre is the opponent's defensive centre, where THEY have the ball
    # while playing out, so every side sits under 50 there — Liverpool at
    # 34.9. Each cell is therefore percentiled across the pool, so 50 means
    # "a typical side here" and the map reads as more or less than normal.
    for frame in cuts.values():
        for k in SHARE_KEYS:
            if k in frame.columns:
                frame[f"{k}_n"] = (frame[k].rank(pct=True) * 100).round(1)

    all_teams = sorted(T["team"].dropna().unique())
    meta = {
        "league": args.league,
        "crests": crest_map(args.league, all_teams),
        "grid": grid_meta(),
        "leagues": [{"key": lk, "label": args.league}],
        "seasons": seasons,
        "season_labels": {s: season_label(s) for s in seasons},
        "min_share": MIN_SHARE,
        "current_season": on_disk[-1],
        "current_teams": current,
        "metrics": [{"key": k, **M[k]} for k in KEYS],
        "reliability": gate,
    }
    spell_of = {}
    for sp in build_spells(args.league, seasons):
        for g in sp.games:
            spell_of[(sp.team, g)] = sp.key
    # The smooth 30x20 density maps are NO LONGER BUILT. They were superseded
    # by the fifteen-cell zone grid — a smooth blur is a pretty picture with
    # no number a reader can act on, and the cells carry a measure — and
    # nothing has fetched them since. They cost a pass over every event in
    # four seasons and 472 KB in the repo. `heat_maps`, `density` and
    # `smooth` are left in services/mental/zones.py if the visuals pass wants
    # a blurred layer under the cells later.
    for root in (OUT, PUB):
        folder = root / lk
        folder.mkdir(parents=True, exist_ok=True)
        # 🐛 THIS USED TO WRITE {"leagues": meta["leagues"]} — i.e. ONLY the
        # league just built — so every per-league run deleted all the others
        # from the index. The board reads leagues[0], so running this for
        # La Liga made the ratings page show La Liga INSTEAD OF the Premier
        # League; and the daily run's per-league loop left the index set to
        # whichever league happened to be last. Harmless while only one
        # league was ever built, silently destructive the moment there were
        # five. Merge, and keep a deterministic order.
        (root / "index.json").write_text(
            json.dumps({"leagues": merge_index(root, meta["leagues"])},
                       ensure_ascii=False),
            encoding="utf-8")
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False),
                                          encoding="utf-8")
        for name, frame in cuts.items():
            (folder / f"{name}.json").write_text(
                frame.round(3).to_json(orient="records"), encoding="utf-8")

    print()
    for name, frame in cuts.items():
        kb = (OUT / lk / f"{name}.json").stat().st_size // 1024
        print(f"   {name + '.json':<16}{len(frame):>4} rows{kb:>6} KB")
    print(f"-> {OUT / lk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
