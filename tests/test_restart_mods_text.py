"""The restart line and question name which mods the Mods page has switched or moved (Longshot PR #305, on this tree's Mods
page): vk_menu.cpp's mods_changes, cut out and compiled against gpu/vk/mods_page.h and menu_restart.h with made-up mods, then
the three places that use it, read from the source. No game, GPU or game data.

- a mod switched Off or On since the start is told by its name and its switch's word, in the list's order now;
- a mod moved (its place is not its start position) is told as the order, not as a switch; both together are both;
- nothing changed tells nothing (no false "Restart needed");
- the line and the question list a mod's change under the restart slot of the Mods page, not as "Mods" alone, and
  restart_texts asks the page's own list (no second copy of the start kept).

python -I -B tests/test_restart_mods_text.py [--cxx g++]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

DRIVER = r'''#include <cstdio>
#include <string>
#include <vector>
#include "mods_page.h"
#include "menu_restart.h"
namespace mp = mkwvk::mods_page;
namespace mr = mkwvk::menu_restart;
namespace i18n { const char* tr(const char* s) { return s; } }
mp::List mods_list;
@@CUT@@
static mp::Mod mod(const char* name, int index, bool on_start, bool on) {
    mp::Mod m;
    m.name = name, m.index = index, m.on_start = on_start, m.on = on, m.files = 1;
    return m;
}
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "FAIL: %s at line %d\n", #c, __LINE__); return 1; } } while (0)
int main() {
    // (nothing changed: nothing to restart for)
    mods_list.mods = {mod("Zelda", 0, true, true), mod("Voice", 1, false, false), mod("Retro", 2, true, true)};
    mr::ModChanges c = mods_changes();
    CHECK(c.switched.empty() && !c.moved);
    // (one switched Off, one On: told by name and word, in the list's order)
    mods_list.mods[0].on = false, mods_list.mods[1].on = true;
    c = mods_changes();
    CHECK(c.switched.size() == 2 && c.switched[0] == "Zelda (Off)" && c.switched[1] == "Voice (On)" && !c.moved);
    // (switched back: nothing)
    mods_list.mods[0].on = true, mods_list.mods[1].on = false;
    CHECK(mods_changes().switched.empty());
    // (two moved: the order is told, no switch)
    std::swap(mods_list.mods[0], mods_list.mods[2]);
    c = mods_changes();
    CHECK(c.switched.empty() && c.moved);
    // (moved and switched: both)
    mods_list.mods[1].on = true;
    c = mods_changes();
    CHECK(c.switched.size() == 1 && c.switched[0] == "Voice (On)" && c.moved);
    std::printf("ok\n");
    return 0;
}
'''


def function(source, start):
    """The function that begins at start, to its closing brace at the margin"""
    at = source.index(start)
    return source[at:source.index("\n}\n", at) + 3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    args = p.parse_args()
    menu = (VK / "vk_menu.cpp").read_text(encoding="utf-8")
    cut = function(menu, "mr::ModChanges mods_changes() {")
    with tempfile.TemporaryDirectory(prefix="restart-mods-") as tmp:
        src, exe = Path(tmp) / "driver.cpp", Path(tmp) / "driver.exe"
        src.write_text(DRIVER.replace("@@CUT@@", cut), encoding="utf-8")
        subprocess.run([args.cxx, "-x", "c++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(VK), str(src), "-o", str(exe)],
                       check=True)
        out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
        if out.strip() != "ok":
            raise SystemExit("FAIL: " + out)
    print("PASS: mods_changes: switched by name and word, moved as the order, nothing changed tells nothing")

    # a negative control: a copy that compares the wrong flag is caught by the same driver
    broken = cut.replace("m.on != m.on_start", "false")
    with tempfile.TemporaryDirectory(prefix="restart-mods-neg-") as tmp:
        src, exe = Path(tmp) / "driver.cpp", Path(tmp) / "driver.exe"
        src.write_text(DRIVER.replace("@@CUT@@", broken), encoding="utf-8")
        subprocess.run([args.cxx, "-x", "c++", "-std=c++20", "-I", str(VK), str(src), "-o", str(exe)], check=True)
        if subprocess.run([str(exe)], capture_output=True).returncode == 0:
            raise SystemExit("FAIL: a mods_changes that never sees a switch was not caught")
    print("PASS: a mods_changes that never tells a switch fails the check")

    # the wiring
    texts = function(menu, "RestartTexts restart_texts() {")
    if "mods_changes()" not in texts or "i != mods_slot" not in texts:
        raise SystemExit("FAIL: restart_texts does not ask the Mods page's list for the mods' changes under its slot")
    if re.search(r"mods_start|mods_keep_start", menu):
        raise SystemExit("FAIL: a second copy of the mods' start is kept (the page's list has it: on_start, index)")
    ask = function(menu, "void draw_ask(ui::Ctx& c) {")
    line = function(menu, "std::string restart_line(ui::Ctx& c, float px, float width) {")
    for what, text in (("draw_ask", ask), ("restart_line", line)):
        if "restart_texts()" not in text:
            raise SystemExit("FAIL: " + what + " does not use restart_texts")
    print("PASS: the line and the question use the page's own list")


if __name__ == "__main__":
    sys.exit(main())
