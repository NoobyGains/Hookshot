// warm_bounded (gpu/vk/warm_bounded.h): every item worked on once, never more alive at once than there are threads, a stop
// honoured before the next item, progress reported. No game, no GPU.
#include <algorithm>
#include "../gpu/vk/warm_bounded.h"

#include <cstdio>
#include <memory>
#include <mutex>

namespace {
int failures = 0;
void expect(bool ok, const char* what) {
    if (!ok) std::printf("FAIL: %s\n", what), failures++;
}

void bounded(size_t n, unsigned threads) {
    std::atomic<int> alive{0}, most{0};
    std::vector<std::atomic<int>> times(n);
    size_t last_tick = 0, ticks = 0;
    const size_t done = warm_bounded::run(n, threads, [&](size_t i) {
        const int now = ++alive;   // (made: a pipeline, in the game)
        int seen = most.load();
        while (now > seen && !most.compare_exchange_weak(seen, now)) {}
        std::this_thread::sleep_for(std::chrono::microseconds(200));
        times[i]++;
        --alive;                   // (let go before the thread takes the next)
    }, [] { return false; }, [&](size_t d) { expect(d >= last_tick, "progress never goes back"), last_tick = d, ticks++; });
    expect(done == n, "every item is done");
    for (size_t i = 0; i < n; i++) expect(times[i] == 1, "each item is worked on exactly once");
    expect(most.load() <= (int)std::max(threads, 1u), "never more alive at once than there are threads");
    expect(n == 0 || most.load() >= 1, "something was made");
    expect(alive.load() == 0, "nothing is left alive at the end");
    expect(ticks >= 1 && last_tick == n, "the last progress report is the whole count");
}

void stopped() {
    std::atomic<size_t> worked{0};
    std::atomic<bool> stop{false};
    const size_t done = warm_bounded::run(100000, 4, [&](size_t) {
        if (++worked == 50) stop = true;
    }, [&] { return stop.load(); }, [](size_t) {});
    expect(done == worked.load() && done >= 50 && done < 100000, "a stop ends the work before the next item, and what was done is counted");
}

// run_or_go_on: one item the "driver" never lets go of. The call goes on once go_on says so, takes no item after that, and the
// stuck worker keeps the state it shares (a shared_ptr in the item, as precompile_warm's): nothing it touches is the caller's
struct Held {
    std::atomic<size_t> worked{0}, after{0};
    std::atomic<bool> release{false}, went_on{false};
};
void goes_on_from_a_stuck_worker() {
    const auto held = std::make_shared<Held>();
    bool asked_none_left = false;
    const auto t0 = std::chrono::steady_clock::now();
    const warm_bounded::Ended e = warm_bounded::run_or_go_on(40, 4, [held](size_t i) {
        if (held->went_on.load()) held->after++;   // (an item taken after the call went on)
        if (i == 39) {   // (the last item: stuck until released, long after the call has returned)
            while (!held->release.load()) std::this_thread::sleep_for(std::chrono::milliseconds(5));
            return;
        }
        held->worked++;
    }, [] { return false; }, [](size_t) {}, [&](bool none_left) {
        if (!none_left) return false;
        asked_none_left = true;
        return std::chrono::steady_clock::now() - t0 > std::chrono::milliseconds(300);
    });
    held->went_on = true;
    expect(e.gone_on, "a stuck worker: the run goes on");
    expect(asked_none_left, "go_on is told once no item is left to hand out");
    expect(e.done == 39 && held->worked == 39, "every other item done, and counted");
    expect(std::chrono::steady_clock::now() - t0 < std::chrono::seconds(10), "it went on without waiting for the stuck worker");
    held->release = true;   // (the driver answers at last: the worker ends on its own, its state still alive)
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    expect(held->after == 0, "no item is taken after the run went on");
}
// run_or_go_on with nothing stuck: every item, joined, never gone on; a stop ends it without going on
void no_go_on_without_a_stall() {
    std::atomic<size_t> worked{0};
    const warm_bounded::Ended e = warm_bounded::run_or_go_on(500, 3, [&](size_t) { worked++; }, [] { return false; },
                                                             [](size_t) {}, [](bool) { return false; });
    expect(!e.gone_on && e.done == 500 && worked == 500, "nothing stuck: every item done, not gone on");
    std::atomic<bool> stop{false};
    const warm_bounded::Ended s = warm_bounded::run_or_go_on(100000, 2, [&](size_t i) {
        if (i == 10) stop = true;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }, [&] { return stop.load(); }, [](size_t) {}, [](bool) { return false; });
    expect(!s.gone_on && s.done >= 11 && s.done < 100000, "a stop ends it without going on");
}
void rule() {
    // (stall_s, still_s, none left, faulted)
    expect(!warm_bounded::goes_on(30, 29.9, true, false), "under the stall: waited for");
    expect(warm_bounded::goes_on(30, 30.1, true, false), "past the stall with every item handed out: the last stragglers, gone on");
    expect(!warm_bounded::goes_on(30, 300, false, false), "stuck early with no fault: waited for (the watchdog's)");
    expect(warm_bounded::goes_on(30, 31, false, true), "after a fault in the driver: anywhere in the run");
    expect(!warm_bounded::goes_on(0, 1e9, true, true), "RX_VK_PRECOMPILE_STALL_S=0: wait for all");
    expect(!warm_bounded::goes_on(-5, 1e9, true, true), "a negative stall: wait for all");
}
}   // namespace

int main() {
    bounded(0, 8);
    bounded(1, 8);
    bounded(500, 1);
    bounded(2000, 6);
    bounded(300, 0);   // (no thread count: one)
    stopped();
    goes_on_from_a_stuck_worker();
    no_go_on_without_a_stall();
    rule();
    // the marker: only a warm that got to its end in a process that plays; never the preparation's own process
    expect(warm_bounded::leaves_marker(false, true, false), "warm_bounded::leaves_marker(false, true, false)");
    expect(!warm_bounded::leaves_marker(true, true, false), "!warm_bounded::leaves_marker(true, true, false)");    // (--prepare-shaders: its cache does not answer the game's asks)
    expect(!warm_bounded::leaves_marker(false, false, false), "!warm_bounded::leaves_marker(false, false, false)");  // (not through)
    expect(!warm_bounded::leaves_marker(false, true, true), "!warm_bounded::leaves_marker(false, true, true)");    // (the window was closed)
    expect(!warm_bounded::leaves_marker(true, false, true), "!warm_bounded::leaves_marker(true, false, true)");
    if (failures) return std::printf("%d checks failed\n", failures), 1;
    std::printf("warm_bounded: ok\n");
    return 0;
}
