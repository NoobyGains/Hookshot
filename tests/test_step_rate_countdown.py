"""A special step rate's phases last their time above a 60 fps cap (host/oot_high_fps.h oot_step_count, nx2/oot_patches.py
patch_step_rate).

The SpStepRate manager (f_82f72df0: the slow motion of a boss's death, a hit, an event) counts each cell's phase down by
max(round(step), 1) an update: one a frame at 60 fps, two at 30, and one every update above 60, so a phase of 60 frames ended
after a quarter of a second at 240 fps. The patch hands the countdown the whole frames of the steps instead, their fraction kept
per cell, while the frames' own time is the step.

The production patch is applied to an authored countdown of the lifted shape (the cell's load, the max's flags, the csinc, the
subtract and the store) and compiled with oot_high_fps.h and frame_whole.h: a 60-frame phase lasts a second, within a frame, at
90 to 240 fps and when two cells count at once; a cap of 60, 30 fps and a step of 0 keep the game's count; the unpatched
countdown fails the same check. No game files or lifted function body are used. After zortos293/Lichii PR #1663 by atk3001.

python -I -B tests/test_step_rate_countdown.py [--cc gcc]
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

# (w9 = trunc(step) rounded to the nearest, as the game's two branches make it, then the countdown's load and the cmp w9, #1)
COUNT = ('void f_82f72df0(Ctx *__restrict A64_NOESC c) {\n'
         '    { float _s; memcpy(&_s,&c->vreg[8][0],4); c->x[9] = (uint32_t)(int32_t)roundf(_s); }\n'
         'L_82f73288:;\n'
         '    c->x[10]=recomp_load32(c,c->x[24] + 152);\n'
         '    { const int32_t _w = (int32_t)c->x[9]; c->z = _w == 1; c->n = _w - 1 < 0; c->v = 0; }\n'
         + oot_patches.STEPRATE_OLD +
         '}\n')
LIFTED = '#include "a64.h"\n' + COUNT
CONTEXT = """#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>
#define A64_NOESC
typedef struct {
    uint64_t x[32], vreg[32][2];
    uint8_t n, z, v;
} Ctx;
static uint32_t guest[64];   /* (the cells' words: guest address / 4) */
static inline uint64_t recomp_load32(Ctx *c, uint64_t at) { (void)c; return guest[at / 4]; }
static inline void recomp_store32(Ctx *c, uint64_t at, uint64_t v) { (void)c; guest[at / 4] = (uint32_t)v; }
"""
FIXTURE = r'''#include "oot_high_fps.h"
#include <stdio.h>
#include "a64.h"

static FrameWhole fractions;
static int timed;   /* (the host gives the frames' time: a cap other than 60) */
static int failures;
#define CHECK(test, what) do { if (!(test)) { printf("FAIL: %s\n", what); failures++; } } while (0)
uint32_t hos_oot_step_count(uint64_t at, uint32_t step_bits, uint32_t game) {
    return oot_step_count(&fractions, at, step_bits, game, timed);
}
@COUNT@
/* one update of the cell at `cell` (the cell's guest address: its countdown at +152) with this step; the count left */
static int32_t update(uint64_t cell, float step) {
    Ctx c = {0};
    c.x[24] = cell;
    c.vreg[8][0] = oot_float_bits(step);
    f_82f72df0(&c);
    return (int32_t)guest[(cell + 152) / 4];
}
/* the updates a phase of `frames` 60 fps frames lasts at fps frames a second */
static int updates(int frames, int fps, int time_given, uint64_t cell) {
    timed = time_given;
    guest[(cell + 152) / 4] = (uint32_t)frames;
    int n = 0;
    while (update(cell, 60.0f / (float)fps) > 0 && n < 100000) n++;
    return n + 1;
}

int main(void) {
    CHECK(updates(60, 60, 0, 0) == 60, "a cap of 60: 60 updates, the game's");
    CHECK(updates(60, 30, 1, 0) == 30, "30 fps: 30 updates, two frames each, the game's");
    static const int rates[] = {90, 120, 144, 165, 240};
    for (int k = 0; k < 5; k++) {
        const int n = updates(60, rates[k], 1, 0);
        const double seconds = n / (double)rates[k];
        if (!(seconds > 1.0 - 1.5 / 60 && seconds < 1.0 + 1.5 / 60)) {
            printf("at %d fps: %d updates, %.3f s\n", rates[k], n, seconds);
            CHECK(0, "above 60 fps a phase of 60 frames lasts a second");
        }
    }
    {   /* (two cells at once, at 240 fps: each its own fraction) */
        timed = 1;
        guest[(0 + 152) / 4] = 60, guest[(64 + 152) / 4] = 30;
        int a = 0, b = 0, n = 0;
        for (; n < 1000 && (!a || !b); n++) {
            if (!a && update(0, 0.25f) <= 0) a = n + 1;
            if (!b && update(64, 0.25f) <= 0) b = n + 1;
        }
        CHECK(a >= 238 && a <= 244 && b >= 118 && b <= 124, "two cells counting at once each keep their own fraction");
    }
    timed = 1;
    guest[(0 + 152) / 4] = 5;
    CHECK(update(0, 0.0f) == 4, "a step of 0 (paused): the game's count of 1");
    CHECK(oot_step_count(&fractions, 8, oot_float_bits(0.0f / 0.0f), 3, 1) == 3, "a NaN step: the game's count");
    CHECK(oot_step_count(&fractions, 8, oot_float_bits(0.4f), 1, 0) == 1, "no frame time: the game's count");
    if (!failures) puts("PASS: special step rate countdown");
    return failures != 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    patched, count = oot_patches.patch_step_rate(LIFTED)
    assert count == 1 and patched.count("hos_oot_step_count(") == 2, patched   # (the call and the declaration)
    assert oot_patches.patch_step_rate(patched) == (patched, 1)   # (made before: counted, left as it is)
    other = LIFTED.replace("c->x[24] + 152", "c->x[24] + 156")   # (another game version)
    assert oot_patches.patch_step_rate(other) == (other, 0)
    none = LIFTED.replace("void f_82f72df0", "void f_92f72df0")
    assert oot_patches.patch_step_rate(none) == (none, 0)
    out, counts, _ = oot_patches.patch_file(LIFTED, "code_000.c")
    assert counts["step rate sites"] == 1 and out == patched, counts
    with tempfile.TemporaryDirectory(prefix="step-rate-") as directory:
        directory = Path(directory)
        (directory / "a64.h").write_text(CONTEXT, encoding="utf-8")
        source, binary = directory / "fixture.c", directory / "fixture.exe"
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-label", "-I", str(ROOT / "host"),
                   str(source), "-o", str(binary), "-lm"]
        body = patched.replace('#include "a64.h"\n', "").replace(oot_patches.STEPRATE_DECL, "")
        source.write_text(FIXTURE.replace("@COUNT@", body), encoding="utf-8")
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True, timeout=60)
        # (the game's countdown compiles, then fails the same checks)
        source.write_text(FIXTURE.replace("@COUNT@", COUNT), encoding="utf-8")
        subprocess.run(command, check=True)
        game = subprocess.run([str(binary)], text=True, capture_output=True, timeout=60)
        if game.returncode == 0 or "above 60 fps a phase of 60 frames lasts a second" not in game.stdout:
            raise SystemExit("FAIL: the game's countdown did not fail the above-60 check:\n" + game.stdout)
        print("PASS: the game's countdown rejected by the same checks")


if __name__ == "__main__":
    main()
