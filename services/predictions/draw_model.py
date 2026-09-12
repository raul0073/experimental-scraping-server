from __future__ import annotations
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.predictions.form_model import DECAY, MIN_MATCHES, WINDOW, FormModel
from services.predictions.probability_service import outcome_probs
from services.understat.understat_service import UnderstatService

log = logging.getLogger(__name__)

PARAMS_PATH = Path("data/config/draw_model.json")

# feature order is the contract between training and inference
FEATURES = [
    "p_draw_poisson",   # the Poisson baseline as a feature — model learns when to trust it
    "lam_sum",          # expected tempo
    "lam_absdiff",      # evenness
    "drawrate_h",       # rolling decayed draw tendency, home
    "drawrate_a",
    "goals_total_h",    # rolling decayed avg total goals in home team's matches
    "goals_total_a",
    "ppda_sum",         # pressing intensity of both (low press = slower game)
    # context (standings pressure) — walk-forward from season table state
    "ppg_gap",          # |points-per-game difference| — results-evenness
    "season_frac",      # how deep into the season
    "mutual_comfort",   # late-season x both-teams-mid-table (a point suits both)
]


class DrawModel:
    """Logistic draw classifier over walk-forward rolling features.

    Trained on one season (24/25), frozen, evaluated out-of-sample — same
    protocol as the core model. Exists because the Stage 5 backtest showed
    Poisson P(draw) is miscalibrated exactly in its top band (the picks zone).
    """

    def __init__(self, weights: Optional[Dict] = None):
        self.w = weights

    # ---------------- features

    @staticmethod
    def rolling_stats(matches: List[Dict], before_date: str) -> Dict[str, Dict[str, float]]:
        """Per-team decayed rolling: draw rate, avg total goals, avg ppda."""
        hist: Dict[str, List[Tuple[int, int, float]]] = {}
        for m in matches:
            if m["date"] >= before_date:
                break
            if m["home_goals"] is None:
                continue
            hist.setdefault(m["home_team"], []).append(
                (m["home_goals"], m["away_goals"], m.get("home_ppda")))
            hist.setdefault(m["away_team"], []).append(
                (m["away_goals"], m["home_goals"], m.get("away_ppda")))
        out = {}
        for team, rows in hist.items():
            rows = rows[-WINDOW:]
            w_total = draws = totals = ppda = ppda_w = 0.0
            for i, (gf, ga, pp) in enumerate(reversed(rows)):
                w = DECAY ** i
                w_total += w
                draws += w * (gf == ga)
                totals += w * (gf + ga)
                if pp is not None:
                    ppda += w * pp
                    ppda_w += w
            out[team] = {
                "drawrate": draws / w_total,
                "goals_total": totals / w_total,
                "ppda": (ppda / ppda_w) if ppda_w else 10.0,
                "n": len(rows),
            }
        return out

    @staticmethod
    def season_context(matches: List[Dict], before_date: str,
                       home: str, away: str) -> Dict[str, float]:
        """Standings state before `date`, from the same season's matches only
        (walk-forward). mutual_comfort peaks when it's late and both teams sit
        mid-table — the classic 'a point suits everyone' configuration."""
        season = None
        pts: Dict[str, int] = {}
        played: Dict[str, int] = {}
        for m in matches:
            if m["date"] >= before_date:
                break
            for team, gf, ga in ((m["home_team"], m["home_goals"], m["away_goals"]),
                                 (m["away_team"], m["away_goals"], m["home_goals"])):
                if gf is None:
                    continue
                pts[team] = pts.get(team, 0) + (3 if gf > ga else 1 if gf == ga else 0)
                played[team] = played.get(team, 0) + 1
        n_h, n_a = played.get(home, 0), played.get(away, 0)
        ppg = {t: pts[t] / played[t] for t in pts if played[t] >= 3}
        ppg_h = ppg.get(home, 1.3)
        ppg_a = ppg.get(away, 1.3)
        season_frac = min(((n_h + n_a) / 2) / 38.0, 1.0)
        if len(ppg) >= 10:
            ordered = sorted(ppg.values())
            def pos_pct(v):
                return sum(1 for x in ordered if x <= v) / len(ordered)
            mid_h = 1 - abs(pos_pct(ppg_h) - 0.5) * 2
            mid_a = 1 - abs(pos_pct(ppg_a) - 0.5) * 2
        else:
            mid_h = mid_a = 0.5
        return {
            "ppg_gap": abs(ppg_h - ppg_a),
            "season_frac": season_frac,
            "mutual_comfort": season_frac * mid_h * mid_a,
        }

    @staticmethod
    def fixture_features(lam_h: float, lam_a: float, rho: float,
                         roll_h: Dict[str, float], roll_a: Dict[str, float],
                         ctx: Dict[str, float]) -> List[float]:
        return [
            outcome_probs(lam_h, lam_a, rho)["draw"],
            lam_h + lam_a,
            abs(lam_h - lam_a),
            roll_h["drawrate"],
            roll_a["drawrate"],
            roll_h["goals_total"],
            roll_a["goals_total"],
            roll_h["ppda"] + roll_a["ppda"],
            ctx["ppg_gap"],
            ctx["season_frac"],
            ctx["mutual_comfort"],
        ]

    # ---------------- training

    @classmethod
    def train(cls, leagues: List[str], seasons: List[str], model_params: Dict,
              out_path: "Path | None" = None) -> "DrawModel":
        X, y = [], []
        for league, season in ((lg, s) for lg in leagues for s in seasons):
            boosts = model_params["leagues"][league]
            fm = FormModel(league, [season])
            data = UnderstatService.load(league, season)
            for m in data["matches"]:
                if m["home_goals"] is None:
                    continue
                ratings = fm.ratings_before(m["date"])
                rh, ra = ratings.get(m["home_team"]), ratings.get(m["away_team"])
                if not rh or not ra or rh["n"] < MIN_MATCHES or ra["n"] < MIN_MATCHES:
                    continue
                roll = cls.rolling_stats(data["matches"], m["date"])
                ctx = cls.season_context(data["matches"], m["date"],
                                         m["home_team"], m["away_team"])
                lam_h, lam_a, _ = fm.lambdas(ratings, m["home_team"], m["away_team"],
                                             boosts["home_boost"], boosts["away_boost"])
                X.append(cls.fixture_features(lam_h, lam_a, model_params["rho"],
                                              roll[m["home_team"]], roll[m["away_team"]], ctx))
                y.append(1.0 if m["home_goals"] == m["away_goals"] else 0.0)

        import numpy as np
        from scipy.optimize import minimize
        X = np.array(X)
        y = np.array(y)
        mean, std = X.mean(axis=0), X.std(axis=0) + 1e-9
        Xn = (X - mean) / std
        Xn = np.hstack([np.ones((len(Xn), 1)), Xn])

        def nll(w):
            z = Xn @ w
            p = 1 / (1 + np.exp(-z))
            p = np.clip(p, 1e-9, 1 - 1e-9)
            return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean() + 1e-3 * (w[1:] ** 2).sum()

        res = minimize(nll, x0=np.zeros(Xn.shape[1]), method="BFGS")
        weights = {
            "coef": [round(float(v), 6) for v in res.x],
            "mean": [round(float(v), 6) for v in mean],
            "std": [round(float(v), 6) for v in std],
            "features": FEATURES,
            "train_seasons": seasons,
            "train_n": len(y),
            "train_nll": round(float(res.fun), 5),
        }
        path = out_path or PARAMS_PATH
        path.write_text(json.dumps(weights, indent=2), encoding="utf-8")
        log.info("draw model trained: n=%d nll=%.5f -> %s", len(y), res.fun, path)
        return cls(weights)

    @classmethod
    def load(cls, path: "Path | None" = None) -> Optional["DrawModel"]:
        path = path or PARAMS_PATH
        if not path.exists():
            return None
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def predict(self, features: List[float]) -> float:
        w = self.w
        z = w["coef"][0]
        for i, f in enumerate(features):
            z += w["coef"][i + 1] * (f - w["mean"][i]) / w["std"][i]
        return 1 / (1 + math.exp(-z))
