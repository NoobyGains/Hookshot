"""The start-up screen's turning Hookshot: nx2/logo_rgba.py packs assets/hookshot_turn.png's frames into a header, zstd-
compressed, and vk_imgui.cpp unpacks them with ZSTD_decompress into one texture.

Checked here, with the real picture: the header's numbers (width, height, frames, frames to a row) describe a sheet of
square frames that holds every frame; the bytes in it unpack to exactly the picture's RGBA pixels; a second write with
the picture unchanged keeps the header as it was (no new compression at every build); a missing picture gives a header
without HOOKSHOT_TURN, which the renderer takes as "turn the flat logo". No game or GPU.

    python -I -B tests/test_logo_turn.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

RUN_ALL_MODULES = ["zstandard"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import logo_rgba  # noqa: E402
import zstandard  # noqa: E402


def check(ok, what):
    if not ok:
        raise SystemExit("FAIL: " + what)


def main():
    text = logo_rgba.turn_header()
    check("#define HOOKSHOT_TURN 1" in text, "no frames in the header: " + text.split("\n", 1)[0])
    w, h, frames, cols = (int(v) for v in re.search(
        r"hookshot_turn_w = (\d+), hookshot_turn_h = (\d+), hookshot_turn_frames = (\d+), hookshot_turn_cols = (\d+);", text).groups())
    cell = w // cols
    check(w % cols == 0 and h % cell == 0 and (h // cell) * cols >= frames, "the sheet is not %d square frames %d to a row" % (frames, cols))
    size = int(re.search(r"hookshot_turn_zst\[(\d+)\]", text).group(1))
    body = text[text.index("{") + 1:text.rindex("}")]
    packed = bytes(int(v) for v in body.replace("\n", "").split(",") if v.strip())
    check(len(packed) == size, "the array holds %d bytes, its size says %d" % (len(packed), size))
    pixels = zstandard.ZstdDecompressor().decompress(packed)
    pw, ph, want = logo_rgba.decode(open(logo_rgba.TURN, "rb").read())
    check((pw, ph) == (w, h) and pixels == want, "the packed frames do not unpack to the picture's pixels")
    with tempfile.TemporaryDirectory(prefix="logo-turn-") as tmp:
        out = os.path.join(tmp, "hookshot_turn.h")
        first = logo_rgba.write_turn(out)
        stamp = os.path.getmtime(out)
        check(logo_rgba.write_turn(out) == first and os.path.getmtime(out) == stamp, "an unchanged picture was written again")
        check("HOOKSHOT_TURN" not in logo_rgba.turn_header(os.path.join(tmp, "missing.png")), "a missing picture still gives frames")
    print("PASS: %d frames of %dx%d, %d to a row, %d KB packed for %d KB of pixels; unchanged pictures are not packed again"
          % (frames, cell, cell, cols, size // 1024, len(pixels) // 1024))


if __name__ == "__main__":
    main()
