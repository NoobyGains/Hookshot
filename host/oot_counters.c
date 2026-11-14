/* The Classic counters row (Gameplay tab, live): as on the N64, no count over Link when he picks something up, and the
   rupees always in the bottom left corner (gpu/vk/vk_menu.cpp draw_rupees).

   - The pick-up indicator (f_80a87e50, its layout at +0x28 of an object of vtable 0x84c0ac28) is updated by the game on
     its own. Its root's alpha (+0x74 of *(*(layout + 0x80) + 0x100)) is set to 0 through the game's own setter
     (f_802f8ac0, which passes the change on to the children), and the setter's later writes to that root (the indicator's
     fade animation) are turned into 0 too. Inventory events, timers and animations run as before; the row Off gives the
     root its alpha back.
   - The rupees: f_80a87c30(manager, 1) is how that indicator reads the wallet, through the game data manager
     *(*0x84c9e0d0). Once every 10 frames, with the row on and a live player, the frame hook asks it and hands the count to
     the renderer (OOT_HUD_RUPEES_ID); -1 without one, and nothing is drawn.
   nx2/oot_counters.py hooks the three sites, on the 1.1.1 build only. From Ocarina Reborn (misterrageguy-cyber), who found
   the layout chain with its UI diagnostics; Hookshot calls the two game functions through a64_lookup, so a lift without
   them leaves the row doing nothing rather than failing to link. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"
#include "../gpu/vk/oot_cheat_items.h"
#include <string.h>
#include <windows.h>   /* (SRW locks; host/posix/windows.h on Linux) */

int rx_option(int id, int otherwise);
void rx_option_set(int id, int value);
int hos_oot_flight_shortcut_ready(void);   /* (a live player, the game updating him: host/hos_main.c) */

#define OOT_PICKUP_VTABLE 0x84c0ac28ull
#define OOT_ALPHA_SETTER 0x802f8ac0ull
#define OOT_WALLET_READ 0x80a87c30ull
#define OOT_HUD_MANAGER_SLOT 0x84c9e0d0ull   /* (the manager's pointer, as f_80a87e50 loads it at 0x80a88458) */

static int on(void) { return rx_option(HOS_OPT_CLASSIC_COUNTERS, 0) == 1; }

typedef struct { uint64_t owner, root; uint32_t alpha; int hidden; } Pickup;
static Pickup pickups[32];
static SRWLOCK pickup_lock = SRWLOCK_INIT;
static _Thread_local int setting_alpha;

static uint64_t pickup_root(Ctx *c, uint64_t owner) {
    if (!owner || recomp_load64(c, owner) != OOT_PICKUP_VTABLE) return 0;
    const uint64_t layout = recomp_load64(c, owner + 0x28);
    const uint64_t instance = layout ? recomp_load64(c, layout + 0x80) : 0;
    return instance ? recomp_load64(c, instance + 0x100) : 0;
}

/* the root's alpha through the game's own setter, which marks the children too; the game's registers kept around it */
static void set_alpha(Ctx *c, uint64_t root, uint32_t alpha) {
    A64Fn setter = a64_lookup(OOT_ALPHA_SETTER);
    if (!setter) return;
    const Ctx saved = *c;
    c->x[0] = root;
    c->x[30] = 0;
    memcpy(&c->vreg[0][0], &alpha, sizeof alpha);
    setting_alpha++;
    setter(c);
    setting_alpha--;
    *c = saved;
}

/* at the head of the pick-up indicator's update: its root hidden while the row is on, given back when it goes off */
void hos_oot_counters_pickup(Ctx *c) {
    const uint64_t owner = c->x[0], root = pickup_root(c, owner);
    if (!root) return;
    const int enabled = on();
    const uint32_t current = (uint32_t)recomp_load32(c, root + 0x74);
    uint32_t alpha = current;
    int write = 0, logged = 0;
    AcquireSRWLockExclusive(&pickup_lock);
    Pickup *p = NULL, *empty = NULL;
    for (unsigned i = 0; i < sizeof pickups / sizeof pickups[0]; i++) {
        if (pickups[i].owner && pickup_root(c, pickups[i].owner) != pickups[i].root)
            memset(&pickups[i], 0, sizeof pickups[i]);   /* (the object reused: forget it) */
        if (pickups[i].owner == owner) { p = &pickups[i]; break; }
        if (!pickups[i].owner && !empty) empty = &pickups[i];
    }
    if (enabled) {
        if (!p) p = empty;
        if (p) {
            if (p->root != root || !p->hidden || current != 0) p->alpha = current;
            logged = !p->hidden || p->root != root;
            p->owner = owner, p->root = root, p->hidden = 1;
            alpha = 0, write = current != 0;
        }
    } else if (p) {
        if (p->root == root && p->hidden && current == 0) alpha = p->alpha, write = alpha != current;
        memset(p, 0, sizeof *p);
    }
    ReleaseSRWLockExclusive(&pickup_lock);
    if (write) set_alpha(c, root, alpha);
    if (logged) {
        static volatile LONG lines;
        if (InterlockedIncrement(&lines) <= 8)
            hos_log("counters: pick-up count hidden (owner %#llx, root %#llx)", (unsigned long long)owner, (unsigned long long)root);
    }
}

/* after the alpha setter's first load, before its comparison: the alpha asked for (s0) kept, and 0 set instead, on a
   hidden root only */
void hos_oot_counters_alpha(Ctx *c) {
    if (setting_alpha || !on()) return;
    AcquireSRWLockExclusive(&pickup_lock);
    for (unsigned i = 0; i < sizeof pickups / sizeof pickups[0]; i++) {
        Pickup *p = &pickups[i];
        if (p->hidden && p->root == c->x[0]) {
            if (pickup_root(c, p->owner) == p->root) {
                memcpy(&p->alpha, &c->vreg[0][0], sizeof p->alpha);
                const uint32_t zero = 0;
                memcpy(&c->vreg[0][0], &zero, sizeof zero);
            } else {
                memset(p, 0, sizeof *p);   /* (the object reused: its new layout left alone) */
            }
            break;
        }
    }
    ReleaseSRWLockExclusive(&pickup_lock);
}

/* once a frame, at the head of f_831f3200: the wallet every 10 frames while the row is on. The game's registers are kept
   around the call: it runs inside the game's own frame */
void hos_oot_counters_frame(Ctx *c) {
    static unsigned frames;
    static int sent = -2;
    if (!on() || !hos_oot_flight_shortcut_ready()) {
        if (sent != -1) rx_option_set(OOT_HUD_RUPEES_ID, -1), sent = -1;
        frames = 0;
        return;
    }
    if (frames++ % 10) return;
    A64Fn wallet = a64_lookup(OOT_WALLET_READ);
    const uint64_t slot = recomp_load64(c, OOT_HUD_MANAGER_SLOT);
    const uint64_t mgr = slot ? recomp_load64(c, slot) : 0;
    int value = -1;
    if (mgr && wallet) {
        const Ctx keep = *c;
        c->x[0] = mgr;
        c->x[1] = 1;
        c->x[30] = 0;
        wallet(c);
        value = (int)(uint32_t)c->x[0];
        *c = keep;
        if (value < 0 || value > 9999) value = -1;   /* (not a wallet: nothing shown) */
    }
    if (value != sent) {
        rx_option_set(OOT_HUD_RUPEES_ID, value), sent = value;
        static int said;
        if (said++ < 8) hos_log("counters: rupees %d", value);
    }
}
