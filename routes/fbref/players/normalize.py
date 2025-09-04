import math
import numpy as np

def sanitize_for_json(obj):
    """
    Recursively convert NaN, inf, -inf to None in dicts/lists.
    Safe for JSON serialization.
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj

def normalize_scores(players: list[dict], key: str = "ranking.performance"):
    scores = []
    for p in players:
        val = p.get("ranking", {}).get("performance")
        if isinstance(val, (int, float)) and not np.isnan(val):
            scores.append(val)

    if not scores:
        return players  # no valid scores

    min_val = min(scores)
    max_val = max(scores)
    range_val = max_val - min_val

    for p in players:
        perf = p.get("ranking", {}).get("performance")
        if perf is None or not isinstance(perf, (int, float)) or np.isnan(perf):
            continue
        if range_val == 0:
            norm = 50.0
        else:
            norm = (perf - min_val) / range_val * 100.0

        # 🧼 clean before inserting
        if np.isnan(norm) or np.isinf(norm):
            continue

        p["ranking"]["normalized"] = round(norm, 2)

    return players