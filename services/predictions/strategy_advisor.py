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


def system_scenarios(legs: List[Dict], k) -> List[Dict]:
    """Exact hit-count table for a Winner form over these legs.

    `k` is a combination SIZE, or a list of them. That generalisation is the
    whole point:

        שיטה K/N   [K]           C(N,K) lines
        טריקסי     [2, 3]        on 3 legs: 3 doubles + 1 treble = 4
        פטנט       [1, 2, 3]     Trixi + 3 singles = 7
        יאנקי      [2, 3, 4]     on 4 legs: 6 + 4 + 1 = 11
        לאקי 15    [1, 2, 3, 4]  Yankee + 4 singles = 15

    🐛 EVERY NAMED FORM USED TO BE DESCRIBED AND ONLY SYSTEMS WERE SCORED.
    The catalog above the module listed Yankee, Lucky 15, Trixi and Patent,
    and `options` printed them with a rough P(return) — but the recommendation
    competed שיטה against שיטה and nothing else, so "chosen over" could only
    ever show systems. Every one of those forms is a SUM OF SYSTEMS over the
    same legs, which means this enumerator could always have priced them; it
    just took one K.

    Enumerates all 2^N hit subsets; per subset, lines won are the combinations
    of every size in `k` lying fully inside the hit set, and the illustrative
    return uses each leg's BREAKEVEN price (1/p — the fair-price floor we
    publish, never a book's number). Aggregated by hit count: P(count), lines
    won, average return as a fraction of total stake. This is what makes 'not
    every win is a gain' visible: with K=2/N=5, two hits pay one line of ten,
    which is a partial refund.
    """
    from itertools import combinations, product
    ks = sorted({k} if isinstance(k, int) else set(k))
    n = len(legs)
    total_lines = sum(len(list(combinations(range(n), j))) for j in ks)
    agg: Dict[int, Dict[str, float]] = {}
    for hits in product((0, 1), repeat=n):
        p = 1.0
        for leg, h in zip(legs, hits):
            p *= leg["prob"] if h else (1 - leg["prob"])
        hit_idx = [i for i, h in enumerate(hits) if h]
        ret = 0.0
        for j in ks:
            for combo in combinations(hit_idx, j):
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
        lines_won = sum(len(list(combinations(range(c), j)))
                        for j in ks if c >= j)
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
        ks = sorted({k} if isinstance(k, int) else set(k))
        return {"title_he": title_he, "title_en": title_en,
                "lines": scen[0]["total_lines"], "legs": legs, "k": k,
                # the combination sizes this form pays on, always a list —
                # [2] is a system, [2,3,4] is a Yankee, and the page should
                # not have to know which of the two it was handed
                "ks": ks, "n": len(legs),
                "scenarios": scen,
                "p_return": sum(s["p"] for s in scen if s["lines_won"] > 0),
                "p_profit": sum(s["p"] for s in scen if s["profit"]),
                "how": how}

    # THE WHOLE CATALOG, NOT JUST SYSTEMS. Every Winner form is a sum of
    # C(N,k) over a set of sizes — a single is k={1} on one leg, an
    # accumulator is k={N} on N, a Yankee is k={2,3,4} on four — so one
    # enumerator prices all of them and they can compete on the same exact
    # P(profit) at breakeven. Before this, four forms were printed in a
    # catalog nobody scored and the recommendation only ever compared systems
    # against systems.
    #
    # (he, en, legs needed, combination sizes, note)
    FORMS = [
        ("בודד", "single — top draw only", 1, [1],
         "one leg, one line. The honest floor: no structure, no dilution, "
         "and the only shape whose return is exactly its leg's fair price."),
        ("כפול", "double — top 2 draws, one line", 2, [2],
         "both must land. One line, biggest multiple per shekel, and nothing "
         "back at 1 of 2."),
        ("טריפל", "treble — top 3 draws, one line", 3, [3],
         "all three. A lottery shape on a draw board: ~3% to land."),
        ("רביעייה", "fourfold — all 4 draws, one line", 4, [4],
         "the accumulator. Everything or nothing."),
        ("טריקסי", "Trixi — top 3 draws, 4 lines", 3, [2, 3],
         "3 doubles + 1 treble. The smallest form that still pays on a "
         "partial board — profit from 2 hits."),
        ("פטנט", "Patent — top 3 draws, 7 lines", 3, [1, 2, 3],
         "Trixi + 3 singles. Softer floor than Trixi: one hit already "
         "returns something, paid for with three extra lines."),
        ("שיטה 2/3", "system 2/3 — top-3 draws, pairs", 3, [2],
         "three draws, every pair a line (3 lines); profit at 2 hits."),
        ("שיטה 2/4", "system 2/4 — 4 draws, pairs only", 4, [2],
         "four draws, every pair a line (6 lines). A draw pair pays ~9-10x "
         "one line against 6 staked — PROFIT already at 2 hits. Highest "
         "profit-frequency shape for this board."),
        ("שיטה 3/4", "system 3/4 — 4 draws, trebles", 4, [3],
         "all trebles of the four (4 lines): nothing below 3 hits, and the "
         "tail is the whole point."),
        ("יאנקי", "Yankee — 4 draws, 11 lines", 4, [2, 3, 4],
         "6 doubles + 4 trebles + 1 fourfold. The standard: money-back zone "
         "at 2 of 4, the tails carry the rest."),
        ("לאקי 15", "Lucky 15 — 4 draws, 15 lines", 4, [1, 2, 3, 4],
         "Yankee + 4 singles — the softest floor, where even 1 of 4 returns "
         "something, bought with four more lines."),
    ]
    pool = [draw_leg(p) for p in draws]
    candidates = [build(he, en, pool[:n], ks, note)
                  for he, en, n, ks, note in FORMS if len(pool) >= n]
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

    # NO MANDATE, NO DEFAULT — THE BEST SHAPE EVERY WEEK, ON THE NUMBERS.
    #
    # This used to pin שיטה 2/4 as the recommendation whatever the board said,
    # and offer everything else as an alternative to swap into on price. The
    # reason was real: ranking crowns a different form most weeks, and a pot
    # that switches instrument between rounds is harder to read. The user has
    # weighed that and chosen the ranking (2026-10-07) — so the bias is gone
    # and the field is sorted on its own merits.
    #
    # RANKED ON P(PROFIT), NOT P(RETURN), and the difference is not small:
    # a שיטה 2/6 can return something 90% of weeks while profiting 28%, and
    # getting 40% of a stake back is not winning. P(return) is carried beside
    # it on every row so the trade stays visible rather than being decided
    # here on the reader's behalf.
    #
    # WHAT THIS COSTS, SAID PLAINLY: at fair prices every structure is EV-0 —
    # they differ in the SHAPE of the distribution, not in expectation. So
    # this is choosing a variance profile, not finding an edge, and the
    # monkey's bankroll now measures "betting the best-looking shape each
    # week" rather than "betting one instrument". That is a weaker claim than
    # the mandate version and the monkey tab has to say so.
    # TIE-BREAK ON FEWER LINES, NOT ON P(RETURN). Ties happen constantly here
    # because several shapes share a profit threshold — this week לאקי 15 and
    # שיטה 2/4 both profit on exactly 39.7% of boards. Breaking that on
    # P(return) crowned the 15-line form over the 6-line one: two and a half
    # times the stake for the SAME chance of ending up ahead, bought with a
    # higher chance of a partial refund. At fair prices every form is EV-0, so
    # the cheaper of two shapes with equal win frequency is strictly the
    # better risk, and P(return) is a comfort rather than a result.
    candidates.sort(key=lambda c: (c["p_profit"], -c["lines"], c["p_return"]),
                    reverse=True)
    slip = candidates[0]
    slip["mandate"] = None
    slip["ranked_on"] = "p_profit"
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
