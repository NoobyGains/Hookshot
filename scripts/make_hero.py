"""Lay out the README header: the Hookshot on the left, the shield on the right, the name between them.

    python scripts/make_hero.py                       the still banner, the social preview and the icon
    python scripts/make_hero.py --frames FOLDER       also the animation, both objects turning once

The objects are rendered with scripts/render_emblem.py (assets/brand/README.md says from which models). The stills
this script reads are assets/brand/emblem_hookshot.png and emblem_shield.png; --frames names a folder of
hookshot_000.png ... and shield_000.png ... from the same script, which is not kept in the repository.

Fonts: Unbounded ExtraBold (wordmark) and JetBrains Mono (tagline), static instances of the SIL OFL fonts, vendored in
assets/brand/fonts/. Pillow is the only dependency. The layout follows NoobyGains/usage-pulse's.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND = REPO_ROOT / "assets" / "brand"
FONTS = BRAND / "fonts"

WORD = "Hookshot"
SUB = "native, no emulator"
TAGLINE = "Ocarina of Time on Windows & Linux"
FOOTLINE = "Vulkan · DLSS · FSR 4 · HDR · up to 240 FPS"

W, H = 1600, 600          # 2x of the 800x300 the README shows
SIDE = 500                # each object's square
BG = (6, 7, 11)
# The objects' own colours: their blue, cyan, the grip cap's gold.
C_BLUE, C_CYAN, C_GOLD = (59, 130, 246), (34, 211, 238), (251, 191, 36)
GLOW = (30, 64, 175)
GRADIENT = [(248, 250, 252), (226, 232, 240), C_BLUE, C_CYAN, C_GOLD]


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def fit(draw, text, name, start, floor, max_width):
    """The largest size from *start* down to *floor* at which *text* fits *max_width*."""
    size = start
    while size > floor:
        f = font(name, size)
        if draw.textlength(text, font=f) <= max_width:
            return f
        size -= 1
    return font(name, floor)


def horizontal_gradient(w, h, stops):
    grad = Image.new("RGB", (w, 1))
    px = grad.load()
    n = len(stops) - 1
    for x in range(w):
        t = x / max(w - 1, 1) * n
        i = min(int(t), n - 1)
        f = t - i
        a, b = stops[i], stops[i + 1]
        px[x, 0] = tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))
    return grad.resize((w, h))


def soft_square(size):
    """A mask that fades a square render out towards its edges, so its own background never shows a seam."""
    m = Image.new("L", (size, size), 0)
    pad = size // 9
    ImageDraw.Draw(m).rounded_rectangle((pad, pad, size - pad, size - pad), radius=size // 5, fill=255)
    return m.filter(ImageFilter.GaussianBlur(size // 14))


def gradient_text(canvas, text, f, xy, glow_radius=28, glow_strength=0.55):
    """Draw *text* filled with the brand gradient over a soft glow."""
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    glow = mask.filter(ImageFilter.GaussianBlur(glow_radius))
    canvas = Image.composite(Image.new("RGB", canvas.size, GLOW), canvas, glow.point(lambda v: v * glow_strength))
    bbox = mask.getbbox()
    grad_full = Image.new("RGB", canvas.size, GRADIENT[0])
    grad_full.paste(horizontal_gradient(bbox[2] - bbox[0], canvas.height, GRADIENT), (bbox[0], 0))
    return Image.composite(grad_full, canvas, mask)


def text_layer():
    """The banner without its objects: the name, the lines under it, all centred."""
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    room = W - 2 * SIDE + 60

    def centred(text, f):
        return (W - d.textlength(text, font=f)) / 2

    word = fit(d, WORD, "Unbounded-ExtraBold.ttf", 118, 60, room)
    canvas = gradient_text(canvas, WORD, word, (centred(WORD, word), 190))
    d = ImageDraw.Draw(canvas)
    sub = fit(d, SUB, "Unbounded-ExtraBold.ttf", 44, 24, room)
    d.text((centred(SUB, sub), 322), SUB, font=sub, fill=(226, 232, 240))
    tag = fit(d, TAGLINE, "JetBrainsMono-Medium.ttf", 27, 16, room)
    d.text((centred(TAGLINE, tag), 408), TAGLINE, font=tag, fill=(203, 213, 225))
    foot = fit(d, FOOTLINE, "JetBrainsMono-Regular.ttf", 19, 11, room)
    d.text((centred(FOOTLINE, foot), 458), FOOTLINE, font=foot, fill=(120, 130, 150))
    return canvas


def compose(base, left, right, mask):
    """The banner: *base* (the text layer) with the two square renders at its sides."""
    canvas = base.copy()
    y = (H - SIDE) // 2
    canvas.paste(left.convert("RGB").resize((SIDE, SIDE), Image.LANCZOS), (20, y), mask)
    canvas.paste(right.convert("RGB").resize((SIDE, SIDE), Image.LANCZOS), (W - SIDE - 20, y), mask)
    return canvas


def round_corners(im, radius):
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    im.putalpha(mask)
    return im


def build_social_preview(still, out_path):
    """GitHub's social preview is 1280x640: the banner, centred on the canvas colour."""
    canvas = Image.new("RGB", (1280, 640), BG)
    small = still.resize((1280, 480), Image.LANCZOS)
    canvas.paste(small, (0, 80))
    canvas.save(out_path, optimize=True)


def build_icon(emblem, out_path, size=512):
    """512x512 rounded square of the Hookshot, for listings and avatars."""
    im = emblem.convert("RGB").resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=255)
    im.putalpha(mask)
    im.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", help="a folder of hookshot_NNN.png and shield_NNN.png: also write the animation")
    ap.add_argument("--frame-ms", type=int, default=70)
    a = ap.parse_args()
    base, mask = text_layer(), soft_square(SIDE)
    hook, shield = Image.open(BRAND / "emblem_hookshot.png"), Image.open(BRAND / "emblem_shield.png")
    still = compose(base, hook, shield, mask)
    round_corners(still, 28).save(BRAND / "hero.png", optimize=True)
    build_social_preview(still, BRAND / "social-preview.png")
    build_icon(hook, BRAND / "icon.png")
    print("wrote hero.png, social-preview.png, icon.png")
    if a.frames:
        folder = Path(a.frames)
        hooks, shields = sorted(folder.glob("hookshot_*.png")), sorted(folder.glob("shield_*.png"))
        if not hooks or len(hooks) != len(shields):
            raise SystemExit("%s: %d hookshot and %d shield frames" % (folder, len(hooks), len(shields)))
        # animated WebP, not GIF: a GIF's 256 colours band the wordmark's gradient and the renders' shading
        frames = [compose(base, Image.open(h), Image.open(s), mask).resize((1200, 450), Image.LANCZOS)
                  for h, s in zip(hooks, shields)]
        out = BRAND / "hero-banner.webp"
        frames[0].save(out, save_all=True, append_images=frames[1:], duration=a.frame_ms, loop=0, quality=86, method=6)
        print("wrote hero-banner.webp: %d frames, %.0f KB" % (len(frames), out.stat().st_size / 1024))


if __name__ == "__main__":
    main()
