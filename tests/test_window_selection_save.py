"""Window survives late monitor discovery and shape-list growth in the real menu saver."""
import argparse
from pathlib import Path
import runpy
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cxx", "{cxx}"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.source
    helpers = runpy.run_path(str(root / "tests/test_menu_env_overrides.py"))
    menu = (root / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    source = helpers["fixture"](root)
    start = source.index("void outputs_sync()")
    end = source.index("#ifdef _WIN32", start)
    source = source[:start] + r'''
#include "hos_wide.h"
int ultrawide_read = 2;
uint32_t screen_w = 0, screen_h = 0;
bool screen_size(uint32_t* w, uint32_t* h) {
    *w = screen_w; *h = screen_h; return screen_w != 0;
}
bool host_screen_size(uint32_t* w, uint32_t* h) { return screen_size(w, h); }
struct { struct { unsigned width, height; } swap_extent; } dev;
int upscaler() { return 0; }
#include "upscaler_rows.h"
namespace ur = upscaler_rows;
''' + source[end:]
    start = source.index("struct Out {")
    end = source.index("const char* tx(int)", start)
    source = source[:start] + menu[menu.index("struct Out {"):menu.index("/// The Render resolution: the value chosen")] + source[end:]
    source = source.replace('struct Host { int (*binding)(int, int, int); }',
                            'struct Host { int (*binding)(int, int, int); float (*aspect_ratio)() = nullptr; }')
    start = source.index("void env_part()")
    end = source.index("std::string slurp()", start)
    source = source[:start] + helpers["definition"](menu, "void outputs_sync") + "\n" + source[end:]
    source = source[:source.index("int main(int argc")] + helpers["definition"](menu, "const char* tx_ultrawide") + r'''
#include "menu_restart.h"
menu_restart::State restart_state;
int restart_slot_of(const Row& r) { return r.value == &opts.ultrawide ? 0 : -1; }
bool menu_refresh = false;
''' + helpers["definition"](menu, "void outputs_follow_screen") + r'''
int main(int argc, char** argv) {
    CHECK(argc == 3);
    ini_file = argv[1];
    opts.output_res = parse_output("2560x1440");
    opts.ultrawide = 2;
    outputs_sync(); // menu_init, before the window's screen size is known
    restart_state.add(opts.ultrawide);
    save();
    CHECK(has("ultrawide=2\n") && has("output_res=2560x1440\n"));
    screen_w = atoi(argv[2]); screen_h = 1440;
    save(); // a harmless setting saved after the monitor became known
    puts(slurp().c_str());
    CHECK(has("ultrawide=2\n"));
    CHECK(has("output_res=2560x1440\n"));
    CHECK(opts.ultrawide == aspect_window_value());
    CHECK(strcmp(tx_ultrawide(opts.ultrawide), "Window") == 0);
    // Late modes are appended; neither Window nor an existing output is an index into the shape list.
    screen_w = 2448; screen_h = 1848;
    for (int i = 0; i < 30; ++i) outputs_follow_screen();
    save();
    CHECK(has("ultrawide=2\n") && has("output_res=2560x1440\n"));
    CHECK(opts.ultrawide == aspect_window_value());
    CHECK(strcmp(tx_ultrawide(opts.ultrawide), "Window") == 0);
    CHECK(aspect_started == aspect_window_value());
    CHECK(!restart_state.pending(&opts.ultrawide));
    // Main's explicit 16:9 and Monitor's shape still serialize as 0 and 1.
    opts.ultrawide = aspect_of_choice(opts.output_res, 0);
    save(); CHECK(has("ultrawide=0\n"));
    opts.ultrawide = aspect_of_choice(opts.output_res, 1);
    save(); CHECK(has("ultrawide=1\n"));
    puts("PASS: Window and output size survive late screen discovery and added shapes; explicit modes unchanged");
}
'''
    with tempfile.TemporaryDirectory(prefix="window-selection-save-") as tmp:
        work = Path(tmp)
        src, exe = work / "check.cpp", work / "check.exe"
        src.write_text(source, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-unused-but-set-global", "-D_CRT_SECURE_NO_WARNINGS", "-I", str(root / "host"),
                        "-I", str(root / "gpu/vk/compat"), "-I", str(root / "gpu/vk"), str(src), "-o", str(exe)], check=True)
        for width in (5120, 2560):
            subprocess.run([str(exe), str(work / "hookshot_options.ini"), str(width)], check=True)


if __name__ == "__main__":
    main()
