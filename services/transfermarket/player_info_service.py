import re
import json
import time
import unicodedata
from pathlib import Path
from random import choice, uniform
from typing import Literal, Optional, Dict

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ------------------ Constants ------------------
RoleType = Literal["GK", "CB", "FB", "DM", "CM", "AM", "W", "CF", "OTHER"]
BASE = "https://fbref.com"
INDEX = f"{BASE}/en/players"
SEARCH = f"{BASE}/search/search.fcgi?search="
CACHE_DIR = Path("data/fbref/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COMPOUND_ROLES_FILE = Path("data/fbref/compound_roles.json")

# ------------------ Constants ------------------
DEFAULT_COMPOUND_MAP = {
    "CB-FB,RIGHT": "RB",
    "CB-FB,LEFT": "LB",
    "AM": "AM",
    "CM-DM-WM": "CM",
    "CB": "CB",
    "CB,LEFT": "LCB",
    "CB,RIGHT": "LCB",
    "DM,RIGHT" :"RWB",
    "DM,LEFT" :"LWB",
    "CM-DM": "DM",
    "AM-CM-WM": "AM",
    "FB": "FB",
    "AM-CM-DM-WM": "CM",
    "AM-WM": "W",
    "CB-CM-DM": "CB",
    "WM": "W",
    "AM-CM": "AM",
    "AM-CM-DM": "CM",
    "AM,RIGHT": "RW",
    "AM,LEFT": "LW",
    "AM-WM,RIGHT": "RW",
    "AM-WM,LEFT": "LW",
    "WM-AM,RIGHT": "LW",
    "WM-AM,LEFT": "RW",
    "GK": "GK",
    "FW-MF": "W",
    "DF-MF": "DM",
    "DM-FB-WM,RIGHT" : "RWB",
    "DM-FB-WM,LEFT" : "LWB"
}

SIMPLE_ROLE_MAP = {
    "GK": "GK",
    "CB": "CB",
    "FB": "FB",
    "DM": "DM",
    "CM": "CM",
    "AM": "AM",
    "W": "W",
    "CF": "CF"
}

FALLBACK_MAP = {
    "GK": "GK",
    "DF": "CB",
    "MF": "CM",
    "FW,MF": "AM",
    "MF,FW": "AM",
    "FW": "CF"
}

# ------------------ Logging ------------------
def log(msg: str):
    print(f"[ROLE INFER] {msg}")



USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0",
]

# ------------------ Utils ------------------
def _ascii(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _normalize(s: str) -> str:
    return re.sub(r"[^a-z\s]", "", _ascii(s).lower()).strip()

def _bucket_prefix(name: str) -> str:
    parts = name.strip().split()
    return _normalize(parts[-1])[:2] if parts else ""

def _cache_read(path: Path) -> Optional[str]:
    return path.read_text("utf-8") if path.exists() else None

def _cache_write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")

def clean_text(s: str) -> str:
    """Uppercase, remove unicode/zero-width spaces, normalize commas, strip."""
    if not s:
        return ""
    s = s.replace("▪", "")
    s = re.sub(r"[\u200b\u00A0]", "", s)  # zero-width & non-breaking spaces
    s = re.sub(r"\s*,\s*", ",", s)        # normalize commas
    s = re.sub(r"\s+", "-", s)            # normalize internal spaces as dash
    return s.upper().strip()

def _fetch_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=choice(USER_AGENTS))
        page = context.new_page()
        page.goto(url, timeout=60000)
        html = page.content()
        browser.close()
        return html

# ------------------ Compound Role Handling ------------------
def load_compound_map() -> Dict[str, str]:
    if COMPOUND_ROLES_FILE.exists():
        return json.loads(COMPOUND_ROLES_FILE.read_text("utf-8"))
    else:
        COMPOUND_ROLES_FILE.write_text(json.dumps(DEFAULT_COMPOUND_MAP, indent=2, ensure_ascii=False))
        return DEFAULT_COMPOUND_MAP.copy()

def save_new_compound_candidate(key: str):
    key = key.strip().upper()
    compound_map = load_compound_map()
    if key not in compound_map:
        compound_map[key] = None
        COMPOUND_ROLES_FILE.write_text(json.dumps(compound_map, indent=2, ensure_ascii=False))
        print(f"🆕 Added new compound role candidate: {key}")

# ------------------ Infer Role ------------------
def infer_role(position_text: str, position: str = None, compound_map: Optional[Dict[str, str]] = None) -> str:
    position_text_raw = position_text or ""
    position_raw = position or ""
    compound_map = compound_map or DEFAULT_COMPOUND_MAP

    print(f"[ROLE INFER] Starting role inference. position_text='{position_text_raw}', position='{position_raw}'")

    text = clean_text(position_text_raw)
    position_clean = clean_text(position_raw)

    # 1️⃣ Check parentheses first
    paren_match = re.search(r"\((.*?)\)", text)
    if paren_match:
        inner_text = paren_match.group(1)
        print(f"[ROLE INFER] Found parentheses content: '{inner_text}'")

        # Lookup full inner text first
        mapped_role = compound_map.get(inner_text)
        print(f"[ROLE INFER] Trying full compound map: '{inner_text}' → {mapped_role}")

        if not mapped_role:
            # Try just role part before any comma
            role_part = inner_text.split(",")[0]
            mapped_role = compound_map.get(role_part)
            print(f"[ROLE INFER] Trying role part only: '{role_part}' → {mapped_role}")

        if mapped_role:
            # Handle side info if role is FB/W/AM
            side_part = None
            if "," in inner_text:
                side_part = inner_text.split(",")[1]
            if mapped_role in ("FB", "W", "AM") and side_part:
                side_letter = side_part[0]
                if mapped_role == "FB":
                    mapped_role = "RB" if side_letter == "R" else "LB"
                if mapped_role == "W":
                    mapped_role = "RW" if side_letter == "R" else "LW"
                if mapped_role == "AM":
                    mapped_role = "RW" if side_letter == "R" else "LW"
            print(f"[ROLE INFER] Role determined from parentheses: {mapped_role}")
            return mapped_role

        # Fallback dash split in parentheses
        for part in role_part.split("-"):
            if part in SIMPLE_ROLE_MAP:
                print(f"[ROLE INFER] Fallback dash split: '{part}' → {SIMPLE_ROLE_MAP[part]}")
                return SIMPLE_ROLE_MAP[part]

    # 2️⃣ Try main text outside parentheses
    main_roles = text.split("(")[0].split("-")
    for r in main_roles:
        if r in SIMPLE_ROLE_MAP:
            print(f"[ROLE INFER] Main text match: '{r}' → {SIMPLE_ROLE_MAP[r]}")
            return SIMPLE_ROLE_MAP[r]

    # 3️⃣ Fallback using original position field
    if position_clean in FALLBACK_MAP:
        fallback_role = FALLBACK_MAP[position_clean]
        print(f"[ROLE INFER] Using FALLBACK_MAP: '{position_clean}' → {fallback_role}")
        return fallback_role

    # 4️⃣ Nothing found
    print("[ROLE INFER] No mapping found → returning 'NA'")
    return "NA"

# ------------------ Player Resolver ------------------
def resolve_player(full_name: str, team_hint: Optional[str] = None, reuse_cache: bool = True) -> Optional[Dict]:
    target = _normalize(full_name)
    prefix = _bucket_prefix(full_name)
    if not prefix:
        return None

    candidates = []
    urls = [
        (f"{INDEX}/{prefix}/", CACHE_DIR / f"players_{prefix}.html"),
        (f"{SEARCH}{'+'.join(full_name.split())}", CACHE_DIR / f"search_{prefix}.html")
    ]

    for url, cache_path in urls:
        html = _cache_read(cache_path) if reuse_cache else None
        if html is None:
            try:
                html = _fetch_html(url)
                _cache_write(cache_path, html)
                time.sleep(uniform(1.5, 3.5))
            except Exception as e:
                print(f"❌ Failed to fetch {url}: {e}")
                continue

        soup = BeautifulSoup(html, "lxml")
        for p in soup.select("p"):
            a = p.select_one("a[href^='/en/players/']")
            if not a:
                continue
            name = a.text.strip()
            if _normalize(name) != target:
                continue

            href = a["href"]
            pid = href.split("/")[3] if len(href.split("/")) >= 4 else None
            if not pid:
                continue

            context = p.get_text(" ", strip=True).lower()
            score = 1
            if team_hint and _normalize(team_hint) in context:
                score += 1

            candidates.append({
                "id": pid,
                "url": BASE + href,
                "name": name,
                "score": score,
                "context": context
            })

        if candidates:
            break

    return max(candidates, key=lambda c: c["score"]) if candidates else None

# ------------------ Player Page Parsing ------------------
def parse_player_meta(html: str) -> Dict:
    soup = BeautifulSoup(html, "lxml")
    position_text, foot, profile_img = None, None, None

    img = soup.select_one("div.media-item img")
    if img and img.has_attr("src"):
        profile_img = img["src"]

    for p in soup.select("#meta p"):
        txt = p.get_text(" ", strip=True)
        if "Position:" in txt:
            if "Footed:" in txt:
                position_text = txt.split("Position:", 1)[1].split("Footed:")[0].strip()
                foot = txt.split("Footed:")[1].strip()
            else:
                position_text = txt.split("Position:", 1)[1].strip()

    player_365_stats = parse_player_365_stats(soup)

    return {
        "position_text": position_text,
        "foot": foot,
        "profile_img": profile_img,
        "player_365_stats": player_365_stats
    }

def parse_player_365_stats(soup) -> Dict:
    stats = {"per90": {}, "percentiles": {}, "position_pool": None}
    table = soup.find("table", {"id": re.compile(r"^scout_summary_")})
    if not table:
        return stats

    rows = table.select("tbody tr")
    for row in rows:
        stat_name = row.find("th", {"data-stat": "statistic"})
        per90 = row.find("td", {"data-stat": "per90"})
        perc = row.find("td", {"data-stat": "percentile"})
        if not stat_name or not per90 or not perc:
            continue

        name = stat_name.get_text(strip=True)
        per90_val = per90.get("csk")
        perc_val = perc.get("csk")

        if per90_val:
            try:
                stats["per90"][name] = float(per90_val)
            except ValueError:
                pass
        if perc_val:
            try:
                stats["percentiles"][name] = int(float(perc_val))
            except ValueError:
                pass

        if not stats["position_pool"]:
            endpoint = perc.get("data-endpoint")
            if endpoint and "pos_title=" in endpoint:
                pool = re.search(r"pos_title=([^&]+)", endpoint)
                if pool:
                    stats["position_pool"] = pool.group(1)

    return stats

# ------------------ Main Enrichment ------------------
ROOT_DIR = Path("data/players")

def enrich_team(team_file: Path):
    data = json.loads(team_file.read_text("utf-8"))
    players = data["players"]

    for player in players:
        print(f"🔎 Resolving {player['name']} ({data['team']})...")

        resolved = resolve_player(player["name"], team_hint=data["team"])
        if not resolved:
            print(f"❌ Could not resolve {player['name']}")
            continue

        html = _fetch_html(resolved["url"])
        meta = parse_player_meta(html)

        player["fbref_id"] = resolved["id"]
        player["fbref_url"] = resolved["url"]
        player["position_text"] = meta.get("position_text")
        player["foot"] = meta.get("foot")
        player["role"] = infer_role(
        meta.get("position_text"),  # scraped text
        player.get("position")      # JSON position
    )
        player["profile_img"] = meta.get("profile_img")
        player["player_365_stats"] = meta.get("player_365_stats")

        # Save after each player
        team_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"✅ {player['name']} → {player['role']} | {player['foot']} | 365 stats: {len(player['player_365_stats']['per90'])} entries")

    print(f"💾 Final save done → {team_file}")

def enrich_league(league_dir: Path):
    for team_file in league_dir.glob("*.json"):
        print(f"\n⚽ Processing team file: {team_file.name}")
        enrich_team(team_file)

def enrich_all(root: Path):
    for league_dir in root.iterdir():
        if league_dir.is_dir():
            print(f"\n🏆 League: {league_dir.name}")
            enrich_league(league_dir)

def enrich_player_by_url(root_dir: Path, player_name: str, fbref_url: str, team_name: str):
    """
    Enrich a single player by FBref URL, updates JSON in-place.
    Compatible with fix_incomplete_players().
    """
    team_file = root_dir / f"{team_name}.json"
    data = json.loads(team_file.read_text("utf-8"))
    players = data.get("players", [])

    # Find the player
    player = next((p for p in players if p.get("name") == player_name), None)
    if not player:
        print(f"❌ Player {player_name} not found in {team_file}")
        return

    print(f"🔎 Fetching FBref data for {player_name} → {fbref_url}")
    html = _fetch_html(fbref_url)
    meta = parse_player_meta(html)

    player["fbref_id"] = fbref_url.split("/")[3] if len(fbref_url.split("/")) >= 4 else None
    player["fbref_url"] = fbref_url
    player["position_text"] = meta.get("position_text")
    player["foot"] = meta.get("foot")
    player["role"] = infer_role(meta.get("position_text"), player.get("position"))
    player["profile_img"] = meta.get("profile_img")
    player["player_365_stats"] = meta.get("player_365_stats")

    # Save after enrichment
    team_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {player_name} enriched → {player['role']} | {player['foot']} | 365 stats: {len(player['player_365_stats']['per90'])} entries")

# ------------------ Diagnostic & Interactive Fix ------------------
def log_incomplete_players(team_file: Path):
    """Logs all players in a team JSON missing critical FBref enrichment data."""
    data = json.loads(team_file.read_text("utf-8"))
    players = data.get("players", [])
    missing_players = []

    required_keys = [
        "fbref_id",
        "fbref_url",
        "position_text",
        "foot",
        "profile_img",
        "player_365_stats",
        "role"
    ]

    for player in players:
        missing = [k for k in required_keys if k not in player or not player[k]]
        if missing:
            missing_players.append((player.get("name", "UNKNOWN"), missing))

    if not missing_players:
        print(f"✅ All players in {team_file.stem} are fully enriched.")
        return []

    print(f"⚠️ Players missing data in {team_file.stem}:")
    for name, keys in missing_players:
        print(f" - {name}: missing {keys}")
    return missing_players


def fix_incomplete_players(team_file: Path):
    """
    Auto-enrich all players in a team JSON missing critical FBref data.
    If a player cannot be resolved automatically, prompts user to input a manual FBref URL.
    """
    data = json.loads(team_file.read_text("utf-8"))
    players = data.get("players", [])

    required_keys = [
        "fbref_id",
        "fbref_url",
        "position_text",
        "foot",
        "profile_img",
        "player_365_stats",
        "role"
    ]

    missing_players = log_incomplete_players(team_file)
    if not missing_players:
        return

    for player_name, missing_keys in missing_players:
        player = next(p for p in players if p.get("name") == player_name)
        print(f"\n🔧 Fixing player: {player_name} (missing {missing_keys})")

        # 1️⃣ Use existing FBref URL if present
        fbref_url = player.get("fbref_url")
        if fbref_url:
            enrich_player_by_url(team_file.parent, player_name, fbref_url, team_name=team_file.stem)
            continue

        # 2️⃣ Try automatic resolution
        resolved = resolve_player(player_name, team_hint=team_file.stem)
        if resolved:
            enrich_player_by_url(team_file.parent, player_name, resolved["url"], team_name=team_file.stem)
            continue

        # 3️⃣ Manual URL fallback
        manual_url = input(f"❌ Could not automatically resolve {player_name}. Enter FBref URL (or leave blank to skip): ").strip()
        if manual_url:
            enrich_player_by_url(team_file.parent, player_name, manual_url, team_name=team_file.stem)
        else:
            print(f"⚠️ Skipped {player_name}, missing data remains.")

    print(f"\n💾 All missing players in {team_file.stem} processed.")
    
    
# ------------------ Entry ------------------
if __name__ == "__main__":
    # enrich_league(ROOT_DIR / "ITA-Serie A")
    # List of specific team files you want to process
    teams_to_process = [
        ROOT_DIR / "ITA-Serie A" / "Atalanta.json",

        # Add more teams here if needed
    ]

    for team_file in teams_to_process:
        if not team_file.exists():
            print(f"⚠️ Team file not found: {team_file}")
            continue

        print(f"\n🏟️ Processing team: {team_file.stem}")

        # Step 1: Diagnostic
        missing_players = log_incomplete_players(team_file)

        # Step 2: Interactive/manual fix
        if missing_players:
            fix_incomplete_players(team_file)
        else:
            print(f"✅ {team_file.stem} is already fully enriched.")