"""The Retro look's maths (gpu/vk/shaders/fg_scale.comp), the shader's own functions compiled as C++.

n64_colour cuts a colour to the 5 bits a channel of the Nintendo 64's 16-bit picture with the RDP's ordered dither, the magic
square (angrylion-rdp-plus rdp/dither.c): black and white stay black and white, every result is one of the 32 steps, no
pixel is more than a step from its colour, a brighter colour is never darker, and over the square's 4 x 4 pixels the steps
average to the colour (to a sixteenth of a step): a dither, no shift in brightness. The square holds each of 0..7 twice and
repeats every 4 pixels.

N64 + CRT, after Timothy Lottes' public-domain CRT shader (libretro glsl-shaders crt/shaders/crt-lottes.glsl):
- crt_lin and crt_code are an exact pair (a flat colour comes back as it went in), 0 and 1 kept, brighter never darker;
- crt_beam, a line's beam: with no scanlines the light shared linearly between two lines; else Lottes' Gaussian, each beam
  keeping its line's light (its integral the line's colour), the three nearest lines (as crt() adds them) keeping a flat
  colour's mean light at every strength and brightness, brightest in a line's middle, dark lines showing the gaps most and
  bright ones filling out, the gaps deeper as the scanlines get stronger;
- crt_mask, the mask on the window's pixels: none is 1; each of the three is Lottes' own (his Mask() for his shadowMask 2, 1
  and 3, his maskDark 1 - strength and maskLight 1 + strength, ported in this check from his shader) over its mean, so over
  its tile every channel's mean is 1: the picture keeps its light; never negative, and black between phosphors at 100%.
Where the rows, their keys and the pass's branch are is tests/test_fg_scale_post.py's check. No GPU.

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

# (just enough of GLSL for the functions, in a namespace of its own so its abs, max, sqrt and exp2 are the ones found)
SHIM = r'''
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
namespace glsl {
struct ivec2 { int x, y; };
struct vec3 {
    float r, g, b;
    vec3() : r(0), g(0), b(0) {}
    explicit vec3(float v) : r(v), g(v), b(v) {}
    vec3(float x, float y, float z) : r(x), g(y), b(z) {}
    vec3& operator*=(float s) { r *= s, g *= s, b *= s; return *this; }
};
static vec3 operator+(vec3 a, float s) { return {a.r + s, a.g + s, a.b + s}; }
static vec3 operator*(vec3 a, float s) { return {a.r * s, a.g * s, a.b * s}; }
static vec3 operator*(float s, vec3 a) { return a * s; }
static vec3 operator*(vec3 a, vec3 b) { return {a.r * b.r, a.g * b.g, a.b * b.b}; }
static vec3 operator/(vec3 a, float s) { return {a.r / s, a.g / s, a.b / s}; }
static vec3 operator-(float s, vec3 a) { return {s - a.r, s - a.g, s - a.b}; }
static vec3 operator-(vec3 a) { return {-a.r, -a.g, -a.b}; }
static vec3 floor(vec3 a) { return {std::floor(a.r), std::floor(a.g), std::floor(a.b)}; }
static vec3 exp2(vec3 a) { return {std::exp2(a.r), std::exp2(a.g), std::exp2(a.b)}; }
static vec3 sqrt(vec3 a) { return {std::sqrt(a.r), std::sqrt(a.g), std::sqrt(a.b)}; }
static float abs(float v) { return std::fabs(v); }
static float min(float a, float b) { return std::min(a, b); }
static float max(float a, float b) { return std::max(a, b); }
static vec3 min(vec3 a, vec3 b) { return {std::min(a.r, b.r), std::min(a.g, b.g), std::min(a.b, b.b)}; }
static float clamp(float v, float lo, float hi) { return std::min(std::max(v, lo), hi); }
static vec3 clamp(vec3 v, float lo, float hi) { return {clamp(v.r, lo, hi), clamp(v.g, lo, hi), clamp(v.b, lo, hi)}; }
'''

FIXTURE = r'''
}  // namespace glsl
using namespace glsl;
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
static float step_of(float v) { return v * 31.0f; }
static float ch(vec3 v, int i) { return i == 0 ? v.r : i == 1 ? v.g : v.b; }
// Lottes' Mask() (crt-lottes.glsl, public domain), as he wrote it, for the parity check: pos the window pixel's centre times
// 1.000001, as his main() calls it (Mask(gl_FragCoord.xy * 1.000001): without it his 0.166666666 puts a multiple of 6 just
// under a whole number, the wrong phosphor). In double here: his float fract()s near a third sit closer to his 0.333 and 0.666
// than a float's step is at 4K, which the shader's whole-number columns do not
static double fr(double v) { return v - std::floor(v); }
static vec3 lottes_mask(double px, double py, int shadowMask, float maskDark, float maskLight) {
    vec3 mask(maskDark);
    if (shadowMask == 1) {
        float line = maskLight;
        double odd = 0.0;
        if (fr(px * 0.166666666) < 0.5) odd = 1.0;
        if (fr((py + odd) * 0.5) < 0.5) line = maskDark;
        px = fr(px * 0.333333333);
        if (px < 0.333) mask.r = maskLight; else if (px < 0.666) mask.g = maskLight; else mask.b = maskLight;
        mask *= line;
    } else if (shadowMask == 2) {
        px = fr(px * 0.333333333);
        if (px < 0.333) mask.r = maskLight; else if (px < 0.666) mask.g = maskLight; else mask.b = maskLight;
    } else if (shadowMask == 3) {
        px += py * 3.0;
        px = fr(px * 0.166666666);
        if (px < 0.333) mask.r = maskLight; else if (px < 0.666) mask.g = maskLight; else mask.b = maskLight;
    }
    return mask;
}
static vec3 beams(float c, float fy, float scan) {   // (a flat colour c: the three nearest lines, as crt() adds them)
    vec3 sum(0.0f);
    for (int j = -1; j <= 1; j++) {
        const vec3 b = crt_beam(vec3(c), fy - j, scan);
        sum = vec3(sum.r + b.r, sum.g + b.g, sum.b + b.b);
    }
    return sum;
}
int main() {
    // ---- n64_colour
    int seen[8] = {};
    for (int v : kMagic) { CHECK(v >= 0 && v < 8); seen[v]++; }
    for (int n : seen) CHECK(n == 2);
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
        const float frac = c * 31.0f - std::floor(c * 31.0f);
        if (std::fabs(frac - 0.5f) < 0.01f) CHECK(up == 8);   // (half a step above a step: half the square goes up)
    }
    CHECK(worst_mean <= 1.0f / (16.0f * 31.0f) + 1e-5f);   // (the 4 x 4's mean: the colour, to a sixteenth of a step)
    // ---- crt_lin and crt_code: an exact pair, 0 and 1 kept, brighter never darker
    for (int i = 0; i <= 1000; i++) {
        const float c = i / 1000.0f;
        CHECK(std::fabs(crt_code(crt_lin(vec3(c))).g - c) < 1e-6f);
        if (i) CHECK(crt_lin(vec3(c)).r > crt_lin(vec3((i - 1) / 1000.0f)).r);
    }
    CHECK(crt_lin(vec3(0.0f)).r == 0.0f && crt_lin(vec3(1.0f)).r == 1.0f && crt_code(vec3(2.0f)).b == 1.0f && crt_code(vec3(-1.0f)).b == 0.0f);
    // ---- crt_beam
    for (float c : {0.0f, 0.3f, 1.0f})   // (no scanlines: the light shared linearly)
        for (int i = -150; i <= 150; i++) CHECK(std::fabs(crt_beam(vec3(c), i / 100.0f, 0.0f).r - c * std::max(1.0f - std::fabs(i / 100.0f), 0.0f)) < 1e-6f);
    float last_gap = 2.0f;
    for (float scan : {-4.0f, -8.0f, -12.0f}) {
        for (float c : {0.02f, 0.2f, 0.5f, 1.0f}) {
            double integral = 0.0;   // (each beam keeps its line's light)
            for (int i = -3000; i < 3000; i++) integral += crt_beam(vec3(c), (i + 0.5f) / 1000.0f, scan).r / 1000.0;
            CHECK(std::fabs(integral - c) <= 0.002 * c + 1e-7);
            for (int i = 1; i <= 150; i++) CHECK(crt_beam(vec3(c), i / 100.0f, scan).r <= crt_beam(vec3(c), 0.0f, scan).r);
            double mean = 0.0;   // (a flat colour through the three nearest lines: its mean light kept, to 2%)
            for (int i = 0; i < 1000; i++) mean += beams(c, -0.5f + (i + 0.5f) / 1000.0f, scan).r / 1000.0;
            CHECK(std::fabs(mean - c) <= 0.02 * c + 1e-7);
        }
        // (dark parts show the gap between lines most; bright parts fill out; stronger scanlines, deeper gaps)
        const float dark_gap = beams(0.1f, 0.5f, scan).r / beams(0.1f, 0.0f, scan).r;
        const float bright_gap = beams(1.0f, 0.5f, scan).r / beams(1.0f, 0.0f, scan).r;
        CHECK(dark_gap < bright_gap && bright_gap <= 1.0f);
        CHECK(dark_gap < last_gap);
        last_gap = dark_gap;
        // (a wider beam for a brighter line: at a quarter of a line from its middle, more of its peak)
        CHECK(crt_beam(vec3(1.0f), 0.25f, scan).r / crt_beam(vec3(1.0f), 0.0f, scan).r >
              crt_beam(vec3(0.1f), 0.25f, scan).r / crt_beam(vec3(0.1f), 0.0f, scan).r);
    }
    CHECK(beams(0.1f, 0.5f, -8.0f).r / beams(0.1f, 0.0f, -8.0f).r < 0.6f);   // (Medium: visible in the dark)
    // ---- crt_mask
    for (int y = 0; y < 8; y++)
        for (int x = 0; x < 8; x++) { const vec3 m = crt_mask(ivec2{x, y}, 0, 0.7f); CHECK(m.r == 1.0f && m.g == 1.0f && m.b == 1.0f); }
    const int lottes_type[4] = {0, 2, 1, 3};   // (ours: 1 aperture grille, 2 slot mask, 3 shadow mask)
    for (int type = 1; type <= 3; type++)
        for (int s10 = 1; s10 <= 10; s10++) {
            const float s = s10 / 10.0f;
            double mean[3] = {0, 0, 0};
            for (int y = 0; y < 12; y++)
                for (int x = 0; x < 12; x++) {
                    const vec3 m = crt_mask(ivec2{x + 3840, y + 2160}, type, s);   // (far from 0, as on a 4K window)
                    const vec3 his = lottes_mask((x + 3840 + 0.5) * 1.000001, (y + 2160 + 0.5) * 1.000001, lottes_type[type],
                                                 1.0f - s, 1.0f + s);
                    for (int k = 0; k < 3; k++) {
                        CHECK(std::fabs(ch(m, k) * (1.0f - s / 3.0f) - ch(his, k)) < 1e-5f);   // (Lottes' own mask, over its mean)
                        CHECK(ch(m, k) >= 0.0f);
                        mean[k] += ch(m, k) / 144.0;
                    }
                }
            for (double v : mean) CHECK(std::fabs(v - 1.0) < 1e-5);   // (the picture keeps its light)
        }
    for (int x = 0; x < 6; x++) {   // (at 100% the unlit phosphors are black; the aperture grille's stripes run down)
        const vec3 m = crt_mask(ivec2{x, 5}, 1, 1.0f);
        CHECK(ch(m, x % 3) > 1.0f && ch(m, (x + 1) % 3) == 0.0f && ch(m, (x + 2) % 3) == 0.0f);
        const vec3 below = crt_mask(ivec2{x, 6}, 1, 1.0f);
        CHECK(below.r == m.r && below.g == m.g && below.b == m.b);
    }
    std::printf("PASS: n64_colour() 5-bit steps with the RDP's dither; crt_lin/crt_code an exact pair; crt_beam keeps the "
                "light, fills out when bright; crt_mask is Lottes' masks over their mean\n");
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
    widen = re.search(r"const float kWiden = ([0-9.]+);", text)
    if not widen:
        raise SystemExit("fg_scale.comp: no kWiden, how much wider a bright beam is")
    functions = ["vec3 n64_colour(vec3 c, ivec2 t)", "vec3 crt_lin(vec3 c)", "vec3 crt_code(vec3 l)",
                 "vec3 crt_beam(vec3 line, float d, float scan)", "vec3 crt_mask(ivec2 g, int type, float strength)"]
    fixture = (SHIM + "static const int kMagic[16] = {%s};\n" % magic.group(1) +
               "static const float kWiden = %s;\n" % widen.group(1) +
               "".join("static " + block(text, f, "fg_scale.comp") + "\n" for f in functions) + FIXTURE)
    with tempfile.TemporaryDirectory(prefix="fg-retro-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
