/* Hero mode (the Gameplay tab's row, HOS_OPT_HERO_MODE, live): double damage (host/oot_damage.c) and no recovery hearts from the
   drop tables (grass, pots, rocks, enemies). The remake has no Hero mode of its own, and its players asked for one: borkiee's
   Simple Hero Mode Options mod on GameBanana doubles the enemies' damage in their actor files, and says hearts still drop
   because it could not change that. Link's Awakening's Hero Mode and Ship of Harkinian's No Heart Drops take the hearts away
   as here (Ocarina 3D's Master Quest only doubles the damage).

   The game's drops are data: an actor's drop tables (game::drop::DropTable / DropSubTable) name each item by its type (Hp, Mp,
   Rupee, ... Other) and an actor, and the lottery (f_82f145e0, or f_82f162f0 when its caller asks for the simple one) fills a list
   with what it drew: Hp items as the master data's HpActor, Obj_Heart (GameParameter/DropGlobalParam), items of type Other by
   their own name (Obj_Heart in enemies' tables, the pots' and grass's ResourceSupply tables), and after the game's own
   replacements (DropLotteryMasterData's ReplaceSetting, judged by f_82f1a060: a heart drawn at full health becomes a green
   rupee, HpMax; a fairy drawn while the bottles hold as many fairies as MaxFairyNum becomes a heart, FairyMax).
   nx2/oot_patches.py patch_drops calls hos_oot_drops after each of the lotteries' five calls with that list: every recovery
   heart is taken out of it, as the game's own erase does, and the drop goes on with what is left. Nothing drawn means nothing
   dropped, as when the lottery draws nothing. Fairies, rupees and the rest stay, and so does the green rupee the game
   itself puts in a heart's place at full health (HpMax: the heart is gone before the list comes back). Pieces of Heart and
   Heart Containers are placed or given, not drawn from these tables; hearts placed in a room stay too (Ship of Harkinian's No
   Heart Drops is the same).

   The list (the lottery's x1): s32 count, s32 capacity, the drops' pointers at +8, the free slots' chain at +16 (a slot's first
   word the next one's address). A drop: its actor's name at +0 (a C string), the name's hash at +8. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"
#include <string.h>

int rx_option(int id, int otherwise);

/* (the recovery heart and its two variants, Obj_Heart's children: not Obj_Heart_Piece* nor Obj_Heart_Container) */
static const char *const hero_hearts[] = {"Obj_Heart", "Obj_Heart_InWater", "Obj_Heart_Shootable"};

/* whether the drop's name is a recovery heart: the actor's name alone, or a path to its ActorParam ("Work/Actor/Obj_Heart.engine__
   actor__ActorParam.gyml"), whose name is between the last '/' and the first '.' after it */
static int hero_heart(Ctx *c, uint64_t name) {
    char s[128];
    size_t n = 0;
    for (; n < sizeof s; n++)
        if (!(s[n] = (char)recomp_load8(c, name + n))) break;
    if (n == sizeof s) return 0;   /* (longer than any actor path: not a heart) */
    const char *base = strrchr(s, '/');
    base = base ? base + 1 : s;
    const size_t len = strcspn(base, ".");
    for (size_t i = 0; i < sizeof hero_hearts / sizeof *hero_hearts; i++)
        if (strlen(hero_hearts[i]) == len && !memcmp(base, hero_hearts[i], len)) return 1;
    return 0;
}

void hos_oot_drops(Ctx *c, uint64_t list) {
    if (!list || rx_option(HOS_OPT_HERO_MODE, 0) != 1) return;
    const int32_t n = (int32_t)recomp_load32(c, list), cap = (int32_t)recomp_load32(c, list + 4);
    const uint64_t slots = recomp_load64(c, list + 8);
    if (n <= 0 || n > cap || !slots) return;
    int32_t kept = 0;
    for (int32_t i = 0; i < n; i++) {
        const uint64_t drop = recomp_load64(c, slots + 8 * (uint64_t)i);
        const uint64_t name = drop ? recomp_load64(c, drop) : 0;
        if (name && hero_heart(c, name)) {
            recomp_store64(c, drop, recomp_load64(c, list + 16));   /* (its slot back to the free ones) */
            recomp_store64(c, list + 16, drop);
            continue;
        }
        if (kept != i) recomp_store64(c, slots + 8 * (uint64_t)kept, drop);
        kept++;
    }
    if (kept != n) recomp_store32(c, list, (uint32_t)kept);
}
