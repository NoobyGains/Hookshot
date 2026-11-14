"""Hero mode (the Gameplay row): no recovery hearts from the drop lotteries (host/oot_hero.c, nx2/oot_patches.py patch_drops),
and the row's wiring. Its double damage is checked with Damage taken's arithmetic in tests/test_oot_damage.py.

The game's drop lotteries (f_82f145e0, and the simple f_82f162f0) fill a list (their x1) with the actors they drew; the patch
follows each of their five calls with hos_oot_drops, which takes every recovery heart (Obj_Heart and its two variants) out of
the list while the row is on. Here the production patch is applied to authored callers of the lifted shape (the five calls, by
their return addresses, f_807a4460's two behind its branch on x4), which are compiled with the real host/oot_hero.c and
stand-in lotteries over a stand-in guest memory: each lottery fills the list from its free slots as the game's does, then
clobbers x1 as any call may. With the row on the hearts are gone and the rest keep their order, the slots taken out go back to
the free ones, a list of hearts only comes back empty, and fairies, rupees, Pieces of Heart and Heart Containers stay. With the
row off, and through the unpatched callers with it on, every heart stays (the negative controls). A list that is not one (a
count over its capacity, no slots) is left alone. No game files or lifted function body are used.

python -I -B tests/test_hero_mode.py [--cc gcc]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import oot_patches  # noqa: E402

# (the five callers' calls, of the lifted shape: f_807a4460 takes the simple lottery when its x4's bit 0 is set)
CALLERS = ('#include "a64.h"\n'
           'void f_807a4460(Ctx *__restrict A64_NOESC c) {\n'
           'if (!((c->x[4] >> 0) & 1)) { goto L_807a4564; }\n'
           'c->x[30] = 0x807a4560ULL; f_82f162f0(c);\n'
           'goto L_807a4568;\n'
           'L_807a4564:;\n'
           'c->x[30] = 0x807a4568ULL; f_82f145e0(c);\n'
           'L_807a4568:;\n'
           '}\n'
           'void f_812178c0(Ctx *__restrict A64_NOESC c) {\n'
           'c->x[30] = 0x81217a64ULL; f_82f145e0(c);\n'
           '}\n'
           'void f_82e0b560(Ctx *__restrict A64_NOESC c) {\n'
           'c->x[30] = 0x82e0b5c4ULL; f_82f145e0(c);\n'
           '}\n'
           'void f_82e0b6a0(Ctx *__restrict A64_NOESC c) {\n'
           'c->x[30] = 0x82e0b6f8ULL; f_82f145e0(c);\n'
           '}\n')

# (a guest memory of 64 KB from 0x10000: the guest's loads and stores, and the game's lists and names in it)
CONTEXT = r"""#pragma once
#include <stdint.h>
#include <string.h>
#define A64_NOESC
typedef struct { uint64_t x[32]; } Ctx;
enum { BASE = 0x10000, SIZE = 0x10000 };
static uint8_t mem[SIZE];
static uint8_t *at(uint64_t a) { if (a < BASE || a + 8 > BASE + SIZE) { extern void bad(uint64_t); bad(a); } return mem + (a - BASE); }
static inline uint64_t recomp_load8(Ctx *c, uint64_t a) { (void)c; return *at(a); }
static inline uint64_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; memcpy(&v, at(a), 4); return v; }
static inline uint64_t recomp_load64(Ctx *c, uint64_t a) { uint64_t v; (void)c; memcpy(&v, at(a), 8); return v; }
static inline void recomp_store32(Ctx *c, uint64_t a, uint32_t v) { (void)c; memcpy(at(a), &v, 4); }
static inline void recomp_store64(Ctx *c, uint64_t a, uint64_t v) { (void)c; memcpy(at(a), &v, 8); }
"""

FIXTURE = r'''#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "a64.h"
enum { HOS_OPT_HERO_MODE = 62 };
static int row, failures, asked;
void bad(uint64_t a) { printf("FAIL: a guest access outside the memory: %#llx\n", (unsigned long long)a); exit(1); }
int rx_option(int id, int otherwise) { asked++; return id == HOS_OPT_HERO_MODE ? row : otherwise; }
#define CHECK(test, what) do { if (!(test)) { printf("FAIL: %s\n", what); failures++; } } while (0)
@HOST@
/* (the list at LIST: s32 count, s32 capacity 16, the slots' pointers at +8 (SLOTS), the free slots' chain at +16; the 16
   drops of 0x20 bytes at DROPS; the names at NAMES, 0x200 bytes each) */
enum { LIST = 0x10000, SLOTS = 0x10100, DROPS = 0x10200, NAMES = 0x10800 };
static const char *draw[16];
static int ndraw, lotteries, simple;
static void lottery(Ctx *c) {   /* (the game's: the list emptied, then each drawn from the free slots) */
    const uint64_t list = c->x[1];
    lotteries++;
    recomp_store32(c, list, 0);
    for (int i = 0; i < ndraw; i++) {
        const uint64_t drop = recomp_load64(c, list + 16);
        recomp_store64(c, list + 16, recomp_load64(c, drop));
        strcpy((char *)at(NAMES + 0x200 * (uint64_t)i), draw[i]);
        recomp_store64(c, drop, NAMES + 0x200 * (uint64_t)i);
        recomp_store64(c, drop + 8, 0x1234u + (uint64_t)i);
        recomp_store64(c, recomp_load64(c, list + 8) + 8 * (uint64_t)i, drop);
        recomp_store32(c, list, (uint32_t)(i + 1));
    }
    c->x[1] = 0xdeadbeefULL;   /* (a call keeps no x1) */
}
void f_82f145e0(Ctx *c) { lottery(c); }
void f_82f162f0(Ctx *c) { lottery(c); simple++; }
@CALLERS@
static void fresh(Ctx *c) {   /* (an empty list, its 16 slots all free) */
    memset(mem, 0, sizeof mem);
    recomp_store32(c, LIST + 4, 16);
    recomp_store64(c, LIST + 8, SLOTS);
    for (int i = 0; i < 16; i++)
        recomp_store64(c, DROPS + 0x20 * (uint64_t)i, i < 15 ? DROPS + 0x20 * (uint64_t)(i + 1) : 0);
    recomp_store64(c, LIST + 16, DROPS);
}
/* what the caller sees after its call: the names, joined by commas */
static const char *after(int which, const char *const *names, int n) {
    static char out[1024];
    Ctx c = {{0}};
    fresh(&c);
    ndraw = n;
    for (int i = 0; i < n; i++) draw[i] = names[i];
    c.x[1] = LIST;
    c.x[4] = which == 1;
    switch (which) {
    case 0: case 1: f_807a4460(&c); break;
    case 2: f_812178c0(&c); break;
    case 3: f_82e0b560(&c); break;
    default: f_82e0b6a0(&c); break;
    }
    const int32_t count = (int32_t)recomp_load32(&c, LIST);
    out[0] = 0;
    for (int32_t i = 0; i < count; i++) {
        if (i) strcat(out, ",");
        strcat(out, (const char *)at(recomp_load64(&c, recomp_load64(&c, SLOTS + 8 * (uint64_t)i))));
    }
    int free_slots = 0;
    for (uint64_t s = recomp_load64(&c, LIST + 16); s && free_slots < 32; s = recomp_load64(&c, s)) free_slots++;
    CHECK(free_slots + count == 16, "every slot taken out goes back to the free ones");
    return out;
}

int main(void) {
    static const char *const mixed[] = {"Obj_Heart", "Obj_Rupee_Green", "Obj_Heart", "Obj_Fairy", "Obj_Heart_Piece",
                                        "Work/Actor/Obj_Heart.engine__actor__ActorParam.gyml", "Obj_Heart_InWater",
                                        "Obj_Heart_Container", "Obj_Heart_Shootable", "Obj_Hearts", "Obj_MagicJar_Small"};
    static const char *const kept = "Obj_Rupee_Green,Obj_Fairy,Obj_Heart_Piece,Obj_Heart_Container,Obj_Hearts,Obj_MagicJar_Small";
    static const char *const all = "Obj_Heart,Obj_Rupee_Green,Obj_Heart,Obj_Fairy,Obj_Heart_Piece,"
                                   "Work/Actor/Obj_Heart.engine__actor__ActorParam.gyml,Obj_Heart_InWater,Obj_Heart_Container,"
                                   "Obj_Heart_Shootable,Obj_Hearts,Obj_MagicJar_Small";
    static const char *const hearts[] = {"Obj_Heart", "Obj_Heart", "Obj_Heart_InWater"};
    static const char *const none[] = {"Obj_Rupee_Blue", "Obj_Bomb"};
    for (int which = 0; which < 5; which++) {
        row = 1;
        CHECK(!strcmp(after(which, mixed, 11), kept), "Hero mode: the recovery hearts gone, the rest in their order");
        CHECK(!strcmp(after(which, hearts, 3), ""), "Hero mode: hearts only, nothing dropped");
        CHECK(!strcmp(after(which, none, 2), "Obj_Rupee_Blue,Obj_Bomb"), "Hero mode: no heart, the list as it was");
        CHECK(!strcmp(after(which, none, 0), ""), "Hero mode: nothing drawn, nothing dropped");
        row = 0;
        CHECK(!strcmp(after(which, mixed, 11), all), "the row off: every drop as the game drew it");
        row = 2;
        CHECK(!strcmp(after(which, hearts, 3), "Obj_Heart,Obj_Heart,Obj_Heart_InWater"), "an unknown value: off");
    }
    CHECK(lotteries == 5 * 6 && simple == 6, "each caller draws through its own lottery, once");
    /* (a list that is not one, left as it is: a count over its capacity, or no slots) */
    row = 1;
    Ctx c = {{0}};
    fresh(&c);
    ndraw = 3;
    draw[0] = draw[1] = draw[2] = "Obj_Heart";
    c.x[1] = LIST;
    lottery(&c);
    recomp_store32(&c, LIST + 4, 2);
    hos_oot_drops(&c, LIST);
    CHECK(recomp_load32(&c, LIST) == 3, "a count over the capacity: left alone");
    recomp_store32(&c, LIST + 4, 16);
    recomp_store64(&c, LIST + 8, 0);
    hos_oot_drops(&c, LIST);
    CHECK(recomp_load32(&c, LIST) == 3, "no slots: left alone");
    hos_oot_drops(&c, 0);
    /* (a name longer than any actor's path is not a heart, though it ends in one: read no further than the bound; an empty
       name, the game's own nothing, stays; an actor path counts by its name; Obj_Heart_ is no heart) */
    char longname[211], expect[300];
    memset(longname, 'a', 200);
    memcpy(longname + 200, "/Obj_Heart", 11);
    const char *const odd[] = {longname, "", "Actor/Obj_Heart.engine__actor__ActorParam", "Obj_Heart_"};
    snprintf(expect, sizeof expect, "%s,,Obj_Heart_", longname);
    CHECK(!strcmp(after(0, odd, 4), expect), "a long name, an empty one and Obj_Heart_ stay; an actor path's heart goes");
    if (!failures) puts("PASS: Hero mode's drops");
    return failures != 0;
}
'''


def build(cc, directory, callers, name):
    host = (ROOT / "host" / "oot_hero.c").read_text(encoding="utf-8")
    host = "\n".join(line for line in host.splitlines() if not line.startswith("#include"))
    source, binary = directory / (name + ".c"), directory / (name + ".exe")
    body = callers.replace('#include "a64.h"\n', "")
    source.write_text(FIXTURE.replace("@HOST@", host).replace("@CALLERS@", body), encoding="utf-8")
    subprocess.run([cc, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-label", "-Wno-unused-function",
                    "-I", str(directory), str(source), "-o", str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)


def wiring():
    api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
    options = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    damage = (ROOT / "host/oot_damage.c").read_text(encoding="utf-8")
    assert "enum { HOS_OPT_HERO_MODE = 62 };" in api
    assert "int hero_mode = 0;" in options
    row = re.search(r'\{TAB_GAMEPLAY, "Hero mode", &opts\.hero_mode, 0, 1, 1, tx_onoff,\s*"([^}]*)\}', menu)
    assert row, "the Gameplay tab's Hero mode row, Off or On"
    assert row.group(1).rstrip().endswith("nullptr, false, true"), "live (no restart) and left alone by the Quality preset"
    assert "if (id == HOS_OPT_HERO_MODE) return opts.hero_mode;" in replay
    assert "rx_option(HOS_OPT_HERO_MODE, 0) == 1" in damage   # (the double damage: tests/test_oot_damage.py)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    wiring()
    made, found = oot_patches.patch_drops(CALLERS)
    assert found == len(oot_patches.DROP_SITES) == 5, (found, made)
    assert made.count("hos_oot_drops(c, _hd);") == 5 and made.count(oot_patches.DROP_DECL) == 1, made
    assert oot_patches.patch_drops(made) == (made, 5)   # (made before: counted, left as it is)
    other = CALLERS.replace("0x807a4568ULL", "0x907a4568ULL").replace("0x82e0b5c4ULL", "0x92e0b5c4ULL")   # (another build)
    assert oot_patches.patch_drops(other)[1] == 3
    twice = CALLERS.replace("c->x[30] = 0x81217a64ULL; f_82f145e0(c);\n", "c->x[30] = 0x81217a64ULL; f_82f145e0(c);\n" * 2)
    assert "0x81217a64ULL; f_82f145e0(c); hos_oot_drops" not in oot_patches.patch_drops(twice)[0]   # (not once: left)
    out, counts, lines = oot_patches.patch_file(CALLERS, "code_000.c", protect_hearts=True)
    assert counts["drop sites"] == 5 and out == made and any("Hero mode" in line for line in lines), (counts, lines)
    out, counts, _ = oot_patches.patch_file(CALLERS, "code_000.c", protect_hearts=False)   # (another build's lift: no sites)
    assert counts["drop sites"] == 0 and out == CALLERS
    with tempfile.TemporaryDirectory(prefix="hero-mode-") as directory:
        directory = Path(directory)
        (directory / "a64.h").write_text(CONTEXT, encoding="utf-8")
        run = build(args.cc, directory, made, "patched")
        print(run.stdout, end="")
        assert run.returncode == 0, run.stdout + run.stderr
        # (the game's callers: Hero mode on, and the hearts stay; the same checks must fail)
        run = build(args.cc, directory, CALLERS.replace("hos_oot_drops", ""), "game")
        assert run.returncode != 0 and "FAIL: Hero mode: the recovery hearts gone" in run.stdout, run.stdout
    print("PASS: Hero mode's patch at the drop lotteries' five calls, the row's wiring, and the game's callers fail the same checks")


if __name__ == "__main__":
    main()
