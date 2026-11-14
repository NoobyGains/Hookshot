"""The Debug tab's Rupees row: Left and Right choose an amount, confirm adds or takes it, up to what the wallet holds.

The game side (host/hos_main.c oot_gamedata_int_at, oot_wallet_capacity, oot_add_rupees) is cut out of the source and compiled
with a made-up guest memory: the GameData int found by its hash (open addressing, wrapping, empty slot ends the search, a full
table ends it too), the wallet's size by the wallets Link has (200, 500, 1000), the result kept from 0 to that size, and
nothing written when the save has no such int. The menu side is read as text: the amounts, the default (+100), the action ids
(clear of the time's, the pouch's, the age's and the teleport's), the row and its place in the Debug tab's order.

python -I -B tests/test_oot_rupees.py [--cc gcc]
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import block  # noqa: E402

RUN_ALL_ARGS = ["--cc", "gcc"]
ROOT = Path(__file__).resolve().parents[1]


def host_checks(cc):
    host = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    cut = "\n".join(block(host, m) for m in (
        "static uint64_t oot_singleton(Ctx *c, uint64_t slot)",
        "static uint64_t oot_gamedata_int_at(Ctx *c, uint32_t hash) {",
        "static int oot_wallet_capacity(Ctx *c)",
        "static void oot_add_rupees(Ctx *c, int delta)"))
    hash_line = re.search(r"#define OOT_RUPEES_HASH 0x([0-9a-f]+)u", host)
    assert hash_line, "OOT_RUPEES_HASH is gone from host/hos_main.c"
    source = r'''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct { int unused; } Ctx;
#define OOT_RUPEES_HASH 0x''' + hash_line.group(1) + r'''u
#define OOT_GAMEDATA_SLOT 0x40ULL
static uint8_t mem[0x4000];   /* the guest's memory: small addresses are offsets in it */
static int stores, logs, small = 0, medium = 0, large = 0;
static uint64_t recomp_load64(Ctx *c, uint64_t a) { uint64_t v; (void)c; memcpy(&v, mem + a, 8); return v; }
static uint64_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; memcpy(&v, mem + a, 4); return v; }
static void recomp_store32(Ctx *c, uint64_t a, uint64_t v) { uint32_t t = (uint32_t)v; (void)c; memcpy(mem + a, &t, 4); stores++; }
static void hos_log(const char *fmt, ...) { (void)fmt; logs++; }
static int oot_item_count(Ctx *c, const char *name) {   /* the pouch: which wallets Link has */
    (void)c;
    if (!strcmp(name, "Item_Wallet_Large")) return large;
    if (!strcmp(name, "Item_Wallet_Medium")) return medium;
    return small;
}
''' + cut + r'''
#define MGR 0x100
#define ENTRIES 0x1000
#define TABLE 0x2000
static void put64(uint64_t a, uint64_t v) { memcpy(mem + a, &v, 8); }
static void put32(uint64_t a, uint32_t v) { memcpy(mem + a, &v, 4); }
/* a GameDataMgr with a table of `size` slots: its (hash, index) pairs, each int's 40-byte entry with the value at +28 */
static void world(uint32_t size, uint32_t count) {
    memset(mem, 0, sizeof mem);
    put64(OOT_GAMEDATA_SLOT, 0x80);   /* the slot holds the singleton's holder, the holder the manager */
    put64(0x80, MGR);
    put64(MGR + 0xd8, ENTRIES), put64(MGR + 0xe0, TABLE);
    put32(MGR + 0xd0, count), put32(MGR + 0xec, size);
}
static void add(uint32_t size, uint32_t hash, uint32_t index) {   /* open addressing, as the game's table */
    uint32_t slot = hash % size;
    while (*(uint32_t *)(mem + TABLE + slot * 8ULL)) slot = (slot + 1) % size;
    put32(TABLE + slot * 8ULL, hash), put32(TABLE + slot * 8ULL + 4, index);
}
static void rupees(uint32_t index, uint32_t v) { put32(ENTRIES + index * 40ULL + 28, v); }
static int have(uint32_t index) { return (int)recomp_load32(0, ENTRIES + index * 40ULL + 28); }
static void run(int delta, int expect_stores) {
    stores = 0;
    oot_add_rupees(0, delta);
    assert(stores == expect_stores);
}
int main(void) {
    Ctx *c = 0;
    /* found by its hash, by value at +28 */
    world(8, 3);
    add(8, 0x11111111u, 0), add(8, OOT_RUPEES_HASH, 1), add(8, 0x22222222u, 2);
    rupees(0, 7), rupees(1, 50), rupees(2, 9);
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == ENTRIES + 40 + 28);
    assert(oot_gamedata_int_at(c, 0x11111111u) == ENTRIES + 28 && oot_gamedata_int_at(c, 0x22222222u) == ENTRIES + 80 + 28);
    assert(oot_gamedata_int_at(c, 0x33333333u) == 0);   /* an int the save does not have: an empty slot ends the search */
    /* the child's wallet holds 200 */
    assert(oot_wallet_capacity(c) == 200);
    run(100, 1), assert(have(1) == 150);
    run(100, 1), assert(have(1) == 200);   /* up to the wallet, not past it */
    run(1, 1), assert(have(1) == 200);
    run(-1000, 1), assert(have(1) == 0);   /* and not below nothing */
    run(-1, 1), assert(have(1) == 0);
    run(1, 1), assert(have(1) == 1);
    run(0, 1), assert(have(1) == 1);
    /* the other ints are left alone */
    assert(have(0) == 7 && have(2) == 9);
    /* the Adult's wallet 500, the Giant's 1000 (and the larger wins when both are in the pouch) */
    medium = 1;
    assert(oot_wallet_capacity(c) == 500);
    rupees(1, 450), run(500, 1), assert(have(1) == 500);
    large = 1;
    assert(oot_wallet_capacity(c) == 1000);
    rupees(1, 900), run(1000, 1), assert(have(1) == 1000);
    medium = 0;
    assert(oot_wallet_capacity(c) == 1000);
    /* a table whose rupees slot was taken: it probes on, wrapping at the end of the table */
    world(8, 2);
    add(8, 0x0000000fu, 0);   /* 15 % 8 == 7 == OOT_RUPEES_HASH % 8: the rupees go on to slot 0 */
    assert(OOT_RUPEES_HASH % 8 == 7);
    add(8, OOT_RUPEES_HASH, 1);
    rupees(0, 3), rupees(1, 20);
    large = medium = 0;
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == ENTRIES + 40 + 28);
    run(30, 1), assert(have(1) == 50 && have(0) == 3);
    /* no such int (an empty slot first): nothing is written, one line logged */
    world(8, 1);
    add(8, 0x0000000fu, 0), rupees(0, 5);
    logs = 0;
    run(100, 0);
    assert(logs == 1 && have(0) == 5);
    /* a table with every slot taken by other ints: the search ends (no endless loop) */
    world(4, 4);
    for (uint32_t i = 0; i < 4; i++) add(4, 0x10 + i, i);
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == 0);
    run(100, 0);
    /* the entry's index past the count (a stale table): not used */
    world(8, 1);
    add(8, OOT_RUPEES_HASH, 5);
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == 0);
    run(100, 0);
    /* no save loaded: no GameData manager, or a table not set up yet */
    world(8, 1);
    put64(0x80, 0);
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == 0);
    run(100, 0);
    world(8, 1);
    put64(MGR + 0xe0, 0);
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == 0);
    world(0, 1);   /* (its size zero: no modulo by zero) */
    assert(oot_gamedata_int_at(c, OOT_RUPEES_HASH) == 0);
    puts("ok");
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="oot-rupees-") as tmp:
        c_file = Path(tmp) / "rupees.c"
        exe = Path(tmp) / "rupees.exe"
        c_file.write_text(source, encoding="utf-8")
        subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", str(c_file), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


def menu_checks():
    items = (ROOT / "gpu/vk/oot_cheat_items.h").read_text(encoding="utf-8")
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    host = (ROOT / "host/hos_main.c").read_text(encoding="utf-8")
    steps = [int(x) for x in re.search(r"#define OOT_RUPEE_STEPS ([-\d, ]+)", items).group(1).split(",")]
    assert steps == sorted(steps) and len(set(steps)) == len(steps), "the amounts go from the most taken to the most added"
    assert 0 not in steps and steps[0] == -1000 and steps[-1] == 1000, steps
    assert len(steps) <= 32, "the host takes OOT_RUPEE_ACTION + 0..31 (hos_main.c)"
    default = int(re.search(r"int rupee_step = (\d+);", menu).group(1))
    assert steps[default] == 100, "the Rupees row starts at +100"
    action = int(re.search(r"#define OOT_RUPEE_ACTION (\d+)", items).group(1))
    assert action > 348 and action + 32 <= 999, "clear of the pouch (200 to 348), the age (999) and the teleport (1000 on)"
    assert "OOT_RUPEE_ACTION + 32" in host and f"action >= OOT_RUPEE_ACTION" in host
    # the row: once, a debug tool (Row::cheat 12), in the order after Inventory and before Teleport, with its confirm and cell
    assert menu.count('{TAB_DEBUG, "Rupees"') == 1
    row = menu[menu.index('{TAB_DEBUG, "Rupees"'):]
    assert re.match(r'[^}]*false, true, 12\}', row), "the Rupees row is Row::cheat 12"
    order = re.search(r"debug_tools_order\[\] = \{([^}]*)\}", menu).group(1).replace(" ", "").split(",")
    assert order.index("12") == order.index("10") + 1 and order.index("8") == order.index("12") + 1, order
    assert "return i == 4 || i == 5 || i == 6 || i == 11 || i == 12;" in menu, "Left and Right choose the amount"
    assert "OOT_CHEAT_RUPEES_ID" in menu and "OOT_CHEAT_RUPEES_ID" in host, "the game side says Link's rupees; the row shows them"
    # the id the row reads is in no other use
    ids = re.findall(r"#define (\w+) (\d+)\s", items)
    used = [n for n, v in ids if v == re.search(r"#define OOT_CHEAT_RUPEES_ID (\d+)", items).group(1)]
    assert used == ["OOT_CHEAT_RUPEES_ID"], used


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    a = p.parse_args()
    menu_checks()
    host_checks(a.cc)
    print("PASS: Rupees row: the amounts, the GameData int found, the wallet's size, the result kept from 0 to it")


if __name__ == "__main__":
    main()
