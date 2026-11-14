"""Execute the live host -> renderer menu-side contract, without a game or GPU."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cc", "clang", "--cxx", "{cxx}"]
RUN_ALL_SKIP = {"windows": "compiles the Linux POSIX host shim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    backend = (ROOT / "host/rx_backend.c").read_text()
    start = backend.index("static float host_wide_menus(")
    host = backend[start:backend.index("\nint hos_mouse_pointer", start)]
    renderer = (ROOT / "gpu/vk/vk_framegen.cpp").read_text()
    start = renderer.index("struct WideSides {")
    sides = renderer[start:renderer.index("\nstd::atomic<WideSides> wide_now", start)]
    source = r'''
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdlib>
extern "C" {
#include "host/hos_wide.h"
float hos_aspect_ratio;
uint32_t hos_output_size(int height) { return height ? 1440 : 2560; }
void hos_log(const char *, ...) {}
extern volatile float hos_wide_ratio;
HOST
}
static void side_log(const char *, ...) {}
#define logf side_log
struct { float (*wide_menus)(uint32_t); } callbacks = {host_wide_menus}, *host = &callbacks;
struct { int wide_menus; } opts;
std::atomic<int64_t> world_drawn_at{0}, wheel_drawn_at{0};
int64_t presents_now = 10;
SIDES
int main() {
    hos_wide_window = 1;
    hos_wide_start(1280,720);
    const float jitter = hos_wide_ratio;
    for (int mode = 0; mode <= 2; ++mode) {
        opts.wide_menus = mode;
        hos_wide_resize(2520,1080);
        const WideSides wide = wide_sides();
        assert(wide.side == mode);
        assert(std::fabs(wide.x0 - (mode ? (1-(16.0f/9)/(21.0f/9))/2 : 0)) < 1e-5f);
        hos_wide_resize(1280,720);
        const WideSides restored = wide_sides();
        assert(restored.x0 == 0 && restored.side == 0 && !wide_possible.load());
        hos_wide_resize(2448,1848);
        const WideSides narrow = wide_sides();
        assert(narrow.x0 == 0 && narrow.side == 0);
        assert(hos_wide_ratio == jitter);
    }
}
'''.replace("HOST", host).replace("SIDES", sides)
    with tempfile.TemporaryDirectory(prefix="window-menu-sides-") as temp:
        work = Path(temp)
        fixture, obj, exe = work / "test.cpp", work / "wide.o", work / "test"
        fixture.write_text(source)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-D_GNU_SOURCE",
                        "-I", str(ROOT / "host/posix"), "-c", str(ROOT / "host/hos_wide.c"), "-o", str(obj)], check=True)
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT),
                        str(fixture), str(obj), "-pthread", "-lm", "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: live host margin reaches blurred/black menu sides; 16:9 restores without bars; DLSS ratio fixed")


if __name__ == "__main__":
    main()
