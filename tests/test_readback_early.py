"""RX_VK_READBACK_EARLY (opt-in): a CPU read of GPU results written in place waits for the part its last writer was recorded in,
not its whole submission, and that part ends right after the writer (gpu/vk/vk_memory.cpp, gpu/vk/vk_replay.cpp's invalidate and
replay).

With no mirror (the Steam Deck: every page) a page the GPU writes is noted with its submission only, and a read of it waited for
the whole submission: the game's job polled ~18 ms a frame for its camera block while the GPU finished a 22-26 ms submission
after the writer. Cut from the source and run:

  - with the switch on, a GPU write in place to a range whose read has waited keeps each of its pages' submission and part,
    whatever its size (note_direct_write notes only bindings up to 1 MB for the plain wait); a write elsewhere, or before
    any read waited, keeps nothing; off, nothing;
  - the part is given only when the newest write it knows is the range's newest (another, unseen, leaves the whole
    submission), and the newest of a submission's writes to its pages;
  - such a write asks for its part to end (once), not the uniform updates written at a part's end; the ranges are at most 64,
    the oldest let go with its pages;
  - invalidate's early wait: for the newest of the in-place writer's part and a mirror's part, when a page written in place is
    not done; the whole submission otherwise (writer not known, only mirrored pages pending, the part not found); none for a
    range RX_VK_READBACK_LATE reads late;
  - with RX_VK_PARALLEL=2 or more the switch is left off (a segment's part never reaches the recordings' timeline);
  - the wiring: note_direct_write notes every in-place write; the early wait comes before the choice of the usual wait, which
    it replaces only when it waited; the replay ends a part after an op that asked, at least RX_VK_READBACK_EARLY_GAP draws
    into it, maybe_split still ends one every RX_VK_CHUNK draws, and a draw of a program that writes storage buffers builds
    its descriptors;
  - RX_VK_LOG_RB_WRITERS: a recording closes its submission's span on every path that finishes it, a burst's end included
    (burst_end and the spans cut out and run).

python -I -B tests/test_readback_early.py [--cxx g++]
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    """the text from marker to the brace that closes its first '{'"""
    if text.count(marker) != 1:
        raise SystemExit("marker not found once: " + marker)
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def between(text, first, last):
    if text.count(first) != 1:
        raise SystemExit("marker not found once: " + first)
    start = text.index(first)
    return text[start:text.index(last, start)]


MEMORY = r"""
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>
constexpr uint64_t kPageShift = 12, kChunkPages = 16, kPages = 1024;
static bool env_on(const char* name) {
    const char* v = std::getenv(name);
    return v && *v && std::strcmp(v, "0");
}
static void logf(const char*, ...) {}
constexpr uint32_t kRbWriterUb = 0x10000, kRbWriterWb = 0x10001;
struct RbWriter {
    uint64_t value = 0, part = 0, work = 0, key = 0;
    uint32_t what = 0;
};
bool rb_writers_on();
bool readback_early_on();
uint64_t memory_in_place_writer_part(uint64_t guest, uint64_t size, uint64_t whole);
void memory_rb_waited(uint64_t guest, uint64_t size);
bool memory_rb_waited_range(uint64_t guest, uint64_t size);
bool memory_split_wanted();
bool memory_readback_early_active();
namespace {
/* PAGES */
std::atomic<uint64_t> mem_rec_part{0}, mem_in_place_part{0};
}  // namespace
/* WRITERS */
static int failures;
static void check(bool ok, const char* what) {
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}
constexpr uint64_t P = 4096;
constexpr uint32_t kDispatch = 27, kCopy = 6;   // (any op but the uniform updates)
static void write(uint64_t lo, uint64_t hi, uint64_t value, uint64_t rec, uint32_t what) {   // (as note_direct_write)
    mem_rec_part = rec;
    memory_writer_note(what, 0);
    early_in_place_write(lo, hi, value);
    if (hi - lo <= (1u << 20)) wb_pages_note(lo, hi, value, 0);
}
int main(int argc, char** argv) {
    const bool on = argc > 1 && !std::strcmp(argv[1], "on");
    check(readback_early_on() == on, "the switch is read");
    write(1 * P, 1 * P + 64, 10, 5, kDispatch);
    check(!memory_readback_early_active(), "idle before a read of pages written in place waited");
    check(memory_in_place_writer_part(1 * P, 64, 10) == 0, "before any read waited: nothing kept");
    check(!memory_split_wanted(), "and no split asked for");
    memory_rb_waited(1 * P, 0x3980);   // (pages 1-4)
    check(memory_rb_waited_range(1 * P + 100, 8) == on, "a range whose read waited is known");
    check(memory_readback_early_active() == on, "and the tracking in use");
    check(!memory_rb_waited_range(9 * P, 8), "another is not");
    write(1 * P, 1 * P + 0x3980, 11, 7, kDispatch);
    check(memory_in_place_writer_part(1 * P, 0x3980, 11) == (on ? 7u : 0u), "a write in place to it keeps its part");
    check(memory_split_wanted() == on, "and asks for its part to end");
    check(!memory_split_wanted(), "once");
    check(memory_in_place_writer_part(1 * P, 0x3980, 12) == 0, "a newer write it did not see: the whole submission");
    write(2 * P, 2 * P + 64, 11, 8, kCopy);
    check(memory_in_place_writer_part(1 * P, 0x3980, 11) == (on ? 8u : 0u), "the latest part of the submission's writes to its pages");
    check(memory_split_wanted() == on, "a copy asks for its part to end too");
    write(9 * P, 10 * P, 12, 9, kDispatch);
    check(!memory_split_wanted(), "a write elsewhere asks for no split");
    check(memory_in_place_writer_part(9 * P, 64, 12) == 0, "and keeps nothing");
    write(0, 320 * P, 13, 10, kDispatch);   // (1.25 MiB: past note_direct_write's 1 MB for the plain wait, kept here whatever its size)
    check(memory_split_wanted() == on, "a write over 1 MB over it asks for its part to end");
    check(memory_in_place_writer_part(1 * P, 0x3980, 11) == 0,
          "and the read of what the plain wait knows (11) no longer finds 11's write there: the whole submission");
    write(1 * P, 1 * P + 64, 14, 11, kRbWriterUb);
    check(memory_in_place_writer_part(1 * P, 64, 14) == (on ? 11u : 0u), "the uniform updates' write keeps its part");
    check(!memory_split_wanted(), "but asks for no split: written at their part's end already");
    // (a range widened over a page that the same submission wrote before: that write was not seen)
    memory_rb_waited(20 * P, 64);
    write(20 * P, 20 * P + 64, 15, 12, kDispatch);
    write(21 * P, 21 * P + 64, 15, 13, kDispatch);   // (page 21: no range of it yet)
    (void)memory_split_wanted();
    memory_rb_waited(20 * P, 2 * P);
    check(memory_in_place_writer_part(20 * P, 2 * P, 15) == 0, "a range widened over a page its submission wrote unseen: the whole submission");
    check(memory_in_place_writer_part(20 * P, 64, 15) == (on ? 12u : 0u), "its first page alone: that page's part");
    write(21 * P, 21 * P + 64, 15, 14, kDispatch);
    check(memory_in_place_writer_part(20 * P, 2 * P, 15) == (on ? 14u : 0u), "seen once written again: the later part");
    (void)memory_split_wanted();
    // (two ranges of one page: a write of the page's other bytes in a later part is seen, for the page)
    memory_rb_waited(30 * P, 64);
    write(30 * P, 30 * P + 64, 16, 15, kDispatch);
    check(memory_split_wanted() == on, "a write of the bytes read asks for its part to end");
    write(30 * P + 128, 30 * P + 192, 16, 16, kDispatch);
    check(!memory_split_wanted(), "a write of the page's other bytes asks for no split");
    check(memory_in_place_writer_part(30 * P, 64, 16) == (on ? 16u : 0u), "but is the page's newest writer: its part");
    memory_rb_waited(30 * P + 128, 64);
    check(memory_in_place_writer_part(30 * P + 128, 64, 16) == (on ? 16u : 0u), "and for a second range of the page");
    write(31 * P, 31 * P + 64, 16, 17, kDispatch);   // (page 31: in no range)
    check(memory_in_place_writer_part(30 * P, 2 * P, 16) == 0, "a range reaching past it into a page written unseen: the whole submission");
    for (uint64_t r = 0; r < 64; r++) memory_rb_waited((100 + 2 * r) * P, 64);   // (64 more ranges: the first is let go)
    check(!memory_rb_waited_range(1 * P + 100, 8), "the oldest range let go");
    check(memory_in_place_writer_part(1 * P, 64, 14) == 0, "with its pages");
    check(memory_rb_waited_range(226 * P, 8) == on, "the newest kept");
    return failures ? 1 : 0;
}
"""

CHOICE = r"""
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
static uint64_t done_value;
static uint64_t completed() { return done_value; }
static bool early_on = true, late_rule = false;   // (late_rule: RX_VK_READBACK_LATE names the range)
static bool readback_early_on() { return early_on; }
static uint64_t writer_part;
static uint64_t memory_in_place_writer_part(uint64_t, uint64_t, uint64_t) { return early_on ? writer_part : 0; }
static int waited_marks;
static void memory_rb_waited(uint64_t, uint64_t) { waited_marks++; }
static uint64_t waited_part;
static bool part_known = true;
static bool wait_recorded_part(uint64_t part, uint64_t, int* ok) {
    if (!part_known) return false;
    waited_part = part, *ok = 1;
    return true;
}
struct Host { uint64_t gpu_guest(uint64_t g) const { return g; } };
static Host host_v;
static Host* host = &host_v;
static std::atomic<int64_t> st_early_waits{0}, st_early_ns{0}, st_early_whole{0};
static const bool unforced = true, by_part = true;
static int failures;
static void check(bool ok, const char* what) {
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}
/// (v: the range's newest write-back value; part: a mirror's part; whole: the newest in-place value) -> waited early, for which part
static bool choose(uint64_t v, uint64_t part, uint64_t whole) {
    const uint64_t gpu = 0x1000, size = 0x3980;
    bool w = false;
    waited_part = 0;
    const bool pending = v > completed(), late = pending && late_rule;
    /* EARLY */
    (void)w;
    return early_done;
}
int main() {
    done_value = 10;
    writer_part = 40;
    check(choose(12, 0, 12) && waited_part == 40, "a page written in place: its writer's part");
    check(choose(12, 44, 12) && waited_part == 44, "with a newer mirror part too: the newer part");
    check(choose(12, 30, 12) && waited_part == 40, "with an older mirror part: the writer's");
    check(!choose(12, 41, 9) && waited_part == 0, "only mirrored pages pending: the usual choice");
    writer_part = 0;
    check(!choose(12, 0, 12), "the writer not known: the whole submission");
    writer_part = 40;
    part_known = false;
    check(!choose(12, 0, 12), "the part not found: the whole submission");
    part_known = true;
    check(!choose(9, 0, 9), "done already: no wait");
    late_rule = true;
    check(!choose(12, 0, 12) && waited_part == 0, "a range RX_VK_READBACK_LATE reads late: no wait, not marked");
    late_rule = false;
    early_on = false;
    check(!choose(12, 0, 12), "off: the usual choice");
    check(st_early_waits == 3 && st_early_whole == 2, "counted");
    check(waited_marks == 5, "each read with a page written in place pending marked its pages (not one of mirrored pages only)");
    return failures ? 1 : 0;
}
"""

SPAN = r"""
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <map>
#include <mutex>
static uint64_t work;   // (draws and dispatches recorded so far)
static uint64_t memory_work_count() { return work; }
static bool rb_writers_on() { return true; }
struct Recording { uint64_t value = 0, part = 0; };
static Recording rec_v;
static Recording* rec_cur = nullptr;
static std::mutex replay_mu;
static bool burst_open = false;
static uint64_t burst_value = 0, ev_looked = 0;
static bool ev_looked_any = false;
static std::atomic<uint64_t> ev_cpu_settled{0};
static int finished;
static uint64_t finished_value;
static void finish_recording(uint64_t v) { rec_cur = nullptr, finished++, finished_value = v; }
/* SPANS */
/* BURST_END */
static int failures;
static void check(bool ok, const char* what) {
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}
int main() {
    rec_v = {20, 5}, rec_cur = &rec_v, work = 100, burst_open = true, burst_value = 20;
    rb_span_begin(20, 5);
    work = 130, rec_v.part = 6;   // (the writer)
    work = 150, rec_v.part = 7;   // (work after it, in a later part)
    burst_end();
    const SubSpan& s = rb_spans[20];
    check(finished == 1 && finished_value == 20, "the burst's recording finished at its end");
    check(s.first_part == 5 && s.last_part == 7 && s.w0 == 100 && s.w1 == 150,
          "and its span closed there: the last part and the submission's work, not the writer's");
    return failures ? 1 : 0;
}
"""


def run(cxx, src, exe, args=(), env=None):
    subprocess.run([cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-unused-variable",
                    "-pthread", "-D_CRT_SECURE_NO_WARNINGS", str(src), "-o", str(exe)], check=True)
    r = subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=60, env=env)
    print(r.stdout, end="")
    if r.returncode:
        raise SystemExit("FAIL: %s %s\n%s" % (exe.name, " ".join(args), r.stderr))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    pages = between(memory, "std::mutex wb_pages_mu;", "} // namespace\n/// The newest write-back value")
    writers = between(memory, "namespace {\nthread_local uint32_t wr_what = 0;", "/// (RX_VK_LOG_RB_WRITERS) the writers of a range's pages")
    inv = block(replay, "void invalidate(uint64_t gpu, uint64_t size) {")
    early = between(inv, "bool early_done = false;", "if (early_done) {")
    if "if (early_done) {\n            } else if (pending && !late) {\n                int ok = 0;" not in inv:
        raise SystemExit("FAIL: invalidate: the early wait no longer replaces the usual choice only when it waited")
    if inv.index("bool early_done = false;") > inv.index("const bool in_place_after = memory_in_place_part() > part;"):
        raise SystemExit("FAIL: invalidate: the early wait comes after the usual choice")
    rep = block(replay, "void replay(VkCommandBuffer& cmd, NvnState& s, const uint8_t* p, const uint8_t* end = nullptr) {")
    if "if (split_after || memory_split_wanted()) early_split_pending = true;" not in rep or \
            "if (early_split_pending && part_work >= early_gap) {" not in rep or \
            "else split_part(cmd, true);\n            }\n        }\n        p += h.size;" not in rep or \
            "if (part_ends_before_draw()) part_end_wanted = true;" not in rep:
        raise SystemExit("FAIL: replay: a part does not end after an op that asked for it, at least the gap into it")
    mem_note = block(memory, "void note_direct_write(")
    if "early_in_place_write(p.lo + off, p.lo + std::min(off + size, p.hi - p.lo), mem_rec_value);" not in mem_note.split("if (size <=")[0]:
        raise SystemExit("FAIL: note_direct_write does not note every write in place for the early wait, whatever its size")
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    if "const bool same_desc = last_desc_aspect == ui_aspect && !no_reuse && !early_rebind && " not in draw or "if (d.is_written) return true;" not in draw or \
            "const bool early_rebind = early && memory_readback_early_active() && [&] {" not in draw:
        raise SystemExit("FAIL: vk_draw.cpp: a draw of a program that writes storage buffers may keep the set before, its write not noted")
    if "if (early && !dry && memory_rb_waited_range(host->gpu_guest(u.dst), u.size)) split_after = true;" not in rep:
        raise SystemExit("FAIL: replay: an update of uniforms a read waited for does not end its part")
    for where, text in (("run_submit", block(replay, "bool run_submit(")), ("resume_queue", replay)):
        if "rb_span_close(), finish_recording(" not in text:
            raise SystemExit("FAIL: %s finishes a recording without closing its RX_VK_LOG_RB_WRITERS span" % where)
    if replay.count("finish_recording(") != replay.count("rb_span_close(), finish_recording(") + 2:   # (+ its declaration, definition)
        raise SystemExit("FAIL: a recording is finished without closing its RX_VK_LOG_RB_WRITERS span")
    # (maybe_split keeps the count and ends a part by it, at the next plain draw where parts end there (part_ends_before_draw);
    # split_part is the end itself, which RX_VK_READBACK_EARLY also asks for after a writer, now)
    if "++part_work < every" not in block(replay, "void maybe_split(VkCommandBuffer& cmd) {"):
        raise SystemExit("FAIL: maybe_split no longer ends a part by its count")
    split = block(replay, "void split_part(VkCommandBuffer& cmd, bool now) {")
    if "if (now) st_early_splits++;" not in split or "part_work = 0;" not in split:
        raise SystemExit("FAIL: split_part: a part's count of draws is no longer kept")
    if "early_split_pending = false;" not in split or "(void)memory_split_wanted();" not in split or \
            "(void)memory_split_wanted(), early_split_pending = false;" not in block(replay, "bool run_submit("):
        raise SystemExit("FAIL: a part ended by its count or its submission's end leaves a split asked for, and the next part ends at once")
    with tempfile.TemporaryDirectory(prefix="readback-early-") as tmp:
        tmp = Path(tmp)
        mem_src, mem_exe = tmp / "memory.cpp", tmp / ("memory.exe" if os.name == "nt" else "memory")
        mem_src.write_text(MEMORY.replace("/* PAGES */", pages).replace("/* WRITERS */", writers), encoding="utf-8")
        env_on = dict(os.environ, RX_VK_READBACK_EARLY="1")
        env_off = {k: v for k, v in os.environ.items() if k not in ("RX_VK_READBACK_EARLY", "RX_VK_LOG_RB_WRITERS")}
        run(a.cxx, mem_src, mem_exe, ["on"], env_on)
        r = subprocess.run([str(mem_exe), "off"], capture_output=True, text=True, timeout=60, env=env_off)
        print(r.stdout, end="")
        if r.returncode:
            raise SystemExit("FAIL: with the switch off\n" + r.stderr)
        env_par = dict(env_on, RX_VK_PARALLEL="3")   # (a parallel replay's segments: their parts never reach the timeline)
        r = subprocess.run([str(mem_exe), "off"], capture_output=True, text=True, timeout=60, env=env_par)
        print(r.stdout, end="")
        if r.returncode:
            raise SystemExit("FAIL: with RX_VK_PARALLEL=3 the switch is not left off\n" + r.stderr)
        choice_src, choice_exe = tmp / "choice.cpp", tmp / ("choice.exe" if os.name == "nt" else "choice")
        choice_src.write_text(CHOICE.replace("/* EARLY */", early), encoding="utf-8")
        run(a.cxx, choice_src, choice_exe)
        span_src, span_exe = tmp / "span.cpp", tmp / ("span.exe" if os.name == "nt" else "span")
        span_src.write_text(SPAN.replace("/* SPANS */", between(replay, "struct SubSpan {", "const char* rb_what_name("))
                            .replace("/* BURST_END */", block(replay, "void burst_end() {")), encoding="utf-8")
        run(a.cxx, span_src, span_exe)
    print("PASS: a read of pages written in place waits for its writer's part, which ends after the writer, with the switch on")


if __name__ == "__main__":
    main()
