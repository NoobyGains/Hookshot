"""The capture buffers' spares (gpu/vk/cap_spares.h, vk_memory.cpp cap_buf_get, cap_prewarm_class, cap_spare_worker): the
policy compiled and run, and the pool's code read from the source. Checked: the classes a size falls in; the bytes of spares
by the PC's RAM; a capture is never served by a spare of a larger class (a 2 MB capture took the 128 MB spare made for the
next load); a spare is made only with RAM and commit to spare; one worker at a time makes them, with no lock held while
the driver allocates, and cap_buf_get allocates a miss without the pool's lock and asks for its class again.

python -I -B tests/test_cap_spares.py [--cxx g++]
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"
CXX = "g++"

FIXTURE = r'''
#include "cap_spares.h"
#include <cstdio>
using namespace mkwvk::cap_spares;
int main() {
    int bad = 0;
#define CHECK(x) do { if (!(x)) { bad++; std::printf("FAIL line %d: %s\n", __LINE__, #x); } } while (0)
    const uint64_t MB = 1ull << 20, GB = 1ull << 30;
    CHECK(class_index(1) == 0 && class_index(32 * MB) == 0 && class_index(32 * MB + 1) == 1 && class_index(130 * MB) == 3);
    CHECK(class_index(256 * MB) == 4 && class_index(256 * MB + 1) == -1);
    CHECK(ram_cap(0) == 64 * MB && ram_cap(8 * GB) == 64 * MB && ram_cap(16 * GB) == 128 * MB && ram_cap(32 * GB) == 256 * MB);
    CHECK(ram_cap(64 * GB) == 512 * MB);
    CHECK(serves(4 * MB, 3 * MB, 4 * MB) && !serves(128 * MB, 3 * MB, 4 * MB) && !serves(2 * MB, 3 * MB, 4 * MB));
    CHECK(serves(64 * MB, 40 * MB, 64 * MB) && !serves(128 * MB, 40 * MB, 64 * MB));
    CHECK(room(false, 0, 0, 64 * MB, GB));                                  // (not known: made)
    CHECK(room(true, 4 * GB, 4 * GB, 64 * MB, GB) && !room(true, GB, 4 * GB, 64 * MB, GB) && !room(true, 4 * GB, GB, 64 * MB, GB));
    std::printf("%s\n", bad ? "FAILED" : "spares policy checked");
    return bad != 0;
}
'''


def block(text, head):
    i = text.index(head)
    j = text.index("{", i)
    depth = 0
    for k in range(j, len(text)):
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        if not depth:
            return text[i:k + 1]
    raise AssertionError(head)


class CapSparesTests(unittest.TestCase):
    def setUp(self):
        self.mem = (VK / "vk_memory.cpp").read_text(encoding="utf-8")

    def test_policy(self):
        with tempfile.TemporaryDirectory(prefix="hookshot-cap-spares-") as tmp:
            src, exe = Path(tmp) / "spares.cpp", Path(tmp) / "spares.exe"
            src.write_text(FIXTURE, encoding="utf-8")
            built = subprocess.run([CXX, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(VK), str(src), "-o", str(exe)],
                                   capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_get(self):
        get = block(self.mem, "bool cap_buf_get(")
        self.assertIn("cap_spares::serves(cap_free[i].size, need, target)", get)
        self.assertLess(get.index("cap_prewarm_class(target);"), get.index("if (best < cap_free.size())"))
        self.assertLess(get.index("lk.unlock();"), get.index("create_buffer_cached("), "a miss allocates without the pool's lock")

    def test_worker(self):
        worker = block(self.mem, "void cap_spare_worker(")
        locked = worker[worker.index("std::lock_guard lk(cap_free_mu);"):worker.index("VkBuffer b = VK_NULL_HANDLE;")]   # (the queue's part)
        self.assertNotIn("create_buffer_cached(", locked)
        self.assertIn("cap_spare_room(want)", locked)
        self.assertIn("cap_prewarm_busy = 0;", locked, "the worker leaves under the lock that queues work")
        self.assertIn("if (cap_shutting_down.load()) return;", worker)
        prewarm = block(self.mem, "void cap_prewarm_class(uint64_t size)")
        self.assertIn("if (cap_prewarm_busy.load()) return;", prewarm)
        self.assertEqual(prewarm.count("std::thread("), 1)
        self.assertIn("cap_spares::ram_cap(", block(self.mem, "uint64_t cap_spare_max()"))
        self.assertNotIn("void cap_spare_make(", self.mem)
        self.assertNotRegex(self.mem, r"cap_prewarm_busy\.load\(\) >= 3", "one worker, not three")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args, rest = parser.parse_known_args()
    CXX = args.cxx
    unittest.main(argv=[sys.argv[0]] + rest)
