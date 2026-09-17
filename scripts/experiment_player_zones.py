"""THE GATE: do zones built from players beat zones built from shots?

The shipping zones infer territory from ~25 shots a match and feed the
predictor through four fitted channels. This builds the alternative the
architecture argues for — a zone IS the players who occupy it — and tests
it the only way that counts: fit on one season, freeze, judge on a season
it has never seen.

    zone strength(team, channel) = SUM over players of
        (his share of the team's actions in that channel)
        x (his quality, measured from everything he does)

Five channels a side, mirrored for the matchup: my right wing attacks their
left, so the feature is my attacking strength in a channel minus their
defensive strength in the facing one.

Everything is WALK-FORWARD: at each match, teams are described only by
matches already played, exactly as the shipping zones are. Nothing about a
fixture informs its own prediction.

Usage: .venv/Scripts/python.exe scripts/experiment_player_zones.py
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import outcome_probs, unified_probs
from services.understat.understat_service import UnderstatService
from services.zones.zones_engine import CHANNELS as SHOT_CHANNELS
from services.zones.zones_engine import ZonesEngine, channel_feats
from scripts.build_territory import CHANNELS, cell_of
from scripts.experiment_persistence import player_minutes

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "whoscored"
LEAGUE = "ENG-Premier League"
FIT, EVAL = "2425", "2526"
MIN_TEAM_MATCHES = 8          # same depth gate the shipping zones use
CHAN_KEYS = [c for c, *_ in CHANNELS]          # RW RH C LH LW
MIRROR = {"RW": "LW", "RH": "LH", "C": "C", "LH": "RH", "LW": "RW"}
CONTROLLED = ("Pass", "TakeOn", "Goal", "SavedShot", "MissedShots", "ShotOnPost")

ATT_EVENTS = ("Goal", "SavedShot", "MissedShots", "ShotOnPost")
DEF_EVENTS = ("Tackle", "Interception", "Clearance", "BallRecovery")


class TeamState:
    """Everything known about a club from the matches already played."""

    def __init__(self) -> None:
        self.matches = 0
        self.cell_actions: dict = defaultdict(lambda: defaultdict(float))  # player -> cell
        self.player_minutes: dict = defaultdict(float)
        self.att_quality: dict = defaultdict(float)   # danger produced
        self.def_quality: dict = defaultdict(float)   # ball won back
        self.giveaways: dict = defaultdict(float)

    def zone(self, third: str, quality: str) -> dict:
        """Strength per channel: who occupies it, times how good they are."""
        totals = defaultdict(float)
        occupancy = defaultdict(float)
        for player, cells in self.cell_actions.items():
            for cell, n in cells.items():
                if cell[0] != third:
                    continue
                occupancy[cell[1:]] += n
        out = {}
        for chan in CHAN_KEYS:
            total = occupancy.get(chan, 0.0)
            if total <= 0:
                out[chan] = 0.0
                continue
            strength = 0.0
            for player, cells in self.cell_actions.items():
                n = cells.get(f"{third}{chan}", 0.0)
                if n <= 0:
                    continue
                mins = self.player_minutes.get(player, 0.0)
                if mins < 90:
                    continue
                if quality == "att":
                    q = self.att_quality[player] / mins * 90
                else:
                    q = (self.def_quality[player] - 0.5 * self.giveaways[player]) / mins * 90
                strength += (n / total) * q
            out[chan] = strength
        return out


def match_features(home: TeamState, away: TeamState) -> tuple:
    """My attacking strength in a channel minus their defensive strength in
    the facing one — mirrored, because my right wing meets their left."""
    ha, ad = home.zone("A", "att"), away.zone("D", "def")
    aa, hd = away.zone("A", "att"), home.zone("D", "def")
    fh = [ha[c] - ad[MIRROR[c]] for c in CHAN_KEYS]
    fa = [aa[c] - hd[MIRROR[c]] for c in CHAN_KEYS]
    return fh, fa


def update(state: TeamState, rows: pd.DataFrame, minutes: dict) -> None:
    state.matches += 1
    for player, played in minutes.items():
        state.player_minutes[player] += played
    for row in rows.itertuples(index=False):
        p = row.player
        if not isinstance(p, str):
            continue
        if row.type in CONTROLLED:
            cell = cell_of(row.x, row.y)
            if cell:
                state.cell_actions[p][cell] += 1
        q = row.qualifiers
        names = set()
        try:
            names = {x["type"]["displayName"] for x in q}
        except Exception:
            pass
        if row.type == "Pass" and row.outcome_type == "Successful":
            if "KeyPass" in names:
                state.att_quality[p] += 1.0
            if "BigChanceCreated" in names:
                state.att_quality[p] += 1.5
        elif row.type in ATT_EVENTS:
            state.att_quality[p] += 1.0
        elif row.type == "TakeOn" and row.outcome_type == "Successful":
            state.att_quality[p] += 0.5
        if row.type in DEF_EVENTS and row.outcome_type == "Successful":
            state.def_quality[p] += 1.0
        elif row.type == "Aerial" and row.outcome_type == "Successful":
            state.def_quality[p] += 0.5
        if row.type == "Dispossessed" or (
                row.type == "BallTouch" and row.outcome_type == "Unsuccessful"):
            state.giveaways[p] += 1.0


def collect(season: str) -> list:
    """Walk the season in order, producing one sample per fixture."""
    params = json.loads((ROOT / "data/config/model_params.json").read_text(encoding="utf-8"))
    rho, boosts = params["rho"], params["leagues"][LEAGUE]
    clf = DrawModel.load()
    fm = FormModel(LEAGUE, (["2425", season] if season != "2425" else [season]))
    us = UnderstatService.load(LEAGUE, season)
    eng = ZonesEngine(LEAGUE, season)
    zb = json.loads((ROOT / "data/config/zone_blend.json").read_text(encoding="utf-8"))

    df = pd.read_parquet(RAW / LEAGUE / f"{season}_stamped.parquet")
    order = (df.groupby("game_id")["game"].first()
             .str.slice(0, 10).sort_values())
    samples, states, zcache = [], defaultdict(TeamState), {}

    for gid in order.index:
        match = df[df["game_id"] == gid]
        date = match["game"].iloc[0][:10]
        teams = [t for t in match["team"].dropna().unique()]
        if len(teams) != 2:
            continue
        # home team is the one named first in "DATE Home-Away"
        label = match["game"].iloc[0][11:]
        home = next((t for t in teams if label.startswith(t[:6])), teams[0])
        away = teams[0] if home == teams[1] else teams[1]
        hs, as_ = states[home], states[away]

        ready = hs.matches >= MIN_TEAM_MATCHES and as_.matches >= MIN_TEAM_MATCHES
        if ready:
            um = next((m for m in us["matches"]
                       if m["date"] == date and m["home_goals"] is not None
                       and m["home_team"][:5] == home[:5]), None)
            lam = fm.lambdas(fm.ratings_before(date), um["home_team"], um["away_team"],
                             boosts["home_boost"], boosts["away_boost"]) if um else None
            if um and lam and not lam[2]:
                lam_h, lam_a, _ = lam
                roll = DrawModel.rolling_stats(fm.matches, date)
                if um["home_team"] in roll and um["away_team"] in roll:
                    ctx = DrawModel.season_context(us["matches"], date,
                                                   um["home_team"], um["away_team"])
                    p_clf = clf.predict(DrawModel.fixture_features(
                        lam_h, lam_a, rho, roll[um["home_team"]],
                        roll[um["away_team"]], ctx))
                    fh, fa = match_features(hs, as_)
                    # the shipping zones, for the same fixture
                    if date not in zcache:
                        try:
                            zcache[date] = eng.build(as_of_date=date, persist=False,
                                                     include_players=False)["teams"]
                        except Exception:
                            zcache[date] = None
                    z = zcache[date]
                    sh = sa = None
                    if z and um["home_team"] in z and um["away_team"] in z:
                        sh = channel_feats(z, um["home_team"], um["away_team"])
                        sa = channel_feats(z, um["away_team"], um["home_team"])
                    outcome = ("home" if um["home_goals"] > um["away_goals"]
                               else "away" if um["away_goals"] > um["home_goals"]
                               else "draw")
                    samples.append({
                        "lam_h": lam_h, "lam_a": lam_a, "rho": rho,
                        "p_clf": p_clf, "outcome": outcome,
                        "ph": fh, "pa": fa,
                        "sh": [sh[c] for c in SHOT_CHANNELS] if sh else None,
                        "sa": [sa[c] for c in SHOT_CHANNELS] if sa else None,
                    })
        mins = {p: m for p, (_s, _f, m) in player_minutes(match).items() if m > 0}
        for team in teams:
            sub = match[match["team"] == team]
            tmins = {p: m for p, m in mins.items() if p in set(sub["player"].dropna())}
            update(states[team], sub, tmins)
    return samples


def standardize(samples: list, key_h: str, key_a: str, stats=None):
    n = len(samples[0][key_h])
    if stats is None:
        stats = []
        for i in range(n):
            vals = [s[key_h][i] for s in samples] + [s[key_a][i] for s in samples]
            mu = float(np.mean(vals))
            sd = float(np.std(vals)) or 1.0
            stats.append((mu, sd))
    for s in samples:
        s[f"z{key_h}"] = [(s[key_h][i] - stats[i][0]) / stats[i][1] for i in range(n)]
        s[f"z{key_a}"] = [(s[key_a][i] - stats[i][0]) / stats[i][1] for i in range(n)]
    return stats


def nll(samples: list, g: list, kh: str, ka: str) -> float:
    total = 0.0
    for s in samples:
        bh = math.exp(sum(gi * zi for gi, zi in zip(g, s[kh])))
        ba = math.exp(sum(gi * zi for gi, zi in zip(g, s[ka])))
        p = unified_probs(outcome_probs(s["lam_h"] * bh, s["lam_a"] * ba, s["rho"]),
                          s["p_clf"])
        total -= math.log(max(p[s["outcome"]], 1e-9))
    return total / len(samples)


def fit(samples: list, kh: str, ka: str, k: int) -> tuple:
    g = [0.0] * k
    best = nll(samples, g, kh, ka)
    for step in (0.04, 0.02, 0.01, 0.005):
        improved = True
        while improved:
            improved = False
            for i in range(k):
                for d in (1, -1):
                    cand = list(g)
                    cand[i] = round(cand[i] + d * step, 4)
                    if abs(cand[i]) > 0.3:
                        continue
                    ll = nll(samples, cand, kh, ka)
                    if ll < best - 1e-6:
                        g, best, improved = cand, ll, True
    return g, best


def cached(season: str) -> list:
    """Collection walks every fixture and rebuilds the shipping zones per
    date, so cache it — re-analysis should cost seconds, not minutes."""
    path = ROOT / "data" / "reports" / f"_player_zone_samples_{season}.json"
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
        print(f"  loaded {len(rows)} cached samples for {season}", flush=True)
        return rows
    rows = collect(season)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def main() -> int:
    print(f"collecting {FIT} (walk-forward, zone builds) ...", flush=True)
    fit_s = cached(FIT)
    print(f"  fit samples: {len(fit_s)}", flush=True)
    print(f"collecting {EVAL} ...", flush=True)
    ev_s = cached(EVAL)
    print(f"  eval samples: {len(ev_s)}", flush=True)

    pstats = standardize(fit_s, "ph", "pa")
    standardize(ev_s, "ph", "pa", pstats)
    shot_fit = [s for s in fit_s if s["sh"]]
    shot_ev = [s for s in ev_s if s["sh"]]
    sstats = standardize(shot_fit, "sh", "sa")
    standardize(shot_ev, "sh", "sa", sstats)

    base_ev = nll(ev_s, [0] * 5, "zph", "zpa")
    gp, fit_p = fit(fit_s, "zph", "zpa", 5)
    ev_p = nll(ev_s, gp, "zph", "zpa")

    gs, fit_sh = fit(shot_fit, "zsh", "zsa", 4)
    base_shot = nll(shot_ev, [0] * 4, "zsh", "zsa")
    ev_sh = nll(shot_ev, gs, "zsh", "zsa")

    # The honest comparison for "beats what already ships": apply the LIVE
    # gammas, fitted across five leagues on 1,368 fixtures, rather than a
    # re-fit on this 270-fixture slice. The shipping model is what it is;
    # re-fitting it small and then beating it proves nothing.
    zb = json.loads((ROOT / "data/config/zone_blend.json").read_text(encoding="utf-8"))
    ship_g = [zb["gammas"][c] for c in SHOT_CHANNELS] if zb.get("gammas") else None
    ev_ship = nll(shot_ev, ship_g, "zsh", "zsa") if ship_g else None

    print(f"\n=== FROZEN EVAL on {EVAL} (EPL only, n={len(ev_s)})")
    print(f"  form only                    {base_ev:.5f}")
    print(f"  PLAYER zones (re-fit here)   {ev_p:.5f}   ({ev_p - base_ev:+.5f})")
    print(f"     gammas {dict(zip(CHAN_KEYS, gp))}")
    print(f"  shot zones (re-fit here)     {ev_sh:.5f}   ({ev_sh - base_shot:+.5f})")
    if ev_ship is not None:
        print(f"  shot zones (LIVE gammas)     {ev_ship:.5f}   "
              f"({ev_ship - base_shot:+.5f})")

    helps_p = ev_p < base_ev
    helps_ship = ev_ship is not None and ev_ship < base_shot
    if not helps_p and not helps_ship:
        verdict = ("NEITHER HELPS on this sample — 5 gammas fitted on "
                   f"{len(fit_s)} fixtures overfits; needs more data")
    elif helps_p and (ev_ship is None or (ev_p - base_ev) < (ev_ship - base_shot)):
        verdict = "PLAYER ZONES BEAT THE LIVE MODEL"
    else:
        verdict = "live shot zones still better"
    print(f"\n  VERDICT: {verdict}")

    out = ROOT / "data" / "reports" / "experiment_player_zones.json"
    out.write_text(json.dumps({
        "league": LEAGUE, "fit": FIT, "eval": EVAL,
        "n_fit": len(fit_s), "n_eval": len(ev_s),
        "player_gammas": dict(zip(CHAN_KEYS, gp)),
        "eval_form_only": round(base_ev, 5),
        "eval_player_zones": round(ev_p, 5),
        "eval_shot_base": round(base_shot, 5),
        "eval_shot_zones": round(ev_sh, 5),
        "eval_shot_live_gammas": round(ev_ship, 5) if ev_ship else None,
        "verdict": verdict,
    }, indent=2), encoding="utf-8")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
