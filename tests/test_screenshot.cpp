// tests/test_screenshot.py: gpu/vk/screenshot.h, the Screenshot key's file name and its free name in the screenshots folder, and
// Native HDR's picture (PQ codes, Rec. 2020) made into the SDR one a PNG holds
#include "screenshot.h"   // (gpu/vk, on the include path: tests/test_screenshot.py)

#include <cmath>
#include <cstdio>
#include <cstring>
#include <set>
#include <string>

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

namespace ss = mkwvk::screenshot;

// (ST 2084's inverse, written here apart from the header's EOTF: light to a 10-bit code)
static unsigned pq_code(double nits) {
    const double m1 = 2610.0 / 16384, m2 = 2523.0 / 4096 * 128, c1 = 3424.0 / 4096, c2 = 2413.0 / 4096 * 32, c3 = 2392.0 / 4096 * 32;
    const double y = std::pow(nits / 10000.0, m1);
    return (unsigned)std::lround(1023.0 * std::pow((c1 + c2 * y) / (1 + c3 * y), m2));
}
static uint32_t pack(unsigned r, unsigned g, unsigned b, unsigned a = 3) { return r | g << 10 | b << 20 | a << 30; }
static bool near(double a, double b, double tolerance) { return std::fabs(a - b) <= tolerance; }

int main() {
    // ---- the name: the local time, no colon (Windows takes none), the n-th in one second
    std::tm t{};
    t.tm_year = 2026 - 1900, t.tm_mon = 10, t.tm_mday = 14, t.tm_hour = 21, t.tm_min = 5, t.tm_sec = 3;
    CHECK("name", ss::file_name(t) == "Hookshot 2026-11-14 21-05-03.png");
    CHECK("the first is plain", ss::file_name(t, 1) == ss::file_name(t));
    CHECK("the second in a second", ss::file_name(t, 2) == "Hookshot 2026-11-14 21-05-03 (2).png");
    std::tm early{};
    early.tm_year = 2027 - 1900, early.tm_mon = 0, early.tm_mday = 2, early.tm_hour = 0, early.tm_min = 0, early.tm_sec = 9;
    CHECK("zero padded", ss::file_name(early) == "Hookshot 2027-01-02 00-00-09.png");
    CHECK("sorted by name in the order taken", ss::file_name(t) < ss::file_name(early));
    for (const std::string& name : {ss::file_name(t), ss::file_name(t, 2), ss::file_name(early, ss::kMaxSameSecond)})
        for (char c : name) CHECK("a name Windows and Linux both take", !std::strchr("<>:\"/\\|?*", c) && (unsigned char)c >= 32);

    // ---- the free name: the first not taken, in the folder given; none once kMaxSameSecond are taken
    std::set<std::string> taken;
    auto is_taken = [&](const std::string& path) { return taken.count(path) != 0; };
    CHECK("free: the plain name", ss::free_path("shots/", t, is_taken) == "shots/" + ss::file_name(t));
    taken.insert("shots/" + ss::file_name(t));
    taken.insert("shots/" + ss::file_name(t, 2));
    CHECK("free: the third", ss::free_path("shots/", t, is_taken) == "shots/" + ss::file_name(t, 3));
    for (int n = 3; n <= ss::kMaxSameSecond; n++) taken.insert("shots/" + ss::file_name(t, n));
    CHECK("none free", ss::free_path("shots/", t, is_taken).empty());
    CHECK("another second is free", ss::free_path("shots/", early, is_taken) == "shots/" + ss::file_name(early));

    // ---- PQ's light: the ends, monotonic, and a round trip through the inverse within its code's step
    CHECK("PQ 0", ss::pq_nits(0) == 0.0);
    CHECK("PQ top", near(ss::pq_nits(1023), 10000.0, 1e-6));
    CHECK("PQ past 10 bits is the top", ss::pq_nits(5000) == ss::pq_nits(1023));
    for (unsigned c = 1; c < 1024; c++) CHECK("PQ rises", ss::pq_nits(c) > ss::pq_nits(c - 1));
    for (double nits : {1.0, 10.0, 80.0, 100.0, 200.0, 203.0, 500.0, 1000.0, 4000.0}) {
        const unsigned c = pq_code(nits);
        CHECK("PQ round trip", ss::pq_nits(c) <= nits * 1.02 && ss::pq_nits(c) >= nits * 0.98);
    }
    CHECK("100 nits", pq_code(100) == 520);

    // ---- the tone curve: unchanged under the knee, the slope kept at it, 1 at the peak and above, never past 1
    CHECK("dark kept", ss::tone(0.25, 5) == 0.25);
    CHECK("knee kept", ss::tone(ss::kKnee, 5) == ss::kKnee);
    CHECK("slope at the knee", near((ss::tone(ss::kKnee + 1e-7, 5) - ss::kKnee) / 1e-7, 1.0, 1e-4));
    CHECK("the paper white", near(ss::tone(1.0, 5), 0.9 + 0.1 / (1 + 0.1 * (10 - 1 / 4.1)), 1e-12));
    CHECK("the peak is white", near(ss::tone(5, 5), 1.0, 1e-12));
    CHECK("past the peak", ss::tone(50, 5) == ss::tone(5, 5));
    double last = 0;
    for (double x = 0; x <= 8; x += 0.01) {
        const double y = ss::tone(x, 5);
        CHECK("rises", y >= last && y <= 1.0);
        last = y;
    }
    CHECK("a peak at the paper white: cut", ss::tone(0.95, 1.0) == 0.95 && ss::tone(3, 1.0) == 1.0);
    CHECK("a peak under it: cut", ss::tone(1.5, 0.8) == 1.0);
    CHECK("negative", ss::tone(-0.5, 5) == 0);
    CHECK("NaN", ss::tone(std::nan(""), 5) == 0);

    // ---- sRGB codes
    CHECK("sRGB ends", ss::srgb8(0) == 0 && ss::srgb8(1) == 255 && ss::srgb8(-1) == 0 && ss::srgb8(7) == 255);
    CHECK("sRGB middle grey", ss::srgb8(0.5) == 188);
    CHECK("sRGB linear part", ss::srgb8(0.002) == 7);   // (12.92 * 0.002 * 255 = 6.6)
    CHECK("sRGB NaN", ss::srgb8(std::nan("")) == 0);

    // ---- the picture: which bits are which channel, grey stays grey, Rec. 2020's red cut to Rec. 709's, the alpha bits left out
    const unsigned white_code = pq_code(200), red_code = pq_code(100), peak_code = 1023;
    const uint32_t in[] = {pack(0, 0, 0), pack(white_code, white_code, white_code), pack(peak_code, peak_code, peak_code),
                           pack(red_code, 0, 0), pack(0, 0, red_code, 0), pack(0, red_code, 0, 1)};
    constexpr size_t n = sizeof in / sizeof in[0];
    uint8_t out[n * 4];
    std::memset(out, 7, sizeof out);
    ss::hdr10_to_rgba8(in, n, out, 200, 1000);
    for (size_t i = 0; i < n; i++) CHECK("opaque", out[i * 4 + 3] == 255);
    CHECK("black", out[0] == 0 && out[1] == 0 && out[2] == 0);
    const int grey = ss::srgb8(ss::tone(ss::pq_nits(white_code) / 200, 5));
    CHECK("the paper white is a grey just under white", std::abs(out[4] - out[5]) <= 1 && std::abs(out[5] - out[6]) <= 1 &&
                                                            std::abs(out[4] - grey) <= 1 && out[4] >= 245 && out[4] < 255);
    CHECK("10000 nits is white", out[8] == 255 && out[9] == 255 && out[10] == 255);
    const int red = ss::srgb8(1.660491 * ss::pq_nits(red_code) / 200);   // (under the knee: kept as it is)
    CHECK("Rec. 2020 red: red alone", std::abs(out[12] - red) <= 1 && out[13] == 0 && out[14] == 0);
    CHECK("bits 20-29 are blue", out[16] == 0 && out[17] == 0 && out[18] > 150);
    CHECK("bits 10-19 are green", out[20] == 0 && out[21] > 150 && out[22] == 0);
    // (grey rises with its code, and the paper white told moves the picture: a brighter one is a darker PNG)
    int prev = -1;
    for (unsigned c = 0; c < 1024; c += 3) {
        const uint32_t p = pack(c, c, c);
        uint8_t px[4];
        ss::hdr10_to_rgba8(&p, 1, px, 200, 1000);
        CHECK("grey rises, and stays grey", px[0] >= prev && std::abs(px[0] - px[1]) <= 1 && std::abs(px[1] - px[2]) <= 1);
        prev = px[0];
    }
    uint8_t brighter[4], dimmer[4];
    ss::hdr10_to_rgba8(&in[3], 1, brighter, 100, 1000);
    ss::hdr10_to_rgba8(&in[3], 1, dimmer, 400, 1000);
    CHECK("the paper white moves it", brighter[0] > out[12] && dimmer[0] < out[12]);
    uint8_t odd[4];
    ss::hdr10_to_rgba8(&in[1], 1, odd, 0, 0);   // (nothing told: no division by zero, a picture all the same)
    CHECK("no paper white told", odd[0] == 255 && odd[3] == 255);
    std::puts("screenshot: all checks passed");
    return 0;
}
