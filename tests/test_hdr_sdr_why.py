"""With the menu's HDR on and the swapchain left SDR, the log and the HDR row say why, from Windows' own setting.

NVIDIA's Vulkan driver can list no HDR10 surface while Windows has HDR on for the display (seen on an RTX 4090, where
NvAPI's own HDR capabilities query failed too, until a clean reinstall of the same driver). The log said
"is HDR on in the display settings?" all the same, which sent players to a setting that was already on. create_swapchain
now tells the cases apart (dev.hdr_sdr_why): no VK_EXT_swapchain_colorspace, HDR off in Windows, HDR on in Windows but no
HDR10 surface from the driver, and not known (Linux, or a Windows that doesn't say). Compile create_swapchain's HDR lines
and the HDR row's hint (hn_hdr) with stubs and check each case, that the line names the display asked about, and that it
is said again only when the reason or the display changes, or the menu's HDR was turned off in between. On Windows, also
compile system_hdr_on, the real one: it answers "not known" with no window, names the desktop's display, and its own
copy of Windows 11 24H2's structure has the Windows SDK's layout and numbers (where the SDK has it). Its time a call is
printed, since create_swapchain asks at each swapchain. No game or GPU is needed.
"""
import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    for at in range(opening, len(text)):
        depth += text[at] == "{"
        depth -= text[at] == "}"
        if depth == 0:
            return text[start:at + 1]
    raise SystemExit("unterminated block: " + marker)


FIXTURE = r"""
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL %d: %s (last line: %s)\n", __LINE__, #x, said.c_str()); return 1; } } while (0)
enum VkFormat { VK_FORMAT_B8G8R8A8_UNORM = 44, VK_FORMAT_A2R10G10B10_UNORM_PACK32 = 58, VK_FORMAT_A2B10G10R10_UNORM_PACK32 = 64 };
enum VkColorSpaceKHR { VK_COLOR_SPACE_SRGB_NONLINEAR_KHR = 0, VK_COLOR_SPACE_HDR10_ST2084_EXT = 1000104008 };
struct VkSurfaceFormatKHR { VkFormat format; VkColorSpaceKHR colorSpace; };
/* ENUM */
struct Device { bool swapchain_colorspace = true, hdr = false; HdrSdrWhy hdr_sdr_why = hdr_sdr_none; } dev;
struct Options { int hdr = 1, hdr_white = 200, hdr_peak = 1000; } opts;
int windows_says = -1;   // (system_hdr_on's answer: 1 on, 0 off, -1 not known)
const char* windows_display = "Screen A";   // (and the display it names)
int system_hdr_on(std::string* display) {
    if (display) *display = windows_display;
    return windows_says;
}
std::string said;
int lines = 0;
void logf(const char* fmt, ...) {
    char b[1024];
    va_list a;
    va_start(a, fmt);
    std::vsnprintf(b, sizeof b, fmt, a);
    va_end(a);
    said = b, lines++;
}
VkFormat pick(const std::vector<VkSurfaceFormatKHR>& formats) {
    VkSurfaceFormatKHR fmt = formats[0];
/* PICK */
    return fmt.format;
}
/* HINT */
int main() {
    const std::vector<VkSurfaceFormatKHR> sdr{{VK_FORMAT_B8G8R8A8_UNORM, VK_COLOR_SPACE_SRGB_NONLINEAR_KHR}};
    std::vector<VkSurfaceFormatKHR> hdr = sdr;
    hdr.push_back({VK_FORMAT_A2B10G10R10_UNORM_PACK32, VK_COLOR_SPACE_HDR10_ST2084_EXT});
    // (an HDR10 surface: taken, nothing to explain)
    CHECK(pick(hdr) == VK_FORMAT_A2B10G10R10_UNORM_PACK32 && dev.hdr && dev.hdr_sdr_why == hdr_sdr_none);
    CHECK(lines == 1 && std::strstr(said.c_str(), "an HDR10 surface (format 64)"));
    CHECK(hn_hdr(1, -1) == nullptr);
    // (Windows has HDR on, the driver lists none: the driver is named, not the setting)
    windows_says = 1;
    CHECK(pick(sdr) == VK_FORMAT_B8G8R8A8_UNORM && !dev.hdr && dev.hdr_sdr_why == hdr_sdr_driver);
    CHECK(lines == 2 && std::strstr(said.c_str(), "though Windows has HDR on") && std::strstr(said.c_str(), "graphics driver") &&
          !std::strstr(said.c_str(), "is HDR on in the display settings?"));
    CHECK(std::strstr(said.c_str(), "the display (Screen A) lists no HDR10 surface"));   // (the display asked about is named)
    CHECK(std::strstr(said.c_str(), "clean reinstall"));                                  // (and what to do)
    CHECK(hn_hdr(1, -1) && std::strstr(hn_hdr(1, -1), "Windows has HDR on") && hn_hdr(2, -1) == hn_hdr(1, -1));
    CHECK(hn_hdr(0, -1) == nullptr);   // (the row Off: no word on it)
    pick(sdr);   // (the swapchain made again, the same answer: not said again)
    CHECK(lines == 2);
    // (the window moved to another display, the same answer there: said for that one, and for the first when it is back)
    windows_display = "Screen B";
    pick(sdr);
    CHECK(lines == 3 && std::strstr(said.c_str(), "the display (Screen B) lists"));
    windows_display = "Screen A";
    pick(sdr);
    CHECK(lines == 4);
    lines = 2;
    // (Windows has HDR off)
    windows_says = 0;
    pick(sdr);
    CHECK(dev.hdr_sdr_why == hdr_sdr_os_off && lines == 3 && std::strstr(said.c_str(), "HDR is off for this display"));
    CHECK(std::strstr(hn_hdr(1, -1), "HDR is off for this display"));
    // (not known: the question as before)
    windows_says = -1;
    pick(sdr);
    CHECK(dev.hdr_sdr_why == hdr_sdr_unknown && lines == 4 && std::strstr(said.c_str(), "is HDR on in the display settings?"));
    CHECK(std::strstr(hn_hdr(1, -1), "Is HDR on in the display settings?"));
    // (no VK_EXT_swapchain_colorspace: Windows not asked)
    dev.swapchain_colorspace = false, windows_says = 1;
    pick(sdr);
    CHECK(dev.hdr_sdr_why == hdr_sdr_no_extension && lines == 5 && std::strstr(said.c_str(), "no VK_EXT_swapchain_colorspace"));
    CHECK(std::strstr(said.c_str(), "the display lists no HDR10 surface"));   // (no display asked about: none named)
    CHECK(std::strstr(hn_hdr(1, -1), "VK_EXT_swapchain_colorspace"));
    // (HDR turned on in Windows while the game runs: said again)
    dev.swapchain_colorspace = true;
    pick(hdr);
    CHECK(dev.hdr && lines == 6 && std::strstr(said.c_str(), "an HDR10 surface"));
    // (the menu's HDR off: SDR with no reason, no line)
    opts.hdr = 0;
    CHECK(pick(hdr) == VK_FORMAT_B8G8R8A8_UNORM && !dev.hdr && dev.hdr_sdr_why == hdr_sdr_none && lines == 6);
    CHECK(hn_hdr(0, -1) == nullptr);
    // (and on again, the same surface: said again, so a log read later has the line for this try)
    opts.hdr = 1;
    pick(hdr);
    CHECK(dev.hdr && lines == 7 && std::strstr(said.c_str(), "an HDR10 surface"));
    pick(hdr);
    CHECK(lines == 7);
    // (every line the hint can show is among the variants the menu measures, and they end)
    int variants = 0;
    while (hn_hdr(1, variants)) variants++;
    CHECK(variants == hdr_sdr_count - 1);
    for (int why = hdr_sdr_no_extension; why < hdr_sdr_count; why++) {
        dev.hdr_sdr_why = (HdrSdrWhy)why;
        bool listed = false;
        for (int k = 0; k < variants; k++) listed |= hn_hdr(1, -1) == hn_hdr(1, k);
        CHECK(listed);
    }
    std::puts("PASS: with HDR on and an SDR swapchain, the log and the HDR row say why (Windows' setting asked)");
}
"""

# (system_hdr_on, the real one, on Windows: no window, not known; with the desktop's, an answer of 0, 1 or -1 that does not
# crash, and the display's name when the display was found. Whether this PC's display is in HDR is not checked: it is the
# PC's. AdvancedColorInfo2 and its numbers are held against the Windows SDK's where the SDK has them: mingw-w64 from 15,
# behind NTDDI_VERSION, and a Windows SDK that knows NTDDI_WIN11_GE)
SYSTEM = r"""
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0A00
#define NTDDI_VERSION 0x0A00000F
#include <windows.h>
#include <chrono>
#include <cstddef>
#include <cstdio>
#include <cwchar>
#include <string>
#include <vector>
static HWND main_window;
/* SYSTEM */
#if defined(__MINGW64_VERSION_MAJOR) ? __MINGW64_VERSION_MAJOR >= 15 : defined(NTDDI_WIN11_GE)
static_assert(sizeof(AdvancedColorInfo2) == sizeof(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO_2), "the SDK's size");
static_assert(offsetof(AdvancedColorInfo2, active_color_mode) == offsetof(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO_2, activeColorMode),
              "the SDK's activeColorMode");
static_assert((int)kGetAdvancedColorInfo2 == (int)DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO_2, "the SDK's request");
static_assert((int)kAdvancedColorModeHdr == (int)DISPLAYCONFIG_ADVANCED_COLOR_MODE_HDR, "the SDK's HDR mode");
static const char* const layout = "held against the SDK's";
#else
static const char* const layout = "not held against the SDK's (these headers lack it)";
#endif
int main() {
    std::string name = "untouched";
    if (system_hdr_on(&name) != -1) return std::fputs("FAIL: system_hdr_on with no window is not 'not known'\n", stderr), 1;
    if (name != "untouched") return std::fputs("FAIL: system_hdr_on named a display with no window\n", stderr), 1;
    main_window = GetDesktopWindow();
    const int on = system_hdr_on(&name);
    if (on < -1 || on > 1) return std::fprintf(stderr, "FAIL: system_hdr_on answered %d\n", on), 1;
    if (on != -1 && (name.empty() || name == "untouched"))
        return std::fputs("FAIL: system_hdr_on answered for a display it did not name\n", stderr), 1;
    if (system_hdr_on(nullptr) != on) return std::fputs("FAIL: system_hdr_on answers otherwise when no name is asked\n", stderr), 1;
    const int calls = 200;
    const auto t0 = std::chrono::steady_clock::now();
    for (int k = 0; k < calls; k++) system_hdr_on(&name);
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count() / calls;
    std::printf("PASS: system_hdr_on: not known with no window; the desktop's display (%s): %d, %.2f ms a call; "
                "AdvancedColorInfo2 %s\n", name.c_str(), on, ms, layout);
}
"""


def compile_and_run(cxx, source, name, libs=()):
    with tempfile.TemporaryDirectory(prefix="hdr-sdr-why-") as tmp:
        src = Path(tmp) / (name + ".cpp")
        exe = Path(tmp) / (name + (".exe" if os.name == "nt" else ""))
        src.write_text(source, encoding="utf-8")
        if Path(cxx).name.lower() in ("cl", "cl.exe", "clang-cl", "clang-cl.exe"):
            command = [cxx, "/nologo", "/std:c++20", "/EHsc", "/W3", "/WX", "/D_CRT_SECURE_NO_WARNINGS", str(src),
                       "/Fo" + str(Path(tmp) / (name + ".obj")), "/Fe" + str(exe)] + ["%s.lib" % l for l in libs]
        else:
            command = [cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D_CRT_SECURE_NO_WARNINGS", str(src), "-o",
                       str(exe)] + ["-l" + l for l in libs]
        subprocess.run(command, cwd=tmp, check=True)
        subprocess.run([str(exe)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    main_cpp = (ROOT / "gpu" / "vk" / "vk_main.cpp").read_text(encoding="utf-8")
    menu = (ROOT / "gpu" / "vk" / "vk_menu.cpp").read_text(encoding="utf-8")
    internal = (ROOT / "gpu" / "vk" / "vk_internal.h").read_text(encoding="utf-8")

    enum = re.search(r"enum HdrSdrWhy : int \{[^}]*\};", internal)
    if not enum:
        raise SystemExit("FAIL: vk_internal.h has no enum HdrSdrWhy (why the swapchain is SDR with HDR on)")
    swap = block(main_cpp, "bool create_swapchain(")
    begin = swap.find("    dev.hdr = false;\n")
    end = swap.find("    // mailbox when the driver has it")
    if begin < 0 or end < begin:
        raise SystemExit("FAIL: create_swapchain's HDR lines (from dev.hdr = false; to the present mode) are not found")
    pick = swap[begin:end]
    if "system_hdr_on(&display)" not in pick:
        raise SystemExit("FAIL: create_swapchain does not ask Windows whether HDR is on when no HDR10 surface is listed")
    if not re.search(r'\{TAB_GRAPHICS, "HDR", &opts\.hdr, 0, 2, 1, tx_hdr,[^}]*hn_hdr, false, true\}', menu):
        raise SystemExit("FAIL: the HDR row does not show hn_hdr's line (why it stays SDR)")
    hint = block(menu, "const char* hn_hdr(int v, int variant) {")
    compile_and_run(args.cxx, FIXTURE.replace("/* ENUM */", enum.group(0)).replace("/* PICK */", pick)
                    .replace("/* HINT */", hint), "why")

    if os.name == "nt":
        begin = main_cpp.find("#ifdef _WIN32\n// (hookshot) Windows 11 24H2's advanced colour info")
        if begin < 0:
            raise SystemExit("FAIL: vk_main.cpp's AdvancedColorInfo2 (before system_hdr_on) is not found")
        system = block(main_cpp, "int system_hdr_on(std::string* display) {")
        compile_and_run(args.cxx, SYSTEM.replace("/* SYSTEM */", main_cpp[begin:main_cpp.index(system) + len(system)]),
                        "system", libs=("user32",))


if __name__ == "__main__":
    main()
