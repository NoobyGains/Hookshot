"""The uniform-buffer snapshot default, game-free: the actual selection code from gpu/vk/vk_draw.cpp, compiled.

On an integrated GPU (or Intel) whose buffer pools have no VRAM mirror, a uniform buffer bound in place is the game's own
memory, which it rewrites right after the submit; the copy as submitted is the default there. With mirrors, or on a
discrete GPU without them (GCN since #2343, RX_VK_MIRROR=0), it stays in place. Set, RX_VK_UB_SNAPSHOT reads as env_on does
(gpu/vk/compat/hookshot_env.h): 1, on, true, yes force the copy; 0, off, false, no, empty force the pool.

    python -I -B tests/test_ub_snapshot_default.py [--cxx g++]
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
RUN_ALL_SKIP = {"windows": "the fixture sets the switch with POSIX setenv: checked on Linux"}

ROOT = Path(__file__).resolve().parents[1]
MARKER = "static const bool snapshot = [] {"
REUSE_MARKER = "static const bool snap_reuse = [] {"


def selection(source):
    start = source.index(MARKER) + len("static const bool snapshot = ")
    end = source.index("}();", start) + 3
    return source[start:end]


def block(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


FIXTURE = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
enum { VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU = 1, VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU = 2 };
static struct { struct { uint32_t vendorID; int deviceType; } props; } dev;
static bool mirrors;
static char logged[256];
[[maybe_unused]] static bool pools_mirrored() { return mirrors; }
static void logf(const char* f, ...) { std::snprintf(logged, sizeof logged, "%s", f); }
static bool pick() { return SNAPSHOT_SELECTION; }
static bool ub_snapshot_on() { return pick(); }
static bool pick_reuse() { return REUSE_CACHE_SELECTION; }
int main(int argc, char** argv) {
    if (argc != 6) return 2;
    mirrors = argv[1][0] == '1';
    dev.props.deviceType = argv[2][0] == 'i' ? VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU : VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU;
    dev.props.vendorID = (uint32_t)std::strtoul(argv[3], nullptr, 16);
    if (std::strcmp(argv[4], "unset")) setenv("RX_VK_UB_SNAPSHOT", argv[4], 1); else unsetenv("RX_VK_UB_SNAPSHOT");
    if (std::strcmp(argv[5], "unset")) setenv("RX_VK_UB_SNAPSHOT_REUSE", argv[5], 1);
    else unsetenv("RX_VK_UB_SNAPSHOT_REUSE");
    const bool on = pick();
    if (!std::strstr(logged, "uniform buffers")) return 3;
    std::puts(on ? "copy" : "pool");
    std::puts(pick_reuse() ? "reuse" : "copy-each");
    return 0;
}
'''

# (mirrors, integrated or discrete, vendor, RX_VK_UB_SNAPSHOT, expected)
CASES = [("0", "i", "1002", "unset", "copy"),    # (an AMD APU, the Steam Deck: no mirrors)
         ("0", "i", "8086", "unset", "copy"),    # (an Intel iGPU, https://github.com/NotRexed/Hookshot/pull/2464)
         ("0", "d", "8086", "unset", "copy"),    # (an Intel discrete card without mirrors, same Intel fix)
         ("0", "d", "1002", "unset", "pool"),    # (GCN, mirrorless since the linked pull above: not measured)
         ("1", "d", "10de", "unset", "pool"), ("1", "i", "1002", "unset", "pool"),
         ("0", "d", "1002", "1", "copy"), ("0", "d", "1002", "on", "copy"), ("0", "d", "1002", "yes", "copy"),
         ("1", "d", "10de", "true", "copy"),
         ("0", "i", "1002", "0", "pool"), ("0", "i", "1002", "off", "pool"), ("0", "i", "1002", "no", "pool"),
         ("0", "i", "1002", "false", "pool"), ("0", "i", "1002", "", "pool")]

REUSE_CASES = [("0", "i", "8086", "unset", "unset", "copy-each"),
               ("0", "i", "8086", "unset", "1", "reuse"),
               ("0", "i", "8086", "unset", "on", "reuse"),
               ("0", "i", "8086", "unset", "0", "copy-each"),
               ("0", "i", "8086", "unset", "off", "copy-each"),
               ("0", "i", "8086", "unset", "", "copy-each"),
               ("0", "i", "1002", "unset", "unset", "reuse"),
               ("0", "i", "1002", "unset", "yes", "reuse"),
               ("0", "i", "1002", "unset", "no", "copy-each"),
               ("0", "d", "1002", "1", "unset", "copy-each"),
               ("1", "i", "1002", "1", "unset", "copy-each"),
               ("0", "i", "10de", "unset", "false", "copy-each")]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--source", type=Path, default=ROOT / "gpu/vk/vk_draw.cpp")
    a = p.parse_args()
    source = a.source.read_text(encoding="utf-8")
    code = FIXTURE.replace("SNAPSHOT_SELECTION", selection(source)).replace("REUSE_CACHE_SELECTION",
        source[source.index(REUSE_MARKER) + len("static const bool snap_reuse = "):
               source.index("}();", source.index(REUSE_MARKER)) + 3])
    with tempfile.TemporaryDirectory(prefix="ub-snapshot-") as tmp:
        cpp, exe = Path(tmp) / "t.cpp", Path(tmp) / "t"
        cpp.write_text(code, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Werror", "-Wno-format-security",
                        "-include", str(ROOT / "gpu" / "vk" / "compat" / "hookshot_env.h"), str(cpp), "-o", str(exe)],
                       check=True)
        for mirrors, kind, vendor, value, want in CASES:
            got = subprocess.run([str(exe), mirrors, kind, vendor, value, "unset"], capture_output=True, text=True,
                                 check=True).stdout.splitlines()[0]
            if got != want:
                raise SystemExit("mirrors=%s %s vendor %s RX_VK_UB_SNAPSHOT=%r: %s, expected %s" %
                                 (mirrors, kind, vendor, value, got, want))
        for mirrors, kind, vendor, snapshot, reuse, want in REUSE_CASES:
            got = subprocess.run([str(exe), mirrors, kind, vendor, snapshot, reuse], capture_output=True, text=True,
                                 check=True).stdout.splitlines()[1]
            if got != want:
                raise SystemExit("mirrors=%s %s vendor %s RX_VK_UB_SNAPSHOT=%r RX_VK_UB_SNAPSHOT_REUSE=%r: %s, expected %s" %
                                 (mirrors, kind, vendor, snapshot, reuse, got, want))
    uniform = block(source, "VkDescriptorBufferInfo uniform_range(")
    begin = block(source, "void draw_begin_recording(")
    memory = (ROOT / "gpu" / "vk" / "vk_memory.cpp").read_text(encoding="utf-8")
    stamp = block(memory, "void memory_stamp_gpu(")
    cpu_write = block(memory, "void guest_cpu_wrote(")
    if "memory_gpu_written_in_recording(guest, n)" not in uniform:
        raise SystemExit("a range written by the GPU earlier in this recording is still copied from stale CPU bytes")
    written = block(memory, "bool memory_gpu_written_in_recording(")
    if "memory_written_since(guest, size, gpu_write_recording_gen)" not in written:
        raise SystemExit("a GPU write from another parallel recording can still leave a stale uniform snapshot")
    if "memory_replay_cpu_view()" not in uniform or "it->second.cpu_view == cpu_view" not in uniform:
        raise SystemExit("a replay CPU write does not invalidate the snapshot reuse")
    if "memory_read_as_submitted(u.addr, cur->mapped + at, n) && view &&" not in uniform:
        raise SystemExit("a failed snapshot read or a changed CPU write view can be cached")
    if "r.ub_snap.clear()" not in begin or "r.ub_snap.reserve(32)" not in begin or \
            "memory_gpu_write_recording_begin(ub_snapshot_on())" not in begin:
        raise SystemExit("the recording's reuse and GPU-write state is not reset and reserved")
    if "memory_gpu_write_recording_note(guest, size)" not in stamp:
        raise SystemExit("GPU writes are not noted for a later uniform-buffer fallback")
    if cpu_write.index("replay_cpu_view.fetch_add") > cpu_write.index("if (!wb_diff_on()) return;"):
        raise SystemExit("replay CPU writes stop invalidating snapshots when the write-back diff is off")
    print("PASS: uniform buffers copied by default on integrated GPUs (and Intel) without mirrors; the switch forces either way")


if __name__ == "__main__":
    main()