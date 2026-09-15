from __future__ import annotations
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Winner (Toto) form catalog — structures only, never odds. A "system K/N"
# covers every K-combination of N picks; a באנקר (banker) is a fixed leg
# multiplied into EVERY line: fewer lines, every return gated by (and
# boosted by) the banker.
# ---------------------------------------------------------------------------
#   יאנקי (Yankee)      4 picks, 11 lines: 6 doubles + 4 trebles + 1 four-fold
#   לאקי 15 (Lucky 15)  4 picks, 15 lines: Yankee + 4 singles (softest floor)
#   שיטה 2/4            4 picks, 6 lines: doubles only (drip shape)
#   טריקסי (Trixi)      3 picks, 4 lines: 3 doubles + 1 treble
#   פטנט (Patent)       3 picks, 7 lines: Trixi + 3 singles
#   באנקר + שיטה        banker leg × system lines (e.g. banker + 2/4 = 6 triples)
# ---------------------------------------------------------------------------


def system_scenarios(legs: List[Dict], k: int) -> List[Dict]:
    """Exact hit-count table for a Winner שיטה K/N over these legs.

    Enumerates all 2^N hit subsets; per subset, lines won = the K-combos fully
    inside the hit set, and the illustrative return uses each leg's BREAKEVEN
    odds (1/p — the fair-price floor we publish). Aggregated by hit count:
    P(count), lines won, avg return as a fraction of total stake. This is what
    makes 'not every win is a gain' visible: with K=2/N=5, two hits pay one
    line of ten — a partial refund."""
    from itertools import combinations, product
    n = len(legs)
    total_lines = len(list(combinations(range(n), k)))
    agg: Dict[int, Dict[str, float]] = {}
    for hits in product((0, 1), repeat=n):
        p = 1.0
        for leg, h in zip(legs, hits):
            p *= leg["prob"] if h else (1 - leg["prob"])
        hit_idx = [i for i, h in enumerate(hits) if h]
        ret = 0.0
        for combo in combinations(hit_idx, k):
            line = 1.0
            for i in combo:
                line *= 1 / legs[i]["prob"]
            ret += line
        c = len(hit_idx)
        a = agg.setdefault(c, {"p": 0.0, "ret": 0.0})
        a["p"] += p
        a["ret"] += p * ret
    out = []
    for c in sorted(agg):
        p = agg[c]["p"]
        avg_ret_frac = (agg[c]["ret"] / p / total_lines) if p else 0.0
        lines_won = len(list(combinations(range(c), k))) if c >= k else 0
        out.append({"hits": c, "p": p, "lines_won": lines_won,
                    "total_lines": total_lines,
                    "ret_frac": avg_ret_frac,
                    "profit": avg_ret_frac > 1.0})
    return out


def _dist(probs: List[float]) -> List[float]:
    """P(exactly k hits) for independent legs."""
    d = [1.0]
    for p in probs:
        nxt = [0.0] * (len(d) + 1)
        for k, q in enumerate(d):
            nxt[k] += q * (1 - p)
            nxt[k + 1] += q * p
        d = nxt
    return d


def _ge(d: List[float], k: int) -> float:
    return sum(d[k:])


def advise(weekly: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    draws = weekly.get("draw_picks") or []
    if len(draws) < 3:
        return None
    p4 = [p["pick_prob"] for p in draws[:4]]
    p3 = p4[:3]
    d4, d3 = _dist(p4), _dist(p3)
    board_avg = sum(p4) / len(p4)

    # banker candidates: certified in-window favorites (>=55%), strongest
    # first, excluding fixtures already used as draw legs
    draw_fixtures = {(p["home"], p["away"]) for p in draws[:4]}
    bankers: List[Dict[str, Any]] = []
    for lg, preds in (weekly.get("all_predictions") or {}).items():
        for p in preds:
            if p["confidence"] != "normal" or not p.get("in_window"):
                continue
            if (p["home"], p["away"]) in draw_fixtures:
                continue
            fav = max(p["probabilities"], key=p["probabilities"].get)
            prob = p["probabilities"][fav]
            team = p["home"] if fav == "home" else p["away"] if fav == "away" else None
            if team and prob >= 0.55:
                bankers.append({"fixture": f"{p['home']} v {p['away']}", "league": lg,
                                "home": p["home"], "away": p["away"],
                                "team": team, "side": fav, "prob": prob,
                                "tier": p.get("tier", ""), "kickoff": p["kickoff"]})
    bankers.sort(key=lambda b: b["prob"], reverse=True)
    bankers = bankers[:4]
    banker = bankers[0] if bankers else None

    options = [
        {"name": "יאנקי — Yankee (4 draws, 11 lines)",
         "lines": 11, "p_return": _ge(d4, 2), "p_big": _ge(d4, 3),
         "note": "the standard: money-back zone at 2/4, tails at 3-4"},
        {"name": "שיטה 2/4 (4 draws, 6 doubles)",
         "lines": 6, "p_return": _ge(d4, 2), "p_big": _ge(d4, 3),
         "note": "same hit points, ~half the outlay — drip shape, no four-fold jackpot"},
        {"name": "לאקי 15 — Lucky 15 (4 draws + singles, 15 lines)",
         "lines": 15, "p_return": _ge(d4, 1), "p_big": _ge(d4, 3),
         "note": "softest floor — even 1/4 returns something"},
        {"name": "טריקסי — Trixi (top-3 draws, 4 lines)",
         "lines": 4, "p_return": _ge(d3, 2), "p_big": _ge(d3, 3),
         "note": "smallest form for a thin board"},
    ]
    if banker:
        pb = banker["prob"]
        options.append({
            "name": f"באנקר + שיטה 2/4 — banker ({banker['team']}) × 4 draws, 6 lines",
            "lines": 6, "p_return": pb * _ge(d4, 2), "p_big": pb * _ge(d4, 3),
            "note": f"every line multiplied by the banker ({pb:.0%}) — "
                    "aggressive value shape, all-or-nothing on the banker leg"})

    # plain-words recommendation
    board = ("strong" if board_avg >= 0.325 else
             "normal" if board_avg >= 0.305 else "thin")
    strong_banker = banker and banker["prob"] >= 0.65 and banker["tier"] == "gold"
    ok_banker = banker and banker["prob"] >= 0.55

    # THE concrete slip — exact games, exact marks
    def draw_leg(p):
        return {"role": "draw", "mark": "X", "fixture": f"{p['home']} v {p['away']}",
                "home": p["home"], "away": p["away"], "league_full": p["league"],
                "league": p["league"].split("-")[1], "kickoff": p["kickoff"],
                "prob": p["pick_prob"], "breakeven": round(1 / p["pick_prob"], 2)}

    # candidate structures, each scored by EXACT P(profit) at breakeven prices
    # — the structure choice is math, the banker is a priced upgrade, never
    # the default (the user's real slip proved banker pairs dilute the form)
    draw_legs4 = [draw_leg(p) for p in draws[:4]]
    draw_legs3 = [draw_leg(p) for p in draws[:3]]
    def bleg(b):
        return {"role": "banker", "mark": "1" if b["side"] == "home" else "2",
                "fixture": b["fixture"], "home": b["home"], "away": b["away"],
                "league_full": b["league"], "league": b["league"].split("-")[1],
                "team": b["team"], "side": b["side"], "prob": b["prob"],
                "breakeven": round(1 / b["prob"], 2), "kickoff": b.get("kickoff")}

    banker_legs = [bleg(b) for b in bankers]
    banker_leg = banker_legs[0] if banker_legs else None

    def build(title_he, title_en, legs, k, how):
        scen = system_scenarios(legs, k)
        return {"title_he": title_he, "title_en": title_en,
                "lines": scen[0]["total_lines"], "legs": legs, "k": k,
                "scenarios": scen,
                "p_return": sum(s["p"] for s in scen if s["lines_won"] > 0),
                "p_profit": sum(s["p"] for s in scen if s["profit"]),
                "how": how}

    candidates = [
        build("שיטה 2/4", "system 2/4 — 4 draws, pairs only", draw_legs4, 2,
              "four draws, every pair a line (6 lines). A draw pair pays ~9-10x one "
              "line against 6 staked — PROFIT already at 2 hits. Highest "
              "profit-frequency shape for this board."),
        build("שיטה 2/3", "system 2/3 — top-3 draws", draw_legs3, 2,
              "three draws, every pair a line (3 lines); profit at 2 hits."),
    ]
    if banker_leg:
        candidates.append(build(
            "שיטה 2/5", "system 2/5 — banker counted as a selection",
            [banker_leg] + draw_legs4, 2,
            f"the banker becomes a 5th selection (10 lines). Banker-pairs pay little "
            f"(~{banker_leg['breakeven'] * 3.1:.1f}x a line) so 2 hits is only a partial "
            f"refund — profit starts at 3 hits. Take this over 2/4 ONLY when the book "
            f"prices {banker_leg['team']} well above its fair {banker_leg['breakeven']} "
            f"(check your slip's 1/X rows against the pair values here)."))
        candidates.append(build(
            "שיטה 3/5", "system 3/5 — banker + 4 draws, trebles", [banker_leg] + draw_legs4, 3,
            "all trebles of the five (10 lines): nothing below 3 hits, bigger tails — "
            "a variance shape, not a frequency shape."))
    if len(banker_legs) >= 2:
        two = banker_legs[:2]
        candidates.append(build(
            "שיטה 2/6", "system 2/6 — 2 bankers + 4 draws, pairs",
            two + draw_legs4, 2,
            "15 lines over six selections; banker-pairs pay little, draw-pairs carry it."))
        candidates.append(build(
            "שיטה 3/6", "system 3/6 — 2 bankers + 4 draws, trebles",
            two + draw_legs4, 3,
            "20 lines; profit needs bankers PLUS draws landing together."))
    if len(banker_legs) >= 3:
        three = banker_legs[:3]
        candidates.append(build(
            "שיטה 3/7", "system 3/7 — 3 bankers + 4 draws, trebles",
            three + draw_legs4, 3,
            "35 lines; hit-frequency from bankers, payout still needs draws."))
        candidates.append(build(
            "שיטה 4/7", "system 4/7 — 3 bankers + 4 draws, quads",
            three + draw_legs4, 4,
            "35 lines, tail-hunting shape: nothing below 4 hits."))

    # PURE-FAVORITE forms are deliberately NOT candidates (mandate decision,
    # user sign-off 2026-09-15). At fair prices every structure is EV-0, so the
    # choice is about SHAPE: enumerated over the 09-16 legs, a favorites 2/4
    # risks 60 to win at most +64 and needs 3 of 4, while the draw 2/4 risks
    # the same 60 to win up to +499 and pays at 2 of 4 — the threshold the
    # product is actually played for. Those same favorites are already
    # measured, cleanly and as singles, by the GOLD pot; a favorites system
    # is duplicate exposure in a costume.

    # MANDATE: the slip pot bets ONE instrument — the draw system. Ranking by
    # P(profit) (the old rule) always crowned the highest-frequency shape,
    # which is how the pot ended up switching products between rounds. The
    # default is now fixed by mandate; everything else is an ALTERNATIVE the
    # user may swap into on PRICE, which is their department.
    primary = "שיטה 2/4" if len(draw_legs4) == 4 else "שיטה 2/3"
    others = [c for c in candidates if c["title_he"] != primary]
    others.sort(key=lambda c: (c["p_profit"], c["p_return"]), reverse=True)
    slip = next((c for c in candidates if c["title_he"] == primary), candidates[0])
    slip["mandate"] = "draws"
    candidates = [slip] + others
    slip["alternatives"] = [
        {"title_he": c["title_he"], "title_en": c["title_en"], "lines": c["lines"],
         "p_return": c["p_return"], "p_profit": c["p_profit"]}
        for c in candidates[1:]]

    lines = []
    lines.append(f"The draw board is {board} this week (top-4 average "
                 f"{board_avg:.1%} against a ~32% ceiling).")
    lines.append(f"MANDATE: this pot bets one instrument — the draw system. "
                 f"{slip['title_he']} ({slip['p_profit']:.0%} profit-weeks) is the "
                 f"default every round, not a weekly beauty contest: at fair prices "
                 f"all shapes are EV-0, and the draw system is the one that pays at "
                 f"2 of 4 with a real tail (a draw pair returns ~9-10x a line). "
                 f"Pure-favorite forms are off-mandate — they need 3 of 4 to profit, "
                 f"cap out near the stake, and duplicate the GOLD pot, which already "
                 f"measures those favorites as singles.")
    if banker:
        lines.append(
            f"Bankers ({', '.join(f'{b['team']} {b['prob']:.0%}' for b in bankers)}) "
            f"are a PRICE tool, not a default: upgrade to a banker form only when the "
            f"book prices the banker leg clearly above its fair value — compare your "
            f"slip's banker-pair rows to the pair values in the table.")
    if board == "thin":
        lines.append("Thin board: the 2/3 on the top-3 (or sitting out) beats forcing four draws.")
    lines.append("Check each leg's offered odds against its breakeven; swap alternates "
                 "when their price clears. Prices and stakes are yours — this is "
                 "probability math only.")

    return {"board": board, "board_avg": round(board_avg, 4), "banker": banker,
            "slip": slip, "options": options, "text": " ".join(lines)}
