"""The Classic counters row (host/oot_counters.c): the pick-up indicator's update (f_80a87e50) and the layout alpha setter
(f_802f8ac0) hooked to hide the count over Link, and the render setup (f_831f3200, once a frame) to read the wallet for the
renderer's rupee counter. Image-absolute addresses (main at 0x80020000). Only on the game build they were found on (ported
from Ocarina Reborn), and only while every word below is there: otherwise left out, and the row does nothing.
"""

BUILD_ID = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
PACIBSP = 0xd503237f
HOOKS = (
    # (the pick-up indicator's update, at its head)
    (0x80a87e50, PACIBSP, "{ extern void hos_oot_counters_pickup(Ctx *c); hos_oot_counters_pickup(c); }"),
    # (the layout alpha setter, after its first load: ldr s1, [x0, #0x74])
    (0x802f8ac0, 0xbd407401, "{ extern void hos_oot_counters_alpha(Ctx *c); hos_oot_counters_alpha(c); }"),
    # (once a frame: the wallet for the bottom left corner. ldrb w8, [x0, #0xe20])
    (0x831f3200, 0x39788008, "{ extern void hos_oot_counters_frame(Ctx *c); hos_oot_counters_frame(c); }"),
)
# (the indicator's update in its vtable, and the two loads the root's chain is read with)
CHECKS = ((0x84c0af28, 0x80a87e50), (0x84c0af2c, 0), (0x80229660, 0xf9402000), (0x8045b1f0, 0xf9408008))
# (the game functions host/oot_counters.c calls through a64_lookup: lifted as functions of their own)
CALLED = (0x802f8ac0, 0x80a87c30)


def install(lifter, img, build_id):
    if build_id != BUILD_ID or any(img.word(pc) != word for pc, word, _ in HOOKS) or \
            any(img.word(pc) != word for pc, word in CHECKS):
        print("classic counters: other game build, left out")
        return 0
    for pc, _, text in HOOKS:
        text += "   /* (nx2/oot_counters.py: Classic counters) */"
        lifter.after[pc] = (lifter.after[pc] + "\n" if pc in lifter.after else "") + text
    lifter.entries.update(CALLED)
    print("classic counters: hooked")
    return 1
