// (hookshot) The Screenshot key (vk_screenshot.h): the picture as the window shows it, copied in the present's own command
// buffer (present_image), read back once that frame slot's fence was waited for (as the frame log's readback is), and made
// into a PNG on a thread of its own in screenshots/ in the game folder. One picture at a time: a press while one is still
// read back or written is taken by the frame after it. The readback's memory is made for the picture and let go after it.
#include "vk_screenshot.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <ctime>
#include <exception>
#include <string>
#include <thread>
#include <vector>

#include "screenshot.h"
#include "vk_dump.h"           // (write_png: vk_replay.cpp's PNG writer, the other shots')
#include "vk_menu.h"          // (opts: the paper white and the peak the game is told with Native HDR)
#include "vk_paths.h"          // (game_module_path: the game folder)
#include "vk_present_rect.h"   // (present_source_rect: the picture's crop)
#include "vk_texture.h"        // (full_barrier)
#include "vk_internal.h"
#include "vk_work.h"   // (after the others: the copies go through the recorder, in order with the present's own commands)

namespace mkwvk {
namespace {

std::atomic<bool> asked{false};
std::atomic<int64_t> note_until{0};   // (the steady clock's ns: the note shows until then)
std::atomic<bool> note_saved{false};

int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
void note(bool saved) {
    note_saved.store(saved, std::memory_order_relaxed);
    note_until.store(now_ns() + (int64_t)screenshot::kNoteMs * 1000000, std::memory_order_release);
}

// (present_image_mu) The picture's readback: made when one is asked for, let go once the writer copied it out
struct Readback {
    VkImage image = VK_NULL_HANDLE;   // (the SDR picture scaled to its size in the window here, when the scale pass did not run)
    VmaAllocation image_alloc = nullptr;
    VkBuffer buf = VK_NULL_HANDLE;    // (cached host memory, mapped: the writer reads it on its own thread)
    VmaAllocation buf_alloc = nullptr;
    void* map = nullptr;
    uint32_t w = 0, h = 0;
    bool pq = false;
    double white = 0, peak = 0;
    std::tm when{};
    int slot = -1;   // (the frame slot whose command buffer fills it; -1: none on its way)
};
Readback rb;
std::atomic<bool> writing{false};   // (the writer is copying rb's buffer out: rb is left alone until it is done)

void release(Readback& r) {
    if (r.buf) destroy_buffer(r.buf, r.buf_alloc);
    if (r.image) destroy_image(r.image, r.image_alloc);
    r = Readback{};
}

void layout(VkCommandBuffer cmd, VkImage image, VkImageLayout from, VkImageLayout to) {
    VkImageMemoryBarrier2 b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2};
    b.srcStageMask = b.dstStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;
    b.srcAccessMask = VK_ACCESS_2_MEMORY_WRITE_BIT;
    b.dstAccessMask = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;
    b.oldLayout = from;
    b.newLayout = to;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = image;
    b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    VkDependencyInfo d{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
    d.imageMemoryBarrierCount = 1;
    d.pImageMemoryBarriers = &b;
    vkCmdPipelineBarrier2(cmd, &d);
}

/// The copy made available to the CPU's reads (the host's memory domain), as the other captures' are
void host_read(VkCommandBuffer cmd, VkBuffer buffer, VkDeviceSize bytes) {
    VkBufferMemoryBarrier2 b{VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER_2};
    b.srcStageMask = VK_PIPELINE_STAGE_2_COPY_BIT;
    b.srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT;
    b.dstStageMask = VK_PIPELINE_STAGE_2_HOST_BIT;
    b.dstAccessMask = VK_ACCESS_2_HOST_READ_BIT;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.buffer = buffer;
    b.size = bytes;
    VkDependencyInfo d{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
    d.bufferMemoryBarrierCount = 1;
    d.pBufferMemoryBarriers = &b;
    vkCmdPipelineBarrier2(cmd, &d);
}

/// The game folder, its separator at the end ("" when it cannot be told: the working folder)
std::string game_folder() {
    char exe[1024];
    const DWORD n = game_module_path(exe, sizeof exe);
    if (!n || n >= sizeof exe) return std::string();
    const std::string path(exe, n);
    return path.substr(0, path.find_last_of("\\/") + 1);
}

/// What collect hands the writer: the readback's mapping (the writer's alone until it lets writing go) and the picture's facts
struct Job {
    const void* map;
    uint32_t w, h;
    bool pq;
    double white, peak;
    std::tm when;
};

void write_shot(const Job& j) {
    SetThreadDescription(GetCurrentThread(), L"mkw_vk screenshot");
    const size_t n = (size_t)j.w * j.h;
    std::vector<uint8_t> rgba;
    bool copied = false;
    try {
        rgba.resize(n * 4);
        // (Native HDR: the game's PQ codes made into the SDR picture (screenshot.h). Else the picture's own bytes, RGBA8 as the
        // window shows them)
        if (j.pq) screenshot::hdr10_to_rgba8(static_cast<const uint32_t*>(j.map), n, rgba.data(), j.white, j.peak);
        else std::memcpy(rgba.data(), j.map, n * 4);
        copied = true;
    } catch (const std::exception&) {
    }
    writing.store(false, std::memory_order_release);   // (the readback is the present's again: let go at its next frame)
    const std::string base = game_folder();
    const std::string folder = base + screenshot::kFolder;
    const bool made = CreateDirectoryA(folder.c_str(), nullptr) || GetLastError() == ERROR_ALREADY_EXISTS;
    const char sep = base.empty() ? '/' : base.back();   // (the game folder's own separator)
    const std::string path = made ? screenshot::free_path(folder + sep, j.when, [](const std::string& p) {
        return GetFileAttributesA(p.c_str()) != INVALID_FILE_ATTRIBUTES;
    }) : std::string();
    const bool saved = copied && !path.empty() && write_png(path.c_str(), rgba.data(), j.w, j.h);
    if (saved)
        logf("vk: screenshot (%ux%u%s) written to %s", j.w, j.h, j.pq ? ", Native HDR's picture tone mapped to SDR" : "",
             path.c_str());
    else if (!copied)
        logf("vk: screenshot not written: no memory for its %ux%u picture", j.w, j.h);
    else if (!made)
        logf("vk: screenshot not written: the folder %s could not be made (error %lu)", folder.c_str(), (unsigned long)GetLastError());
    else if (path.empty())
        logf("vk: screenshot not written: %d were taken in this second already", screenshot::kMaxSameSecond);
    else
        logf("vk: screenshot not written to %s", path.c_str());
    note(saved);
}

}  // namespace

void screenshot_ask() { asked.store(true, std::memory_order_relaxed); }

void screenshot_record(VkCommandBuffer cmd, int slot, const ShownPicture& p) {
    if (rb.buf && rb.slot < 0 && !writing.load(std::memory_order_acquire)) release(rb);   // (the last one is written: let go)
    if (!asked.load(std::memory_order_relaxed) || p.made) return;   // (a made frame: the next of the game's own is taken)
    if (rb.slot >= 0 || writing.load(std::memory_order_acquire)) return;   // (the one before is still on its way: the next frame)
    asked.store(false, std::memory_order_relaxed);
    const bool scaled = p.scaled != VK_NULL_HANDLE;
    const PresentSourceRect source = present_source_rect(p.sw, p.sh, p.crop);
    // (Native HDR without the scale pass: the game's codes copied as they are, at the picture's own size. A blit would convert
    // them from its image's format, which is not always the picture's (vk_texture.cpp format_class), as the window never does)
    const bool raw = p.pq && !scaled;
    const uint32_t w = raw ? source.w : p.w, h = raw ? source.h : p.h;
    if (!w || !h || (!scaled && (!p.src || !source.w || !source.h))) {   // (the start-up screen: no picture of the game's yet)
        logf("vk: screenshot not taken: the game shows no picture yet");
        note(false);
        return;
    }
    Readback next;
    const uint64_t bytes = (uint64_t)w * h * 4;
    bool ok = create_buffer_cached(bytes, VK_BUFFER_USAGE_TRANSFER_DST_BIT, next.buf, next.buf_alloc, &next.map, true) && next.map;
    if (ok && !scaled && !raw) {
        VkImageCreateInfo ci{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        ci.imageType = VK_IMAGE_TYPE_2D;
        ci.format = VK_FORMAT_R8G8B8A8_UNORM;
        ci.extent = {w, h, 1};
        ci.mipLevels = ci.arrayLayers = 1;
        ci.samples = VK_SAMPLE_COUNT_1_BIT;
        ci.usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        ok = create_image(ci, next.image, next.image_alloc);
    }
    if (!ok) {
        release(next);
        logf("vk: screenshot not taken: no memory for its %ux%u readback", w, h);
        note(false);
        return;
    }
    full_barrier(cmd);   // (after the picture's writes: the scale pass's, or the game's frame)
    const VkBufferImageCopy whole{0, 0, 0, {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}, {0, 0, 0}, {w, h, 1}};
    if (scaled) {   // (the scale pass's image, as the window got it: RGBA8, or RGB10A2 PQ codes with Native HDR)
        vkCmdCopyImageToBuffer(cmd, p.scaled, VK_IMAGE_LAYOUT_GENERAL, next.buf, 1, &whole);
    } else if (raw) {
        VkBufferImageCopy c = whole;
        c.imageOffset = {(int32_t)source.x, (int32_t)source.y, 0};
        vkCmdCopyImageToBuffer(cmd, p.src, VK_IMAGE_LAYOUT_GENERAL, next.buf, 1, &c);
    } else {   // (the picture's crop scaled to its size in the window, as the window's own copy does it)
        layout(cmd, next.image, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
        VkImageBlit b{};
        b.srcSubresource = b.dstSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
        b.srcOffsets[0] = {(int32_t)source.x, (int32_t)source.y, 0};
        b.srcOffsets[1] = {(int32_t)(source.x + source.w), (int32_t)(source.y + source.h), 1};
        b.dstOffsets[1] = {(int32_t)w, (int32_t)h, 1};
        vkCmdBlitImage(cmd, p.src, VK_IMAGE_LAYOUT_GENERAL, next.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &b, VK_FILTER_LINEAR);
        layout(cmd, next.image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
        vkCmdCopyImageToBuffer(cmd, next.image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, next.buf, 1, &whole);
    }
    host_read(cmd, next.buf, bytes);
    next.w = w, next.h = h, next.pq = p.pq;
    // (the paper white and the peak brightness the game is told with Native HDR, vk_replay.cpp's option(): its picture's white
    // and its brightest)
    next.white = std::clamp(opts.hdr_white, 80, 500), next.peak = std::clamp(opts.hdr_peak, 400, 10000);
    const std::time_t now = std::time(nullptr);
    if (localtime_s(&next.when, &now) != 0) next.when = std::tm{};
    next.slot = slot;
    rb = next;
}

void screenshot_collect(int slot) {
    if (slot < 0 || rb.slot != slot) return;
    rb.slot = -1;
    invalidate_mapped(rb.buf_alloc, (uint64_t)rb.w * rb.h * 4);   // (what the GPU wrote, seen by the CPU's reads)
    writing.store(true, std::memory_order_release);
    const Job job{rb.map, rb.w, rb.h, rb.pq, rb.white, rb.peak, rb.when};
    try {
        std::thread([job] { write_shot(job); }).detach();
    } catch (const std::exception&) {
        writing.store(false, std::memory_order_release);
        logf("vk: screenshot not written: no thread to write it on");
        note(false);
    }
}

bool screenshot_note(bool* saved) {
    const int64_t until = note_until.load(std::memory_order_acquire);
    if (!until || now_ns() >= until) return false;
    if (saved) *saved = note_saved.load(std::memory_order_relaxed);
    return true;
}

}  // namespace mkwvk
