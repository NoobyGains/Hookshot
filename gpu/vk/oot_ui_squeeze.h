// (hookshot, nx2/oot_wide.py) OoT's 2D canvas projections, squeezed into the window's middle 16:9 at each draw.
// The game computes a canvas's projection once, when its layout is made, so the canvas setup site alone cannot follow
// a window resized later. That site marks each canvas it squeezes: m00 x (1 + 2^-16). The full-screen canvases
// (KEEP_VTABLES: captures of the whole picture, fades) keep exactly 2/3840 and are left alone here as well.
// A canvas's vertex block (0x90 bytes: the projection, the same one flipped, then 3840 2160 3840 2160) gets the
// projection for the window's shape now: m00 x 1/shape on a wider window, m11 x shape on a narrower one. Both axes are
// written from the grid's constants, so a block squeezed once is squeezed again to the same values.
// Plain C: nx2/test_oot_wide.py compiles it as it is.
#pragma once
#include <string.h>

#define OOT_UI_BLOCK_BYTES 0x90
#define OOT_UI_MARK (1.0f + 1.0f / 65536.0f)
static inline int oot_ui_squeeze(unsigned char* bytes, unsigned long long n, float window_aspect) {
    if (n != OOT_UI_BLOCK_BYTES || !(window_aspect > 0.0f)) return 0;
    float f[36];
    memcpy(f, bytes, sizeof f);
    if (f[32] != 3840.0f || f[33] != 2160.0f || f[34] != 3840.0f || f[35] != 2160.0f) return 0;
    for (int m = 0; m <= 16; m += 16)
        if (f[m + 1] != 0.0f || f[m + 2] != 0.0f || f[m + 3] != 0.0f || f[m + 4] != 0.0f || f[m + 6] != 0.0f ||
            f[m + 7] != 0.0f || f[m + 12] != 0.0f || f[m + 13] != 0.0f || f[m + 15] != 1.0f || !(f[m] > 0.0f) ||
            f[m + 5] == 0.0f)
            return 0;
    const float grid_x = 2.0f / 3840.0f, grid_y = 2.0f / 2160.0f;
    if (f[0] == grid_x) return 0;   // (unmarked: a full-screen canvas, or one the setup site never saw)
    const float r = f[0] / grid_x;
    if (!(r > 0.1f && r < 1.0f + 1.0f / 4096.0f)) return 0;
    const float shape = window_aspect / (16.0f / 9.0f);
    const float qx = shape > 1.0f ? 1.0f / shape : 1.0f, qy = shape < 1.0f ? shape : 1.0f;
    for (int m = 0; m <= 16; m += 16) {
        f[m] = grid_x * qx * OOT_UI_MARK;
        f[m + 5] = (f[m + 5] < 0.0f ? -grid_y : grid_y) * qy;

    }
    memcpy(bytes, f, sizeof f);
    return 1;
}
