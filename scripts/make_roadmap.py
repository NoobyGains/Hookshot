"""The README's roadmap picture, laid out as game roadmaps are: a title, then one band per stage (Done, In progress,
Coming next), each with a ribbon and a row of feature cards, each card a picture, a title and a line or two.

    python scripts/make_roadmap.py     (assets/brand/roadmap.png)

The card pictures are in assets/brand/roadmap/ (screenshots of the game, which CONTRIBUTING.md allows; memory-soak.csv
is the memory card's chart). Edit STAGES and run it again. readme.md repeats the items as text under the picture, for
search and screen readers; keep the two alike. "In progress" lists only what is being worked on now. Needs Pillow.
"""
import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BRAND = Path(__file__).resolve().parent.parent / "assets" / "brand"
FONTS, PICS = BRAND / "fonts", BRAND / "roadmap"
BG, CARD, EDGE = (7, 9, 14), (15, 19, 29), (34, 41, 58)
TEXT, MUTED = (232, 236, 243), (146, 156, 176)
GREEN, AMBER, BLUE, PURPLE = (52, 211, 153), (251, 191, 36), (96, 165, 250), (167, 139, 250)
GRADIENT = [(248, 250, 252), (59, 130, 246), (34, 211, 238), (251, 191, 36)]
UPDATED = "14 November 2026"

# (kind, title, what it means, colour, [(picture or drawn panel, title, text)])
STAGES = [
    ("done", "DONE", "on main now, tested in the game", GREEN, [
        ("above-60.jpg", "Smooth above 60 FPS", "Gohma steers, slow motions and water behave at 120 to 240 FPS."),
        ("graphics.jpg", "New graphics options", "View distance, grass, shadows, bloom, colour grade, FXAA."),
        ("counters.jpg", "Timer and counters", "Speedrun timer, death counter and the N64's rupee counter."),
        ("panel:shaders", "No more stuck at 99%", "Shader preparation carries on past a stuck graphics driver."),
        ("retro.jpg", "Retro N64 look", "240 lines and the N64's own dither, at no cost."),
        ("crt.jpg", "A better CRT look", "Scanlines, mask, glow and curvature, each set in the menu."),
        ("eyes.jpg", "Brightness, colour vision", "A brightness slider and colour-blind modes."),
        ("f12.jpg", "Screenshot key", "F12 saves the picture as you see it, as a PNG beside the game."),
    ]),
    ("doing", "IN PROGRESS", "being worked on now", AMBER, [
        ("panel:name:Mods", "Mod manager", "Your own mods listed in the menu: on and off, load order, conflicts."),
        ("panel:name:Hero", "Hero mode, quiet Navi", "Double damage and no recovery hearts; Navi's callouts off."),
        ("panel:name:Launcher", "Hookshot Launcher", "Builds side by side, update channels, saves import and export."),
        ("panel:name:More", "More fixes and features", "Faster prompts, less memory, Mono audio, hold-to-toggle, Intel and AMD fixes."),
    ]),
    ("next", "COMING NEXT", "planned, not started", BLUE, [
        ("chart:memory", "Memory in long sessions", "Levels off at about 33 GB on a 96 GB PC; next, held to 16 GB."),
        ("towns.jpg", "Faster towns and fields", "Castle Town and Hyrule Field, where the processor holds frames back."),
        ("gohma.jpg", "Jump loop after Gohma", "Link repeats a jump in dialogue above 60 FPS."),
        ("invisible.jpg", "Invisible doors and walls", "Objects that vanish in a few places of the game."),
        ("panel:amd", "AMD on Windows", "Crashes on some Radeon cards: needs a tester."),
        ("panel:amiibo", "amiibo", "Scan your own amiibo files."),
        # (what players of the remake ask for most; only what Hookshot can build as a toggle over the player's own game
        # files: no Nintendo assets)
        ("panel:name:Photo", "Photo mode", "A free camera with the HUD hidden (F12 screenshots already work)."),
        ("panel:name:Aim", "First-person aim", "Bow, slingshot and Hookshot from Link's eyes, with the mouse."),
        ("panel:name:QoL", "Small toggles", "Auto jump, Young Link on Epona, gear on and off, N64 controls."),
        ("panel:name:Random", "Randomizer", "Items shuffled each run, a new game every time."),
        ("panel:name:Online", "Online co-op", "Play the adventure together with a friend."),
    ]),
]
PER_ROW = 4   # (a stage of more than five cards wraps, four to a row)

W, M, GAP = 1600, 48, 20


def per_row_of(n):
    """Cards to a row: all of them up to five, else as even rows of at most PER_ROW (six: two rows of three)"""
    if n <= 5:
        return n
    rows = (n + PER_ROW - 1) // PER_ROW
    return (n + rows - 1) // rows


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def gradient_text(canvas, xy, text, f):
    """Text filled with the header's gradient, left to right."""
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    box = mask.getbbox()
    grad = Image.new("RGB", (box[2] - box[0], 1))
    n = len(GRADIENT) - 1
    for x in range(grad.width):
        t = x / max(grad.width - 1, 1) * n
        i = min(int(t), n - 1)
        a, b = GRADIENT[i], GRADIENT[i + 1]
        grad.putpixel((x, 0), tuple(round(a[k] + (b[k] - a[k]) * (t - i)) for k in range(3)))
    full = Image.new("RGB", canvas.size)
    full.paste(grad.resize((grad.width, canvas.height)), (box[0], 0))
    canvas.paste(full, (0, 0), mask)


def mark(d, kind, cx, cy, r, colour):
    """The stage's mark: a filled circle with a tick (done), a half-filled ring (in progress), an empty ring (next)."""
    if kind == "done":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
        d.line((cx - r * 0.45, cy + r * 0.02, cx - r * 0.1, cy + r * 0.38, cx + r * 0.5, cy - r * 0.35), fill=BG,
               width=max(2, int(r * 0.32)), joint="curve")
    elif kind == "doing":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=max(2, int(r * 0.25)))
        d.pieslice((cx - r * 0.62, cy - r * 0.62, cx + r * 0.62, cy + r * 0.62), -90, 90, fill=colour)
    elif kind == "request":   # (a ring with a plus: asked for)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=max(2, int(r * 0.22)))
        k = max(2, int(r * 0.24))
        d.line((cx - r * 0.5, cy, cx + r * 0.5, cy), fill=colour, width=k)
        d.line((cx, cy - r * 0.5, cx, cy + r * 0.5), fill=colour, width=k)
    else:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colour, width=max(2, int(r * 0.22)))


def wrap(d, text, f, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=f) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def panel(kind, w, h, colour):
    """A drawn picture for a card with no screenshot: the shader bar, the memory chart, or a name on a tile."""
    im = Image.new("RGB", (w, h), (11, 14, 22))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 24):   # (a faint grid)
        d.line((0, y, w, y), fill=(17, 21, 32))
    for x in range(0, w, 24):
        d.line((x, 0, x, h), fill=(17, 21, 32))
    if kind == "shaders":
        f, small = font("JetBrainsMono-Medium.ttf", 22), font("JetBrainsMono-Regular.ttf", 17)
        d.text((28, h * 0.30), "Preparing shaders", font=f, fill=TEXT)
        d.rounded_rectangle((28, h * 0.50, w - 28, h * 0.50 + 16), radius=8, fill=(30, 36, 52))
        d.rounded_rectangle((28, h * 0.50, w - 28, h * 0.50 + 16), radius=8, fill=colour)
        d.text((28, h * 0.50 + 28), "50,940 of 50,940 (100%)", font=small, fill=MUTED)
    elif kind == "memory":
        rows = list(csv.DictReader(open(PICS / "memory-soak.csv")))
        ys = [float(r["private_gb"]) for r in rows]
        top, bottom, left, right = 54, h - 40, 74, w - 18
        lo, hi = 0, 40
        f = font("JetBrainsMono-Regular.ttf", 15)
        for g in (0, 10, 20, 30, 40):
            y = bottom - (g - lo) / (hi - lo) * (bottom - top)
            d.line((left, y, right, y), fill=(32, 38, 54))
            d.text((14, y - 9), "%d GB" % g, font=f, fill=MUTED)
        pts = [(left + i / (len(ys) - 1) * (right - left), bottom - (v - lo) / (hi - lo) * (bottom - top))
               for i, v in enumerate(ys)]
        d.polygon(pts + [(right, bottom), (left, bottom)], fill=(54, 44, 18))
        d.line(pts, fill=colour, width=4, joint="curve")
        d.text((left, h - 30), "44 area changes, 8 minutes", font=f, fill=MUTED)
    else:   # (a name on a tile: "amd", "amiibo", or "name:<word>")
        name = kind.split(":", 1)[1] if kind.startswith("name:") else {"amd": "Radeon", "amiibo": "amiibo"}[kind]
        top_free = 44   # (below the card's badge)
        size = min(44, int((h - top_free) * 0.62))
        while d.textlength(name, font=font("Unbounded-ExtraBold.ttf", size)) > w - 40 and size > 16:
            size -= 2
        f = font("Unbounded-ExtraBold.ttf", size)
        box = d.textbbox((0, 0), name, font=f)
        tint = tuple(int(c * 0.5) for c in colour) if kind.startswith("name:") else (70, 84, 112)
        mid = (top_free + h) / 2 if h < 160 else h / 2
        d.text(((w - (box[2] - box[0])) / 2 - box[0], mid - (box[3] - box[1]) / 2 - box[1]), name, font=f, fill=tint)
    return im


def picture(source, w, h, kind, colour):
    if source.startswith("panel:") or source.startswith("chart:"):
        im = panel(source.split(":", 1)[1], w, h, colour)
    else:
        im = Image.open(PICS / source).convert("RGB")
        scale = max(w / im.width, h / im.height)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        x, y = (im.width - w) // 2, (im.height - h) // 2
        im = im.crop((x, y, x + w, y + h))
    if kind == "next":   # (not started: grey and dimmed)
        im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(0.15)).enhance(0.55)
    return im


def rounded(im, radius, corners=(True, True, False, False)):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255,
                                           corners=corners)
    return mask


def badge(d, x, y, kind, label, colour):
    f = font("JetBrainsMono-Medium.ttf", 15)
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((x, y, x + tw + 44, y + 28), radius=14, fill=(7, 9, 14))
    mark(d, kind, x + 15, y + 14, 8, colour)
    d.text((x + 30, y + 5), label, font=f, fill=colour)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BRAND / "roadmap.png"))
    a = ap.parse_args()
    title_f, sub_f = font("Unbounded-ExtraBold.ttf", 30), font("JetBrainsMono-Regular.ttf", 18)
    card_t, card_b = font("Unbounded-ExtraBold.ttf", 19), font("JetBrainsMono-Regular.ttf", 16)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    # measure the bands first: a stage of up to two items has wide cards, picture on the left
    bands = []
    y = 196
    for kind, title, note, colour, items in STAGES:
        wide = len(items) <= 2
        n = per_row_of(len(items))
        rows = (len(items) + n - 1) // n
        cw = (W - 2 * M - (n - 1) * GAP) // n
        if wide:
            pw, ph = 380, 214
            ch = ph
        else:
            pw, ph = cw, round(cw * 9 / 16)
            lines = max(len(wrap(probe, t, card_b, cw - 36)) for _, _, t in items)
            ch = ph + 58 + lines * 22 + 16
        if kind == "request" or all(src.startswith("panel:name:") for src, _, _ in items):   # (no pictures: shorter tiles)
            ph = round(cw * 9 / 32)
            ch = ph + 58 + max(len(wrap(probe, t, card_b, cw - 36)) for _, _, t in items) * 22 + 16
        bands.append((kind, title, note, colour, items, wide, cw, pw, ph, ch, y))
        y += 64 + rows * ch + (rows - 1) * GAP + 40
    H = y + 34

    im = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W * 0.28, -160, W * 0.72, 200), fill=(22, 40, 84))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(70)), 0.9)
    d = ImageDraw.Draw(im)

    # the title
    word = font("Unbounded-ExtraBold.ttf", 76)
    tw = d.textlength("Hookshot", font=word)
    gradient_text(im, ((W - tw) / 2, 18), "Hookshot", word)
    d = ImageDraw.Draw(im)
    road = font("Unbounded-ExtraBold.ttf", 30)
    label = "R O A D M A P"
    lw = d.textlength(label, font=road)
    d.text(((W - lw) / 2, 120), label, font=road, fill=TEXT)
    small = font("JetBrainsMono-Regular.ttf", 16)
    upd = "updated " + UPDATED
    d.text((W - M - d.textlength(upd, font=small), 132), upd, font=small, fill=MUTED)
    counts = "   ".join("%d %s" % (len(s[4]), s[1].lower()) for s in STAGES)
    d.text((M, 132), counts, font=small, fill=MUTED)

    for kind, title, note, colour, items, wide, cw, pw, ph, ch, top in bands:
        # the stage's ribbon
        d.rounded_rectangle((M, top, W - M, top + 48), radius=12, fill=CARD, outline=EDGE)
        d.rounded_rectangle((M, top, M + 10, top + 48), radius=5, fill=colour)
        mark(d, kind, M + 40, top + 24, 14, colour)
        d.text((M + 66, top + 7), title, font=title_f, fill=colour)
        d.text((M + 76 + d.textlength(title, font=title_f), top + 15), note, font=sub_f, fill=MUTED)
        per_row = per_row_of(len(items))
        for i, (source, ctitle, ctext) in enumerate(items):
            cx = M + (i % per_row) * (cw + GAP)
            cy = top + 64 + (i // per_row) * (ch + GAP)
            d.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=16, fill=CARD, outline=EDGE)
            pic = picture(source, pw, ph, kind, colour)
            if wide:
                im.paste(pic, (cx, cy), rounded(pic, 16, (True, False, False, True)))
                tx, ty, tw_ = cx + pw + 22, cy + 22, cw - pw - 44
            else:
                im.paste(pic, (cx, cy), rounded(pic, 16))
                tx, ty, tw_ = cx + 18, cy + ph + 16, cw - 36
            d = ImageDraw.Draw(im)
            badge(d, cx + 12, cy + 12, kind, {"done": "DONE", "doing": "IN PROGRESS", "next": "PLANNED", "request": "REQUESTED"}[kind], colour)
            tf, ts = card_t, 19
            while d.textlength(ctitle, font=tf) > tw_ - 6 and ts > 13:   # (a long title is set smaller to fit its card)
                ts -= 1
                tf = font("Unbounded-ExtraBold.ttf", ts)
            d.text((tx, ty + (19 - ts) // 2), ctitle, font=tf, fill=TEXT if kind != "next" else (200, 208, 222))
            for j, line in enumerate(wrap(d, ctext, card_b, tw_)):
                d.text((tx, ty + 34 + j * 22), line, font=card_b, fill=MUTED)
            if kind == "doing":   # (an amber stripe along the bottom: work under way)
                d.rounded_rectangle((cx + (pw if wide else 0) + 1, cy + ch - 6, cx + cw - 1, cy + ch - 1), radius=3,
                                    fill=colour)

    foot = "Contents subject to change. The order follows docs/worklist.md: how bad a problem is, times how many players it reaches."
    d.text(((W - d.textlength(foot, font=small)) / 2, H - 30), foot, font=small, fill=MUTED)
    out = im.convert("RGBA")
    out.putalpha(rounded(out, 28, (True, True, True, True)))
    out.save(a.out, optimize=True)
    print("wrote", a.out, out.size)


if __name__ == "__main__":
    main()
