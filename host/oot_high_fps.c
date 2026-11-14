/* (hookshot) The sound manager's job at up to 60 Hz, the physics solver's steps rounded up, the floor-carry gate, the turn
   action's speed clamp and the special step rates' countdowns, with a measured frame step: the lifted f_80435300, f_838ceb80,
   f_838cfc10, the three follow-surface updates, f_8263e8e0 and f_82f72df0 call these (nx2/oot_patches.py); host/oot_high_fps.h
   has why and the logic.
   HOS_FPS_LOG (on, by the switches' rule: =0 is off): what they do, every 600 calls. HOS_FPS_FLOOR=0: the game's floor-carry
   gate at every frame rate, HOS_FPS_TURN=0: the game's turn speed clamp, HOS_FPS_STEPRATE=0: the game's special step rate
   countdowns (for comparisons). */
#include "hos.h"
#include "oot_high_fps.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdlib.h>

#include "../gpu/vk/compat/hookshot_env.h" /* (env_on: the switches' one rule) */

extern volatile uint32_t hos_frame_seconds_bits;   /* (host/nn_vi.c: the frame's seconds, 0 at a cap of 60) */

static int timed(void) { return __atomic_load_n(&hos_frame_seconds_bits, __ATOMIC_RELAXED) != 0; }
static int fps_log(void) {
    static int on = -1;   /* (read by the game's threads) */
    int v = __atomic_load_n(&on, __ATOMIC_RELAXED);
    if (v < 0) v = env_on("HOS_FPS_LOG"), __atomic_store_n(&on, v, __ATOMIC_RELAXED);
    return v;
}

static OotSoundGate sound_gate = OOT_SOUND_GATE_INIT;
static long long sound_calls, sound_runs;   /* (HOS_FPS_LOG's counts, under sound_lock) */
static SRWLOCK sound_lock = SRWLOCK_INIT;   /* (the job's phases may come from different threads) */

/* f_80435300's head: phase w2, slot the guest address of the pointer to the object whose +0x10 is the game step (the job's own
   load). 0: the job returns at once */
int hos_oot_sound_gate(Ctx *c, uint32_t phase, uint64_t slot) {
    (void)c;
    float step = 1.0f;
    const int t = timed();
    if (t && phase == 0) {
        const uint64_t object = G64(slot);
        const uint64_t time = object ? G64(object) : 0;
        if (time) step = oot_bits_float(*(const uint32_t *)GP(time + 0x10));
    }
    long long ran = -1;
    AcquireSRWLockExclusive(&sound_lock);
    const int run = oot_sound_gate(&sound_gate, phase, step, t);
    if (phase == 0 && fps_log()) {
        sound_runs += run;
        if (!(++sound_calls % 600)) ran = sound_runs, sound_runs = 0;
    }
    ReleaseSRWLockExclusive(&sound_lock);
    if (ran >= 0)
        hos_log("oot: sound job ran %lld of the last 600 frames (step %.3f%s)", ran, step,
                oot_sound_partial(step, t) ? ", held to 60 Hz" : "");
    return run;
}

/* The step f_80435300's phase 0 hands to the sound engine (its float's bits) */
uint32_t hos_oot_sound_step(uint32_t step_bits) {
    return oot_sound_step(step_bits, timed());
}

/* The solver steps of f_838ceb80 / f_838cfc10: game, the game's count; scaled_bits, the float it cut; per_frame_bits, the steps
   of a 60 fps frame (a float) */
uint32_t hos_oot_solver_steps(uint32_t game, uint32_t scaled_bits, uint32_t per_frame_bits) {
    const int32_t steps = oot_solver_steps((int32_t)game, scaled_bits, per_frame_bits, timed());
    if (fps_log()) {
        static volatile LONG64 calls;
        const LONG64 n = InterlockedIncrement64(&calls);
        if (n % 600 == 1)
            hos_log("oot: physics solver steps %d (the game's %d: frame step %.3f x %.0f steps a 60 fps frame)", steps, (int32_t)game,
                    (oot_bits_float(scaled_bits) - 0.001f) / oot_bits_float(per_frame_bits), oot_bits_float(per_frame_bits));
    }
    return (uint32_t)steps;
}

/* The number the follow-surface updates compare the physics' inverse step with (its float's bits): the game's 100, or 100 over
   the frame step while that is under 1 */
uint32_t hos_oot_floor_cut(uint32_t inverse_step_bits) {
    static int on = -1;   /* (read by the physics' job threads) */
    int v = __atomic_load_n(&on, __ATOMIC_RELAXED);
    if (v < 0) v = !(getenv("HOS_FPS_FLOOR") && !atoi(getenv("HOS_FPS_FLOOR"))), __atomic_store_n(&on, v, __ATOMIC_RELAXED);
    const float cut = v ? oot_floor_cut(__atomic_load_n(&hos_frame_seconds_bits, __ATOMIC_RELAXED)) : 100.0f;
    if (fps_log()) {   /* (of every 600 updates: how many kept a tenth, and how many the game's gate would have cut) */
        static volatile LONG64 calls, tenths, game_tenths;
        const float inverse = oot_bits_float(inverse_step_bits);
        if (inverse > cut) InterlockedIncrement64(&tenths);
        if (inverse > 100.0f) InterlockedIncrement64(&game_tenths);
        const LONG64 n = InterlockedIncrement64(&calls);
        if (n % 600 == 0)
            hos_log("oot: floor carry: %lld of the last 600 updates kept a tenth of the floor's velocity (the game's gate: %lld); "
                    "inverse step %.1f, cut at %.1f%s", (long long)InterlockedExchange64(&tenths, 0),
                    (long long)InterlockedExchange64(&game_tenths, 0), inverse, cut, v ? "" : " (HOS_FPS_FLOOR=0: the game's gate)");
    }
    return oot_float_bits(cut);
}

/* The factor f_8263e8e0's turn speed clamp multiplies the applied turn by (its float's bits: the step, or minus the step): one
   over it while the step is under one frame */
uint32_t hos_oot_turn_factor(uint32_t factor_bits) {
    static int on = -1;   /* (read by the game's AI threads) */
    int v = __atomic_load_n(&on, __ATOMIC_RELAXED);
    if (v < 0) v = !(getenv("HOS_FPS_TURN") && !atoi(getenv("HOS_FPS_TURN"))), __atomic_store_n(&on, v, __ATOMIC_RELAXED);
    const uint32_t made = v ? oot_turn_factor(factor_bits, timed()) : factor_bits;
    if (fps_log()) {   /* (of every 600 factors: how many the step's inverse replaced) */
        static volatile LONG64 calls, changed;
        if (made != factor_bits) InterlockedIncrement64(&changed);
        const LONG64 n = InterlockedIncrement64(&calls);
        if (n % 600 == 0)
            hos_log("oot: turn speed clamp: %lld of the last 600 factors were one over the step (factor %.3f%s)",
                    (long long)InterlockedExchange64(&changed, 0), oot_bits_float(factor_bits), v ? "" : ", HOS_FPS_TURN=0: the game's");
    }
    return made;
}

/* What f_82f72df0 takes off the SpStepRate cell's countdown at `at` this update (step_bits the frame step, game its own count):
   the whole frames of the steps while the frames' own time is the step */
static FrameWhole step_rate_frames;   /* (under step_rate_lock: the manager's update may run on any job thread) */
static SRWLOCK step_rate_lock = SRWLOCK_INIT;
uint32_t hos_oot_step_count(uint64_t at, uint32_t step_bits, uint32_t game) {
    static int on = -1;
    int v = __atomic_load_n(&on, __ATOMIC_RELAXED);
    if (v < 0) v = !(getenv("HOS_FPS_STEPRATE") && !atoi(getenv("HOS_FPS_STEPRATE"))), __atomic_store_n(&on, v, __ATOMIC_RELAXED);
    if (!v) return game;
    AcquireSRWLockExclusive(&step_rate_lock);
    const uint32_t count = oot_step_count(&step_rate_frames, at, step_bits, game, timed());
    ReleaseSRWLockExclusive(&step_rate_lock);
    if (fps_log()) {
        static volatile LONG64 calls, taken, game_taken;
        InterlockedAdd64(&taken, count);
        InterlockedAdd64(&game_taken, game);
        const LONG64 n = InterlockedIncrement64(&calls);
        if (n % 600 == 0)
            hos_log("oot: special step rate countdowns: %lld frames counted in the last 600 updates (the game's count: %lld; step %.3f)",
                    (long long)InterlockedExchange64(&taken, 0), (long long)InterlockedExchange64(&game_taken, 0), oot_bits_float(step_bits));
    }
    return count;
}
