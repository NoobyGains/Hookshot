"""The Insert menu's Mods page (Gameplay, Mods): the player's own mods on and off and in load order, kept for the next start in
mods/hookshot-mods.ini by the host (host/mods.c; its own checks: tests/test_mods_list.py). Made-up mod names, no game data.

- gpu/vk/mods_page.h, compiled and run: what is movable (the mods off by their folder's name are not, and stay last), on and
  off, moving up and down, what is pending against this run, the choice handed to the host, the mods on that share files with
  one and who wins them, and the lines the page shows (the label, the detail line, the help, the conflicts line, ordinals);
- vk_menu.cpp's mods_tick, cut out and run with the page's state: Up and Down (wrapping), Page Up and Down, Home and End,
  Left, Right and Enter on and off, the tab keys moving the mod, Esc and a right click going back, the mouse choosing a row,
  setting Off or On by its halves and moving by the arrows; a change saved (mods_commit) only when something changed;
- the menu's wiring, read from the source: the Gameplay row before Bug report, opened ahead of the Controls page's catch-all,
  drawn as page 6, its one slot in the restart question, its value cell, its save through MkwVkHost.mods_save, the pipeline
  report listing the mods this run loaded;
- the interface (AGENTS.md): MKWVK_API_VERSION bumped to 23 for MkwVkHost's mod, mod_shared and mods_save, MkwVkMod's fields,
  and host/rx_backend.c's table giving one function per member in order.

python -I -B tests/test_mods_page.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"

LOGIC = r'''#include "mods_page.h"
#include <cstdio>
#include <map>
using namespace mkwvk::mods_page;
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "FAIL: %s at line %d\n", #c, __LINE__); return 1; } } while (0)
static Mod mod(const char* name, int index, bool on, int files, bool renamed = false, bool exefs = false) {
    Mod m;
    m.name = name, m.index = index, m.on_start = m.on = on, m.files = files, m.renamed = renamed, m.exefs = exefs;
    return m;
}
int main() {
    // (the host's order: Zelda, Voice, Retro, Deep (off in the file), then one off by its folder's name)
    List l;
    l.mods = {mod("Playable Zelda", 0, true, 12), mod("Classic Voice", 1, true, 40), mod("Retro", 2, true, 1, false, true),
              mod("contents/0100/Deep", 3, false, 5), mod("_old/Zelda Hair", 4, false, 2, true)};
    std::map<std::pair<int, int>, int> table = {{{0, 1}, 3}, {{1, 0}, 3}, {{0, 2}, 1}, {{2, 0}, 1}, {{3, 1}, 7}, {{1, 3}, 7}};
    auto shared = [&](int a, int b) { auto it = table.find({a, b}); return it == table.end() ? 0 : it->second; };
    CHECK(l.size() == 5 && l.movable() == 4 && l.on_count() == 3 && !l.pending() && l.key() == 0);
    {   // (the restart slot's number: 0 as started, another for each different choice, the same for the same one)
        List k = l;
        k.toggle(0);
        const int off0 = k.key();
        k.toggle(1);
        const int off01 = k.key();
        k.toggle(1);
        CHECK(off0 != 0 && off01 != 0 && off0 != off01 && k.key() == off0);
        k.toggle(0);
        CHECK(k.key() == 0);
        k.move(0, 1);
        CHECK(k.key() != 0 && k.key() != off0);
    }
    // on and off
    CHECK(!l.set(4, true) && !l.toggle(4) && !l.mods[4].on);   // (off by its folder's name: not the page's)
    CHECK(!l.set(0, true) && !l.set(-1, false) && !l.set(9, false));   // (already so; no such mod)
    CHECK(l.toggle(1) && !l.mods[1].on && l.pending() && l.changed(1) && !l.changed(0));
    CHECK(l.toggle(1) && l.mods[1].on && !l.pending());   // (back as it started: nothing pending)
    // moving: among the movable ones, never past the renamed ones
    CHECK(l.move(0, -1) == 0 && !l.pending());
    CHECK(l.move(0, 1) == 1 && l.mods[0].name == "Classic Voice" && l.mods[1].name == "Playable Zelda" && l.pending());
    CHECK(l.changed(0) && l.changed(1) && !l.changed(2));
    CHECK(l.move(1, -1) == 0 && !l.pending());
    CHECK(l.move(3, 1) == 3 && l.move(4, -1) == 4 && l.mods[4].name == "_old/Zelda Hair");
    CHECK(l.move(3, -1) == 2 && l.mods[2].name == "contents/0100/Deep" && l.mods[3].name == "Retro");
    // the choice for the host: the movable mods' host indexes in order, and on or off each
    std::vector<int> order, on;
    l.toggle(2);   // (Deep on)
    l.choice(&order, &on);
    CHECK((order == std::vector<int>{0, 1, 3, 2}) && (on == std::vector<int>{1, 1, 1, 1}));
    l.move(2, 1), l.toggle(3);   // (as it started)
    CHECK(!l.pending());
    // the mods on that share files: who wins (the later one), none while either is off
    std::vector<Clash> c = clashes(l, 0, shared);
    CHECK(c.size() == 2 && c[0].other == 1 && c[0].files == 3 && !c[0].wins && c[1].other == 2 && c[1].files == 1 && !c[1].wins);
    c = clashes(l, 1, shared);
    CHECK(c.size() == 1 && c[0].other == 0 && c[0].wins);   // (Deep shares 7 with Voice, but is off)
    CHECK(clashes(l, 3, shared).empty() && clashes(l, 4, shared).empty());
    l.move(0, 1);   // (Zelda after Voice: Zelda wins now)
    c = clashes(l, 1, shared);
    CHECK(l.mods[1].name == "Playable Zelda" && c.size() == 2 && c[0].other == 0 && c[0].wins && !c[1].wins);
    l.move(1, -1);
    // the lines shown
    CHECK(ordinal(1) == "1st" && ordinal(2) == "2nd" && ordinal(3) == "3rd" && ordinal(4) == "4th" && ordinal(11) == "11th" &&
          ordinal(12) == "12th" && ordinal(13) == "13th" && ordinal(21) == "21st" && ordinal(22) == "22nd" && ordinal(101) == "101st" &&
          ordinal(111) == "111th");
    CHECK(label(l, 3) == "Deep" && label(l, 4) == "Zelda Hair" && label(l, 9) == "");
    CHECK(detail(l, 0, shared) == "12 files, files also in 2 other mods");
    CHECK(detail(l, 1, shared) == "40 files, 3 also in Playable Zelda: this one wins");
    CHECK(detail(l, 2, shared) == "1 file, exefs left out, 1 also in Playable Zelda: this one wins");
    CHECK(detail(l, 3, shared) == "5 files");   // (off: no conflict to show)
    CHECK(detail(l, 4, shared) == "Off by its folder's name, 2 files");
    l.toggle(2);   // (Retro off: Zelda's one conflict left, with Voice, which wins)
    CHECK(detail(l, 0, shared) == "12 files, 3 also in Classic Voice, which wins");
    CHECK(clash_text(l, 0, shared) == "3 files are also in Classic Voice, lower in the list: its load instead.");
    CHECK(clash_text(l, 1, shared) == "3 files are also in Playable Zelda, higher in the list: this mod's load.");
    CHECK(clash_text(l, 2, shared).empty());
    l.toggle(2);
    CHECK(help(l, 1).rfind("Loads 2nd of the 4 mods; when two mods on have the same file, the one lower in the list wins it. 40 files", 0) == 0);
    CHECK(help(l, 2).find("Its exefs patches are left out") != std::string::npos);
    CHECK(help(l, 3).rfind("Off: the game starts without it. 5 files", 0) == 0);
    CHECK(help(l, 4).rfind("Off by its folder's name", 0) == 0);
    // two mods' last folders alike: the whole names
    List same;
    same.mods = {mod("a/Hair", 0, true, 1), mod("b/Hair", 1, true, 1)};
    CHECK(label(same, 0) == "a/Hair" && label(same, 1) == "b/Hair");
    // more than four conflicts: four named, the rest counted
    List many;
    for (int i = 0; i < 7; i++) many.mods.push_back(mod(("m" + std::to_string(i)).c_str(), i, true, 2));
    const std::string t = clash_text(many, 0, [](int a, int b) { return a != b; });
    CHECK(t.find("also in m4") != std::string::npos && t.find("m5") == std::string::npos &&
          t.find("And 2 more mods share files with it.") != std::string::npos);
    std::puts("PASS: mods_page.h");
    return 0;
}
'''

TICK = r'''#include <algorithm>
#include <cstdio>
#include <cstdint>
#include <cstring>
%(pointer)s
#include "vk_menu_hit.h"
#include "mods_page.h"
namespace mkwvk {
namespace mp = mods_page;
enum { TAB_MOTION = 6 };
constexpr int kModsSlot = TAB_MOTION + 2;
int scrolled_to[TAB_MOTION + 3], wheel_rows[TAB_MOTION + 3];
menu_hit::Map hits;
mp::List mods_list;
int mod_sel = 0, mods_fit = 4, page = 6, commits = 0;
void mods_commit() { commits++; }
%(mods_tick)s
}
using namespace mkwvk;
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "FAIL: %%s at line %%d\n", #c, __LINE__); return 1; } } while (0)
static mp::Mod mod(const char* name, int index, bool renamed = false) {
    mp::Mod m;
    m.name = name, m.index = index, m.on_start = m.on = !renamed, m.files = 1, m.renamed = renamed;
    return m;
}
// (keys: 1 Up, 2 Down, 3 Left, 4 Right, 5 Esc, 7 Enter, 13 Page Up, 14 Page Down, 15 Home, 16 End)
static bool key(int k, bool tab_left = false, bool tab_right = false) {
    bool press[17] = {};
    if (k >= 0) press[k] = true;
    bool changed = false;
    mods_tick(press, tab_left, tab_right, nullptr, 0, 0, false, changed);
    return changed;
}
static bool click(int x, int y, uint32_t buttons, bool moved = false, int wheel = 0) {
    bool press[17] = {};
    MkwVkPointer p{};
    p.pressed = buttons, p.wheel = wheel;
    bool changed = false;
    mods_tick(press, false, false, &p, x, y, moved, changed);
    return changed;
}
int main() {
    for (int i = 0; i < 5; i++) mods_list.mods.push_back(mod(i == 4 ? "_off/r" : ("m" + std::to_string(i)).c_str(), i, i == 4));
    // Up and Down choose, wrapping; Page Up and Down by the rows that fit less one; Home and End
    CHECK(key(1) && mod_sel == 4 && key(2) && mod_sel == 0 && key(2) && mod_sel == 1);
    CHECK(key(14) && mod_sel == 4 && key(13) && mod_sel == 1 && key(16) && mod_sel == 4 && key(15) && mod_sel == 0);
    CHECK(commits == 0 && !mods_list.pending());
    // Left, Right and Enter turn the mod on and off, each a change saved
    CHECK(key(3) && !mods_list.mods[0].on && commits == 1 && key(4) && mods_list.mods[0].on && commits == 2);
    CHECK(key(7) && !mods_list.mods[0].on && commits == 3 && key(7) && mods_list.mods[0].on && commits == 4);
    // the tab keys move it; at an end nothing changes and nothing is saved
    CHECK(!key(-1, true) && commits == 4 && mod_sel == 0);
    CHECK(key(-1, false, true) && mod_sel == 1 && mods_list.mods[1].name == "m0" && commits == 5 && mods_list.pending());
    CHECK(key(-1, true) && mod_sel == 0 && mods_list.mods[0].name == "m0" && commits == 6 && !mods_list.pending());
    // the renamed one: nothing to turn on, nothing to move, nothing saved
    key(16);
    CHECK(mod_sel == 4 && !key(3) && !key(7) && !key(-1, true) && commits == 6 && !mods_list.mods[4].on && mods_list.mods[4].name == "_off/r");
    key(2);   // (wraps to the first)
    // nor can the last movable one go past it
    key(2), key(2), key(2);
    CHECK(mod_sel == 3 && !key(-1, false, true) && mod_sel == 3 && commits == 6);
    // the mouse: a row chosen by moving over it (in view: marked scrolled to), Off's and On's halves, the arrows
    hits.clear(0, 0, 1000, 1000);
    for (int i = 0; i < 5; i++) hits.add(0, i * 100.f, 600, i * 100.f + 90, menu_hit::kRow, i, 300, 600);
    hits.add(250, 105, 270, 185, menu_hit::kButton, 0), hits.add(275, 105, 295, 185, menu_hit::kButton, 1);
    CHECK(click(100, 150, 0, true) && mod_sel == 1 && scrolled_to[kModsSlot] == 1 && commits == 6);
    CHECK(click(350, 150, HOS_MOUSE_LEFT) && !mods_list.mods[1].on && commits == 7);   // (Off's half)
    CHECK(!click(360, 150, HOS_MOUSE_LEFT) && commits == 7);                          // (Off again: no change)
    CHECK(click(550, 150, HOS_MOUSE_LEFT) && mods_list.mods[1].on && commits == 8);    // (On's half)
    CHECK(!click(100, 150, HOS_MOUSE_LEFT) && commits == 8);                           // (the name: chosen already, no change)
    CHECK(click(285, 150, HOS_MOUSE_LEFT) && mod_sel == 2 && mods_list.mods[2].name == "m1" && commits == 9);   // (down)
    mod_sel = 2;
    hits.box[5].y0 = 205, hits.box[5].y1 = 285;   // (the arrows drawn on the new row)
    CHECK(click(260, 250, HOS_MOUSE_LEFT) && mod_sel == 1 && mods_list.mods[1].name == "m1" && commits == 10 && !mods_list.pending());
    CHECK(click(100, 450, 0, false, -2) && wheel_rows[kModsSlot] == -2 && mod_sel == 1);   // (the wheel scrolls, the choice stays)
    // back: Esc, or a right click, to the Gameplay tab
    CHECK(key(5) && page == 0);
    page = 6;
    CHECK(click(100, 150, HOS_MOUSE_RIGHT) && page == 0 && commits == 10);
    // no mods: nothing to choose, Esc still goes back
    mods_list.mods.clear(), page = 6, mod_sel = 0;
    CHECK(!key(2) && !key(7) && mod_sel == 0 && key(5) && page == 0);
    std::puts("PASS: mods_tick");
    return 0;
}
'''


def need(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)


def function(source, start):
    at = source.find(start)
    need(at >= 0, "vk_menu.cpp: %s is missing" % start)
    body = source[at:]
    return body[:body.index("\n}\n") + 3]


def struct_members(api, name):
    body = api[api.index("typedef struct %s {" % name):]
    body = body[:body.index("} %s;" % name)]
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    return re.findall(r"\(\*(\w+)\)\(", body), body


def source_checks():
    menu = (VK / "vk_menu.cpp").read_text(encoding="utf-8")
    api = (VK / "vk_api.h").read_text(encoding="utf-8")
    backend = (ROOT / "host" / "rx_backend.c").read_text(encoding="utf-8")
    # the interface
    version = int(re.search(r"#define MKWVK_API_VERSION (\d+)", api).group(1))
    need(version >= 23, "MKWVK_API_VERSION is %d: MkwVkHost's mods members came with 23" % version)
    fns, body = struct_members(api, "MkwVkHost")
    need(fns[-3:] == ["mod", "mod_shared", "mods_save"] or {"mod", "mod_shared", "mods_save"} <= set(fns),
         "MkwVkHost has no mod, mod_shared and mods_save")
    need(re.search(r"int \(\*mod\)\(int index, MkwVkMod \*out\);", body) and
         re.search(r"int \(\*mods_save\)\(const int \*order, const int \*on, int n\);", body), "MkwVkHost's mods members' types")
    _, mod = struct_members(api, "MkwVkMod")
    for field in ("char name[260];", "int32_t on;", "int32_t files;", "int32_t renamed;", "int32_t exefs;"):
        need(field in mod, "MkwVkMod has no " + field)
    table = backend[backend.index("static const MkwVkHost vk_host = {"):]
    table = re.sub(r"/\*.*?\*/", "", table[table.index("{") + 1:table.index("};")], flags=re.S)
    items = [t.strip() for t in table.split(",") if t.strip()]
    need(items[0] == "MKWVK_API_VERSION" and len(items) == 1 + len(fns),
         "host/rx_backend.c's vk_host gives %d values for MkwVkHost's %d members" % (len(items), 1 + len(fns)))
    at = fns.index("mod") + 1
    need(items[at:at + 3] == ["host_mod", "hos_mods_shared", "hos_mods_save"],
         "vk_host's mod, mod_shared and mods_save are %s" % items[at:at + 3])
    for decl in ("int hos_mods_info(int index, const char **name, int *on, int *files, int *renamed, int *exefs)",
                 "int hos_mods_shared(int a, int b)", "int hos_mods_save(const int *order, const int *on, int n)"):
        need(decl + ";" in backend and decl + " {" in (ROOT / "host" / "mods.c").read_text(encoding="utf-8"),
             "host/rx_backend.c and host/mods.c do not agree on " + decl)
    # the Gameplay row: value-less, after the tab's rows and before Bug report, Restart and Quit
    rows = menu[menu.index("Row rows[] = {"):]
    rows = rows[:rows.index("\n};")]
    names = re.findall(r'\n    \{TAB_GAMEPLAY, "([^"]+)"', rows)
    need("Mods" in names and names[-4:] == ["Mods", "Bug report", "Restart", "Quit"],
         "the Gameplay tab's last rows are %s, not Mods, Bug report, Restart, Quit" % names[-4:])
    need(re.search(r'\{TAB_GAMEPLAY, "Mods", nullptr, 0, 0, 0, nullptr,', rows), "the Mods row has a value")
    need('return r.tab == TAB_GAMEPLAY && !r.value && !strcmp(r.name, "Mods");' in menu, "is_mods_row does not find the row")
    tick = function(menu, "void menu_tick() {")
    opens = tick.find("else if (press[7] && is_mods_row(r)) mods_open()")
    need(0 <= opens < tick.find("else if (press[7] && !r.value && can_bind()) page = 1"),
         "Enter on the Mods row is not handled before the Controls page's catch-all")
    need("} else if (open_now.load() && page == 6) {" in tick and "mods_tick(press, tab_left, tab_right, mouse ? &ptr : nullptr" in tick,
         "menu_tick has no Mods page")
    need("else if (page == 6) draw_mods(k);" in function(menu, "void draw_menu(ui::Ctx& c) {"), "draw_menu does not draw the Mods page")
    need("page = 6" in function(menu, "void mods_open() {"), "mods_open does not show page 6")
    # its restart slot: one for the page, counted pending while its choice differs from this run
    init = function(menu, "void restart_init() {")
    need("mods_slot = restart_state.add(0);" in init and 'restart_names[mods_slot] = "Mods";' in init, "the Mods page has no restart slot")
    need("if (mods_slot >= 0) now[mods_slot] = mods_list.key();" in function(menu, "void restart_values(int* now) {"),
         "restart_values does not give the Mods page's slot its choice's number")
    need("if (is_mods_row(r)) return mods_slot >= 0 && mods_list.pending();" in function(menu, "bool restart_changed(const Row& r) {"),
         "the Mods row is not marked After restart while its choice is pending")
    commit = function(menu, "void mods_commit() {")
    need("mods_list.choice(&order, &on);" in commit and "host->mods_save(order.data(), on.data(), (int)order.size())" in commit and
         "restart_state.note(now);" in commit, "mods_commit does not hand the choice to the host, or the restart question")
    need("is_mods_row(r)" in function(menu, "void row_value_cell(ui::Ctx& c, const Row& r, ImVec2 va, ImVec2 vb, bool selected, float* t0, float* t1) {"),
         "the Mods row's value cell")
    share = function(menu, "std::vector<std::string> share_values(long long pipelines, bool v2, long long computes) {")
    need("if (m.on_start) mods.push_back(m.name);" in share, "the pipeline report does not list the mods this run loaded (host/mods.c's)")
    need(re.search(r"\w+ scroll_at\[TAB_MOTION \+ 3\];", menu) and "kModsSlot = TAB_MOTION + 2" in menu,
         "the Mods page has no scroll slot of its own")
    return function(menu, "void mods_tick(")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    tick = source_checks()
    print("PASS: the menu's wiring and the interface (MKWVK_API_VERSION, MkwVkHost, vk_host)")
    with tempfile.TemporaryDirectory(prefix="mods-page-") as tmp:
        tmp = Path(tmp)
        api = (VK / "vk_api.h").read_text(encoding="utf-8")   # (the mouse's part of it: vk_api.h's rx_nvn.h is C)
        pointer = "\n".join(re.search(p, api, re.S).group(0) for p in (r"enum \{ HOS_MOUSE_LEFT = 1[^}]*\};",
                                                                        r"typedef struct MkwVkPointer \{.*?\} MkwVkPointer;"))
        for name, text in (("logic", LOGIC), ("tick", TICK % {"mods_tick": tick, "pointer": pointer})):
            src, exe = tmp / (name + ".cpp"), tmp / name
            src.write_text(text, encoding="utf-8")
            subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(VK), str(src), "-o", str(exe)],
                           check=True)
            out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
            print(out.strip())


if __name__ == "__main__":
    main()
