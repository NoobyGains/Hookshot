// keep_resampled (gpu/vk/keep_resampled.h): the textures the GPU drew that the game samples again after finalizing them, used
// recently, stay through an eviction pass over the budget, up to a cap spent on the most recently used. tests/test_keep_resampled.py
#include "../gpu/vk/keep_resampled.h"
#include "../gpu/vk/keep_rendered.h"

#include <cstdio>
#include <cstdlib>

static int failures = 0;
static void expect(bool ok, const char* what) {
    if (!ok) {
        std::printf("FAIL: %s\n", what);
        failures++;
    }
}

int main() {
    const uint64_t MB = 1ull << 20, max = 512 * MB;
    using keep_resampled::cap;
    using keep_resampled::candidate;
    using keep_resampled::finalized_room;
    using keep_resampled::keep;
    using keep_resampled::kMaxUnused;

    // candidate(overwritten, gpu_owned, gpu_written, resampled, unused)
    expect(candidate(false, true, true, true, 400), "the 12288 x 12288 shadow map, sampled again, unused 400 presents: a candidate");
    expect(!candidate(true, true, true, true, 0), "drawn over since: nothing left to keep");
    expect(!candidate(false, false, true, true, 0),
           "its storage no longer the GPU's (another render target took the range, an area change): the pin goes at once");
    expect(!candidate(false, true, false, true, 0), "uploaded from the game's memory: made again from there");
    expect(!candidate(false, true, true, false, 0), "never sampled again after finalizing: goes as before");
    expect(kMaxUnused == vram_compact::kReserveUnused, "the age limit is the compaction reserve's line");
    expect(candidate(false, true, true, true, kMaxUnused - 1), "unused one present short of 1,800: still one");
    expect(!candidate(false, true, true, true, kMaxUnused), "unused 1,800 presents: the reserve's, not kept here");
    expect(!candidate(false, true, true, true, kMaxUnused + 1),
           "unused longer (an area left behind): goes, as Hookshot pull 2198's reserve lets it");

    // the cap: an eighth of the budget, at most RX_VK_KEEP_RESAMPLED_MB and the cap shared with keep_finalized
    const uint64_t allowed = 8192 * MB, calm = 4096 * MB;
    expect(cap(max, max, 1024 * MB, true, calm, allowed) == 128 * MB, "a 1 GB budget (an iGPU): 128 MB, an eighth");
    expect(cap(max, max, 1600 * MB, true, calm, allowed) == 200 * MB, "a 1.6 GB budget (a 4 GB card): 200 MB");
    expect(cap(max, max, 2560 * MB, true, calm, allowed) == 320 * MB, "2.5 GB: 320 MB, both of Dodongo's Cavern's shadow maps");
    expect(cap(max, max, 6144 * MB, true, calm, allowed) == max, "a 6 GB budget: RX_VK_KEEP_RESAMPLED_MB's 512 MB");
    expect(cap(64 * MB, max, 6144 * MB, true, calm, allowed) == 64 * MB, "RX_VK_KEEP_RESAMPLED_MB=64: 64");
    expect(cap(0, max, 6144 * MB, true, calm, allowed) == 0, "RX_VK_KEEP_RESAMPLED_MB=0: off");
    expect(cap(2048 * MB, max, 16384 * MB, true, calm, allowed) == max, "never past the cap it shares with keep_finalized");
    expect(cap(max, 0, 6144 * MB, true, calm, allowed) == 0, "RX_VK_KEEP_FINALIZED_MB=0: the shared cap is 0, nothing kept");
    expect(cap(max, max, 6144 * MB, false, 0, 0) == max, "the driver's use unknown: the budget's eighth alone");

    // nothing near what the driver allows: 97% of it, keep_rendered's own line
    expect(cap(max, max, 4096 * MB, true, allowed / 100 * 97, allowed) == 0, "at 97% of what the driver allows: nothing kept");
    expect(cap(max, max, 4096 * MB, true, allowed, allowed) == 0, "at the driver's limit (an 8 GB RX 6600, Longshot issue 130): none");
    expect(cap(max, max, 4096 * MB, true, allowed / 100 * 97 - 1, allowed) == max, "just under 97%: kept");
    for (uint64_t used = allowed / 100 * 90; used <= allowed + 64 * MB; used += 16 * MB)
        expect((cap(max, max, 4096 * MB, true, used, allowed) == 0) == (keep_rendered::presents(true, used, allowed, false) == 600),
               "the line is keep_rendered's: at it, both step");
    uint64_t at_limit = 320 * MB;
    expect(!keep(288 * MB, at_limit, cap(max, max, 4096 * MB, true, allowed, allowed)), "at the limit the shadow map goes, as before");

    // one cap for both rules: what keep_resampled may hold comes off keep_finalized's room, so together no more than it held alone
    expect(finalized_room(max, 320 * MB, 512 * MB) == 192 * MB, "320 MB of shadow maps: 192 MB left for keep_finalized");
    expect(finalized_room(max, 320 * MB, 128 * MB) == 384 * MB, "at most its cap off the room: 128 MB on a 1 GB budget");
    expect(finalized_room(max, 0, 512 * MB) == max, "no resampled textures: keep_finalized's 512 MB as before");
    expect(finalized_room(max, 320 * MB, 0) == max, "near the limit (cap 0): keep_finalized's as before, the small ones its own");
    expect(finalized_room(max, 2048 * MB, 2048 * MB) == 0, "never below 0");
    for (uint64_t budget = 512 * MB; budget <= 16384 * MB; budget += 512 * MB)
        for (uint64_t total = 0; total <= 1024 * MB; total += 32 * MB) {
            const uint64_t c = cap(max, max, budget, true, calm, allowed);
            expect(std::min(total, c) + finalized_room(max, total, c) <= max, "the two together: at most the shared cap");
        }

    // within the cap: every candidate kept, the total unchanged
    uint64_t total = 288 * MB + 32 * MB;
    expect(keep(288 * MB, total, max) && keep(32 * MB, total, max) && total == 320 * MB, "both shadow maps fit: kept");
    total = max;
    expect(keep(1, total, max), "exactly the cap: kept");

    // over the cap, oldest first: the oldest go until the rest fit, then the most recently used are kept
    total = 288 * MB + 288 * MB + 32 * MB;   // (608 MB: oldest 288, then 288, then the newest 32)
    expect(!keep(288 * MB, total, max) && total == 320 * MB, "the oldest 288 MB one goes, leaving 320 MB");
    expect(keep(288 * MB, total, max), "the next fits now: kept");
    expect(keep(32 * MB, total, max), "the newest: kept");
    expect(total == 320 * MB, "kept ones leave the total");

    // a 1 GB budget's 128 MB: the 288 MB map goes, the 32 MB one stays
    total = 288 * MB + 32 * MB;
    const uint64_t small = cap(max, max, 1024 * MB, true, calm, allowed);
    expect(!keep(288 * MB, total, small) && keep(32 * MB, total, small), "a 1 GB budget: only what fits in an eighth of it");

    uint64_t drift = 2;
    expect(!keep(8, drift, 1) && drift == 0, "a total below a texture's bytes clamps at 0, not wraps");

    uint64_t none = 64 * MB;
    expect(!keep(1, none, 0), "RX_VK_KEEP_RESAMPLED_MB=0: evicted as before");
    if (failures) return EXIT_FAILURE;
    std::printf("keep resampled: all checks passed\n");
    return EXIT_SUCCESS;
}
