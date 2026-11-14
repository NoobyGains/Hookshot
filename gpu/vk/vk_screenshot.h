// (hookshot) The Screenshot key (vk_screenshot.cpp): F12 saves the picture as the window shows it, after the window's scale pass
// (the Retro look, the Colour grade, the Bloom, FXAA, Sharpness and the scaling filter in it) and without the Insert menu, the
// FPS counter or any other overlay of ours, at its size in the window, as a PNG in screenshots/ in the game folder. Copied
// in the present's own command buffer and read back once its frame slot comes round again (present_image waits for that
// slot's fence anyway), then made into a PNG and written on a thread of its own: the frame never waits for it.
#pragma once

#include <cstdint>

#include "vk_internal.h"

namespace mkwvk {

/// What present_image put in the window this frame: the picture the Screenshot key takes
struct ShownPicture {
    VkImage scaled = VK_NULL_HANDLE;   // the window's scale pass's image (framegen_scale), w x h, GENERAL; null: it did not run
    VkImage src = VK_NULL_HANDLE;      // the picture's own image and its crop (what the window copies without the pass), GENERAL
    uint32_t sw = 0, sh = 0;
    const int* crop = nullptr;
    uint32_t w = 0, h = 0;             // its size in the window (present_rect's: the black bars around it left out)
    bool pq = false;                   // the game's own HDR10 picture (Native HDR): PQ codes in RGB10A2, made SDR for the PNG
    bool made = false;                 // a frame frame generation made: not taken, the next of the game's own is
};

/// (menu_tick) The Screenshot key was pressed: the next of the game's frames present_image shows is saved
void screenshot_ask();
/// (present_image, present_image_mu held) This frame's copy, when one was asked for and none is being read back or written; in
/// slot's command buffer, after the picture went into the window's image and before the overlays are drawn over it
void screenshot_record(VkCommandBuffer cmd, int slot, const ShownPicture& p);
/// (present_image, present_image_mu held) slot's fence was waited for: a copy made in it is complete, and is written now
void screenshot_collect(int slot);
/// (menu_record) Whether the note shows now (for kNoteMs after a picture was written or failed), and whether it was saved
bool screenshot_note(bool* saved);

}  // namespace mkwvk
