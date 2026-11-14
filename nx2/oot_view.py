"""The View distance, Grass and Shadow distance rows: host/oot_view.c's hos_oot_view at the head of the game's render setup
(f_831f3200, main+0x31d3200), once a frame. Only on the game build its object chains were found on (hotoni's Graphics-Menu
mod; ported from Ocarina Reborn), and only while that function's first word is there: otherwise left out, and the rows do
nothing.
"""

MAIN = 0x80020000
BUILD_ID = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
SITE = MAIN + 0x31d3200
WORD = 0x39788008   # ldrb w8, [x0, #0xe20]
HOOK = "{ extern void hos_oot_view(Ctx *c); hos_oot_view(c); }   /* (nx2/oot_view.py: View distance, Grass, Shadow distance) */"


def install(lifter, img, build_id):
    if build_id != BUILD_ID or img.word(SITE) != WORD:
        print("view distance: other game build, left out")
        return 0
    lifter.after[SITE] = (lifter.after[SITE] + "\n" if SITE in lifter.after else "") + HOOK
    print("view distance: render setup hooked")
    return 1
