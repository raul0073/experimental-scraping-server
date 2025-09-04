import json
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
def _safe_name(s: str) -> str:
    return s.replace("/", "-").replace("\\", "-").strip()

def _sanitize_value(v):
    try:
        if v is None:
            return None
        if hasattr(v, "item"):
            return v.item()  # unwrap numpy scalars
        if isinstance(v, (float, int, str, bool)):
            return v
        if isinstance(v, (pd.Series, pd.DataFrame)):
            return v.to_dict()
        if pd.isna(v):  # scalar NaN check only
            return None
    except Exception:
        pass
    return str(v)


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    return _sanitize_value(obj)

def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
