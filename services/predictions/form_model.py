from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple

from services.understat.understat_service import UnderstatService

log = logging.getLogger(__name__)

DECAY = 0.985     # per-match recency decay (matches zones engine)
WINDOW = 38       # rolling matches per team
MIN_MATCHES = 5   # below this a team gets league-average priors (low confidence)
# strength-of-schedule adjustment REJECTED 2026-09-10: frozen 25/26 eval got
# WORSE (log-loss 0.9959->0.9969, draw picks 32.2%->30.3%) — balanced
# round-robins self-average schedule strength; the adjustment adds noise.
# Set >0 only to re-test; ship-gate applies.
OPP_ADJUST_ITERS = 0


class FormModel:
    """Walk-forward team attack/defense strengths from Understat per-match xG.

    Multiplicative model:
        lam_home = (att_home * def_away / mu) * home_boost
        lam_away = (att_away * def_home / mu) * away_boost
    att/def are decay-weighted rolling means of xG for/against per match;
    mu is the league's average xG per team-match over the same pool.
    home_boost / away_boost are per-league calibrated constants.
    """

    def __init__(self, league: str, seasons: List[str]):
        self.league = league
        rows = []
        loaded = 0
        for season in seasons:
            data = UnderstatService.load(league, season)
            if not data:
                # normal preseason state for the newest season — no matches yet
                log.info("understat data missing for %s %s (skipping)", league, season)
                continue
            rows.extend(data["matches"])
            loaded += 1
        if not loaded:
            raise RuntimeError(f"no understat data for {league} in any of {seasons}")
        rows.sort(key=lambda m: m["date"])
        self.matches = [m for m in rows if m.get("home_xg") is not None]
        self._ratings_cache: Dict[str, Dict] = {}

    def ratings_before(self, date: str) -> Dict[str, Dict[str, float]]:
        """Per-team decay-weighted att/def as of (strictly before) `date`,
        OPPONENT-ADJUSTED: each match's xG-for is scaled by how leaky that
        opponent's defence is (and xG-against by how sharp their attack is),
        iterated to convergence — so feasting on weak teams no longer looks
        like beating strong ones. Memoized per date (fixtures in one round
        share the cutoff)."""
        if date in self._ratings_cache:
            self._mu = self._ratings_cache[date]["__mu__"]
            return self._ratings_cache[date]["ratings"]
        hist: Dict[str, List[Tuple[str, float, float]]] = {}
        for m in self.matches:
            if m["date"] >= date:
                break
            hist.setdefault(m["home_team"], []).append(
                (m["away_team"], m["home_xg"], m["away_xg"]))
            hist.setdefault(m["away_team"], []).append(
                (m["home_team"], m["away_xg"], m["home_xg"]))

        windows = {t: rows[-WINDOW:] for t, rows in hist.items()}
        pool_for = [xf for rows in windows.values() for _, xf, _ in rows]
        mu = (sum(pool_for) / len(pool_for)) if pool_for else 1.3

        # pass 0: plain decayed means; passes 1..K: re-weight by opponent
        att = {}
        dfn = {}
        for t, rows in windows.items():
            w_total = a = d = 0.0
            for i, (_, xf, xa) in enumerate(reversed(rows)):
                w = DECAY ** i
                w_total += w
                a += w * xf
                d += w * xa
            att[t], dfn[t] = a / w_total, d / w_total

        for _ in range(OPP_ADJUST_ITERS):
            new_att, new_dfn = {}, {}
            for t, rows in windows.items():
                w_total = a = d = 0.0
                for i, (opp, xf, xa) in enumerate(reversed(rows)):
                    w = DECAY ** i
                    w_total += w
                    # xf against a leaky defence counts for less; xa conceded
                    # to a blunt attack counts for more (and vice versa)
                    a += w * xf * (mu / max(dfn.get(opp, mu), 0.3))
                    d += w * xa * (mu / max(att.get(opp, mu), 0.3))
                new_att[t], new_dfn[t] = a / w_total, d / w_total
            att, dfn = new_att, new_dfn

        ratings = {t: {"att": att[t], "def": dfn[t], "n": len(windows[t]), "mu": mu}
                   for t in windows}
        self._mu = mu
        self._ratings_cache[date] = {"ratings": ratings, "__mu__": mu}
        return ratings

    def lambdas(self, ratings: Dict[str, Dict[str, float]], home: str, away: str,
                home_boost: float, away_boost: float) -> Optional[Tuple[float, float, bool]]:
        """xG pair for a fixture; low_confidence=True when either team is on
        priors (promoted / early data)."""
        mu = getattr(self, "_mu", 1.3)
        rh = ratings.get(home)
        ra = ratings.get(away)
        low_conf = (rh is None or rh["n"] < MIN_MATCHES
                    or ra is None or ra["n"] < MIN_MATCHES)
        prior = {"att": mu, "def": mu, "n": 0, "mu": mu}
        rh = rh if rh and rh["n"] >= MIN_MATCHES else prior
        ra = ra if ra and ra["n"] >= MIN_MATCHES else prior
        lam_h = (rh["att"] * ra["def"] / mu) * home_boost
        lam_a = (ra["att"] * rh["def"] / mu) * away_boost
        return max(lam_h, 0.05), max(lam_a, 0.05), low_conf
