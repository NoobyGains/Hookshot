// compute_gate (gpu/vk/compute_gate.h): how many of the driver's compute compiles run at once. The budget the memory gives,
// the rule for one more by the compiles' weights, and the gate itself under threads: one always let through, one more only
// while its weight fits and the memory is there, never more than an asked limit, a stop that ends a wait without a turn.
// No game, no GPU.
#include "../gpu/vk/compute_gate.h"

#include <atomic>
#include <cstdio>
#include <thread>
#include <vector>

using compute_gate::budget_for;
using compute_gate::kFreeMB;
using compute_gate::kMost;
using compute_gate::kPinnedMB;
using compute_gate::kReserveMB;
using compute_gate::kUnknownMB;
using compute_gate::may_start;

namespace {
int failures = 0;
void expect(bool ok, const char* what) {
    if (!ok) std::printf("FAIL: %s\n", what), failures++;
}

void rules() {
    expect(compute_gate::weight(true, 0) == kPinnedMB && compute_gate::weight(false, 0) == kFreeMB && kPinnedMB > kFreeMB,
           "a compile held to 32 lanes weighs more");
    expect(compute_gate::weight(true, 2190) == compute_gate::kHeavyMB && compute_gate::weight(true, 1892) == kPinnedMB &&
               compute_gate::weight(false, 12329) == kFreeMB && compute_gate::kHeavyMB > kPinnedMB,
           "a pinned compile of 2,000 phis or more weighs the most; at the driver's lanes the phis do not count");
    expect(compute_gate::weight(true, 58, true) == compute_gate::kMeshMB && compute_gate::kMeshMB > kPinnedMB &&
               compute_gate::kHeavyMB > compute_gate::kMeshMB && compute_gate::weight(true, 80000, true) == compute_gate::kHeavyMB &&
               compute_gate::weight(false, 58, true) == kFreeMB && compute_gate::weight(true, 58) == kPinnedMB,
           "a pinned mesh fallback stage weighs more than an ordinary pinned compile, whatever its phis");
    expect(budget_for(0) == 0 && budget_for(kReserveMB) == 0 && budget_for(kUnknownMB) == 0, "no budget: one at a time");
    expect(budget_for(kReserveMB + 100) == 100, "the budget: what is past the reserve");

    const uint64_t plenty = uint64_t(1) << 40, budget = 16 * 1024;
    // (no gate)
    expect(may_start(99, 0, kPinnedMB, 0, false, 0, 0), "no limit and no memory rule: no gate");
    // (none running: always, whatever the memory)
    expect(may_start(0, 0, kPinnedMB, 0, true, 0, 0) && may_start(0, 0, kPinnedMB, 1, false, 0, 0), "the first one always starts");
    // (an asked limit: the limit alone)
    expect(!may_start(4, 0, kFreeMB, 4, false, 0, plenty) && may_start(3, 0, kFreeMB, 4, false, 0, 0), "an asked limit alone");
    // (by memory: the weights in the budget, and the weight available now)
    expect(may_start(1, kPinnedMB, kFreeMB, 0, true, budget, plenty), "one more that fits");
    expect(!may_start(1, budget - kFreeMB + 1, kFreeMB, 0, true, budget, plenty), "not one more past the budget");
    expect(!may_start(1, kFreeMB, kFreeMB, 0, true, budget, kReserveMB + kFreeMB - 1), "not one more without the memory now");
    expect(may_start(1, kFreeMB, kFreeMB, 0, true, budget, kReserveMB + kFreeMB), "one more with exactly its memory");
    expect(!may_start(1, kFreeMB, kFreeMB, 0, true, budget, kUnknownMB), "memory unknown now: no more than one");
    expect(!may_start(kMost, 0, 0, 0, true, plenty, plenty), "never more than kMost");
    expect(!may_start(1, kFreeMB, kFreeMB, 0, true, 0, plenty), "no budget: one at a time");
    // (the PC this was measured on: about 16 GB past the reserve: 8 held to 32 lanes, or kMost others)
    expect(may_start(7, 7 * kPinnedMB, kPinnedMB, 0, true, budget, plenty) &&
               !may_start(8, 8 * kPinnedMB, kPinnedMB, 0, true, budget, plenty) &&
               may_start(kMost - 1, (kMost - 1) * kFreeMB, kFreeMB, 0, true, budget, plenty),
           "16 GB past the reserve: 8 held to 32 lanes, or 16 others");
    // (the freed memory handed back: only where there is a gate, and only after a long compile)
    expect(!compute_gate::trims(false, 60000), "no gate: nothing is handed back, as before");
    expect(!compute_gate::trims(true, compute_gate::kTrimAfterMs - 1), "a short compile hands nothing back");
    expect(compute_gate::trims(true, compute_gate::kTrimAfterMs) && compute_gate::trims(true, 600000), "a long one does");
}

/// `threads` threads each take `each` turns of weight_mb at a gate; avail_mb is what the memory reads. The most that ran at once
int most_running(unsigned limit, bool by_memory, uint64_t budget_mb, uint64_t weight_mb, uint64_t avail_mb, unsigned threads,
                 int each, uint64_t* waits = nullptr) {
    compute_gate::Gate gate;
    gate.set(limit, by_memory, budget_mb);
    std::atomic<int> running{0}, most{0}, turns{0};
    std::vector<std::thread> pool;
    for (unsigned t = 0; t < threads; t++)
        pool.emplace_back([&] {
            for (int i = 0; i < each; i++) {
                if (!gate.enter(weight_mb, [&] { return avail_mb; }, [] { return false; })) continue;
                const int now = ++running;
                int seen = most.load();
                while (now > seen && !most.compare_exchange_weak(seen, now)) {}
                std::this_thread::sleep_for(std::chrono::microseconds(300));
                --running;
                turns++;
                gate.leave(weight_mb);
            }
        });
    for (std::thread& t : pool) t.join();
    expect(turns.load() == (int)threads * each, "every compile got its turn: none is left out");
    expect(running.load() == 0, "nothing is left running");
    unsigned gate_most = 0;
    uint64_t gate_waits = 0;
    gate.seen(&gate_most, &gate_waits);
    expect((int)gate_most == most.load(), "the gate's own count of the most at once is what ran");
    if (waits) *waits = gate_waits;
    return most.load();
}

void gate() {
    const uint64_t plenty = uint64_t(1) << 30, none = 0;
    uint64_t waits = 0;
    expect(most_running(0, false, 0, kPinnedMB, none, 8, 200) > 1, "no gate: they run together, as before");
    expect(most_running(1, false, 0, kFreeMB, plenty, 8, 200, &waits) == 1 && waits > 0, "an asked 1: one at a time");
    {
        const int most = most_running(3, false, 0, kFreeMB, none, 8, 200);
        expect(most <= 3 && most >= 2, "an asked 3: up to three, whatever the memory");
    }
    {
        const int most = most_running(0, true, 3 * kPinnedMB, kPinnedMB, plenty, 8, 200);
        expect(most <= 3 && most >= 2, "a budget of three pinned compiles: up to three of them");
    }
    {
        const int most = most_running(0, true, 3 * kPinnedMB, kFreeMB, plenty, 20, 100);
        expect(most > 3 && most <= (int)kMost, "the same budget: more of the light ones, never past kMost");
    }
    // (the budget allows several, but there is not a compile's worth of memory available now: one at a time, and still every one)
    expect(most_running(0, true, 16 * 1024, kPinnedMB, none, 8, 100) == 1, "within the budget without the memory: one at a time");
    expect(most_running(0, true, 16 * 1024, kPinnedMB, kReserveMB + kPinnedMB - 1, 8, 100) == 1, "one MB short: one at a time");
}

void stopped() {
    // (one holds the only turn; the one waiting behind it is told to stop: it gets no turn, and does not hang)
    compute_gate::Gate gate;
    gate.set(1, false);
    expect(gate.enter(kFreeMB, [] { return uint64_t(0); }, [] { return false; }), "the first turn");
    std::atomic<bool> stop{false}, returned{false}, got{true};
    std::thread waiter([&] {
        got = gate.enter(kFreeMB, [] { return uint64_t(0); }, [&] { return stop.load(); });
        returned = true;
    });
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    expect(!returned.load(), "the second waits while the first runs");
    stop = true;
    waiter.join();
    expect(returned.load() && !got.load(), "a stop ends the wait with no turn taken");
    gate.leave(kFreeMB);
    stop = false;
    expect(gate.enter(kFreeMB, [] { return uint64_t(0); }, [] { return true; }), "a free gate gives a turn even when stopped");
    gate.leave(kFreeMB);
}

void memory_returns() {
    // (the second waits for memory, not for a turn: it starts when the memory is back, without any leave())
    compute_gate::Gate gate;
    gate.set(0, true, 16 * 1024);
    std::atomic<uint64_t> avail{0};
    expect(gate.enter(kPinnedMB, [&] { return avail.load(); }, [] { return false; }), "the first turn");
    std::atomic<bool> entered{false};
    std::thread waiter([&] { entered = gate.enter(kPinnedMB, [&] { return avail.load(); }, [] { return false; }); });
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    expect(!entered.load(), "no second compile while the memory is short");
    avail = kReserveMB + kPinnedMB;
    waiter.join();
    expect(entered.load(), "the second starts once the memory is available again");
    gate.leave(kPinnedMB);
    gate.leave(kPinnedMB);
}
}   // namespace

int main() {
    rules();
    gate();
    stopped();
    memory_returns();
    if (failures) return std::printf("%d checks failed\n", failures), 1;
    std::printf("compute_gate: ok\n");
    return 0;
}
