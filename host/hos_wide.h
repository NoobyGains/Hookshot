/* Window-shaped picture geometry, independent of the host window API. */
#ifndef HOS_WIDE_H
#define HOS_WIDE_H
#include <stdint.h>
#include <math.h>
#include "hos_wide_size.h"

typedef struct HosWideSize {
    uint64_t picture, scene;
    float aspect;
} HosWideSize;

static inline HosWideSize hos_wide_picture_size(double aspect, unsigned output_height) {
    HosWideSize size = {0, 0, 0};
    if (!(aspect > 0) || !isfinite(aspect) || !output_height) return size;
    aspect = hos_wide_clamp(aspect);
    /* Hor+ grows width; Vert+ grows height. Do not shrink either axis below
       the selected 16:9 output's dimensions (before the pixel cap): the
       fixed upscaler's network is still configured with those minimum sizes. */
    unsigned oh = output_height;
    unsigned ow = (unsigned)(output_height * (16.0 / 9.0) / 8 + 0.5) * 8;
    if (aspect < 16.0 / 9.0) oh = (unsigned)(ow / aspect / 8 + 0.5) * 8;
    else ow = (unsigned)(oh * aspect / 8 + 0.5) * 8;
    /* Upstream's render-target pool guard (issue 1031): cap pixels, not shape. */
    if ((double)ow * oh > hos_wide_max_px()) {
        oh = (unsigned)(sqrt(hos_wide_max_px() / aspect) / 8) * 8;
        ow = (unsigned)(oh * aspect / 8) * 8;
    }
    const unsigned sh = oh * 3 / 4;   /* preserve the shipped 4K scene height (1620), too */
    const unsigned sw = (unsigned)(ow * 0.75 / 8 + 0.5) * 8;
    size.picture = (uint64_t)oh << 32 | ow;
    size.scene = (uint64_t)sh << 32 | sw;
    /* Use the window, not its rounded render target, for projection and HUD. */
    size.aspect = (float)aspect;
    return size;
}

static inline HosWideSize hos_wide_window_size(unsigned width, unsigned height, unsigned output_height) {
    return hos_wide_picture_size(height ? (double)width / height : 0, output_height);
}

/* The originals survive repeated matrix updates and window changes. The game
   also reads these fields for culling, so the caller stores the result back. */
typedef struct HosWideProjection {
    int valid;
    float original_tangent, patched_tangent, patched_aspect;
} HosWideProjection;

static inline int hos_wide_perspective(HosWideProjection *view, float want, float *tangent, float *aspect) {
    const float game = 16.0f / 9.0f;
    if (!(want > 0.0f)) return 0;
    if (fabsf(*aspect - game) > 0.01f &&
        !(view->valid && *aspect == view->patched_aspect)) {
        view->valid = 0;
        return 0;
    }
    if (!view->valid || *tangent != view->patched_tangent) view->original_tangent = *tangent;
    *tangent = view->original_tangent * (want < game ? game / want : 1.0f);
    *aspect = want;
    view->patched_tangent = *tangent;
    view->patched_aspect = want;
    view->valid = 1;
    return 1;
}

extern int hos_wide_window;
float hos_wide_aspect(void);
float hos_wide_thumb_ratio(void);
void hos_wide_start(unsigned width, unsigned height);
void hos_wide_resize(unsigned width, unsigned height);
int hos_wide_projection(uint64_t projection, float *tangent, float *aspect);
#endif
