"""The Retro look's maths (gpu/vk/shaders/fg_scale.comp), the shader's own n64_colour() and crt_lines() compiled as C++.

n64_colour cuts a colour to the 5 bits a channel of the Nintendo 64's 16-bit picture with the RDP's ordered dither, the magic
square (angrylion-rdp-plus rdp/dither.c): black and white stay black and white, every result is one of the 32 steps, no
pixel is more than a step from its colour, a brighter colour is never darker, and over the square's 4 x 4 pixels the steps
average to the colour (to a sixteenth of a step): a dither, no shift in brightness. The square holds each of 0..7 twice and
repeats every 4 pixels. crt_lines, N64 + CRT's scanlines: brightest in a line's middle, darker between lines, the mean light
of a line kept, and none where the window has 2 or fewer of its pixels to a line. Where the row, its key and the pass's
branch are is tests/test_fg_scale_post.py's check. No GPU.

python -I -B tests/test_fg_scale_retro.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block   # noqa: E402

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "gpu" / "vk" / "shaders" / "fg_scale.comp"

# (just enough of GLSL for the two functions)
SHIM = r'''
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
struct ivec2 { int x, y; };
struct vec3 {
    float r, g, b;
    vec3() : r(0), g(0), b(0) {}
    explicit vec3(float v) : r(v), g(v), b(v) {}
    vec3(float x, float y, float z) : r(x), g(y), b(z) {}
};
static vec3 operator+(vec3 a, float s) { return {a.r + s, a.g + s, a.b + s}; }
static vec3 operator*(vec3 a, float s) { return {a.r * s, a.g * s, a.b * s}; }
static vec3 operator/(vec3 a, float s) { return {a.r / s, a.g / s, a.b / s}; }
static vec3 floor(vec3 a) { return {std::floor(a.r), std::floor(a.g), std::floor(a.b)}; }
static vec3 min(vec3 a, vec3 b) { return {std::min(a.r, b.r), std::min(a.g, b.g), std::min(a.b, b.b)}; }
static float clamp(float v, float lo, float hi) { return std::min(std::max(v, lo), hi); }
static vec3 clamp(vec3 v, float lo, float hi) { return {clamp(v.r, lo, hi), clamp(v.g, lo, hi), clamp(v.b, lo, hi)}; }
using std::cos;
'''

FIXTURE = r'''
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
static float step_of(float v) { return v * 31.0f; }
int main() {
    // the square: each of 0..7 twice
    int seen[8] = {};
    for (int v : kMagic) { CHECK(v >= 0 && v < 8); seen[v]++; }
    for (int n : seen) CHECK(n == 2);
    // black and white at every pixel of the square, and the square repeating every 4 pixels
    for (int y = 0; y < 4; y++)
        for (int x = 0; x < 4; x++) {
            CHECK(n64_colour(vec3(0.0f), ivec2{x, y}).r == 0.0f);
            CHECK(n64_colour(vec3(1.0f), ivec2{x, y}).g == 1.0f);
            CHECK(n64_colour(vec3(1.5f), ivec2{x, y}).b == 1.0f && n64_colour(vec3(-0.5f), ivec2{x, y}).b == 0.0f);
            for (float c : {0.1f, 0.37f, 0.5f, 0.83f})
                CHECK(n64_colour(vec3(c), ivec2{x, y}).r == n64_colour(vec3(c), ivec2{x + 4, y + 8}).r);
        }
    float worst_mean = 0.0f;
    for (int i = 0; i <= 2550; i++) {
        const float c = i / 2550.0f;
        float sum = 0.0f;
        int up = 0;
        for (int y = 0; y < 4; y++)
            for (int x = 0; x < 4; x++) {
                const vec3 o = n64_colour(vec3(c, 1.0f - c, c * 0.5f), ivec2{x, y});
                for (float v : {o.r, o.g, o.b}) {
                    CHECK(v >= 0.0f && v <= 1.0f);
                    CHECK(std::fabs(step_of(v) - std::round(step_of(v))) < 1e-4f);   // (one of the 32 steps)
                }
                CHECK(std::fabs(o.r - c) < 1.0f / 31.0f);   // (never a step or more from the colour)
                if (i) CHECK(o.r >= n64_colour(vec3((i - 1) / 2550.0f), ivec2{x, y}).r);   // (brighter is never darker)
                sum += o.r;
                up += o.r > std::floor(c * 31.0f) / 31.0f + 1e-6f;
            }
        worst_mean = std::max(worst_mean, std::fabs(sum / 16.0f - c));
        // (half a step above a step: half the square goes up, the dither, not a rounding)
        const float frac = c * 31.0f - std::floor(c * 31.0f);
        if (std::fabs(frac - 0.5f) < 0.01f) CHECK(up == 8);
    }
    CHECK(worst_mean <= 1.0f / (16.0f * 31.0f) + 1e-5f);   // (the 4 x 4's mean: the colour, to a sixteenth of a step)
    // the scanlines: none at 2 window pixels to a line or fewer; from 3 the mean light of a line kept, brightest in the middle
    for (float lines : {0.5f, 1.0f, 2.0f})
        for (int i = 0; i < 100; i++) CHECK(crt_lines(i / 100.0f, lines) == 1.0f);
    float last_dip = 1.0f;
    for (float lines : {2.25f, 2.5f, 2.75f, 3.0f, 4.5f, 9.0f}) {
        double mean = 0.0;
        float lo = 2.0f, hi = 0.0f;
        for (int i = 0; i < 1000; i++) {
            const float v = crt_lines((i + 0.5f) / 1000.0f, lines);
            mean += v / 1000.0;
            lo = std::min(lo, v), hi = std::max(hi, v);
        }
        CHECK(std::fabs(mean - 1.0) < 1e-3);
        CHECK(crt_lines(0.5f, lines) >= hi - 1e-6f && crt_lines(0.0f, lines) <= lo + 1e-6f);
        CHECK(lo >= 0.85f && hi <= 1.15f);   // (faint)
        CHECK(crt_lines(0.0f, lines) <= last_dip);   // (deeper from 2 to 3 lines, then the same)
        last_dip = crt_lines(0.0f, lines);
    }
    CHECK(last_dip < 0.9f);
    std::printf("PASS: n64_colour() keeps black and white, steps of 5 bits, a dither whose 4 x 4 mean is the colour; "
                "crt_lines() faint, the mean kept, none under 2 pixels a line\n");
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    text = COMP.read_text(encoding="utf-8")
    magic = re.search(r"const int kMagic\[16\] = int\[\]\(([^)]*)\);", text)
    if not magic:
        raise SystemExit("fg_scale.comp: no kMagic[16], the RDP's magic square")
    values = [int(v) for v in magic.group(1).split(",")]
    if values != [0, 6, 1, 7, 4, 2, 5, 3, 3, 5, 2, 4, 7, 1, 6, 0]:
        raise SystemExit("kMagic is not the RDP's magic square (angrylion-rdp-plus rdp/dither.c magic_matrix): %s" % values)
    fixture = (SHIM + "static const int kMagic[16] = {%s};\n" % magic.group(1) +
               "static " + block(text, "vec3 n64_colour(vec3 c, ivec2 t)", "fg_scale.comp") + "\n" +
               "static " + block(text, "float crt_lines(float t, float lines)", "fg_scale.comp") + "\n" + FIXTURE)
    with tempfile.TemporaryDirectory(prefix="fg-retro-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
