// (hookshot) Work done one item at a time on a few threads, each item made, used and let go before the thread takes the
// next: no more than `threads` items are alive at once, however many there are (vk_draw.cpp precompile_warm: every noted
// pipeline built into the pipeline cache and destroyed, where keeping them all ready needs more memory than some PCs have).
// A run can also go on without workers the GPU driver never lets go of (run_or_go_on, goes_on).
// tests/test_warm_bounded.py, tests/test_warm_stall.py.
#pragma once

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <memory>
#include <thread>
#include <utility>
#include <vector>

namespace warm_bounded {

/// How a run_or_go_on ended: the items done, and whether it went on without workers that were still busy
struct Ended {
    size_t done = 0;
    bool gone_on = false;
};

/// run, for work a GPU driver can hold for good (a pipeline compile it never returns from: #2107, "stuck at 99%"). go_on(none_left)
/// is asked on the calling thread with each tick, none_left true once no item will be taken any more (every one handed out, or
/// stop() said so); once it answers true, no item is taken after that and the call returns at once, the workers still busy left
/// to end on their own (detached), however long that takes. So the workers own what they use: work and stop are copied into a
/// state they share with this call, and work must hold what it touches by value (a shared_ptr), never the caller's stack
template <class Work, class Stop, class Tick, class GoOn>
Ended run_or_go_on(size_t n, unsigned threads, Work work, Stop stop, Tick&& tick, GoOn&& go_on) {
    struct Shared {
        Work work;
        Stop stop;
        std::atomic<size_t> next{0}, done{0};
        std::atomic<unsigned> busy{0};
        std::atomic<bool> left{false};
        Shared(Work w, Stop s) : work(std::move(w)), stop(std::move(s)) {}
    };
    const auto sh = std::make_shared<Shared>(std::move(work), std::move(stop));
    const unsigned count = n ? (unsigned)std::min<size_t>(threads ? threads : 1, n) : 0;
    sh->busy = count;
    std::vector<std::thread> pool;
    for (unsigned t = 0; t < count; t++)
        pool.emplace_back([sh, n] {
            for (;;) {
                if (sh->left.load() || sh->stop()) break;
                const size_t i = sh->next.fetch_add(1);
                if (i >= n) break;
                sh->work(i);
                sh->done.fetch_add(1);
            }
            sh->busy.fetch_sub(1);
        });
    while (sh->busy.load()) {
        tick(sh->done.load());
        if (go_on(sh->next.load() >= n || sh->stop())) {
            sh->left = true;
            for (std::thread& t : pool) t.detach();
            tick(sh->done.load());
            return {sh->done.load(), true};
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    for (std::thread& t : pool) t.join();
    tick(sh->done.load());
    return {sh->done.load(), false};
}

/// work(i) for every i < n, on up to `threads` threads (at least one), each call finished before its thread takes another
/// item. stop(): asked before each item; once true no new item is taken. tick(done): called on the calling thread about
/// every 50 ms while the others work, and once at the end. Returns how many items were done
template <class Work, class Stop, class Tick>
size_t run(size_t n, unsigned threads, Work&& work, Stop&& stop, Tick&& tick) {
    return run_or_go_on(n, threads, std::forward<Work>(work), std::forward<Stop>(stop), tick, [](bool) { return false; }).done;
}

/// Whether a run whose workers have finished nothing for still_s seconds goes on without them (vk_draw.cpp precompile_warm, by
/// the rule predict_run keeps): never with stall_s 0 (RX_VK_PRECOMPILE_STALL_S=0: wait for all); otherwise once nothing has
/// finished for longer than stall_s, and only when no item is left to hand out (the last stragglers, never the bulk: a slow
/// driver that still works keeps its pipelines), or when the driver faulted in this run (it can stop answering after one, so
/// then anywhere in the run). Stuck early with no fault is left to wait: the --prepare-shaders run's watchdog ends that
inline bool goes_on(int stall_s, double still_s, bool none_left, bool faulted) {
    return stall_s > 0 && still_s > (double)stall_s && (none_left || faulted);
}


/// Whether a warm may leave the marker that says every noted pipeline is in the pipeline cache (hookshot_pipelines.bin.built),
/// after which a start loads at create calls and builds nothing itself. Only a warm that got to its end, and only in a process
/// that plays: on NVIDIA the cache a --prepare-shaders process writes does not answer the asks of the play process that
/// follows (0 of 32 of a sample; 3,720 of 3,880 pipelines "in no cache" in the first session, compiled in play with draws left
/// out), while what a play process builds is answered from then on. So the preparation's process never leaves the marker,
/// and the first start of the game after it warms again, itself
inline bool leaves_marker(bool prepare_only, bool got_to_the_end, bool stopped) { return !prepare_only && got_to_the_end && !stopped; }
} // namespace warm_bounded
