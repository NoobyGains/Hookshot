/* The Death counter row (gpu/vk/vk_menu.cpp draw_corner): how often Link's hearts reached zero since the game started.
   nx2/oot_patches.py patch_life calls hos_oot_life_seen at Link's life write (f_804bd8c0) with each change as it will be
   written, after Damage taken. A bottled fairy revives Link through that same write, 0 to 20 right after the hearts ran
   out, while a game over refills them without it: 0 counts a death, and a raise from 0 takes it back, a fairy saved him.
   From Ocarina Reborn (misterrageguy-cyber; its fairy test, 2026-11-12). */
#include "hos.h"
#include "../gpu/vk/oot_cheat_items.h"
#include <windows.h>   /* (Interlocked; host/posix/windows.h on Linux) */

void rx_option_set(int id, int value);

void hos_oot_life_seen(uint32_t old, uint32_t next) {
    static volatile LONG deaths;
    if (next == 0 && old > 0) {
        rx_option_set(OOT_HUD_DEATHS_ID, (int)InterlockedIncrement(&deaths));
        hos_log("life: Link's hearts ran out (%u to 0)", old);
    } else if (old == 0 && next > 0 && deaths > 0) {
        rx_option_set(OOT_HUD_DEATHS_ID, (int)InterlockedDecrement(&deaths));
        hos_log("life: revived from 0 to %u (a fairy): not counted", next);
    }
}
