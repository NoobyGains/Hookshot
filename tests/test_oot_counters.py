"""Classic counters (host/oot_counters.c, nx2/oot_counters.py, the Gameplay row and draw_rupees): the hooks' install gate,
the row's wiring from the menu to the host and the wallet back, and the C code itself over a made-up guest memory. Checked:
the pick-up indicator's root is hidden through the game's setter while the row is on and given its alpha back when it goes
off; the setter's later writes to a hidden root become 0, others are left alone; a reused object is forgotten; the wallet
goes to the renderer every 10 frames with a live player, and -1 once without one or with the row off.

python -I -B tests/test_oot_counters.py [--cc gcc]
"""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUN_ALL_ARGS = ["--cc", "gcc"]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import game_profile
import oot_counters

CC = "gcc"

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
typedef struct { uint64_t x[32]; uint64_t vreg[32][2]; } Ctx;
typedef void (*A64Fn)(Ctx *);
typedef int SRWLOCK;
#define SRWLOCK_INIT 0
typedef long LONG;
static void AcquireSRWLockExclusive(SRWLOCK *l) { (void)l; }
static void ReleaseSRWLockExclusive(SRWLOCK *l) { (void)l; }
static LONG InterlockedIncrement(volatile LONG *p) { return ++*p; }
static void hos_log(const char *f, ...) { (void)f; }
enum { HOS_OPT_CLASSIC_COUNTERS = 61 };
#define OOT_HUD_RUPEES_ID 4084
static int row, player = 1, sent_n, last_sent = -99, setter_calls, wallet = 123;
int rx_option(int id, int otherwise) { return id == HOS_OPT_CLASSIC_COUNTERS ? row : otherwise; }
void rx_option_set(int id, int value) { if (id == OOT_HUD_RUPEES_ID) sent_n++, last_sent = value; }
int hos_oot_flight_shortcut_ready(void) { return player; }
static uint64_t at_[256]; static uint32_t word_[256]; static int words;
static int find(uint64_t a) { for (int i = 0; i < words; i++) if (at_[i] == a) return i; return -1; }
static void put32(uint64_t a, uint32_t v) { int i = find(a); if (i < 0) i = words++, at_[i] = a; word_[i] = v; }
static void put64(uint64_t a, uint64_t v) { put32(a, (uint32_t)v); put32(a + 4, (uint32_t)(v >> 32)); }
static uint64_t recomp_load32(Ctx *c, uint64_t a) { (void)c; int i = find(a); return i < 0 ? 0 : word_[i]; }
static uint64_t recomp_load64(Ctx *c, uint64_t a) { return recomp_load32(c, a) | recomp_load32(c, a + 4) << 32; }
/* the game's setter: the root's alpha (+0x74) from s0, as f_802f8ac0 stores it; the wallet reader: the count in x0 */
static void setter(Ctx *c) { setter_calls++; uint32_t a; memcpy(&a, &c->vreg[0][0], 4); put32(c->x[0] + 0x74, a); c->x[5] = 77; }
static void wallet_read(Ctx *c) { c->x[0] = (uint64_t)(uint32_t)wallet; c->x[7] = 99; }
static A64Fn a64_lookup(uint64_t a) { return a == 0x802f8ac0ull ? setter : a == 0x80a87c30ull ? wallet_read : 0; }
/* SOURCE */
static int failures;
#define CHECK(x) do { if (!(x)) { failures++; printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
static const uint32_t ONE = 0x3f800000u;   /* 1.0f */
int main(void) {
    Ctx c; memset(&c, 0, sizeof c);
    const uint64_t owner = 0x90000000ull, layout = 0x90001000ull, inst = 0x90002000ull, root = 0x90003000ull;
    put64(owner, 0x84c0ac28ull); put64(owner + 0x28, layout); put64(layout + 0x80, inst); put64(inst + 0x100, root);
    put32(root + 0x74, ONE);
    c.x[0] = owner; c.x[5] = 5;
    hos_oot_counters_pickup(&c);                 /* row off: nothing */
    CHECK(setter_calls == 0 && recomp_load32(&c, root + 0x74) == ONE);
    row = 1;
    hos_oot_counters_pickup(&c);                 /* on: hidden through the game's setter, the game's registers kept */
    CHECK(setter_calls == 1 && recomp_load32(&c, root + 0x74) == 0 && c.x[5] == 5 && c.x[0] == owner);
    c.x[0] = root; memcpy(&c.vreg[0][0], &ONE, 4);
    hos_oot_counters_alpha(&c);                  /* the fade's own write to the hidden root: 0 */
    uint32_t s0; memcpy(&s0, &c.vreg[0][0], 4); CHECK(s0 == 0);
    c.x[0] = 0x95000000ull; memcpy(&c.vreg[0][0], &ONE, 4);
    hos_oot_counters_alpha(&c);                  /* another layout's: left alone */
    memcpy(&s0, &c.vreg[0][0], 4); CHECK(s0 == ONE);
    row = 0; c.x[0] = owner;
    hos_oot_counters_pickup(&c);                 /* off again: its alpha back */
    CHECK(setter_calls == 2 && recomp_load32(&c, root + 0x74) == ONE);
    row = 1; hos_oot_counters_pickup(&c); CHECK(recomp_load32(&c, root + 0x74) == 0);
    put64(inst + 0x100, 0x90004000ull);          /* the object reused for another layout: forgotten, the old root not written */
    c.x[0] = root; memcpy(&c.vreg[0][0], &ONE, 4);
    hos_oot_counters_alpha(&c);
    memcpy(&s0, &c.vreg[0][0], 4); CHECK(s0 == ONE);

    put64(0x84c9e0d0ull, 0x91000000ull); put64(0x91000000ull, 0x92000000ull);   /* the game data manager */
    row = 1; player = 1; sent_n = 0; c.x[7] = 7;
    for (int f = 0; f < 25; f++) hos_oot_counters_frame(&c);
    CHECK(last_sent == 123 && sent_n == 1 && c.x[7] == 7);   /* (asked at frames 0, 10, 20; sent once: it did not change) */
    wallet = 456; for (int f = 0; f < 10; f++) hos_oot_counters_frame(&c);
    CHECK(last_sent == 456 && sent_n == 2);
    wallet = 100000; for (int f = 0; f < 10; f++) hos_oot_counters_frame(&c);
    CHECK(last_sent == -1);                                   /* (not a wallet: nothing shown) */
    wallet = 5; player = 0; hos_oot_counters_frame(&c); CHECK(last_sent == -1);
    player = 1; hos_oot_counters_frame(&c); CHECK(last_sent == 5);
    row = 0; hos_oot_counters_frame(&c); CHECK(last_sent == -1);
    const int n = sent_n; hos_oot_counters_frame(&c); CHECK(sent_n == n);   /* (said once) */
    printf("%s\n", failures ? "FAILED" : "all classic counters checks passed");
    return failures != 0;
}
'''


def host_source():
    text = (ROOT / "host/oot_counters.c").read_text(encoding="utf-8")
    keep = []
    for line in text.splitlines():
        if line.startswith("#include") or line.startswith("#ifdef _WIN32") or line.startswith("#endif"):
            continue
        keep.append(line)
    return "\n".join(keep)


class Image:
    def __init__(self, words):
        self.words = words

    def word(self, pc):
        return self.words.get(pc, 0xdeadbeef)


class Lifter:
    def __init__(self, after=None):
        self.after = dict(after or {})
        self.entries = set()


GOOD = {pc: word for pc, word, _ in oot_counters.HOOKS}
GOOD.update(dict(oot_counters.CHECKS))


class OotCountersTests(unittest.TestCase):
    def test_install_gate(self):
        lifter = Lifter({0x831f3200: "prior();"})
        self.assertEqual(oot_counters.install(lifter, Image(GOOD), oot_counters.BUILD_ID), 1)
        self.assertEqual(set(lifter.after), {pc for pc, _, _ in oot_counters.HOOKS})
        self.assertTrue(lifter.after[0x831f3200].startswith("prior();\n"))
        self.assertIn("hos_oot_counters_frame(c);", lifter.after[0x831f3200])
        self.assertEqual(lifter.entries, set(oot_counters.CALLED))
        for pc in GOOD:
            words = dict(GOOD)
            words[pc] ^= 1
            lifter = Lifter()
            self.assertEqual(oot_counters.install(lifter, Image(words), oot_counters.BUILD_ID), 0, hex(pc))
            self.assertEqual((lifter.after, lifter.entries), ({}, set()))
        self.assertEqual(oot_counters.install(Lifter(), Image(GOOD), "another build"), 0)
        self.assertIn("oot_counters", game_profile.GAMES["oot"].patch_modules)

    def test_wiring(self):
        api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
        items = (ROOT / "gpu/vk/oot_cheat_items.h").read_text(encoding="utf-8")
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
        options = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
        self.assertIn("enum { HOS_OPT_CLASSIC_COUNTERS = 61 };", api)
        self.assertIn("#define OOT_HUD_RUPEES_ID 4084", items)
        self.assertIn("int classic_counters = 0;", options)
        self.assertIn('{TAB_GAMEPLAY, "Classic counters", &opts.classic_counters, 0, 1, 1, tx_onoff,', menu)
        self.assertIn("if (id == HOS_OPT_CLASSIC_COUNTERS) return opts.classic_counters;", replay)
        self.assertIn("if (id == OOT_HUD_RUPEES_ID) {   // (Classic counters: draw_rupees reads it)\n"
                      "        hud_rupees.store(value, std::memory_order_relaxed);", menu)
        # (both overlays draw it while the menu is closed, and a frame with only the rupees still records one)
        self.assertEqual(menu.count("if (rupees >= 0) draw_rupees(c, rupees);   // (Classic counters)"), 2)
        self.assertIn("if (!start && !fps && !open && rupees < 0 && !timer && !deaths) {", menu)
        self.assertIn("if (!open && !fps && rupees < 0 && !timer && !deaths) return;", menu)

    def test_c_behaviour(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-oot-counters-") as tmp:
            src, exe = Path(tmp) / "counters.c", Path(tmp) / "counters.exe"
            src.write_text(HARNESS.replace("/* SOURCE */", host_source()), encoding="utf-8")
            built = subprocess.run([CC, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", str(src),
                                    "-o", str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args, rest = parser.parse_known_args()
    CC = args.cc
    unittest.main(argv=[sys.argv[0]] + rest)
