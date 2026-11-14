# /// script
# dependencies = ["pillow"]
# ///
"""The launcher's pictures, made from Hookshot's brand art (assets/brand, its README has the models' credits):

    App/Assets/hookshot.png   the window's and the program's icon: assets/brand/icon.png, as an 8-bit RGBA PNG
    App/Assets/hookshot.ico   the Windows icon, from it (scripts/make_icon.py)
    App/Assets/shield.png     the blank Hyrule shield, assets/brand/emblem_shield.png with its black studio made transparent,
                              so it stands on the window's own background (the saves page's mark, the home's banner)

The turning Hookshot (assets/hookshot_turn.png, already transparent) and the fonts (assets/brand/fonts) are not copied: the
project file takes them from assets/ as they are. Pillow only. Run it after the brand art changes:

    python -I launcher/scripts/make_art.py
"""
import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT.parent / "assets" / "brand"
ASSETS = ROOT / "App" / "Assets"
SHIELD_SIZE = 320


def icon():
    im = Image.open(BRAND / "icon.png").convert("RGBA")
    if im.size != (512, 512):
        im = im.resize((512, 512), Image.Resampling.LANCZOS)
    im.save(ASSETS / "hookshot.png", "PNG", optimize=True)
    spec = importlib.util.spec_from_file_location("make_icon", Path(__file__).with_name("make_icon.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def keyed(path, edge=10):
    """A render on its studio backdrop (black at the top, a dark blue floor below), the backdrop made transparent. The backdrop
    of each row is read from the picture's left and right edges, which the object does not reach; a pixel is backdrop as far as
    it is near that colour and joined to the edge through such pixels. Those keep an alpha from how far they are from the
    backdrop (the rim light's fall-off, the soft shadow) and their colour with the backdrop taken out; the object stays opaque"""
    rgb = Image.open(path).convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    back = []
    for y in range(h):
        side = [px[x, y] for x in list(range(edge)) + list(range(w - edge, w))]
        back.append(tuple(sum(c[k] for c in side) / len(side) for k in range(3)))
    dist = Image.new("L", (w, h))
    pd = dist.load()
    for y in range(h):
        br, bg, bb = back[y]
        for x in range(w):
            r, g, b = px[x, y]
            pd[x, y] = min(255, round(max(abs(r - br), abs(g - bg), abs(b - bb))))
    # (the backdrop: near its row's colour, and reached from the edge without crossing the object)
    near = dist.point(lambda v: 255 if v < 14 else 0)
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if near.getpixel(corner) == 255:
            ImageDraw.floodfill(near, corner, 128)
    studio = near.point(lambda v: 255 if v == 128 else 0).filter(ImageFilter.MaxFilter(5))
    ps = studio.load()
    alpha = Image.new("L", (w, h))
    pa = alpha.load()
    for y in range(h):
        for x in range(w):
            pa[x, y] = max(0, min(255, round((pd[x, y] - 4) * 255 / 36))) if ps[x, y] else 255
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.6))
    pa = alpha.load()
    out = Image.new("RGBA", (w, h))
    po = out.load()
    for y in range(h):
        br, bg, bb = back[y]
        for x in range(w):
            a = pa[x, y]
            if a == 0:
                po[x, y] = (0, 0, 0, 0)
                continue
            r, g, b = px[x, y]
            t = a / 255
            po[x, y] = tuple(max(0, min(255, round((c - (1 - t) * k) / t))) for c, k in ((r, br), (g, bg), (b, bb))) + (a,)
    return out


def shield():
    im = keyed(BRAND / "emblem_shield.png")
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    im = im.crop(box)
    side = max(im.size)
    square = Image.new("RGBA", (side, side))
    square.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    square.convert("RGBa").resize((SHIELD_SIZE, SHIELD_SIZE), Image.Resampling.LANCZOS).convert("RGBA").save(
        ASSETS / "shield.png", "PNG", optimize=True)


if __name__ == "__main__":
    icon()
    shield()
    print("App/Assets: hookshot.png, hookshot.ico, shield.png")
