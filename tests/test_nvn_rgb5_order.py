"""NVN's 16-bit packed texture formats sample in the Vulkan renderer as NVN defines them: every 16-bit texel of RGB5A1,
RGB5, RGB565, BGR565 and RGBA4, decoded from the Vulkan format gpu/vk/vk_formats.cpp vk_format keeps it in (the spec's
bit layout: packed formats from the most significant bit) and read through the sampled view's swizzle as vk_texture.cpp
texture_view makes it, reads what the WebGPU renderer's decoding of the same NVN format reads (gpu/render/rx_nvn.cpp
nvn_pixel_format, gpu/render/rx_texture.cpp convert_packed16), with the game's own swizzle too.

NVN names packed formats from the lowest bit: RGB5A1 is red in bits 0-4, green 5-9, blue 10-14, alpha 15 (deko3d,
source/maxwell/format_traits.inc: A1B5G5R5 with R,G,B,A; RGB5 the same with alpha one), as RGB565 is red in bits 0-4.
The real code is cut out of the sources and compiled with stubs. Synthetic data only.
python -I -B tests/test_nvn_rgb5_order.py --headers <Vulkan headers> [--cxx clang++]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]
FORMATS = ("RGB5A1", "RGB5", "RGB565", "BGR565", "RGBA4")


def block(text, marker, semicolon=False):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end] + (";" if semicolon else "")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="clang++")
    p.add_argument("--headers", type=Path, required=True)
    a = p.parse_args()
    fmts = (ROOT / "gpu/vk/vk_formats.cpp").read_text(encoding="utf-8")
    tex = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    rx_nvn = (ROOT / "gpu/render/rx_nvn.cpp").read_text(encoding="utf-8")
    rx_tex = (ROOT / "gpu/render/rx_texture.cpp").read_text(encoding="utf-8")
    # the sampled view's swizzle, as texture_view makes it: from the descriptor's swizzle to the VkComponentMapping
    view = block(tex, "VkImageView texture_view(")
    start = view.index("        unsigned sw[4] = {d.swizzle_r")
    end_mark = "        cm = {component(sw[0]), component(sw[1]), component(sw[2]), component(sw[3])};"
    swizzle = view[start:view.index(end_mark) + len(end_mark)]
    # the WebGPU renderer's pixel format of each NVN format (RGB5 has none there: RGB5A1's, alpha one)
    webgpu = dict(re.findall(r"case NVN_FORMAT_(\w+): return P::(\w+);", block(rx_nvn, "PixelFormat nvn_pixel_format(")))
    webgpu["RGB5"] = webgpu["RGB5A1"]
    cases = ",\n".join(f"    {{NVN_FORMAT_{f}, PixelFormat::{webgpu[f]}, {int(f == 'RGB5')}, \"{f}\"}}" for f in FORMATS)
    fixture = r'''
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan_core.h>
#include "nvn_api.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <utility>
static const char* at = "";
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s (%s)\n", __LINE__, #x, at); std::exit(1); } } while (0)
struct VkFormatInfo { VkFormat format; bool astc; int block_w, block_h; };
namespace { bool astc_native() { return false; } }
static bool env_on(const char*) { return false; }
''' + block(fmts, "namespace {\nconstexpr int kAstcBw", True) + "\n" + block(fmts, "VkFormatInfo vk_format(") + "\n" + \
        block(tex, "VkComponentSwizzle component(") + "\n" + block(tex, "VkFormat widened(") + "\n" + \
        block(tex, "bool alpha_reads_one(") + r'''
// the WebGPU renderer's decoding (gpu/render/rx_texture.cpp), to RGBA8
enum class PixelFormat { R5G6B5_UNORM, B5G6R5_UNORM, A1R5G5B5_UNORM, A1B5G5R5_UNORM, A5B5G5R1_UNORM, A4B4G4R4_UNORM, G4R4_UNORM };
''' + block(rx_tex, "uint8_t expand(") + "\n" + block(rx_tex, "void convert_packed16(") + r'''
// the sampled view's component mapping for a descriptor swizzle (texture_view's code)
static VkComponentMapping sampled(int nf, const unsigned swizzle[4]) {
    const struct { unsigned swizzle_r, swizzle_g, swizzle_b, swizzle_a; } d{swizzle[0], swizzle[1], swizzle[2], swizzle[3]};
    const struct { bool set_swizzle; unsigned swz[4]; }* v = nullptr;
    VkComponentMapping cm{};
''' + swizzle + r'''
    return cm;
}
// a 16-bit texel as the Vulkan spec lays the format out (components from the most significant bit), to RGBA8
static void vk_decode(VkFormat f, uint32_t v, uint8_t o[4]) {
    switch (f) {
    case VK_FORMAT_A1R5G5B5_UNORM_PACK16:
        o[3] = v >> 15 ? 255 : 0, o[0] = expand(v >> 10 & 31, 5), o[1] = expand(v >> 5 & 31, 5), o[2] = expand(v & 31, 5); break;
    case VK_FORMAT_B5G5R5A1_UNORM_PACK16:
        o[2] = expand(v >> 11, 5), o[1] = expand(v >> 6 & 31, 5), o[0] = expand(v >> 1 & 31, 5), o[3] = v & 1 ? 255 : 0; break;
    case VK_FORMAT_B5G6R5_UNORM_PACK16:
        o[2] = expand(v >> 11, 5), o[1] = expand(v >> 5 & 63, 6), o[0] = expand(v & 31, 5), o[3] = 255; break;
    case VK_FORMAT_R5G6B5_UNORM_PACK16:
        o[0] = expand(v >> 11, 5), o[1] = expand(v >> 5 & 63, 6), o[2] = expand(v & 31, 5), o[3] = 255; break;
    case VK_FORMAT_A4B4G4R4_UNORM_PACK16:
        o[3] = expand(v >> 12, 4), o[2] = expand(v >> 8 & 15, 4), o[1] = expand(v >> 4 & 15, 4), o[0] = expand(v & 15, 4); break;
    default: CHECK(!"a 16-bit Vulkan format this test does not know"); break;
    }
}
static uint8_t vk_pick(VkComponentSwizzle s, int self, const uint8_t in[4]) {
    if (s == VK_COMPONENT_SWIZZLE_IDENTITY) return in[self];
    if (s == VK_COMPONENT_SWIZZLE_ZERO) return 0;
    if (s == VK_COMPONENT_SWIZZLE_ONE) return 255;
    return in[s - VK_COMPONENT_SWIZZLE_R];
}
static uint8_t nvn_pick(unsigned s, const uint8_t in[4]) {
    return s == NVN_TEXTURE_SWIZZLE_ZERO ? 0 : s == NVN_TEXTURE_SWIZZLE_ONE ? 255 : in[s - NVN_TEXTURE_SWIZZLE_R];
}
int main() {
    struct Case { int nvn; PixelFormat webgpu; int alpha_one; const char* name; };
    static const Case cases[] = {
''' + cases + r'''
    };
    // the descriptor's swizzles: none, red and blue the other way, and one reading constants and alpha
    static const unsigned swizzles[3][4] = {
        {NVN_TEXTURE_SWIZZLE_R, NVN_TEXTURE_SWIZZLE_G, NVN_TEXTURE_SWIZZLE_B, NVN_TEXTURE_SWIZZLE_A},
        {NVN_TEXTURE_SWIZZLE_B, NVN_TEXTURE_SWIZZLE_G, NVN_TEXTURE_SWIZZLE_R, NVN_TEXTURE_SWIZZLE_A},
        {NVN_TEXTURE_SWIZZLE_R, NVN_TEXTURE_SWIZZLE_A, NVN_TEXTURE_SWIZZLE_ONE, NVN_TEXTURE_SWIZZLE_ZERO}};
    long texels = 0;
    for (const Case& c : cases) {
        at = c.name;
        const VkFormat f = vk_format(c.nvn).format;
        CHECK(f != VK_FORMAT_UNDEFINED);
        for (const auto& sw : swizzles) {
            const VkComponentMapping cm = sampled(c.nvn, sw);
            const VkComponentSwizzle map[4] = {cm.r, cm.g, cm.b, cm.a};
            for (uint32_t v = 0; v < 65536; v++, texels++) {
                const uint8_t bytes[2] = {(uint8_t)v, (uint8_t)(v >> 8)};
                uint8_t nvn[4], image[4];
                convert_packed16(c.webgpu, bytes, nvn, 1);
                if (c.alpha_one) nvn[3] = 255;
                vk_decode(f, v, image);
                for (int k = 0; k < 4; k++) {
                    const uint8_t want = nvn_pick(sw[k], nvn), got = vk_pick(map[k], k, image);
                    if (want != got) {
                        std::fprintf(stderr, "%s texel %#06x, swizzle %u %u %u %u: component %d reads %u, NVN %u\n", c.name, v,
                                     sw[0], sw[1], sw[2], sw[3], k, got, want);
                        CHECK(want == got);
                    }
                }
            }
        }
    }
    std::printf("PASS: every texel of RGB5A1, RGB5, RGB565, BGR565 and RGBA4 (%ld reads, 3 swizzles) samples as NVN defines it\n",
                texels);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="nvn-rgb5-order-") as tmp:
        cpp, exe = Path(tmp) / "fixture.cpp", Path(tmp) / "fixture.exe"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-I", str(a.headers),
                        "-I", str(ROOT / "gpu/render"), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
