"""One-time (idempotent) team-crest fetcher.

Downloads each 26/27 team's badge from TheSportsDB's free API into
static/logos/<league>/<team>.png and writes static/logos/manifest.json
mapping league -> team -> served path. Teams it can't match just stay out
of the manifest — the dashboard renders a monogram chip for those, so a
miss is cosmetic, never a broken image.

Usage: .venv/Scripts/python scripts/fetch_team_logos.py [--season 2627]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.fbref.fbref_types import LEAGUE_NAME_MAP
from services.fbref.fixtures.fixtures_service import FixturesService
from services.fbref.league.fbref_utils import _safe_name

API = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={}"
OUT = Path("static/logos")
UA = {"User-Agent": "Mozilla/5.0 (predictor-dashboard; personal use)"}

COUNTRY = {"ENG-Premier League": "England", "ESP-La Liga": "Spain",
           "ITA-Serie A": "Italy", "GER-Bundesliga": "Germany",
           "FRA-Ligue 1": "France"}

# TheSportsDB competition ids (fixed) — for league crests in dashboard tables
LEAGUE_IDS = {"ENG-Premier League": 4328, "ESP-La Liga": 4335, "ITA-Serie A": 4332,
              "GER-Bundesliga": 4331, "FRA-Ligue 1": 4334}
SLEEP_S = 2.5  # free key is ~30 req/min; 1.2s tripped 429s

# fbref canonical name -> TheSportsDB search term
ALIASES = {
    "Manchester Utd": "Manchester United", "Newcastle Utd": "Newcastle United",
    "Nott'ham Forest": "Nottingham Forest", "Nottingham": "Nottingham Forest",
    "Tottenham": "Tottenham Hotspur",
    "West Ham": "West Ham United", "Wolves": "Wolverhampton Wanderers",
    "Brighton": "Brighton and Hove Albion", "Leeds United": "Leeds United",
    "Betis": "Real Betis", "Athletic Club": "Athletic Bilbao",
    "Atlético Madrid": "Atletico Madrid", "Alavés": "Deportivo Alaves",
    "Cádiz": "Cadiz", "Leganés": "Leganes", "Almería": "Almeria",
    "Inter": "Inter Milan", "Milan": "AC Milan", "Roma": "AS Roma",
    "Lazio": "SS Lazio", "Napoli": "SSC Napoli",
    "Gladbach": "Borussia Monchengladbach", "Leverkusen": "Bayer Leverkusen",
    "Dortmund": "Borussia Dortmund", "Eint Frankfurt": "Eintracht Frankfurt",
    "St. Pauli": "St Pauli", "Köln": "FC Koln", "Mainz 05": "Mainz",
    "Hoffenheim": "TSG Hoffenheim", "Stuttgart": "VfB Stuttgart",
    "Wolfsburg": "VfL Wolfsburg", "Augsburg": "FC Augsburg",
    "Werder Bremen": "Werder Bremen", "Union Berlin": "Union Berlin",
    "Hamburger SV": "Hamburg", "Heidenheim": "FC Heidenheim",
    "PSG": "Paris Saint Germain", "Marseille": "Olympique Marseille",
    "Lyon": "Olympique Lyonnais", "Saint-Étienne": "Saint-Etienne",
    "Brest": "Stade Brestois", "Le Havre": "Le Havre AC",
    "Lens": "RC Lens", "Lille": "Lille OSC", "Nice": "OGC Nice",
    "Rennes": "Stade Rennais", "Strasbourg": "RC Strasbourg",
    "Toulouse": "Toulouse FC", "Nantes": "FC Nantes", "Angers": "Angers",
    "Auxerre": "AJ Auxerre", "Metz": "FC Metz", "Lorient": "FC Lorient",
    "Monaco": "Monaco", "Paris FC": "Paris FC",
}


def _get(url: str, timeout: int = 30) -> bytes:
    """GET with one long backoff-retry on 429 (free-key rate limit)."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        print("     ...429, backing off 70s", flush=True)
        time.sleep(70)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()


def _get_json(url: str):
    return json.loads(_get(url, timeout=20).decode("utf-8"))


def _pick(teams, query: str, country: str):
    cands = [t for t in (teams or []) if (t.get("strSport") or "") == "Soccer"]
    if not cands:
        return None
    local = [t for t in cands if (t.get("strCountry") or "") == country]
    pool = local or cands
    ql = query.lower()
    for t in pool:
        names = [t.get("strTeam") or ""] + (t.get("strAlternate") or "").split(",")
        if any(ql == n.strip().lower() for n in names):
            return t
    return pool[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="2627")
    args = ap.parse_args()

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    misses = []

    for league in LEAGUE_NAME_MAP:
        fx = FixturesService.load(league, args.season)
        if not fx:
            print(f"WARN {league}: no fixtures on disk", flush=True)
            continue
        teams = sorted({m["home_team"] for m in fx["matches"]})
        lg_map = manifest.setdefault(league, {})
        for team in teams:
            dest = OUT / _safe_name(league) / f"{_safe_name(team)}.png"
            if team in lg_map and dest.exists():
                continue
            query = ALIASES.get(team, team)
            try:
                data = _get_json(API.format(urllib.parse.quote(query)))
                hit = _pick(data.get("teams"), query, COUNTRY[league])
                url = (hit or {}).get("strTeamBadge") or (hit or {}).get("strBadge")
                if not url:
                    raise LookupError("no badge in result")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(_get(url))
                lg_map[team] = f"/static/logos/{_safe_name(league)}/{_safe_name(team)}.png"
                print(f"OK   {league} :: {team}  ({hit.get('strTeam')})", flush=True)
            except Exception as e:
                misses.append(f"{league} :: {team} ({e})")
                print(f"MISS {league} :: {team}: {e}", flush=True)
            time.sleep(SLEEP_S)

    # competition crests for the dashboard tables
    lg_badges = manifest.setdefault("_leagues", {})
    for league, lid in LEAGUE_IDS.items():
        dest = OUT / "leagues" / f"{_safe_name(league)}.png"
        if league in lg_badges and dest.exists():
            continue
        try:
            data = _get_json(f"https://www.thesportsdb.com/api/v1/json/3/lookupleague.php?id={lid}")
            row = (data.get("leagues") or [{}])[0]
            url = row.get("strBadge") or row.get("strLogo")
            if not url:
                raise LookupError("no badge")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_get(url))
            lg_badges[league] = f"/static/logos/leagues/{_safe_name(league)}.png"
            print(f"OK   league crest :: {league}", flush=True)
        except Exception as e:
            misses.append(f"league {league} ({e})")
            print(f"MISS league {league}: {e}", flush=True)
        time.sleep(SLEEP_S)

    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nmanifest: {sum(len(v) for v in manifest.values())} logos -> {manifest_path}")
    if misses:
        print("misses (monogram fallback will be used):")
        for m in misses:
            print("  " + m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
