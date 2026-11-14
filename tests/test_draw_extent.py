# SPDX-License-Identifier: GPL-3.0-or-later
"""An indexed indirect draw binds every index its records may point at, and a vertex stream bound whole binds up to the
end of its pool, so the import the draw reads through holds those bytes.

draw()'s own vertex-stream loop and indirect branch, cut from gpu/vk/vk_draw.cpp, run against stand-ins: game pools,
imports made by 4 MB chunk around what is bound (pool_lookup with mirrors on), a device limit on an import's size, and
recorded Vulkan binds. For each binding the test takes the bytes the bound buffer holds from the binding's offset and
compares them with what the draw may read: an index anywhere in [ibuf, ibuf + 2^33 units) up to its pool's end (a 32-bit
first index plus a 32-bit count, both from the records on the GPU), a vertex up to its pool's end. Where no single import
can hold that (more than 1 GB, or the import fails), the draw binds as before, by 4 bytes or 1, and logs a line.

python -I -B tests/test_draw_extent.py --cxx g++ --headers <Vulkan include> [--source <a tree>]
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]
ROOT = Path(__file__).resolve().parents[1]

HEAD = r"""
#include <vulkan/vulkan.h>
#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#define FINE_SCOPE(...)
#define FINE_N(...)
int skips = 0;
#define SKIP_HERE() do { ++skips; return; } while (0)
/* BUFFER_REF */
/* DRAW_ARGS */
struct NvnState {
    struct Stream { uint32_t stride = 0, divisor = 0; } vstream[16];
    struct Buffer { uint64_t address = 0, size = 0; } vbuf[16];
};

// ---- guest memory: the game's pools, and imports by 4 MB chunk around a bound range in one pool (pool_lookup) ----
constexpr uint64_t kChunk = 4ull << 20, kVirtual = 1ull << 40;
struct Range { uint64_t lo, hi; };
std::vector<Range> pools, imports;   // (an import's VkBuffer is its index + 1)
uint64_t device_limit = UINT64_MAX;  // (the device's allocation or buffer limit: a larger import fails)
struct Bind { uint64_t addr, size; bool ok; };
std::vector<Bind> binds;
int pool_end_asks = 0;
std::vector<std::string> logged;
void logf(const char* f, ...) {
    char line[512];
    va_list ap;
    va_start(ap, f);
    std::vsnprintf(line, sizeof line, f, ap);
    va_end(ap);
    logged.push_back(line);
}
const Range* pool_holding(uint64_t a) {
    for (const Range& p : pools)
        if (a >= p.lo && a < p.hi) return &p;
    return nullptr;
}
// (above 1 TB an address is the host's, translated to the first pool's guest bytes: no pool end is known there)
uint64_t gpu_pool_end(uint64_t gpu) {
    ++pool_end_asks;
    const Range* p = pool_holding(gpu);
    return p ? p->hi : 0;
}
uint64_t stamp = 1;
uint64_t gpu_bind_stamp() { return stamp; }
BufferRef gpu_buffer_bind(uint64_t gpu, uint64_t size, bool) {
    const uint64_t guest = gpu >= kVirtual ? pools[0].lo + (gpu - kVirtual) : gpu;
    const Range* p = pool_holding(guest);
    const uint64_t lo = guest / kChunk * kChunk, hi = (guest + size + kChunk - 1) / kChunk * kChunk;
    const bool ok = p && size && size <= p->hi - guest && hi - lo <= device_limit;
    binds.push_back({gpu, size, ok});
    if (!ok) return {};
    imports.push_back({lo, hi});
    BufferRef r{};
    r.buffer = reinterpret_cast<VkBuffer>(static_cast<uintptr_t>(imports.size()));
    r.offset = guest - lo, r.size = size;
    return r;
}
uint64_t held_from(VkBuffer b, uint64_t offset) {   // (the bytes the bound buffer holds from offset)
    const Range& i = imports.at(reinterpret_cast<uintptr_t>(b) - 1);
    return i.hi - i.lo - offset;
}

// ---- the draw's bind state, and recorded Vulkan ----
/* LAST_VB */
LastVb last_vb{};
bool last_vb_valid = false;
/* VERTEX_SET */
VertexSet vertex_set{};
/* INDEX_BIND */
IndexBind last_ib{};
/* KEPT_VERTEX */
KeptVertex kept_vb[16]{};
VkBuffer zero_buffer = reinterpret_cast<VkBuffer>(uintptr_t{0xEE00});
struct Occ { void issue() {} } occ;
VkBuffer vb_bound[16]{};
VkDeviceSize vo_bound[16]{}, vz_bound[16]{};
int vertex_binds = 0, draws = 0;
VkBuffer ib_bound = VK_NULL_HANDLE;
VkDeviceSize io_bound = 0;
VkIndexType it_bound = VK_INDEX_TYPE_MAX_ENUM;
VKAPI_ATTR void VKAPI_CALL vkCmdBindVertexBuffers2(VkCommandBuffer, uint32_t first, uint32_t count, const VkBuffer* b,
                                                   const VkDeviceSize* o, const VkDeviceSize* z, const VkDeviceSize*) {
    ++vertex_binds;
    for (uint32_t i = 0; i < count && first + i < 16; i++) vb_bound[first + i] = b[i], vo_bound[first + i] = o[i], vz_bound[first + i] = z[i];
}
VKAPI_ATTR void VKAPI_CALL vkCmdBindIndexBuffer(VkCommandBuffer, VkBuffer b, VkDeviceSize o, VkIndexType t) {
    ib_bound = b, io_bound = o, it_bound = t;
}
VKAPI_ATTR void VKAPI_CALL vkCmdDrawIndexedIndirect(VkCommandBuffer, VkBuffer, VkDeviceSize, uint32_t, uint32_t) { ++draws; }
VKAPI_ATTR void VKAPI_CALL vkCmdDrawIndexedIndirectCount(VkCommandBuffer, VkBuffer, VkDeviceSize, VkBuffer, VkDeviceSize,
                                                         uint32_t, uint32_t) { ++draws; }
VKAPI_ATTR void VKAPI_CALL vkCmdDrawIndirect(VkCommandBuffer, VkBuffer, VkDeviceSize, uint32_t, uint32_t) { ++draws; }
VKAPI_ATTR void VKAPI_CALL vkCmdDrawIndirectCount(VkCommandBuffer, VkBuffer, VkDeviceSize, VkBuffer, VkDeviceSize, uint32_t,
                                                  uint32_t) { ++draws; }
/* VERTEX_BIND_REUSE */
/* VERTEX_SET_SAME */
/* INDEX_BIND_SAME */
/* BIND_INDEX */
/* EXTENT */

// ---- draw()'s vertex streams and its indirect branch, as they are in the source ----
void draw_binds(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d) {
/* VERTICES */
    (void)vertex_complete;
/* ITYPE */
/* INDIRECT */
}
"""

MAIN = r"""
int failures = 0;
void check(bool ok, const char* what, const char* detail) {
    if (!ok) {
        std::printf("FAIL: %s: %s\n", what, detail);
        ++failures;
    }
}
constexpr uint64_t kGiB = 1ull << 30, kMiB = 1ull << 20;
// (what the draw may read, worked out here: an index in [ibuf, ibuf + 2^33 units) to its pool's end; 4 bytes in no pool)
uint64_t may_read_indices(uint64_t ibuf, uint32_t unit) {
    const Range* p = pool_holding(ibuf);
    return p ? std::min(p->hi - ibuf, (uint64_t)unit << 33) : 4;
}
uint64_t may_read_vertices(uint64_t addr) {
    const Range* p = pool_holding(addr);
    return p ? p->hi - addr : 1;
}
void fresh() {
    binds.clear(), logged.clear(), skips = 0, draws = 0, vertex_binds = 0, ib_bound = VK_NULL_HANDLE, last_ib.on = false;
    device_limit = UINT64_MAX;
}
bool too_large_asked() {
    for (const Bind& b : binds)
        if (b.size > kGiB) return true;
    return false;
}
DrawArgs indexed_indirect(uint64_t ibuf, int itype) {
    DrawArgs d{};
    d.indexed = true, d.itype = itype, d.ibuf = ibuf, d.indirect = pools[0].lo + 0x1000, d.max = 4, d.stride = 20;
    return d;
}
bool logged_once(uint64_t addr, uint64_t extent) {
    char a[32], e[32];
    std::snprintf(a, sizeof a, "%#llx", (unsigned long long)addr);
    std::snprintf(e, sizeof e, " %llu ", (unsigned long long)extent);
    return logged.size() == 1 && logged[0].find(a) != std::string::npos && logged[0].find(e) != std::string::npos;
}
int main() {
    VkCommandBuffer cmd = reinterpret_cast<VkCommandBuffer>(uintptr_t{1});
    pools = {{0x1000100000ull, 0x1000100000ull + 120 * kMiB}, {0x2000000000ull, 0x2000000000ull + 10 * kGiB}};
    NvnState none{};
    char detail[256];

    // 1. u16 indices 64 bytes before a 4 MB chunk's end, in a 120 MB pool: bound to the pool's end
    fresh();
    {
        const uint64_t ibuf = 0x1000400000ull - 64, want = may_read_indices(ibuf, 2);
        draw_binds(cmd, none, indexed_indirect(ibuf, 1));
        const uint64_t held = ib_bound ? held_from(ib_bound, io_bound) : 0;
        std::snprintf(detail, sizeof detail, "the bound index buffer holds %llu of the %llu bytes the draw may read",
                      (unsigned long long)held, (unsigned long long)want);
        check(draws == 1 && held >= want, "an indexed indirect draw's indices past the import holding its first bytes", detail);
        check(it_bound == VK_INDEX_TYPE_UINT16 && logged.empty(), "the index type, and no line", "wrong type or a line logged");
    }
    // 2. u8 indices in a 10 GB pool: 2^33 bytes may be read, more than one import holds: bound by 4 as before, logged
    fresh();
    {
        const uint64_t ibuf = pools[1].lo + 0x100, want = may_read_indices(ibuf, 1);
        draw_binds(cmd, none, indexed_indirect(ibuf, 0));
        std::snprintf(detail, sizeof detail, "%d draws, %zu lines logged, %s", draws, logged.size(),
                      too_large_asked() ? "an import over 1 GB asked for" : "no import over 1 GB asked for");
        check(draws == 1 && want == (1ull << 33) && !too_large_asked() && logged_once(ibuf, want),
              "an index extent of 2^33 bytes (u8) is bound by 4 bytes as before, with one line", detail);
        check(binds.back().addr == ibuf && binds.back().size == 4, "that binding is by 4 bytes", "not by 4 bytes");
    }
    // 3. u32 indices there: the pool's end is nearer than 2^35 bytes
    fresh();
    {
        const uint64_t ibuf = pools[1].lo + 0x100, want = may_read_indices(ibuf, 4);
        draw_binds(cmd, none, indexed_indirect(ibuf, 2));
        std::snprintf(detail, sizeof detail, "%zu lines logged", logged.size());
        check(draws == 1 && want == pools[1].hi - ibuf && logged_once(ibuf, want),
              "a u32 extent ends at the pool's end, 10 GB on: bound by 4 bytes as before, with one line", detail);
    }
    // 4. the import of the extent fails (a device limit of 64 MB): bound by 4 bytes as before, logged
    fresh();
    {
        device_limit = 64 * kMiB;
        const uint64_t ibuf = pools[0].lo + 0x40, want = may_read_indices(ibuf, 2);
        draw_binds(cmd, none, indexed_indirect(ibuf, 1));
        std::snprintf(detail, sizeof detail, "%d draws, %d skipped, %zu lines logged", draws, skips, logged.size());
        check(draws == 1 && skips == 0 && ib_bound && binds.back().size == 4 && logged_once(ibuf, want),
              "an extent whose import fails is bound by 4 bytes as before, with one line", detail);
    }
    // 5. above 1 TB no pool end is known: 4 bytes, as before, no line
    fresh();
    {
        const uint64_t ibuf = kVirtual + 0x80;
        draw_binds(cmd, none, indexed_indirect(ibuf, 1));
        check(draws == 1 && binds.back().addr == ibuf && binds.back().size == 4 && logged.empty(),
              "an index buffer with no pool end is bound by 4 bytes as before", "not so");
    }
    // 6. an indirect draw that is not indexed binds no index buffer
    fresh();
    {
        DrawArgs d = indexed_indirect(pools[0].lo, 1);
        d.indexed = false, d.stride = 16;
        draw_binds(cmd, none, d);
        check(draws == 1 && !ib_bound && binds.size() == 1, "a non-indexed indirect draw", "an index buffer bound");
    }

    // 7. vertex streams: 0 sized, 1 bound whole 16 bytes before a chunk's end, 2 bound whole above 1 TB
    fresh();
    NvnState s{};
    const uint64_t v0 = 0x1000400000ull - 32, v1 = 0x1000800000ull - 16, v2 = kVirtual + 0x200;
    s.vbuf[0] = {v0, 64}, s.vstream[0].stride = 16;
    s.vbuf[1] = {v1, 0}, s.vstream[1].stride = 12;
    s.vbuf[2] = {v2, 0}, s.vstream[2].stride = 8;
    DrawArgs plain{};
    plain.indirect = pools[0].lo + 0x1000, plain.max = 1;
    draw_binds(cmd, s, plain);
    {
        const uint64_t want = may_read_vertices(v1);
        const uint64_t held = vb_bound[1] && vb_bound[1] != zero_buffer ? held_from(vb_bound[1], vo_bound[1]) : 0;
        std::snprintf(detail, sizeof detail, "the bound buffer holds %llu of the %llu bytes the stream may read",
                      (unsigned long long)held, (unsigned long long)want);
        check(vertex_binds == 1 && vz_bound[1] == VK_WHOLE_SIZE && held >= want,
              "a vertex stream bound whole, its vertices past the import holding its first byte", detail);
        check(vz_bound[0] == 64 && binds[0].addr == v0 && binds[0].size == 64, "a stream with a size binds that size",
              "not its size");
        bool v2_by_one = false;
        for (const Bind& b : binds)
            if (b.addr == v2 && b.size == 1) v2_by_one = true;
        check(v2_by_one && vz_bound[2] == VK_WHOLE_SIZE && logged.empty(),
              "a stream bound whole with no pool end is bound by 1 byte as before", "not so");
    }
    // 8. the same streams on a new command buffer: the kept bindings, no lookup and no pool end asked again
    {
        const size_t had = binds.size();
        const int asked = pool_end_asks;
        vertex_set.on = false, last_vb_valid = false;
        draw_binds(cmd, s, plain);
        std::snprintf(detail, sizeof detail, "%zu lookups and %d pool ends asked again", binds.size() - had - 1,
                      pool_end_asks - asked);
        check(vertex_binds == 2 && binds.size() == had + 1 && pool_end_asks == asked,
              "a kept stream is not looked up again (only the draw's records are)", detail);
    }
    // 9. a stream bound whole in the 10 GB pool: more than one import holds, bound by 1 byte as before, logged
    fresh();
    {
        NvnState w{};
        const uint64_t v = pools[1].lo + 0x300;
        w.vbuf[0] = {v, 0}, w.vstream[0].stride = 16;
        vertex_set.on = false, stamp++;
        draw_binds(cmd, w, plain);
        std::snprintf(detail, sizeof detail, "%zu lines logged, %s", logged.size(),
                      too_large_asked() ? "an import over 1 GB asked for" : "no import over 1 GB asked for");
        check(vb_bound[0] != zero_buffer && vz_bound[0] == VK_WHOLE_SIZE && !too_large_asked() &&
                  logged_once(v, may_read_vertices(v)),
              "a stream bound whole past 1 GB of its pool is bound by 1 byte as before, with one line", detail);
    }

    if (failures) {
        std::printf("FAIL: %d of the checks above\n", failures);
        return 1;
    }
    std::puts("PASS: an indexed indirect draw binds the indices it may read and a stream bound whole its pool, both in one "
              "import; past 1 GB or a failed import as before, with a line:");
    fresh();
    draw_binds(cmd, none, indexed_indirect(pools[1].lo + 0x100, 0));
    for (const std::string& l : logged) std::printf("  %s\n", l.c_str());
    return 0;
}
"""


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
    parser.add_argument("--cxx", default="g++")
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT, help="the tree whose renderer is tested (default: this one)")
    args = parser.parse_args()
    vk = args.source / "gpu" / "vk"
    source = (vk / "vk_draw.cpp").read_text(encoding="utf-8")
    header = (vk / "vk_draw.h").read_text(encoding="utf-8")
    internal = (vk / "vk_internal.h").read_text(encoding="utf-8")
    draw = block(source, "void draw(VkCommandBuffer cmd, NvnState& s, const DrawArgs& d) {")
    fixture = HEAD.replace("/* BUFFER_REF */", block(internal, "struct BufferRef {") + ";")
    fixture = fixture.replace("/* DRAW_ARGS */", block(header, "struct DrawArgs {") + ";")
    for token, marker in [
            ("LAST_VB", "struct LastVb {"), ("VERTEX_SET", "struct VertexSet {"), ("INDEX_BIND", "struct IndexBind {"),
            ("KEPT_VERTEX", "struct KeptVertex {"), ("VERTEX_BIND_REUSE", "bool vertex_bind_reuse("),
            ("VERTEX_SET_SAME", "bool vertex_set_same("), ("INDEX_BIND_SAME", "bool index_bind_same("),
            ("BIND_INDEX", "void bind_index(")]:
        fixture = fixture.replace("/* " + token + " */", block(source, marker) + (";" if marker.startswith("struct ") else ""))
    # (the helpers the two blocks bind through, where the source has them)
    extent = ""
    for marker in ("uint64_t index_extent(", "uint64_t vertex_whole_extent("):
        if marker in source:
            extent += block(source, marker) + "\n"
    if "constexpr uint64_t kImportMax" in source:
        limit = source[source.index("constexpr uint64_t kImportMax"):]
        extent += limit[:limit.index("\n") + 1]
    if "BufferRef extent_bind(" in source:
        extent += block(source, "BufferRef extent_bind(") + "\n"
    fixture = fixture.replace("/* EXTENT */", extent)
    start = draw.index("    uint64_t vaddr[16]{};")
    end = draw.index("    if (g_fine) fine_ns[FT_VERTEX]", start)
    fixture = fixture.replace("/* VERTICES */", draw[start:end])
    itype = draw[draw.index("    const VkIndexType itype ="):]
    fixture = fixture.replace("/* ITYPE */", itype[:itype.index("\n") + 1])
    fixture = fixture.replace("/* INDIRECT */", block(draw, "    if (d.indirect) {\n        // (hookshot) the records the draw reads"))
    with tempfile.TemporaryDirectory(prefix="hookshot-draw-extent-") as temp:
        cpp, exe = Path(temp) / "extent.cpp", Path(temp) / "extent.exe"
        cpp.write_text(fixture + MAIN, encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
                        "-I", str(args.headers), str(cpp), "-o", str(exe)], check=True)
        raise SystemExit(subprocess.run([str(exe)]).returncode)


if __name__ == "__main__":
    main()
