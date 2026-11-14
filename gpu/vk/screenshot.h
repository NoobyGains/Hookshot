/* (hookshot) The Screenshot key's plain parts (vk_screenshot.cpp has the renderer's): the file's name, the free name in the
   screenshots folder, and the game's own HDR10 picture (Native HDR) made into an SDR one. No Vulkan and no file system here:
   tests/test_screenshot.cpp checks them, tests/test_screenshot.py writes PNGs through them. */
#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <string>

namespace mkwvk::screenshot {

constexpr const char* kFolder = "screenshots";   // (in the game folder, beside hookshot_options.ini and bug-reports)
constexpr int kNoteMs = 2000;                    // (how long "Screenshot saved" shows)
constexpr int kMaxSameSecond = 99;               // (pictures in one second: "(2)" up to this, then none)

/// "Hookshot 2026-11-14 21-05-33.png", the local time it was taken; the n-th in that second (n >= 2) "Hookshot 2026-11-14
/// 21-05-33 (2).png". No colon: Windows takes none in a name. Sorted by name, they are in the order they were taken
inline std::string file_name(const std::tm& t, int n = 1) {
    char b[64];
    std::snprintf(b, sizeof b, "Hookshot %04d-%02d-%02d %02d-%02d-%02d", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour,
                  t.tm_min, t.tm_sec);
    std::string name = b;
    if (n >= 2) name += " (" + std::to_string(n) + ")";
    return name + ".png";
}

/// The first name of file_name(t, 1), (2), ... that taken(path) says is free, as folder + name (folder ends with its
/// separator); "" when kMaxSameSecond are taken
template <class Taken>
std::string free_path(const std::string& folder, const std::tm& t, Taken taken) {
    for (int n = 1; n <= kMaxSameSecond; n++) {
        std::string path = folder + file_name(t, n);
        if (!taken(path)) return path;
    }
    return std::string();
}

// ---- Native HDR's picture: the game's own HDR10 (PQ codes, Rec. 2020 primaries, A2B10G10R10: red in bits 0-9) made into the
// SDR picture a PNG is looked at as (sRGB). This is the HDR10 picture tone mapped simply, not the game's own SDR picture: while
// Native HDR is on the game draws no SDR one to take. The codes to light (SMPTE ST 2084), Rec. 2020 to Rec. 709, the paper
// white the game was told (the HDR paper white row) as SDR's white, the highlights above it eased into white up to the peak
// brightness it was told, then sRGB's curve. Never the PQ codes written as they are: that picture looks grey and washed out.

/// Nits of a 10-bit PQ code (SMPTE ST 2084's EOTF)
inline double pq_nits(unsigned code) {
    constexpr double m1 = 2610.0 / 16384, m2 = 2523.0 / 4096 * 128, c1 = 3424.0 / 4096, c2 = 2413.0 / 4096 * 32,
                     c3 = 2392.0 / 4096 * 32;
    const double e = std::pow(std::min(code, 1023u) / 1023.0, 1.0 / m2);
    return 10000.0 * std::pow(std::max(e - c1, 0.0) / (c2 - c3 * e), 1.0 / m1);
}

constexpr double kKnee = 0.9;   // (light below this share of the paper white is kept as it is; above, the shoulder)

/// SDR light (1 the paper white) of x, light in paper whites: x itself up to kKnee, then a shoulder that keeps the slope at the
/// knee and reaches 1 at top (the peak brightness in paper whites) and stays there. A peak at or under the paper white: cut at 1
inline double tone(double x, double top) {
    if (!(x > 0)) return 0;   // (and NaN)
    if (x <= kKnee) return x;
    if (top <= 1.0) return std::min(x, 1.0);
    const double t = std::min(x, top) - kKnee, room = 1.0 - kKnee;
    return kKnee + t / (1.0 + t * (1.0 / room - 1.0 / (top - kKnee)));
}

/// An 8-bit sRGB code of linear light (0 to 1, cut at both ends)
inline uint8_t srgb8(double v) {
    if (!(v > 0)) return 0;
    if (v >= 1) return 255;
    const double e = v <= 0.0031308 ? 12.92 * v : 1.055 * std::pow(v, 1 / 2.4) - 0.055;
    return (uint8_t)std::lround(e * 255);
}

/// The SDR picture of n packed A2B10G10R10 pixels into rgba (4 bytes each, alpha 255). white and peak: the paper white and the
/// peak brightness the game was told, nits
inline void hdr10_to_rgba8(const uint32_t* packed, size_t n, uint8_t* rgba, double white, double peak) {
    white = std::max(white, 1.0);
    const double top = std::max(peak, 1.0) / white;
    static const auto nits = [] {   // (the 1024 codes' light, once)
        struct Table { double v[1024]; } t{};
        for (unsigned i = 0; i < 1024; i++) t.v[i] = pq_nits(i);
        return t;
    }();
    // (sRGB codes of light 0 to 1 in 4096 steps: the steps are under one code apart, an exp and a pow a pixel saved)
    static const auto codes = [] {
        struct Table { uint8_t v[4097]; } t{};
        for (unsigned i = 0; i <= 4096; i++) t.v[i] = srgb8(i / 4096.0);
        return t;
    }();
    for (size_t i = 0; i < n; i++) {
        const uint32_t p = packed[i];
        const double r = nits.v[p & 1023] / white, g = nits.v[p >> 10 & 1023] / white, b = nits.v[p >> 20 & 1023] / white;
        // (Rec. 2020 to Rec. 709, ITU-R BT.2087; a colour outside Rec. 709 cut at its edge)
        const double rgb[3] = {1.66049100 * r - 0.58764114 * g - 0.07284986 * b, -0.12455047 * r + 1.13289990 * g - 0.00834942 * b,
                               -0.01815076 * r - 0.10057890 * g + 1.11872966 * b};
        for (int c = 0; c < 3; c++) rgba[i * 4 + c] = codes.v[(int)std::lround(tone(rgb[c], top) * 4096)];
        rgba[i * 4 + 3] = 255;
    }
}

}  // namespace mkwvk::screenshot
