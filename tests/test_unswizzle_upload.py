"""Run gpu/vk/vk_texture.cpp's unswizzle source choice and its threaded CPU unswizzle against a model of guest memory.

upload_unswizzle_gpu takes the GPU unswizzle only from a pool an import already holds (vk_memory.cpp
memory_guest_contained). A texture no pool holds, half in one, split between two, in a virtual mapping that breaks
before its end, or unmapped, takes the CPU path without reaching for a pool: gpu_buffer would import one for it, 22-25 ms
on the replay thread. RX_VK_UNSWIZZLE_IMPORT=1 imports as before (a process of its own: the switch is read once).

upload_inner unswizzles a 2D level's GOB-block rows on several threads from 4 MB. Each case is compared with one call of
suyu's real UnswizzleTexture over the whole level: just under and at 4 MB, a width that is no GOB multiple with a
partial last block row, partial uploads (rows from the middle, and to the end), sparse storage gathered by gpu_read, and
storage ending inside the level's span.

    python tests/test_unswizzle_upload.py --headers <Vulkan include> --cxx <compiler> [--source <checkout>]

--source runs another checkout's code in the same fixture: on a main from before this change, the cases that should take
the CPU path reach for a pool, and the 4-16 MB levels run on one thread.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
CHOICES = ["contained", "exact", "missing", "partial", "split", "virtual", "virtual-missing", "noncontiguous", "unmapped"]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def actual(source):
    tex = (source / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    mem = (source / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
    # the choice: what upload_unswizzle_gpu does once the texture suits it, up to the pool lookup (an import when none
    # holds it)
    fn = block(tex, "bool upload_unswizzle_gpu(")
    start = fn.index("\n", fn.index("if (!unswizzle_ready()) return false;")) + 1
    lookup = "const BufferRef src = gpu_buffer(tex.gpu, total);"
    choice = fn[start:fn.index(lookup) + len(lookup)]
    marker = "int memory_guest_contained("
    contained = block(mem, marker) if marker in mem else ""
    # the rows: from where a block-linear level's source is found to the unswizzle's timing
    cpu = block(tex, "bool upload_inner(Texture& tex, const Ranges* dirty, uint64_t* moved) {")
    start = cpu.rindex("\n", 0, cpu.index("const uint64_t from = src_off")) + 1
    end = cpu.index(";", cpu.index("st_unswizzle_ns +=", start)) + 1
    rows = cpu[start:end]
    for old, new in [("std::thread::hardware_concurrency()", "fixture_cpus()"),
                     ("Tegra::Texture::UnswizzleTexture(", "counted_unswizzle("), ("logf(", "test_log(")]:
        assert old in rows, old
        rows = rows.replace(old, new)
    return {"/* ACTUAL CONTAINED */": contained, "/* ACTUAL CHOICE */": choice, "/* ACTUAL ROWS */": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", type=Path, default=ROOT)
    p.add_argument("--headers", type=Path, required=True)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    fixture = (ROOT / "tests/unswizzle_upload_test.cpp").read_text(encoding="utf-8")
    for marker, code in actual(a.source).items():
        assert marker in fixture, marker
        fixture = fixture.replace(marker, code)
    # (suyu's and the Vulkan headers as system headers: the fixture's own warnings are errors, not theirs)
    inc = ["-isystem", str(a.source / "gpu/third_party/suyu"), "-isystem", str(a.headers)]
    inc += ["-I" + str(a.source / d) for d in ("gpu/compat", "gpu/vk/compat")]
    threads = [] if sys.platform == "win32" else ["-pthread"]
    failed = []
    with tempfile.TemporaryDirectory(prefix="unswizzle-upload-") as temp:
        cpp, obj, exe = Path(temp) / "fixture.cpp", Path(temp) / "decoders.o", Path(temp) / "fixture.exe"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-O2", "-w", *inc, "-c",
                        str(a.source / "gpu/third_party/suyu/video_core/textures/decoders.cpp"), "-o", str(obj)], check=True)
        # (_CRT_SECURE_NO_WARNINGS: the MSVC CRT's getenv deprecation, as the game's own Windows build passes)
        subprocess.run([a.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-D_CRT_SECURE_NO_WARNINGS", *inc, *threads,
                        str(cpp), str(obj),
                        "-o", str(exe)], check=True)
        env = {k: v for k, v in os.environ.items() if k != "RX_VK_UNSWIZZLE_IMPORT"}
        runs = [(c, env) for c in CHOICES] + [("override", dict(env, RX_VK_UNSWIZZLE_IMPORT="1")), ("rows", env)]
        for case, case_env in runs:
            r = subprocess.run([str(exe), case], env=case_env, capture_output=True, text=True, timeout=300)
            sys.stdout.write(r.stdout + r.stderr)
            if r.returncode:
                failed.append(case)
    if failed:
        sys.exit("failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
