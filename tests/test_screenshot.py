"""The Screenshot key (gpu/vk/vk_screenshot.h): F12 saves the picture as the window shows it, after the window's scale pass and
without the menu or the FPS counter, as a PNG in screenshots/ in the game folder. No game or GPU.

1. gpu/vk/screenshot.h (tests/test_screenshot.cpp): the file's name ("Hookshot <date> <time>.png", no colon), the free name
   in the folder, and Native HDR's PQ picture made into SDR (light, Rec. 2020 to 709, the shoulder, sRGB).
2. A round trip through the PNG writer: vk_replay.cpp's own write_png, cut out and compiled with screenshot.h, writes an SDR
   picture and a converted HDR10 one under their names; read back here with zlib, pixel by pixel (the HDR one against this
   file's own float version of the conversion).
3. The key is free: no default control, no key of the menu's, not F11's fullscreen or F9's frame dump, not one the Controls
   page can bind; and its press (cut out of menu_tick and run) asks once per press, with either way the keys are read, never
   while another window has the focus or the row is Off.
4. The save path: present_image hands the picture to the screenshot after the scale pass and the window's copy, before the
   overlays (menu_record) are drawn; the copy is collected after its frame slot's fence; vk_screenshot.cpp copies the scale
   pass's image when it ran, makes the copy visible to the host, reads it after invalidating, and writes on a thread of its
   own. The row, the note and the readme's lines.

python -I -B tests/test_screenshot.py [--cxx g++]
"""
import argparse
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block  # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"


def need(ok, what):
    if not ok:
        raise SystemExit("FAIL: " + what)


def read(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def code(text):
    """the text without // and /* */ comments"""
    return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def compile_run(cxx, source, tmp, name, args=()):
    cpp, exe = Path(tmp) / (name + ".cpp"), Path(tmp) / (name + ".exe")
    cpp.write_text(source, encoding="utf-8")
    subprocess.run([cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I" + str(VK), str(cpp), "-o", str(exe)], check=True,
                   timeout=180)
    # (its failures on stderr, through to the run's output; what it prints on stdout read here)
    return subprocess.run([str(exe), *args], check=True, timeout=60, stdout=subprocess.PIPE, text=True).stdout


# ---- 2. the PNG round trip

PQ = dict(m1=2610 / 16384, m2=2523 / 4096 * 128, c1=3424 / 4096, c2=2413 / 4096 * 32, c3=2392 / 4096 * 32)
REC2020_TO_709 = [[1.66049100, -0.58764114, -0.07284986], [-0.12455047, 1.13289990, -0.00834942],
                  [-0.01815076, -0.10057890, 1.11872966]]
WHITE, PEAK = 200.0, 1000.0


def pq_code(nits):
    """ST 2084's inverse: light to a 10-bit code"""
    y = (nits / 10000) ** PQ["m1"]
    return round(1023 * ((PQ["c1"] + PQ["c2"] * y) / (1 + PQ["c3"] * y)) ** PQ["m2"])


# (packed A2B10G10R10 test pixels: black, the paper white's grey, 10000 nits, Rec. 2020's red at 100 nits, a colour)
HDR_CODES = [(0, 0, 0), (pq_code(WHITE),) * 3, (1023, 1023, 1023), (pq_code(100), 0, 0), (560, 540, 480)]
SDR = bytes([255, 0, 0, 9, 0, 255, 0, 9, 0, 0, 255, 9, 1, 2, 3, 0, 128, 128, 128, 255, 250, 251, 252, 77])


def pq_nits(c):
    e = (min(c, 1023) / 1023) ** (1 / PQ["m2"])
    return 10000 * (max(e - PQ["c1"], 0) / (PQ["c2"] - PQ["c3"] * e)) ** (1 / PQ["m1"])


def tone(x, top, knee=0.9):
    if not x > 0:
        return 0.0
    if x <= knee:
        return x
    if top <= 1:
        return min(x, 1.0)
    t = min(x, top) - knee
    return knee + t / (1 + t * (1 / (1 - knee) - 1 / (top - knee)))


def srgb8(v):
    if not v > 0:
        return 0
    if v >= 1:
        return 255
    e = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
    return int(math.floor(e * 255 + 0.5))


def hdr_expected(rgb):
    light = [pq_nits(c) / WHITE for c in rgb]
    return [srgb8(tone(sum(m * l for m, l in zip(row, light)), PEAK / WHITE)) for row in REC2020_TO_709]


def decode(path):
    data = path.read_bytes()
    need(data[:8] == b"\x89PNG\r\n\x1a\n", "%s is not a PNG" % path.name)
    at, image, size = 8, b"", None
    while at < len(data):
        length = struct.unpack_from(">I", data, at)[0]
        kind, payload = data[at + 4:at + 8], data[at + 8:at + 8 + length]
        need(zlib.crc32(kind + payload) == struct.unpack_from(">I", data, at + 8 + length)[0], "a chunk's CRC")
        if kind == b"IHDR":
            w, h, bits, color = struct.unpack(">IIBB", payload[:10])
            need(bits == 8 and color == 2, "an 8-bit RGB PNG")
            size = (w, h)
        if kind == b"IDAT":
            image += payload
        at += length + 12
    w, h = size
    raw = zlib.decompress(image)
    need(len(raw) == (w * 3 + 1) * h, "the PNG's rows")
    rows = [raw[y * (w * 3 + 1):(y + 1) * (w * 3 + 1)] for y in range(h)]
    need(all(r[0] == 0 for r in rows), "rows without a filter")
    return w, h, b"".join(r[1:] for r in rows)


PNG_FIXTURE = r'''#define _CRT_SECURE_NO_WARNINGS
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <string>
#include <vector>
#include "screenshot.h"
namespace mkwvk {
void logf(const char* format, ...) {
    va_list a;
    va_start(a, format);
    std::vfprintf(stderr, format, a);
    va_end(a);
    std::fputc('\n', stderr);
}
/* PNG */
}  // namespace mkwvk
namespace ss = mkwvk::screenshot;
int main(int argc, char** argv) {
    if (argc < 2) return 2;
    const std::string folder = std::string(argv[1]) + "/";
    std::tm t{};
    t.tm_year = 126, t.tm_mon = 10, t.tm_mday = 14, t.tm_hour = 21, t.tm_min = 5, t.tm_sec = 3;
    auto taken = [](const std::string& p) {
        FILE* f = std::fopen(p.c_str(), "rb");
        if (f) std::fclose(f);
        return f != nullptr;
    };
    static const uint8_t sdr[] = {/* SDR */};
    const std::string a = ss::free_path(folder, t, taken);
    if (a.empty() || !mkwvk::write_png(a.c_str(), sdr, 3, 2)) return 3;
    const unsigned codes[][3] = {/* CODES */};
    constexpr size_t n = sizeof codes / sizeof codes[0];
    uint32_t packed[n];
    for (size_t i = 0; i < n; i++) packed[i] = codes[i][0] | codes[i][1] << 10 | codes[i][2] << 20 | 3u << 30;
    uint8_t rgba[n * 4];
    ss::hdr10_to_rgba8(packed, n, rgba, /* WHITE */, /* PEAK */);
    const std::string b = ss::free_path(folder, t, taken);   // (the same second: its "(2)")
    if (b.empty() || !mkwvk::write_png(b.c_str(), rgba, (uint32_t)n, 1)) return 4;
    std::printf("%s\n%s\n", a.c_str(), b.c_str());
    return 0;
}
'''


def png_round_trip(cxx, tmp):
    replay = read("gpu", "vk", "vk_replay.cpp")
    png = block(replay, "uint32_t crc32(") + "\n" + block(replay, "bool write_png(")
    fixture = (PNG_FIXTURE.replace("/* PNG */", png).replace("/* SDR */", ", ".join(map(str, SDR)))
               .replace("/* CODES */", ", ".join("{%d, %d, %d}" % c for c in HDR_CODES))
               .replace("/* WHITE */", repr(WHITE)).replace("/* PEAK */", repr(PEAK)))
    folder = Path(tmp) / "screenshots"
    folder.mkdir()
    out = compile_run(cxx, fixture, tmp, "png", [str(folder)]).split("\n")
    names = sorted(p.name for p in folder.iterdir())
    need(names == ["Hookshot 2026-11-14 21-05-03 (2).png", "Hookshot 2026-11-14 21-05-03.png"],
         "the two pictures of one second are not named as they should be (or left parts behind): %s" % names)
    need(Path(out[0]).name == names[1] and Path(out[1]).name == names[0], "the first is the plain name, the second its (2)")
    w, h, rgb = decode(folder / names[1])
    need((w, h) == (3, 2), "the SDR picture's size")
    need(rgb == bytes(v for i, v in enumerate(SDR) if i % 4 != 3), "the SDR picture's pixels (alpha left out)")
    w, h, rgb = decode(folder / names[0])
    need((w, h) == (len(HDR_CODES), 1), "the HDR picture's size")
    for i, codes in enumerate(HDR_CODES):
        got, want = list(rgb[i * 3:i * 3 + 3]), hdr_expected(codes)
        need(all(abs(g - x) <= 1 for g, x in zip(got, want)), "HDR pixel %d %s: %s, not %s" % (i, codes, got, want))
    need(list(rgb[0:3]) == [0, 0, 0] and list(rgb[6:9]) == [255, 255, 255], "black stays black, 10000 nits is white")
    need(245 <= rgb[3] < 255, "the paper white is a grey just under white, never PQ's washed-out code (%d)" % rgb[3])
    need(rgb[10] == 0 and rgb[11] == 0, "Rec. 2020's red is red alone")


# ---- 3. the key is free, and its press

PRESS_FIXTURE = r'''#include <cstdio>
#include <cstdlib>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
constexpr int VK_F12 = 0x7B;
bool down = false;
int queued = 0, asks = 0;
short GetAsyncKeyState(int vk) { return vk == VK_F12 && down ? (short)0x8000 : (short)0; }
int take(int vk) { const int q = vk == VK_F12 ? queued : 0; if (vk == VK_F12) queued = 0; return q; }
struct Host { int (*take_key_press)(int); } windows{take}, linux_{nullptr};
Host* host = nullptr;
struct { int screenshot_key = 1; } opts;
void screenshot_ask() { asks++; }
void tick(bool mine, bool shot_script) {
/* BLOCK */
}
int main() {
    // (Linux: the key's state read each frame, a press once on its way down)
    host = &linux_;
    down = true;
    for (int i = 0; i < 5; i++) tick(true, false);
    CHECK(asks == 1);   // (held: one picture)
    down = false, tick(true, false), down = true, tick(true, false);
    CHECK(asks == 2);
    down = false, tick(true, false);
    down = true, tick(false, false), down = false, tick(false, false);
    CHECK(asks == 2);   // (another window had the focus)
    opts.screenshot_key = 0, down = true, tick(true, false), down = false, tick(true, false);
    CHECK(asks == 2);   // (the row Off)
    opts.screenshot_key = 1;
    // (Windows: the window's WM_KEYDOWN queued, taken once; held without a new press, nothing)
    host = &windows;
    queued = 1, tick(true, false);
    CHECK(asks == 3 && queued == 0);
    down = true, tick(true, false), tick(true, false);
    CHECK(asks == 3);
    queued = 1, tick(false, false);
    CHECK(asks == 3 && queued == 0);   // (taken, but not ours: no picture, and no old press left to come later)
    // (RX_VK_MENU_SCRIPT's SHOT, and not with the row Off)
    tick(true, true);
    CHECK(asks == 4);
    opts.screenshot_key = 0, tick(true, true);
    CHECK(asks == 4);
    std::puts("press: once a press, focus and the row respected");
    return 0;
}
'''


def key_is_free(cxx, tmp):
    menu, hid, display = read("gpu", "vk", "vk_menu.cpp"), read("host", "nn_hid.c"), read("host", "display.c")
    sdl, replay = read("host", "posix", "display_sdl.c"), read("gpu", "vk", "vk_replay.cpp")
    defaults = block(hid, "static const unsigned char key_default[HOS_KEY_N][2] = {")
    need("VK_F12" not in defaults and "0x7B" not in defaults, "a control takes F12 by default (host/nn_hid.c key_default)")
    tick = menu[menu.index("void menu_tick() {"):menu.index("void menu_record(")]
    keys = re.search(r"static const int keys\[K_N\] = \{(.*?)\};", tick, re.S)
    need(keys and "VK_F12" not in keys.group(1), "F12 is one of the menu's own keys")
    bindable = block(menu, "const std::vector<int>& bindable_keys() {")
    need("for (int c = VK_F2; c <= VK_F11; c++) k.push_back(c);" in bindable and "VK_F12" not in bindable,
         "the Controls page can bind F12 to a control (bindable_keys)")
    need("VK_F12" not in code(display) and "VK_F12" not in code(replay), "the window or the renderer does something else with F12")
    need(not re.search(r"scancode == 69\b", sdl), "the Linux window does something else with F12 (scancode 69)")
    need("GetAsyncKeyState(VK_F9)" in replay, "the frame dump's key moved (RX_VK_DUMP_KEY): check it is not F12")
    need("wp == VK_F11" in display, "fullscreen's key moved: check it is not F12")
    # (F12 named in the menu's code only by the key names' range and the Screenshot key's block)
    sites = [m.start() for m in re.finditer(r"\bVK_F12\b", code(menu))]
    shot = block(menu, "{   // (hookshot) the Screenshot key, F12")
    need(len(sites) == 3 and code(shot).count("VK_F12") == 2, "F12 is read somewhere else in the menu too")
    print(compile_run(cxx, PRESS_FIXTURE.replace("/* BLOCK */", shot), tmp, "press").strip())


# ---- 4. the save path, the row, the note, the readme

def at(text, marker, where):
    """where marker is in text, or a failure naming it"""
    i = text.find(marker)
    need(i >= 0, "%s has no %r (moved or reshaped? update this check with it)" % (where, marker))
    return i


def save_path():
    replay = read("gpu", "vk", "vk_replay.cpp")
    image = block(replay, "void present_image(")
    pi = "present_image"
    fence = at(image, "vkWaitForFences(dev.device, 1, &f.done, VK_TRUE, UINT64_MAX)", pi)
    collect = at(image, "    screenshot_collect(log_slot);", pi)
    need(fence < at(image, "framelog_collect(log_slot);", pi) < collect < at(image, "vkAcquireNextImageKHR(", pi),
         "the screenshot is not collected after its frame slot's fence (and before the slot's command buffer is reset)")
    scaled = at(image, "const VkImage scaled = src && view ? framegen_scale(f.cmd, view, src, sw, sh, crop, rect.w, rect.h, native_pq)", pi)
    shown = at(image, "blit_crop_to_rect(f.cmd, scaled, rect.w, rect.h, nullptr, dst, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, rect);", pi)
    record = at(image, "    screenshot_record(f.cmd, log_slot, {scaled, src, sw, sh, crop, rect.w, rect.h, native_pq, "
                "present_kind.load() != 0});", pi)
    need(scaled < shown < record < at(image, "    menu_record(f.cmd, index,", pi),
         "the screenshot is not taken from the scale pass's picture, after the window got it and before the menu and the FPS "
         "counter are drawn over it")
    need(image.count("screenshot_record(") == 1 and image.count("screenshot_collect(") == 1, "one record and one collect a present")
    need('#include "vk_screenshot.h"' in replay, "vk_replay.cpp does not include vk_screenshot.h")

    shot = read("gpu", "vk", "vk_screenshot.cpp")
    record = block(shot, "void screenshot_record(VkCommandBuffer cmd, int slot, const ShownPicture& p) {")
    need("vkCmdCopyImageToBuffer(cmd, p.scaled, VK_IMAGE_LAYOUT_GENERAL, next.buf, 1, &whole);" in record,
         "the scale pass's image is not what is copied when it ran")
    need(record.index("full_barrier(cmd);") < record.index("vkCmdCopyImageToBuffer(") and
         record.rindex("vkCmdCopyImageToBuffer(") < record.index("host_read(cmd, next.buf, bytes);"),
         "the copy is not ordered after the picture's writes, or not made visible to the host")
    need("|| p.made) return;" in record, "a frame frame generation made can be taken")
    need("rb.slot >= 0 || writing.load(" in record, "a second picture can be copied over one still read back or written")
    need("create_buffer_cached(" in record, "the readback is not in cached host memory (slow CPU reads)")
    collect = block(shot, "void screenshot_collect(int slot) {")
    need(collect.index("invalidate_mapped(rb.buf_alloc") < collect.index("std::thread("),
         "the readback is read before it is invalidated (non-coherent memory)")
    writer = block(shot, "void write_shot(const Job& j) {")
    need("hdr10_to_rgba8(" in writer and "if (j.pq)" in writer, "Native HDR's picture is not made SDR: a washed-out PNG")
    need("write_png(path.c_str()" in writer and "screenshot::free_path(" in writer and "screenshot::kFolder" in writer,
         "the picture is not written as a PNG under a free name in the screenshots folder")
    need(writer.index("writing.store(false") < writer.index("write_png("), "the readback is held while the file is written")
    need("game_module_path(" in shot and "CP_ACP" not in shot, "the folder is not the game folder's, as UTF-8")
    includes = re.findall(r'^#include "([^"]+)"', shot, re.M)
    need(includes[-1] == "vk_work.h", "vk_screenshot.cpp's commands do not go through the recorder (vk_work.h last)")

    menu, header = read("gpu", "vk", "vk_menu.cpp"), read("gpu", "vk", "vk_menu.h")
    need("int screenshot_key = 1;" in header, "the Screenshot key is not on by default")
    need(re.search(r'\{TAB_CONTROLS, "Screenshot key", &opts\.screenshot_key, 0, 1, 1, tx_screenshot_key,[^}]*nullptr, false, true\}',
                   menu), "the Controls tab has no Screenshot key row (kept out of the Quality preset)")
    need(menu.index('"Compact menu key", &opts.compact_menu_key') < menu.index('"Screenshot key", &opts.screenshot_key'),
         "the Screenshot key row is not after the Compact menu key")
    need('const char* tx_screenshot_key(int v) { return v ? "F12" : "Off"; }' in menu, "the row's choices")
    rec = block(menu, "void menu_record(VkCommandBuffer cmd, uint32_t index, uint32_t w, uint32_t h) {")
    need("const bool shot_note = screenshot_note(&shot_saved);" in rec and "&& !shot_note) {" in rec,
         "a frame with only the note shows nothing")
    need(rec.index("draw_corner(c, timer, deaths);") < rec.index("if (shot_note) draw_screenshot_note(c, shot_saved);") <
         rec.rindex("ui::record(cmd, index, w, h);"), "the note is not drawn last, over the overlays")
    note = block(menu, "void draw_screenshot_note(ui::Ctx& c, bool saved) {")
    need('"Screenshot saved"' in note and '"Screenshot not saved"' in note and "outlined_right(" in note,
         "the note does not say Screenshot saved in the overlays' outlined style")

    readme = read("readme.md")
    need("| | Screenshot key | Off, F12 " in readme and readme.index("| | Compact menu key |") < readme.index("| | Screenshot key |"),
         "readme.md's option table has no Screenshot key line after the Compact menu key")
    controls = readme[readme.index("### Controls"):]
    need("<kbd>F12</kbd>" in controls[:2000] and "`screenshots`" in controls[:2000], "readme.md's Controls do not say F12 saves a screenshot")
    need("`SHOT`" in read("docs", "development.md"), "docs/development.md: RX_VK_MENU_SCRIPT's SHOT")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    save_path()
    with tempfile.TemporaryDirectory(prefix="screenshot-") as tmp:
        cpp = (ROOT / "tests" / "test_screenshot.cpp").read_text(encoding="utf-8")
        print(compile_run(a.cxx, cpp, tmp, "unit").strip())
        png_round_trip(a.cxx, tmp)
        key_is_free(a.cxx, tmp)
    print("PASS: the Screenshot key: its name, its SDR picture, the PNG, a free key, the scale pass's picture without the overlays")


if __name__ == "__main__":
    main()
