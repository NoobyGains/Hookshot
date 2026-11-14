"""The physics' water managers keep their 60-Hz simulation above a 60 fps cap (nx2/oot_patches.py WHOLE_SITES, host/frame_whole.h).

phive::InteractiveWaterMgr (f_83895f20) and phive::ResponsiveWaterMgr (f_838a2660) run on the floor web's base: each update cuts
the frame's seconds over 1/60 to whole simulation steps (into x8), queues at most 3 and skips the simulation under 1. Under a
quarter-frame step that cut is 0 every update, so above 60 fps their water, ice and sand surfaces stood still. With the sites in
WHOLE_SITES the fraction is carried per manager (x19), as for the floor web.

The production patch is applied to authored updates of the lifted shape (the cut, then the 0..3 clamp) and compiled with
frame_whole.h: at 240, 144 and 120 Hz each manager runs 60 steps a second (59 to 60 where the step is not exact) with its own
remainder; without the frames' time the game's truncation stays; the unpatched updates fail the same checks. No game files or
lifted function body are used. After NX2navi's owater set, which found the two managers.

python -I -B tests/test_water_mgr_steps.py [--cc gcc]
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

CUT = "    c->x[8]=recomp_fp_to_int(c->vreg[0][0]&UINT64_C(0xffffffff),32,32,1,3,c->fpcr,&c->fpsr);\n"
UPDATE = ('void %s(Ctx *__restrict A64_NOESC c) {\n' + CUT +
          '    { uint64_t _b=c->x[29]; int64_t _o=-32; (void)_b; (void)_o; }\n'
          '    const int32_t steps = (int32_t)c->x[8];\n'
          '    c->x[0] = (uint32_t)(steps < 0 ? 0 : steps > 3 ? 3 : steps);\n'
          '}\n')
LIFTED = '#include "a64.h"\n' + UPDATE % "f_83895f20" + UPDATE % "f_838a2660"
CONTEXT = """#pragma once
#define A64_NOESC
typedef struct {
    uint64_t x[32], vreg[32][2];
    uint32_t fpcr, fpsr;
} Ctx;
"""
FIXTURE = r'''#define _CRT_SECURE_NO_WARNINGS
#include "frame_whole.h"
#include <stdio.h>
#include "a64.h"

static FrameWhole fractions;
static int carry = 1;
static int failures;
#define CHECK(test, what) do { if (!(test)) { printf("FAIL: %s\n", what); failures++; } } while (0)

uint32_t hos_frame_whole(uint64_t at, uint32_t amount_bits) {
    return frame_whole(&fractions, at, amount_bits, carry);
}
uint64_t recomp_fp_to_int(uint64_t bits, int in_width, int out_width, int sign, int mode, uint32_t fpcr, uint32_t *fpsr) {
    float amount;
    uint32_t low = (uint32_t)bits;
    memcpy(&amount, &low, sizeof amount);
    (void)in_width; (void)out_width; (void)sign; (void)mode; (void)fpcr; (void)fpsr;
    return (uint64_t)(int64_t)(int32_t)amount;
}
@UPDATES@
typedef void (*Update)(Ctx *);
static const Update managers[2] = {f_83895f20, f_838a2660};
/* one update of manager m (its object at mgr) with the frame's seconds over 1/60 */
static uint32_t step(int m, uint64_t mgr, float frames) {
    Ctx ctx = {0};
    ctx.x[19] = mgr;
    memcpy(&ctx.vreg[0][0], &frames, sizeof frames);
    managers[m](&ctx);
    return (uint32_t)ctx.x[0];
}

int main(void) {
    static const int rates[] = {240, 144, 120};
    for (int r = 0; r < 3; r++) {
        memset(&fractions, 0, sizeof fractions);
        uint32_t steps[2] = {0, 0};
        for (int frame = 0; frame < rates[r]; frame++)
            for (int m = 0; m < 2; m++) steps[m] += step(m, 0x10000 + (uint64_t)m * 0x10000, 60.0f / (float)rates[r]);
        for (int m = 0; m < 2; m++)
            if (!(steps[m] == 60 || steps[m] == 59)) {
                printf("at %d Hz manager %d: %u steps\n", rates[r], m, steps[m]);
                CHECK(0, "above 60 Hz each water manager runs 60 steps a second");
            }
    }
    memset(&fractions, 0, sizeof fractions);
    CHECK(step(0, 0x10000, 0.75f) == 0 && step(1, 0x20000, 0.5f) == 0, "the managers keep their own remainders (1)");
    CHECK(step(0, 0x10000, 0.25f) == 1 && step(1, 0x20000, 0.25f) == 0, "the managers keep their own remainders (2)");
    CHECK(step(0, 0x10000, 4.75f) == 3, "the game's clamp of three stays");
    carry = 0;
    uint32_t steps = 0;
    for (int frame = 0; frame < 60; frame++) steps += step(0, 0x10000, 1.0f);
    CHECK(steps == 60, "the ordinary 60-Hz path is unchanged");
    CHECK(step(1, 0x20000, 0.25f) == 0 && step(1, 0x20000, 1.75f) == 1, "without the frames' time the game's truncation stays");
    if (!failures) puts("PASS: water manager steps");
    return failures != 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    patched, count = oot_patches.patch_whole_frames(LIFTED)
    assert count == 2 and patched.count("=hos_frame_whole(c->x[19] + 2296, (uint32_t)c->vreg[0][0]);") == 2, patched
    assert CUT not in patched and oot_patches.patch_whole_frames(patched) == (patched, 0)
    with tempfile.TemporaryDirectory(prefix="water-mgr-steps-") as directory:
        directory = Path(directory)
        (directory / "a64.h").write_text(CONTEXT, encoding="utf-8")
        source, binary = directory / "fixture.c", directory / "fixture.exe"
        command = [args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "host"), str(source), "-o", str(binary)]
        source.write_text(FIXTURE.replace("@UPDATES@", patched.replace('#include "a64.h"\n', "").replace(
            oot_patches.WHOLE_DECL, "")), encoding="utf-8")
        subprocess.run(command, check=True)
        subprocess.run([str(binary)], check=True, timeout=30)
        # (the game's updates compile, then fail the same checks)
        source.write_text(FIXTURE.replace("@UPDATES@", LIFTED.replace('#include "a64.h"\n', "")), encoding="utf-8")
        subprocess.run(command, check=True)
        game = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30)
        if game.returncode == 0 or "above 60 Hz each water manager runs 60 steps a second" not in game.stdout:
            raise SystemExit("FAIL: the game's truncation did not fail the above-60 check:\n" + game.stdout)
        print("PASS: the game's truncation rejected by the same checks")


if __name__ == "__main__":
    main()
