# SPDX-License-Identifier: GPL-3.0-or-later
"""The preparation's compute warm, each variant an item of its own (gpu/vk/vk_draw.cpp warm_computes_apart).

prepare_run compiled a compute program's texture variants (up to 64) one after the other on the worker that translated
them. On an Iris Xe (Mesa's Intel driver) one held to 32 lanes takes 15-25 s a variant: four such programs held four of
the ten workers for half an hour, the program count stood still, and the watchdog stopped the preparation at 300 s. Where
the compiles are gated, the variants are compiled after the translation, each its own item on every CPU.

Cuts warm_computes_apart from the source and runs it with stand-ins for the program cache: every variant of every program
warmed exactly once, only while its program is borrowed (its modules alive), one program's variants side by side on
several threads, a failed variant or one without a module left out, a stop that ends the pass, and with a set of programs
only those warmed. And that prepare_run leaves the variants to it on the gated driver, gives it the precompile's plan
(computes_plan: on Mesa's Intel driver the listed programs, not every one) and runs it before the driver's part is written
down. No game or GPU.

python -I -B tests/test_compute_warm_apart.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

HEAD = r"""
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <set>
#include <thread>
#include <unordered_set>
#include <vector>
struct Stage { int module = 1; };
struct Program {
    uint64_t key = 0, variant = 0;
    bool compute = true, failed = false;
    std::vector<Stage> stages{Stage{}};
    std::atomic<bool> alive{true};
};
static int fails = 0;
#define CHECK(c, what) do { if (!(c)) { std::printf("FAIL: %s\n", what); fails++; } } while (0)
static std::atomic<bool> stop{false};
static bool prepare_stopped() { return stop.load(); }
static unsigned usable_cpus() { return 8; }
static void ub_thread_off() {}
#define THREAD_PRIORITY_BELOW_NORMAL 0
static int GetCurrentThread() { return 0; }
static void SetThreadPriority(int, int) {}
static void Sleep(unsigned ms) { std::this_thread::sleep_for(std::chrono::milliseconds(ms)); }
static void compute_compiles_log() {}
static std::vector<uint64_t> keys;
static std::vector<uint64_t> program_cache_compute_keys() { return keys; }
static std::atomic<int> borrowed_now{0}, most_borrowed{0};
static void program_cache_borrow_all(uint64_t key, const std::function<void(std::vector<std::unique_ptr<Program>>&)>& fn) {
    std::vector<std::unique_ptr<Program>> v;
    for (uint64_t i = 0; i < key % 100; i++) {   // (key % 100 variants: up to 64 in the game)
        auto p = std::make_unique<Program>();
        p->key = key, p->variant = i;
        if (key == 7 && i == 1) p->failed = true;          // (a failed variant)
        if (key == 7 && i == 2) p->stages[0].module = 0;   // (one with no module)
        v.push_back(std::move(p));
    }
    const int n = ++borrowed_now;
    int seen = most_borrowed.load();
    while (n > seen && !most_borrowed.compare_exchange_weak(seen, n)) {}
    fn(v);
    for (auto& p : v) p->alive = false;   // (its modules let go, as program_cache_borrow_all does)
    --borrowed_now;
}
"""

MAIN = r"""
static std::mutex seen_mu;
static std::multiset<std::pair<uint64_t, uint64_t>> warmed;
static std::atomic<int> most_of_one{0};
static std::atomic<uint64_t> heavy_running{0};
int main() {
    keys = {164, 7, 103, 1, 132, 110};   // (64, 7, 3, 1, 32 and 10 variants)
    size_t want = 0;
    for (uint64_t k : keys) want += k % 100;
    want -= 2;   // (key 7's failed variant and the one without a module)
    std::vector<size_t> ticks;
    const size_t done = warm_computes_apart([](size_t d, size_t t) { (void)d, (void)t; }, [&](Program& p) {
        CHECK(p.alive.load(), "a variant warmed after its program was let go");
        CHECK(!p.failed && p.stages[0].module, "a failed variant or one with no module warmed");
        if (p.key == 164) {   // (the program of 64 variants: its variants side by side)
            const int n = (int)++heavy_running;
            int seen = most_of_one.load();
            while (n > seen && !most_of_one.compare_exchange_weak(seen, n)) {}
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(p.key == 164 ? 20 : 2));
        if (p.key == 164) --heavy_running;
        std::lock_guard lk(seen_mu);
        warmed.insert({p.key, p.variant});
    }, nullptr);
    CHECK(done == keys.size(), "every program done");
    CHECK(warmed.size() == want, "every variant warmed");
    std::set<std::pair<uint64_t, uint64_t>> once(warmed.begin(), warmed.end());
    CHECK(once.size() == warmed.size(), "a variant warmed twice");
    CHECK(most_of_one.load() >= 4, "one program's variants were not compiled side by side");
    CHECK(most_borrowed.load() <= (int)usable_cpus(), "more programs read in at once than threads");

    // (the plan's programs alone: a key it names that has no program is not one, and the others are never read in)
    {
        const std::unordered_set<uint64_t> only{7, 110, 999};
        std::multiset<uint64_t> of;
        const size_t some = warm_computes_apart(nullptr, [&](Program& p) {
            std::lock_guard lk(seen_mu);
            of.insert(p.key);
        }, &only);
        CHECK(some == 2, "the programs done were not the plan's two");
        CHECK(of.size() == 5 + 10 && of.count(7) == 5 && of.count(110) == 10, "a program the plan does not name was warmed");
        const std::unordered_set<uint64_t> none;
        CHECK(warm_computes_apart(nullptr, [&](Program&) { CHECK(false, "warmed with an empty plan"); }, &none) == 0,
              "an empty plan warmed programs");
    }

    // (stopped meanwhile: the pass ends, every borrowed program let go)
    stop = false;
    keys.clear();
    for (uint64_t k = 0; k < 200; k++) keys.push_back(1000 + k * 100 + 20);
    std::atomic<int> n{0};
    std::thread stopper([] { std::this_thread::sleep_for(std::chrono::milliseconds(100)); stop = true; });
    const size_t partly = warm_computes_apart(nullptr, [&](Program&) { n++, std::this_thread::sleep_for(std::chrono::milliseconds(5)); },
                                              nullptr);
    stopper.join();
    CHECK(partly < keys.size() && borrowed_now.load() == 0, "a stop did not end the pass, or left a program borrowed");
    std::printf(fails ? "compute warm apart: FAILED\n" : "compute warm apart: ok\n");
    return fails ? 1 : 0;
}
"""


def block(text, head):
    start = text.index(head)
    at = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[at] == "{") - (text[at] == "}")
        at += 1
    return text[start:at]


def check_source(draw):
    prepare = block(draw, "bool prepare_run(void (*progress)(size_t done, size_t total), bool background, bool refresh_states) {")
    for needle, why in (
            (': dev.driver_id == VK_DRIVER_ID_INTEL_OPEN_SOURCE_MESA;', "the pass apart is no longer Mesa's Intel driver's default"),
            ('getenv("RX_VK_COMPUTE_WARM_APART")', "the switch is gone"),
            ("(apart && !warming_apart)) return;", "the translation still compiles the variants where they are warmed apart"),
            ("warm_computes_apart(progress, warm_compute, only)", "prepare_run does not run the pass apart"),
            ('const ComputePlan plan = computes_plan(precompile_computes_which(), !env_on("RX_VK_NO_STATE_LIST"));',
             "the pass apart does not take the precompile's plan"),
            ("const std::unordered_set<uint64_t>* only = plan.all ? nullptr : plan.none ? &none : &plan.keys;",
             "the pass apart warms programs the plan leaves out")):
        if needle not in prepare:
            raise SystemExit("prepare_run: " + why)
    if prepare.index("warm_computes_apart(progress, warm_compute, only)") > prepare.rindex("prepared_for.warmed = warmed;"):
        raise SystemExit("prepare_run writes the driver's part down as made before the pass apart")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    check_source(draw)
    fn = block(draw, "size_t warm_computes_apart(void (*progress)(size_t done, size_t total), const std::function<void(Program&)>& warm,\n")
    with tempfile.TemporaryDirectory(prefix="compute-warm-apart-") as tmp:
        src, exe = Path(tmp) / "t.cpp", Path(tmp) / "t"
        src.write_text(HEAD + fn + "\n" + MAIN, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread", str(src), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=120)


if __name__ == "__main__":
    main()
