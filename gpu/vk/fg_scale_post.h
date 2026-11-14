// The window pass's FXAA, Bloom, Colour grade and Retro look (shaders/fg_scale.comp; vk_framegen.cpp framegen_scale, vk_menu.cpp's
// rows): the pass's push constants and the rows' tables. FXAA, Bloom and the Colour grade from Ocarina Reborn
#pragma once

namespace mkwvk {

// (fg_scale.comp's push constants, as its P block has them: tests/test_fg_scale_post.py)
struct ScalePush {
    int mode; float sharp; float x0, x1; int side; float cover;
    float sat, contrast, warm, vignette; int look; float bloom; int fxaa;   // (the Colour grade, Bloom and FXAA rows)
    int retro;   // (the Retro look row: 0 Off, 1 N64, 2 N64 + CRT)
    // (N64 + CRT's rows: the scanlines' hardness, 0 none (kCrtScan), the mask (0 none, 1 aperture grille, 2 slot, 3 shadow)
    // and its strength 0..1, the glow, the curvature and its corners (kCrtCurve). No semicolons in these comments: the check
    // that matches the fields to the shader's splits on them)
    float scan; int mask; float mask_str; float glow; float warp_x, warp_y; float corner;
    float gamma;   // (the Brightness row: the picture's code to this power, 1 none. SDR only)
    int cvd;       // (the Colour vision row: 0 Off, 1 protanopia, 2 deuteranopia, 3 tritanopia, daltonized)
};
inline constexpr int kGrades = 6, kBloomSteps = 4;   // (the Colour grade's looks and the Bloom's steps: Options grade, bloom)
// (the Colour grade's looks: saturation, contrast, warmth, vignette. Off, Rich, Vivid, Warm, Cool, Cinematic)
inline constexpr float kGradeLooks[kGrades][4] = {{1.0f, 1.0f, 0.0f, 0.0f},   {1.12f, 1.06f, 0.03f, 0.18f}, {1.25f, 1.10f, 0.0f, 0.0f},
                                                  {1.05f, 1.03f, 0.07f, 0.12f}, {1.05f, 1.04f, -0.05f, 0.10f}, {0.92f, 1.12f, 0.02f, 0.30f}};
inline constexpr float kBloomLevels[kBloomSteps] = {0.0f, 0.25f, 0.5f, 0.85f};   // (the Bloom: Off, Low, Medium, High)
// (the Retro look's values, Options retro: Off, N64, N64 + CRT. Its picture is kRetroLines tall, the Nintendo 64's 320 x 240 as
// tall, and as wide as the window's picture is at that height: 427 for 16:9)
inline constexpr int kCvds = 4;   // (the Colour vision row's values, Options colour_vision: Off and the three daltonized)
inline constexpr int kRetroLooks = 3;
inline constexpr unsigned kRetroLines = 240;
// (N64 + CRT, after Timothy Lottes' public-domain CRT shader (libretro glsl-shaders crt/shaders/crt-lottes.glsl), its rows'
// steps. Options crt_scanlines, crt_mask, crt_mask_strength (percent), crt_glow, crt_curvature)
inline constexpr int kCrtScans = 4, kCrtMasks = 4, kCrtGlows = 4, kCrtCurves = 3;
// (the scanlines: Off, Light, Medium, Strong. Lottes' hardScan, the beam a Gaussian exp2(scan * d * d) of the distance d from a
// line's middle in lines; his default -8 is Medium. 0: none, the lines run together)
inline constexpr float kCrtScan[kCrtScans] = {0.0f, -4.0f, -8.0f, -12.0f};
// (the glow: Off, Low, Medium, High. Lottes' bloomAmount, his default 0.15 Medium)
inline constexpr float kCrtGlow[kCrtGlows] = {0.0f, 0.08f, 0.15f, 0.30f};
// (the curvature: Off, Subtle, Strong. Lottes' warpX and warpY (his defaults 0.031 and 0.041 Strong), and how much darker the
// corners are)
inline constexpr float kCrtCurve[kCrtCurves][3] = {{0.0f, 0.0f, 0.0f}, {0.015f, 0.02f, 0.10f}, {0.031f, 0.041f, 0.20f}};

}  // namespace mkwvk
