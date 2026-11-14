"""The window pass's last step (gpu/vk/shaders/fg_scale.comp finish()), the shader's own functions compiled as C++.

Brightness (brighten(), the code to the power gamma = 100 / the row's percent): the game's picture bit for bit at 100% (finish()
with gamma 1); black and white kept at every step of the row; a brighter colour never darker; greys stay grey; each step
up never darker than the one below and the mid-tones lighter above 100%, darker below.

Colour vision (daltonize(), in light through the shader's sRGB to_light and to_code): Off is the picture bit for bit; the
matrices are Machado, Oliveira and Fernandes' (IEEE TVCG 2009, Table 1, severity 1.0) as published, each row summing to 1;
every grey, black and white unchanged for each of the three; red's channel never moved (the daltonize error shift adds to
green and blue only); and the colours each deficiency confuses (red and green for protanopia and deuteranopia, blue and
green or yellow and pink for tritanopia) are further apart as that viewer sees them after it than before.
Where the rows are and how they reach the shader is tests/test_fg_scale_post.py's check. No GPU.

python -I -B tests/test_fg_scale_finish.py [--cxx g++]
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

# (just enough of GLSL, in a namespace of its own so its pow, clamp and dot are the ones found; pc as the push constants)
SHIM = r'''
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
namespace glsl {
struct vec3 {
    float r, g, b;
    vec3() : r(0), g(0), b(0) {}
    explicit vec3(float v) : r(v), g(v), b(v) {}
    vec3(float x, float y, float z) : r(x), g(y), b(z) {}
};
static vec3 operator+(vec3 a, vec3 b) { return {a.r + b.r, a.g + b.g, a.b + b.b}; }
static vec3 operator-(vec3 a, vec3 b) { return {a.r - b.r, a.g - b.g, a.b - b.b}; }
static float clamp(float v, float lo, float hi) { return std::min(std::max(v, lo), hi); }
static vec3 clamp(vec3 v, float lo, float hi) { return {clamp(v.r, lo, hi), clamp(v.g, lo, hi), clamp(v.b, lo, hi)}; }
static float pow(float a, float e) { return std::pow(a, e); }
static vec3 pow(vec3 a, vec3 e) { return {std::pow(a.r, e.r), std::pow(a.g, e.g), std::pow(a.b, e.b)}; }
static float dot(vec3 a, vec3 b) { return a.r * b.r + a.g * b.g + a.b * b.b; }
struct { float gamma = 1.0f; int cvd = 0; } pc;
'''

# (Machado, Oliveira and Fernandes 2009, Table 1 at severity 1.0, rows: protanopia, deuteranopia, tritanopia; as published on
# https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html)
MACHADO = [0.152286, 1.052583, -0.204868, 0.114503, 0.786281, 0.099216, -0.003882, -0.048116, 1.051998,
           0.367322, 0.860646, -0.227968, 0.280085, 0.672501, 0.047413, -0.011820, 0.042940, 0.968881,
           1.255528, -0.076749, -0.178779, -0.078411, 0.930809, 0.147602, 0.004733, 0.691367, 0.303900]

FIXTURE = r'''
}  // namespace glsl
using namespace glsl;
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
static float gamma_of(int percent) { return 100.0f / (float)percent; }   // (vk_framegen.cpp framegen_scale)
int main() {
    // ---- the default: the picture bit for bit
    pc = {};
    for (int i = 0; i <= 255; i++)
        for (int j = 0; j <= 255; j += 17) {
            const vec3 c(i / 255.0f, j / 255.0f, (255 - i) / 255.0f), o = finish(c);
            CHECK(o.r == c.r && o.g == c.g && o.b == c.b);
        }
    // ---- Brightness
    for (int percent = 70; percent <= 150; percent += 5) {
        const float gm = gamma_of(percent);
        CHECK(brighten(vec3(0.0f), gm).r == 0.0f && brighten(vec3(1.0f), gm).g == 1.0f);   // (black and white kept)
        float last = -1.0f;
        for (int i = 0; i <= 1000; i++) {
            const float c = i / 1000.0f;
            const vec3 o = brighten(vec3(c), gm);
            CHECK(o.r == o.g && o.g == o.b);   // (a grey stays grey)
            CHECK(o.r >= last && o.r >= 0.0f && o.r <= 1.0f);   // (brighter never darker)
            last = o.r;
            if (percent > 70) CHECK(o.r >= brighten(vec3(c), gamma_of(percent - 5)).r);   // (a step up never darker)
            if (c > 0.0f && c < 1.0f && percent > 100) CHECK(o.r > c);
            if (c > 0.0f && c < 1.0f && percent < 100) CHECK(o.r < c);
        }
        pc.gamma = gm;
        const vec3 mid = finish(vec3(0.5f));
        CHECK(percent == 100 ? mid.r == 0.5f : (percent > 100) == (mid.r > 0.5f));
    }
    pc = {};
    pc.gamma = gamma_of(150);
    CHECK(finish(vec3(0.5f)).r > 0.6f);   // (150%: mid grey visibly lighter, 0.5 to 0.63)
    pc.gamma = gamma_of(70);
    CHECK(finish(vec3(0.5f)).r < 0.4f);   // (70%: visibly darker, 0.5 to 0.37)
    // ---- Colour vision
    for (int m = 0; m < 27; m += 3) CHECK(std::fabs(kCvd[m] + kCvd[m + 1] + kCvd[m + 2] - 1.0f) < 2e-6f);   // (a grey seen as itself)
    for (int type = 1; type <= 3; type++) {
        pc = {};
        pc.cvd = type;
        for (int i = 0; i <= 255; i++) {   // (greys, black and white unchanged)
            const float v = i / 255.0f;
            const vec3 o = finish(vec3(v));
            CHECK(std::fabs(o.r - v) < 1e-4f && std::fabs(o.g - v) < 1e-4f && std::fabs(o.b - v) < 1e-4f);
        }
        for (int i = 0; i <= 255; i += 15)   // (red's channel never moved; every result in range)
            for (int j = 0; j <= 255; j += 15)
                for (int k = 0; k <= 255; k += 51) {
                    const vec3 c(i / 255.0f, j / 255.0f, k / 255.0f), o = finish(c);
                    CHECK(std::fabs(o.r - c.r) < 1e-4f);
                    CHECK(o.g >= 0.0f && o.g <= 1.0f && o.b >= 0.0f && o.b <= 1.0f);
                }
    }
    // (each type its own matrix: daltonize() against the method written out here from the published table, kRef, not the
    // shader's copy: what the viewer sees, what they miss, red's part of it to green and blue, added back, in range)
    for (int type = 1; type <= 3; type++)
        for (int i = 0; i <= 255; i += 17)
            for (int j = 0; j <= 255; j += 17)
                for (int k = 0; k <= 255; k += 51) {
                    const vec3 l(to_light(i / 255.0f), to_light(j / 255.0f), to_light(k / 255.0f));
                    const float* r = kRef + (type - 1) * 9;
                    const float s[3] = {r[0] * l.r + r[1] * l.g + r[2] * l.b, r[3] * l.r + r[4] * l.g + r[5] * l.b,
                                        r[6] * l.r + r[7] * l.g + r[8] * l.b};
                    const float er = l.r - s[0], eg = l.g - s[1], eb = l.b - s[2];
                    const vec3 want(clamp(l.r, 0.0f, 1.0f), clamp(l.g + 0.7f * er + eg, 0.0f, 1.0f), clamp(l.b + 0.7f * er + eb, 0.0f, 1.0f));
                    const vec3 got = daltonize(l, type);
                    CHECK(std::fabs(got.r - want.r) < 1e-5f && std::fabs(got.g - want.g) < 1e-5f && std::fabs(got.b - want.b) < 1e-5f);
                }
    // (the confused pairs further apart as the viewer sees them: their simulated view, the same model, before and after)
    struct Pair { int type; vec3 a, b; };
    const Pair pairs[] = {{1, {0.8f, 0.2f, 0.1f}, {0.3f, 0.6f, 0.1f}}, {1, {0.9f, 0.3f, 0.2f}, {0.5f, 0.5f, 0.2f}},
                          {2, {0.8f, 0.2f, 0.1f}, {0.3f, 0.6f, 0.1f}}, {2, {0.9f, 0.3f, 0.2f}, {0.5f, 0.5f, 0.2f}},
                          {3, {0.2f, 0.4f, 0.8f}, {0.2f, 0.6f, 0.4f}}, {3, {0.9f, 0.9f, 0.3f}, {0.95f, 0.75f, 0.8f}}};
    for (const Pair& p : pairs) {
        const int m = (p.type - 1) * 9;
        auto light = [](vec3 c) { return vec3(to_light(c.r), to_light(c.g), to_light(c.b)); };
        auto seen = [&](vec3 l) {
            return vec3(dot(vec3(kCvd[m], kCvd[m + 1], kCvd[m + 2]), l), dot(vec3(kCvd[m + 3], kCvd[m + 4], kCvd[m + 5]), l),
                        dot(vec3(kCvd[m + 6], kCvd[m + 7], kCvd[m + 8]), l));
        };
        auto apart = [](vec3 x, vec3 y) { const vec3 d = x - y; return std::sqrt(dot(d, d)); };
        pc = {};
        pc.cvd = p.type;
        const float before = apart(seen(light(p.a)), seen(light(p.b)));
        const float after = apart(seen(light(finish(p.a))), seen(light(finish(p.b))));
        CHECK(after > before * 1.15f);
    }
    std::printf("PASS: finish() is the picture at the defaults; brighten() keeps black, white and greys, rises with the colour "
                "and with the row; daltonize() keeps greys and red, and moves each deficiency's confused colours apart\n");
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    text = COMP.read_text(encoding="utf-8")
    cvd = re.search(r"const float kCvd\[27\] = float\[\]\(([^)]*)\);", text)
    if not cvd:
        raise SystemExit("fg_scale.comp: no kCvd[27], the Colour vision row's matrices")
    values = [float(v) for v in cvd.group(1).split(",")]
    if values != MACHADO:
        raise SystemExit("kCvd is not Machado, Oliveira and Fernandes' Table 1 at severity 1.0: %s" % values)
    # (the shader's sRGB to_light and to_code: its #else, the PQ pair being FG_SCALE_PQ's)
    srgb = re.search(r"#else\n// \(sRGB\)\n(.*?)#endif", text, re.S)
    if not srgb or "float to_light(float c)" not in srgb.group(1) or "float to_code(float l)" not in srgb.group(1):
        raise SystemExit("fg_scale.comp: the sRGB to_light and to_code were not found")
    functions = ["vec3 brighten(vec3 c, float gamma)", "vec3 daltonize(vec3 lin, int type)", "vec3 finish(vec3 c)"]
    fixture = (SHIM + "static const float kCvd[27] = {%s};\n" % cvd.group(1) +
               "static const float kRef[27] = {%s};\n" % ", ".join("%.6ff" % v for v in MACHADO) +
               srgb.group(1).replace("float to_light", "static float to_light").replace("float to_code", "static float to_code") +
               "".join("static " + block(text, f, "fg_scale.comp") + "\n" for f in functions) + FIXTURE)
    with tempfile.TemporaryDirectory(prefix="fg-finish-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
