/* (hookshot) Mouse look's game-agnostic part: what turns a mouse's counts into a camera's degrees, with no game memory, no
   operating system and no Longshot header. Plain values in, plain values out, so another runtime that hooks the same
   cameras (another recomp, an emulator's patch) can take this file as it is. host/mouse_native.c is Longshot's glue: where
   the angles live in the game, the hooks, the options, the log.

   The conventions are the game's player cameras' (Switch 2 Ocarina of Time): yaw falls as the view turns right, pitch
   rises as it tilts down, both in degrees; the right stick's own turn has the same signs. */
#ifndef MOUSE_LOOK_H
#define MOUSE_LOOK_H

#include <stdint.h>

/* Degrees a count at sensitivity 1 (the menu's Mouse sensitivity 1.00) */
#define ML_DEG_PER_COUNT 0.1

/* Degrees per count for a sensitivity and an extra scale (1 for the camera, the aim's own for the aims) */
double ml_degrees_per_count(double sensitivity, double scale);

/* The turn of a motion of dx counts (right positive) and dy counts (toward the player positive) at k degrees a count:
   the yaw's, which falls as the mouse goes right, and the pitch's, which rises as it comes toward the player unless
   inverted */
float ml_yaw_by(int32_t dx, double k);
float ml_pitch_by(int32_t dy, double k, int invert);

/* An angle within -180 (in) and 180 (out), as the game's f_80746430; a non-finite angle as it is */
float ml_wrap180(float a);

/* v cut to lo..hi (lo <= hi) */
float ml_clamp(float v, float lo, float hi);

/* The pitch of a direction (x, y, z; y up) as the game's f_80738800 gives it: 90 - atan2(its length across, its height),
   level 0, rising as it points up. 0 when the direction is too short to have one */
int ml_pitch_of_vector(float x, float y, float z, float *pitch);

/* A camera that draws its pitch as pitch + (1 - t) * offset, t easing from 0 to 1 after another camera (the follow
   camera's view blend), started from pitch_in with offset_in. The offset that keeps the drawn start where it was once
   the pitch becomes `pitch`: so changing the pitch at that moment does not add a jump on top of the game's own blend */
float ml_blend_offset_kept(float pitch_in, float offset_in, float pitch);

/* A frame's motion shared by two calls, one per axis (the yaw's and the pitch's turn functions): the first call adds
   what the mouse moved, each takes its own axis, and what nobody takes within keep_ns is dropped, so a motion of long ago
   does not turn a camera that starts asking later */
typedef struct {
    int32_t x, y;   /* (counts taken from the mouse and not yet asked for) */
    int64_t ns;     /* (when counts were last added) */
} ml_latch;
void ml_latch_add(ml_latch *l, int64_t now_ns, int64_t keep_ns, int32_t dx, int32_t dy);
int32_t ml_latch_take(ml_latch *l, int axis);   /* (axis 0 the x counts, 1 the y counts; they are cleared) */

#endif
