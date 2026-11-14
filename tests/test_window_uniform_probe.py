"""Window rejects a non-canvas uniform before copying its projection.

Execute uniform_range's actual Window branch with submitted-memory readers.
A rejected block may later become a canvas at the same address/program: no
negative cache may hide that change, an inline update, or a live resize.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--cxx", "{cxx}"]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    args = parser.parse_args()
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text()
    probe = block(draw, "if (window_fit_active() && st.nvn_stage == 0 && u.size == OOT_UI_BLOCK_BYTES")
    source = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include "gpu/vk/oot_ui_squeeze.h"
static float submitted[36], updated[36], aspect = 2448.0f/1848;
static unsigned char stream[144];
static int full_reads, tail_reads, overlays;
static bool window = true, has_update = false, readable = true;
static bool window_fit_active() { return window; }
static bool ui_squeeze(uint8_t* b, uint64_t n) { return oot_ui_squeeze(b,n,aspect); }
static bool memory_read_as_submitted(uint64_t addr, void* dst, uint64_t n) {
    if (n == 144) ++full_reads; else ++tail_reads;
    if (!readable) return false;
    assert(addr >= 4096 && addr+n <= 4096+144);
    std::memcpy(dst,reinterpret_cast<uint8_t*>(submitted)+addr-4096,n);
    return true;
}
static bool ub_read(uint64_t addr, void* dst, uint64_t n) {
    if (!memory_read_as_submitted(addr,dst,n)) return false;
    if (has_update) std::memcpy(dst,reinterpret_cast<uint8_t*>(updated)+addr-4096,n);
    return true;
}
template<class Alloc> static uint64_t ub_overlay(uint64_t addr, uint64_t n, uint8_t* dst, Alloc alloc) {
    ++overlays;
    if (!has_update) return UINT64_MAX;
    const uint64_t at=alloc(n); assert(at==0);
    if (!ub_read(addr,dst,n)) return UINT64_MAX;
    return at;
}
static bool stream_reserve(uint64_t, uint64_t) { return true; }
static uint64_t stream_alloc(uint64_t, uint64_t) { return 0; }
struct Descriptor { int buffer; uint64_t at,n; };
static Descriptor probe(int stage=0, uint64_t size=144, uint64_t n=64) {
    const struct { int nvn_stage; } st{stage};
    const struct { uint64_t addr,size; } u{4096,size};
    const struct Stream { uint8_t* mapped; int stream; } recording{stream,7};
    const Stream* cur=&recording;
    const uint64_t align=16;
    BRANCH
    return {0,0,0};
}
static void canvas(float* f) {
    std::memset(f,0,144);
    f[0]=f[16]=(2.0f/3840)*OOT_UI_MARK;
    f[5]=2.0f/2160; f[21]=-f[5]; f[10]=f[26]=-1.0f/150;
    f[15]=f[31]=1;
    f[32]=f[34]=3840;f[33]=f[35]=2160;
}
int main() {
    // The same non-canvas 3D block: no full projection copy, but still one submitted tail read per call.
    for(int i=0;i<1000;++i) assert(probe().buffer==0);
    assert(full_reads==0 && overlays==0 && tail_reads==1000);
    // The same address can become a canvas through submitted inline updates.
    canvas(updated);has_update=true;
    assert(probe().buffer==7);
    float f[36]{};std::memcpy(f,stream,64);
    assert(std::fabs(f[5]-(2.0f/2160)*(aspect/(16.0f/9))) < 1e-8);
    aspect=2560.0f/1080;
    assert(probe().buffer==7);std::memcpy(f,stream,64);
    assert(std::fabs(f[0]-(2.0f/3840)*OOT_UI_MARK/ (aspect/(16.0f/9))) < 1e-8);
    // Tail match alone must not rewrite a 3D matrix or a full-screen canvas.
    updated[1]=1;assert(probe().buffer==0);updated[1]=0;
    updated[0]=updated[16]=2.0f/3840;assert(probe().buffer==0);
    // Off and unrelated slots make no probe reads, and unreadable data is rejected.
    int before=full_reads+tail_reads;
    window=false;assert(probe().buffer==0);window=true;
    assert(probe(1).buffer==0 && probe(0,128).buffer==0);
    assert(full_reads+tail_reads==before);
    readable=false;assert(probe().buffer==0);
    puts("PASS: non-canvas blocks skip full copies; submitted updates and live canvas resizes preserved");
}
'''.replace("BRANCH", probe)
    with tempfile.TemporaryDirectory(prefix="window-uniform-") as temp:
        path = Path(temp)
        cpp, exe = path / "probe.cpp", path / "probe"
        cpp.write_text(source)
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                        "-I", str(ROOT), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
