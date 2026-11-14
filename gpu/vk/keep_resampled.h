// Which textures the GPU drew and the game samples again after finalizing them the eviction pass keeps (vk_texture.cpp).
// tests/test_keep_resampled.py
#pragma once
#include <algorithm>
#include <cstdint>

#include "vram_compact.h"

namespace keep_resampled {

// A texture the GPU drew, that the game finalized and then sampled again (Texture::resampled), with nothing drawn over its
// storage since and that storage still the GPU's (gpu_owned, as keep_finalized asks): a cache the game keeps, such as the
// 12288 x 12288 shadow map it draws once and samples for many frames. It is depth, so its texels cannot be written back into its
// memory; evicted over the budget, it was made again over storage the GPU rendered, not uploaded, and sampled EMPTY until the
// game drew it again some 40 frames later (Dodongo's Cavern at a 512 MB budget; the dark ground in Hyrule Field of
// https://github.com/NotRexed/Hookshot/issues/2209). Once another render target takes its storage's range (an area change, the
// game's heap given to something else) the pin goes, not only with age.
//
// Only while used in the last kMaxUnused presents (unused for fewer), the compaction reserve's own line
// (upstream #2198): one from an area left behind goes as before, and a texture this rule keeps is
// never one the reserve may take. The 12288 x 12288 map went unused 400 presents before the eviction took it.
constexpr uint64_t kMaxUnused = vram_compact::kReserveUnused;
inline bool recent(uint64_t unused) { return unused < kMaxUnused; }
inline bool candidate(bool overwritten, bool gpu_owned, bool gpu_written, bool resampled, uint64_t unused) {
    return !overwritten && gpu_owned && gpu_written && resampled && recent(unused);
}

// What it may hold in one pass. It shares keep_finalized's cap (shared, RX_VK_KEEP_FINALIZED_MB): what it may hold comes off
// that rule's room (finalized_room), so the two together hold no more than keep_finalized alone did. Within that, at most max
// (RX_VK_KEEP_RESAMPLED_MB) and an eighth of the textures' budget: on a 4 GB card or an iGPU (a budget of 1-1.6 GB) 128-200 MB, not
// a third of it. Nothing near what the driver allows (its 97%, keep_rendered's line): past it the driver pages VRAM to system
// memory or loses the device (an 8 GB RX 6600, https://git.magicbean.dev/MagicBeanDev/Longshot/issues/130), and the textures go
// as before this rule, the small ones keep_finalized's again
inline uint64_t cap(uint64_t max, uint64_t shared, uint64_t budget, bool known, uint64_t used, uint64_t allowed) {
    if (known && used >= allowed / 100 * 97) return 0;
    return std::min({max, shared, budget / 8});
}
// keep_finalized's room in the shared cap: less what this rule may hold this pass (its candidates' total, at most its cap)
inline uint64_t finalized_room(uint64_t shared, uint64_t total, uint64_t cap) {
    return shared - std::min({shared, total, cap});
}

// The candidates' bytes are summed before the pass (total); the pass walks the textures least recently used first, so a candidate
// is kept while the total left is within max, and beyond it this one, the oldest, goes and leaves the total: the cap is spent on
// the most recently used, as keep_finalized does. max 0: none kept
inline bool keep(uint64_t bytes, uint64_t& total, uint64_t max) {
    if (!max) return false;
    if (total <= max) return true;
    total -= std::min(total, bytes);
    return false;
}

} // namespace keep_resampled
