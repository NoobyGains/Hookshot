"""Compile and run the rule that keeps the textures the GPU drew which the game samples again after finalizing them (gpu/vk/keep_resampled.h; no game/GPU)."""
import argparse
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]


def check_source():
    """The eviction pass still asks the rule with its bounded cap and the storage's owner, keep_finalized judges by its room in the shared cap, the flag is still set where a finalized texture is sampled again, and the switch is read"""
    src = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    for needle in ('#include "keep_resampled.h"',
                   "const uint64_t resampled_cap = keep_resampled::cap(keep_resampled_max, keep_finalized_max, size_budget, known, used, allowed);",
                   "if (!gpu_owns(tex)) return false;",
                   "keep_resampled::candidate(drawn_over_shifted(tex) || drawn_over(tex), gpu_owns(tex), tex->gpu_written, true,",
                   "keep_resampled::candidate(overwritten, gpu_owns(tex), tex->gpu_written, true, frame_no - last);",
                   "if (resampled_candidate && keep_resampled::keep(tex->bytes, resampled_total, resampled_cap)) {",
                   "if (resampled_cap && tex->resampled && keep_resampled::recent(frame_no - tex->last_frame)) return false;",
                   "const uint64_t finalized_room = keep_resampled::finalized_room(keep_finalized_max, resampled_total, resampled_cap);",
                   "if (finalized_kept <= finalized_room) continue;",
                   "const bool finalized_after_resampled = resampled_candidate && finalized_once(tex);",
                   "if (finalized_kept && (finalized_after_resampled || keep_finalized(tex))) {",
                   "if (tex->gpu_written && tex->released) tex->resampled = true;", 'getenv("RX_VK_KEEP_RESAMPLED_MB")'):
        if needle not in src:
            raise SystemExit("vk_texture.cpp no longer has: " + needle)
    if src.count("tex->resampled = false;") != src.count("tex->released = false;"):
        raise SystemExit("vk_texture.cpp: each place a texture is drawn again (released = false) must clear resampled too")
    if "bool resampled = false;" not in (ROOT / "gpu/vk/vk_texture.h").read_text(encoding="utf-8"):
        raise SystemExit("vk_texture.h no longer has the resampled flag")
    if "finalized_kept <= keep_finalized_max" in src:
        raise SystemExit("vk_texture.cpp: keep_finalized must judge by its room in the shared cap (finalized_room), not its own 512 MB")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="keep-resampled-") as tmp:
        exe = Path(tmp) / "keep-resampled"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "tests/test_keep_resampled.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
