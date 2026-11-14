// (hookshot) How many of the GPU driver's compute compiles run at once (vk_draw.cpp cached_compute and prepare_run's
// warm_compute: the shader preparation, the precompile, the mesh fallback's compute pipelines and play's own builds).
//
// The preparation ran one on every worker: half the CPUs in its first part, every CPU in the precompile. That is right
// where a compile holds a few hundred MB (prepare_workers.h: 400-520 MB a worker on AMD's Windows driver). Mesa's Intel
// driver held gigabytes for each of the game's large compute programs while every one was held to 32 lanes, and an
// integrated GPU has no memory of its own to hold anything else in: on an i9-13900H with Iris Xe and 32 GB (20 threads,
// Mesa 26.2.4) the process passed 24 GB of private memory and 7 GB of swap and Linux killed it, in the build's last step
// and then at every start of the game (issue 496 is the same compiler in play: four at once froze an A750's PC).
//
// With only the programs that see their lanes held to 32 (compute_pin.h), ordinary compiles there were measured one at
// a time: 16a842f009aff538 (730 KB of SPIR-V) added 0.8-1 GB over 23-25 s; one at the lanes the driver chose added
// 300 MB at most. So each compile is weighed (kPinnedMB, kFreeMB) and a compile starts beside the ones running only
// while the weights of all of them fit in what was available past kReserveMB when the first one started, and the system
// still has its weight available past kReserveMB now (for whatever else took the memory meanwhile). One always starts
// when none runs; never more than kMost. A worker whose compile has to wait, waits: its program is compiled when its
// turn comes, never left out. The pinned programs of 2,000 phis or more (SPIR-V's OpPhi: Stage::phis) are the ones that
// took minutes and gigabytes: 7a548525c239b91b (2,534 phis) 7.6 GB and 531 s, abccf81b45c5eb50 (2,190, in the shipped
// list) past 5.6 GB and not done after 15 minutes; others there took 24-34 s and 1-2.2 GB, and nothing below 2,000 took more
// than 2.2 GB. So a pinned compile of kHeavyPhis or more weighs kHeavyMB: beside it only what still fits. The preparation's
// watchdog lets a compile with a CPU at work run long (vk_main.cpp).
// The mesh fallback's compute stages (the GPU has no mesh shaders) are large, and their phis do not show what they cost: with
// their records written unrolled (emit_spirv_mesh.cpp MeshFallbackEpilogue, before its loop) 6fcc901fbc8b73c7 (58 phis) took
// 3.8 GB and 207 s, and three at once took a test run on that PC from 7 GB to 14.7 GB, with 1.5 GB left to the desktop, when
// each weighed kPinnedMB. Written by a loop, the largest measured (6fcc901fbc8b73c7, 1cd6ed71bb3f651e, 0c2412f39d385c07)
// peak at 1.55 GB; most take under 200 MB. So a pinned one weighs kMeshMB, twice that, as kPinnedMB is.
//
// What a finished compile held does not go back to the system by itself: the compile runs on whichever worker's turn it
// is, glibc gives each thread its own heap, and the little the compile leaves behind (the pipeline) sits on top of the
// memory it freed, which pins it. With 20 workers taking turns the process stood at 12.6 GB with one compile running,
// where it had started the precompile at 5.5 GB. So a compile that held its turn for kTrimAfterMs or longer hands the
// freed memory back when it leaves (trims(), glibc's malloc_trim; nothing on other C libraries).
//
// On by default on Mesa's Intel driver alone, where it was measured. RX_VK_COMPUTE_AT_ONCE=<n>: at most n at once on any
// GPU, whatever the memory; 0: no limit, as before. tests/test_compute_gate.py.
#pragma once

#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>

namespace compute_gate {

constexpr uint64_t kReserveMB = 4096;   // (memory left to the rest of the PC, as prepare_workers.h)
constexpr uint64_t kPinnedMB = 2048;    // (an ordinary compile held to 32 lanes: twice 16a842f009aff538's measured peak)
constexpr uint32_t kHeavyPhis = 2000;   // (a pinned program this big may take minutes and gigabytes)
constexpr uint64_t kHeavyMB = 8192;     // (7a548525c239b91b's measured 7.6 GB)
constexpr uint64_t kMeshMB = 3072;     // (a mesh fallback stage: twice the largest measured, 1.55 GB)
constexpr uint64_t kFreeMB = 512;       // (one at the lanes the driver chooses: the largest measured, with room)
constexpr unsigned kMost = 16;
constexpr uint64_t kUnknownMB = UINT64_MAX;   // (the system does not say what is available: one at a time)
constexpr int64_t kTrimAfterMs = 1000;        // (a compile this long held memory worth handing back; the short ones did not)

/// A compile's weight: held to 32 lanes or not, how many phis its SPIR-V has, and whether it is a mesh fallback stage
inline uint64_t weight(bool pinned, uint32_t phis, bool mesh_fallback = false) {
    return !pinned ? kFreeMB : phis >= kHeavyPhis ? kHeavyMB : mesh_fallback ? kMeshMB : kPinnedMB;
}

/// What the compiles may hold together, with avail_mb available when the first one starts: what is past kReserveMB.
/// 0 (one at a time) when the system does not say
inline uint64_t budget_for(uint64_t avail_mb) {
    return avail_mb == kUnknownMB || avail_mb <= kReserveMB ? 0 : avail_mb - kReserveMB;
}

/// Whether a compile of weight_mb may start now, running compiles holding running_mb by their weights.
/// limit: a count that was asked for (RX_VK_COMPUTE_AT_ONCE), 0 for none. by_memory: the budget and the memory decide.
/// Neither: no gate. With none running: always (the preparation never stops for lack of memory, it only stops adding to
/// what it holds)
inline bool may_start(unsigned running, uint64_t running_mb, uint64_t weight_mb, unsigned limit, bool by_memory,
                      uint64_t budget_mb, uint64_t avail_mb) {
    if (!limit && !by_memory) return true;
    if (!running) return true;
    if (limit && running >= limit) return false;
    if (!by_memory) return true;
    if (running >= kMost || running_mb + weight_mb > budget_mb) return false;
    return avail_mb != kUnknownMB && avail_mb >= kReserveMB + weight_mb;
}

/// Whether a compile that held its turn for held_ms hands the freed memory back to the system as it leaves: only where
/// there is a gate (none: nothing changes), and only after a long one
inline bool trims(bool gated, int64_t held_ms) { return gated && held_ms >= kTrimAfterMs; }

/// The gate itself. No gate until set: every enter() returns at once
class Gate {
public:
    /// (before the first enter, or at any time: the waiting compiles see it at their next look)
    void set(unsigned limit, bool by_memory, uint64_t budget_mb = 0) {
        std::lock_guard lk(mu);
        limit_ = limit, by_memory_ = by_memory, budget_mb_ = budget_mb;
        cv.notify_all();
    }
    bool on() {
        std::lock_guard lk(mu);
        return limit_ || by_memory_;
    }
    /// Waits for a turn for a compile of weight_mb. avail(): the memory available now, in MB (kUnknownMB when the system
    /// does not say), asked only when it decides. stop(): looked at while waiting; once true the wait ends and enter
    /// returns false, with no turn taken (the caller does not compile). True: the turn is taken, leave(weight_mb) gives
    /// it back
    template <class Avail, class Stop>
    bool enter(uint64_t weight_mb, Avail&& avail, Stop&& stop) {
        std::unique_lock lk(mu);
        bool waited = false;
        for (;;) {
            const bool memory_decides = by_memory_ && running_ && running_ < kMost && (!limit_ || running_ < limit_) &&
                                        running_mb_ + weight_mb <= budget_mb_;
            if (may_start(running_, running_mb_, weight_mb, limit_, by_memory_, budget_mb_, memory_decides ? avail() : kUnknownMB))
                break;
            if (stop()) return false;
            if (!waited) waited = true, waits_++;
            // (a look every 250 ms as well as at each leave(): memory comes back without one, and stop() is only asked here)
            cv.wait_for(lk, std::chrono::milliseconds(250));
        }
        running_++, running_mb_ += weight_mb;
        most_ = std::max(most_, running_);
        return true;
    }
    void leave(uint64_t weight_mb) {
        {
            std::lock_guard lk(mu);
            running_--, running_mb_ -= std::min(running_mb_, weight_mb);
        }
        cv.notify_all();
    }
    /// (for the log: the most that ran at once, and how many compiles had to wait for a turn)
    void seen(unsigned* most, uint64_t* waits) {
        std::lock_guard lk(mu);
        *most = most_, *waits = waits_;
    }

private:
    std::mutex mu;
    std::condition_variable cv;
    unsigned limit_ = 0, running_ = 0, most_ = 0;
    bool by_memory_ = false;
    uint64_t budget_mb_ = 0, running_mb_ = 0, waits_ = 0;
};

}  // namespace compute_gate
