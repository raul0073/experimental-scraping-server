import json
import math
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.fbref.league.fbref_utils import _safe_name
from services.predictions.ledger_service import LedgerService
from services.predictions.prediction_service import ZONES_SOURCE_SEASON, PredictionService
from services.zones.zones_engine import ZonesEngine

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")
# league crest path for table chips (fetched by scripts/fetch_team_logos.py;
# templates hide the <img> onerror so a missing file is cosmetic)
templates.env.globals["league_crest"] = \
    lambda lg: f"/static/logos/leagues/{_safe_name(lg)}.png"
# cache-buster: style.css mtime — browsers cache /static hard, so every CSS
# change must change the URL or users see the old design for days
templates.env.globals["asset_v"] = \
    lambda: int(Path("static/style.css").stat().st_mtime)

_CACHE: dict = {}
CACHE_TTL_S = 600


def _cached(key, builder):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]
    value = builder()
    _CACHE[key] = (now, value)
    return value


LANES = [("Left", "Left"), ("Central", "Central"), ("Right", "Right")]
BANDS = ["def", "att"]
# defender's mirrored lane for each attacker lane
MIRROR = {"Left": "Right", "Central": "Central", "Right": "Left"}
# a home DEF zone is attacked by the opponent's mirrored ATT zone, and vice versa
OPP_BAND = {"def": "att", "att": "def"}
# grid-area codes for the 3x3 pitch (mid is one spanning cell)
AREA = {"defLeft": "dl", "defCentral": "dc", "defRight": "dr", "mid": "m",
        "attLeft": "al", "attCentral": "ac", "attRight": "ar"}


def _delta_class(delta: float) -> str:
    if delta >= 25:
        return "h2"
    if delta >= 10:
        return "h1"
    if delta <= -25:
        return "a2"
    if delta <= -10:
        return "a1"
    return "even"


def _team_facts(league: str):
    """Season-to-date 'dry' facts per team from stored shot events: top
    scorer/assister, finishing vs xG, shot accuracy. Own goals count for the
    scoreline but not toward shots, xG or the scorer chart. (Passing accuracy
    is not recoverable post-Opta — deep completions is the closest signal and
    already feeds the midfield build-up rating.)"""
    from services.predictions.prediction_service import SEASON
    from services.understat.shot_events_service import ShotEventsService
    data = ShotEventsService.load(league, SEASON)
    teams: dict = {}
    for m in (data or {}).get("matches", {}).values():
        for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
            t = teams.setdefault(team, {"mp": 0, "shots": 0, "sot": 0, "goals": 0,
                                        "ng": 0, "xg": 0.0, "sp_xg": 0.0,
                                        "scorers": {}, "assisters": {}})
            t["mp"] += 1
            for s in m["shots"]:
                if s.get("side") != side:
                    continue
                res = s.get("result")
                if res == "OwnGoal":  # understat lists these under the side credited
                    t["goals"] += 1
                    continue
                t["shots"] += 1
                t["xg"] += s.get("xg") or 0.0
                if s.get("situation") in ("FromCorner", "SetPiece", "DirectFreekick"):
                    t["sp_xg"] += s.get("xg") or 0.0
                if res == "Goal":
                    t["goals"] += 1
                    t["ng"] += 1
                    t["sot"] += 1
                    if s.get("player"):
                        t["scorers"][s["player"]] = t["scorers"].get(s["player"], 0) + 1
                    if s.get("assist_player"):
                        t["assisters"][s["assist_player"]] = t["assisters"].get(s["assist_player"], 0) + 1
                elif res == "SavedShot":
                    t["sot"] += 1
    out = {}
    for team, t in teams.items():
        fin = round(t["goals"] - t["xg"], 1)
        out[team] = {
            "mp": t["mp"], "goals": t["goals"], "xg": round(t["xg"], 1), "fin": fin,
            "fin_note": ("running hot" if fin >= 1.0 else
                         "running cold" if fin <= -1.0 else "about right"),
            "shots": t["shots"],
            "sot_pct": round(t["sot"] / t["shots"] * 100) if t["shots"] else None,
            "conv_pct": round(t["ng"] / t["shots"] * 100) if t["shots"] else None,
            "top_scorer": max(t["scorers"].items(), key=lambda kv: kv[1]) if t["scorers"] else None,
            "top_assist": max(t["assisters"].items(), key=lambda kv: kv[1]) if t["assisters"] else None,
            "sp_xg": round(t["sp_xg"], 1),
            "sp_pct": round(t["sp_xg"] / t["xg"] * 100) if t["xg"] else None,
        }

    # record: points / PPG / last-5 form from fixtures, xPTS from understat
    from services.fbref.fixtures.fixtures_service import FixturesService
    fx = FixturesService.load(league, SEASON)
    if fx:
        rec: dict = {}
        for m in fx["matches"]:
            if not m.get("played"):
                continue
            for team, gf, ga in ((m["home_team"], m["home_goals"], m["away_goals"]),
                                 (m["away_team"], m["away_goals"], m["home_goals"])):
                r = rec.setdefault(team, {"pts": 0, "mp": 0, "cs": 0, "blank": 0, "form": []})
                res = "W" if gf > ga else "D" if gf == ga else "L"
                r["pts"] += {"W": 3, "D": 1, "L": 0}[res]
                r["mp"] += 1
                r["cs"] += ga == 0
                r["blank"] += gf == 0
                r["form"].append((m["date"] or "", res))
        for team, r in rec.items():
            if team in out and r["mp"]:
                out[team]["pts"] = r["pts"]
                out[team]["ppg"] = round(r["pts"] / r["mp"], 2)
                out[team]["cs"] = r["cs"]
                out[team]["blank"] = r["blank"]
                out[team]["form"] = [x[1] for x in sorted(r["form"])[-5:]]
    from services.understat.understat_service import UnderstatService
    us = UnderstatService.load(league, SEASON)
    if us:
        xp: dict = {}
        for m in us["matches"]:
            for pre, team in (("home", m["home_team"]), ("away", m["away_team"])):
                v = m.get(f"{pre}_xpts")
                if v is not None:
                    xp[team] = xp.get(team, 0.0) + v
        for team, v in xp.items():
            if team in out:
                out[team]["xpts"] = round(v, 1)

    return {"season": SEASON, "teams": out}


_RESULT_LABEL = {"Goal": ("goal", "GOAL"), "SavedShot": ("ontarget", "saved"),
                 "ShotOnPost": ("off", "hit the post"), "MissedShots": ("off", "missed"),
                 "BlockedShot": ("off", "blocked")}


def _team_shots(league: str):
    """Season shot dots per team for the match-page shot maps, pre-mapped to
    half-pitch SVG coords (272x210, goal at top, shooter's left = screen left,
    matching the battle-map lane orientation). Own goals excluded — their
    coordinates describe the defender, not an attack."""
    from services.predictions.prediction_service import SEASON
    from services.understat.shot_events_service import ShotEventsService
    data = ShotEventsService.load(league, SEASON)
    teams: dict = {}
    for m in (data or {}).get("matches", {}).values():
        for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
            t = teams.setdefault(team, {"for": [], "against": []})
            for s in m["shots"]:
                if s.get("x") is None or s.get("y") is None or s.get("result") == "OwnGoal":
                    continue
                depth = min(max((s["x"] - 0.5) * 2.0, 0.0), 1.0)
                cls, lab = _RESULT_LABEL.get(s.get("result"), ("off", s.get("result") or "?"))
                xg = s.get("xg") or 0.0
                t["for" if s.get("side") == side else "against"].append({
                    "px": round((1.0 - s["y"]) * 272, 1),
                    "py": round((1.0 - depth) * 210, 1),
                    "r": round(3.0 + 9.0 * xg, 1),
                    "xg": xg,
                    "cls": cls,
                    "tip": f"{s.get('player') or '?'} {s.get('minute') if s.get('minute') is not None else '?'}′ · xG {xg:.2f} · {lab}",
                })
    for t in teams.values():
        for k in ("for", "against"):
            t[k].sort(key=lambda d: d["cls"] == "goal")  # goals draw on top
            t[k] = {"dots": t[k], "heat": _shot_heat(t[k])}
    return teams


def _shot_heat(dots):
    """xG-density heat cells (8x6 grid over the 272x210 half pitch) so the
    dot cloud also reads as zones. Opacity is xG share of the hottest cell."""
    CW, CH = 34.0, 35.0
    cells: dict = {}
    for d in dots:
        cx = min(int(d["px"] // CW), 7)
        cy = min(int(d["py"] // CH), 5)
        cells[(cx, cy)] = cells.get((cx, cy), 0.0) + max(d["xg"], 0.02)
    if not cells:
        return []
    mx = max(cells.values())
    return [{"x": int(cx * CW), "y": int(cy * CH), "o": o}
            for (cx, cy), v in cells.items()
            if (o := round(0.38 * (v / mx) ** 0.7, 2)) >= 0.05]


def _badge_fn(league: str):
    """Team crest lookup (manifest built by scripts/fetch_team_logos.py) with
    a monogram fallback so a missing crest is never a broken image."""
    p = Path("static/logos/manifest.json")
    lg = json.loads(p.read_text(encoding="utf-8")).get(league, {}) if p.exists() else {}

    def badge(team: str):
        words = [w for w in team.replace("'", " ").split() if w]
        abbr = ("".join(w[0] for w in words)[:3] if len(words) > 1 else team[:3]).upper()
        return {"logo": lg.get(team), "abbr": abbr}
    return badge


# 9-slice team pizza: league percentiles, grouped attack / shooting / defending,
# rendered with mplsoccer's PyPizza (PNG cached on disk, rebuilt after each
# data refresh). Post-Opta honesty: DEEP (deep completions) stands in for
# passing, PRESS (PPDA) for tackling. Inverted metrics are negated before
# ranking so a longer slice is ALWAYS better.
_PIZZA_PARAMS = ["xG /game", "Big\nchances", "Deep\ncompletions", "Shots /game",
                 "On target %", "Conversion %", "Press\n(PPDA)", "xGA /game",
                 "Screen\n(deep allowed)"]
_PIZZA_COLORS = ["#d97706"] * 3 + ["#2563eb"] * 3 + ["#16a34a"] * 3


def _render_pizza(team: str, values, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mplsoccer import PyPizza
    baker = PyPizza(params=_PIZZA_PARAMS, background_color="#ffffff",
                    straight_line_color="#e8eaec", straight_line_lw=1,
                    last_circle_lw=1, last_circle_color="#d7dadd",
                    other_circle_lw=0, inner_circle_size=11)
    fig, _ = baker.make_pizza(
        values, figsize=(7, 7.4), color_blank_space="same",
        slice_colors=_PIZZA_COLORS, value_bck_colors=_PIZZA_COLORS, blank_alpha=0.32,
        kwargs_slices=dict(edgecolor="#ffffff", zorder=2, linewidth=1.6),
        kwargs_params=dict(color="#2a3138", fontsize=12, va="center"),
        kwargs_values=dict(color="#ffffff", fontsize=11.5, zorder=3,
                           bbox=dict(edgecolor="#ffffff", boxstyle="round,pad=0.18", lw=1)),
    )
    fig.text(0.515, 0.975, team, size=16, ha="center", weight="bold", color="#1c2228")
    fig.text(0.515, 0.947, "league percentiles · attack / shooting / defending",
             size=10, ha="center", color="#6a7480")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=135, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)


def _pizza_png(league: str, team: str) -> Optional[str]:
    """Disk-cached pizza PNG url for a team; rebuilt when data refreshed."""
    pcts = _cached(("pizza", league), lambda: _team_pizza(league)).get(team)
    if not pcts:
        return None
    out = Path("static/pizzas") / _safe_name(league) / f"{_safe_name(team)}.png"
    stamp = Path("data/reports/last_weekly_run.txt")
    fresh = out.exists() and (not stamp.exists()
                              or out.stat().st_mtime >= stamp.stat().st_mtime)
    if not fresh:
        _render_pizza(team, pcts, out)
    # mtime in the URL so browsers refetch after each regeneration
    return f"/{out.as_posix()}?v={int(out.stat().st_mtime)}"


def _team_pizza(league: str):
    from services.predictions.prediction_service import SEASON
    from services.understat.shot_events_service import ShotEventsService
    from services.understat.understat_service import UnderstatService
    us = UnderstatService.load(league, SEASON)
    sh = ShotEventsService.load(league, SEASON)
    facts = _team_facts(league)["teams"]
    if not us or not sh or not facts:
        return {}

    per: dict = {}
    for m in us["matches"]:
        if m.get("home_goals") is None:
            continue
        for pre, opp, team in (("home", "away", m["home_team"]),
                               ("away", "home", m["away_team"])):
            t = per.setdefault(team, {"mp": 0, "deep": 0.0, "deep_allowed": 0.0,
                                      "ppda": 0.0, "xga": 0.0})
            t["mp"] += 1
            t["deep"] += m.get(f"{pre}_deep") or 0
            t["deep_allowed"] += m.get(f"{opp}_deep") or 0
            t["ppda"] += m.get(f"{pre}_ppda") or 0
            t["xga"] += m.get(f"{opp}_xg") or 0

    big: dict = {}
    for m in sh["matches"].values():
        for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
            big[team] = big.get(team, 0) + sum(
                1 for s in m["shots"]
                if s["side"] == side and (s.get("xg") or 0) > 0.30
                and s.get("result") != "OwnGoal")

    vals: dict = {}
    for team, f in facts.items():
        p = per.get(team)
        if not p or not p["mp"] or not f.get("mp") or not f.get("shots"):
            continue
        vals[team] = [
            f["xg"] / f["mp"],
            big.get(team, 0) / f["mp"],
            p["deep"] / p["mp"],
            f["shots"] / f["mp"],
            f["sot_pct"] or 0,
            f["conv_pct"] or 0,
            -(p["ppda"] / p["mp"]),
            -(p["xga"] / p["mp"]),
            -(p["deep_allowed"] / p["mp"]),
        ]
    teams = list(vals)
    if len(teams) < 2:
        return {}
    n = len(teams)
    pcts = {t: [] for t in teams}
    for i in range(len(_PIZZA_PARAMS)):
        for rank, t in enumerate(sorted(teams, key=lambda t: vals[t][i])):
            pcts[t].append(round(rank / (n - 1) * 100))
    return pcts


# formation-slot -> tactics-board coords (272x420 full pitch, attacking UP)
_SLOT_XY = {
    "GK": (136, 390),
    "DL": (36, 322), "DC": (136, 332), "DR": (236, 322),
    "DML": (52, 276), "DMC": (136, 278), "DMR": (220, 276),
    "ML": (36, 220), "MC": (136, 224), "MR": (236, 220),
    "AML": (44, 166), "AMC": (136, 170), "AMR": (228, 166),
    "FWL": (84, 110), "FW": (136, 104), "FWR": (188, 110),
}


def _team_shape(league: str):
    """Minutes-weighted typical XI per team from lineup slots. This is a ROLE
    map derived from team sheets, not measured average positions — no free
    source publishes tracking-based positions post-Opta."""
    from services.predictions.prediction_service import SEASON
    from services.understat.rosters_service import RostersService
    data = RostersService.load(league, SEASON)
    acc: dict = {}
    for m in (data or {}).get("matches", {}).values():
        for side, team in (("h", m["home_team"]), ("a", m["away_team"])):
            for p in m["rosters"].get(side, []):
                if not p.get("player"):
                    continue
                e = acc.setdefault(team, {}).setdefault(p["player"], {"mins": 0, "slots": {}})
                e["mins"] += p.get("minutes") or 0
                pos = p.get("position")
                if pos and pos != "Sub":
                    e["slots"][pos] = e["slots"].get(pos, 0) + (p.get("minutes") or 0)
    out = {}
    for team, players in acc.items():
        cands = sorted(((e["mins"], name, max(e["slots"].items(), key=lambda kv: kv[1])[0])
                        for name, e in players.items() if e["slots"]), reverse=True)[:11]
        if not cands:
            continue
        max_mins = cands[0][0] or 1
        by_slot: dict = {}
        for mins, name, slot in cands:
            by_slot.setdefault(slot, []).append((mins, name))
        dots = []
        for slot, ps in by_slot.items():
            x0, y0 = _SLOT_XY.get(slot, (136, 224))
            for i, (mins, name) in enumerate(ps):
                off = (i - (len(ps) - 1) / 2.0) * 46
                toks = name.split()
                short = toks[-1]
                if short.rstrip(".") in ("Jr", "Sr", "II", "III", "IV") and len(toks) > 1:
                    short = toks[-2]
                dots.append({"x": round(x0 + off, 1), "y": y0,
                             "name": short, "full": name, "mins": mins,
                             "op": round(0.45 + 0.55 * mins / max_mins, 2)})
        out[team] = dots
    return out


def _bottom_line(home, away, zh, za, bands, battles, hfacts, afacts, pred):
    """Auto-written one-paragraph verdict in plain football language:
    who runs midfield and WHY, attack quality, flank danger spots,
    finishing form, and the model's lean when one exists."""
    bits = []

    # -- midfield story: band gap first, on-the-ball phase asymmetry second
    ph_h = zh["midProgress"]["rating"] - (za["midPress"]["rating"] + za["midShield"]["rating"]) / 2
    ph_a = za["midProgress"]["rating"] - (zh["midPress"]["rating"] + zh["midShield"]["rating"]) / 2
    dm = round(bands["home"]["mid"] - bands["away"]["mid"], 1)
    mid_clause = None
    win = None
    if dm >= 10:
        win, verb = home, "should control midfield"
    elif dm <= -10:
        win, verb = away, "should control midfield"
    elif ph_h >= 10 and ph_a <= 0:
        win, verb = home, "should have more of the ball"
    elif ph_a >= 10 and ph_h <= 0:
        win, verb = away, "should have more of the ball"
    if win:
        lose = away if win == home else home
        wb = bands["home" if win == home else "away"]["mid"]
        lb = bands["away" if win == home else "home"]["mid"]
        wz, lz = (zh, za) if win == home else (za, zh)
        s = f"{win} {verb} ({wb} v {lb})"
        lpress = lz["midPress"]["rating"]
        if lpress <= 25 and wb < 55:
            s += f" — not because they're good, but because {lose} won't press them (press {int(round(lpress))})"
        elif wz["midProgress"]["rating"] >= 65:
            s += f" — their build-up ({int(round(wz['midProgress']['rating']))}) should play through"
        elif wz["midPress"]["rating"] >= 65:
            s += f" — they'll keep winning it back high (press {int(round(wz['midPress']['rating']))})"
        bits.append(s)
    else:
        mid_clause = "no midfield dominance either way"

    # -- attacks + flank spike + finishing, comma-joined into one sentence
    clauses = []
    ha, aa = bands["home"]["att"], bands["away"]["att"]
    if ha < 30 and aa < 30:
        clauses.append("two blunt attacks")
    elif ha < 45 and aa < 45:
        clauses.append("two mediocre attacks")
    elif ha >= 60 and aa >= 60:
        clauses.append("two dangerous attacks")
    elif abs(ha - aa) >= 20:
        b, w, bv, wv = (home, away, ha, aa) if ha > aa else (away, home, aa, ha)
        clauses.append(f"{b}'s attack clearly outguns {w}'s ({bv} v {wv})")
    if mid_clause:
        clauses.append(mid_clause)
    spike = max(battles["right_half"] + battles["left_half"],
                key=lambda x: x["delta"], default=None)
    if spike and spike["delta"] >= 25:
        clauses.append(f"the danger spot is {spike['att_team']} down their "
                       f"{spike['att_lane']} (Δ+{spike['delta']})")
    if hfacts and afacts:
        hf, af = hfacts["fin"], afacts["fin"]
        pair = (f"({hfacts['goals']} goals from {hfacts['xg']} xG / "
                f"{afacts['goals']} from {afacts['xg']} xG)")
        if hf <= -1 and af <= -1:
            clauses.append(f"both sides finishing cold {pair}")
        elif hf >= 1 and af >= 1:
            clauses.append(f"both sides finishing hot {pair} — regression looms")
        else:
            for name, f in ((home, hfacts), (away, afacts)):
                if f["fin"] <= -1:
                    clauses.append(f"{name} are finishing cold ({f['goals']} goals from {f['xg']} xG)")
                elif f["fin"] >= 1:
                    clauses.append(f"{name} are finishing hot ({f['goals']} goals from {f['xg']} xG)")
    if clauses:
        bits.append(", ".join(clauses))

    # -- tie it to the model's lean
    if pred:
        p = pred["probabilities"]
        if p["draw"] >= 0.30:
            bits.append(f"the profile of a draw candidate ({round(p['draw'] * 100)}% draw)")
        elif p["home"] >= 0.55:
            bits.append(f"the model makes {home} strong favourites ({round(p['home'] * 100)}%)")
        elif p["away"] >= 0.55:
            bits.append(f"the model makes {away} strong favourites ({round(p['away'] * 100)}%)")

    if not bits:
        return None
    return ". ".join(b[0].upper() + b[1:] for b in bits) + "."


@router.get("/dashboard", response_class=HTMLResponse)
async def picks_page(request: Request, start: Optional[str] = Query(None)):
    data = _cached(("weekly", start), lambda: PredictionService().weekly_picks(start))
    w = data.get("window") or {}
    week_label = f"{w.get('start', '—')} → {w.get('end', '—')}"

    from pathlib import Path
    stamp = Path("data/reports/last_weekly_run.txt")
    last_update = (stamp.read_text(encoding="utf-8").strip().replace("T", " ")[:16]
                   if stamp.exists() else None)

    return templates.TemplateResponse(request, "picks.html",
                                      {"data": data, "week_label": week_label,
                                       "last_update": last_update, "page": "picks"})


@router.get("/dashboard/ledger", response_class=HTMLResponse)
async def ledger_page(request: Request):
    entries = sorted(LedgerService.entries(), key=lambda r: (r["season"], r["week"], r["pick_type"], r["rank"]),
                     reverse=True)
    return templates.TemplateResponse(request, "ledger.html",
                                      {"summary": LedgerService.summary(),
                                       "entries": entries, "page": "ledger"})


@router.get("/dashboard/match", response_class=HTMLResponse)
async def match_page(request: Request, league: str, home: str, away: str):
    zones = _cached(("zones", league),
                    lambda: ZonesEngine(league, ZONES_SOURCE_SEASON).build(persist=False)["teams"])

    battles = None
    headline = None
    bands = None
    if home in zones and away in zones:
        zh, za = zones[home], zones[away]

        from models.zones.zones_config import ZONE_IMPORTANCE

        def band_avg(z, prefix):
            zs = [k for k in z if k.startswith(prefix)]
            w = sum(ZONE_IMPORTANCE[k] for k in zs)
            return round(sum(z[k]["rating"] * ZONE_IMPORTANCE[k] for k in zs) / w, 1)

        bands = {"home": {b: band_avg(zh, b) for b in ("att", "mid", "def")},
                 "away": {b: band_avg(za, b) for b in ("att", "mid", "def")}}

        def verdict(delta, att_team, def_team):
            if delta >= 25:
                return f"{att_team} should create here", "h2"
            if delta >= 10:
                return f"{att_team} edge", "h1"
            if delta <= -25:
                return f"{def_team} shuts this down", "a2"
            if delta <= -10:
                return f"{def_team} edge", "a1"
            return "even contest", "even"

        # one battle per (physical strip x attacking side) + midfield.
        # strips top->bottom are home's L/C/R (home attacks right); the same
        # strip is the away team's R/C/L.
        battles = {"left_half": [], "right_half": []}
        for lane_label, lane in LANES:
            # home attacks this strip (right half of the screen)
            az, dz = f"att{lane}", f"def{MIRROR[lane]}"
            d = round(zh[az]["rating"] - za[dz]["rating"], 1)
            text, cls = verdict(d, home, away)
            battles["right_half"].append({
                "att_team": home, "def_team": away,
                "att_lane": lane_label.lower(), "def_lane": MIRROR[lane].lower(),
                "att_r": zh[az]["rating"], "def_r": za[dz]["rating"],
                "delta": d, "text": text, "cls": cls,
                "tooltip": "; ".join(f"{k} {v}" for k, v in zh[az]["components"].items()),
            })
            # away attacks the same strip (left half of the screen);
            # away's OWN lane name for this strip is the mirror
            aw_lane = MIRROR[lane]
            az2, dz2 = f"att{aw_lane}", f"def{lane}"
            d2 = round(za[az2]["rating"] - zh[dz2]["rating"], 1)
            text2, cls2 = verdict(d2, away, home)
            # color language: blue = home favored, red = away favored.
            # here a positive delta favors AWAY -> flip the class family
            flip = {"h2": "a2", "h1": "a1", "a2": "h2", "a1": "h1", "even": "even"}
            battles["left_half"].append({
                "att_team": away, "def_team": home,
                "att_lane": aw_lane.lower(), "def_lane": lane_label.lower(),
                "att_r": za[az2]["rating"], "def_r": zh[dz2]["rating"],
                "delta": d2, "text": text2, "cls": flip[cls2],
                "tooltip": "; ".join(f"{k} {v}" for k, v in za[az2]["components"].items()),
            })
        # midfield strip: one card per on-the-ball phase + the overall verdict.
        # A team's build-up (midProgress) is opposed by the other side's
        # press (midPress, hunts the ball) and screen (midShield, blocks entries).
        def mid_phase(z_att, z_def, att_team, def_team):
            atk = z_att["midProgress"]["rating"]
            prs, scr = z_def["midPress"]["rating"], z_def["midShield"]["rating"]
            d = round(atk - (prs + scr) / 2.0, 1)
            if d >= 25:
                text = f"{att_team} will play through"
            elif d >= 10:
                text = f"{att_team} edge on the ball"
            elif d <= -25:
                text = f"{def_team} smothers their build-up"
            elif d <= -10:
                text = f"{def_team} edge off the ball"
            else:
                text = "even contest"
            return {"kind": "phase", "att_team": att_team,
                    "atk": atk, "prs": prs, "scr": scr, "delta": d, "text": text}

        ph_home = mid_phase(zh, za, home, away)
        ph_home["cls"] = _delta_class(ph_home["delta"])
        ph_away = mid_phase(za, zh, away, home)
        ph_away["cls"] = flip[_delta_class(ph_away["delta"])]
        dm = round(bands["home"]["mid"] - bands["away"]["mid"], 1)
        overall = {"kind": "verdict",
                   "h": bands["home"]["mid"], "a": bands["away"]["mid"],
                   "delta": dm, "cls": _delta_class(dm),
                   "text": (f"{home} should run midfield" if dm >= 10
                            else f"{away} should run midfield" if dm <= -10
                            else "midfield shared")}
        battles["mid"] = [ph_home, overall, ph_away]

        best_home = max(battles["right_half"], key=lambda b: b["delta"])
        best_away = max(battles["left_half"], key=lambda b: b["delta"])
        headline = {
            "home": f"{home}'s biggest threat: down their {best_home['att_lane']} (Δ{best_home['delta']:+})"
                    if best_home["delta"] >= 10 else f"{home}: no clear attacking edge",
            "away": f"{away}'s reply: down their {best_away['att_lane']} (Δ{best_away['delta']:+})"
                    if best_away["delta"] >= 10 else f"{away}: no clear attacking edge",
        }

    pred = None
    weekly = _cached(("weekly", None), lambda: PredictionService().weekly_picks(None))
    for p in weekly["all_predictions"].get(league, []):
        if p["home"] == home and p["away"] == away:
            pred = p
            break

    facts = _cached(("facts", league), lambda: _team_facts(league))
    shots = _cached(("shots", league), lambda: _team_shots(league))
    shape = _cached(("shape", league), lambda: _team_shape(league))
    badge = _badge_fn(league)

    bottom = None
    if battles:
        bottom = _bottom_line(home, away, zones[home], zones[away], bands, battles,
                              facts["teams"].get(home), facts["teams"].get(away), pred)

    return templates.TemplateResponse(request, "match.html", {
        "league": league, "home": home, "away": away, "bottom": bottom,
        "pred": pred, "battles": battles, "headline": headline, "bands": bands,
        "zones_season": ZONES_SOURCE_SEASON,
        "facts_season": facts["season"],
        "hfacts": facts["teams"].get(home), "afacts": facts["teams"].get(away),
        "hshots": shots.get(home), "ashots": shots.get(away),
        "hshape": shape.get(home), "ashape": shape.get(away),
        "hpizza": _pizza_png(league, home), "apizza": _pizza_png(league, away),
        "hbadge": badge(home), "abadge": badge(away),
        "page": "match",
    })


@router.get("/dashboard/history", response_class=HTMLResponse)
async def history_page(request: Request):
    from services.predictions.history_service import HistoryService
    HistoryService.grade()
    entries = HistoryService.entries()

    def tier_of(r):
        p = max(r["probabilities"].values())
        return "gold" if p >= 0.55 else "silver" if p >= 0.45 else "flip"

    tiers = {}
    for r in entries:
        r["tier"] = tier_of(r)
        if r["status"] == "graded":
            t = tiers.setdefault(r["tier"], [0, 0])
            t[1] += 1
            t[0] += r["outcome_hit"]
    tier_stats = {k: {"hits": v[0], "n": v[1],
                      "rate": round(v[0] / v[1] * 100, 1) if v[1] else None}
                  for k, v in tiers.items()}

    return templates.TemplateResponse(request, "history.html", {
        "s": HistoryService.summary(), "entries": entries,
        "tiers": tier_stats, "page": "history",
    })


@router.get("/dashboard/monkey", response_class=HTMLResponse)
async def monkey_page(request: Request):
    from services.predictions.slip_ledger import SlipLedger
    SlipLedger.grade()
    return templates.TemplateResponse(request, "monkey.html", {
        "m": SlipLedger.monkey(), "page": "monkey",
    })


@router.get("/dashboard/monkey/slip", response_class=HTMLResponse)
async def slip_detail_page(request: Request, window: str):
    from services.predictions.slip_ledger import SlipLedger
    SlipLedger.grade()
    s = SlipLedger.slip_detail(window)
    if not s:
        return HTMLResponse("<p>No slip for that window.</p>", status_code=404)
    return templates.TemplateResponse(request, "slip_detail.html", {"s": s, "page": "monkey"})


@router.get("/dashboard/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request):
    import json
    from collections import defaultdict
    from pathlib import Path

    path = Path("data/reports/backtest_2526_picks.json")
    if not path.exists():
        return HTMLResponse("<p>No backtest report on disk — run scripts/backtest_2526.py</p>")
    data = json.loads(path.read_text(encoding="utf-8"))

    weeks = defaultdict(lambda: {"draws": [], "home_wins": []})
    stats = {}
    for key in ("draws", "home_wins"):
        rows = data[key]
        for r in rows:
            weeks[r["week"]][key].append(r)
        hits = sum(1 for r in rows if r["hit"])
        stats[key] = {"hits": hits, "total": len(rows),
                      "rate": round(hits / len(rows) * 100, 1) if rows else 0}

    prior = None
    p2425 = Path("data/reports/backtest_2425.json")
    if p2425.exists():
        prior = json.loads(p2425.read_text(encoding="utf-8"))

    return templates.TemplateResponse(request, "backtest.html", {
        "weeks": sorted(weeks.items()), "stats": stats, "prior": prior,
        "page": "backtest",
    })
