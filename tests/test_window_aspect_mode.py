"""Execute the actual startup selection and live-window policy without a game.

Explicit 16:9 and monitor modes retain upstream behavior. Only 2 uses Window.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cc", "clang"]
RUN_ALL_SKIP = {"windows": "compiles the Linux POSIX host shim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="clang")
    args = parser.parse_args()
    host = (ROOT / "host/hos_main.c").read_text()
    start = host.index("    {   /* (hookshot) Widescreen and ultrawide")
    block = host[start:host.index('    hos_log("boot: image', start)]
    source = r'''
#include "host/hos_wide.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#define SEP '/'
extern volatile uint64_t hos_wide_out, hos_wide_scene;
extern volatile float hos_wide_ratio, hos_wide_squeeze, hos_wide_margin;
float hos_aspect_ratio;
uint32_t hos_output_size(int height) { return height ? 1440 : 2560; }
DWORD hos_game_path_a(char *p, int n) { return snprintf(p, n, "./hookshot"); }
void hos_log(const char *fmt, ...) { (void)fmt; }
int GetSystemMetrics(int metric) { return metric == SM_CXSCREEN ? 1600 : 1200; }
static void start(void) {
STARTUP
}
int main(int argc, char **argv) {
    assert(argc == 3);
    const int window = atoi(argv[1]), fixed = atoi(argv[2]);
    start(); assert(hos_wide_window == window);
    const uint64_t before = hos_wide_out;
    if (window) { /* no window was created: headless uses the boot picture */
        assert(hos_wide_aspect() == hos_aspect_ratio);
        float tangent = 0.5f, aspect = 16.0f/9.0f;
        assert(hos_wide_projection(0x1234, &tangent, &aspect));
        assert(aspect == hos_aspect_ratio);
    }
    hos_wide_start(1600, 1200);
    if (window) {
        assert((unsigned)hos_wide_out == 2560 && (hos_wide_out >> 32) == 1920);
        assert(fabsf(hos_wide_aspect() - 4.0f/3.0f) < 1e-5f);
        const uint64_t allocated = hos_wide_out;
        const float jitter = hos_wide_ratio;
        hos_wide_resize(3440, 1440);
        assert(hos_wide_out == allocated && fabsf(hos_wide_aspect() - 3440.0f/1440) < 1e-5f);
        assert(fabsf(hos_wide_squeeze - (16.0f/9.0f)/(3440.0f/1440)) < 1e-5f);
        assert(fabsf(hos_wide_margin - (1-hos_wide_squeeze)/2) < 1e-5f);
        assert(hos_wide_ratio == jitter); /* render-target/DLSS shape never changes */
        hos_wide_resize(0, 0);
        assert(hos_wide_out == allocated && fabsf(hos_wide_aspect() - 3440.0f/1440) < 1e-5f);
        hos_wide_resize(1280, 720);
        assert(hos_wide_margin == 0 && hos_wide_squeeze == 1);
        hos_wide_resize(1600, 40);
        assert(fabsf(hos_wide_aspect() - 48.0f/9.0f) < 1e-5f);
        hos_wide_resize(40, 1600);
        assert(hos_wide_aspect() == 1.25f);
        float t = 0.5f, a = 16.0f/9.0f;
        assert(hos_wide_projection(1, &t, &a));
        a = 2.0f; assert(!hos_wide_projection(1, &t, &a)); /* retire recycled view */
        a = 1.25f; assert(!hos_wide_projection(1, &t, &a)); /* not a tracked camera now */
        assert(hos_wide_ratio == jitter && hos_wide_out == allocated);
        HosWideSize narrow = hos_wide_picture_size(0.025, 1440);
        HosWideSize wide = hos_wide_picture_size(40, 2160);
        assert(narrow.aspect == 1.25f && (unsigned)narrow.scene >= 1920);
        assert(fabsf(wide.aspect - 48.0f/9.0f) < 1e-5f);
        assert((wide.scene >> 32) >= 1080 && (unsigned)wide.picture <= 16384);
    } else {
        assert(hos_wide_out == before);
        const float aspect = hos_wide_aspect();
        hos_wide_resize(3440, 1440);
        assert(hos_wide_aspect() == aspect && hos_wide_out == before);
        if (fixed) assert(!before && aspect == 0);  /* upstream 16:9 */
        else assert((unsigned)before == 1920 && (before >> 32) == 1440);
    }
}
'''.replace("STARTUP", block)
    with tempfile.TemporaryDirectory(prefix="window-aspect-") as temp:
        work = Path(temp)
        path, exe = work / "test.c", work / "test"
        path.write_text(source)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-D_GNU_SOURCE", "-I", str(ROOT),
                        "-I", str(ROOT / "host/posix"), str(path), str(ROOT / "host/hos_wide.c"), "-pthread", "-lm", "-o", str(exe)], check=True)
        for saved, window, fixed in (("", 0, 0), ("ultrawide=2\n", 1, 0),
                                     ("ultrawide=1\n", 0, 0), ("ultrawide=0\noptions_version=6\n", 0, 1),
                                     ("ultrawide=0\noptions_version=4\n", 0, 0)):
            (work / "hookshot_options.ini").write_text(saved)
            subprocess.run([str(exe), str(window), str(fixed)], cwd=work, check=True)
    print("PASS: Window opt-in/2; explicit upstream modes; live resize without target reallocation")


if __name__ == "__main__":
    main()
