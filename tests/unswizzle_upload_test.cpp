// Two parts of gpu/vk/vk_texture.cpp cut from the source and run against a model of guest memory
// (tests/test_unswizzle_upload.py pastes them in place of the ACTUAL markers):
//   - upload_unswizzle_gpu's choice of a source, with vk_memory.cpp's memory_guest_contained: the GPU unswizzle only
//     from a pool already imported, the CPU path for everything else (RX_VK_UNSWIZZLE_IMPORT=1: an import as before);
//   - upload_inner's CPU unswizzle of a block-linear 2D level's GOB-block rows, on several threads from 4 MB, with
//     suyu's real UnswizzleTexture, against one call of it over the whole level.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <random>
#include <set>
#include <span>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "hookshot_env.h"
#include "video_core/textures/decoders.h"

namespace {

int failures;
void check(bool ok, const char* what, int line) {
    if (!ok) {
        std::printf("FAIL line %d: %s\n", line, what);
        failures++;
    }
}
#define CHECK(x) check((x), #x, __LINE__)

void test_log(const char* fmt, ...) { (void)fmt; }

// ---- the guest memory model: one mapped GPU range, its bytes, and where gpu_ptr's contiguous view of it ends
struct Model {
    uint64_t lo = 0, hi = 0;          // the GPU addresses mapped
    uint64_t contiguous_to = 0;       // gpu_ptr's view ends here (0: at hi); past it, a separate mapping
    bool direct = true;               // false: gpu_ptr sees none of it (sparse storage: gpu_read only)
    uint64_t virt_guest = 0;          // a GPU address above 1 TB: the guest address its lo maps to
    std::vector<uint8_t> bytes;       // the storage (empty: the choice's cases, which read none of it)
} model;
const uint8_t dummy_byte = 0;

struct Host {
    const uint8_t* gpu_ptr(uint64_t gpu, uint64_t* avail) const {
        if (!model.direct || gpu < model.lo || gpu >= model.hi) return nullptr;
        const uint64_t end = model.contiguous_to && gpu < model.contiguous_to ? model.contiguous_to : model.hi;
        *avail = end - gpu;
        return model.bytes.empty() ? &dummy_byte : model.bytes.data() + (gpu - model.lo);
    }
    uint64_t gpu_guest(uint64_t gpu) const { return gpu - model.lo + model.virt_guest; }
    bool gpu_read(uint64_t gpu, void* out, uint64_t n) const {
        if (gpu < model.lo || gpu + n > model.hi || gpu + n > model.lo + model.bytes.size()) {
            std::printf("FAIL: a read past the storage: %#llx + %llu\n", (unsigned long long)gpu, (unsigned long long)n);
            std::exit(1);
        }
        std::memcpy(out, model.bytes.data() + (gpu - model.lo), n);
        return true;
    }
};
Host host_model;
Host* host = &host_model;

// ---- the choice of a source
std::mutex pools_mu;
struct Pool {
    uint64_t lo = 0, hi = 0;
};
std::map<uint64_t, Pool> imported;   // (by lo, as vk_memory.cpp keeps them)

struct BufferRef {
    uint64_t buffer = 0, offset = 0;
    explicit operator bool() const { return buffer != 0; }
};
int lookups, imports;   // gpu_buffer's calls, and those no imported pool held (production imports a pool for them)
BufferRef gpu_buffer(uint64_t gpu, uint64_t size) {
    std::lock_guard lk(pools_mu);   // (as production's lookup)
    lookups++;
    const uint64_t guest = gpu < (1ull << 40) ? gpu : host->gpu_guest(gpu);
    bool held = false;
    for (const auto& [lo, p] : imported) held |= p.lo <= guest && guest + size <= p.hi;
    if (!held) imports++;
    return {1, 0};
}
struct Texture {
    uint64_t gpu = 0;
};

/* ACTUAL CONTAINED */

bool choose(Texture& tex, uint64_t total) {
/* ACTUAL CHOICE */
    return (bool)src;
}

// ---- the CPU unswizzle's rows
struct LevelGeo {
    uint32_t tw = 0, td = 1;
    unsigned tile_h = 0, tile_d = 0;
};
unsigned cpus = 16;
unsigned fixture_cpus() { return cpus; }
int64_t st_unswizzle_bytes, st_unswizzle_ns;
std::mutex seen_mu;
std::set<std::thread::id> seen;   // (the threads UnswizzleTexture ran on)
void counted_unswizzle(std::span<u8> out, std::span<const u8> in, u32 bpp, u32 w, u32 h, u32 d, u32 bh, u32 bd, u32 align) {
    {
        std::lock_guard lk(seen_mu);
        seen.insert(std::this_thread::get_id());
    }
    Tegra::Texture::UnswizzleTexture(out, in, bpp, w, h, d, bh, bd, align);
}
const uint8_t* guest_bytes(uint64_t gpu, uint64_t n, std::vector<uint8_t>& scratch) {
    uint64_t avail = 0;
    const uint8_t* p = host->gpu_ptr(gpu, &avail);
    if (p && avail >= n) return p;
    scratch.resize(n);
    host->gpu_read(gpu, scratch.data(), n);
    return scratch.data();
}

void unswizzle_rows(Texture& tex, uint64_t total, const LevelGeo& g, uint32_t level, uint64_t src_off, uint64_t span,
                    const std::vector<std::pair<uint32_t, uint32_t>>& runs, uint32_t row0, uint32_t nrow,
                    uint32_t nrows, uint32_t rows_per, uint64_t row_bytes, uint32_t th, int src_bpb,
                    uint64_t block_bytes, uint8_t* blocks, std::vector<uint8_t>& scratch) {
    (void)tex, (void)total, (void)g, (void)level, (void)src_off, (void)span, (void)runs, (void)row0, (void)nrow;
    (void)nrows, (void)rows_per, (void)row_bytes, (void)th, (void)src_bpb, (void)block_bytes, (void)blocks, (void)scratch;
/* ACTUAL ROWS */
}

// ---- the choice's cases: a 16 MB RGBA8 level
constexpr uint64_t kTotal = 16u << 20;
constexpr uint64_t kLow = 0x180000000ull;           // (a GPU address below 1 TB: the guest's own)
constexpr uint64_t kVirt = (1ull << 40) + 0x40000000ull;   // (a virtual pool's, above 1 TB)
constexpr uint64_t kVirtGuest = 0x2c0000000ull;     // (where that one's guest memory is)

bool run_choice(const std::string& name) {
    Texture tex;
    imported.clear();
    model = Model{};
    bool want_gpu = false;
    if (name == "contained") {   // one imported pool holds it: the GPU unswizzle, from that pool
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        imported[kLow - 0x100000] = {kLow - 0x100000, kLow + kTotal + 0x100000};
        want_gpu = true;
    } else if (name == "exact") {   // a pool exactly the texture's range
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        imported[kLow] = {kLow, kLow + kTotal};
        want_gpu = true;
    } else if (name == "missing") {   // no pool: the CPU path, nothing imported for it
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        imported[kLow + kTotal] = {kLow + kTotal, kLow + kTotal + (64u << 20)};   // (one after it, not under it)
    } else if (name == "partial") {   // a pool holds its first half
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        imported[kLow - 0x100000] = {kLow - 0x100000, kLow + kTotal / 2};
    } else if (name == "split") {   // two pools hold it between them, no one pool all of it
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        imported[kLow - 0x100000] = {kLow - 0x100000, kLow + kTotal / 2};
        imported[kLow + kTotal / 2] = {kLow + kTotal / 2, kLow + kTotal + 0x100000};
    } else if (name == "virtual") {   // above 1 TB: the pool looked up at its guest address
        tex.gpu = kVirt, model.lo = kVirt, model.hi = kVirt + kTotal, model.virt_guest = kVirtGuest;
        imported[kVirtGuest] = {kVirtGuest, kVirtGuest + kTotal};
        want_gpu = true;
    } else if (name == "virtual-missing") {   // above 1 TB, its guest memory in no pool
        tex.gpu = kVirt, model.lo = kVirt, model.hi = kVirt + kTotal, model.virt_guest = kVirtGuest;
        imported[kVirtGuest + kTotal] = {kVirtGuest + kTotal, kVirtGuest + 2 * kTotal};
    } else if (name == "noncontiguous") {   // its virtual mapping breaks halfway: a pool under the start is no source
        tex.gpu = kVirt, model.lo = kVirt, model.hi = kVirt + kTotal, model.virt_guest = kVirtGuest;
        model.contiguous_to = kVirt + kTotal / 2;
        imported[kVirtGuest] = {kVirtGuest, kVirtGuest + kTotal};
    } else if (name == "unmapped") {   // gpu_ptr sees none of it
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal, model.direct = false;
    } else if (name == "override") {   // RX_VK_UNSWIZZLE_IMPORT=1 (set by the test): an import, as before
        tex.gpu = kLow, model.lo = kLow, model.hi = kLow + kTotal;
        want_gpu = true;
    } else {
        std::printf("unknown case %s\n", name.c_str());
        return false;
    }
    lookups = imports = 0;
    const bool gpu = choose(tex, kTotal);
    CHECK(gpu == want_gpu);
    if (name == "override") {
        CHECK(lookups == 1 && imports == 1);
    } else if (want_gpu) {
        CHECK(lookups == 1 && imports == 0);
    } else {
        CHECK(lookups == 0);   // (main reaches for a pool here, and imports one: the 22-25 ms stall)
        CHECK(imports == 0);
    }
    std::printf("%s: %s, %d lookups, %d imports\n", name.c_str(), gpu ? "GPU" : "CPU", lookups, imports);
    return true;
}

// ---- the rows' cases
struct RowsCase {
    const char* name;
    uint32_t width, height;   // texels (= blocks: no compressed formats here)
    int bpb;
    unsigned tile_h;
    uint32_t row0, nrow;      // the GOB-block rows uploaded (nrow 0: all of them)
    bool direct;              // false: sparse storage, gathered by gpu_read
    uint64_t short_by;        // the storage ends this many bytes before the level's swizzled span
    unsigned cpus;
    int want_threads;         // 1: one thread; 2: more than one
};

bool run_rows(const RowsCase& c) {
    LevelGeo g;
    g.tw = c.width, g.tile_h = c.tile_h;
    const uint32_t rows_per = 8u << g.tile_h;
    const uint32_t nrows = (c.height + rows_per - 1) / rows_per;
    const uint64_t gobs_x = ((uint64_t)g.tw * c.bpb + 63) / 64;
    const uint64_t row_bytes = gobs_x * (512ull << (g.tile_h + g.tile_d));
    const uint64_t span = row_bytes * nrows;
    const uint64_t total = span - c.short_by;
    std::mt19937_64 rng(c.width * 131 + c.height);
    model = Model{};
    model.lo = kLow, model.hi = kLow + total, model.direct = c.direct;
    model.bytes.resize(total);
    for (auto& b : model.bytes) b = (uint8_t)rng();
    // what one call over the whole level gives, from the span with zeros past the storage
    std::vector<uint8_t> whole(span, 0), want((uint64_t)g.tw * c.height * c.bpb);
    std::memcpy(whole.data(), model.bytes.data(), total);
    Tegra::Texture::UnswizzleTexture(want, whole, (u32)c.bpb, g.tw, c.height, 1, g.tile_h, 0, 1);

    const uint32_t row0 = c.row0, nrow = c.nrow ? c.nrow : nrows - c.row0;
    std::vector<std::pair<uint32_t, uint32_t>> runs{{row0, nrow}};
    if (c.nrow) runs.push_back({nrows, 0});   // (a partial upload: dirty pages picked these rows, not the whole level)
    const uint32_t y0 = row0 * rows_per;
    const uint32_t th = std::min(c.height - y0, nrow * rows_per);
    const uint64_t block_bytes = (uint64_t)g.tw * th * c.bpb;
    std::vector<uint8_t> blocks(block_bytes, 0xCD), scratch;
    Texture tex;
    tex.gpu = kLow;
    cpus = c.cpus;
    seen.clear();
    st_unswizzle_bytes = st_unswizzle_ns = 0;
    unswizzle_rows(tex, total, g, 0, 0, span, runs, row0, nrow, nrows, rows_per, row_bytes, th, c.bpb, block_bytes,
                   blocks.data(), scratch);
    const bool same = !std::memcmp(blocks.data(), want.data() + (uint64_t)y0 * g.tw * c.bpb, block_bytes);
    CHECK(same);
    CHECK(st_unswizzle_bytes == (int64_t)block_bytes);
    const int threads = (int)seen.size();
    if (c.want_threads == 1)
        CHECK(threads == 1);
    else
        CHECK(threads > 1);
    std::printf("%s: %ux%u x%d, rows %u+%u of %u (%.3f MB), %s%s: %d threads, %.1f ms, %s\n", c.name, c.width, c.height,
                c.bpb, row0, nrow, nrows, block_bytes / 1048576.0, c.direct ? "contiguous" : "sparse",
                c.short_by ? ", storage ends early" : "", threads, st_unswizzle_ns / 1e6,
                same ? "same as one call" : "DIFFERENT");
    return true;
}

const RowsCase kRows[] = {
    // around the threshold: 1024 x 1023 RGBA8 is 4 KB short of 4 MB, 1024 x 1024 is 4 MB
    {"below-4mb", 1024, 1023, 4, 4, 0, 0, true, 0, 16, 1},
    {"at-4mb", 1024, 1024, 4, 4, 0, 0, true, 0, 16, 2},
    {"at-4mb-sparse", 1024, 1024, 4, 4, 0, 0, false, 0, 16, 2},
    // the Deku Tree's scene-size target: a width no GOB multiple, a partial last GOB-block row (1318 = 10 x 128 + 38)
    {"scene-target", 2779, 1318, 4, 4, 0, 0, true, 0, 16, 2},
    {"scene-target-sparse", 2779, 1318, 4, 4, 0, 0, false, 0, 16, 2},
    {"scene-target-3-threads", 2779, 1318, 4, 4, 0, 0, true, 0, 6, 2},
    {"scene-target-chunks", 2779, 1318, 4, 4, 0, 0, false, 0, 4, 2},   // (2 threads: 6 rows and 5, gathered 5 at a time)
    // partial uploads: some GOB-block rows, from the middle, and to the end with its partial last row
    {"partial-middle", 2779, 1318, 4, 4, 3, 5, true, 0, 16, 2},
    {"partial-middle-sparse", 2779, 1318, 4, 4, 3, 5, false, 0, 16, 2},
    {"partial-last", 4000, 1318, 4, 4, 8, 3, true, 0, 16, 2},
    {"partial-last-sparse", 4000, 1318, 4, 4, 8, 3, false, 0, 16, 2},
    {"partial-small", 2779, 1318, 4, 4, 8, 3, true, 0, 16, 1},   // (2779 x 294 x 4 = 3.1 MB: one thread)
    // the storage ending inside the level's span: zeros past it
    {"short-storage", 2779, 1318, 4, 4, 0, 0, true, 300000, 16, 2},
    {"short-storage-sparse", 2779, 1318, 4, 4, 0, 0, false, 300000, 16, 2},
    {"short-storage-partial", 4000, 1318, 4, 4, 8, 3, false, 300000, 16, 2},
    {"short-storage-one-thread", 1024, 1023, 4, 4, 0, 0, true, 300000, 16, 1},
    // other texel sizes and block heights
    {"rgba16f", 1500, 900, 8, 3, 0, 0, true, 0, 16, 2},
    {"rgba32f-sparse", 700, 600, 16, 2, 0, 0, false, 0, 16, 2},
    {"r8-below", 2048, 2047, 1, 4, 0, 0, true, 0, 16, 1},
};

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    const std::string what = argv[1];
    if (what == "rows") {
        for (const RowsCase& c : kRows) run_rows(c);
    } else if (!run_choice(what)) {
        return 2;
    }
    if (failures) std::printf("failures=%d\n", failures);
    return failures ? 1 : 0;
}
