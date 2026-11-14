"""The README header's animation: a band of light that crosses assets/brand/hero.png, then a rest.

    python scripts/make_hero.py        (the still banner, from the emblem)
    python scripts/make_hero_gif.py    (assets/brand/hero.gif, from the still banner)

The light only brightens what is already bright (the emblem's edges, the chain, the wordmark), so the dark background
stays one flat colour and the file stays small. Pillow is the only dependency.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
W, H = 800, 300            # the size the README shows
BG = (6, 7, 11)            # (scripts/make_hero.py's canvas)
SWEEP_FRAMES, REST_MS, FRAME_MS = 34, 2600, 45


def band(x):
    """A soft diagonal band of light centred on column x, as an L image."""
    im = Image.new("L", (W, H), 0)
    px = im.load()
    for y in range(H):
        cx = x + (H / 2 - y) * 0.45          # leaning to the right at the top
        for dx in range(-90, 91):
            xx = int(cx + dx)
            if 0 <= xx < W:
                px[xx, y] = max(px[xx, y], int(255 * (1 - abs(dx) / 90) ** 2))
    return im.filter(ImageFilter.GaussianBlur(6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", default=str(BRAND / "hero.png"))
    ap.add_argument("--out", default=str(BRAND / "hero.gif"))
    a = ap.parse_args()
    hero = Image.open(a.hero).convert("RGBA").resize((W, H), Image.LANCZOS)
    still = Image.new("RGB", (W, H), BG)
    still.paste(hero, (0, 0), hero)           # (a GIF has no soft edge: the rounded corners sit on the canvas colour)
    bright = still.convert("L").point(lambda v: 0 if v < 70 else min(255, (v - 70) * 2))   # where there is light to catch
    frames, durations = [still], [REST_MS]
    for i in range(SWEEP_FRAMES):
        x = -140 + (W + 280) * i / (SWEEP_FRAMES - 1)
        glint = ImageChops.multiply(band(x), bright).point(lambda v: v * 0.6)
        lit = ImageChops.add(still, Image.merge("RGB", (glint, glint, glint)))
        frames.append(lit)
        durations.append(FRAME_MS)
    # one palette for every frame, from the still and the brightest frames together, so the picture does not shimmer
    sample = Image.new("RGB", (W, H * 3))
    for n, f in enumerate((still, frames[len(frames) // 3], frames[2 * len(frames) // 3])):
        sample.paste(f, (0, H * n))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [f.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    out[0].save(a.out, save_all=True, append_images=out[1:], duration=durations, loop=0, optimize=False, disposal=1)
    print("wrote", a.out, "%d frames, %.0f KB" % (len(out), Path(a.out).stat().st_size / 1024))


if __name__ == "__main__":
    main()
