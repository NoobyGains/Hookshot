"""Gohma steers above a 60 fps cap as at 60 (host/oot_high_fps.h oot_turn_factor, nx2/oot_patches.py patch_turn_speed).

The AI turn action ExecuteASApproachStickX (f_8263e8e0; Gohma walks with it) keeps a turn speed per 60 fps frame, turns by it
times the step, and ends by clamping the speed to the applied turn times the step: the bound is speed x step x step. At a step
of 1 that changes nothing; under 1 the speed shrinks by the step squared every frame, so above 60 fps Gohma soon cannot turn,
walks into the walls of her room and never comes down from the ceiling. The patch makes the clamp's two factors one over the
step while the step is under one frame.

The production patch is applied to an authored tail of the lifted shape (the call before it, the two multiplies, the clamp)
and compiled with oot_high_fps.h: at 90, 120, 144, 165 and 240 fps Gohma turns as far a second as at 60, a cap of 60 and 30 fps
keep the game's result bit for bit, a step of 0 or NaN leaves no NaN speed, and the unpatched tail fails the same checks. No
game files or lifted function body are used. After zortos293/Lichii PR #1645 by atk3001.

python -I -B tests/test_turn_speed.py [--cc gcc]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_patches  # noqa: E402

# (the tail: s0 the applied turn's size, [sp+0xc] minus the step into s1, s8 the step, +0x24 the speed into s2; then the game's
# fcsel pair, which clamps the speed to [s1, s0])
TAIL = ('void f_8263e8e0(Ctx *__restrict A64_NOESC c) {\n'
        'c->x[30] = 0x8263eaf8ULL; f_8084fd40(c);\n'
        '@MULS@'
        '    { float _s, _lo, _hi; memcpy(&_s,&c->vreg[2][0],4); memcpy(&_hi,&c->vreg[0][0],4); memcpy(&_lo,&c->vreg[1][0],4);\n'
        '      float _r = _s > _hi ? _hi : _s; if (_s < _lo) _r = _lo; memcpy(&c->vreg[0][0],&_r,4); }\n'
        '}\n')
OLD = oot_patches.TURN_OLD.replace("@", "a64_fpx_mul32_fma32")
LIFTED = '#include "a64.h"\n' + TAIL.replace("@MULS@", OLD)
CONTEXT = """#pragma once
#include <stdint.h>
#include <string.h>
#define A64_NOESC
typedef struct {
    uint64_t x[32], vreg[32][2];
} Ctx;
static inline void a64_vset64(uint64_t *v, uint64_t x) { v[0] = x; v[1] = 0; }
static inline uint64_t a64_fpx_mul32_fma32(Ctx *c, uint64_t a, uint64_t b, uint64_t z) {
    float x, y, r;
    uint32_t u = (uint32_t)a, w = (uint32_t)b;
    (void)c; (void)z;
    memcpy(&x, &u, 4); memcpy(&y, &w, 4);
    r = x * y;
    memcpy(&u, &r, 4);
    return u;
}
static inline void f_8084fd40(Ctx *c) { (void)c; }
"""
FIXTURE = r'''#include "oot_high_fps.h"
#include <stdio.h>
#include "a64.h"

static int timed;   /* (the host gives the frames' time: a cap other than 60) */
static int failures;
#define CHECK(test, what) do { if (!(test)) { printf("FAIL: %s\n", what); failures++; } } while (0)
uint32_t hos_oot_turn_factor(uint32_t factor_bits) { return oot_turn_factor(factor_bits, timed); }
@TAIL@
/* the speed after one frame's clamp: speed, the applied turn (its size) and the step */
static float clamp(float speed, float turn, float step) {
    Ctx c = {0};
    c.vreg[0][0] = oot_float_bits(turn);
    c.vreg[1][0] = oot_float_bits(-step);
    c.vreg[8][0] = oot_float_bits(step);
    c.vreg[2][0] = oot_float_bits(speed);
    f_8263e8e0(&c);
    return oot_bits_float((uint32_t)c.vreg[0][0]);
}
/* radians turned in one second at fps frames a second from a speed of 0.02 a 60 fps frame, the target never reached */
static double second(int fps, int time_given) {
    timed = time_given;
    const float step = 60.0f / (float)fps;
    float speed = 0.02f;
    double turned = 0;
    for (int i = 0; i < fps; i++) {
        const float turn = speed * step;
        turned += turn;
        speed = clamp(speed, turn, step);
    }
    return turned;
}

int main(void) {
    const double at60 = second(60, 0);
    CHECK(at60 > 1.19 && at60 < 1.21, "a cap of 60: 1.2 radians a second, the speed kept");
    static const int rates[] = {90, 120, 144, 165, 240};
    for (int k = 0; k < 5; k++) {
        const double r = second(rates[k], 1);
        if (!(r > at60 * 0.99 && r < at60 * 1.01)) {
            printf("at %d fps: %.4f radians a second, %.4f at 60\n", rates[k], r, at60);
            CHECK(0, "above 60 fps Gohma turns as far a second as at 60");
        }
    }
    /* (the game's own result where the step is 1 or more, or no frame time is given) */
    timed = 0;
    CHECK(clamp(0.02f, 0.01f, 1.0f) == 0.01f, "a cap of 60, a turn near the target: the game's clamp to it");
    CHECK(clamp(0.02f, 0.005f, 0.5f) == 0.0025f, "a cap of 60 in a slow motion of 0.5: the game's clamp");
    timed = 1;
    CHECK(clamp(0.02f, 0.04f, 2.0f) == 0.02f, "30 fps: the game's bound, four times the speed");
    CHECK(oot_turn_factor(oot_float_bits(2.0f), 1) == oot_float_bits(2.0f) &&
          oot_turn_factor(oot_float_bits(-1.0f), 1) == oot_float_bits(-1.0f), "a step of 1 or more keeps the game's factor");
    CHECK(oot_turn_factor(oot_float_bits(-0.25f), 1) == oot_float_bits(-4.0f), "minus a quarter step: minus four");
    CHECK(oot_turn_factor(oot_float_bits(0.25f), 0) == oot_float_bits(0.25f), "no frame time: the game's factor");
    const float paused = clamp(0.02f, 0.0f, 0.0f);
    CHECK(paused == paused && paused == 0.0f, "a step of 0 (paused): the game's 0, not NaN");
    CHECK(oot_turn_factor(oot_float_bits(0.0f / 0.0f), 1) == oot_float_bits(0.0f / 0.0f) &&
          oot_turn_factor(oot_float_bits(1e-30f), 1) == oot_float_bits(1e-30f), "NaN and a tiny step keep the game's factor");
    if (!failures) puts("PASS: turn speed");
    return failures != 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    patched, count = oot_patches.patch_turn_speed(LIFTED)
    assert count == 1 and patched.count(oot_patches.TURN_MARK) == 2, patched
    assert patched.count(oot_patches.TURN_DECL) == 1, patched
    assert oot_patches.patch_turn_speed(patched) == (patched, 1)   # (made before: counted, left as it is)
    hot = LIFTED.replace("a64_fpx_mul32_fma32(c,", "a64_fpx_hot_mul32_fma32(c,")
    made, n = oot_patches.patch_turn_speed(hot)
    assert n == 1 and made.count(oot_patches.TURN_MARK) == 2 and "a64_fpx_hot_mul32_fma32(c," in made
    other = LIFTED.replace("memcpy(&_b,c->vreg[8],4)", "memcpy(&_b,c->vreg[9],4)")   # (another game version)
    assert oot_patches.patch_turn_speed(other) == (other, 0)
    none = LIFTED.replace("void f_8263e8e0", "void f_9263e8e0")
    assert oot_patches.patch_turn_speed(none) == (none, 0)
    region = LIFTED.replace("f_8084fd40(c);\n", "f_8084fd40(c);\n{ if (A64_FF_ON(c)) { }\n", 1)   # (a fast float region)
    assert oot_patches.patch_turn_speed(region) == (region, 0)
    out, counts, lines = oot_patches.patch_file(LIFTED, "code_000.c")
    assert counts["turn sites"] == 1 and out == patched and any("turn action" in line for line in lines), (counts, lines)
    with tempfile.TemporaryDirectory(prefix="turn-speed-") as directory:
        directory = Path(directory)
        (directory / "a64.h").write_text(CONTEXT, encoding="utf-8")
        source, binary = directory / "fixture.c", directory / "fixture.exe"
        command = [args.cc, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-label", "-I", str(ROOT / "host"),
                   str(source), "-o", str(binary), "-lm"]
        tail = patched.replace('#include "a64.h"\n', "").replace(oot_patches.TURN_DECL, "")
        source.write_text(FIXTURE.replace("@TAIL@", tail), encoding="utf-8")
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True, timeout=60)
        # (the game's tail compiles, then fails the same checks)
        source.write_text(FIXTURE.replace("@TAIL@", LIFTED.replace('#include "a64.h"\n', "")), encoding="utf-8")
        subprocess.run(command, check=True)
        game = subprocess.run([str(binary)], text=True, capture_output=True, timeout=60)
        if game.returncode == 0 or "above 60 fps Gohma turns as far a second as at 60" not in game.stdout:
            raise SystemExit("FAIL: the game's tail did not fail the above-60 check:\n" + game.stdout)
        print("PASS: the game's tail rejected by the same checks")


if __name__ == "__main__":
    main()
