/* (hookshot) Mouse look's game-agnostic part (mouse_look.h): only <math.h> and <stdint.h>. */
#include "mouse_look.h"

#include <math.h>

double ml_degrees_per_count(double sensitivity, double scale) { return ML_DEG_PER_COUNT * sensitivity * scale; }

float ml_yaw_by(int32_t dx, double k) { return (float)(-dx * k); }

float ml_pitch_by(int32_t dy, double k, int invert) { return (float)((invert ? -dy : dy) * k); }

float ml_wrap180(float a) {
    if (!isfinite(a)) return a;
    while (a >= 180.0f) a -= 360.0f;
    while (a < -180.0f) a += 360.0f;
    return a;
}

float ml_clamp(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }

int ml_pitch_of_vector(float x, float y, float z, float *pitch) {
    const float across = sqrtf(x * x + z * z);
    if (!isfinite(across) || !isfinite(y) || across * across + y * y < 1e-6f) return 0;
    *pitch = 90.0f - atan2f(across, y) * (180.0f / 3.14159265358979f);
    return 1;
}

float ml_blend_offset_kept(float pitch_in, float offset_in, float pitch) {
    return ml_wrap180(pitch_in + offset_in - pitch);
}

void ml_latch_add(ml_latch *l, int64_t now_ns, int64_t keep_ns, int32_t dx, int32_t dy) {
    if (now_ns - l->ns > keep_ns) l->x = l->y = 0;
    if (dx || dy) l->x += dx, l->y += dy, l->ns = now_ns;
}

int32_t ml_latch_take(ml_latch *l, int axis) {
    int32_t *at = axis == 0 ? &l->x : &l->y;
    const int32_t v = *at;
    *at = 0;
    return v;
}
