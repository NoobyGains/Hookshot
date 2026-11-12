// Authored API spies around functions inserted from vk_framegen.cpp by test_upscale_independent.py.
#ifdef _WIN32
#define _CRT_SECURE_NO_WARNINGS
#endif
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <mutex>
#include "fg_scale_post.h"   // (framegen_scale's push constants and the FXAA, Bloom, Colour grade and Retro look rows' tables)
using mkwvk::ScalePush, mkwvk::kGrades, mkwvk::kBloomSteps, mkwvk::kGradeLooks, mkwvk::kBloomLevels, mkwvk::kRetroLooks,
    mkwvk::kRetroLines, mkwvk::kCrtScans, mkwvk::kCrtMasks, mkwvk::kCrtGlows, mkwvk::kCrtCurves, mkwvk::kCrtScan, mkwvk::kCrtGlow,
    mkwvk::kCrtCurve, mkwvk::kCvds;
#include <utility>
#include "vk_present_rect.h"
using mkwvk::PresentSourceRect;
using mkwvk::present_source_rect;
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
using VkImage = uint64_t;
using VkImageView = uint64_t;
using VkSampler = uint64_t;
using VkCommandBuffer = int;
using VkDescriptorType = int;
using VkImageUsageFlags = int;
using VkFormat = int;
constexpr uint64_t VK_NULL_HANDLE = 0;
constexpr int VK_SUCCESS = 0, VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO = 1;
constexpr int VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER = 2, VK_DESCRIPTOR_TYPE_STORAGE_IMAGE = 3;
constexpr int VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE = 4, VK_FILTER_LINEAR = 5, VK_FILTER_NEAREST = 6;
constexpr int VK_FORMAT_R8G8B8A8_UNORM = 7, VK_IMAGE_LAYOUT_GENERAL = 8, VK_IMAGE_ASPECT_COLOR_BIT = 9;
constexpr int VK_FORMAT_A2B10G10R10_UNORM_PACK32 = 10;
constexpr int VK_IMAGE_USAGE_SAMPLED_BIT = 1, VK_IMAGE_USAGE_TRANSFER_DST_BIT = 2;
constexpr int VK_IMAGE_USAGE_STORAGE_BIT = 4, VK_IMAGE_USAGE_TRANSFER_SRC_BIT = 8;
const uint32_t FG_SCALE_COMP_SPV[] = {123}, FG_SCALE_PQ_COMP_SPV[] = {456};
// (gpu/vk/vk_builtin_spv.h's lookup as with RX_VK_SHADER_DIR unset: the compiled-in words themselves)
#define BUILTIN_SPV_ARGS(words) words, sizeof words
struct Img { VkImage image = 0; VkImageView view = 0; };
struct Pipe { uint64_t set = 0, layout = 0, pipe = 0; };
struct VkSamplerCreateInfo {
    int sType, addressModeU = 0, addressModeV = 0, addressModeW = 0;
    float maxLod = 0; int magFilter = 0, minFilter = 0;
};
struct Offset { int x = 0, y = 0, z = 0; };
struct Layers { int aspect = 0, level = 0, first = 0, count = 0; };
struct VkImageBlit { Layers srcSubresource, dstSubresource; Offset srcOffsets[2], dstOffsets[2]; };
struct Extent { uint32_t width = 0, height = 0, depth = 0; };
struct VkImageCopy { Layers srcSubresource; Offset srcOffset; Layers dstSubresource; Offset dstOffset; Extent extent; };
struct {
    int upscale = 0, sharpness = 0, framegen = 0, fxaa = 0, bloom = 0, grade = 0, retro = 0, brightness = 100, colour_vision = 0;
    int crt_scanlines = 2, crt_mask = 1, crt_mask_strength = 30, crt_glow = 2, crt_curvature = 1;   // (vk_menu.h's defaults)
} opts;
// (hookshot) The Upscaling row carries two things: 0-2 filter the finished picture and 3-4 name a
// scene upscaler. framegen_scale wants only the first half, exactly as the inline in vk_menu.h
// gives it, so the spy mirrors that rather than reading opts.upscale raw.
int window_filter() {
    return opts.upscale >= 0 && opts.upscale <= 2 ? opts.upscale : 0;
}
struct SpyMutex {
    bool held = false;
    void lock() { CHECK(!held); held = true; }
    void unlock() { CHECK(held); held = false; }
};
struct { bool push_descriptor = true, offscreen = false, hdr = false; int device = 1; SpyMutex present_mu; } dev;
// Only used by framegen_on and by the original scaler's negative control. No interpolation is initialized.
struct {
    bool init = false, failed = false, thread_started = false;
    Pipe scale; VkSampler linear = 0; Img cropped, scaled;
    uint32_t cropped_w = 0, cropped_h = 0, scaled_w = 0, scaled_h = 0;
} fg;
bool vkCmdPushDescriptorSetKHR = true;
int pipe_calls = 0, sampler_calls = 0, image_calls = 0, dispatches = 0, blits = 0, copies = 0, logs = 0;
int destroyed_pipes = 0, destroyed_layouts = 0, destroyed_sets = 0, waits = 0, flushes = 0;
bool pipe_fail = false, sampler_fail = false, image_fail = false, pq_pipe_fail = false;
uint64_t next_handle = 100;
uint32_t made_w = 0, made_h = 0, dispatched_w = 0, dispatched_h = 0;
int made_usage = 0, made_format = 0, dispatched_mode = -1;
uint64_t dispatched_pipe = 0;
float dispatched_sharp = -1, dispatched_x0 = -1, dispatched_x1 = -1;
int dispatched_side = -1;
float dispatched_cover = -1.0f;
int dispatched_look = -1, dispatched_fxaa = -1;   // (the Colour grade, Bloom and FXAA rows)
float dispatched_bloom = -1.0f, dispatched_sat = -1.0f;
int dispatched_retro = -1;   // (the Retro look row)
ScalePush dispatched_pc{};   // (the last dispatch's push constants whole: N64 + CRT's rows)
VkImageView small_bound = 0;   // (binding 2 of the last dispatch: the small picture, or the picture itself)
VkImageView sampled_view = 0;
VkImageBlit last_blit;
VkImageCopy last_copy;
// (fg_scale's pipeline is 3; fg_scale_pq's, the game's own HDR10 picture's, 5)
bool make_pipe(Pipe& p, const uint32_t* code, size_t bytes, std::initializer_list<int> types, uint32_t push) {
    const bool pq = code == FG_SCALE_PQ_COMP_SPV;
    CHECK((pq ? bytes == sizeof FG_SCALE_PQ_COMP_SPV : code == FG_SCALE_COMP_SPV && bytes == sizeof FG_SCALE_COMP_SPV));
    CHECK(types.size() == 3 && push == sizeof(ScalePush));   // (fg_scale_post.h: the FXAA, Bloom and Colour grade rows too)
    CHECK(*types.begin() == VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER && *(types.begin() + 1) == VK_DESCRIPTOR_TYPE_STORAGE_IMAGE);
    const bool fail = pq ? pq_pipe_fail : pipe_fail;
    ++pipe_calls; p.set = 1; p.layout = 2; p.pipe = fail ? 0 : pq ? 5 : 3; return !fail;
}
int vkCreateSampler(int, const VkSamplerCreateInfo* s, void*, VkSampler* out) {
    CHECK(s->magFilter == VK_FILTER_LINEAR && s->minFilter == VK_FILTER_LINEAR);
    ++sampler_calls; *out = sampler_fail ? 0 : 4; return sampler_fail ? -1 : VK_SUCCESS;
}
void vkDestroyPipeline(int, uint64_t, void*) { ++destroyed_pipes; }
void vkDestroyPipelineLayout(int, uint64_t, void*) { ++destroyed_layouts; }
void vkDestroyDescriptorSetLayout(int, uint64_t, void*) { ++destroyed_sets; }
void queue_flush_locked() { CHECK(dev.present_mu.held); ++flushes; }
void vkDeviceWaitIdle(int) {
    CHECK(dev.present_mu.held); // the real scaler must take the submit lock before waiting
    CHECK(flushes > waits); // upstream batching must be drained before waiting for idle
    ++waits;
}
// vk_replay.cpp's helper (it also takes the present queue's own lock, which this fixture has no queue for): drain, then idle
void device_wait_idle_locked() { queue_flush_locked(); vkDeviceWaitIdle(dev.device); }
void drop_img(Img& i) { i = {}; }
bool make_img(Img& i, uint32_t w, uint32_t h, int format, int usage) {
    CHECK(w && h && (format == VK_FORMAT_R8G8B8A8_UNORM || format == VK_FORMAT_A2B10G10R10_UNORM_PACK32));
    ++image_calls; made_w = w; made_h = h; made_usage = usage; made_format = format;
    if (image_fail) { image_fail = false; i.image = ++next_handle; return false; } // image made, view failed
    i.image = ++next_handle; i.view = ++next_handle; return true;
}
void to_general(int, VkImage image) { CHECK(image); }
void full_barrier(int) {}
void vkCmdBlitImage(int, VkImage src, int, VkImage dst, int, int count, const VkImageBlit* b, int filter) {
    CHECK(src == 11 && dst && count == 1 && filter == VK_FILTER_NEAREST);
    ++blits; last_blit = *b;
}
void vkCmdCopyImage(int, VkImage src, int, VkImage dst, int, int count, const VkImageCopy* c) {
    CHECK(src == 11 && dst && count == 1);
    ++copies; last_copy = *c;
}
void pass(int, const Pipe& p, std::initializer_list<std::pair<VkImageView, VkSampler>> b,
          uint32_t w, uint32_t h, const void* data, uint32_t bytes) {
    CHECK((p.pipe == 3 || p.pipe == 5) && b.size() == 3 && b.begin()->first && b.begin()->second == 4 && bytes == sizeof(ScalePush));
    CHECK((b.begin() + 2)->first && (b.begin() + 2)->second == 4);
    CHECK((b.begin() + 1)->first && !(b.begin() + 1)->second);
    ScalePush pc;
    std::memcpy(&pc, data, sizeof pc);
    dispatched_look = pc.look, dispatched_bloom = pc.bloom, dispatched_fxaa = pc.fxaa, dispatched_sat = pc.sat;
    dispatched_retro = pc.retro, small_bound = (b.begin() + 2)->first, dispatched_pc = pc;
    ++dispatches; dispatched_mode = pc.mode; dispatched_sharp = pc.sharp;
    dispatched_side = pc.side; dispatched_x0 = pc.x0; dispatched_x1 = pc.x1; dispatched_cover = pc.cover;
    dispatched_w = w; dispatched_h = h; sampled_view = b.begin()->first; dispatched_pipe = p.pipe;
}
void logf(const char*, ...) { CHECK(dispatches > 0); ++logs; }
// PRODUCTION_FUNCTIONS
void reset() {
    scale = {}; fg = {}; opts = {}; wide_now = WideSides{}; dev.push_descriptor = true; dev.hdr = false; vkCmdPushDescriptorSetKHR = true;
    pipe_calls = sampler_calls = image_calls = dispatches = blits = copies = waits = flushes = 0;
    destroyed_pipes = destroyed_layouts = destroyed_sets = 0;
    pipe_fail = sampler_fail = image_fail = pq_pipe_fail = false;
}
VkImage draw(const int* crop = nullptr, uint32_t dw = 2560, uint32_t dh = 1440, bool pq = false) {
    return framegen_scale(1, 12, 11, 2560, 1440, crop, dw, dh, pq);
}
int main() {
    reset(); CHECK(!draw()); CHECK(pipe_calls == 0 && image_calls == 0 && dispatches == 0);
    opts.upscale = 1;
    CHECK(!framegen_scale(1, 0, 11, 2560, 1440, nullptr, 100, 100, false));
    CHECK(!framegen_scale(1, 12, 11, 0, 1440, nullptr, 100, 100, false));
    CHECK(!draw(nullptr, 0));
    const int bad[][4] = {{-1,0,10,10}, {2560,0,10,10}, {0,1440,10,10}};
    for (const auto& crop : bad) CHECK(!draw(crop));
    CHECK(pipe_calls == 0 && image_calls == 0);
    for (int mode : {1, 2, 0}) {
        reset(); opts.upscale = mode; opts.sharpness = mode ? 0 : 37;
        CHECK(!framegen_on() && !fg.init && !fg.thread_started);
        CHECK(draw()); // original FG-off implementation returns null here
        CHECK(pipe_calls == 1 && sampler_calls == 1 && dispatches == 1 && image_calls == 1);
        CHECK(dispatched_mode == mode && dispatched_sharp == (mode ? 0.0f : 0.37f));
        CHECK(dispatched_w == 2560 && dispatched_h == 1440 && sampled_view == 12);
        CHECK(made_usage == (VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_SAMPLED_BIT));   // (sampled: the HDR pass reads it)
        CHECK(draw()); CHECK(pipe_calls == 1 && sampler_calls == 1 && image_calls == 1);
        CHECK(!fg.init && !fg.thread_started && !framegen_on());
        opts.upscale = opts.sharpness = 0; CHECK(!draw());
        CHECK(dispatches == 2 && image_calls == 1 && pipe_calls == 1);
    }
    // (the FXAA, Bloom and Colour grade rows alone run the pass, each with its value; none on the game's own HDR10 picture. The
    // Bloom first makes the picture at 1/8, as the blurred sides do, and the pass then runs without the sides)
    reset(); opts.fxaa = 1; CHECK(draw()); CHECK(dispatches == 1 && dispatched_fxaa == 1 && dispatched_look == 0 && dispatched_bloom == 0.0f);
    reset(); opts.fxaa = 1; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    reset(); opts.grade = 3; CHECK(draw()); CHECK(dispatches == 1 && dispatched_look == 3 && dispatched_sat == kGradeLooks[3][0] && dispatched_fxaa == 0);
    reset(); opts.grade = kGrades + 4; CHECK(draw()); CHECK(dispatched_look == kGrades - 1);   // (an options file's value past the last: the last)
    reset(); opts.bloom = 2; CHECK(draw()); CHECK(dispatches == 2 && dispatched_side == 0 && dispatched_bloom == kBloomLevels[2]);
    reset(); opts.bloom = 3; opts.grade = 1; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    // (the Retro look alone runs the pass too: first its picture of kRetroLines (240) lines, as wide as the window's picture at
    // that height (427 for 16:9), then the pass that reads it, unsharpened. None on the game's own HDR10 picture; an options
    // file's value past the last is the last)
    reset(); opts.retro = 1; opts.sharpness = 60; CHECK(draw());
    CHECK(dispatches == 2 && dispatched_retro == 1 && dispatched_side == 0 && dispatched_sharp == 0.0f && dispatched_fxaa == 0);
    CHECK(image_calls == 2 && made_w == 427 && made_h == kRetroLines && small_bound == scale.small.view && sampled_view == 12);
    reset(); opts.retro = 2; opts.fxaa = 1; CHECK(draw(nullptr, 3440, 1440));   // (an ultrawide window: 573 x 240)
    CHECK(dispatched_retro == 2 && made_w == 573 && made_h == 240 && dispatched_fxaa == 1);   // (the shader puts it before FXAA)
    reset(); opts.retro = kRetroLooks + 2; CHECK(draw()); CHECK(dispatched_retro == kRetroLooks - 1);
    // (N64 + CRT pushes its rows: the defaults Lottes' hardScan -8, an aperture grille at 30%, his bloom 0.15, a subtle curve;
    // each cut to its range. N64 and Off push none of them)
    reset(); opts.retro = 2; CHECK(draw());
    CHECK(dispatched_pc.scan == -8.0f && dispatched_pc.mask == 1 && dispatched_pc.mask_str == 0.3f && dispatched_pc.glow == 0.15f);
    CHECK(dispatched_pc.warp_x == kCrtCurve[1][0] && dispatched_pc.warp_y == kCrtCurve[1][1] && dispatched_pc.corner == kCrtCurve[1][2]);
    reset(); opts.retro = 2; opts.crt_scanlines = 9; opts.crt_mask = -1; opts.crt_mask_strength = 400; opts.crt_glow = -5;
    opts.crt_curvature = 7; CHECK(draw());
    CHECK(dispatched_pc.scan == kCrtScan[kCrtScans - 1] && dispatched_pc.mask == 0 && dispatched_pc.mask_str == 1.0f &&
          dispatched_pc.glow == 0.0f && dispatched_pc.warp_x == 0.031f && dispatched_pc.corner == kCrtCurve[kCrtCurves - 1][2]);
    reset(); opts.retro = 2; opts.crt_mask = 3; opts.crt_mask_strength = 0; opts.crt_scanlines = 0; CHECK(draw());
    CHECK(dispatched_pc.mask == 3 && dispatched_pc.mask_str == 0.1f && dispatched_pc.scan == 0.0f);
    reset(); opts.retro = 1; CHECK(draw());
    CHECK(dispatched_pc.scan == 0.0f && dispatched_pc.mask == 0 && dispatched_pc.glow == 0.0f && dispatched_pc.warp_x == 0.0f);
    reset(); opts.retro = 2; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    // (Brightness: at 100% no pass and the gamma 1; else the pass alone, the code to the power 100 / brightness, cut to 70..150;
    // never for an HDR window, where HDR paper white does it, nor on the game's own HDR10 picture)
    reset(); CHECK(!draw()); CHECK(dispatches == 0);
    reset(); opts.brightness = 150; CHECK(draw()); CHECK(dispatches == 1 && dispatched_pc.gamma == 100.0f / 150.0f && dispatched_retro == 0);
    reset(); opts.brightness = 70; opts.grade = 1; CHECK(draw()); CHECK(dispatched_pc.gamma == 100.0f / 70.0f && dispatched_look == 1);
    reset(); opts.brightness = 400; CHECK(draw()); CHECK(dispatched_pc.gamma == 100.0f / 150.0f);
    reset(); opts.brightness = 150; dev.hdr = true; CHECK(!draw()); CHECK(dispatches == 0);
    opts.grade = 2; CHECK(draw()); CHECK(dispatched_pc.gamma == 1.0f); dev.hdr = false;
    reset(); opts.brightness = 150; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    reset(); opts.grade = 1; CHECK(draw()); CHECK(dispatched_pc.gamma == 1.0f && dispatched_pc.cvd == 0);
    // (Colour vision: each of the three alone runs the pass with its type, a value past the last the last; not on pq; with HDR
    // expanded it still runs, on the SDR picture before the expansion)
    for (int type = 1; type <= 3; type++) {
        reset(); opts.colour_vision = type; CHECK(draw()); CHECK(dispatches == 1 && dispatched_pc.cvd == type);
    }
    reset(); opts.colour_vision = 9; CHECK(draw()); CHECK(dispatched_pc.cvd == 3);
    reset(); opts.colour_vision = 2; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    reset(); opts.colour_vision = 1; dev.hdr = true; CHECK(draw()); CHECK(dispatched_pc.cvd == 1 && dispatched_pc.gamma == 1.0f);
    reset(); opts.retro = -3; CHECK(!draw()); CHECK(dispatches == 0);
    reset(); opts.retro = 2; CHECK(!draw(nullptr, 2560, 1440, true)); CHECK(dispatches == 0);
    // (a picture under 240 lines: its own size, never more pixels than it has, however wide the window)
    {
        const int tiny[] = {0, 0, 320, 180};
        reset(); opts.retro = 1; CHECK(draw(tiny)); CHECK(made_w == 320 && made_h == 180);
        reset(); opts.retro = 1; CHECK(draw(tiny, 3440, 1440)); CHECK(made_w == 320 && made_h == 180);
    }
    // (with a menu's blurred sides: one small picture, the Retro look's, which the sides read too; Off again, the pass not run
    // for it, and the sides' small picture back at 1/8)
    reset(); opts.retro = 1; wide_now = WideSides{0.25f, 1}; CHECK(draw());
    CHECK(dispatches == 2 && dispatched_side == 1 && dispatched_retro == 1 && made_h == kRetroLines && image_calls == 2);
    reset(); opts.retro = 1; CHECK(draw()); opts.retro = 0; CHECK(!draw()); CHECK(dispatches == 2);
    wide_now = WideSides{0.25f, 1}; CHECK(draw());
    CHECK(dispatches == 4 && dispatched_retro == 0 && made_w == 320 && made_h == 180 && image_calls == 3);
    // (ultrawide's menu sides alone run the pass, with the plain copy, and push the middle 16:9's edges)
    reset(); wide_now = WideSides{0.25f, 2}; CHECK(draw());
    CHECK(dispatches == 1 && dispatched_mode == 0 && dispatched_sharp == 0.0f);
    CHECK(dispatched_side == 2 && dispatched_x0 == 0.25f && dispatched_x1 == 0.75f);
    wide_now = WideSides{}; CHECK(!draw()); CHECK(dispatches == 1);
    // (the loading cover in the middle 16:9 alone runs the pass too, the sides closed by as much as it is, with no menu sides;
    // with the blurred sides of a loading screen it closes those)
    reset(); wide_now = WideSides{0.25f, 0, 65535}; CHECK(draw());
    CHECK(dispatches == 1 && dispatched_side == 0 && dispatched_cover == 1.0f && dispatched_x0 == 0.25f && dispatched_x1 == 0.75f);
    reset(); wide_now = WideSides{0.25f, 0, 32768}; CHECK(draw());
    CHECK(dispatched_cover > 0.4999f && dispatched_cover < 0.5001f);
    reset(); wide_now = WideSides{0.25f, 2}; CHECK(draw()); CHECK(dispatched_cover == 0.0f);
    reset(); wide_now = WideSides{0.25f, 1, 65535}; CHECK(draw());
    CHECK(dispatches == 2 && dispatched_side == 1 && dispatched_cover == 1.0f);
    // (a frame the display thread shows, frame generation's: the cover is in its sides already, framegen_record's copy; the
    // menu sides are still this pass's)
    wide_cover_in_frame = true;
    reset(); wide_now = WideSides{0.25f, 0, 65535}; CHECK(!draw()); CHECK(dispatches == 0);
    reset(); wide_now = WideSides{0.25f, 2, 65535}; CHECK(draw()); CHECK(dispatched_side == 2 && dispatched_cover == 0.0f);
    wide_cover_in_frame = false;
    reset(); wide_now = WideSides{0.25f, 0, 65535}; CHECK(draw()); CHECK(dispatched_cover == 1.0f);
    // (the reading may be of the game's next frame: a frame's sides take the larger of its reading and the one before, so an
    // opening cover's sides follow a present behind and a closing cover's at once)
    {
        const float read[] = {0.0f, 0.25f, 1.0f, 1.0f, 0.75f, 0.5f, 0.5f, 0.25f, 0.0f, 0.0f};
        const float held[] = {0.0f, 0.25f, 1.0f, 1.0f, 1.0f, 0.75f, 0.5f, 0.5f, 0.25f, 0.0f};
        for (int i = 0; i < 10; i++) CHECK(wide_cover_held(read[i]) == held[i]);
    }
    // (the blurred sides: first the picture at 1/8, then the pass, which reads it)
    reset(); wide_now = WideSides{0.25f, 1}; CHECK(draw());
    CHECK(dispatches == 2 && dispatched_side == 1 && dispatched_x0 == 0.25f && dispatched_x1 == 0.75f);
    CHECK(image_calls == 2);
    reset(); opts.upscale = 1; opts.framegen = std::atoi(std::getenv("RX_VK_FRAMEGEN")) == 0 ? 2 : 0;
    CHECK(!framegen_on()); CHECK(draw()); CHECK(!fg.init && !fg.thread_started);
    reset(); opts.upscale = 1; pipe_fail = true;
    CHECK(!draw() && scale.failed && !fg.failed); CHECK(pipe_calls == 1 && sampler_calls == 0 && dispatches == 0);
    CHECK(destroyed_sets == 1 && destroyed_layouts == 1 && destroyed_pipes == 0);
    pipe_fail = false; CHECK(!draw() && pipe_calls == 1); // cached failure, no per-frame allocation loop
    reset(); opts.upscale = 2; sampler_fail = true;
    CHECK(!draw() && dispatches == 0 && image_calls == 0);
    CHECK(destroyed_sets == 1 && destroyed_layouts == 1 && destroyed_pipes == 1);
    reset(); opts.upscale = 1; dev.push_descriptor = false; CHECK(!draw()); CHECK(pipe_calls == 0);
    reset(); opts.upscale = 1; CHECK(draw());
    image_fail = true; CHECK(!draw(nullptr, 1920, 1080));
    CHECK(scale.scaled_w == 0 && scale.scaled_h == 0 && !scale.scaled.image);
    CHECK(draw()); CHECK(image_calls == 3 && dispatches == 2); // old size must allocate again after failure
    reset(); opts.upscale = 2;
    const int crop[] = {2500, 1400, 100, 100}; CHECK(draw(crop, 1920, 1080));
    CHECK(blits == 1 && last_blit.srcOffsets[1].x == 2560 && last_blit.srcOffsets[1].y == 1440);
    CHECK(last_blit.dstOffsets[1].x == 60 && last_blit.dstOffsets[1].y == 40 && sampled_view == scale.cropped.view);
    const int resized_crop[] = {0,0,1280,720}; image_fail = true; CHECK(!draw(resized_crop));
    CHECK(!scale.cropped.image && scale.cropped_w == 0 && scale.cropped_h == 0);
    CHECK(draw(crop, 1920, 1080)); CHECK(blits == 2 && !fg.init && !fg.thread_started);
    CHECK(logs == (std::getenv("RX_VK_UPSCALE_LOG") ? 1 : 0));
    // (Native HDR, pq: the game's PQ picture scaled by fg_scale_pq, made at its first use, into RGB10A2 images; the crop copied
    // as its bits, not blitted (the texture's image may be RGBA8 with the RGB10A2 picture in it); the SDR picture's images
    // made again in RGBA8 after it)
    reset(); opts.sharpness = 50;
    CHECK(draw(nullptr, 2560, 1440, true));
    CHECK(pipe_calls == 2 && dispatched_pipe == 5 && image_calls == 1 && made_format == VK_FORMAT_A2B10G10R10_UNORM_PACK32);
    CHECK(draw(nullptr, 2560, 1440, true)); CHECK(pipe_calls == 2 && image_calls == 1 && dispatched_pipe == 5);
    const int pq_crop[] = {160, 90, 2240, 1260};
    CHECK(draw(pq_crop, 2560, 1440, true));
    CHECK(copies == 1 && blits == 0 && sampled_view == scale.cropped.view && made_format == VK_FORMAT_A2B10G10R10_UNORM_PACK32);
    CHECK(last_copy.srcOffset.x == 160 && last_copy.srcOffset.y == 90 && last_copy.extent.width == 2240 && last_copy.extent.height == 1260);
    const int waited = waits;
    CHECK(draw(pq_crop, 2560, 1440, false));
    CHECK(dispatched_pipe == 3 && blits == 1 && copies == 1 && made_format == VK_FORMAT_R8G8B8A8_UNORM && waits > waited);
    CHECK(draw(pq_crop, 2560, 1440, true) && dispatched_pipe == 5 && copies == 2 && pipe_calls == 2);
    // (ultrawide's blurred sides: fg_scale_pq writes the 1/8 picture too, so it is RGB10A2 as well)
    reset(); wide_now = WideSides{0.25f, 1}; CHECK(draw(nullptr, 2560, 1440, true));
    CHECK(dispatches == 2 && dispatched_pipe == 5 && image_calls == 2 && made_format == VK_FORMAT_A2B10G10R10_UNORM_PACK32);
    // (fg_scale_pq not made: the game's picture unscaled, said once and not tried again; the SDR picture still scaled)
    reset(); opts.upscale = 1; CHECK(draw()); pq_pipe_fail = true;
    const int logged = logs;
    CHECK(!draw(nullptr, 2560, 1440, true) && pipe_calls == 2 && logs == logged + 1 && dispatches == 1);
    CHECK(!draw(nullptr, 2560, 1440, true) && pipe_calls == 2 && logs == logged + 1);
    CHECK(draw() && dispatched_pipe == 3 && dispatches == 2);
    std::puts("PASS: production scaler works independently, caches/retries safely, scales Native HDR's picture in 10 bits, "
              "and leaves interpolation uninitialized");
}
