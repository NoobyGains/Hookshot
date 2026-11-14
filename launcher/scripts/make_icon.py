# /// script
# dependencies = ["pillow==13.0.0"]
# ///
"""App/Assets/longshot.ico, the Windows icon, made from the logo App/Assets/longshot.png: each size scaled down with Lanczos
(premultiplied alpha), under 256 as 32-bit bitmaps with their mask, 256 as a PNG. Run it after changing the logo:

    uv run scripts/make_icon.py
"""
import io
from pathlib import Path
import struct

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def image(logo, size):
    """size's icon image: a PNG for 256, else a DIB (twice the height: BGRA rows bottom up, then the 1-bit mask, rows of 32 bits)"""
    im = logo.convert("RGBa").resize((size, size), Image.Resampling.LANCZOS).convert("RGBA")
    if size == 256:
        out = io.BytesIO()
        im.save(out, "PNG", optimize=True)
        return out.getvalue()
    px = im.tobytes("raw", "BGRA")
    rows = [px[y * size * 4:(y + 1) * size * 4] for y in reversed(range(size))]
    mask = b""
    for row in rows:
        bits = bytearray((size + 31) // 32 * 4)
        for x in range(size):
            if row[x * 4 + 3] == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask += bytes(bits)
    return struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0) + b"".join(rows) + mask


def main():
    logo = Image.open(ROOT / "App" / "Assets" / "longshot.png").convert("RGBA")
    blobs = [image(logo, size) for size in SIZES]
    out = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    for size, blob in zip(SIZES, blobs):
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    (ROOT / "App" / "Assets" / "longshot.ico").write_bytes(out + b"".join(blobs))


if __name__ == "__main__":
    main()
