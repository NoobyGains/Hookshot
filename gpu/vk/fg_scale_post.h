// The window pass's FXAA, Bloom and Colour grade (shaders/fg_scale.comp; vk_framegen.cpp framegen_scale, vk_menu.cpp's rows):
// the pass's push constants and the rows' tables. From Ocarina Reborn
#pragma once

namespace mkwvk {

// (fg_scale.comp's push constants, as its P block has them: tests/test_fg_scale_post.py)
struct ScalePush {
    int mode; float sharp; float x0, x1; int side; float cover;
    float sat, contrast, warm, vignette; int look; float bloom; int fxaa;   // (the Colour grade, Bloom and FXAA rows)
};
inline constexpr int kGrades = 6, kBloomSteps = 4;   // (the Colour grade's looks and the Bloom's steps: Options grade, bloom)
// (the Colour grade's looks: saturation, contrast, warmth, vignette. Off, Rich, Vivid, Warm, Cool, Cinematic)
inline constexpr float kGradeLooks[kGrades][4] = {{1.0f, 1.0f, 0.0f, 0.0f},   {1.12f, 1.06f, 0.03f, 0.18f}, {1.25f, 1.10f, 0.0f, 0.0f},
                                                  {1.05f, 1.03f, 0.07f, 0.12f}, {1.05f, 1.04f, -0.05f, 0.10f}, {0.92f, 1.12f, 0.02f, 0.30f}};
inline constexpr float kBloomLevels[kBloomSteps] = {0.0f, 0.25f, 0.5f, 0.85f};   // (the Bloom: Off, Low, Medium, High)

}  // namespace mkwvk
