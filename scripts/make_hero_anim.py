"""The README header's animation: a band of light that crosses assets/brand/hero.png, then a rest.

    python scripts/make_hero.py        (the still banner, from the emblem)
    python scripts/make_hero_anim.py    (assets/brand/hero.webp, from the still banner)

The light only brightens what is already bright (the emblem's edges, the chain, the wordmark), so the dark background
stays one flat colour and the file stays small. Pillow is the only dependency.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
W, H = 1200, 450           # 1.5x of the 800x300 the README shows
BG = (6, 7, 11)            # (scripts/make_hero.py's canvas)
SWEEP_FRAMES, REST_MS, FRAME_MS = 34, 2600, 45


def band(x):
    """A soft diagonal band of light centred on column x, as an L image."""
    im = Image.new("L", (W, H), 0)
    px = im.load()
    for y in range(H):
        cx = x + (H / 2 - y) * 0.45          # leaning to the right at the top
        for dx in range(-135, 136):
            xx = int(cx + dx)
            if 0 <= xx < W:
                px[xx, y] = max(px[xx, y], int(255 * (1 - abs(dx) / 135) ** 2))
    return im.filter(ImageFilter.GaussianBlur(9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", default=str(BRAND / "hero.png"))
    ap.add_argument("--out", default=str(BRAND / "hero.webp"))
    a = ap.parse_args()
    hero = Image.open(a.hero).convert("RGBA").resize((W, H), Image.LANCZOS)
    still = Image.new("RGB", (W, H), BG)
    still.paste(hero, (0, 0), hero)           # (the rounded corners sit on the canvas colour)
    bright = still.convert("L").point(lambda v: 0 if v < 70 else min(255, (v - 70) * 2))   # where there is light to catch
    frames, durations = [still], [REST_MS]
    for i in range(SWEEP_FRAMES):
        x = -210 + (W + 420) * i / (SWEEP_FRAMES - 1)
        glint = ImageChops.multiply(band(x), bright).point(lambda v: v * 0.6)
        lit = ImageChops.add(still, Image.merge("RGB", (glint, glint, glint)))
        frames.append(lit)
        durations.append(FRAME_MS)
    # animated WebP, not GIF: a GIF's 256 colours band the wordmark's gradient and its glow
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=88, method=6)
    print("wrote", a.out, "%d frames, %.0f KB" % (len(frames), Path(a.out).stat().st_size / 1024))


if __name__ == "__main__":
    main()
