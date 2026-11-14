"""Navi callouts (the Gameplay row): with it Off, no area hint is registered with Navi (host/oot_navi.c, nx2/oot_patches.py
patch_navi_hints), so she has no "Hey! Listen!" for one and none to give when asked; and the row's wiring.

f_80ccf0f0 registers an area hint (x0 the registry, x1 the NaviAreaHintEventActor, x2 its AreaHintEventName, x3 its
AreaHintPriority) and returns 1 when it did; its one caller is the AI node ExecuteNaviAreaHintRegist. The patch makes it return
0 first while the row is Off, as the game's own does with its registry full. Here the production patch is applied to an
authored function of the lifted shape (its head, its prologue's stack frame, a registration into a stand-in registry), which
is compiled with the real host/oot_navi.c: On (and any value but 0) registers as the game does; Off registers nothing, returns 0
and leaves the stack and the callee-saved registers as they were. The game's function registers with the row Off (the
negative control). No game files or lifted function body are used.

python -I -B tests/test_navi_callouts.py [--cc gcc]
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

# (the lifted shape: the head, the prologue's frame and saves, then the registration: count +1, the actor's id kept)
LIFTED = ('#include "a64.h"\n'
          'void f_80ccf0f0(Ctx *__restrict A64_NOESC c) {\n'
          '    /* nop/hint */\n'
          '    { uint64_t _b=c->x[31]; int64_t _o=-96; c->x[31]=_b+_o; }\n'
          '    c->x[19] = c->x[0];\n'
          '    c->x[22] = c->x[1];\n'
          '    registry[0]++; registry[1] = c->x[1]; registry[2] = c->x[3];\n'
          '    c->x[0] = 1;\n'
          '    c->x[19] = 0x1919; c->x[22] = 0x2222;   /* (restored by the epilogue) */\n'
          '    { uint64_t _b=c->x[31]; int64_t _o=96; c->x[31]=_b+_o; }\n'
          'return;\n'
          '}\n')
CONTEXT = """#pragma once
#include <stdint.h>
#define A64_NOESC
typedef struct { uint64_t x[32]; } Ctx;
"""
FIXTURE = r'''#include <stdio.h>
#include "a64.h"
enum { HOS_OPT_NAVI_CALLOUTS = 64 };
static int row = 1, failures;
static uint64_t registry[3];
int rx_option(int id, int otherwise) { return id == HOS_OPT_NAVI_CALLOUTS ? row : otherwise; }
#define CHECK(test, what) do { if (!(test)) { printf("FAIL: %s\n", what); failures++; } } while (0)
@HOST@
@LIFTED@
/* one registration as ExecuteNaviAreaHintRegist makes it: what came back in x0 */
static uint64_t regist(Ctx *c) {
    c->x[0] = 0x84000000ULL; c->x[1] = 0x10000000ULL; c->x[2] = 0x20000000ULL; c->x[3] = 1; c->x[31] = 0x7000;
    c->x[19] = 19; c->x[22] = 22;
    f_80ccf0f0(c);
    return c->x[0];
}

int main(void) {
    Ctx c = {{0}};
    row = 1;
    CHECK(regist(&c) == 1 && registry[0] == 1 && registry[1] == 0x10000000ULL, "On: the hint is registered, as the game does");
    row = 2;
    CHECK(regist(&c) == 1 && registry[0] == 2, "a value that is not 0: On");
    row = 0;
    CHECK(regist(&c) == 0 && registry[0] == 2, "Off: no hint registered, 0 back as with the registry full");
    CHECK(c.x[31] == 0x7000 && c.x[19] == 19 && c.x[22] == 22, "Off: the stack and the callee-saved registers as they were");
    row = 1;
    CHECK(regist(&c) == 1 && registry[0] == 3, "On again: registered");
    if (!failures) puts("PASS: Navi callouts' area hints");
    return failures != 0;
}
'''


def build(cc, directory, lifted, name):
    host = (ROOT / "host" / "oot_navi.c").read_text(encoding="utf-8")
    host = "\n".join(line for line in host.splitlines() if not line.startswith("#include"))
    source, binary = directory / (name + ".c"), directory / (name + ".exe")
    source.write_text(FIXTURE.replace("@HOST@", host).replace("@LIFTED@", lifted.replace('#include "a64.h"\n', "")),
                      encoding="utf-8")
    subprocess.run([cc, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(directory), str(source), "-o",
                    str(binary)], check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)


def wiring():
    api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
    options = (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8")
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    assert "enum { HOS_OPT_NAVI_CALLOUTS = 64 };" in api
    assert "int navi_callouts = 1;" in options   # (On, the game's, by default)
    row = re.search(r'\{TAB_GAMEPLAY, "Navi callouts", &opts\.navi_callouts, 0, 1, 1, tx_onoff,\s*"([^}]*)\}', menu)
    assert row, "the Gameplay tab's Navi callouts row, Off or On"
    assert re.sub(r"\s+", " ", row.group(1)).rstrip().endswith("nullptr, false, true"), \
        "live (no restart) and left alone by the Quality preset"
    assert "if (id == HOS_OPT_NAVI_CALLOUTS) return opts.navi_callouts;" in replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default="gcc")
    args = parser.parse_args()
    wiring()
    made = oot_patches.patch_navi_hints(LIFTED)
    assert made and made.count(oot_patches.NAVI_HINT_CALL) == 1 and made.count(oot_patches.NAVI_HINT_DECL) == 1, made
    assert made.index(oot_patches.NAVI_HINT_CALL) == made.index(oot_patches.NAVI_HINT_HEAD) + len(oot_patches.NAVI_HINT_HEAD)
    assert oot_patches.patch_navi_hints(made) == made   # (made before: left as it is)
    other = LIFTED.replace("void f_80ccf0f0", "void f_90ccf0f0")   # (another build: not this function)
    assert oot_patches.patch_navi_hints(other) is None
    out, counts, lines = oot_patches.patch_file(LIFTED, "code_000.c", protect_hearts=True)
    assert counts["Navi callouts hook"] == 1 and out == made and any("Navi callouts" in line for line in lines), (counts, lines)
    out, counts, _ = oot_patches.patch_file(LIFTED, "code_000.c", protect_hearts=False)   # (another build's lift)
    assert counts["Navi callouts hook"] == 0 and out == LIFTED
    with tempfile.TemporaryDirectory(prefix="navi-callouts-") as directory:
        directory = Path(directory)
        (directory / "a64.h").write_text(CONTEXT, encoding="utf-8")
        run = build(args.cc, directory, made, "patched")
        print(run.stdout, end="")
        assert run.returncode == 0, run.stdout + run.stderr
        run = build(args.cc, directory, LIFTED, "game")   # (the game's: registers with the row Off)
        assert run.returncode != 0 and "FAIL: Off: no hint registered" in run.stdout, run.stdout
    print("PASS: the Navi callouts row's patch at the area hints' registration, its wiring, and the game's function fails the "
          "same checks")


if __name__ == "__main__":
    main()
