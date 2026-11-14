# SPDX-License-Identifier: GPL-3.0-or-later
"""The first start's warm goes on from a pipeline the GPU driver never finishes, and a start closed in it is not counted.

Where the GPU has mesh shaders, programs are loaded when the game creates them (RX_VK_LOAD=create, #2760), and the start after
every preparation builds each noted pipeline into the pipeline cache first (precompile_warm, #2869): the Builder's
--prepare-shaders run does it, and so does the game's own first start after it. That warm had no stall guard: a pipeline the
driver never returned from (#2107, "stuck at 99%") held it for ever, the game's start-up screen with it, and the Builder's run
until its watchdog ended it after 5 minutes and left the game unprepared (hookshot_prepare_skipped). precompile_run and
predict_run went on from such stragglers after 30 s; the warm did not. And a start closed in it counted as one that did not get
through, so two closes ("it looked stuck") took the notes as they were, and play compiled the rest with draws left out.

Compiled from the real source (gpu/vk/vk_draw.cpp precompile_warm, gpu/vk/warm_bounded.h), with stand-ins for the driver, the
program cache and the files:

- every noted pipeline built and let go, then every compute program's; the first pipeline alone; the bar counts both, to its end;
  the cache saved before the marker, which is written; the unfinished-start count removed;
- the last pipelines never finish: after RX_VK_PRECOMPILE_STALL_S with nothing finished, the warm goes on (the workers left in
  the driver), saves nothing and leaves no marker, keeps the start counted, and says so; the same for a compute pipeline;
- a slow driver that still finishes pipelines, each program longer than the limit: no stop (each pipeline counts as it ends);
- the driver faulted, then nothing finishes, early in the run: it goes on; stuck early with no fault: waited for (the
  --prepare-shaders run's watchdog ends that);
- closed in it: the count written back as it was; after two starts that did not get through, the notes are taken as they are;
- the preparation's own process: everything built, no marker, no save of its own (the run saves next, as its last part);
- RX_VK_WARM_THREADS sets the worker count.
And in the source: precompile_run loads at create calls after a warm that went on, not the keep-everything precompile.

python -I -B tests/test_warm_stall.py --cxx clang++
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cxx", "{cxx}"]


def block(text, marker):
    """The function that starts at marker, through its closing brace"""
    if text.count(marker) != 1:
        raise SystemExit("expected one %r" % marker)
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


HEAD = r'''
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include "warm_bounded.h"
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "CHECK failed line %d: %s\n", __LINE__, #c); std::_Exit(7); } } while (0)
using VkPipeline = uintptr_t;
using VkPrimitiveTopology = int;
using VkResult = int;
constexpr VkResult VK_SUCCESS = 0;
constexpr VkPipeline VK_NULL_HANDLE = 0;
struct NvnState { int unused = 0; };
struct Targets {};
struct PipeNote { NvnState s; uint32_t topo = 3; };
struct NoteRef { uint64_t key = 0, prog = 0, variant = 0; int64_t at = 0; };
struct Stage { uintptr_t module = 1; };
struct Program { uint64_t key = 0, variant = 0; bool compute = false, failed = false; std::vector<Stage> stages{Stage{}}; };
struct VkComputePipelineCreateInfo { uint64_t key = 0; };
struct { uintptr_t device = 1; } dev;
static bool env_on(const char* n) { const char* v = std::getenv(n); return v && *v && std::strcmp(v, "0"); }   // (compat/hookshot_env.h)
static std::string dir() { return std::getenv("FIXTURE_DIR"); }
std::string pipe_notes_path() { return dir() + "/hookshot_pipelines.bin"; }
std::string precompile_built_path() { return pipe_notes_path() + ".built"; }
static std::string mode;
static int programs_n = 30, per_program = 3, computes_n = 10;
static constexpr uint64_t kStuck = 7, kStuckCompute = 1003;
static std::atomic<int> built{0}, destroyed{0}, inside{0}, faults{0}, computes_built{0}, saves{0}, markers{0}, borrowed_open{0};
static std::atomic<bool> first_was_alone{true}, first_seen{false}, left_noted{false}, stop{false}, saved_before_marker{true};
static std::atomic<size_t> marker_total{0};
static std::string logged;
static std::mutex log_mu;
void logf(const char* f, ...) {
    char b[2048];
    va_list a;
    va_start(a, f);
    std::vsnprintf(b, sizeof b, f, a);
    va_end(a);
    std::lock_guard lk(log_mu);
    logged += b;
    logged += "\n";
}
bool prepare_stopped() { return stop.load(); }
int driver_faults() { return faults.load(); }
void prepare_left_workers_note() { left_noted = true; }
void prepare_progress_log(const char*, size_t, size_t, std::chrono::steady_clock::time_point, std::chrono::steady_clock::time_point&) {}
void ub_thread_off() {}
unsigned usable_cpus() { return std::max(1u, std::thread::hardware_concurrency()); }
void pcache_init() {}
void pipeline_cache_save(bool force) { CHECK(force); saves++; }
void precompile_built_write(size_t notes) {
    if (!saves.load() && mode != "two-failed") saved_before_marker = false;
    marker_total = notes, markers++;
}
std::vector<NoteRef> pipe_notes_refs() {
    std::vector<NoteRef> v;
    uint64_t key = 1;
    for (int p = 1; p <= programs_n; p++)
        for (int k = 0; k < per_program; k++) v.push_back(NoteRef{key++, (uint64_t)p, 0, 16});
    v.push_back(NoteRef{key++, 2, 99, 16});   // (a variant no kept program answers)
    return v;
}
std::vector<uint64_t> program_cache_compute_keys() {
    std::vector<uint64_t> v;
    for (int i = 0; i < computes_n; i++) v.push_back(1000 + (uint64_t)i);
    return v;
}
void program_cache_borrow(uint64_t key, const std::function<void(Program&)>& fn) {
    Program p;
    p.key = key, p.compute = key >= 1000;
    borrowed_open++;
    fn(p);
    borrowed_open--;
}
void ensure_layout(Program&) {}
bool taau_key(uint64_t) { return false; }
bool pipe_note_at(FILE* f, int64_t, PipeNote* out) { CHECK(f && out); return true; }
Targets note_targets(const PipeNote&) { return {}; }
static void hang() { for (;;) std::this_thread::sleep_for(std::chrono::hours(1)); }
VkPipeline build_graphics(const Program& p, const NvnState&, const Targets&, VkPrimitiveTopology) {
    CHECK(!p.compute);
    ++inside;
    const bool first = !first_seen.exchange(true);
    // (the driver never answers; never on the first pipeline, which the others wait for)
    if (!first && ((mode == "stuck-last" && p.key == kStuck) || mode == "fault-early" || mode == "stuck-early")) {
        if (mode == "fault-early") faults++;   // (caught in the driver: "the driver faulted compiling")
        hang();
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(mode == "slow" ? 300 : first ? 200 : 1));
    if (first && inside.load() != 1) first_was_alone = false;   // (another began while the first was being built)
    --inside;
    if (mode == "closed" && built.load() >= 20) stop = true;   // (the window closed)
    return (VkPipeline)(0x100 + ++built);
}
VkComputePipelineCreateInfo compute_pipeline_info(const Program& p, bool) { return {p.key}; }
bool precompile_compute_quick(VkComputePipelineCreateInfo& ci) { (void)ci; return false; }   // (Intel's quick compute builds: not Intel here)
VkResult cached_compute(const VkComputePipelineCreateInfo* ci, VkPipeline* out) {
    if (mode == "stuck-compute" && ci->key == kStuckCompute) hang();
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    *out = (VkPipeline)(0x10000 + ++computes_built);
    return VK_SUCCESS;
}
void vkDestroyPipeline(uintptr_t, VkPipeline, const void*) { ++destroyed; }
static std::atomic<size_t> last_done{0}, last_total{0};
void progress(size_t done, size_t total) {
    CHECK(done <= total);
    CHECK(done >= last_done.load() || total != last_total.load());   // (the bar never goes back)
    last_done = done, last_total = total;
}
static int warming() {   // (the unfinished-start count: -1 none)
    FILE* f = std::fopen((precompile_built_path() + ".warming").c_str(), "rb");
    if (!f) return -1;
    int n = -2;
    if (std::fscanf(f, "%d", &n) != 1) n = -2;
    std::fclose(f);
    return n;
}
'''

MAIN = r'''
int main(int argc, char** argv) {
    CHECK(argc == 2);
    mode = argv[1];
    if (FILE* f = std::fopen(pipe_notes_path().c_str(), "wb")) std::fclose(f);   // (the notes file the workers open)
    const char* had = std::getenv("FIXTURE_WARMING");
    if (had) {
        FILE* f = std::fopen((precompile_built_path() + ".warming").c_str(), "wb");
        std::fprintf(f, "%s\n", had);
        std::fclose(f);
    } else {
        std::remove((precompile_built_path() + ".warming").c_str());
    }
    if (mode == "slow") programs_n = 3, per_program = 6;   // (each program 1.8 s, past the 1 s stall: only per pipeline counts)
    if (mode == "fault-early" || mode == "stuck-early") programs_n = 400;   // (stuck before every program is handed out)
    const int notes = programs_n * per_program + 1, all_total = notes + computes_n;
    const auto t0 = std::chrono::steady_clock::now();
    const bool gone_on = precompile_warm(progress);
    const double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::printf("%s", logged.c_str());
    std::fflush(stdout);
    CHECK(mode != "stuck-early");   // (no fault and stuck early: waited for, the watchdog's to end; the test stops it)
    CHECK(first_was_alone);
    if (mode == "stuck-last" || mode == "fault-early" || mode == "stuck-compute") {
        CHECK(gone_on);
        CHECK(secs < 20);
        CHECK(logged.find("nothing finished for 1 s") != std::string::npos);
        CHECK(logged.find(mode == "fault-early" ? "the driver faulted, and is stuck since" : "the last ones stuck in the driver") !=
              std::string::npos);
        CHECK(logged.find("gone on without the pipelines the driver did not finish") != std::string::npos);
        CHECK(left_noted);
        CHECK(!saves && !markers);   // (a save could wait on the stuck worker; no marker: not every note is in the cache)
        CHECK(warming() == 1);       // (counted as a start that did not get through: two, and the notes are taken as they are)
        CHECK(last_done == (size_t)all_total && last_total == (size_t)all_total);   // (the bar full: the game starts)
        if (mode == "stuck-last") {
            CHECK(computes_built == 0);   // (the driver is suspect: the compute pipelines are left to play too)
            CHECK(built >= notes - 1 - per_program && built <= notes - 1);   // (only the stuck program's left)
        }
        if (mode == "stuck-compute") CHECK(built == notes - 1 && computes_built == computes_n - 1);
        std::_Exit(0);   // (its workers are still in the "driver")
    }
    CHECK(!gone_on && !left_noted && logged.find("nothing finished") == std::string::npos);
    if (mode == "two-failed") {   // (the last two starts did not get through: the notes as they are, nothing built)
        CHECK(built == 0 && computes_built == 0 && markers == 1 && marker_total == (size_t)notes && warming() == -1);
        CHECK(logged.find("the last two starts did not get through") != std::string::npos);
        return 0;
    }
    if (mode == "closed") {   // (closed in it: not counted; nothing saved or marked here)
        CHECK(stop && built < notes - 1 && !markers && !saves);
        CHECK(warming() == (had ? std::atoi(had) : 0));
        CHECK(logged.find("stopped before the end") != std::string::npos);
        return 0;
    }
    CHECK(built == notes - 1 && computes_built == computes_n);   // (the unkept variant's note is not built)
    CHECK(destroyed == built + computes_built);                   // (each let go: nothing kept)
    CHECK(borrowed_open == 0);
    CHECK(last_done == (size_t)all_total && last_total == (size_t)all_total);
    CHECK(warming() == -1);
    CHECK(logged.find("1 whose program variant is not kept") != std::string::npos);
    if (mode == "prepare-only") {   // (no marker, and the run saves the cache itself next, as its last part)
        CHECK(!markers && !saves);
        CHECK(logged.find("the preparation's own process") != std::string::npos);
        return 0;
    }
    CHECK(saves == 1 && markers == 1 && marker_total == (size_t)notes && saved_before_marker);
    if (const char* t = std::getenv("RX_VK_WARM_THREADS")) CHECK(logged.find("on " + std::string(t) + " threads") != std::string::npos);
    return 0;
}
'''


def compile_run(cxx, code, tmp):
    src = Path(tmp) / "warm_stall.cpp"
    exe = Path(tmp) / ("warm_stall" + (".exe" if os.name == "nt" else ""))
    src.write_text(code, encoding="utf-8")
    # (-D_CRT_SECURE_NO_WARNINGS: a clang that targets MSVC's C library, CI's, calls getenv and fopen deprecated)
    cmd = [cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-D_CRT_SECURE_NO_WARNINGS",
           "-I" + str(ROOT / "gpu" / "vk"), str(src), "-o", str(exe)]
    if os.name != "nt":
        cmd.insert(1, "-pthread")
    subprocess.run(cmd, check=True, timeout=180)
    return exe


def check_warm(cxx, tmp):
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    exe = compile_run(cxx, HEAD + block(draw, "bool precompile_warm(") + MAIN, tmp)
    base = {k: v for k, v in os.environ.items() if k not in ("HOOKSHOT_PREPARE_ONLY", "RX_VK_WARM_THREADS", "FIXTURE_WARMING")}
    base.update(RX_VK_PRECOMPILE_STALL_S="1")
    for case, extra, what in (
            ("quick", {}, "every noted and compute pipeline built and let go, the first alone; saved, then the marker"),
            ("quick", {"RX_VK_WARM_THREADS": "2"}, "RX_VK_WARM_THREADS sets the worker count"),
            # (four workers whatever the CPUs: one stuck, the others finish the rest)
            ("stuck-last", {"RX_VK_WARM_THREADS": "4"}, "the last pipelines never finish: the warm goes on without them"),
            ("stuck-compute", {"RX_VK_WARM_THREADS": "4"}, "a compute pipeline never finishes: the warm goes on without it"),
            ("slow", {}, "a slow driver that still finishes pipelines: no stop"),
            ("fault-early", {}, "the driver faulted, then nothing finishes: the warm goes on"),
            ("closed", {}, "closed in it: not counted"),
            ("closed", {"FIXTURE_WARMING": "1"}, "closed in the start after one that ended in it: still one"),
            ("two-failed", {"FIXTURE_WARMING": "2"}, "after two starts that did not get through: the notes as they are"),
            ("prepare-only", {"HOOKSHOT_PREPARE_ONLY": "1"}, "the preparation's own process: no marker, no save of its own")):
        work = Path(tmp) / ("case-%s-%d" % (case, len(extra)))
        work.mkdir()
        env = dict(base, FIXTURE_DIR=str(work), **extra)
        r = subprocess.run([str(exe), case], env=env, capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise SystemExit("precompile_warm, %s: exit %d\n%s%s" % (what, r.returncode, r.stdout, r.stderr))
        print("PASS precompile_warm:", what, flush=True)
    # (stuck early with no fault: the bulk is not given up here; it waits, and the --prepare-shaders watchdog ends a real hang)
    work = Path(tmp) / "case-stuck-early"
    work.mkdir()
    try:
        r = subprocess.run([str(exe), "stuck-early"], env=dict(base, FIXTURE_DIR=str(work)), capture_output=True, text=True,
                           timeout=6)
        raise SystemExit("precompile_warm gave up the bulk of the run with no fault in the driver: exit %d\n%s%s"
                         % (r.returncode, r.stdout, r.stderr))
    except subprocess.TimeoutExpired:
        print("PASS precompile_warm: stuck early with no fault: waited for", flush=True)


def check_source():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    warm = block(draw, "bool precompile_warm(")
    if "prepare_left_workers_note();" not in warm:
        raise SystemExit("precompile_warm goes on from stuck workers without saying so to the save (vk_main.cpp)")
    if 'getenv("RX_VK_PRECOMPILE_STALL_S")' not in warm:
        raise SystemExit("precompile_warm's stall is not RX_VK_PRECOMPILE_STALL_S, precompile_run's")
    run = block(draw, "void precompile_run(")
    head = run[:run.index("const auto t0 = std::chrono::steady_clock::now();")]
    went_on = 'if (warm_gone_on && !prepare_stopped() && !env_on("HOOKSHOT_PREPARE_ONLY")) return precompile_at_create();'
    if "const bool warm_gone_on = !precompile_covers_notes() && precompile_warm(progress);" not in head or went_on not in head:
        raise SystemExit("precompile_run does not load at create calls after a warm that went on")
    if head.index(went_on) > head.index('if (prepare_stopped() || env_on("HOOKSHOT_PREPARE_ONLY")) return;'):
        raise SystemExit("precompile_run's own return comes before the load at create calls after a warm that went on")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    check_source()
    if not shutil.which(args.cxx):
        raise SystemExit("C++ compiler not found: " + args.cxx)
    with tempfile.TemporaryDirectory(prefix="warm-stall-") as tmp:
        check_warm(args.cxx, tmp)
    print("PASS: precompile_warm goes on from a stuck driver, and a close is not counted")


if __name__ == "__main__":
    main()
