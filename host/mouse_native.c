/* (hookshot) Native mouse look (the Insert menu's "Mouse camera", off by default; HOS_MOUSE_NATIVE=1 or 0 overrides it):
   the captured mouse turns the player camera's own yaw and pitch, in degrees, with no dead zone, no response curve, no
   smoothing and no top speed, in place of the mouse as the right stick (nn_hid.c's mouse_stick).
   Not only the camera that follows Link: the aim (hos_mouse_aim), the aim while locked on (hos_mouse_lock_aim),
   lock-on's manual mode (hos_mouse_lockon), riding and the tail, fixed and event/talk cameras the stick turns
   (hos_mouse_turn), each below. The aim starts at the view's pitch, and with Disable camera centering the camera keeps
   the aim's direction when the aim ends. HorseLockOnEmpty, HorseRevolve and ZoomTarget stay on the emulated stick (they
   do not turn by it; see hos_mouse_turn).

   This file is Longshot's glue: where the game keeps the angles, the hooks, the options, the log. The arithmetic that
   does not depend on the game's memory or on Longshot (counts to degrees, the wrap, the cuts, the two-axis latch, the
   view blend's offset) is mouse_look.c's, which builds alone, for another runtime to reuse.

   Where the angles are: the player camera's update, f_80644c80 (a virtual method, the camera in x0), calls
   hos_mouse_camera first (nx2/oot_patches.py, patch_mouse_camera), on the game's thread, once a frame while that camera
   runs. The camera holds its pitch limits at +0x178 ({-85, 89} in the field), its pitch at +0x18c and its yaw at +0x1a4.
   The game turns them by the right stick in f_80649c10 (yaw, wrapped at 180) and f_8064b770 (pitch, within the limits),
   which f_80644c80 calls only while the stick is out of its dead zone (found with hardware write watchpoints on the two
   angles in Kokiri Forest). Yaw falls as the view turns right and pitch rises as it tilts down.

   The camera's state at +0x204 is 3 while it follows Link by itself, and then it eases the pitch back toward its rest and,
   as Link walks, turns the yaw back behind him; the right stick makes it 4 (the player's), where the angles stay. The
   mouse does not move the stick, so the game's follow kept easing the view back toward Link's: after a while of playing,
   the camera drifted to where Link faced. So the angles the mouse chose are the host's own (target_yaw and target_pitch
   below), put back into the camera every frame: the camera's update still runs inside the frame -- its easing, its
   follow, its collision -- but what it does to the angles never adds up over the frames. The game's own right stick is
   let through: while the camera's keys or a pad turn it (nn_hid.c, hos_mouse_native_stick), its angles become the mouse's
   new start.

   The motion is added before the camera reads its input, so the game's own collision, lock-on and scripted cameras still
   follow. The camera is the mouse's only while the game gives it free control: the hook ran within the last 150 ms, the
   camera's state at +0x204 is 3 or 4, and the game holds none of the buttons that take the right stick for its own use
   (L, the item wheel; R — nn_hid.c says which with hos_mouse_native_free). Otherwise (a menu, an item wheel, a lock-on,
   the pause menu, cutscenes with another camera, a build the patch did not find its place in) the motion is the right
   stick as before, so the game's own menus and selections still take it. The aim (ZR) is the aiming camera's, below.

   The sensitivity is the mouse's (the menu's Mouse sensitivity, - and =): 0.1 degrees a count at 1. HOS_MOUSE_INVERT_Y=1
   or the menu's Invert mouse vertical flips up and down.

   Aiming (the slingshot, the bow, the hookshot, the first-person look: ZR) is another node of the player camera,
   ExecutePlayerCameraAiming (its name from its vtable at 0x849ddd98), with an update of its own, f_827c0470, which calls
   hos_mouse_aim first (nx2/oot_patches.py, patch_mouse_aim). It keeps its pitch at +0x194 (what the stick turns: the goal
   at +0x18c is +0x194 plus the stick's turn, cut to the limits at +0x224 and +0x228, and +0x194 then follows the goal)
   and reads its yaw each frame from the camera state it shares with the other nodes (the node's +0x20, the yaw at +0x52c),
   adds the stick's turn and keeps the result at +0x190. With the stick at rest and the game's motion aim on, it turns the
   goals at +0x18c and +0x190 by the gyroscope instead and eases +0x194 and the shared yaw toward them. So the mouse's
   degrees are added to all four before the update reads them: the view turns by exactly the mouse's motion in either
   branch, with no dead zone, curve or top speed, and the game's own limits, recoil and collision follow. The signs are the
   stick's (f_80643e70 and f_80643ac0: the turn is -0.5 * speed * stick), as in the camera that follows Link. While the
   shared state's flags at +0x218 (bits 30 and 53) make the update skip its input, the motion is dropped as the stick's
   would be. HOS_MOUSE_AIM_SCALE=<x> scales the aim's sensitivity against the camera's (1).

   A mouse at rest (someone on a controller): with Mouse camera off no hook writes anything. With it on, the camera that
   follows Link has its angles put back every frame, as above, and the other hooks (hos_mouse_aim, hos_mouse_turn,
   hos_mouse_lock_aim) write nothing and return exactly 0 while the mouse has not moved, with two exceptions that do not
   wait for the mouse: the aim begins at the view's pitch (the blend at +0x198, in hos_mouse_aim), and with Disable
   camera centering the camera that follows Link starts from where the aim looked when the aim ends (hos_mouse_camera).
   tests/test_mouse_native.py holds the rest to it. */
#include "hos.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#ifndef HOOKSHOT_ENV_H   /* (env_on: the switches' one rule) */
#include "../gpu/vk/compat/hookshot_env.h"
#endif
#include "mouse_look.h"   /* (the game-agnostic part: counts to degrees, wraps, cuts, the latch, the view blend) */

int hos_mouse_take(int32_t *dx, int32_t *dy);                                   /* display.c */
void hos_mouse_give_back(int32_t dx, int32_t dy);                               /* display.c */
int rx_option(int id, int otherwise);
extern double hos_mouse_sens;

enum { LIMITS_AT = 0x178, PITCH_AT = 0x18c, PITCH_BLEND_AT = 0x190, YAW_AT = 0x1a4, STATE_AT = 0x204 };
#define LIVE_NS 150000000LL   /* (the hook ran this recently: the camera takes the mouse) */
/* (the camera's state at +0x204: 3 while it follows Link by itself, where the right stick takes it over, 4 the player's) */
#define STATE_FOLLOWS 3
#define STATE_PLAYER 4

static volatile LONG64 last_hook_ns;
static volatile LONG64 last_camera;
static volatile LONG last_state = -1;   /* (the last camera's state at +0x204) */
static volatile LONG game_free = 1;     /* (nn_hid.c: the game leaves the camera to the player this frame) */
static volatile LONG stick_held;        /* (nn_hid.c: the camera's keys or a pad turn the camera this frame) */
static uint64_t own_camera;             /* (the camera target_yaw and target_pitch belong to) */
static float target_yaw, target_pitch;  /* (the mouse's angles: the game's own follow is undone every frame) */
static int target_ok;
static long long applied, cameras_seen;

/* (the aiming node, ExecutePlayerCameraAiming: see the top) */
enum { AIM_SHARED_AT = 0x20, AIM_PITCH_GOAL_AT = 0x18c, AIM_YAW_GOAL_AT = 0x190, AIM_PITCH_AT = 0x194, AIM_BLEND_AT = 0x198, AIM_LIMITS_AT = 0x224,
       SHARED_FLAGS_AT = 0x218, SHARED_YAW_AT = 0x52c, SHARED_VIEW_TO_AT = 0x450, SHARED_VIEW_FROM_AT = 0x45c };
#define SHARED_NO_INPUT ((1ULL << 30) | (1ULL << 53))   /* (f_827c0470: with one of them set it turns by nothing) */
#define AIM_WAIT_NS 250000000LL   /* (after ZR goes down the motion waits this long for the aiming camera's first update) */
static volatile LONG64 aim_hook_ns;   /* (the aiming node's update ran then) */
static volatile LONG64 zr_down_ns;    /* (nn_hid.c: ZR went down then) */
static volatile LONG zr_held, wheel_held;   /* (nn_hid.c: ZR, the aim; L, the item wheel, where the mouse points) */
static long long aim_applied, aims_seen;
/* (where the aim last looked, for the camera that follows Link to start from when the aim ends) */
static float aim_last_pitch, aim_last_yaw;
static int64_t aim_last_ns;
static int aim_last_ok;
/* (the follow camera's pitch less the view's, as the aim began: the two are different angles of the same view) */
static float aim_follow_dp;
static int aim_follow_dp_ok;
static int aim_kept;   /* (the follow camera holds the aim's end: hos_mouse_camera; a new aim frame clears it) */
static uint64_t aim_shared;   /* (the aim's shared camera state, for the trace's view below) */
static int trace_frames;      /* (HOS_MOUSE_DEBUG: the follow camera's updates still to trace after an aim) */
static void trace_follow(uint64_t cam, uint32_t state, float pitch_in, float yaw_in, const char *did);
#define AIM_KEEP_NS 2000000000LL   /* (the follow camera comes back within this of the aim's last update) */
#define AIM_YIELD_NS 50000000LL    /* (the aim ran this recently: the follow camera leaves the mouse to it) */
/* (a turn function or the locked-on aim ran then, hos_mouse_turn and hos_mouse_lock_aim below: another node is the view) */
static volatile LONG64 turn_hook_ns;

static int debug_on(void);   /* (HOS_MOUSE_DEBUG, below) */
static float getf(uint64_t a) { float f; memcpy(&f, GP(a), 4); return f; }
static void putf(uint64_t a, float f) { memcpy(GP(a), &f, 4); }
static int32_t geti(uint64_t a) { int32_t v; memcpy(&v, GP(a), 4); return v; }

/* the menu's Mouse camera (option 6), or HOS_MOUSE_NATIVE */
static int native_on(void) {
    static const char *env;
    static int looked;
    if (!looked) looked = 1, env = getenv("HOS_MOUSE_NATIVE");
    return env ? atoi(env) != 0 : rx_option(6, 0) == 1;   /* (2: Off) */
}

static int invert_y(void) {
    static int env = -1;
    if (env < 0) env = env_on("HOS_MOUSE_INVERT_Y");
    return env || rx_option(8, 0);   /* (the menu's Invert mouse vertical) */
}

/* a camera's angles as the game keeps them: limits in order within +-90, angles finite */
static int looks_like_camera(uint64_t cam) {
    const float lo = getf(cam + LIMITS_AT), hi = getf(cam + LIMITS_AT + 4), p = getf(cam + PITCH_AT), y = getf(cam + YAW_AT);
    return isfinite(lo) && isfinite(hi) && lo < hi && lo >= -90.0f && hi <= 90.0f && isfinite(p) && isfinite(y) &&
           fabsf(y) <= 360.0f;
}

/* Whether the game gives the camera to the player now: its update ran within the last 150 ms, its state is one the
   right stick turns (3 or 4), and none of the buttons the game takes the stick for is held. Otherwise the mouse is the
   right stick, as in As the stick: in a menu, an item wheel, a lock-on, a scripted camera or the bow's aim. */
static int free_look(void) {
    if (hos_now_ns() - InterlockedCompareExchange64(&last_hook_ns, 0, 0) >= LIVE_NS) return 0;
    const int state = last_state;
    return (state == STATE_FOLLOWS || state == STATE_PLAYER) && game_free != 0;
}

/* The Controls row "Disable camera centering" (option 45), independent of the mouse mode. The game's state-3 yaw-follow
   branch asks before it runs (nx2/oot_patches.py); 0 keeps the stock behavior, including without a renderer. (#2617 took it
   out with its rewrite of this file; the lifted game still calls it, and the link failed without it) */
int hos_disable_camera_centering(void) { return rx_option(45, 0); }

/* nn_hid.c, with each read of the controller: 1 while the game leaves the camera to the player, 0 while it takes the
   right stick for its own use (ZR, the bow's aim; L, the item wheel; R) */
void hos_mouse_native_free(int free) { InterlockedExchange(&game_free, free ? 1 : 0); }

/* nn_hid.c, with each read of the controller: 1 while the player's own right stick (the camera's keys, a pad) turns the
   camera this frame. The game has then moved the angles itself, so they are the mouse's new start: the stick and the
   mouse both turn the camera instead of undoing each other. */
void hos_mouse_native_stick(int held) { InterlockedExchange(&stick_held, held ? 1 : 0); }

/* f_80644c80's first line (nx2/oot_patches.py): cam is the player camera, the game's thread */
void hos_mouse_camera(uint64_t cam) {
    if (!cam || !native_on() || !looks_like_camera(cam)) return;
    const float pitch_in = getf(cam + PITCH_AT), yaw_in = getf(cam + YAW_AT);   /* (what the game left: the trace) */
    /* Only while it is the view: following Link (3) or turned by the player (4). Aiming the slingshot in first person
       leaves this camera updating with its state 0 while another one draws (traced at Hyrule Castle); shops are reported
       the same. In any other state the mouse is the right stick, which those views turn by (the hook counts as not
       run, so hos_mouse_native gives -1) */
    uint32_t state;
    memcpy(&state, GP(cam + STATE_AT), 4);
    if (state != 3 && state != 4) {
        /* (at once: the stick takes the next motion, not one burst once the 150 ms run out) */
        InterlockedExchange64(&last_hook_ns, 0);
        target_ok = 0;   /* the game's angles may change while another camera owns the view */
        /* (each state seen leaving the mouse to the stick, once: what another view, Z-targeting, climbing or swimming,
           is, to add here if one of them should turn with the mouse) */
        static uint32_t said[8];
        static int nsaid;
        int seen = 0;
        for (int i = 0; i < nsaid; i++) seen |= said[i] == state;
        if (!seen && nsaid < 8) {
            said[nsaid++] = state;
            hos_log("mouse native: camera state %u: the mouse is the right stick", state);
        }
        trace_follow(cam, state, pitch_in, yaw_in, "left to the game (its state)");
        return;
    }
    InterlockedExchange64(&last_hook_ns, hos_now_ns());
    InterlockedExchange(&last_state, geti(cam + STATE_AT));
    /* (a menu, an item wheel, a lock-on: the game's camera, and the motion is the right stick's, nn_hid.c; or the game
       aims, and the motion is the aiming camera's alone, hos_mouse_aim; or another node the stick turns is the view
       (riding, an event's camera, the locked-on aim: hos_mouse_turn, hos_mouse_lock_aim) while this one still updates
       behind it in state 3 or 4, and the motion is that node's. This camera's own stick turns, f_80649c10 and
       f_8064b770, do not go through the turn functions, so it never yields to itself) */
    const int64_t hook_now = hos_now_ns();
    /* (the aim's end, below, does not wait out the aim's yield: the camera is put where the aim looked from the first
       frame it is the view again. Waiting the 50 ms let the game recentre it for about three frames first, a flick up
       and back seen in play. The motion still waits: the aim may run again in this frame) */
    const int aim_recent = hook_now - InterlockedCompareExchange64(&aim_hook_ns, 0, 0) < AIM_YIELD_NS;
    const int keep_aim = aim_last_ok && hos_disable_camera_centering() && hook_now - aim_last_ns < AIM_KEEP_NS;
    if (!free_look() || (aim_recent && !keep_aim && !aim_kept) ||
        hook_now - InterlockedCompareExchange64(&turn_hook_ns, 0, 0) < AIM_YIELD_NS) {
        target_ok = 0, aim_kept = 0;
        trace_follow(cam, state, pitch_in, yaw_in, !free_look() ? "left to the game (not free)" : "left to the game (yield)");
        return;
    }
    /* (the aim's own frames take the mouse themselves: only after the aim's yield does this camera ask for it) */
    int32_t dx = 0, dy = 0;
    if (!aim_recent && !hos_mouse_take(&dx, &dy)) {   /* (the mouse released: the view is the game's, and the next captured frame starts from it) */
        target_ok = 0, aim_kept = 0, aim_last_ok = 0;
        return;
    }
    if (InterlockedExchange64(&last_camera, (LONG64)cam) != (LONG64)cam && cameras_seen++ < 8)
        hos_log("mouse native: the player camera at %#llx turns with the mouse", (unsigned long long)cam);
    /* (a new camera, or one the game's own stick turned: its angles now are where the mouse starts from) */
    if (!target_ok || own_camera != cam || stick_held) {
        own_camera = cam;
        target_yaw = getf(cam + YAW_AT);
        target_pitch = getf(cam + PITCH_AT);
        target_ok = 1;
    }
    /* The aim just ended and Disable camera centering is on: the game put this camera back behind Link, at its rest
       pitch. It starts from where the aim looked instead (the two cameras' angles are the same ones: the aim takes its
       first from this camera's view, f_827bfed0) */
    {
        if (keep_aim) {
            const float lo = getf(cam + LIMITS_AT), hi = getf(cam + LIMITS_AT + 4);
            /* (the aim's pitch is the view's; this camera's is that plus what it differed by as the aim began) */
            const float p = aim_last_pitch + (aim_follow_dp_ok ? aim_follow_dp : 0.0f);
            target_yaw = aim_last_yaw;
            target_pitch = ml_clamp(p, lo, hi);
            /* The pitch this camera draws is not +0x18c alone: f_80644c80 (80646ba0) draws +0x18c plus (1 - its blend)
               times +0x190, and as the aim ends the game puts +0x18c back at rest and +0x190 at the last view less that
               rest, so the drawn view starts where the aim looked and eases to the rest. With +0x18c now the aim's, that
               offset was added on top: the view jumped by it and eased back (a flick up of about 11 degrees, traced in
               play). The offset is moved so the drawn view still starts at the same place, now also where it stays */
            const float blend_off = getf(cam + PITCH_BLEND_AT);
            if (isfinite(blend_off) && fabsf(blend_off) <= 360.0f && isfinite(pitch_in))
                putf(cam + PITCH_BLEND_AT, ml_blend_offset_kept(pitch_in, blend_off, target_pitch));
            hos_log("mouse native: the camera keeps the aim's view (pitch %.2f, the aim's %.2f; yaw %.2f)", target_pitch,
                    aim_last_pitch, target_yaw);
            aim_kept = 1;   /* (and holds it through the rest of the yield, frame by frame) */
        }
        aim_last_ok = 0;
    }
    if (!aim_recent && (dx || dy)) {
        const double k = ml_degrees_per_count(hos_mouse_sens, 1.0);
        target_yaw += ml_yaw_by(dx, k);
        target_pitch += ml_pitch_by(dy, k, invert_y());
        const float lo = getf(cam + LIMITS_AT), hi = getf(cam + LIMITS_AT + 4);
        while (target_yaw > 180.0f) target_yaw -= 360.0f;   /* (180 itself kept: this camera's own wrap) */
        while (target_yaw < -180.0f) target_yaw += 360.0f;
        target_pitch = ml_clamp(target_pitch, lo, hi);
        if ((++applied & 4095) == 1)
            hos_log("mouse native: %lld moves applied; pitch %.2f yaw %.2f", applied, target_pitch, target_yaw);
    }
    /* (put back every frame: the camera eases and follows by itself inside one, but none of that adds up to a view that
       drifts back toward Link while the mouse is the camera) */
    putf(cam + YAW_AT, target_yaw), putf(cam + PITCH_AT, target_pitch);
    trace_follow(cam, state, pitch_in, yaw_in, "put");
}

/* Whether the aiming camera takes the mouse now: its update ran within the last 150 ms, and the item wheel (L), where the
   mouse points as the stick, is not open */
static int aim_live(void) {
    return !wheel_held && hos_now_ns() - InterlockedCompareExchange64(&aim_hook_ns, 0, 0) < LIVE_NS;
}

/* nn_hid.c, with each read of the controller: whether ZR (the aim) and L (the item wheel) are held */
void hos_mouse_native_held(int zr, int wheel) {
    if (zr && !InterlockedExchange(&zr_held, 1)) InterlockedExchange64(&zr_down_ns, hos_now_ns());
    if (!zr) InterlockedExchange(&zr_held, 0);
    InterlockedExchange(&wheel_held, wheel ? 1 : 0);
}

/* HOS_MOUSE_DEBUG: the follow camera update by update for 40 of them after each aim: its state, the angles the game left
   in it, what the hook did, and the view's own pitch on screen (the aim's shared state, +0x450 less +0x45c, as
   f_80738800 reads it; last frame's), to see what moves the view as the aim ends */
static void trace_follow(uint64_t cam, uint32_t state, float pitch_in, float yaw_in, const char *did) {
    if (trace_frames <= 0) return;
    trace_frames--;
    float view = NAN, to[3], from[3];
    if (aim_shared) {
        memcpy(to, GP(aim_shared + SHARED_VIEW_TO_AT), 12), memcpy(from, GP(aim_shared + SHARED_VIEW_FROM_AT), 12);
        ml_pitch_of_vector(to[0] - from[0], to[1] - from[1], to[2] - from[2], &view);
    }
    hos_log("mouse native trace: %+.1f ms after the aim, state %u, the game left pitch %.2f yaw %.2f, view %.2f; %s "
            "pitch %.2f yaw %.2f", (double)(hos_now_ns() - aim_last_ns) / 1e6, state, pitch_in, yaw_in, view, did,
            getf(cam + PITCH_AT), getf(cam + YAW_AT));
}

static double aim_scale(void) {
    static double scale = -1;
    if (scale < 0) {
        const char *e = getenv("HOS_MOUSE_AIM_SCALE");
        scale = e && atof(e) > 0 ? atof(e) : 1.0;
    }
    return scale;
}

/* f_827c0470's first line (nx2/oot_patches.py, patch_mouse_aim): node is the player camera's aiming node, on the game's
   thread, once a frame while the game aims */
void hos_mouse_aim(uint64_t node) {
    if (!node || !native_on()) return;
    uint64_t shared;
    memcpy(&shared, GP(node + AIM_SHARED_AT), 8);
    if (!shared) return;
    float pitch = getf(node + AIM_PITCH_AT), pitch_goal = getf(node + AIM_PITCH_GOAL_AT);
    const float yaw_goal = getf(node + AIM_YAW_GOAL_AT), yaw = getf(shared + SHARED_YAW_AT);
    if (!isfinite(pitch) || !isfinite(pitch_goal) || !isfinite(yaw_goal) || !isfinite(yaw) || fabsf(pitch) > 180.0f ||
        fabsf(yaw) > 360.0f)
        return;   /* (not the node this build's offsets are for: the stick takes the mouse, as before) */
    InterlockedExchange64(&aim_hook_ns, hos_now_ns());
    if (InterlockedExchange64(&last_camera, (LONG64)node) != (LONG64)node && aims_seen++ < 8)
        hos_log("mouse native: the aiming camera at %#llx turns with the mouse", (unsigned long long)node);
    float lo = getf(node + AIM_LIMITS_AT), hi = getf(node + AIM_LIMITS_AT + 4);
    if (!(isfinite(lo) && isfinite(hi) && lo < hi && lo >= -90.0f && hi <= 90.0f)) lo = -90.0f, hi = 90.0f;
    /* The aim begins (f_827bfed0, the only writer of +0x198): the game starts its pitch at the view's pitch plus a tuned
       offset and keeps the difference at +0x198 to blend it in, so the view tilted a little as the bow came up. The pitch
       starts at the view's own instead; +0x198 keeps only what the limits cut. A new +0x198 is a new aim */
    {
        static uint64_t entry_node;
        static uint32_t entry_bits;
        uint32_t bits;
        memcpy(&bits, GP(node + AIM_BLEND_AT), 4);
        if (node != entry_node || bits != entry_bits) {
            /* The view's pitch the aim starts from is read another way than the follow camera's: f_827bfed0 takes it
               from the view's own direction (f_80738800 of shared +0x450 less +0x45c), the follow camera's +0x18c is the
               angle it circles Link at. In play the two were the same (the difference logged 0.00 at every aim), but it
               is kept for the aim's end (hos_mouse_camera) in case a view is found where they part. With a blend the
               view's pitch is the game's own number, the aim's pitch plus +0x198; without one (the aim took back its last
               pitch, f_827bfed0's other path) it is worked out as f_80738800 does */
            float to[3], from[3], view = 0.0f;
            const float blend = getf(node + AIM_BLEND_AT);
            memcpy(to, GP(shared + SHARED_VIEW_TO_AT), 12), memcpy(from, GP(shared + SHARED_VIEW_FROM_AT), 12);
            const int have_view = isfinite(blend) && blend != 0.0f && fabsf(blend) <= 180.0f
                                      ? (view = ml_wrap180(pitch + blend), 1)
                                      : ml_pitch_of_vector(to[0] - from[0], to[1] - from[1], to[2] - from[2], &view);
            aim_follow_dp_ok = 0;
            if (own_camera && looks_like_camera(own_camera) && have_view) {
                const float dp = getf(own_camera + PITCH_AT) - view;
                if (isfinite(dp) && fabsf(dp) <= 90.0f) aim_follow_dp = dp, aim_follow_dp_ok = 1;
            }
            if (debug_on())
                hos_log("mouse native: the aim begins: the view's pitch %.2f (%s), the follow camera's %s %.2f", view,
                        isfinite(blend) && blend != 0.0f ? "blend" : "direction", aim_follow_dp_ok ? "differs by" : "unknown",
                        aim_follow_dp_ok ? aim_follow_dp : 0.0f);
            const float off = blend;
            if (isfinite(off) && fabsf(off) <= 180.0f && off != 0.0f) {
                const float start = ml_wrap180(pitch + off), p = ml_clamp(start, lo, hi);
                putf(node + AIM_PITCH_AT, p), putf(node + AIM_PITCH_GOAL_AT, p), putf(node + AIM_BLEND_AT, ml_wrap180(start - p));
                pitch = pitch_goal = p;
            }
            entry_node = node;
            memcpy(&entry_bits, GP(node + AIM_BLEND_AT), 4);
        }
    }
    aim_last_pitch = pitch, aim_last_yaw = yaw, aim_last_ns = hos_now_ns(), aim_last_ok = 1, aim_kept = 0;
    aim_shared = shared;
    if (debug_on()) trace_frames = 40;
    if (wheel_held) return;   /* (the item wheel: the mouse points, nn_hid.c) */
    int32_t dx, dy;
    if (!hos_mouse_take(&dx, &dy) || !(dx || dy)) return;
    uint64_t flags;
    memcpy(&flags, GP(shared + SHARED_FLAGS_AT), 8);
    if (flags & SHARED_NO_INPUT) return;   /* (the game takes no turn now: the motion is dropped, as the stick's is) */
    const double k = ml_degrees_per_count(hos_mouse_sens, aim_scale());
    const float by_yaw = ml_yaw_by(dx, k), by_pitch = ml_pitch_by(dy, k, invert_y());
    const float p = ml_clamp(pitch + by_pitch, lo, hi), pg = ml_clamp(pitch_goal + by_pitch, lo, hi);
    putf(node + AIM_PITCH_AT, p), putf(node + AIM_PITCH_GOAL_AT, pg);
    putf(shared + SHARED_YAW_AT, ml_wrap180(yaw + by_yaw)), putf(node + AIM_YAW_GOAL_AT, ml_wrap180(yaw_goal + by_yaw));
    aim_last_pitch = p, aim_last_yaw = ml_wrap180(yaw + by_yaw);
    if ((++aim_applied & 4095) == 1)
        hos_log("mouse native: %lld aim moves applied; pitch %.2f yaw %.2f", aim_applied, p, ml_wrap180(yaw + by_yaw));
}

/* The player camera's other nodes that the right stick turns (riding: ExecutePlayerCameraHorse; ExecutePlayerCameraTail,
   ExecutePlayerCameraFix, and the events' and talks' manual cameras: EventSingle, EventMultiTalk, TalkManualCtrl,
   TalkOverShoulder) each add what f_80643e70 (yaw) and f_80643ac0 (pitch) return, the stick's turn of this frame in
   degrees (-0.5 * speed * frame time * stick), to an angle of their own, and call them only while they take the stick.
   Both functions add hos_mouse_turn's degrees to what they return (nx2/oot_patches.py, patch_mouse_turn): the mouse turns
   whichever of those cameras runs, within that camera's own limits. A frame's motion is taken at the first of the two
   calls and the other axis kept for the second; an axis nobody asks for within 100 ms is dropped. While the game aims,
   hos_mouse_aim has taken the motion before these run.

   Three nodes are left to the mouse as the right stick on purpose, since none of them turns by it: riding with the lock
   held and no target (ExecutePlayerCameraHorseLockOnEmpty, f_827d9c90) takes the stick's vertical axis alone as a
   position, a goal of -stick * limit that the angle at +0x98 eases toward and springs back from; HorseRevolve
   (f_827dbe50) does not read the stick; ZoomTarget (f_827e4970) only asks whether the stick has moved, to give the
   view back to the player. */
#define TURN_KEEP_NS 100000000LL
static ml_latch turn;   /* (the motion taken and not yet asked for, axis by axis) */
static long long turn_applied;

static int turn_live(void) {
    return !wheel_held && hos_now_ns() - InterlockedCompareExchange64(&turn_hook_ns, 0, 0) < LIVE_NS;
}

static void turn_take(int64_t now) {
    int32_t dx = 0, dy = 0;
    if (!hos_mouse_take(&dx, &dy)) dx = dy = 0;
    ml_latch_add(&turn, now, TURN_KEEP_NS, dx, dy);
}

/* f_80643e70's (axis 0, the yaw) and f_80643ac0's (axis 1, the pitch) returns: the degrees to add to the stick's turn */
float hos_mouse_turn(int axis) {
    if (!native_on()) return 0.0f;
    const int64_t now = hos_now_ns();
    InterlockedExchange64(&turn_hook_ns, now);
    if (wheel_held) return 0.0f;
    turn_take(now);
    const double k = ml_degrees_per_count(hos_mouse_sens, 1.0);
    const float by = axis == 0 ? ml_yaw_by(ml_latch_take(&turn, 0), k) : ml_pitch_by(ml_latch_take(&turn, 1), k, invert_y());
    if (by != 0.0f && (++turn_applied & 4095) == 1)
        hos_log("mouse native: %lld turns of the game's other cameras (riding, events) applied", turn_applied);
    return by;
}

/* The aim while locked on (ExecutePlayerCameraLockOnAimingAt): f_827de2a0 turns the node's own offsets by the stick, the
   pitch's at +0x1d0 and the yaw's at +0x1d4, and then cuts them to its limits on every path. It calls hos_mouse_lock_aim
   first (nx2/oot_patches.py): the mouse's degrees go into the two offsets before it reads them. */
void hos_mouse_lock_aim(uint64_t node) {
    if (!node || !native_on()) return;
    const float pitch = getf(node + 0x1d0), yaw = getf(node + 0x1d4);
    if (!isfinite(pitch) || !isfinite(yaw) || fabsf(pitch) > 360.0f || fabsf(yaw) > 360.0f) return;
    const int64_t now = hos_now_ns();
    InterlockedExchange64(&turn_hook_ns, now);
    if (wheel_held) return;
    turn_take(now);
    if (!turn.x && !turn.y) return;
    const double k = ml_degrees_per_count(hos_mouse_sens, aim_scale());
    const float by_pitch = ml_pitch_by(ml_latch_take(&turn, 1), k, invert_y()), by_yaw = ml_yaw_by(ml_latch_take(&turn, 0), k);
    /* (the game masks the stick here, f_82b8e1f0: the motion is dropped as the stick's is) */
    uint64_t shared;
    memcpy(&shared, GP(node + AIM_SHARED_AT), 8);
    if (shared && (*(uint8_t *)GP(shared + 0x7db) & 0x10) && (*(uint8_t *)GP(shared + 0x7d5) & 0x48)) return;
    /* The offsets, cut as f_827de2a0 cuts them (the pitch's to +0x1d8..+0x1dc and, with the pitch toward the target at
       +0x1ac, to +0x1a4..+0x1a8; the yaw's to +0x1e0..+0x1e4). The view's own angles (+0x1c0 the pitch, +0x1c4 the yaw)
       only ease toward the target's direction plus the offsets, at 3 degrees a frame at most (f_806443c0 in f_827dd500):
       the view trailed the mouse. So what the offsets really turned by is added to the view's angles too */
    float p = ml_wrap180(pitch + by_pitch), y = ml_wrap180(yaw + by_yaw);
    const float plo = getf(node + 0x1d8), phi = getf(node + 0x1dc), tlo = getf(node + 0x1a4), thi = getf(node + 0x1a8),
                base = getf(node + 0x1ac), ylo = getf(node + 0x1e0), yhi = getf(node + 0x1e4);
    if (isfinite(plo) && isfinite(phi) && plo < phi) p = p > phi ? phi : p < plo ? plo : p;
    if (isfinite(tlo) && isfinite(thi) && isfinite(base) && tlo < thi) {
        const float t = ml_wrap180(base + p), tc = t > thi ? thi : t < tlo ? tlo : t;
        p = ml_wrap180(p - t + tc);
    }
    if (isfinite(ylo) && isfinite(yhi) && ylo < yhi) y = y > yhi ? yhi : y < ylo ? ylo : y;
    const float view_pitch = getf(node + 0x1c0), view_yaw = getf(node + 0x1c4);
    putf(node + 0x1d0, p), putf(node + 0x1d4, y);
    if (isfinite(view_pitch)) putf(node + 0x1c0, ml_wrap180(view_pitch + ml_wrap180(p - pitch)));
    if (isfinite(view_yaw)) putf(node + 0x1c4, ml_wrap180(view_yaw + ml_wrap180(y - yaw)));
}

/* HOS_MOUSE_DEBUG=1 says in the log, once a change, whose the mouse is (hos_mouse_native) and which lock-on node runs in
   which mode (hos_mouse_lockon_seen): what an in-game check of these cameras needs to know. Off by default. */
static int debug_on(void) {
    static int env = -1;
    if (env < 0) env = env_on("HOS_MOUSE_DEBUG");
    return env;
}

static void debug_owner(const char *whose) {
    static const char *last;
    if (debug_on() && whose != last) last = whose, hos_log("mouse native: the mouse is %s", whose);
}

/* Z-targeting: ExecutePlayerCameraLockOn (its vtable at 0x849e0b78) and ExecutePlayerCameraTarget (0x849e1448) share one
   update, f_8072da10, which calls hos_mouse_lockon_seen first (nx2/oot_patches.py, patch_mouse_lockon). The node's mode
   at +0x164 is 2 as it begins (it centres behind Link), 0 while the game turns it and 1 once the right stick has turned
   it (the player's: f_80a3e250, LockOn's own, picks it each frame; Target's never leaves 2). This only keeps which node
   ran and in which mode, and says a change of either with HOS_MOUSE_DEBUG.

   The player's mode turns two angles of the node by the right stick: the yaw's offset from the direction behind Link at
   +0xec (8072eba4: the stick's turn, -0.5 * speed * stick, scaled by the frame's time and the distance to the target,
   is added and wrapped) and the pitch at +0xd8 (8072f1d4, the same way). Each has a place where the stick's path and
   the path of a stick at rest join, with this frame's turn in a register: 8072ee0c (the offset in s0, the turn in s9)
   and 8072f2a4 (the turn in s11). After them the game cuts the angles to its limits and eases the view toward them,
   at the turn's own speed at least, so a turn is followed at once. Both places call hos_mouse_lockon (nx2/oot_patches.py)
   with the node, the mode the frame began in (w28) and the axis: in the player's mode the mouse's degrees go into the
   angle, and the lifted code adds what is returned to the turn's register, so the view follows the mouse as it follows
   the stick. In the other modes the mouse stays the right stick: that is what makes the game enter the player's mode
   (f_80a3e250), and it stays in it with the stick back at rest. Target's node never is in it. */
enum { LOCKON_MODE_AT = 0x164, LOCKON_PITCH_AT = 0xd8, LOCKON_YAW_AT = 0xec };
#define LOCKON_VTABLE 0x849e0b78ULL
#define TARGET_VTABLE 0x849e1448ULL
#define LOCKON_PLAYERS 1   /* (the mode in which the right stick turns the view) */
static volatile LONG64 lockon_node;
static volatile LONG lockon_mode = -1;

void hos_mouse_lockon_seen(uint64_t node) {
    if (!node || !native_on()) return;
    const int32_t mode = geti(node + LOCKON_MODE_AT);
    const int same = InterlockedExchange64(&lockon_node, (LONG64)node) == (LONG64)node;
    const int same_mode = InterlockedExchange(&lockon_mode, mode) == mode;
    if (!debug_on() || (same && same_mode)) return;
    uint64_t vtable;
    memcpy(&vtable, GP(node), 8);
    hos_log("mouse native: the lock-on node at %#llx (%s, vtable %#llx) is in mode %d", (unsigned long long)node,
            vtable == LOCKON_VTABLE ? "LockOn" : vtable == TARGET_VTABLE ? "Target" : "unknown",
            (unsigned long long)vtable, (int)mode);
}

/* 8072ee0c (axis 0, the yaw's offset) and 8072f2a4 (axis 1, the pitch) of f_8072da10: the degrees the mouse turned the
   node's angle by, for the lifted code to add to the turn of this frame; 0 with nothing done */
float hos_mouse_lockon(uint64_t node, uint32_t mode, int axis) {
    if (!node || !native_on() || mode != LOCKON_PLAYERS) return 0.0f;
    const uint64_t at = node + (axis == 0 ? LOCKON_YAW_AT : LOCKON_PITCH_AT);
    const float angle = getf(at);
    if (!isfinite(angle) || fabsf(angle) > 360.0f) return 0.0f;   /* (not the node this build's offsets are for) */
    const int64_t now = hos_now_ns();
    InterlockedExchange64(&turn_hook_ns, now);
    if (wheel_held) return 0.0f;
    turn_take(now);
    const double k = ml_degrees_per_count(hos_mouse_sens, 1.0);
    const float by = axis == 0 ? ml_yaw_by(ml_latch_take(&turn, 0), k) : ml_pitch_by(ml_latch_take(&turn, 1), k, invert_y());
    if (by == 0.0f) return 0.0f;
    /* (the game masks the stick here, f_82b8e1f0: the motion is dropped as the stick's is) */
    uint64_t shared;
    memcpy(&shared, GP(node + AIM_SHARED_AT), 8);
    if (shared && (*(uint8_t *)GP(shared + 0x7db) & 0x10) && (*(uint8_t *)GP(shared + 0x7d5) & 0x48)) return 0.0f;
    putf(at, ml_wrap180(angle + by));
    return by;
}

/* With each read of the controller (nn_hid.c, the game's threads): 0 if the mouse is not captured, 1 if a camera takes
   its motion (hos_mouse_camera, or hos_mouse_aim while the game aims), -1 if the game does not give the camera free
   control now (a menu, an item wheel, a lock-on, the wheels, no player camera: the right stick takes it) */
int hos_mouse_native(void) {
    static int said, waited;
    static int64_t live_ns;   /* (a camera took the mouse then) */
    if (!said) said = 1, hos_log("mouse native: on (the menu's Mouse camera, or HOS_MOUSE_NATIVE)");
    const int64_t now = hos_now_ns();
    if (aim_live() || turn_live() || free_look()) {
        waited = 0, live_ns = now;
        debug_owner(aim_live() ? "the aiming camera's" : turn_live() ? "another camera's (riding, an event, a lock-on)"
                                                                       : "the camera's that follows Link");
    } else {
        /* ZR is held and a camera had the mouse a moment ago, or ZR just went down: the aiming camera's first update is a
           few frames away, and the motion waits for it rather than push the stick meanwhile. When no aiming camera comes
           (ZR with nothing to aim), what waited is dropped, so the stick does not get it as one push */
        const int64_t down_ns = InterlockedCompareExchange64(&zr_down_ns, 0, 0);
        if (zr_held && !wheel_held && now - (down_ns > live_ns ? down_ns : live_ns) < AIM_WAIT_NS)
            waited = 1;
        else {
            int32_t dx, dy;
            if (waited) waited = 0, hos_mouse_take(&dx, &dy);
            debug_owner("the right stick's");
            return -1;
        }
    }
    int32_t dx, dy;
    const int captured = hos_mouse_take(&dx, &dy);   /* (only to know the capture: the motion is the camera's) */
    if (dx || dy) hos_mouse_give_back(dx, dy);
    return captured ? 1 : 0;
}
