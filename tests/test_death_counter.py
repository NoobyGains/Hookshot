"""The Speedrun timer and the Death counter (gpu/vk/vk_menu.cpp timer_tick and draw_corner, host/oot_deaths.c, nx2/oot_patches.py
patch_life). Checked: the life write's guards run Damage taken first and the Death counter's after it, at both of the
write's sites; hos_oot_life_seen counts a change to 0 as a death and takes it back when the next change is a revive from 0
(a bottled fairy), never below 0; the timer counts real time, stands still while paused, and starts from zero when its row
goes off and on again; the rows and the game side's id are wired.

python -I -B tests/test_death_counter.py [--cc gcc] [--cxx g++]
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUN_ALL_ARGS = ["--cc", "gcc", "--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_patches as patches

CC, CXX = "gcc", "g++"

DEATHS = r'''
#include <stdint.h>
#include <stdio.h>
typedef long LONG;
static LONG InterlockedIncrement(volatile LONG *p) { return ++*p; }
static LONG InterlockedDecrement(volatile LONG *p) { return --*p; }
static void hos_log(const char *f, ...) { (void)f; }
#define OOT_HUD_DEATHS_ID 4085
static int said = -1, calls;
void rx_option_set(int id, int value) { if (id == OOT_HUD_DEATHS_ID) said = value, calls++; }
/* SOURCE */
int main(void) {
    int bad = 0;
#define CHECK(x) do { if (!(x)) { bad++; printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
    hos_oot_life_seen(0, 20);  CHECK(calls == 0);                 /* a raise from 0 with no death counted: nothing */
    hos_oot_life_seen(20, 12); CHECK(calls == 0);                 /* a hit */
    hos_oot_life_seen(12, 0);  CHECK(said == 1);                  /* the hearts ran out */
    hos_oot_life_seen(0, 20);  CHECK(said == 0);                  /* a fairy: taken back */
    hos_oot_life_seen(20, 0);  CHECK(said == 1);
    hos_oot_life_seen(40, 0);  CHECK(said == 2);                  /* (a game over refilled them elsewhere; the next death counts) */
    hos_oot_life_seen(4, 8);   CHECK(said == 2);                  /* healing */
    printf("%s\n", bad ? "FAILED" : "deaths counted");
    return bad != 0;
}
'''

TIMER = r'''
#include <cstdint>
#include <cstdio>
static int64_t clock_ns;
int64_t prof_now() { return clock_ns; }
/* SOURCE */
int main() {
    int bad = 0;
#define CHECK(x) do { if (!(x)) { bad++; std::printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
    clock_ns = 5000000000;
    timer_tick(false, false); CHECK(timer_ns == 0);
    timer_tick(true, false); CHECK(timer_ns == 0);                 /* (just turned on: from zero) */
    clock_ns += 1500000000; timer_tick(true, false); CHECK(timer_ns == 1500000000);
    clock_ns += 2000000000; timer_tick(true, true); CHECK(timer_ns == 1500000000);   /* (the menu open: paused) */
    clock_ns += 1000000000; timer_tick(true, false); CHECK(timer_ns == 2500000000);
    clock_ns -= 10; timer_tick(true, false); CHECK(timer_ns == 2500000000);          /* (a clock going back adds nothing) */
    timer_tick(false, false); CHECK(timer_ns == 0 && timer_last == 0);               /* (off: back to zero) */
    clock_ns += 7; timer_tick(true, false); CHECK(timer_ns == 0);
    std::printf("%s\n", bad ? "FAILED" : "timer counted");
    return bad != 0;
}
'''


def function(source, head):
    i = source.index(head)
    j = source.index("{", i)
    depth = 0
    for k in range(j, len(source)):
        depth += {"{": 1, "}": -1}.get(source[k], 0)
        if not depth:
            return source[i:k + 1]
    raise AssertionError(head)


def run(compiler, flags, text, name):
    with tempfile.TemporaryDirectory(prefix="hookshot-deaths-") as tmp:
        src, exe = Path(tmp) / name, Path(tmp) / (name + ".exe")
        src.write_text(text, encoding="utf-8")
        built = subprocess.run([compiler, *flags, "-Wall", "-Wextra", "-Werror", str(src), "-o", str(exe)],
                               capture_output=True, text=True, timeout=120)
        if built.returncode:
            return built.stdout + built.stderr
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
        return "" if ran.returncode == 0 else ran.stdout + ran.stderr


class DeathCounterTests(unittest.TestCase):
    def test_guards_in_order(self):
        source = '#include "a64.h"\n' + patches.LIFE_HEAD + patches.LIFE_CAS + "\n" + patches.LIFE_CAS + "\n}\n"
        made = patches.patch_life(source)
        self.assertIn("extern void hos_oot_life_seen(uint32_t old, uint32_t next);", made)
        body = made.split(patches.LIFE_HEAD)[1]
        for guard in body.split(patches.LIFE_CAS)[:2]:
            self.assertLess(guard.index("hos_oot_damage("), guard.index("hos_oot_life_seen("))
            self.assertIn("if ((uint32_t)c->x[12] != (uint32_t)c->x[11] &&", guard)

    def test_deaths(self):
        host = (ROOT / "host/oot_deaths.c").read_text(encoding="utf-8")
        host = "\n".join(line for line in host.splitlines() if not line.startswith("#include"))
        self.assertEqual(run(CC, ["-std=c11"], DEATHS.replace("/* SOURCE */", host), "deaths.c"), "")

    def test_timer(self):
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        state = re.search(r"^int64_t timer_ns = 0, timer_last = 0;.*$", menu, re.M).group(0)
        text = TIMER.replace("/* SOURCE */", state + "\n" + function(menu, "void timer_tick(bool on, bool paused)"))
        self.assertEqual(run(CXX, ["-std=c++17"], text, "timer.cpp"), "")

    def test_wiring(self):
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        options = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
        items = (ROOT / "gpu/vk/oot_cheat_items.h").read_text(encoding="utf-8")
        self.assertIn("#define OOT_HUD_DEATHS_ID 4085", items)
        for field, row in (("speedrun_timer", "Speedrun timer"), ("death_counter", "Death counter")):
            self.assertIn("int %s = 0;" % field, options)
            self.assertIn('{TAB_GAMEPLAY, "%s", &opts.%s, 0, 1, 1, tx_onoff,' % (row, field), menu)
        self.assertIn("hud_deaths.store(value, std::memory_order_relaxed);", menu)
        self.assertIn("timer_tick(opts.speedrun_timer && !start, open);", menu)
        self.assertEqual(menu.count("if (timer || deaths) draw_corner(c, timer, deaths);"), 2)
        # (top centre: in the top left corner the block covered the game's own hearts, seen in the game on 2026-11-14)
        start = menu.index("void draw_corner(ui::Ctx& c, bool timer, bool deaths) {")
        corner = menu[start:menu.index("\n}\n", start)]
        self.assertIn("c.w * 0.5f + tw * 0.5f", corner)
        self.assertNotIn("c.safe + tw", corner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--cxx", default="g++")
    args, rest = parser.parse_known_args()
    CC, CXX = args.cc, args.cxx
    unittest.main(argv=[sys.argv[0]] + rest)
