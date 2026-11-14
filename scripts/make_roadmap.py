"""The README's roadmap as a picture: three stages on one line, in the header's type and colours.

    python scripts/make_roadmap.py     (assets/brand/roadmap.png)

The stages and their items are the lists below: edit them and run it again. readme.md repeats the same items as text
under the picture, for search and screen readers; keep the two alike. Pillow is the only dependency.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
FONTS = BRAND / "fonts"
BG, CARD, EDGE = (6, 7, 11), (13, 16, 24), (30, 36, 52)
TEXT, MUTED = (226, 232, 240), (140, 150, 170)

STAGES = [
    ("MERGED HERE", "ahead of the release", (59, 130, 246), [
        "Shader prep no longer stalls at 99%",
        "Gohma, slow motions, water above 60",
        "View distance, grass, shadow rows",
        "FXAA, bloom and colour grade",
        "Speedrun timer, death counter",
        "Fixes from Longshot and Reborn",
    ]),
    ("NEXT", "the most reported problems", (34, 211, 238), [
        "Memory filling up in long sessions",
        "Link's jump loop after Gohma",
        "AMD crashes on Windows",
        "Low FPS in Castle Town, Hyrule Field",
        "Objects and doors turning invisible",
        "amiibo support",
    ]),
    ("LATER", "wider reach", (251, 191, 36), [
        "A signed Builder (antivirus flags)",
        "Intel cards",
        "Cards without mesh shaders",
        "More games on the same engine",
    ]),
]

W, PAD, GAP, TOP = 1600, 60, 28, 150
ROW, CARD_PAD = 46, 34


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BRAND / "roadmap.png"))
    a = ap.parse_args()
    rows = max(len(s[3]) for s in STAGES)
    card_h = 118 + rows * ROW + CARD_PAD
    H = TOP + card_h + PAD
    im = Image.new("RGB", (W, H), BG)
    card_w = (W - 2 * PAD - 2 * GAP) // 3
    title, sub = font("Unbounded-ExtraBold.ttf", 30), font("JetBrainsMono-Regular.ttf", 19)
    # one size for every item: the largest at which the longest of them fits its card
    size, probe = 24, ImageDraw.Draw(im)
    longest = max((t for s in STAGES for t in s[3]), key=len)
    while probe.textlength(longest, font=font("JetBrainsMono-Medium.ttf", size)) > card_w - 2 * CARD_PAD - 26:
        size -= 1
    item = font("JetBrainsMono-Medium.ttf", size)
    # the line the three stages sit on, in the stages' colours, with a soft glow
    line_y = 84
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    for n, (_, _, colour, _) in enumerate(STAGES):
        x0 = PAD + n * (card_w + GAP)
        gd.rectangle((x0, line_y - 3, x0 + card_w + (GAP if n < 2 else 0), line_y + 3), fill=colour)
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(14)), 0.9)
    d = ImageDraw.Draw(im)
    for n, (name, note, colour, items) in enumerate(STAGES):
        x0 = PAD + n * (card_w + GAP)
        d.rectangle((x0, line_y - 2, x0 + card_w + (GAP if n < 2 else 0), line_y + 2), fill=colour)
        cx = x0 + 34
        d.ellipse((cx - 17, line_y - 17, cx + 17, line_y + 17), fill=BG, outline=colour, width=5)
        d.ellipse((cx - 6, line_y - 6, cx + 6, line_y + 6), fill=colour)
        # the stage's card
        d.rounded_rectangle((x0, TOP, x0 + card_w, TOP + card_h), radius=22, fill=CARD, outline=EDGE, width=2)
        d.rounded_rectangle((x0, TOP, x0 + card_w, TOP + 8), radius=4, fill=colour)
        d.text((x0 + CARD_PAD, TOP + 34), name, font=title, fill=colour)
        d.text((x0 + CARD_PAD, TOP + 78), note, font=sub, fill=MUTED)
        for i, text in enumerate(items):
            y = TOP + 126 + i * ROW
            d.rounded_rectangle((x0 + CARD_PAD, y + 9, x0 + CARD_PAD + 10, y + 19), radius=3, fill=colour)
            d.text((x0 + CARD_PAD + 26, y), text, font=item, fill=TEXT)
    # rounded corners, as the header has
    out = im.convert("RGBA")
    mask = Image.new("L", out.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=28, fill=255)
    out.putalpha(mask)
    out.save(a.out, optimize=True)
    print("wrote", a.out, out.size)


if __name__ == "__main__":
    main()
