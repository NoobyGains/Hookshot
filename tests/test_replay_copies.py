"""Two per-op / per-draw copies of the replay made cheaper (gpu/vk/vk_replay.cpp payload, gpu/vk/vk_draw.cpp RecordingRes).

payload<T> is cut from the source and run: a payload at least as long as T is copied whole, a shorter one is copied for its length
and the rest of T stays zero, as before. The recording's c1 map is the flat table (flat_map.h): a c1 upload kept no longer allocates a map node.
python -I -B tests/test_replay_copies.py [--cxx clang++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    if text.count(marker) != 1:
        raise SystemExit("marker not found once: " + marker)
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


FIXTURE = r"""
#include <cstdint>
#include <cstdio>
#include <cstring>
template <class T>
/* FN */
struct P { uint32_t a, b, c, d; };
int main() {
    uint8_t buf[64];
    for (int i = 0; i < 64; i++) buf[i] = (uint8_t)(i + 1);
    int fails = 0;
    for (uint32_t n = 0; n <= 32; n++) {
        const P v = payload<P>(buf, n);
        uint8_t got[sizeof v];
        std::memcpy(got, &v, sizeof v);
        for (uint32_t i = 0; i < sizeof v; i++) {
            const uint8_t want = i < n ? buf[i] : 0;
            if (got[i] != want) { std::printf("FAIL: %u bytes, byte %u: %u, want %u\n", n, i, got[i], want); fails++; break; }
        }
    }
    return fails ? 1 : 0;
}
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="clang++")
    a = p.parse_args()
    replay = (ROOT / "gpu" / "vk" / "vk_replay.cpp").read_text(encoding="utf-8")
    fn = block(replay, "T payload(const uint8_t* a, uint32_t bytes) {")
    if "if (bytes >= sizeof v) [[likely]]" not in fn:
        raise SystemExit("FAIL: payload: a payload as long as T is copied at T's size")
    draw = (ROOT / "gpu" / "vk" / "vk_draw.cpp").read_text(encoding="utf-8")
    res = block(draw, "struct RecordingRes {")
    if "FlatMap<uintptr_t, std::pair<VkBuffer, uint64_t>> c1_at;" not in res:
        raise SystemExit("FAIL: RecordingRes: the c1 map is flat")
    with tempfile.TemporaryDirectory(prefix="replay-copies-") as temp:
        src, exe = Path(temp) / "copies.cpp", Path(temp) / "copies.exe"
        src.write_text(FIXTURE.replace("/* FN */", fn), encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", str(src), "-o", str(exe)], check=True)
        r = subprocess.run([str(exe)], text=True, capture_output=True, timeout=20)
        if r.returncode:
            print(r.stdout, end="")
            raise SystemExit("FAIL: payload")
    print("PASS: an op's payload copied as before, inline at T's size; the recording's c1 map flat")


if __name__ == "__main__":
    main()
