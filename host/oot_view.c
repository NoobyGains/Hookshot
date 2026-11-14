/* The Graphics tab's View distance, Grass and Shadow distance rows (live).

   nx2/oot_view.py calls hos_oot_view at the head of the game's render setup (f_831f3200, main+0x31d3200), once a frame.
   Each row is a step, not a slider; the step's factor multiplies the game's own value, which is kept per object and taken
   again whenever the game writes it, so nothing compounds and Original gives the game's value back. While every row sits
   on Original and none has moved since the start, the game is never touched.

   Where the values live (the object chains, their vtables and offsets) was found by hotoni (the Graphics-Menu mod for the
   Switch 2 game); this code came to Hookshot from Ocarina Reborn (misterrageguy-cyber), with the model detail and the
   character shadows scaled from the game's own values too, where Reborn wrote fixed ones. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"
#include <string.h>

int rx_option(int id, int otherwise);

#define G(off) (0x80020000ULL + (off))   /* main's base in this image */

/* one game float we scale: where it is, the game's own value and ours */
typedef struct { uint64_t at; float game, ours; } Knob;

static float rd(Ctx *c, uint64_t a) { uint32_t u = (uint32_t)recomp_load32(c, a); float f; memcpy(&f, &u, 4); return f; }
static void wr(Ctx *c, uint64_t a, float f) { uint32_t u; memcpy(&u, &f, 4); recomp_store32(c, a, u); }

/* the object a slot points at, when it is the kind expected (its vtable) */
static uint64_t obj(Ctx *c, uint64_t slot, uint64_t vtable) {
    if (!slot) return 0;
    const uint64_t o = recomp_load64(c, slot);
    return o && recomp_load64(c, o) == vtable ? o : 0;
}

static void apply(Ctx *c, Knob *k, uint64_t at, float factor) {
    if (!at) { k->at = 0; return; }
    const float now = rd(c, at);
    if (k->at != at || now != k->ours) k->at = at, k->game = now;   /* a new object, or the game wrote it */
    k->ours = k->game * factor;
    if (now != k->ours) wr(c, at, k->ours);
}

static const float VIEW[] = {0.75f, 1.0f, 1.5f, 2.0f, 2.5f};   /* Short, Original, Far, Very far, Max */
static const float GRASS[] = {0.0f, 0.5f, 1.0f, 1.5f, 2.0f};   /* Off, Less, Original, More, Dense */
static const float SHADOW[] = {0.5f, 1.0f, 2.0f, 3.0f};        /* Short, Original, Far, Max */

static Knob foliage[2][8], grass, lod[3], char_shadow[2], shadow_far;
static int touched;

static int step(int v, int hi) { return v < 0 ? 0 : v > hi ? hi : v; }

void hos_oot_view(Ctx *c) {
    const int v = step(rx_option(HOS_OPT_VIEW_DISTANCE, 1), 4), g = step(rx_option(HOS_OPT_GRASS, 2), 4),
              s = step(rx_option(HOS_OPT_SHADOW_DISTANCE, 1), 3);
    if (!touched && v == 1 && g == 2 && s == 1) return;
    touched = 1;   /* (from now on Original writes the game's own values back where ours differ) */
    const float fv = VIEW[v], fg = GRASS[g], fs = SHADOW[s];
    const float detail = fv < 1.0f ? 1.0f : fv;   /* (models never coarser than the game's) */

    /* the foliage: two parameter blocks of 8 distances each, and the grass's density */
    uint64_t o = obj(c, G(0x4e22540), G(0x4b24800));
    o = o ? obj(c, o + 0xf0, G(0x4b24a70)) : 0;
    o = o ? obj(c, o + 0x2a90, G(0x4bf9010)) : 0;
    o = o ? obj(c, o + 0x150, G(0x4b23228)) : 0;
    for (int b = 0; b < 2; b++) {
        const uint64_t p = o ? obj(c, o + 0x40 + 8 * b, G(0x4b235d0)) : 0;
        for (int i = 0; i < 8; i++) apply(c, &foliage[b][i], p ? p + 0x38 + 4 * i : 0, fv);
    }
    apply(c, &grass, o ? o + 0x68 : 0, fg);

    /* the scene renderer: model detail, the characters' shadows (the game's 30 m and 25 m), the scenery shadow's reach
       (the game's 160 m) */
    const uint64_t scene = obj(c, G(0x4e3e258), G(0x4b895b0));
    const uint64_t r = scene ? obj(c, scene + 0x1e8, G(0x4b8bc00)) : 0;
    uint64_t h = r ? obj(c, r + 0xd50, G(0x4bf9010)) : 0;
    const uint64_t lp = h ? obj(c, h + 0x150, G(0x4b87a88)) : 0;
    for (int i = 0; i < 3; i++) apply(c, &lod[i], lp ? lp + 0x48 + 4 * i : 0, detail);
    const uint64_t ch = r ? obj(c, r + 0xba8, G(0x4b8a3e8)) : 0;
    h = ch ? obj(c, ch + 0xc18, G(0x4bf9010)) : 0;
    const uint64_t cp = h ? obj(c, h + 0x150, G(0x4b86828)) : 0;
    for (int i = 0; i < 2; i++) apply(c, &char_shadow[i], cp ? cp + 0x90 + 4 * i : 0, fs);
    const uint64_t sh = r ? obj(c, r + 0xb30, G(0x4b8a0a8)) : 0;
    apply(c, &shadow_far, sh ? sh + 0xb4 : 0, fs);
}
