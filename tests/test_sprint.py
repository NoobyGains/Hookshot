"""Sprint (host/nn_hid.c, the Controls page's row, the Controls tab's Sprint row): a control past the Switch's buttons with
keys and gamepad inputs that, while the left stick is pushed, holds A, the game's own run. Off by default.

The bindings: host/nn_hid.c's binding table is compiled alone (C), as tests/test_bound_keys.py does, and linked with the
menu's apply_sprint_layout cut out of gpu/vk/vk_menu.cpp (C++), against a fake hookshot_options.ini for each case. A new
install's defaults are the ones from before Sprint (Shift B, the left stick's press LS) and give Sprint nothing; the row
turned on gives it Shift and the press (B to V, LS keeping its other input) and turned off puts them back; a player who
rebound B, Shift or the press, or whose V is taken, or who bound Sprint, keeps theirs. The sources are checked for the
rest: read_input reads Sprint's key and gamepad input, npad_states hands sprint_step the stick only with the row on, the
menu has the rows, writes the pad_ line and runs the layout when the row changes or the Controls page resets.
sprint_step is compiled alone: A only while steered, the key held, the gamepad input a toggle that ends when Link stops and
wants a new press while he moves, hos_sprint_press_mask A's bit while it is Sprint's A (not the player's own), the
player's own A mid-sprint a gap and then a press of theirs (a tap shorter than the gap too), and with
HOS_SPRINT_STILL_MS the stick let go as it starts. nx2/oot_patches.py patch_sprint_press runs on lifted text: the mask goes
between the pair that makes "pressed" and its store, in the two controllers' updates only, once.
python -I -B tests/test_sprint.py   (needs a C and a C++ compiler)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_bound_keys  # noqa: E402  (its PRELUDE and the helpers that cut code out of a source)

MAIN = r"""
void sprint_layout(int on);   /* (the menu's apply_sprint_layout, layout.cpp) */
static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL %s line %d: %s\n", which, __LINE__, #c); fails++; } } while (0)
#define KEY(b) hos_binding(HOS_BIND_KEY, b, 0)
#define KEY2(b) hos_binding(HOS_BIND_KEY, b, 1)
#define PAD(b) hos_binding(HOS_BIND_PAD, b, 0)
#define PAD2(b) hos_binding(HOS_BIND_PAD, b, 1)
#define S HOS_KEY_SPRINT
int main(int argc, char **argv) {
    (void)argc;
    ini_dir = argv[1];
    const char *which = argv[2];
    binds_load();
    if (!strcmp(which, "new")) {
        /* the defaults are those from before Sprint: it has nothing */
        CHECK(KEY(S) == 0 && KEY2(S) == 0 && PAD(S) == -1 && PAD2(S) == -1);
        CHECK(KEY(HOS_SW_B) == VK_SHIFT && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
        sprint_layout(1);
        CHECK(KEY(S) == VK_SHIFT && PAD(S) == HOS_PAD_LSTICK);
        CHECK(KEY(HOS_SW_B) == 'V' && PAD(HOS_SW_B) == HOS_PAD_SOUTH);
        CHECK(PAD(HOS_SW_LS) == -1 && PAD2(HOS_SW_LS) == -1 && KEY(HOS_SW_LS) == VK_CONTROL);
        sprint_layout(1);   /* (on again: nothing moves) */
        CHECK(KEY(S) == VK_SHIFT && KEY(HOS_SW_B) == 'V' && PAD(S) == HOS_PAD_LSTICK && PAD(HOS_SW_LS) == -1);
        sprint_layout(0);
        CHECK(KEY(S) == 0 && KEY2(S) == 0 && PAD(S) == -1 && PAD2(S) == -1);
        CHECK(KEY(HOS_SW_B) == VK_SHIFT && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
        CHECK(!KEY2(HOS_SW_B));   /* (V gone with it) */
        /* a gamepad input bound to Sprint trades places with the Switch button that had it */
        sprint_layout(1);
        hos_bind(HOS_BIND_PAD, S, 0, HOS_PAD_SOUTH);
        CHECK(PAD(S) == HOS_PAD_SOUTH && PAD(HOS_SW_B) == HOS_PAD_LSTICK);
        hos_bind(HOS_BIND_KEY, S, 1, 'E');   /* a key bound to Sprint is taken from the button that had it */
        CHECK(KEY2(S) == 'E' && KEY(HOS_SW_A) == 0);
        hos_bind(HOS_BIND_PAD, HOS_KEY_MOVE_UP, 0, HOS_PAD_NORTH);   /* no gamepad input for a keys-only control */
        CHECK(PAD(HOS_KEY_MOVE_UP) == -1 && PAD(HOS_SW_X) == HOS_PAD_NORTH);
        hos_bind(HOS_BIND_KEY, -1, 0, 0);   /* Reset to defaults: Sprint's go (the menu then lays them out again) */
        CHECK(KEY(S) == 0 && PAD(S) == -1 && KEY(HOS_SW_B) == VK_SHIFT && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
    } else if (!strcmp(which, "ls-two")) {   /* LS has a second gamepad input: it keeps it */
        sprint_layout(1);
        CHECK(PAD(S) == HOS_PAD_LSTICK && PAD(HOS_SW_LS) == HOS_PAD_RPADDLE1 && PAD2(HOS_SW_LS) == -1);
        sprint_layout(0);
        CHECK(PAD(S) == -1 && PAD(HOS_SW_LS) == HOS_PAD_RPADDLE1 && PAD2(HOS_SW_LS) == HOS_PAD_LSTICK);
    } else if (!strcmp(which, "rebound")) {   /* B on the B key, Shift on X, LS on the right stick's press: all kept */
        sprint_layout(1);
        CHECK(KEY(HOS_SW_B) == 'B' && KEY(HOS_SW_X) == VK_SHIFT && KEY(S) == 0);
        CHECK(PAD(HOS_SW_LS) == HOS_PAD_RSTICK && PAD(HOS_SW_RS) == HOS_PAD_LSTICK && PAD(S) == -1);
        sprint_layout(0);
        CHECK(KEY(HOS_SW_B) == 'B' && KEY(HOS_SW_X) == VK_SHIFT && PAD(HOS_SW_RS) == HOS_PAD_LSTICK);
    } else if (!strcmp(which, "v-taken")) {   /* V already Y's: B keeps Shift, Sprint gets no key, the press still */
        sprint_layout(1);
        CHECK(KEY(HOS_SW_B) == VK_SHIFT && KEY2(HOS_SW_Y) == 'V' && KEY(S) == 0);
        CHECK(PAD(S) == HOS_PAD_LSTICK && PAD(HOS_SW_LS) == -1);
        sprint_layout(0);
        CHECK(KEY(HOS_SW_B) == VK_SHIFT && KEY2(HOS_SW_Y) == 'V' && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
    } else if (!strcmp(which, "own")) {   /* Sprint bound by the player: the row leaves everything as it is */
        CHECK(KEY(S) == 'G' && PAD(S) == HOS_PAD_LPADDLE1);
        sprint_layout(1);
        CHECK(KEY(S) == 'G' && PAD(S) == HOS_PAD_LPADDLE1 && KEY(HOS_SW_B) == VK_SHIFT && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
        sprint_layout(0);
        CHECK(KEY(S) == 'G' && PAD(S) == HOS_PAD_LPADDLE1 && KEY(HOS_SW_B) == VK_SHIFT && PAD(HOS_SW_LS) == HOS_PAD_LSTICK);
    } else {
        CHECK(!"no such case");
    }
    if (!fails) printf("PASS %s\n", which);
    return fails != 0;
}
"""

# (the menu's layout, cut out of vk_menu.cpp, with the host table above as its MkwVkHost)
LAYOUT = r"""
#include "vk_api.h"
extern "C" int hos_binding(int set, int button, int slot);
extern "C" void hos_bind(int set, int button, int slot, int code);
struct Host { int (*binding)(int, int, int); void (*bind)(int, int, int, int); } host_value{hos_binding, hos_bind},
    *host = &host_value;
static bool can_bind() { return true; }
%s
extern "C" void sprint_layout(int on) { apply_sprint_layout(on != 0); }
"""

CASES = {
    "new": None,
    "ls-two": "pad_ls=7,17\n",
    "rebound": "key_b=66,0\nkey_x=16,0\npad_ls=8\npad_rs=7\n",
    "v-taken": "key_b=16,0\nkey_y=1,86\n",
    "own": "key_sprint=71,0\npad_sprint=18\n",
}

class SprintTests(unittest.TestCase):
    def test_sources(self):
        hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
        read = test_bound_keys.block(hid, "static void read_input(")
        self.assertIn("bound_down(HOS_KEY_SPRINT, captured)", read, "read_input does not read Sprint's keys")
        # (this tree's read_input takes the pads through pads_merge, in front and behind another window alike)
        merge = test_bound_keys.block(hid, "static int pads_merge(")
        self.assertEqual(merge.count("sprint_now = pad_sprint_down();"), 1, "pads_merge does not read Sprint's gamepad input")
        self.assertEqual(read.count("pads_merge(buttons, stick)"), 2,
                         "read_input does not read the pads, in front and behind another window")
        npad = test_bound_keys.block(hid, "static void npad_states(")
        self.assertIn("const int sprint_held = rx_option(HOS_OPT_SPRINT, 0) ? sprint_now : 0;", npad,
                      "Sprint runs without the Controls tab's Sprint row on")
        self.assertIn("sprint_step(&buttons, stick, sprint_held, steered, menu_open || hos_oc_wait == 1, hos_now_ns());", npad,
                      "npad_states does not give Sprint the stick as the game will get it")
        self.assertLess(npad.index("const int steered ="), npad.index("sprint_step("),
                        "Sprint must see the stick before it lets it go")
        menu = (ROOT / "gpu" / "vk" / "vk_menu.cpp").read_text(encoding="utf-8")
        self.assertIn('{TAB_CONTROLS, "Sprint", &opts.sprint, 0, 1, 1, tx_onoff,', menu, "the Controls tab has no Sprint row")
        row = menu[menu.index('{TAB_CONTROLS, "Sprint"'):]
        row = row[:row.index("},") + 2]
        self.assertIn("changes your controls", row, "the Sprint row does not warn that it changes the controls")
        self.assertIn("int sprint = 0;", (ROOT / "gpu" / "vk" / "vk_menu.h").read_text(encoding="utf-8"),
                      "Sprint is not off by default")
        self.assertIn("if (r.value == &opts.sprint) apply_sprint_layout(*r.value != 0);",
                      test_bound_keys.block(menu, "void set_row("), "turning the row on or off does not lay out the controls")
        self.assertIn("if (opts.sprint) apply_sprint_layout(true);", menu, "Reset to defaults leaves Sprint with nothing")
        replay = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
        self.assertIn("if (id == HOS_OPT_SPRINT) return opts.sprint;", replay, "the host cannot see the Sprint row")
        names = test_bound_keys.block(hid, "static const char *const bind_names[HOS_KEY_N]")
        menu_names = test_bound_keys.block(menu, "const char* const bind_names[HOS_KEY_N]")
        self.assertEqual(re.findall(r'"(\w+)"', names), re.findall(r'"(\w+)"', menu_names),
                         "the menu writes other names than host/nn_hid.c reads")
        self.assertEqual(re.findall(r'"(\w+)"', names)[-1], "sprint", "Sprint's lines are not pad_sprint and key_sprint")
        self.assertIn('{HOS_KEY_SPRINT, "Sprint"}', menu, "the Controls page has no Sprint row")
        self.assertIn("|| i == HOS_KEY_SPRINT) {\n                const int alternate", menu, "the menu does not write pad_sprint")
        api = (ROOT / "gpu" / "vk" / "vk_api.h").read_text(encoding="utf-8")
        self.assertIn("HOS_KEY_OC_NOTE_X, HOS_KEY_WALK, HOS_KEY_SPRINT, HOS_KEY_N };", api, "Sprint is not the control after the ocarina's notes")

    def test_bindings(self):
        cc = shutil.which("gcc") or shutil.which("clang")
        cxx = shutil.which("g++") or shutil.which("clang++")
        if not cc or not cxx:
            self.skipTest("no C and C++ compiler")
        hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
        code = test_bound_keys.between(hid, "static const char *const bind_names[HOS_KEY_N]", "\nvoid hos_bind(")
        code = code.replace("GetModuleFileNameA(NULL,", "GetModuleFileNameA(0,")
        menu = (ROOT / "gpu" / "vk" / "vk_menu.cpp").read_text(encoding="utf-8")
        layout = test_bound_keys.block(menu, "void apply_sprint_layout(")
        include = ["-I", str(ROOT / "gpu" / "vk"), "-I", str(ROOT / "gpu")]
        with tempfile.TemporaryDirectory(prefix="hookshot-sprint-") as tmp:
            tmp = Path(tmp)
            (tmp / "t.c").write_text(test_bound_keys.PRELUDE + code + MAIN, encoding="utf-8")
            (tmp / "layout.cpp").write_text(LAYOUT % layout, encoding="utf-8")
            binary = tmp / ("t.exe" if sys.platform == "win32" else "t")
            for command in ([cc, "-std=gnu11", "-Wall", "-Wno-unused-function", *include, "-c", str(tmp / "t.c"),
                             "-o", str(tmp / "t.o")],
                            [cxx, "-std=c++17", "-Wall", "-Wextra", "-D_Static_assert=static_assert", *include, "-c", str(tmp / "layout.cpp"),
                             "-o", str(tmp / "layout.o")],
                            [cxx, str(tmp / "t.o"), str(tmp / "layout.o"), "-o", str(binary)]):
                build = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(build.returncode, 0, build.stderr)
            for name, ini in CASES.items():
                with self.subTest(case=name):
                    folder = tmp / name
                    folder.mkdir()
                    if ini is not None:
                        (folder / "hookshot_options.ini").write_text(ini, encoding="utf-8")
                    run = subprocess.run([str(binary), str(folder), name], text=True, capture_output=True, timeout=30)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


STEP_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
enum { B_A = 0 };
volatile uint32_t hos_sprint_press_mask;
static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)
static uint64_t b;
static int32_t st[4];
static void step_a(int held, int steered, int menu, int64_t ms, int own_a) {
    b = own_a ? 1 : 0, st[0] = steered ? 30000 : 0, st[1] = 0;
    sprint_step(&b, st, held, steered, menu, ms * 1000000);
}
static void step(int held, int steered, int menu, int64_t ms) { step_a(held, steered, menu, ms, 0); }
#define RUNS (b & 1)
#define STILL (st[0] == 0)
#define MASK hos_sprint_press_mask
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "still")) {   /* HOS_SPRINT_STILL_MS=120: the stick let go for the first 120 ms */
        step(SPRINT_KEY, 1, 0, 1000);    CHECK(RUNS && STILL);
        step(SPRINT_KEY, 1, 0, 1100);    CHECK(RUNS && STILL);
        step(SPRINT_KEY, 1, 0, 1130);    CHECK(RUNS && !STILL);
        step(0, 1, 0, 1200);             CHECK(!RUNS && !STILL);
        step(SPRINT_KEY, 1, 0, 1300);    CHECK(RUNS && STILL);     /* again: a new start */
        if (!fails) printf("PASS still\n");
        return fails != 0;
    }
    /* the key: A while held and steered, the stick as it is; the press mask A's bit while it is Sprint's A */
    step(SPRINT_KEY, 0, 0, 0);       CHECK(!RUNS && !MASK);   /* standing: nothing */
    step(SPRINT_KEY, 1, 0, 1000);    CHECK(RUNS && !STILL && MASK == 1);
    step(SPRINT_KEY, 1, 0, 1100);    CHECK(RUNS && !STILL && MASK == 1);
    /* the player's own A going down mid-sprint: A let go for the gap, then held as their press (the mask 0) */
    step_a(SPRINT_KEY, 1, 0, 1150, 1);   CHECK(!RUNS && MASK == 0);   /* the gap: A up */
    step_a(SPRINT_KEY, 1, 0, 1180, 1);   CHECK(!RUNS && MASK == 0);
    step_a(SPRINT_KEY, 1, 0, 1201, 1);   CHECK(RUNS && MASK == 0);    /* A down again: a press, theirs */
    step(SPRINT_KEY, 1, 0, 1230);        CHECK(RUNS && MASK == 0);    /* theirs up: still owed for the gap */
    step(SPRINT_KEY, 1, 0, 1260);        CHECK(RUNS && MASK == 1);    /* Sprint's own A again: no press */
    /* a tap shorter than the gap: the press still comes */
    step_a(SPRINT_KEY, 1, 0, 1300, 1);   CHECK(!RUNS);
    step(SPRINT_KEY, 1, 0, 1320);        CHECK(!RUNS);
    step(SPRINT_KEY, 1, 0, 1360);        CHECK(RUNS && MASK == 0);
    step(SPRINT_KEY, 1, 0, 1420);        CHECK(RUNS && MASK == 1);
    step(0, 1, 0, 1450);             CHECK(!RUNS && !STILL && !MASK);   /* let go: walks */
    /* their A down before Sprint starts: theirs, no gap */
    step_a(0, 1, 0, 1460, 1);        CHECK(RUNS && !MASK);    /* (the player's own A: not Sprint's) */
    step_a(SPRINT_KEY, 1, 0, 1470, 1);   CHECK(RUNS && MASK == 0);
    step(0, 1, 0, 1480);
    step(SPRINT_KEY, 1, 1, 1500);    CHECK(!RUNS && !MASK);   /* not with the menu open */
    step(0, 1, 0, 1600);
    /* the gamepad input: a toggle while steered */
    step(SPRINT_PAD, 1, 0, 2000);    CHECK(RUNS && !STILL && MASK == 1);
    step(0, 1, 0, 2050);             CHECK(RUNS && MASK == 1);   /* let go: still runs */
    step(SPRINT_PAD, 1, 0, 2300);    CHECK(RUNS);              /* held on: no change */
    step(0, 1, 0, 2400);             CHECK(RUNS);
    step(0, 0, 0, 2500);             CHECK(!RUNS && !MASK);    /* stopped: off */
    step(0, 1, 0, 2600);             CHECK(!RUNS);             /* moving again: wants a new press */
    step(SPRINT_PAD, 0, 0, 2700);    CHECK(!RUNS);             /* pressed standing: nothing */
    step(SPRINT_PAD, 1, 0, 2800);    CHECK(!RUNS);             /* (still the same press) */
    step(0, 1, 0, 2900);
    step(SPRINT_PAD, 1, 0, 3000);    CHECK(RUNS && MASK == 1);   /* a new press while moving */
    if (!fails) printf("PASS\n");
    return fails != 0;
}
"""


class SprintStepTests(unittest.TestCase):
    def test_step(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("no C compiler")
        hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
        gap = re.search(r"^#define SPRINT_ROLL_GAP_MS [^\n]*", hid, re.M).group(0)
        code = (test_bound_keys.block(hid, "enum { SPRINT_KEY") + ";\n" + gap + "\n" +
                test_bound_keys.block(hid, "static void sprint_step("))
        head, body = STEP_MAIN.split("static int fails;", 1)
        with tempfile.TemporaryDirectory(prefix="hookshot-sprint-step-") as tmp:
            tmp = Path(tmp)
            (tmp / "t.c").write_text(head + code + "\nstatic int fails;" + body, encoding="utf-8")
            binary = tmp / ("t.exe" if sys.platform == "win32" else "t")
            build = subprocess.run([compiler, "-std=gnu11", "-Wall", "-Werror", str(tmp / "t.c"), "-o", str(binary)],
                                   text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            env = {k: v for k, v in os.environ.items() if k != "HOS_SPRINT_STILL_MS"}
            run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30, env=env)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            run = subprocess.run([str(binary), "still"], text=True, capture_output=True, timeout=30,
                                 env=dict(env, HOS_SPRINT_STILL_MS="120"))
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


# (the controllers' update as the lifter writes it, cut down: the pair that makes "pressed" and "released", then the store)
LIFTED = '''#include "a64.h"
void f_8038a220(Ctx *__restrict A64_NOESC c) {
    c->x[8]=recomp_load32(c,c->x[19] + 276);
    { uint64_t _r = (c->x[8] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[28])) << 0))); _r &= 0xFFFFFFFFULL; c->x[9] = _r; }
    { uint64_t _r = (c->x[28] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[8])) << 0))); _r &= 0xFFFFFFFFULL; c->x[8] = _r; }
    { uint64_t _b=c->x[19]; int64_t _o=8; recomp_stp32(c,(_b+_o),c->x[9],c->x[8]); }
}
void f_834a3680(Ctx *__restrict A64_NOESC c) {
    { uint64_t _r = (c->x[8] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[21])) << 0))); _r &= 0xFFFFFFFFULL; c->x[9] = _r; }
    { uint64_t _r = (c->x[21] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[8])) << 0))); _r &= 0xFFFFFFFFULL; c->x[8] = _r; }
    { uint64_t _b=c->x[19]; int64_t _o=8; recomp_stp32(c,(_b+_o),c->x[9],c->x[8]); }
}
void f_80000000(Ctx *__restrict A64_NOESC c) {
    { uint64_t _r = (c->x[8] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[28])) << 0))); _r &= 0xFFFFFFFFULL; c->x[9] = _r; }
    { uint64_t _r = (c->x[28] & ~((uint64_t)(uint32_t)(((uint32_t)(c->x[8])) << 0))); _r &= 0xFFFFFFFFULL; c->x[8] = _r; }
}
'''


class SprintPressPatchTests(unittest.TestCase):
    """nx2/oot_patches.py patch_sprint_press on lifted text: the mask after the pair in the two functions, nowhere else"""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "nx2"))
        import oot_patches
        self.p = oot_patches

    def test_patch(self):
        out, n = self.p.patch_sprint_press(LIFTED)
        self.assertEqual(n, 2)
        self.assertEqual(out.count(self.p.SPRINT_MASK), 2, "the mask is not in both controllers' update")
        self.assertEqual(out.count(self.p.SPRINT_DECL), 1)
        for head in self.p.SPRINT_HEADS:
            body = out[out.index(head):]
            body = body[:body.index("\n}\n")]
            self.assertLess(body.index("c->x[9] = _r; }"), body.index(self.p.SPRINT_MASK), "the mask before pressed is made")
            self.assertLess(body.index(self.p.SPRINT_MASK), body.index("recomp_stp32"), "the mask after the store")
        other = out[out.index("void f_80000000"):]
        self.assertNotIn("hos_sprint_press_mask", other, "a function that is not the controllers' update was patched")
        again, n2 = self.p.patch_sprint_press(out)
        self.assertEqual((again, n2), (out, 2), "a second run changes the code")

    def test_drifted(self):
        """an anchor that is not there leaves the code as it was, and the count says so (report() warns)"""
        drifted = LIFTED.replace("c->x[28]", "c->x[27]")
        out, n = self.p.patch_sprint_press(drifted)
        self.assertEqual(n, 1)
        self.assertNotIn("f_8038a220(Ctx *__restrict A64_NOESC c) {\n    c->x[8]=recomp_load32(c,c->x[19] + 276);\n" +
                         self.p.SPRINT_MASK, out)
        self.assertEqual(self.p.patch_sprint_press("#include \"a64.h\"\n"), ("#include \"a64.h\"\n", 0))

    def test_body_ends_at_its_brace(self):
        """f_8038a220 without its pair, followed by a function that is not a `void f_` with one: that pair is not
        counted as f_8038a220's (the body ends at its own closing brace), and is left alone"""
        lines = LIFTED.split("\n")
        start = lines.index("void f_8038a220(Ctx *__restrict A64_NOESC c) {")
        pair, store = lines[start + 2:start + 4], lines[start + 4]
        helper = ["static void helper(Ctx *__restrict A64_NOESC c) {"] + pair + [store, "}"]
        text = "\n".join(lines[:start + 2] + [store, "}"] + helper + lines[start + 6:])
        self.assertIn("static void helper", text)
        out, n = self.p.patch_sprint_press(text)
        self.assertEqual(n, 1, "the pair in the function after f_8038a220 was counted as its own")
        self.assertNotIn(self.p.SPRINT_MASK, out[out.index("static void helper"):out.index("void f_834a3680")])

    def test_host_side(self):
        hid = (ROOT / "host" / "nn_hid.c").read_text(encoding="utf-8")
        self.assertIn("volatile uint32_t hos_sprint_press_mask;", hid, "the host has no press mask for the patch")
        patches = (ROOT / "nx2" / "oot_patches.py").read_text(encoding="utf-8")
        self.assertIn('counts["sprint press"] += n', patches, "patch_file does not run the patch")
        self.assertIn('total["sprint press"] != len(SPRINT_HEADS)', patches, "report() does not warn when it is missing")


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=1))
