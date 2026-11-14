"""host/mouse_look.c, mouse look's game-agnostic part, stands alone: it is compiled with nothing but itself, its header and
the C library (no Longshot header, no windows.h, no game memory), so another runtime can take it as it is, and its
functions keep the game cameras' conventions: counts to degrees at 0.1 a count, yaw falling to the right, pitch rising
toward the player unless inverted, the game's wrap (-180 in, 180 out), a direction's pitch as f_80738800 gives it, the view
blend's offset kept, and the two-axis latch that drops what nobody took within its time.
python -I -B tests/test_mouse_look.py   (needs a C compiler)
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAIN = r"""
#include <math.h>
#include <stdio.h>
#include "mouse_look.h"
static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static int near_f(float a, float b) { return fabsf(a - b) < 1e-3f; }
int main(void) {
    const double k = ml_degrees_per_count(1.0, 1.0);
    CHECK(fabs(k - 0.1) < 1e-12 && fabs(ml_degrees_per_count(2.5, 0.5) - 0.125) < 1e-12);
    CHECK(near_f(ml_yaw_by(10, k), -1.0f) && near_f(ml_yaw_by(-10, k), 1.0f));   /* right: the yaw falls */
    CHECK(near_f(ml_pitch_by(4, k, 0), 0.4f) && near_f(ml_pitch_by(4, k, 1), -0.4f));
    CHECK(ml_yaw_by(0, k) == 0.0f && ml_pitch_by(0, k, 1) == 0.0f);
    CHECK(near_f(ml_wrap180(180.0f), -180.0f) && near_f(ml_wrap180(-180.0f), -180.0f) && near_f(ml_wrap180(190.0f), -170.0f));
    CHECK(near_f(ml_wrap180(-540.0f), -180.0f) && near_f(ml_wrap180(725.0f), 5.0f) && isnan(ml_wrap180(NAN)));
    CHECK(ml_clamp(5, -1, 1) == 1 && ml_clamp(-5, -1, 1) == -1 && ml_clamp(0.5f, -1, 1) == 0.5f);
    float p = 99;
    CHECK(ml_pitch_of_vector(1, 0, 0, &p) && near_f(p, 0.0f));
    CHECK(ml_pitch_of_vector(0, 1, 1, &p) && near_f(p, 45.0f));
    CHECK(ml_pitch_of_vector(0, -1, 1, &p) && near_f(p, -45.0f));
    p = 99;
    CHECK(!ml_pitch_of_vector(0, 0, 0, &p) && p == 99 && !ml_pitch_of_vector(NAN, 1, 0, &p));
    /* the game put the pitch at rest (5) and the offset at the last view less it (-6 - 5): with the pitch -6 the offset
       is 0, and the drawn start (pitch + offset) does not move */
    CHECK(near_f(ml_blend_offset_kept(5, -11, -6), 0.0f));
    CHECK(near_f(-6 + ml_blend_offset_kept(5, -11, -6), 5 + -11));
    ml_latch l = {0};
    ml_latch_add(&l, 1000, 100, 3, -2);
    ml_latch_add(&l, 1050, 100, 1, 0);
    CHECK(l.x == 4 && l.y == -2);
    CHECK(ml_latch_take(&l, 0) == 4 && l.x == 0 && l.y == -2);
    ml_latch_add(&l, 1200, 100, 0, 0);   /* (nothing new, and the y waited past its 100: dropped) */
    CHECK(l.y == 0 && ml_latch_take(&l, 1) == 0);
    ml_latch_add(&l, 1300, 100, 0, 7);
    CHECK(ml_latch_take(&l, 1) == 7 && ml_latch_take(&l, 1) == 0);
    if (!fails) printf("PASS\n");
    return fails != 0;
}
"""


class MouseLookTests(unittest.TestCase):
    def test_stands_alone(self):
        source = (ROOT / "host" / "mouse_look.c").read_text(encoding="utf-8")
        header = (ROOT / "host" / "mouse_look.h").read_text(encoding="utf-8")
        for text, name in ((source, "mouse_look.c"), (header, "mouse_look.h")):
            includes = re.findall(r'^#include [<"]([^>"]+)[>"]', text, re.M)
            self.assertTrue(set(includes) <= {"mouse_look.h", "math.h", "stdint.h"}, "%s includes %s" % (name, includes))
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("no C compiler")
        with tempfile.TemporaryDirectory(prefix="hookshot-mouse-look-") as tmp:
            tmp = Path(tmp)
            for name in ("mouse_look.c", "mouse_look.h"):
                shutil.copy(ROOT / "host" / name, tmp / name)   # (alone: no host/ or gpu/ on the include path)
            (tmp / "t.c").write_text(MAIN, encoding="utf-8")
            binary = tmp / ("t.exe" if sys.platform == "win32" else "t")
            build = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(tmp), str(tmp / "t.c"),
                                    str(tmp / "mouse_look.c"), "-o", str(binary), "-lm"], text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("PASS", run.stdout)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=1))
