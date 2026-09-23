"""Render the Open Graph share card to web/public/og.png.

Every link to the site posted anywhere — WhatsApp, Slack, LinkedIn, a CV —
renders from one 1200x630 image. Without it the preview is a bare URL, which
for a portfolio piece is the difference between a card someone looks at and a
line someone scrolls past.

WHY THE CARD CARRIES NO LIVE FIGURES. The obvious move is to print today's
record on it and regenerate nightly. Don't: every social platform caches the
image hard and refreshes on its own schedule, so the number people see is not
the number on the site, and a stale "50.8%" is worse than no claim at all.
The calibration bars are the real bucket shape, but unlabelled — they say
"this model is measured" without asserting a figure that goes out of date.

Fonts are the site's own (Prosto One display, Montserrat body), fetched once
into a gitignored cache rather than committed: ~840KB of binary for an asset
regenerated about twice a year is a bad trade, and Google Fonts is the same
source next/font pulls from at build time.

Usage:
    .venv/Scripts/python.exe scripts/build_og_image.py
"""
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "og.png"
FONT_CACHE = ROOT / "data" / "cache" / "fonts"

GF = "https://github.com/google/fonts/raw/main"
FONTS = {
    "ProstoOne-Regular.ttf": f"{GF}/ofl/prostoone/ProstoOne-Regular.ttf",
    "Montserrat[wght].ttf": f"{GF}/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
}

# Rendered at 2x and downsampled: the card is mostly hairlines and small text,
# which PIL's rasteriser leaves ragged at final size.
SCALE = 2
W, H = 1200, 630

BG = "#1b2026"          # the site's ink, a shade deeper for a dark card
FG = "#f4f6f7"
MUTED = "#98a2ac"
FAINT = "#6d7882"
RULE = "#2e363d"
SAID = "#39434c"        # the pale bar: what the model claimed
LANDED = "#4a7ba6"      # the solid bar: what happened — site's --color-home

# The real calibration shape (said, landed) per confidence band. Unlabelled
# on the card, so it reads as a motif rather than a claim that expires.
BARS = [(36.8, 42.7), (44.2, 41.2), (54.7, 57.1), (65.0, 78.6), (74.5, 100.0)]


def font_path(name: str) -> Path:
    """The font on disk, fetching it once if this is a fresh checkout."""
    path = FONT_CACHE / name
    if path.exists():
        return path
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    print(f"fetching {name} ...", flush=True)
    urllib.request.urlretrieve(FONTS[name], path)
    return path


def body(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(font_path("Montserrat[wght].ttf")), size * SCALE)
    f.set_variation_by_name(weight)
    return f


def display(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path("ProstoOne-Regular.ttf")),
                              size * SCALE)


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    """Greedy wrap against measured width — the card has no reflow to fall
    back on, so a line that overruns is a line that is simply cut off."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w * SCALE:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def px(v: int) -> int:
    return v * SCALE


def build() -> Path:
    img = Image.new("RGB", (W * SCALE, H * SCALE), BG)
    d = ImageDraw.Draw(img)

    left, top = 80, 74
    col_w = 560                      # text column; bars take the right side

    # ---- wordmark -------------------------------------------------------
    d.text((px(left), px(top)), "Predictorous", font=display(62), fill=FG)
    d.rectangle([px(left), px(top + 104), px(left + col_w), px(top + 104) + 1],
                fill=RULE)

    # ---- the claim ------------------------------------------------------
    y = top + 140
    head = body(42, "SemiBold")
    for line in wrap(d, "A football model that shows its work", head, col_w):
        d.text((px(left), px(y)), line, font=head, fill=FG)
        y += 54

    y += 14
    sub = body(23)
    blurb = ("Every call is recorded before kickoff and graded "
             "afterwards — including the wrong ones.")
    for line in wrap(d, blurb, sub, col_w):
        d.text((px(left), px(y)), line, font=sub, fill=MUTED)
        y += 34

    # ---- calibration bars ----------------------------------------------
    # Widths are DERIVED from the column, not chosen: fixed bar and gap sizes
    # summed past the right margin and silently cropped the last band, which
    # in a share card is invisible until someone posts a link.
    bx, base, span = 690, 452, 250    # right column, baseline, tallest bar
    pair_gap, group_gap = 6, 26
    avail = (W - left) - bx
    group_w = (avail - group_gap * (len(BARS) - 1)) / len(BARS)
    bar_w = (group_w - pair_gap) / 2
    for i, (said, landed) in enumerate(BARS):
        x = bx + i * (group_w + group_gap)
        for j, (val, colour) in enumerate(((said, SAID), (landed, LANDED))):
            h = span * val / 100
            x0 = x + j * (bar_w + pair_gap)
            d.rounded_rectangle(
                [px(round(x0)), px(round(base - h)),
                 px(round(x0 + bar_w)), px(base)],
                radius=px(4), fill=colour)

    legend = body(15, "Medium")
    lx = bx
    for label, colour in (("said", SAID), ("landed", LANDED)):
        d.rounded_rectangle([px(lx), px(base + 22), px(lx + 11),
                             px(base + 33)], radius=px(2), fill=colour)
        d.text((px(lx + 19), px(base + 19)), label, font=legend, fill=FAINT)
        lx += round(d.textlength(label, font=legend) / SCALE) + 52

    # ---- footer ---------------------------------------------------------
    foot_y = H - 92
    d.rectangle([px(left), px(foot_y), px(W - left), px(foot_y) + 1], fill=RULE)
    d.text((px(left), px(foot_y + 26)), "predictorous.com",
           font=body(21, "Medium"), fill=MUTED)
    leagues = "Premier League · La Liga · Serie A · Bundesliga · Ligue 1"
    lf = body(17)
    d.text((px(W - left) - d.textlength(leagues, font=lf), px(foot_y + 30)),
           leagues, font=lf, fill=FAINT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(OUT, optimize=True)
    return OUT


def main() -> int:
    out = build()
    kb = out.stat().st_size / 1024
    print(f"wrote {out.relative_to(ROOT)} — {W}x{H}, {kb:.0f} KB")
    if kb > 900:
        print("WARN over 900KB; some scrapers skip large images", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
