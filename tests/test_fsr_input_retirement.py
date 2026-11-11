"""FSR input images and depth views survive CPU frames until GPU completion."""
RUN_ALL_ARGS = ["--cxx", "{cxx}"]

import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker):
    start = source.index(marker)
    end = source.index("{", start) + 1
    depth = 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    source = (ROOT / "gpu/vk/vk_fsr3_inputs.cpp").read_text(encoding="utf-8")
    actual = "\n".join(block(source, marker) for marker in ["void later(", "void free_dead()"])
    dead = block(source, "struct Dead {") + ";"
    fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <functional>
#include <utility>
#include <vector>
uint64_t cpu_frame = 10, retirement = 101, completed = 100;
[[maybe_unused]] uint64_t texture_frame_no() { return cpu_frame; }
[[maybe_unused]] uint64_t vk_retirement_value() { return retirement; }
[[maybe_unused]] uint64_t vk_timeline_completed() { return completed; }
struct State {
DEAD
    std::vector<Dead> dead;
};
State& st() { static State s; return s; }
ACTUAL
int main() {
    int image = 0, view = 0, unknown = 0;
    later([&] { ++image; });
    // A stalled GPU must retain the image, however many CPU frames pass.
    cpu_frame += 1000;
    free_dead();
    assert(image == 0);
    // Completion of the retirement ticket is sufficient, with no extra CPU frames.
    completed = 101;
    free_dead();
    assert(image == 1);
    free_dead();
    assert(image == 1);
    // Several resource classes, including cached depth views, use the same queue.
    retirement = 105;
    later([&] { ++image; });
    retirement = 103;
    later([&] { ++view; });
    retirement = 0; // unavailable timeline or exhausted ticket: retain ownership
    later([&] { ++unknown; });
    completed = 103;
    free_dead();
    assert(image == 1 && view == 1 && unknown == 0);
    completed = 105;
    free_dead();
    assert(image == 2 && view == 1 && unknown == 0);
    completed = UINT64_MAX;
    cpu_frame += 1000;
    free_dead();
    assert(unknown == 0 && st().dead.size() == 1);
}
'''.replace("DEAD", dead).replace("ACTUAL", actual)
    with tempfile.TemporaryDirectory(prefix="fsr-input-retirement-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: FSR inputs retire on GPU completion, not CPU frame age")


if __name__ == "__main__":
    main()
