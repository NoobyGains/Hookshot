"""The window pass's last step (gpu/vk/shaders/fg_scale.comp finish()), the shader's own functions compiled as C++.

Brightness (brighten(), the code to the power gamma = 100 / the row's percent): the game's picture bit for bit at 100% (finish()
with gamma 1); black and white kept at every step of the row; a brighter colour never darker; greys stay grey; each step
up never darker than the one below and the mid-tones lighter above 100%, darker below.
Where the rows are and how they reach the shader is tests/test_fg_scale_post.py's check. No GPU.

python -I -B tests/test_fg_scale_finish.py [--cxx g++]
"""
import argparse
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
static float clamp(float v, float lo, float hi) { return std::min(std::max(v, lo), hi); }
static vec3 clamp(vec3 v, float lo, float hi) { return {clamp(v.r, lo, hi), clamp(v.g, lo, hi), clamp(v.b, lo, hi)}; }
static vec3 pow(vec3 a, vec3 e) { return {std::pow(a.r, e.r), std::pow(a.g, e.g), std::pow(a.b, e.b)}; }
struct { float gamma = 1.0f; int cvd = 0; } pc;
'''

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
    std::printf("PASS: finish() is the picture at the defaults; brighten() keeps black, white and greys, rises with the colour "
                "and with the row\n");
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    text = COMP.read_text(encoding="utf-8")
    functions = ["vec3 brighten(vec3 c, float gamma)", "vec3 finish(vec3 c)"]
    fixture = SHIM + "".join("static " + block(text, f, "fg_scale.comp") + "\n" for f in functions) + FIXTURE
    with tempfile.TemporaryDirectory(prefix="fg-finish-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Wno-unused-function", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
