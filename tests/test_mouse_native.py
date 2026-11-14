"""Native mouse look turns the player camera's own angles and holds them there (host/mouse_native.c).

The file is compiled on its own against a fake guest memory that holds a player camera: its pitch limits at +0x178, its
pitch at +0x18c, its yaw at +0x1a4 and its state at +0x204. hos_mouse_camera is what the camera's update (f_80644c80,
nx2/oot_patches.py) calls each frame. Until it has run the mouse's motion is the right stick's (hos_mouse_native gives
-1); then it turns yaw and pitch by 0.1 degrees a count at sensitivity 1, pitch kept within the limits and yaw wrapped at
180, up and down swapped with the menu's Invert mouse vertical (option 8), and the controller reads leave the motion to
the camera. The game eases the angles back toward Link's by itself inside a frame (its follow camera): the mouse's angles
are put back every frame, so the view does not drift, and a move adds to the mouse's angles, not to the game's. The game's
own right stick is let through (hos_mouse_native_stick: the camera's keys, a pad): its angles become the mouse's new
start. Without the menu's Mouse camera (option 6), or on an object that is not a camera, it does nothing. The game gives
the camera free control only in its states 3 (it follows Link, the right stick takes it over) and 4 (the player's), and
while no button it takes the right stick for is held (ZR, the bow's aim; L, the item wheel; R: hos_mouse_native_free);
150 ms without the camera (the pause menu, another camera) give the motion back to the stick as well.

The player camera's other nodes are covered the same way. The aiming node (hos_mouse_aim): the mouse's degrees go into
its pitch, its goals and the shared yaw, within its limits and wrapped, inverted with option 8, dropped while the shared
flags make the game take no turn, left to the stick while the item wheel is open; ZR waits for the node's first update
and drops what waited when none comes; the aim begins at the view's pitch (+0x198), and with Disable camera centering
(option 45) the follow camera starts from where the aim looked, its pitch kept apart from the view's by what the two
differed by as the aim began (the view's pitch: the aim's plus its blend, or its direction's, shared +0x450 less +0x45c). The turn functions (hos_mouse_turn): one frame's motion
split over the two axes, an axis nobody asks for within 100 ms dropped. The locked-on aim (hos_mouse_lock_aim): the
offsets and the view's own angles turn together, cut to the game's limits, dropped while the game masks the stick.
Z-targeting (hos_mouse_lockon): in the node's mode of the player (1) the mouse's degrees go into the yaw's offset at +0xec
and the pitch at +0xd8 and are given back for the game's turn; in the other modes the mouse stays the right stick.
python -I -B tests/test_mouse_native.py   (Windows: the compiler's windows.h; Linux: host/posix's)
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# (env_on, the switches' rule, before the code cut out of the sources: gpu/vk/compat/hookshot_env.h)
ENV_ON_H = str(Path(__file__).resolve().parents[1] / "gpu" / "vk" / "compat" / "hookshot_env.h")

ROOT = Path(__file__).resolve().parents[1]

HOS_H = r"""
#pragma once
#include <stdint.h>
#include <stddef.h>
extern uint8_t *fake_heap;
#define HOS_HEAP_BASE 0x1000000000ULL
#define GP(a) ((void *)(fake_heap + ((uint64_t)(a) - HOS_HEAP_BASE)))
extern uint64_t hos_heap_size;
void hos_log(const char *fmt, ...);
int64_t hos_now_ns(void);
"""

FIXTURE = r"""
#include "hos.h"
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
uint8_t *fake_heap;
uint64_t hos_heap_size = 64 * 4096;
double hos_mouse_sens = 1.0;
static int64_t clock_ns = 1000000000LL;
void hos_log(const char *fmt, ...) { va_list a; va_start(a, fmt); vfprintf(stderr, fmt, a); va_end(a); fputc(10, stderr); }
int64_t hos_now_ns(void) { return clock_ns; }
static int32_t move_x, move_y;
static int captured = 1, menu_invert, menu_native = 1, opt45;
int rx_option(int id, int otherwise) { return id == 8 ? menu_invert : id == 6 ? menu_native : id == 45 ? opt45 : otherwise; }
int hos_mouse_take(int32_t *dx, int32_t *dy) { *dx = move_x, *dy = move_y; move_x = move_y = 0; return captured; }
void hos_mouse_give_back(int32_t dx, int32_t dy) { move_x += dx, move_y += dy; }
int hos_mouse_native(void);
void hos_mouse_native_free(int free);
void hos_mouse_native_held(int zr, int wheel);
void hos_mouse_native_stick(int held);
void hos_mouse_camera(uint64_t camera);
static const uint64_t CAM = HOS_HEAP_BASE + 10 * 4096 + 0x40, CAM2 = HOS_HEAP_BASE + 30 * 4096 + 0x40,
                      OTHER = HOS_HEAP_BASE + 20 * 4096;
static float getf(uint64_t a) { float f; memcpy(&f, GP(a), 4); return f; }
static void putf(uint64_t a, float f) { memcpy(GP(a), &f, 4); }
static void puti(uint64_t a, int32_t v) { memcpy(GP(a), &v, 4); }
static int fails;
#define PITCH (CAM + 0x18c)
#define YAW (CAM + 0x1a4)
static void state(uint32_t v) { memcpy(GP(CAM + 0x204), &v, 4); }
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s (pitch %g yaw %g)\n", __LINE__, #c, getf(PITCH), getf(YAW)); fails++; } } while (0)
/* (near_f: Windows' headers define near) */
static int near_f(float a, float b) { return fabsf(a - b) < 1e-3f; }
static void frame(int32_t dx, int32_t dy) { move_x += dx, move_y += dy; clock_ns += 16666667; hos_mouse_camera(CAM); }
/* (the camera's angles become the mouse's start: a stick turn of the game's own, or a camera put somewhere by hand) */
static void seed(void) { hos_mouse_native_stick(1); frame(0, 0); hos_mouse_native_stick(0); }
static void seed_at(float pitch, float yaw) { putf(PITCH, pitch), putf(YAW, yaw); seed(); }
int main(void) {
    fake_heap = (uint8_t *)calloc(72, 4096);
    putf(CAM + 0x178, -85), putf(CAM + 0x17c, 89);
    puti(CAM + 0x204, 3);
    putf(PITCH, 10), putf(YAW, 30);
    state(4);   /* turned by the player */
    move_x = 5, move_y = 3;
    CHECK(hos_mouse_native() == -1);   /* no camera has run yet: the stick takes it */
    move_x = move_y = 0;
    frame(10, 4);
    CHECK(near_f(getf(YAW), 29.0f) && near_f(getf(PITCH), 10.4f));   /* right: yaw falls; down: pitch rises */
    move_x = 3;
    CHECK(hos_mouse_native() == 1 && move_x == 3);   /* the camera's now: the motion stays for it */
    move_x = 0;
    /* the game's follow camera inside a frame: it eases the pitch and turns the yaw by itself; the mouse's angles are put back */
    putf(YAW, 12), putf(PITCH, 4);
    frame(0, 0);
    CHECK(near_f(getf(YAW), 29.0f) && near_f(getf(PITCH), 10.4f));   /* no drift back toward Link */
    putf(YAW, -40), putf(PITCH, 40);
    frame(4, 0);
    CHECK(near_f(getf(YAW), 28.6f) && near_f(getf(PITCH), 10.4f));   /* a move adds to the mouse's angles, not the game's */
    frame(0, 100000);
    CHECK(near_f(getf(PITCH), 89.0f));   /* kept within the limits */
    seed_at(0, 0);
    frame(0, -100000);
    CHECK(near_f(getf(PITCH), -85.0f));
    seed_at(0, -179.5f);
    frame(10, 0);
    CHECK(near_f(getf(YAW), 179.5f));   /* wrapped */
    seed_at(0, 0);
    menu_invert = 1;   /* the menu's Invert mouse vertical: down tilts up */
    frame(0, 10);
    CHECK(near_f(getf(PITCH), -1.0f));
    menu_invert = 0;
    /* the game's own right stick (the camera's keys, a pad): its angles are the mouse's new start, and it still turns */
    putf(YAW, 70), putf(PITCH, 30);
    seed();
    CHECK(near_f(getf(YAW), 70.0f) && near_f(getf(PITCH), 30.0f));
    frame(-10, 0);
    CHECK(near_f(getf(YAW), 71.0f));
    /* another camera: its own angles are the start, not the last camera's */
    putf(CAM2 + 0x178, -85), putf(CAM2 + 0x17c, 89), puti(CAM2 + 0x204, 3);
    putf(CAM2 + 0x18c, -20), putf(CAM2 + 0x1a4, 100);
    move_x = 0;
    clock_ns += 16666667;
    hos_mouse_camera(CAM2);
    CHECK(near_f(getf(CAM2 + 0x18c), -20.0f) && near_f(getf(CAM2 + 0x1a4), 100.0f));
    clock_ns += 16666667;
    hos_mouse_camera(CAM2);
    CHECK(near_f(getf(CAM2 + 0x18c), -20.0f) && near_f(getf(CAM2 + 0x1a4), 100.0f));
    putf(OTHER + 0x18c, NAN);   /* (no limits, no angles: not a camera) */
    move_x = 50;
    hos_mouse_camera(OTHER);
    CHECK(move_x == 50 && isnan(getf(OTHER + 0x18c)));
    move_x = 0;
    menu_native = 0;   /* the menu's Mouse camera off: the hook does nothing */
    putf(YAW, 0);
    frame(10, 0);
    CHECK(near_f(getf(YAW), 0.0f));
    menu_native = 1;
    seed_at(10, 30);
    /* the game's own state: only 3 (it follows Link) and 4 (the player's) turn with the mouse */
    puti(CAM + 0x204, 1);
    putf(YAW, 0);
    move_x = 10;
    hos_mouse_camera(CAM);
    CHECK(move_x == 10 && near_f(getf(YAW), 0.0f));   /* (a lock-on, a menu, first person: the right stick's) */
    CHECK(hos_mouse_native() == -1);
    move_x = 0;
    puti(CAM + 0x204, 3);
    /* a button the game takes the stick for (ZR, the bow's aim; L, the item wheel; R): the game's camera too */
    hos_mouse_native_free(0);
    putf(YAW, 5);
    move_x = 10;
    hos_mouse_camera(CAM);
    CHECK(move_x == 10 && near_f(getf(YAW), 5.0f));
    CHECK(hos_mouse_native() == -1);
    hos_mouse_native_free(1);
    move_x = 0;
    captured = 0;
    CHECK(hos_mouse_native() == 0);   /* not captured: nothing */
    captured = 1;
    clock_ns += 200000000LL;   /* no camera for 200 ms (the pause menu): the stick again */
    CHECK(hos_mouse_native() == -1);
    /* aiming in first person (the slingshot): the camera keeps updating, state 0, another draws: the stick takes it */
    for (uint32_t resumed = 3; resumed <= 4; resumed++) {
        state(4);
        frame(0, 0);   /* the camera's a moment ago (the hook ran: hos_mouse_native would give 1 for 150 ms) */
        state(0);
        putf(YAW, 0), putf(PITCH, 20);
        frame(10, 5);
        CHECK(near_f(getf(YAW), 0.0f) && near_f(getf(PITCH), 20.0f) && move_x == 10 && move_y == 5);
        CHECK(hos_mouse_native() == -1);   /* at once, not 150 ms later */
        move_x = move_y = 0;
        state(resumed);   /* following Link or turned by the player: start at the game's current angles */
        frame(10, 5);
        CHECK(near_f(getf(YAW), -1.0f));
        CHECK(near_f(getf(PITCH), 20.5f));
        CHECK(hos_mouse_native() == 1);
    }
    /* the mouse released (capture off): the game's camera is left alone, and the next captured frame starts from it */
    state(4);
    seed_at(10, 30);
    frame(0, 0);
    captured = 0;
    putf(YAW, 10);   /* (the game's follow camera turns it) */
    frame(0, 0);
    CHECK(near(getf(YAW), 10.0f));
    captured = 1;
    frame(-10, 0);
    CHECK(near(getf(YAW), 11.0f));   /* from the game's 10, not the mouse's old 30 */

    /* ---- the aiming camera ---- */
    {
        void hos_mouse_aim(uint64_t node);
        void hos_mouse_native_held(int zr, int wheel);
        const uint64_t NODE = HOS_HEAP_BASE + 40 * 4096 + 0x40, SH = HOS_HEAP_BASE + 50 * 4096;
        uint64_t sh = SH; memcpy(GP(NODE + 0x20), &sh, 8);
        putf(NODE + 0x224, -60), putf(NODE + 0x228, 70);
        putf(NODE + 0x194, 10), putf(NODE + 0x18c, 10), putf(NODE + 0x190, 30), putf(SH + 0x52c, 30);
        clock_ns += 1000000000LL; move_x = move_y = 0;
        CHECK(hos_mouse_native() == -1);                      /* nothing live: the stick */
        hos_mouse_native_held(1, 0);                          /* ZR goes down */
        move_x = 7;
        CHECK(hos_mouse_native() == 1 && move_x == 7);        /* the motion waits for the aiming camera */
        clock_ns += 16666667; move_y = 4; move_x = 10;
        hos_mouse_aim(NODE);
        CHECK(move_x == 0 && near_f(getf(SH + 0x52c), 29.0f) && near_f(getf(NODE + 0x190), 29.0f));
        CHECK(near_f(getf(NODE + 0x194), 10.4f) && near_f(getf(NODE + 0x18c), 10.4f));
        CHECK(hos_mouse_native() == 1);
        /* the follow camera in the same frame leaves the motion alone while the game aims */
        state(4); putf(YAW, 0); move_x = 10; clock_ns += 1000; hos_mouse_camera(CAM);
        CHECK(move_x == 10 && near_f(getf(YAW), 0.0f));
        hos_mouse_aim(NODE);
        CHECK(near_f(getf(SH + 0x52c), 28.0f));
        move_y = 100000; hos_mouse_aim(NODE);
        CHECK(near_f(getf(NODE + 0x194), 70.0f) && near_f(getf(NODE + 0x18c), 70.0f));   /* the limits */
        move_y = -100000; hos_mouse_aim(NODE);
        CHECK(near_f(getf(NODE + 0x194), -60.0f));
        putf(SH + 0x52c, -179.5f); putf(NODE + 0x190, -179.5f); move_x = 10; hos_mouse_aim(NODE);
        CHECK(near_f(getf(SH + 0x52c), 179.5f) && near_f(getf(NODE + 0x190), 179.5f));   /* wrapped */
        menu_invert = 1; putf(NODE + 0x194, 0); putf(NODE + 0x18c, 0); move_y = 10; hos_mouse_aim(NODE);
        CHECK(near_f(getf(NODE + 0x194), -1.0f)); menu_invert = 0;
        /* the game takes no turn: dropped */
        uint64_t fl = 1ULL << 30; memcpy(GP(SH + 0x218), &fl, 8);
        putf(SH + 0x52c, 0); move_x = 10; hos_mouse_aim(NODE);
        CHECK(move_x == 0 && near_f(getf(SH + 0x52c), 0.0f));
        fl = 0; memcpy(GP(SH + 0x218), &fl, 8);
        /* the item wheel: the mouse points (the stick) */
        hos_mouse_native_held(1, 1); hos_mouse_native_free(0); move_x = 10; hos_mouse_aim(NODE);
        CHECK(move_x == 10 && near_f(getf(SH + 0x52c), 0.0f) && hos_mouse_native() == -1);
        hos_mouse_native_held(1, 0); hos_mouse_native_free(1); move_x = 0;
        hos_mouse_aim(NODE); CHECK(hos_mouse_native() == 1);
        /* the aim ends: after 150 ms without the node and ZR up, the stick again (no camera here) */
        hos_mouse_native_held(0, 0); state(0); clock_ns += 16666667; hos_mouse_camera(CAM);
        clock_ns += 200000000LL;
        CHECK(hos_mouse_native() == -1);
        /* ZR with nothing to aim: what waited is dropped, not pushed into the stick */
        hos_mouse_native_held(1, 0); move_x = 50;
        CHECK(hos_mouse_native() == 1 && move_x == 50);
        clock_ns += 300000000LL;
        CHECK(hos_mouse_native() == -1 && move_x == 0);
        move_x = 5; CHECK(hos_mouse_native() == -1 && move_x == 5);
        hos_mouse_native_held(0, 0); move_x = 0;
        /* ZR held with the follow camera still the view: it keeps the mouse */
        hos_mouse_native_held(1, 0); state(4); seed_at(0, 0); frame(10, 0);
        CHECK(near_f(getf(YAW), -1.0f) && hos_mouse_native() == 1);
        hos_mouse_native_held(0, 0);
        /* not a node (garbage): untouched */
        putf(NODE + 0x194, NAN); move_x = 9; clock_ns += 400000000LL; hos_mouse_aim(NODE); CHECK(move_x == 9);
    }

    {   /* ---- the aim begins at the view's pitch; the follow camera keeps the aim's view ---- */
        void hos_mouse_aim(uint64_t node);
        const uint64_t N2 = HOS_HEAP_BASE + 60 * 4096 + 0x40, S2 = HOS_HEAP_BASE + 62 * 4096;
        uint64_t s2 = S2; memcpy(GP(N2 + 0x20), &s2, 8);
        clock_ns += 1000000000LL; move_x = move_y = 0;
        putf(N2 + 0x224, -60), putf(N2 + 0x228, 70);
        putf(N2 + 0x194, 4), putf(N2 + 0x18c, 4), putf(N2 + 0x198, 6), putf(N2 + 0x190, 40), putf(S2 + 0x52c, 40);
        hos_mouse_aim(N2);   /* the view was at 10: the game began the aim at 4 */
        CHECK(near_f(getf(N2 + 0x194), 10.0f) && near_f(getf(N2 + 0x18c), 10.0f) && near_f(getf(N2 + 0x198), 0.0f));
        putf(N2 + 0x194, 12); putf(N2 + 0x18c, 12); clock_ns += 16666667; hos_mouse_aim(N2);
        CHECK(near_f(getf(N2 + 0x194), 12.0f));   /* once an aim */
        putf(N2 + 0x194, 65), putf(N2 + 0x18c, 65), putf(N2 + 0x198, 10); hos_mouse_aim(N2);   /* a new aim, past the limit */
        CHECK(near_f(getf(N2 + 0x194), 70.0f) && near_f(getf(N2 + 0x198), 5.0f));
        putf(N2 + 0x194, 20), putf(N2 + 0x18c, 20), putf(N2 + 0x198, 0); move_x = 10; clock_ns += 16666667; hos_mouse_aim(N2);
        CHECK(near_f(getf(S2 + 0x52c), 39.0f));
        /* the aim ends: with Disable camera centering the follow camera starts from the aim's view */
        opt45 = 1; clock_ns += 100000000LL; state(4); putf(PITCH, 0), putf(YAW, 0); move_x = 0; hos_mouse_camera(CAM);
        CHECK(near_f(getf(YAW), 39.0f) && near_f(getf(PITCH), 20.0f));   /* (no view to measure: the aim's pitch as it is) */
        /* the follow camera's pitch is not the view's (it circles Link and looks at a point of its own): what they
           differed by as the aim began is given back when it ends, so an aim begun and ended with no motion leaves the
           view where it was instead of flicking it up */
        clock_ns += 1000000000LL; state(4); seed_at(25, 40);
        putf(N2 + 0x194, 4), putf(N2 + 0x18c, 4), putf(N2 + 0x198, 6), putf(S2 + 0x52c, 40);
        clock_ns += 16666667; hos_mouse_aim(N2);   /* the view's pitch 10 (4 and the blend's 6); the follow camera at 25 */
        CHECK(near_f(getf(N2 + 0x194), 10.0f));
        clock_ns += 100000000LL; putf(PITCH, 0); hos_mouse_camera(CAM);   /* the game put it back behind Link */
        CHECK(near_f(getf(PITCH), 25.0f) && near_f(getf(YAW), 40.0f));
        /* with no blend (the aim took back its last pitch) the view's pitch is its direction's, as f_80738800 gives it:
           shared +0x450 less +0x45c, here (0, 1, 1), 45 degrees */
        {
            const uint64_t N4 = HOS_HEAP_BASE + 64 * 4096 + 0x40, S4 = HOS_HEAP_BASE + 66 * 4096;
            uint64_t s4 = S4; memcpy(GP(N4 + 0x20), &s4, 8);
            putf(N4 + 0x224, -60), putf(N4 + 0x228, 70);
            putf(S4 + 0x450, 0), putf(S4 + 0x454, 1), putf(S4 + 0x458, 1);
            clock_ns += 1000000000LL; state(4); seed_at(50, 40);
            putf(N4 + 0x194, 20), putf(N4 + 0x18c, 20), putf(N4 + 0x198, 0), putf(N4 + 0x190, 40), putf(S4 + 0x52c, 40);
            clock_ns += 16666667; hos_mouse_aim(N4);
            CHECK(near_f(getf(N4 + 0x194), 20.0f));   /* (the aim's own pitch is left alone) */
            clock_ns += 100000000LL; putf(PITCH, 0); hos_mouse_camera(CAM);
            CHECK(near_f(getf(PITCH), 25.0f));   /* 20 and the 5 the follow camera (50) was above the view (45) */
            /* and cut to the follow camera's limits (-85, 89) */
            clock_ns += 1000000000LL; seed_at(88, 40);
            putf(N4 + 0x194, 60), putf(S4 + 0x458, 2);   /* (a new view: (0, 1, 2) is 26.57 degrees) */
            uint64_t n5 = N4 + 0x400; memcpy(GP(n5 + 0x20), &s4, 8);
            putf(n5 + 0x224, -60), putf(n5 + 0x228, 70), putf(n5 + 0x194, 60), putf(n5 + 0x18c, 60), putf(n5 + 0x198, 0);
            clock_ns += 16666667; hos_mouse_aim(n5);   /* a new node: a new aim; 88 - 26.57 above the view */
            clock_ns += 100000000LL; putf(PITCH, 0); hos_mouse_camera(CAM);
            CHECK(near_f(getf(PITCH), 89.0f));
        }
        /* the aim's end is kept from the very next frame, not after the aim's 50 ms yield (three frames of the game's
           recentring first: a flick up and back, seen in play); the motion of that frame still waits for the aim */
        clock_ns += 1000000000LL; state(4); seed_at(10, 40);
        putf(N2 + 0x194, 30), putf(N2 + 0x18c, 30), putf(N2 + 0x198, 0), putf(S2 + 0x52c, 50);
        clock_ns += 16666667; hos_mouse_aim(N2);   /* the aim's last frame, at 30 */
        move_x = 7; clock_ns += 16666667; putf(PITCH, -20), putf(YAW, 0); hos_mouse_camera(CAM);   /* the next frame */
        CHECK(near_f(getf(PITCH), 30.0f) && near_f(getf(YAW), 50.0f) && move_x == 7);
        move_x = 0; clock_ns += 16666667; putf(PITCH, -20); hos_mouse_camera(CAM);
        CHECK(near_f(getf(PITCH), 30.0f));   /* and held there, not recentred */
        /* the drawn pitch is +0x18c plus (1 - blend) * +0x190: as the aim ends the game puts +0x18c at rest (-20) and
           +0x190 at the last view less it (30 - -20 = 50); with +0x18c the aim's, +0x190 becomes 0, so the drawn view
           starts and stays at 30 instead of 80 easing back */
        clock_ns += 1000000000LL; seed_at(10, 40);
        clock_ns += 16666667; hos_mouse_aim(N2);
        clock_ns += 16666667; putf(PITCH, -20), putf(CAM + 0x190, 50); hos_mouse_camera(CAM);
        CHECK(near_f(getf(PITCH), 30.0f) && near_f(getf(CAM + 0x190), 0.0f));
        CHECK(near_f(getf(PITCH) + getf(CAM + 0x190), 30.0f));   /* (where the drawn view starts: the game's own start) */
        clock_ns += 16666667; hos_mouse_camera(CAM);
        CHECK(near_f(getf(CAM + 0x190), 0.0f));   /* (once: the frames after leave it to the game) */
        putf(CAM + 0x190, 0);
        /* without Disable camera centering the follow camera still waits out the yield and leaves the game's angles */
        opt45 = 0; clock_ns += 1000000000LL; seed_at(10, 40);
        clock_ns += 16666667; hos_mouse_aim(N2);
        clock_ns += 16666667; putf(PITCH, -20), putf(YAW, 0); hos_mouse_camera(CAM);
        CHECK(near_f(getf(PITCH), -20.0f) && near_f(getf(YAW), 0.0f));
        /* the mouse released as the aim ends: the game's camera is left alone, and the aim's end is not kept later */
        opt45 = 1; clock_ns += 1000000000LL; seed_at(10, 40);
        clock_ns += 16666667; hos_mouse_aim(N2);
        captured = 0; clock_ns += 100000000LL; putf(PITCH, -20), putf(YAW, 0); hos_mouse_camera(CAM);
        CHECK(near_f(getf(PITCH), -20.0f) && near_f(getf(YAW), 0.0f));
        captured = 1; clock_ns += 16666667; putf(PITCH, -20); hos_mouse_camera(CAM);
        CHECK(near_f(getf(PITCH), -20.0f));
        opt45 = 0;
    }

    {   /* ---- the other cameras' turn functions, the locked-on aim ---- */
        float hos_mouse_turn(int axis); void hos_mouse_lock_aim(uint64_t node);
        clock_ns += 1000000000LL; move_x = move_y = 0; state(0); hos_mouse_camera(CAM);
        CHECK(hos_mouse_native() == -1);
        move_x = 10; move_y = 4;
        CHECK(near_f(hos_mouse_turn(0), -1.0f) && move_x == 0);
        CHECK(near_f(hos_mouse_turn(1), 0.4f));
        CHECK(near_f(hos_mouse_turn(1), 0.0f) && hos_mouse_native() == 1);
        move_y = 5; CHECK(near_f(hos_mouse_turn(0), 0.0f)); clock_ns += 200000000LL;
        CHECK(near_f(hos_mouse_turn(1), 0.0f));   /* kept too long: dropped */
        const uint64_t LN = HOS_HEAP_BASE + 45 * 4096;
        putf(LN + 0x1d0, 1), putf(LN + 0x1d4, 2); move_x = 10; move_y = 10; hos_mouse_lock_aim(LN);
        CHECK(near_f(getf(LN + 0x1d0), 2.0f) && near_f(getf(LN + 0x1d4), 1.0f) && move_x == 0);
        /* the view's own angles turn with the offsets; the game's limits cut both */
        putf(LN + 0x1d8, -20), putf(LN + 0x1dc, 20), putf(LN + 0x1e0, -30), putf(LN + 0x1e4, 30);
        putf(LN + 0x1a4, -60), putf(LN + 0x1a8, 10), putf(LN + 0x1ac, 5);
        putf(LN + 0x1d0, 0), putf(LN + 0x1d4, 0), putf(LN + 0x1c0, 3), putf(LN + 0x1c4, 100);
        move_x = -50; move_y = 20; hos_mouse_lock_aim(LN);
        CHECK(near_f(getf(LN + 0x1d0), 2.0f) && near_f(getf(LN + 0x1d4), 5.0f));
        CHECK(near_f(getf(LN + 0x1c0), 5.0f) && near_f(getf(LN + 0x1c4), 105.0f));
        move_x = -1000; move_y = 1000; hos_mouse_lock_aim(LN);   /* base 5 + offset <= 10; the yaw's <= 30 */
        CHECK(near_f(getf(LN + 0x1d0), 5.0f) && near_f(getf(LN + 0x1d4), 30.0f));
        CHECK(near_f(getf(LN + 0x1c0), 8.0f) && near_f(getf(LN + 0x1c4), 130.0f));
        move_y = -1000; hos_mouse_lock_aim(LN);
        CHECK(near_f(getf(LN + 0x1d0), -20.0f) && near_f(getf(LN + 0x1c0), -17.0f));
        /* the game masks the stick: dropped */
        const uint64_t LS = HOS_HEAP_BASE + 52 * 4096; uint64_t ls = LS; memcpy(GP(LN + 0x20), &ls, 8);
        *(uint8_t *)GP(LS + 0x7db) = 0x10, *(uint8_t *)GP(LS + 0x7d5) = 0x40;
        move_x = 100; hos_mouse_lock_aim(LN);
        CHECK(move_x == 0 && near_f(getf(LN + 0x1d4), 30.0f) && near_f(getf(LN + 0x1c4), 130.0f));
        *(uint8_t *)GP(LS + 0x7db) = 0; move_x = 100; hos_mouse_lock_aim(LN);
        CHECK(near_f(getf(LN + 0x1d4), 20.0f) && near_f(getf(LN + 0x1c4), 120.0f));
        clock_ns += 200000000LL; CHECK(hos_mouse_native() == -1);
    }

    {   /* ---- a mouse at rest (someone on a controller): the hooks of the other nodes write nothing ---- */
        void hos_mouse_aim(uint64_t node); float hos_mouse_turn(int axis); void hos_mouse_lock_aim(uint64_t node);
        const uint64_t N3 = HOS_HEAP_BASE + 54 * 4096 + 0x40, S3 = HOS_HEAP_BASE + 56 * 4096, L3 = HOS_HEAP_BASE + 58 * 4096;
        uint64_t s3 = S3; memcpy(GP(N3 + 0x20), &s3, 8);
        putf(N3 + 0x224, -60), putf(N3 + 0x228, 70);
        putf(N3 + 0x194, 12.5f), putf(N3 + 0x18c, 13.25f), putf(N3 + 0x190, -0.0f), putf(S3 + 0x52c, 179.99f);
        putf(L3 + 0x1d0, 1.5f), putf(L3 + 0x1d4, -0.0f), putf(L3 + 0x1c0, 3), putf(L3 + 0x1c4, 100);
        putf(L3 + 0x1d8, -20), putf(L3 + 0x1dc, 20), putf(L3 + 0x1e0, -30), putf(L3 + 0x1e4, 30);
        uint8_t *before = (uint8_t *)malloc(hos_heap_size);
        clock_ns += 1000000000LL; move_x = move_y = 0;
        memcpy(before, fake_heap, hos_heap_size);
        for (int i = 0; i < 3; i++) {
            clock_ns += 16666667;
            hos_mouse_aim(N3);   /* (+0x198 is 0: no blend to take over, the one write the aim makes by itself) */
            CHECK(hos_mouse_turn(0) == 0.0f && hos_mouse_turn(1) == 0.0f);   /* exactly: the lifted code adds nothing then */
            hos_mouse_lock_aim(L3);
            CHECK(!memcmp(before, fake_heap, hos_heap_size));
        }
        /* a mouse the game has not captured is at rest too, whatever it reports */
        captured = 0; move_x = 40, move_y = -30; clock_ns += 16666667;
        hos_mouse_aim(N3);
        CHECK(hos_mouse_turn(0) == 0.0f && hos_mouse_turn(1) == 0.0f);
        hos_mouse_lock_aim(L3);
        CHECK(!memcmp(before, fake_heap, hos_heap_size));
        captured = 1; move_x = move_y = 0;
        /* Mouse camera off: nothing at all, with motion */
        menu_native = 0; move_x = 40, move_y = -30; clock_ns += 16666667;
        hos_mouse_aim(N3);
        CHECK(hos_mouse_turn(0) == 0.0f && hos_mouse_turn(1) == 0.0f);
        hos_mouse_lock_aim(L3);
        hos_mouse_camera(CAM);
        CHECK(!memcmp(before, fake_heap, hos_heap_size) && move_x == 40 && move_y == -30);
        menu_native = 1; move_x = move_y = 0;
        free(before);
        clock_ns += 200000000LL; CHECK(hos_mouse_native() == -1);
    }

    {   /* ---- another node is the view while the follow camera still updates behind it: the motion is that node's ---- */
        float hos_mouse_turn(int axis); void hos_mouse_lock_aim(uint64_t node);
        clock_ns += 1000000000LL; move_x = move_y = 0;
        state(4); seed_at(10, 30);
        for (int i = 0; i < 3; i++) {   /* the follow camera first in the frame, then the view's turn functions */
            clock_ns += 16666667; move_x = 10, move_y = 4;
            putf(PITCH, 11 + i), putf(YAW, 31 + i);   /* (the game's own angles: not put back, not turned) */
            hos_mouse_camera(CAM);
            if (i) CHECK(move_x == 10 && move_y == 4 && near_f(getf(PITCH), 11 + i) && near_f(getf(YAW), 31 + i));
            /* (the first frame is still the follow camera's: no other node had run yet) */
            if (i) CHECK(near_f(hos_mouse_turn(0), -1.0f) && near_f(hos_mouse_turn(1), 0.4f));
            else CHECK(near_f(getf(YAW), 29.0f) && hos_mouse_turn(0) == 0.0f && hos_mouse_turn(1) == 0.0f);
            CHECK(hos_mouse_native() == 1);
        }
        /* the locked-on aim counts the same */
        const uint64_t L4 = HOS_HEAP_BASE + 59 * 4096;
        clock_ns += 1000000000LL; move_x = move_y = 0;
        state(4); seed_at(10, 30);
        clock_ns += 16666667; hos_mouse_lock_aim(L4);
        clock_ns += 1000; move_x = 10; putf(YAW, 50); hos_mouse_camera(CAM);
        CHECK(move_x == 10 && near_f(getf(YAW), 50.0f));
        move_x = 0;
        /* the view is the follow camera's again: it starts from the game's angles, 50 ms after the other node's last turn */
        clock_ns += 60000000LL; putf(PITCH, 5), putf(YAW, 60); move_x = 10; hos_mouse_camera(CAM);
        CHECK(near_f(getf(YAW), 59.0f) && near_f(getf(PITCH), 5.0f) && move_x == 0);
        clock_ns += 200000000LL; CHECK(hos_mouse_native() == -1);
    }

    {   /* ---- Z-targeting: the mouse turns the node's own angles in the player's mode only ---- */
        float hos_mouse_lockon(uint64_t node, uint32_t mode, int axis); void hos_mouse_lockon_seen(uint64_t node);
        const uint64_t ZN = HOS_HEAP_BASE + 46 * 4096, ZS = HOS_HEAP_BASE + 48 * 4096;
        uint64_t zs = ZS; memcpy(GP(ZN + 0x20), &zs, 8);
        clock_ns += 1000000000LL; move_x = move_y = 0; state(0); hos_mouse_camera(CAM);
        putf(ZN + 0xec, 5), putf(ZN + 0xd8, -3); puti(ZN + 0x164, 2);
        hos_mouse_lockon_seen(ZN);
        /* as it begins (2) and while the game turns it (0): the right stick's, which is what enters the player's mode */
        for (uint32_t mode = 0; mode <= 2; mode += 2) {
            move_x = 10, move_y = 4; clock_ns += 16666667;
            CHECK(hos_mouse_lockon(ZN, mode, 0) == 0.0f && hos_mouse_lockon(ZN, mode, 1) == 0.0f);
            CHECK(move_x == 10 && move_y == 4 && near_f(getf(ZN + 0xec), 5.0f) && near_f(getf(ZN + 0xd8), -3.0f));
            CHECK(hos_mouse_native() == -1);
            move_x = move_y = 0;
        }
        /* the player's (1): right, the yaw's offset falls; down, the pitch rises; the degrees go back to the game's turn */
        puti(ZN + 0x164, 1); hos_mouse_lockon_seen(ZN);
        move_x = 10, move_y = 4; clock_ns += 16666667;
        CHECK(near_f(hos_mouse_lockon(ZN, 1, 0), -1.0f) && move_x == 0 && near_f(getf(ZN + 0xec), 4.0f));
        CHECK(near_f(hos_mouse_lockon(ZN, 1, 1), 0.4f) && near_f(getf(ZN + 0xd8), -2.6f));
        CHECK(hos_mouse_native() == 1);   /* not the stick's: the stick stays at rest and the game stays in the mode */
        /* at rest: nothing written, exactly 0 */
        clock_ns += 16666667;
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && hos_mouse_lockon(ZN, 1, 1) == 0.0f);
        CHECK(near_f(getf(ZN + 0xec), 4.0f) && near_f(getf(ZN + 0xd8), -2.6f));
        putf(ZN + 0xec, -179.5f); move_x = 10; clock_ns += 16666667;
        CHECK(near_f(hos_mouse_lockon(ZN, 1, 0), -1.0f) && near_f(getf(ZN + 0xec), 179.5f));   /* wrapped */
        menu_invert = 1; putf(ZN + 0xd8, 0); move_y = 10; clock_ns += 16666667;
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && near_f(hos_mouse_lockon(ZN, 1, 1), -1.0f) && near_f(getf(ZN + 0xd8), -1.0f));
        menu_invert = 0;
        /* the game masks the stick: dropped */
        *(uint8_t *)GP(ZS + 0x7db) = 0x10, *(uint8_t *)GP(ZS + 0x7d5) = 0x08;
        putf(ZN + 0xec, 0); move_x = 10; clock_ns += 16666667;
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && move_x == 0 && near_f(getf(ZN + 0xec), 0.0f));
        *(uint8_t *)GP(ZS + 0x7db) = 0;
        /* the item wheel: the mouse points (the stick) */
        hos_mouse_native_held(0, 1); move_x = 10; clock_ns += 16666667;
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && move_x == 10 && near_f(getf(ZN + 0xec), 0.0f) && hos_mouse_native() == -1);
        hos_mouse_native_held(0, 0); move_x = 0;
        /* Mouse camera off, or not a node: nothing */
        menu_native = 0; move_x = 10;
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && move_x == 10);
        menu_native = 1; putf(ZN + 0xec, NAN);
        CHECK(hos_mouse_lockon(ZN, 1, 0) == 0.0f && move_x == 10);
        move_x = 0;
        clock_ns += 200000000LL; CHECK(hos_mouse_native() == -1);
    }
    if (!fails) printf("PASS\n");
    return fails != 0;
}
"""


class MouseNativeTests(unittest.TestCase):
    def test_turns_the_player_camera(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("no C compiler")
        # (Windows: the compiler's own windows.h; elsewhere host/posix's stands in for it)
        windows = sys.platform == "win32"
        includes = [] if windows else ["-I", str(ROOT / "host" / "posix")]
        with tempfile.TemporaryDirectory(prefix="hookshot-mouse-native-") as tmp:
            tmp = Path(tmp)
            (tmp / "hos.h").write_text(HOS_H, encoding="utf-8")
            # (beside the stand-in hos.h, so its #include "hos.h" finds that one)
            shutil.copy(ROOT / "host" / "mouse_native.c", tmp / "mouse_native.c")
            shutil.copy(ROOT / "host" / "mouse_look.c", tmp / "mouse_look.c")   # (the game-agnostic part it calls)
            shutil.copy(ROOT / "host" / "mouse_look.h", tmp / "mouse_look.h")
            (tmp / "t.c").write_text(FIXTURE, encoding="utf-8")
            binary = tmp / ("t.exe" if windows else "t")
            build = subprocess.run([compiler, "-std=gnu11", "-include", ENV_ON_H, "-Wall", "-O1", "-g", "-I", str(tmp), *includes,
                                    str(tmp / "t.c"), str(tmp / "mouse_native.c"), str(tmp / "mouse_look.c"), "-o", str(binary),
                                    "-lm"],
                                   text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=1))
