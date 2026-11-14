// The capture buffers' spares (vk_memory.cpp cap_buf_get, cap_prewarm_class): which classes are made ahead, how many bytes
// of spares this PC's RAM affords, whether a spare may serve a capture, and whether a spare may be made now. Pure: checked
// by tests/test_cap_spares.py. From Ocarina Reborn's capture pool (v1.0.7)
#pragma once
#include <cstdint>

namespace mkwvk::cap_spares {

// (the classes made ahead: cap_buf_size's above 16 MB)
inline constexpr uint64_t kClassMb[] = {32, 64, 128, 192, 256};
inline constexpr int kClasses = sizeof kClassMb / sizeof kClassMb[0];

/// The class a capture of `size` bytes is made in, or -1 past the largest
inline int class_index(uint64_t size) {
    for (int i = 0; i < kClasses; i++)
        if (size <= (kClassMb[i] << 20)) return i;
    return -1;
}

/// The most bytes of spares on a PC with `ram` bytes of RAM (0: not known), when the card does not set a smaller one: each
/// is host memory, resident. 64 MB up to 9 GB of RAM, 128 up to 17, 256 up to 33, else 512
inline uint64_t ram_cap(uint64_t ram) {
    const uint64_t mb = !ram || ram <= (9ull << 30) ? 64 : ram <= (17ull << 30) ? 128 : ram <= (33ull << 30) ? 256 : 512;
    return mb << 20;
}

/// Whether a spare of `size` bytes may serve a capture that needs `need` bytes and is made in a buffer of `target`: not
/// one of a larger class (a 2 MB capture took the 128 MB spare made for the next area's load)
inline bool serves(uint64_t size, uint64_t need, uint64_t target) { return size >= need && size <= target; }

/// Whether a spare of `bytes` may be made now: RAM and commit both keep `reserve` free past it (unknown: yes)
inline bool room(bool known, uint64_t avail_phys, uint64_t avail_commit, uint64_t bytes, uint64_t reserve) {
    return !known || (avail_phys > reserve + bytes && avail_commit > reserve + bytes);
}

}  // namespace mkwvk::cap_spares
