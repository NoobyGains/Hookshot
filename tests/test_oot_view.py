"""View distance, Grass and Shadow distance (host/oot_view.c, nx2/oot_view.py): the hook's install gate, the rows' wiring,
and the C code itself run over a made-up guest memory with the game's object chains. Checked: nothing is written while
every row is on Original; each step multiplies the game's own value; Original gives it back exactly; a value the game
writes meanwhile is taken again (nothing compounds); a chain with an unexpected vtable is left alone.

python -I -B tests/test_oot_view.py [--cc gcc]
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUN_ALL_ARGS = ["--cc", "gcc"]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import game_profile
import oot_view

CC = "gcc"

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { uint64_t x[32]; } Ctx;
enum { HOS_OPT_VIEW_DISTANCE = 57, HOS_OPT_GRASS, HOS_OPT_SHADOW_DISTANCE };
static int view = 1, grass_row = 2, shadow_row = 1, stores;
int rx_option(int id, int otherwise) {
    return id == HOS_OPT_VIEW_DISTANCE ? view : id == HOS_OPT_GRASS ? grass_row : id == HOS_OPT_SHADOW_DISTANCE ? shadow_row
                                                                                                           : otherwise;
}
/* the guest's memory: 32-bit words by address */
static uint64_t at_[512];
static uint32_t word_[512];
static int words;
static int find(uint64_t a) { for (int i = 0; i < words; i++) if (at_[i] == a) return i; return -1; }
static void put32(uint64_t a, uint32_t v) { int i = find(a); if (i < 0) i = words++, at_[i] = a; word_[i] = v; }
static void put64(uint64_t a, uint64_t v) { put32(a, (uint32_t)v); put32(a + 4, (uint32_t)(v >> 32)); }
static uint64_t recomp_load32(Ctx *c, uint64_t a) { (void)c; int i = find(a); return i < 0 ? 0 : word_[i]; }
static uint64_t recomp_load64(Ctx *c, uint64_t a) { return recomp_load32(c, a) | recomp_load32(c, a + 4) << 32; }
static void recomp_store32(Ctx *c, uint64_t a, uint64_t v) { (void)c; stores++; put32(a, (uint32_t)v); }
static void putf(uint64_t a, float f) { uint32_t u; memcpy(&u, &f, 4); put32(a, u); }
static float getf(uint64_t a) { uint32_t u = (uint32_t)recomp_load32(0, a); float f; memcpy(&f, &u, 4); return f; }
/* SOURCE */
#define M(off) (0x80020000ULL + (off))
static uint64_t next_obj = 0x90000000ULL;
static uint64_t link(uint64_t slot, uint64_t vtable) {   /* a new object of that kind, its pointer at slot */
    const uint64_t o = next_obj;
    next_obj += 0x4000;
    put64(o, vtable);
    put64(slot, o);
    return o;
}
static int failures;
#define CHECK(x) do { if (!(x)) { failures++; printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
#define NEAR(a, b) CHECK((a) > (b) - 1e-4f && (a) < (b) + 1e-4f)
int main(void) {
    Ctx c = {{0}};
    uint64_t o = link(M(0x4e22540), M(0x4b24800));
    o = link(o + 0xf0, M(0x4b24a70));
    o = link(o + 0x2a90, M(0x4bf9010));
    const uint64_t d = link(o + 0x150, M(0x4b23228));
    uint64_t p[2];
    for (int b = 0; b < 2; b++) {
        p[b] = link(d + 0x40 + 8 * b, M(0x4b235d0));
        for (int i = 0; i < 8; i++) putf(p[b] + 0x38 + 4 * i, 10.0f * (i + 1) + b);
    }
    putf(d + 0x68, 0.8f);   /* the grass */
    const uint64_t s = link(M(0x4e3e258), M(0x4b895b0)), r = link(s + 0x1e8, M(0x4b8bc00));
    const uint64_t h = link(r + 0xd50, M(0x4bf9010)), lod = link(h + 0x150, M(0x4b87a88));
    putf(lod + 0x48, 1.0f), putf(lod + 0x4c, 0.8f), putf(lod + 0x50, 1.0f);
    const uint64_t ch = link(r + 0xba8, M(0x4b8a3e8)), h2 = link(ch + 0xc18, M(0x4bf9010)), cp = link(h2 + 0x150, M(0x4b86828));
    putf(cp + 0x90, 30.0f), putf(cp + 0x94, 25.0f);
    const uint64_t sh = link(r + 0xb30, M(0x4b8a0a8));
    putf(sh + 0xb4, 160.0f);

    for (int f = 0; f < 3; f++) hos_oot_view(&c);   /* every row on Original: nothing touched */
    CHECK(stores == 0);

    view = 2;   /* Far: the foliage and the models' detail at 1.5 times the game's, the rest as it was */
    hos_oot_view(&c);
    NEAR(getf(p[0] + 0x38), 15.0f); NEAR(getf(p[1] + 0x38 + 28), 121.5f);
    NEAR(getf(lod + 0x48), 1.5f); NEAR(getf(lod + 0x4c), 1.2f); NEAR(getf(d + 0x68), 0.8f); NEAR(getf(sh + 0xb4), 160.0f);
    hos_oot_view(&c);   /* a second frame does not compound */
    NEAR(getf(p[0] + 0x38), 15.0f); NEAR(getf(lod + 0x48), 1.5f);
    putf(p[0] + 0x3c, 40.0f);   /* the game writes a new value: taken again */
    hos_oot_view(&c);
    NEAR(getf(p[0] + 0x3c), 60.0f);

    view = 0;   /* Short: the foliage closer, the models never coarser than the game's */
    hos_oot_view(&c);
    NEAR(getf(p[0] + 0x38), 7.5f); NEAR(getf(lod + 0x48), 1.0f); NEAR(getf(lod + 0x4c), 0.8f);

    view = 1, grass_row = 0, shadow_row = 3;
    hos_oot_view(&c);
    NEAR(getf(p[0] + 0x38), 10.0f); NEAR(getf(p[0] + 0x3c), 40.0f); NEAR(getf(d + 0x68), 0.0f);
    NEAR(getf(cp + 0x90), 90.0f); NEAR(getf(cp + 0x94), 75.0f); NEAR(getf(sh + 0xb4), 480.0f);

    grass_row = 2, shadow_row = 1;   /* Original again: the game's own values back, exactly */
    hos_oot_view(&c);
    NEAR(getf(d + 0x68), 0.8f); NEAR(getf(cp + 0x90), 30.0f); NEAR(getf(cp + 0x94), 25.0f); NEAR(getf(sh + 0xb4), 160.0f);
    for (int b = 0; b < 2; b++)
        for (int i = 0; i < 8; i++) NEAR(getf(p[b] + 0x38 + 4 * i), b == 0 && i == 1 ? 40.0f : 10.0f * (i + 1) + b);
    NEAR(getf(lod + 0x48), 1.0f); NEAR(getf(lod + 0x4c), 0.8f); NEAR(getf(lod + 0x50), 1.0f);

    put64(recomp_load64(0, M(0x4e22540)), 0x1234);   /* the foliage's root now an object of another kind */
    view = 4;
    stores = 0;
    hos_oot_view(&c);
    NEAR(getf(p[0] + 0x38), 10.0f);   /* its chain left alone */
    NEAR(getf(lod + 0x48), 2.5f);     /* the scene's still followed */
    printf("%s\n", failures ? "FAILED" : "all view distance checks passed");
    return failures != 0;
}
'''


def host_source():
    text = (ROOT / "host/oot_view.c").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("#include"))


class Image:
    def __init__(self, word):
        self._word = word

    def word(self, pc):
        return self._word if pc == oot_view.SITE else 0


class Lifter:
    def __init__(self, after=None):
        self.after = dict(after or {})


class OotViewTests(unittest.TestCase):
    def test_install_gate(self):
        lifter = Lifter()
        self.assertEqual(oot_view.install(lifter, Image(oot_view.WORD), oot_view.BUILD_ID), 1)
        self.assertEqual(lifter.after[oot_view.SITE], oot_view.HOOK)
        lifter = Lifter({oot_view.SITE: "prior();"})
        oot_view.install(lifter, Image(oot_view.WORD), oot_view.BUILD_ID)
        self.assertEqual(lifter.after[oot_view.SITE], "prior();\n" + oot_view.HOOK)
        for image, build in ((Image(0), oot_view.BUILD_ID), (Image(oot_view.WORD), "another build")):
            lifter = Lifter()
            self.assertEqual(oot_view.install(lifter, image, build), 0)
            self.assertEqual(lifter.after, {})
        self.assertIn("hos_oot_view(c);", oot_view.HOOK)
        self.assertIn("oot_view", game_profile.GAMES["oot"].patch_modules)

    def test_rows_wired(self):
        api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        options = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
        self.assertIn("enum { HOS_OPT_VIEW_DISTANCE = 57, HOS_OPT_GRASS, HOS_OPT_SHADOW_DISTANCE };", api)
        for field, default, row, hi in (("view_distance", 1, "View distance", 4), ("grass", 2, "Grass", 4),
                                         ("shadow_distance", 1, "Shadow distance", 3)):
            self.assertIn("int %s = %d;" % (field, default), options)
            self.assertRegex(menu, r'\{TAB_GRAPHICS, "%s", &opts\.%s, 0, %d, 1, tx_%s,' % (row, field, hi, field))
            self.assertRegex(replay, r"if \(id == HOS_OPT_%s\) return opts\.%s;" % (field.upper(), field))
        # (the C's own step tables and the menu's names have as many entries)
        source = (ROOT / "host/oot_view.c").read_text(encoding="utf-8")
        for table, names in (("VIEW", "tx_view_distance"), ("GRASS", "tx_grass"), ("SHADOW", "tx_shadow_distance")):
            factors = re.search(r"static const float %s\[\] = \{([^}]*)\}" % table, source).group(1).count("f")
            texts = re.search(r'const char\* %s\(int v\) \{\n    static const char\* t\[\] = \{([^}]*)\}' % names, menu)
            self.assertEqual(factors, texts.group(1).count('"') // 2, table)

    def test_c_behaviour(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-oot-view-") as tmp:
            src, exe = Path(tmp) / "view.c", Path(tmp) / "view.exe"
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
