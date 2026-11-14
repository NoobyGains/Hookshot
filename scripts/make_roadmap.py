"""The README's roadmap as a picture: Done, In progress and Coming next, each item with its own status mark.

    python scripts/make_roadmap.py     (assets/brand/roadmap.png)

Edit STAGES and run it again. readme.md repeats the same items as text under the picture, for search and screen
readers; keep the two alike. "In progress" lists only what someone is working on now. Pillow is the only dependency.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
FONTS = BRAND / "fonts"
BG, CARD, EDGE = (6, 7, 11), (13, 16, 24), (30, 36, 52)
TEXT, MUTED = (226, 232, 240), (140, 150, 170)
GREEN, AMBER, BLUE = (52, 211, 153), (251, 191, 36), (96, 165, 250)

# (kind, title, what it means, colour, items)
STAGES = [
    ("done", "DONE", "in this repository now", GREEN, [
        "Shader prep never stalls at 99%",
        "Gohma, slow motions, water above 60",
        "View distance, grass, shadow rows",
        "FXAA, bloom and colour grade",
        "Speedrun timer, death, rupee counters",
        "One-click HDR launcher",
        "Longshot and Ocarina Reborn fixes",
    ]),
    ("doing", "IN PROGRESS", "being worked on now", AMBER, [
        "Memory filling up in long sessions",
        "Low FPS in Castle Town, Hyrule Field",
    ]),
    ("next", "COMING NEXT", "planned, not started", BLUE, [
        "Link's jump loop after Gohma",
        "Objects and doors turning invisible",
        "AMD crashes on Windows",
        "amiibo support",
        "A signed Builder",
        "Intel cards; cards without mesh shaders",
    ]),
]

W, PAD, GAP = 1600, 56, 26
TOP, ROW, CARD_PAD = 190, 62, 30


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def mark(d, kind, cx, cy, r, colour):
    """The item's status mark: a filled circle with a tick (done), a half-filled ring (in progress), an empty ring (next)."""
    if kind == "done":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
        d.line((cx - r * 0.45, cy + r * 0.02, cx - r * 0.1, cy + r * 0.38, cx + r * 0.5, cy - r * 0.35), fill=BG,
               width=max(2, int(r * 0.32)), joint="curve")
    elif kind == "doing":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=max(2, int(r * 0.25)))
        d.pieslice((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), -90, 90, fill=colour)
    else:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=max(2, int(r * 0.22)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BRAND / "roadmap.png"))
    a = ap.parse_args()
    rows = max(len(s[4]) for s in STAGES)
    card_h = 96 + rows * ROW + CARD_PAD
    H = TOP + card_h + PAD
    card_w = (W - 2 * PAD - 2 * GAP) // 3
    im = Image.new("RGB", (W, H), BG)
    head, sub = font("Unbounded-ExtraBold.ttf", 34), font("JetBrainsMono-Regular.ttf", 20)
    count_f, legend_f = font("Unbounded-ExtraBold.ttf", 56), font("JetBrainsMono-Medium.ttf", 21)
    probe = ImageDraw.Draw(im)
    longest = max((t for s in STAGES for t in s[4]), key=len)
    size = 25
    while probe.textlength(longest, font=font("JetBrainsMono-Medium.ttf", size)) > card_w - 2 * CARD_PAD - 44:
        size -= 1
    item = font("JetBrainsMono-Medium.ttf", size)

    # a soft glow under each card's coloured top, then the cards
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    for n, (_, _, _, colour, _) in enumerate(STAGES):
        x0 = PAD + n * (card_w + GAP)
        gd.rounded_rectangle((x0 + 20, TOP - 6, x0 + card_w - 20, TOP + 30), radius=16, fill=colour)
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(22)), 0.55)
    d = ImageDraw.Draw(im)

    # the legend: how many in each stage, with the marks the items use
    x = PAD
    for kind, title, _, colour, items in STAGES:
        mark(d, kind, x + 22, 74, 20, colour)
        d.text((x + 56, 40), str(len(items)), font=count_f, fill=colour)
        nx = x + 56 + d.textlength(str(len(items)), font=count_f) + 14
        d.text((nx, 56), title.lower(), font=legend_f, fill=TEXT)
        x = nx + d.textlength(title.lower(), font=legend_f) + 64
    total = sum(len(s[4]) for s in STAGES)
    bar_y, bx = 128, PAD   # (one bar, split by stage, across the picture)
    for kind, _, _, colour, items in STAGES:
        w = (W - 2 * PAD) * len(items) / total
        d.rounded_rectangle((bx, bar_y, bx + w - 6, bar_y + 12), radius=6, fill=colour if kind != "next" else (40, 60, 92))
        bx += w

    for n, (kind, title, note, colour, items) in enumerate(STAGES):
        x0 = PAD + n * (card_w + GAP)
        d.rounded_rectangle((x0, TOP, x0 + card_w, TOP + card_h), radius=22, fill=CARD, outline=EDGE, width=2)
        d.rounded_rectangle((x0, TOP, x0 + card_w, TOP + 10), radius=5, fill=colour)
        mark(d, kind, x0 + CARD_PAD + 18, TOP + 50, 18, colour)
        d.text((x0 + CARD_PAD + 48, TOP + 30), title, font=head, fill=colour)
        d.text((x0 + CARD_PAD + 48, TOP + 74), note, font=sub, fill=MUTED)
        for i, text in enumerate(items):
            y = TOP + 124 + i * ROW
            mark(d, kind, x0 + CARD_PAD + 12, y + size * 0.62, 12, colour)
            d.text((x0 + CARD_PAD + 38, y), text, font=item, fill=TEXT if kind != "next" else (196, 204, 218))
            if i < len(items) - 1:
                d.line((x0 + CARD_PAD, y + ROW - 14, x0 + card_w - CARD_PAD, y + ROW - 14), fill=(24, 29, 42), width=1)

    out = im.convert("RGBA")
    mask = Image.new("L", out.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=255)
    out.putalpha(mask)
    out.save(a.out, optimize=True)
    print("wrote", a.out, out.size)


if __name__ == "__main__":
    main()
