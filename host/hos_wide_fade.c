/* Window's centred loading canvas: fill only its spanning fade pane, not its icon.
   Size hook and layout fields from llun's #95 (7cedec2d), based on ozwaldorf's
   pane work. Whichever of #95/#142 lands second removes this #142 bridge and
   uses #95's size hook, so the combined build never resizes the pane twice. */
#include "hos.h"
#include <math.h>
#include <string.h>

extern int hos_wide_window;
extern volatile uint32_t hos_wide_keep_mask;
float hos_wide_aspect(void);

static float fade_float(Ctx *c, uint64_t address) {
    const uint32_t bits = (uint32_t)recomp_load32(c, address);
    float value;
    memcpy(&value, &bits, sizeof value);
    return value;
}

/* f_8154ac30 has just loaded the authored width/height into s0/s1. Changing
   only these lanes leaves guest dimensions and the icon's transform untouched. */
void hos_wide_fade_size(Ctx *c, uint64_t pane) {
    if (!hos_wide_window || (hos_wide_keep_mask & 8u)) return;
    const float shape = hos_wide_aspect() / (16.0f / 9.0f);
    if (!(shape > 0.0f) || !isfinite(shape) || shape == 1.0f) return;
    float width, height;
    memcpy(&width, c->vreg[0], 4);
    memcpy(&height, c->vreg[1], 4);
    const float x = fade_float(c, pane + 0x4c), y = fade_float(c, pane + 0x50);
    const float w = width * fabsf(fade_float(c, pane + 0x28));
    const float h = height * fabsf(fade_float(c, pane + 0x38));
    const uint32_t flags = (uint32_t)recomp_load32(c, pane + 0xa8);
    /* A centred picture covering the 3840x2160 canvas, not a container, icon,
       text or capture. The 40-unit edge tolerance is #95's spanning-pane rule. */
    /* The origin field packs base-3 anchors. Its higher trits are not X/Y:
       the game's loading pane uses 40, which is centre/centre just like 4. */
    const uint32_t origin = (flags >> 11) & 0x7f;
    if (((flags >> 22) & 0xf) != 1 || origin % 3 != 1 || origin / 3 % 3 != 1 ||
        !(fabsf(x) <= 1.0f && fabsf(y) <= 1.0f && w >= 3760.0f && h >= 2080.0f)) return;
    const uint64_t layout = recomp_load64(c, pane + 0x18);
    const uint64_t resource = layout ? recomp_load64(c, layout + 0xf8) : 0;
    const uint64_t name = resource ? recomp_load64(c, resource + 0x18) : 0;
    if (!name) return;
    static const char loading[] = "LoadingFade_00";
    for (unsigned i = 0; i < sizeof loading; ++i)
        if (recomp_load8(c, name + i) != (uint8_t)loading[i]) return;
    /* Invert only the squeezed axis. Event fades already have a whole-picture
       canvas (keep bit 2); Monitor and Full width retain their existing path. */
    if (shape > 1.0f) width *= shape;
    else height /= shape;
    memcpy(c->vreg[0], &width, 4);
    memcpy(c->vreg[1], &height, 4);
}
