from __future__ import annotations
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.fbref.fixtures.fixtures_service import FixturesService
from services.predictions.draw_model import DrawModel
from services.predictions.form_model import FormModel
from services.predictions.probability_service import (
    call_outcome,
    modal_scores_by_outcome,
    outcome_probs,
    top_scorelines,
    unified_probs,
)
from services.zones.match_prediction_service import MatchPredictionService
from services.zones.zones_engine import ZonesEngine

log = logging.getLogger(__name__)

PARAMS_PATH = Path("data/config/model_params.json")

# ---- THE PUBLISHED TRIPLET IS A LAYER, NOT ONE MODEL (2026-09-20) --------
#
# Settled on 1,714 fixtures — every 25/26 match of all five leagues, the one
# complete season the frozen draw classifier has never seen, so it is the
# only leak-free test that exists for the shipped artifact.
#
# Two questions came back with different winners, which is why this is a
# layer rather than a swap:
#
#   what PRICES a match   the blend of the shipped model and the Elo arm
#                         (log-loss 0.9924 against ship's 0.9937)
#   what RANKS a draw     the Elo's lambdas through the shipped classifier
#                         (top-200 draw picks 32.5% against ship's 29.5%,
#                          binomial p=0.0175 against a 25.6% base)
#
# So: average the two triplets for the home:away ratio, then hand P(draw) to
# the arm that ranks draws best. `unified_probs` already does exactly this —
# it is how the shipped model itself is built, Poisson for the ratio and a
# classifier for the draw — so the layer is one extra call, not a new model.
#
# HONEST LIMITS. Blend beats ship on the triplet by 0.0013 nats at
# P(better)=0.74 — directional, not proven. Layer and blend are within two
# picks of each other on 200. What IS solid is that both beat ship at
# ranking draws, and the product ranks draws.
#
# Naive layerings were tried and failed: ship's ratio with the Elo's RAW
# draw, and the Elo's ratio with ship's draw, both land between their
# parents and beat neither (mix_se 0.9957, mix_es 0.9982).
ELO_PARAMS_PATH = Path("data/config/elo_params.json")
ELO_TABLE_DIR = Path("data/web/team")


def _elo_slug(league: str) -> str:
    return league.lower().replace(" ", "-")


SEASON = "2627"
HISTORY_SEASONS = ["2526", "2627"]
# zones blend both seasons' shot data through the rolling decayed window —
# current form flows in from day one, last season ages out naturally
ZONES_SOURCE_SEASON = ["2526", "2627"]

# draws pool ALL leagues (user decision 2026-08-08: backtest showed 12 vs 10
# money-back weeks and the only 4/4 came from the wide pool — p^4 economics)
DRAW_LEAGUES = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga",
                "GER-Bundesliga", "FRA-Ligue 1"]
HOME_LEAGUES = ["ENG-Premier League", "FRA-Ligue 1"]
AWAY_LEAGUES = DRAW_LEAGUES  # away favorites pool wide; GOLD tier is side-agnostic
N_DRAWS, N_HOME, N_AWAY = 4, 3, 3

# ticket window: leagues' rounds don't align and calendar weeks lie (rounds
# drift Fri-Mon / Fri-Sat / midweek). A window is the next CLUSTER of match
# days — consecutive dates with no gap of 2+ empty days — capped defensively.
WINDOW_GAP_DAYS = 2   # a gap this big ends the cluster
WINDOW_MAX_DAYS = 6   # safety cap on cluster length


class PredictionService:
    """Generates the weekly product: outcome probabilities for upcoming
    fixtures, plus the top-4 draw picks (EPL+Serie A) and top-3 home-win
    picks (EPL+Ligue 1)."""

    def __init__(self):
        self.params = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
        self.draw_model = DrawModel.load()
        self._zone_cache: Dict[str, Optional[Dict]] = {}
        self._matchup = MatchPredictionService()
        blend_path = Path("data/config/zone_blend.json")
        self.zone_blend = (json.loads(blend_path.read_text(encoding="utf-8"))
                           if blend_path.exists() else None)

    # ------------------------------------------------ fixtures

    def unplayed_fixtures(self, league: str) -> List[Dict]:
        fx = FixturesService.load(league, SEASON)
        if not fx:
            return []
        return [m for m in fx["matches"]
                if not m["played"] and isinstance(m["week"], int) and m["date"]]

    # ------------------------------------------------ zones (the "why")

    def _elo_for(self, league: str):
        """(params, {team: {attack, defence}}) for the Elo arm, or None.

        A league with no fitted Elo simply falls back to the shipped
        triplet — the layer is an improvement, not a dependency, and a
        missing artifact must never stop the round being priced."""
        if not hasattr(self, "_elo_cache"):
            self._elo_cache: Dict[str, Any] = {}
        if league in self._elo_cache:
            return self._elo_cache[league]
        got = None
        try:
            params = json.loads(
                ELO_PARAMS_PATH.read_text(encoding="utf-8"))[league]
            table = json.loads(
                (ELO_TABLE_DIR / _elo_slug(league) / "elo.json")
                .read_text(encoding="utf-8"))["table"]
            ratings = {r["team"]: r for r in table if r.get("current")}
            got = (params, ratings) if ratings else None
        except Exception as e:                       # noqa: BLE001
            log.warning("Elo arm unavailable for %s: %s", league, e)
        self._elo_cache[league] = got
        return got

    def _zones_for(self, league: str) -> Optional[Dict]:
        if league not in self._zone_cache:
            try:
                self._zone_cache[league] = ZonesEngine(
                    league, ZONES_SOURCE_SEASON).build(persist=False)["teams"]
            except Exception as e:
                log.warning("zones unavailable for %s: %s", league, e)
                self._zone_cache[league] = None
        return self._zone_cache[league]

    def _why(self, league: str, home: str, away: str) -> Optional[Dict[str, str]]:
        zones = self._zones_for(league)
        if not zones or home not in zones or away not in zones:
            return None
        result = self._matchup.predict(home, zones[home], away, zones[away])
        return result["matchups"]

    # ------------------------------------------------ prediction

    def predict_fixtures(self, league: str, fixtures: List[Dict]) -> List[Dict[str, Any]]:
        if not fixtures:
            return []
        boosts = self.params["leagues"][league]
        rho = self.params["rho"]
        fm = FormModel(league, HISTORY_SEASONS)

        out = []
        for m in fixtures:
            date = m["date"] or "9999-12-31"
            ratings = fm.ratings_before(date)
            lam_h, lam_a, low_conf = fm.lambdas(
                ratings, m["home_team"], m["away_team"],
                boosts["home_boost"], boosts["away_boost"])

            # calibrated zone-matchup blend. channels mode (Experiment A,
            # 2026-09-15) keeps the 9-zone STRUCTURE as four fitted channel
            # gammas — gated on frozen 25/26 full-stack (beats the scalar on
            # log-loss/acc/GOLD, draws top-4 equal); legacy scalar kept as
            # fallback for old configs.
            if self.zone_blend:
                zones = self._zones_for(league)
                if zones and self.zone_blend.get("mode") == "channels":
                    from services.zones.zones_engine import channel_boosts
                    b = channel_boosts(zones, m["home_team"], m["away_team"],
                                       self.zone_blend)
                    if b:
                        lam_h *= b[0]
                        lam_a *= b[1]
                elif zones and self.zone_blend.get("gamma"):
                    # (math is imported at module level — a local `import
                    # math` here made the name function-local and shadowed
                    # it for every other branch)
                    from services.zones.zones_engine import zone_advantage
                    adv = zone_advantage(zones, m["home_team"], m["away_team"])
                    if adv:
                        g = self.zone_blend["gamma"]
                        mu, sd = self.zone_blend["adv_mean"], self.zone_blend["adv_std"] or 1.0
                        lam_h *= math.exp(g * (adv[0] - mu) / sd)
                        lam_a *= math.exp(g * (adv[1] - mu) / sd)

            probs = outcome_probs(lam_h, lam_a, rho)

            p_draw_clf = None
            draw_drivers = None
            roll = ctx = None
            if self.draw_model:
                roll = DrawModel.rolling_stats(fm.matches, date)
                if m["home_team"] in roll and m["away_team"] in roll:
                    from services.understat.understat_service import UnderstatService
                    season_matches = (UnderstatService.load(league, SEASON) or {}).get("matches", [])
                    ctx = DrawModel.season_context(season_matches, date,
                                                  m["home_team"], m["away_team"])
                    feats = DrawModel.fixture_features(
                        lam_h, lam_a, rho,
                        roll[m["home_team"]], roll[m["away_team"]], ctx)
                    p_draw_clf = round(self.draw_model.predict(feats), 4)
                    draw_drivers = self.draw_model.explain(feats)
                else:
                    roll = None

            probs_ship = unified_probs(probs, p_draw_clf)

            # ---- the Elo arm, and the layer it makes (see the note by
            # ELO_PARAMS_PATH for what was measured and on how many rows)
            probs_elo = None
            elo = self._elo_for(league)
            if elo and roll is not None and ctx is not None and not low_conf:
                ep, ratings = elo
                rh = ratings.get(m["home_team"])
                ra = ratings.get(m["away_team"])
                if rh and ra:
                    elh = math.exp(rh["attack"] - ra["defence"]
                                   + ep["home_adv"]) * ep["conv"]
                    ela = math.exp(ra["attack"] - rh["defence"]) * ep["conv"]
                    p_draw_elo = round(self.draw_model.predict(
                        DrawModel.fixture_features(
                            elh, ela, ep["rho"],
                            roll[m["home_team"]], roll[m["away_team"]], ctx)), 4)
                    probs_elo = unified_probs(
                        outcome_probs(elh, ela, ep["rho"]), p_draw_elo)

            if probs_elo:
                # average the triplets for the home:away ratio…
                mix = {k: (probs_ship[k] + probs_elo[k]) / 2
                       for k in ("home", "draw", "away")}
                tot = sum(mix.values()) or 1.0
                mix = {k: v / tot for k, v in mix.items()}
                # …then give P(draw) to the arm that ranks draws best
                probs_unified = unified_probs(mix, probs_elo["draw"])
            else:
                probs_unified = probs_ship
            p_max = max(probs_unified.values())
            tier = "gold" if p_max >= 0.55 else "silver" if p_max >= 0.45 else "flip"
            out.append({
                "tier": tier,
                "league": league,
                "season": SEASON,
                "week": m["week"],
                "kickoff": m["date"],
                "home": m["home_team"],
                "away": m["away_team"],
                "xg": {m["home_team"]: round(lam_h, 2), m["away_team"]: round(lam_a, 2)},
                # official triplet: blended H:A ratio, Elo-arm classifier draw
                "probabilities": probs_unified,
                # both arms kept so a fixture can be audited after the fact —
                # "why did it say that" needs the inputs, not just the output
                "probabilities_ship": probs_ship,
                "probabilities_elo": probs_elo,
                # the model's stated call: draw once P(draw) hits the ceiling
                # zone (DRAW_CALL_MIN), else argmax — football has ~26% draws
                "call": call_outcome(probs_unified),
                "probabilities_poisson": probs,
                "p_draw_classifier": p_draw_clf,
                "draw_drivers": draw_drivers,
                "top_scorelines": top_scorelines(lam_h, lam_a, rho),
                "modal_scores": modal_scores_by_outcome(lam_h, lam_a, rho),
                "confidence": "low" if low_conf else "normal",
                "why": self._why(league, m["home_team"], m["away_team"]),
            })
        return out

    # ------------------------------------------------ picks

    @staticmethod
    def _last_bet_end() -> Optional[str]:
        """Latest kickoff across every committed bet (picks, slip legs, gold
        singles). The next betting window may only contain fixtures AFTER
        this date — the user's rule: the next bet is the NEXT round, never a
        re-suggestion while the current round's games are still playing."""
        import json as _json
        latest = None
        for path, extract in (
                (Path("data/ledger/picks.jsonl"), lambda r: [r.get("kickoff")]),
                (Path("data/slips/slips.jsonl"),
                 lambda r: [l.get("kickoff") for l in r.get("legs", [])]),
                (Path("data/slips/gold.jsonl"),
                 lambda r: [b.get("kickoff") for b in r.get("bets", [])])):
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                for k in extract(_json.loads(line)):
                    if k and (latest is None or k > latest):
                        latest = k
        return latest

    @staticmethod
    def _pending_bets_span() -> Optional[tuple]:
        """(first upcoming kickoff, last kickoff) across PENDING bets. While a
        booked round is still in play the dashboard must show THAT round —
        not leap to the next one (bug caught 2026-09-15: booking Monday made
        the dash skip to October while the live bet hadn't kicked off).
        Already-played kickoffs inside a still-pending group (gold grades as
        a block) don't drag the span backwards."""
        import json as _json
        from datetime import date as _d
        ks: list = []
        for path, kicks in (
                (Path("data/ledger/picks.jsonl"),
                 lambda r: [r.get("kickoff")] if r.get("status") == "pending" else []),
                (Path("data/slips/slips.jsonl"),
                 lambda r: [l.get("kickoff") for l in r.get("legs", [])]
                 if r.get("status") == "pending" else []),
                (Path("data/slips/gold.jsonl"),
                 lambda r: [b.get("kickoff") for b in r.get("bets", [])]
                 if r.get("status") == "pending" else [])):
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    ks.extend(k for k in kicks(_json.loads(line)) if k)
        if not ks:
            return None
        today = _d.today().isoformat()
        future = [k for k in ks if k >= today]
        if not future:
            return None  # all played, grading lag — fall through to next round
        return min(future), max(ks)

    def weekly_picks(self, start: Optional[str] = None) -> Dict[str, Any]:
        """Weekend-based selection: league round numbers drift (Serie A can be
        on round 2 while the EPL is on round 1, cup weeks shift things), so the
        unit of play is the DATE WINDOW — earliest upcoming kickoff + WINDOW_DAYS
        — never the gameweek."""
        from datetime import date as _date, timedelta

        unplayed = {lg: self.unplayed_fixtures(lg)
                    for lg in set(DRAW_LEAGUES + HOME_LEAGUES)}
        if start:
            unplayed = {lg: [m for m in ms if m["date"] >= start]
                        for lg, ms in unplayed.items()}
        pending_span = None
        if not start:
            # while a booked round is pending, show exactly its remaining
            # span (no re-clustering, no fresh move); once it fully grades,
            # move past the last bet to the next round
            pending_span = self._pending_bets_span()
            if pending_span:
                lo, hi = pending_span
                unplayed = {lg: [m for m in ms if lo <= m["date"] <= hi]
                            for lg, ms in unplayed.items()}
            else:
                last_end = self._last_bet_end()
                if last_end:
                    unplayed = {lg: [m for m in ms if m["date"] > last_end]
                                for lg, ms in unplayed.items()}

        def league_cluster(ms):
            """A league's NEXT round = the fbref ROUND NUMBER of its earliest
            upcoming fixture. Date-clustering merged two rounds whenever a
            league played daily (La Liga leftovers + midweek round put the
            same team on one slip twice, 2026-09-13); round numbers make
            round-purity structural. Span still capped defensively."""
            dated = [m for m in ms if m["date"]]
            if not dated:
                return None
            first = min(m["date"] for m in dated)
            wk = min(m["week"] for m in dated if m["date"] == first)
            dates = sorted({m["date"] for m in dated if m["week"] == wk
                            and (_date.fromisoformat(m["date"])
                                 - _date.fromisoformat(first)).days <= WINDOW_MAX_DAYS})
            return first, dates[-1], wk

        if pending_span:
            # the booked round IS the window — every league shows its
            # remaining games in the span, round labels come from the data
            window_start, window_end = pending_span
            preds: Dict[str, List[Dict]] = {}
            for league, ms in unplayed.items():
                rows = self.predict_fixtures(league, ms)
                for p in rows:
                    p["in_window"] = True
                preds[league] = rows
        else:
            clusters = {lg: league_cluster(ms) for lg, ms in unplayed.items()}
            starts = [c[0] for c in clusters.values() if c]
            if not starts:
                return {"season": SEASON, "window": None, "weeks": {},
                        "draw_picks": [], "draw_candidates": [], "home_win_picks": [],
                        "trixy": None, "all_predictions": {}, "strategy": None}
            earliest = min(starts)
            # only leagues whose round STARTS with the pack join this window
            active = {lg: c for lg, c in clusters.items() if c and
                      (_date.fromisoformat(c[0]) - _date.fromisoformat(earliest)).days <= 2}
            window_start = earliest
            window_end = max(c[1] for c in active.values())

            preds = {}
            for league, ms in unplayed.items():
                c = active.get(league)
                in_scope = [m for m in ms
                            if c and m["week"] == c[2] and c[0] <= m["date"] <= c[1]]
                rows = self.predict_fixtures(league, in_scope)
                for p in rows:
                    p["in_window"] = True  # each league shows ONLY its own next round
                preds[league] = rows

        def pick(leagues, score_fn, n, pick_type):
            pool = [p for lg in leagues for p in preds[lg]
                    if p["confidence"] == "normal" and p["in_window"]
                    and score_fn(p) is not None]
            pool.sort(key=score_fn, reverse=True)
            picks = []
            used_teams: set = set()
            for p in pool:
                if len(picks) == n:
                    break
                # no team twice on one board — system math assumes independent
                # legs, and a doubled team correlates them
                if p["home"] in used_teams or p["away"] in used_teams:
                    continue
                used_teams.update((p["home"], p["away"]))
                picks.append({**p, "rank": len(picks) + 1, "pick_type": pick_type,
                              "pick_prob": round(score_fn(p), 4)})
            return picks

        # top 8 candidates; the first 4 are the official ticket (ledger-graded),
        # 5-8 exist so the user can swap in better-priced alternatives
        draw_candidates = pick(DRAW_LEAGUES,
                               lambda p: p["p_draw_classifier"] if p["p_draw_classifier"] is not None
                               else p["probabilities"]["draw"],
                               N_DRAWS * 2, "draw")
        draw_picks = draw_candidates[:N_DRAWS]
        home_picks = pick(HOME_LEAGUES, lambda p: p["probabilities"]["home"],
                          N_HOME, "home")
        away_picks = pick(AWAY_LEAGUES, lambda p: p["probabilities"]["away"],
                          N_AWAY, "away")

        # uncertified watchlist: low-confidence fixtures whose draw number is
        # ticket-grade — shown to the user (their judgment), never picked or
        # ledger-committed (the probability rests on league-average priors)
        min_ticket_p = draw_picks[-1]["pick_prob"] if draw_picks else 0.30
        watchlist = sorted(
            (p for lg in DRAW_LEAGUES for p in preds[lg]
             if p["confidence"] == "low" and p["in_window"]
             and p["probabilities"]["draw"] >= min_ticket_p),
            key=lambda p: p["probabilities"]["draw"], reverse=True)[:3]
        draw_watchlist = [{**p, "pick_prob": p["probabilities"]["draw"]} for p in watchlist]

        result = {
            "season": SEASON,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "window": {"start": window_start, "end": window_end},
            "weeks": {lg: sorted({p["week"] for p in ps if p["in_window"]}) for lg, ps in preds.items()},
            "draw_picks": draw_picks,
            "draw_candidates": draw_candidates,
            "draw_watchlist": draw_watchlist,
            "home_win_picks": home_picks,
            "away_win_picks": away_picks,
            "trixy": _trixy_outlook([p["pick_prob"] for p in draw_picks]),
            "all_predictions": preds,
        }
        from services.predictions.strategy_advisor import advise
        result["strategy"] = advise(result)
        return result


def _trixy_outlook(probs):
    """P(exactly k of the 4 draw picks hit), assuming independence —
    the user's trixy market pays at 2/4 (money back), 3/4, 4/4."""
    if not probs:
        return None
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nxt[k] += q * (1 - p)
            nxt[k + 1] += q * p
        dist = nxt
    return {
        "p_ge2": round(sum(dist[2:]), 4),
        "p_ge3": round(sum(dist[3:]), 4),
        "p_4of4": round(dist[4] if len(dist) > 4 else 0.0, 4),
    }
