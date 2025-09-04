import re
import json
import time
import unicodedata
from pathlib import Path
from random import choice, uniform
from typing import Optional, Dict

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ------------------ Constants ------------------

BASE = "https://fbref.com"
INDEX = f"{BASE}/en/players"
SEARCH = f"{BASE}/search/search.fcgi?search="
CACHE_DIR = Path("data/fbref/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

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

def _fetch_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=choice(USER_AGENTS))
        page = context.new_page()
        page.goto(url, timeout=60000)
        html = page.content()
        browser.close()
        return html

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
            break  # stop after first usable method

    return max(candidates, key=lambda c: c["score"]) if candidates else None

# ------------------ Player Page Parsing ------------------

def parse_player_meta(html: str) -> Dict:
    soup = BeautifulSoup(html, "lxml")
    position_text, foot, profile_img = None, None, None

    # --- profile image ---
    img = soup.select_one("div.media-item img")
    if img and img.has_attr("src"):
        profile_img = img["src"]

    # --- position + foot ---
    for p in soup.select("#meta p"):
        txt = p.get_text(" ", strip=True)
        if "Position:" in txt:
            if "Footed:" in txt:
                position_text = txt.split("Position:", 1)[1].split("Footed:")[0].strip()
                foot = txt.split("Footed:")[1].strip()
            else:
                position_text = txt.split("Position:", 1)[1].strip()

    return {
        "position_text": position_text,
        "foot": foot,
        "profile_img": profile_img
    }

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

        # --- overwrite player fields ---
        player["fbref_id"] = resolved["id"]
        player["fbref_url"] = resolved["url"]
        player["position_text"] = meta.get("position_text")
        player["foot"] = meta.get("foot")
        player["role"] = meta.get("position_text")
        player["profile_img"] = meta.get("profile_img")

        # --- write after each player ---
        team_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"✅ {player['name']} → {resolved['id']} | {meta.get('position_text')} | {meta.get('foot')} | {meta.get('profile_img')}")

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


if __name__ == "__main__":
    # 👇 choose one of these:
    # 1) Single league
    enrich_league(ROOT_DIR / "ENG-Premier League")

    # 2) Or all leagues
    # enrich_all(ROOT_DIR)


