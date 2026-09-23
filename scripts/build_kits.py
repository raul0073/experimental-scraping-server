"""A shirt and shorts colour for every club, read off its crest.

WHY THE CREST. A kit colour table written by hand is accurate and is also a
hundred rows of manual research once the other four leagues land, out of date
the moment anyone changes a sponsor. A crest is already on disk for every
club in every league, and the colour a club is ABOUT is the colour of its
badge — Arsenal red, Chelsea blue, Wolves gold. So the badge is read and the
handful it gets wrong are corrected by hand.

WHERE IT GETS THINGS WRONG, and why an overrides file is not an admission of
defeat: a badge is not a kit. Spurs play in white and their crest is navy.
Clubs whose badge is mostly a white shield lose their real colour to the
background filter. Those are a handful per league, they are stable for years,
and one line each in data/config/kit_overrides.json fixes them permanently.

HOW THE COLOURS ARE PICKED. Not "the most common pixel": crests are mostly
outline and background, so the modal colour of a badge is very often white or
black. Instead pixels are binned coarsely, transparent and near-neutral ones
are set aside, and the ranking is by COUNT WEIGHTED BY SATURATION — which is
what makes a badge's identity colour win over the white it sits on. Shorts
are the next bin far enough away in hue to be a different colour, and if
there isn't one they fall back to the club's own neutral.

Writes data/web/kits/{league}.json and the served copy.

Usage: .venv/Scripts/python.exe scripts/build_kits.py
"""
from __future__ import annotations

import argparse
import colorsys
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGOS = ROOT / "web" / "public" / "logos"
OUT = ROOT / "data" / "web" / "kits"
PUB = ROOT / "web" / "public" / "data" / "kits"
OVERRIDES = ROOT / "data" / "config" / "kit_overrides.json"

BINS = 6            # per channel, so 216 buckets — coarse enough that
                    # anti-aliased edges fall in with the colour they edge
MIN_ALPHA = 200     # a badge's own pixels, not its soft edge
HUE_APART = 0.10    # 36 degrees: far enough to read as a different colour


def slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def hsv(rgb: tuple[int, int, int]):
    return colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


def hexof(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def palette(path: Path) -> list[tuple[tuple[int, int, int], float, float]]:
    """Every colour in a crest, as (mean rgb, pixels, saturation-weighted)."""
    im = Image.open(path).convert("RGBA")
    if max(im.size) > 200:                     # crests are small; keep it cheap
        im.thumbnail((200, 200))
    buckets: dict[tuple, list] = defaultdict(lambda: [0, 0, 0, 0])
    for r, g, b, a in im.getdata():
        if a < MIN_ALPHA:
            continue
        key = (r * BINS // 256, g * BINS // 256, b * BINS // 256)
        acc = buckets[key]
        acc[0] += r
        acc[1] += g
        acc[2] += b
        acc[3] += 1

    out = []
    for acc in buckets.values():
        n = acc[3]
        rgb = (acc[0] // n, acc[1] // n, acc[2] // n)
        h, s, v = hsv(rgb)
        # A badge is mostly outline and background, so ranking on count alone
        # returns white for half the league. Weighting by saturation asks
        # "which colour is this club" rather than "which pixel is commonest",
        # and the v term keeps a dark outline from standing in for a kit.
        out.append((rgb, n, n * (s ** 1.8) * (0.35 + 0.65 * v)))
    out.sort(key=lambda t: -t[2])
    return out


def kit(path: Path) -> dict:
    cols = palette(path)
    if not cols:
        return {"shirt": "#e8edf1", "shorts": "#1b2733", "from": "empty"}

    shirt = cols[0][0]
    h1, s1, _ = hsv(shirt)

    shorts = None
    for rgb, _, _ in cols[1:]:
        h2, s2, v2 = hsv(rgb)
        apart = min(abs(h1 - h2), 1 - abs(h1 - h2))
        # either a genuinely different hue, or a neutral dark/light that
        # reads as the second kit colour anyway (white shorts, black shorts)
        if (s2 > 0.25 and apart > HUE_APART) or (s2 < 0.15 and abs(v2 - 0.5) > 0.3):
            shorts = rgb
            break
    if shorts is None:
        # nothing else in the badge: pair a strong shirt with white, and a
        # pale shirt with near-black, which is what kits actually do
        _, _, v1 = hsv(shirt)
        shorts = (240, 244, 247) if v1 < 0.75 else (24, 32, 44)

    # Socks follow the shorts unless a club is told otherwise. That is what
    # most kits do, and it beats inventing a third colour from a badge that
    # only ever had two.
    return {
        "shirt": hexof(shirt),
        "shorts": hexof(shorts),
        "socks": hexof(shorts),
        "from": "crest",
        "sat": round(s1, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default=None, help="one league, or all on disk")
    args = ap.parse_args()

    over = {}
    if OVERRIDES.exists():
        over = json.loads(OVERRIDES.read_text(encoding="utf-8"))

    # THE SAME LEAGUE IS ON DISK UNDER TWO SPELLINGS — "ENG-Premier League"
    # and "ENG-Premier_League" — and the second one holds exactly one club.
    # Reading only the first silently lost a team, which is the kind of
    # miss that shows up as one blank figure months later. Both are read and
    # merged under the spaced name.
    def folders(league: str) -> list[Path]:
        return [p for p in (LOGOS / league, LOGOS / league.replace(" ", "_"))
                if p.is_dir()]

    leagues = ([args.league] if args.league else
               sorted({p.name.replace("_", " ") for p in LOGOS.iterdir()
                       if p.is_dir() and p.name != "leagues"}))
    for league in leagues:
        pngs = {p.stem: p for f in folders(league) for p in sorted(f.glob("*.png"))}
        kits = {}
        for club, png in sorted(pngs.items()):
            k = kit(png)
            fix = (over.get(league) or {}).get(club)
            if fix:
                k = {**k, **fix, "from": "override"}
                # an override that moved the shorts without saying anything
                # about socks meant the socks, too
                if "shorts" in fix and "socks" not in fix:
                    k["socks"] = fix["shorts"]
            kits[club] = k

        lk = slug(league)
        for root in (OUT, PUB):
            root.mkdir(parents=True, exist_ok=True)
            (root / f"{lk}.json").write_text(
                json.dumps(kits, ensure_ascii=False, indent=1), encoding="utf-8")

        n_over = sum(1 for v in kits.values() if v["from"] == "override")
        print(f"  {league}: {len(kits)} clubs, {n_over} overridden")
        for club, k in list(kits.items())[:6]:
            print(f"      {club[:22]:<24} shirt {k['shirt']}  shorts {k['shorts']}"
                  f"   {'(override)' if k['from'] == 'override' else ''}")

    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
