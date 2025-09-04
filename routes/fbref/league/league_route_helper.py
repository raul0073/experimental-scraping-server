from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from services.fbref.league.fbref_utils import _safe_name


DATA_ROOT = Path("data")
LEAGUE_INIT_DIR = DATA_ROOT / "league_init"



_LEAGUE_DIR_RX = re.compile(r"^(?P<league>.+)-(?P<season>\d{4,})$")  # e.g. ENG-Premier League-2425
_STAT_FILE_RX  = re.compile(r"^team_(?P<stype>[a-z0-9_]+)\.json$", re.I)


@lru_cache(maxsize=256)
def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(str(path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON: {path} ({e})") from e

def _scan_league_dirs() -> List[Dict[str, str]]:
    """Return [{'league': 'ENG-Premier League', 'season': '2425', 'dir': '...'}, ...]"""
    out: List[Dict[str, str]] = []
    if not LEAGUE_INIT_DIR.exists(): return out
    for d in LEAGUE_INIT_DIR.iterdir():
        if not d.is_dir(): continue
        m = _LEAGUE_DIR_RX.match(d.name)
        if not m: continue
        out.append({"league": m.group("league"), "season": m.group("season"), "dir": str(d)})
    return out

def _find_league_dir(league: str, season: Optional[str]) -> Path:
    league = _safe_name(league)
    candidates = [x for x in _scan_league_dirs() if x["league"] == league]
    if not candidates:
        raise FileNotFoundError(f"League not found: {league}")
    if season:
        for c in candidates:
            if c["season"] == str(season):
                return Path(c["dir"])
        raise FileNotFoundError(f"Season not found for league '{league}': {season}")
    # choose latest season (lexicographically OK for same-width numbers like '2425')
    latest = sorted(candidates, key=lambda c: c["season"], reverse=True)[0]
    return Path(latest["dir"])

def _list_stat_types(ldir: Path) -> List[str]:
    stypes: List[str] = []
    for f in ldir.glob("team_*.json"):
        m = _STAT_FILE_RX.match(f.name)
        if m:
            stypes.append(m.group("stype"))
    return sorted(set(stypes))

def _load_stat_file(ldir: Path, stype: str) -> List[Dict[str, Any]]:
    path = ldir / f"team_{stype}.json"
    data = _read_json(path)
    if isinstance(data, list):
        return data
    raise RuntimeError(f"{path} must be a JSON array of team objects")

def _merge_team_metrics(existing: Dict[str, Any], new_metrics: Dict[str, Any]) -> None:
    # Merge into existing['metrics'] (create if missing)
    metrics = existing.setdefault("metrics", {})
    for k, v in (new_metrics or {}).items():
        metrics[k] = v  # last write wins; fine since each file covers different keys

def _index_by_team(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        team = r.get("team")
        if not team:  # skip broken rows
            continue
        # Normalize base shape
        base = out.setdefault(team, {
            "league": r.get("league"),
            "season": r.get("season"),
            "team": team,
            "metrics": {}
        })
        # Many sources already present 'metrics' per row; if not, assume the rest are metrics-like
        if "metrics" in r and isinstance(r["metrics"], dict):
            _merge_team_metrics(base, r["metrics"])
        else:
            # Collect any non-core keys as metrics
            metrics_like = {k: v for k, v in r.items() if k not in {"league", "season", "team"}}
            _merge_team_metrics(base, metrics_like)
    return out