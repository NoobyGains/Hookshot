"""A GPU buffer's write older than a pass's drawing no longer replaces the drawing (gpu/vk/vk_texture.cpp).

After the game finalizes an image the GPU drew, the image's next check asks what changed in its storage since, and
uploads the whole image from guest memory when a GPU buffer wrote that storage (gpu_wrote_into). That write was compared
only with the last such write the texture had seen, never with the drawing, so a render target made over a buffer's old
storage counted that older write as newer, and the whole image was uploaded over what the pass drew.
texture_rendered, which only a pass calls, now takes buffer writes of earlier submissions as older than the drawing.

Cuts texture_written, texture_rendered, texture_released, texture_dirty, texture_gpu_wrote, gpu_wrote_into and
texture_touch's check of an uploaded texture out of the source as they are, and checks:
- a buffer write of a submission before the pass: not taken;
- one after the drawing, one in the pass's own submission, and one before a copy into the texture (no pass): taken, as
  before;
- drawn and finalized with no buffer write: kept, as before.
Then again with RX_VK_NO_DRAWN_OVER_BUFFER_WRITE=1, where the first case is taken too, as before.

python -I -B tests/test_drawn_target.py [--cxx g++] [--source path/to/vk_texture.cpp]
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]
ENV_ON_H = ROOT / "gpu" / "vk" / "compat" / "hookshot_env.h"
SWITCH = "RX_VK_NO_DRAWN_OVER_BUFFER_WRITE"

FIXTURE = r'''#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#if defined(__GNUC__) && !defined(__clang__) && __GNUC__ >= 13
#pragma GCC diagnostic ignored "-Wdangling-reference"   // (texture_dirty's runs.back(): the vector's element)
#endif
namespace mkwvk {
using Ranges = std::vector<std::pair<uint64_t, uint64_t>>;
struct Texture {   // (the fields the code cut out uses, as gpu/vk/vk_texture.h has them)
    uint32_t width = 64, height = 64, layers = 1;
    bool sparse = false;
    uint64_t gpu = 0, guest = 0, guest_size = 0, bytes = 0;
    int nvn_format = 0x25;
    bool uploaded = false, gpu_written = false, only_cleared = false, released = false, resampled = false;
    uint32_t upload_gen = 0, gpu_gen = 0, release_gen = 0, id = 0;
    uint64_t map_sig = 0;
    std::vector<uint64_t> page_map;
    struct Run { uint64_t off, guest, n; };
    std::vector<Run> runs;
    uint32_t runs_maps_gen = ~0u;
    uint64_t last_written = 0, first_written = 0, upload_value = 0, upload_seg = 0, first_seen = 0;
    uint64_t gpu_wrote_seen = 0, first_render_frame = 0, owned_frame = 0;
};
struct nvn_tex { uint64_t gpu = 0; };
std::unordered_map<uint32_t, std::unique_ptr<Texture>> textures;
std::unordered_multimap<uint64_t, Texture*> by_gpu;
uint64_t frame_no = 1, rec_value = 1, completed_value = 0;
thread_local uint64_t tl_seg = 0, tl_watch_prog = 0;
void logf(const char*, ...) {}
enum LogLevel : int { log_error, log_warn, log_info, log_debug, log_trace };
void logf_at(LogLevel, const char*, ...) {}
void vw_note(Texture&) {}
void watch_tex(const Texture*, const char*) {}
void drawn_writeback_note(Texture*) {}
bool texture_resident(Texture*, uint32_t, uint32_t) { return true; }
std::mutex gpu_wrote_mu;
std::map<uint64_t, std::pair<uint64_t, uint64_t>> gpu_wrote;
std::map<uint64_t, std::pair<uint64_t, uint32_t>> gpu_owned;

// (the host's GPU mappings: each 64 KB virtual page's guest address. `walks` counts the lookups, a page walk's)
std::map<uint64_t, uint64_t> vpages;
uint32_t maps_now = 1;
int walks = 0;
uint64_t gpu_guest(uint64_t gpu) {
    walks++;
    const auto it = vpages.find(gpu & ~0xFFFFull);
    return it == vpages.end() ? 0 : it->second + (gpu & 0xFFFF);
}
uint32_t maps_generation() { return maps_now; }
uint32_t vmap_generation() { return 1; }
struct Host {
    uint64_t (*gpu_guest)(uint64_t gpu);
    uint32_t (*maps_generation)();
    uint32_t (*vmap_generation)();
};
const Host the_host{gpu_guest, maps_generation, vmap_generation};
const Host* host = &the_host;

// (guest memory's page generations, as vk_memory.cpp keeps them: 4 KB pages)
std::map<uint64_t, uint32_t> page_gen;
uint32_t gen_now = 1;
uint32_t memory_generation() { return gen_now; }
void cpu_write(uint64_t guest, uint64_t n) {
    gen_now++;
    for (uint64_t p = guest >> 12; p <= (guest + n - 1) >> 12; p++) page_gen[p] = gen_now;
}
void memory_written_runs(uint64_t guest, uint64_t size, uint32_t gen, Ranges& out) {
    for (uint64_t p = guest >> 12; size && p <= (guest + size - 1) >> 12; p++) {
        const auto it = page_gen.find(p);
        if (it == page_gen.end() || it->second <= gen) continue;
        const uint64_t lo = std::max(p << 12, guest) - guest, hi = std::min((p + 1) << 12, guest + size) - guest;
        if (!out.empty() && out.back().second == lo) out.back().second = hi;
        else out.push_back({lo, hi});
    }
}

CUT_MIX
CUT_DIRTY
CUT_DECLARATION
CUT_WRITTEN
CUT_GPU_WROTE
CUT_WROTE_INTO
CUT_RENDERED
CUT_RELEASED

// (texture_touch's check of a texture uploaded, or marked so by texture_written, its lines as they are: the texture back
// when it is not uploaded again, nullptr when it is, with what it took for written left in `dirty`)
Ranges dirty;
Texture* touch(Texture* tex) {
    const bool gpu_part = false;   // (a GPU write is taken whole here: the ranges it names are tests/test_gpu_write_part.py's)
CUT_GPU_DIRTY
CUT_SINCE
CUT_CHECK
    if (gpu_dirty) dirty.assign(1, {0, tex->guest_size});   // (upload(*tex, nullptr): all of it)
    tex->uploaded = true, tex->upload_gen = memory_generation(), tex->gpu_written = tex->released = false;
    return nullptr;
}
}  // namespace mkwvk

using namespace mkwvk;
namespace {
int failed = 0;
const uint64_t vpool = 1ull << 40;
Ranges span(uint64_t lo, uint64_t hi) { return Ranges{{lo, hi}}; }
void expect(bool ok, const char* what) {
    if (ok) return;
    failed++;
    std::printf("FAIL: %s; taken for written:", what);
    for (const auto& [lo, hi] : dirty) std::printf(" {%#llx, %#llx}", (unsigned long long)lo, (unsigned long long)hi);
    std::printf("\n");
}
Texture* make(uint64_t gpu, uint64_t guest, uint64_t size) {
    auto t = std::make_unique<Texture>();
    t->id = (uint32_t)textures.size() + 1, t->gpu = gpu, t->guest = guest, t->guest_size = t->bytes = size;
    for (uint64_t off = 0; gpu >= vpool && off < size; off += 0x10000) vpages[gpu + off] = guest + off;
    Texture* p = t.get();
    by_gpu.emplace(gpu, p);
    textures[p->id] = std::move(t);
    return p;
}
void next_frame() { frame_no++, rec_value++, completed_value = rec_value - 1; }
void draw(Texture* t) {   // (a pass draws into it, as begin_pass calls them)
    texture_written(t, "a pass's colour target");
    texture_rendered(t);
}
void finalize(Texture* t) {   // (the game finalizes it, then samples it a frame later, its submissions done)
    nvn_tex n;
    n.gpu = t->gpu;
    texture_released(&n);
    next_frame();
    completed_value = rec_value;
}
}  // namespace

int main(int argc, char**) {
    const bool old = argc > 1;   // (RX_VK_NO_DRAWN_OVER_BUFFER_WRITE=1)

    // A target made over storage a GPU buffer wrote in an earlier submission (a buffer's old storage, after an area load)
    Texture* over = make(0x90000000, 0x90000000, 0x8000);
    texture_gpu_wrote(over->gpu + 0x2000, 0x1000);
    next_frame();
    draw(over);
    finalize(over);
    Texture* kept = touch(over);
    expect(old ? !kept && dirty == span(0, 0x8000) : kept == over,
           old ? "as before: a buffer's write before the pass, all of it" : "a buffer's write of a submission before the pass: kept");
    // One after the drawing is newer: all of it, as before
    texture_gpu_wrote(over->gpu + 0x2000, 0x1000);
    next_frame();
    completed_value = rec_value;
    kept = touch(over);
    expect(!kept && dirty == span(0, 0x8000), "a buffer's write after the drawing: all of it, as before");

    // One in the pass's own submission: which came first is not known, so all of it, as before
    Texture* same = make(0x90100000, 0x90100000, 0x8000);
    texture_gpu_wrote(same->gpu, 0x1000);
    draw(same);
    finalize(same);
    kept = touch(same);
    expect(!kept && dirty == span(0, 0x8000), "a buffer's write in the pass's own submission: all of it, as before");

    // One before a copy into the texture (no pass): all of it, as before
    Texture* copied = make(0x90300000, 0x90300000, 0x8000);
    texture_gpu_wrote(copied->gpu, 0x1000);
    next_frame();
    texture_written(copied, "a texture-to-texture copy");
    finalize(copied);
    kept = touch(copied);
    expect(!kept && dirty == span(0, 0x8000), "a buffer's write before a copy into the texture: all of it, as before");

    // Drawn and finalized with no buffer write: kept, as before
    Texture* low = make(0x90200000, 0x90200000, 0x8000);
    draw(low);
    finalize(low);
    kept = touch(low);
    expect(kept == low, "drawn and finalized, nothing written since: kept, as before");

    if (failed) return 1;
    std::printf("PASS: %s\n", old ? "RX_VK_NO_DRAWN_OVER_BUFFER_WRITE=1: a buffer's write before the pass replaces the "
                                    "drawing, as before"
                                  : "a GPU buffer's write of a submission before the pass no longer replaces the drawing");
    return 0;
}
'''


def cut(text, start, what):
    """From start, found once, to the end of its function: the first closing brace at the start of a line"""
    if text.count(start) != 1:
        raise SystemExit("%s: %r is there %d times, not once: update this check" % (what, start, text.count(start)))
    at = text.index(start)
    return text[at:text.index("\n}\n", at) + 3]


def line(text, start, what):
    """From start, found once, to the end of its line"""
    if text.count(start) != 1:
        raise SystemExit("%s: %r is there %d times, not once: update this check" % (what, start, text.count(start)))
    at = text.index(start)
    return text[at:text.index("\n", at)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--source", type=Path, default=ROOT / "gpu" / "vk" / "vk_texture.cpp",
                   help="the vk_texture.cpp to cut the code from (main's: the check fails there)")
    a = p.parse_args()
    src = a.source.read_text(encoding="utf-8")
    header = (ROOT / "gpu" / "vk" / "vk_texture.h").read_text(encoding="utf-8")
    declaration = line(header, "void texture_written(", "vk_texture.h")
    declaration = declaration[:declaration.index(";") + 1]
    touch = cut(src, "Texture* texture_touch(Texture* tex, bool for_sampling) {", "texture_touch")
    code = FIXTURE
    for name, part in (("CUT_MIX", cut(src, "uint64_t mix(uint64_t h, uint64_t v) {", "mix")),
                       ("CUT_DIRTY", cut(src, "bool texture_dirty(Texture& tex, uint32_t gen, Ranges& out) {", "texture_dirty")),
                       ("CUT_DECLARATION", declaration),
                       ("CUT_WRITTEN", cut(src, "void texture_written(Texture* tex, const char* why) {", "texture_written")),
                       ("CUT_GPU_WROTE", cut(src, "void texture_gpu_wrote(uint64_t gpu, uint64_t size) {", "texture_gpu_wrote")),
                       ("CUT_WROTE_INTO", cut(src, "bool gpu_wrote_into(Texture& tex, Ranges* out) {", "gpu_wrote_into")),
                       ("CUT_RENDERED", cut(src, "void texture_rendered(Texture* tex) {", "texture_rendered")),
                       ("CUT_RELEASED", cut(src, "void texture_released(const nvn_tex* t) {", "texture_released")),
                       ("CUT_GPU_DIRTY", line(touch, "    const bool gpu_dirty = ", "texture_touch")),
                       ("CUT_SINCE", line(touch, "    const uint32_t since = ", "texture_touch")),
                       ("CUT_CHECK", line(touch, "    if (tex->uploaded && !gpu_dirty && !texture_dirty(*tex, since, dirty)) return tex;",
                                          "texture_touch"))):
        code = code.replace(name, part)
    cxx = shutil.which(a.cxx) or shutil.which("g++") or shutil.which("clang++")
    if not cxx:
        print("SKIP: no C++ compiler")
        return
    with tempfile.TemporaryDirectory(prefix="drawn-target-") as tmp:
        tmp = Path(tmp)
        (tmp / "f.cpp").write_text(code, encoding="utf-8")
        exe = tmp / ("f.exe" if os.name == "nt" else "f")
        built = subprocess.run([cxx, "-std=c++20", "-include", str(ENV_ON_H), "-O0", "-Wall", "-Wextra", "-Werror",
                                str(tmp / "f.cpp"), "-o", str(exe)])
        if built.returncode:
            raise SystemExit("FAIL: the code cut out of %s does not build in this test's FIXTURE: if the error names a "
                             "Texture field, a global or a function that code uses, add it to FIXTURE" % a.source.name)
        env = {k: v for k, v in os.environ.items() if k not in (SWITCH, "RX_VK_LOG_REMAP", "RX_VK_WATCH_GPU_WRITE")}
        env["PATH"] = str(Path(cxx).parent) + os.pathsep + env.get("PATH", "")   # (a compiler's runtime DLLs, llvm-mingw's)
        for extra in ({}, {SWITCH: "1"}):
            r = subprocess.run([str(exe)] + (["old"] if extra else []), env={**env, **extra}, capture_output=True, text=True)
            print((r.stdout + r.stderr).strip())
            if r.returncode:
                raise SystemExit("FAIL%s: the code cut out of %s" % (" with %s=1" % SWITCH if extra else "", a.source.name))


if __name__ == "__main__":
    main()
