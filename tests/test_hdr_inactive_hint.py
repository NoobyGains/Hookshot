"""The HDR row says when HDR is chosen but not active (gpu/vk/vk_menu.cpp hn_hdr): the window's picture is SDR because the
display offers no HDR10 surface (Windows' Use HDR off). hn_hdr compiled with a stand-in device: nothing while HDR is Off,
before there is a swapchain, or with an HDR10 one; the line otherwise, and as the row's one variant for the menu's height.
vk_main.cpp's HDR log line is said again when the surface changes, not once only. No GPU.

python -I -B tests/test_hdr_inactive_hint.py [--cxx g++]
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]
CXX = "g++"

FIXTURE = r'''
#include <cstdio>
#include <cstring>
struct { struct { unsigned width = 0; } swap_extent; bool hdr = false; } dev;
/* HINT */
int main() {
    int bad = 0;
#define CHECK(x) do { if (!(x)) { bad++; std::printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
    CHECK(!hn_hdr(1, -1));                                    // (no swapchain yet)
    dev.swap_extent.width = 1920;
    CHECK(!hn_hdr(0, -1));                                    // (HDR Off)
    CHECK(hn_hdr(1, -1) && std::strstr(hn_hdr(2, -1), "Use HDR"));
    dev.hdr = true;
    CHECK(!hn_hdr(1, -1) && !hn_hdr(2, -1));                  // (an HDR10 swapchain: active)
    CHECK(hn_hdr(0, 0) && !hn_hdr(0, 1));                     // (one variant, for the help's height)
    std::printf("%s\n", bad ? "FAILED" : "hint checked");
    return bad != 0;
}
'''


def function(source, head):
    i = source.index(head)
    j = source.index("{", i)
    depth = 0
    for k in range(j, len(source)):
        depth += {"{": 1, "}": -1}.get(source[k], 0)
        if not depth:
            return source[i:k + 1]
    raise AssertionError(head)


class HdrHintTests(unittest.TestCase):
    def test_hint(self):
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        self.assertRegex(menu, r'\{TAB_GRAPHICS, "HDR", &opts\.hdr, 0, 2, 1, tx_hdr,[^{}]*?hn_hdr, false, true\}')
        text = FIXTURE.replace("/* HINT */", function(menu, "const char* hn_hdr(int v, int variant)"))
        with tempfile.TemporaryDirectory(prefix="hookshot-hdr-hint-") as tmp:
            src, exe = Path(tmp) / "hint.cpp", Path(tmp) / "hint.exe"
            src.write_text(text, encoding="utf-8")
            built = subprocess.run([CXX, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(src), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_log_on_change(self):
        main = (ROOT / "gpu/vk/vk_main.cpp").read_text(encoding="utf-8")
        at = main.index("// (hookshot) the Insert menu's HDR: a 10-bit HDR10 surface")
        part = main[at:at + 1600]
        self.assertIn("static int told = -1;", part)
        self.assertIn("if (told != (int)dev.hdr) {", part)
        self.assertNotRegex(part, r"static bool told;\s*if \(!told\)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args, rest = parser.parse_known_args()
    CXX = args.cxx
    unittest.main(argv=[sys.argv[0]] + rest)
