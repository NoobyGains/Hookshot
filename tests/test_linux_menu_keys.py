"""On Linux the Insert menu takes its keys from the same queue as on Windows: host/posix/display_sdl.c's keys_update notes
each key on the look it goes down (host/rx_backend.c hos_vk_note_key_press, as host/display.c's WM_KEYDOWN does), once
while it is held, again after it is let go; none while the window is not in front. So the pause menu's Recomp Options
button (host/oot_pause_menu.c), which asks for F1 through that queue, opens the menu on Linux too.

keys_update is cut from the source and compiled with stand-ins for SDL's key state, the window's focus and the queue.

python -I -B tests/test_linux_menu_keys.py [--cc gcc]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cc", "gcc"]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


FIXTURE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
/* VK */
volatile uint8_t hos_posix_keys[256];
volatile int hos_posix_window[4];
static uint8_t sdl[512];
static const uint8_t *hos_sdl_keys(int *n) { *n = (int)sizeof sdl; return sdl; }
static uint32_t hos_sdl_mouse_buttons(void) { return 0; }
static int noted[256];
void hos_vk_note_key_press(unsigned key) { if (key < 256) noted[key]++; }
%s
static int fails;
#define CHECK(c, what) do { if (!(c)) { printf("FAIL: %%s\n", what); fails++; } } while (0)
int main(void) {
    const int f1 = 58;   /* (SDL's scancode for F1) */
    hos_posix_window[0] = 1;
    sdl[f1] = 1;
    keys_update();
    CHECK(noted[VK_F1] == 1, "F1 going down is not noted once");
    CHECK(hos_posix_keys[VK_F1] == 1, "F1 held is not in the key state");
    keys_update();
    keys_update();
    CHECK(noted[VK_F1] == 1, "F1 held is noted again");
    sdl[f1] = 0;
    keys_update();
    sdl[f1] = 1;
    keys_update();
    CHECK(noted[VK_F1] == 2, "F1 pressed again is not noted");
    sdl[f1] = 0;
    keys_update();
    hos_posix_window[0] = 0;
    sdl[f1] = 1;
    keys_update();
    CHECK(noted[VK_F1] == 2, "a key is noted while the window is not in front");
    CHECK(hos_posix_keys[VK_F1] == 0, "a key is in the state while the window is not in front");
    if (!fails) printf("PASS: Linux keys reach the Insert menu's queue on their way down, once\n");
    return fails != 0;
}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    sdl = (ROOT / "host" / "posix" / "display_sdl.c").read_text(encoding="utf-8")
    # (Linux's virtual keys, as host/posix/windows.h has them: tests/test_sdl_mouse_buttons.py's way, so this builds on Windows too)
    win = (ROOT / "host" / "posix" / "windows.h").read_text(encoding="utf-8")
    vk = "\n".join(m.group(0) for m in re.finditer(r"^#define VK_\w+ 0x[0-9A-Fa-f]+", win, re.M))
    rx = (ROOT / "host" / "rx_backend.c").read_text(encoding="utf-8")
    if "void hos_vk_note_key_press(unsigned key) {" not in rx or "#define host_take_key_press NULL" in rx:
        raise SystemExit("FAIL: the Insert menu's key queue is not on every platform (host/rx_backend.c)")
    with tempfile.TemporaryDirectory() as d:
        src, exe = Path(d) / "fixture.c", Path(d) / "fixture.exe"
        src.write_text((FIXTURE % block(sdl, "static void keys_update(void) {")).replace("/* VK */", vk), encoding="utf-8")
        subprocess.run([a.cc, "-std=c11", "-Wall", "-Werror", "-Wno-unused-function", str(src), "-o", str(exe)], check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        print(r.stdout, end="")
        if r.returncode:
            sys.exit(1)


if __name__ == "__main__":
    main()
