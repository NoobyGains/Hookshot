"""NVN's texture formats on Vulkan (gpu/vk/vk_formats.cpp vk_format): every format gpu/render/nvn_api.h names is mapped, or
is a vertex format only (LEFT_OUT, which vk_draw.cpp vertex_format maps). Then the real format code, cut out of the sources
and compiled with stubs for a made-up GPU, checks:

- every mapped format's bytes per texel (its Vulkan format's, or the 3 components a widened one is uploaded from) are the
  texture layout's (host/nvn_layout.c fmt_of): what the game's storage holds;
- synthetic texels of each format the renderer used to leave out (RGB16 F/UNORM/SNORM/UI/I, RGB32 UI/I, BGRA8 and its sRGB
  twin, BGR5, BGR5A1, A1BGR5, RGB_DXT1 and its sRGB twin) go through what a texture's upload does with them (vk_format,
  the image's format, the upload's texel size and widen_rows for 3 components) and are read back by the Vulkan format of
  the sampled view, with its swizzle: each texel reads what NVN's definition of the format says, alpha one where the
  format has none, and a widened image holds alpha one itself (storage views and copies read it without the swizzle).

NVN's definitions: the component order of nvn_api.h's names; packed formats name their components from the lowest bit, as
RGB565 (red in bits 0-4) is read by both of LS's renderers and by deko3d (source/maxwell/format_traits.inc: RGB5A1, BGR5,
BGR5A1, A1BGR5, RGB_BC1 and BGRA8, with alpha one for BGR5 and RGB_BC1). Vulkan's: the spec's format tables (components
in name order in memory; packed formats from the most significant bit).
Synthetic data only. python -I -B tests/test_nvn_formats.py --headers <Vulkan headers> [--cxx clang++]
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}", "--headers", "{vulkan_headers}"]

ROOT = Path(__file__).resolve().parents[1]

# NVN formats with no texture mapping, and why: vertex attribute formats (deko3d's image formats name none of them;
# vk_draw.cpp vertex_format maps each)
LEFT_OUT = {
    **{v: "vertex only: an integer read as float" for v in range(0x51, 0x69)},
    0x69: "vertex only", 0x6A: "vertex only", 0x6B: "vertex only: an integer read as float",
    0x6C: "vertex only: an integer read as float",
}


def block(text, marker, semicolon=False):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end] + (";" if semicolon else "")


def vk_bytes(name):
    """A Vulkan format's bytes per texel or block, from its name (the spec's naming: bits per component, PACKn, BLOCK)"""
    if name.endswith("_BLOCK"):
        return 8 if name.startswith(("VK_FORMAT_BC1_", "VK_FORMAT_BC4_")) else 16
    if name.endswith("_PACK16"):
        return 2
    if name.endswith("_PACK32"):
        return 4
    return sum(int(bits) for bits in re.findall(r"[RGBAX](\d+)", name[len("VK_FORMAT_"):].split("_")[0])) // 8


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="clang++")
    p.add_argument("--headers", type=Path, required=True)
    a = p.parse_args()
    fmts = (ROOT / "gpu/vk/vk_formats.cpp").read_text(encoding="utf-8")
    tex = (ROOT / "gpu/vk/vk_texture.cpp").read_text(encoding="utf-8")
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    layout = (ROOT / "host/nvn_layout.c").read_text(encoding="utf-8")
    nvn_h = (ROOT / "gpu/render/nvn_api.h").read_text(encoding="utf-8")
    nvn = {int(v, 16): n for n, v in re.findall(r"(NVN_FORMAT_\w+)\s*=\s*(0x[0-9A-Fa-f]+)", nvn_h)}
    del nvn[0x0], nvn[0x7FFFFFFF]   # (NONE, LARGE)

    # the table: each format mapped (a case of vk_format, or the ASTC range) or left out, never both
    mapped = set(re.findall(r"case (NVN_FORMAT_\w+): return \{VK_FORMAT_\w+", block(fmts, "VkFormatInfo vk_format(")))
    astc = "nvn_format >= 0x79 && nvn_format <= 0x94" in fmts
    missing = [f"{v:#x} {n}" for v, n in sorted(nvn.items())
               if n not in mapped and v not in LEFT_OUT and not (astc and 0x79 <= v <= 0x94)]
    both = [f"{v:#x} {nvn[v]}" for v in LEFT_OUT if nvn[v] in mapped]
    vertex = block(draw, "VkFormat vertex_format(int f)")
    vertex_ok = "f >= 0x51 && f <= 0x68" in vertex and all(
        f"case {nvn[v]}:" in vertex for v in LEFT_OUT if v > 0x68)
    if missing or both or not vertex_ok:
        raise SystemExit("NVN formats with no Vulkan format (their textures are left out): %s; left out but mapped: %s; "
                         "vertex_format maps the left-out ones: %s" % (missing or "none", both or "none", vertex_ok))

    vk_names = sorted(set(re.findall(r"VK_FORMAT_\w+", block(fmts, "VkFormatInfo vk_format(") +
                                     block(tex, "VkFormat widened(")) + re.findall(r"VK_FORMAT_\w+", block(fmts, "constexpr VkFormat kAstcVk[14]"))))
    sizes = "\n".join(f"    case {n}: return {vk_bytes(n)};" for n in vk_names if n != "VK_FORMAT_UNDEFINED")
    formats = "\n".join([block(fmts, "namespace {\nconstexpr int kAstcBw", True), block(fmts, "VkFormatInfo vk_format("),
                         block(fmts, "bool is_depth_format("), block(fmts, "bool has_stencil(")])
    texture = "\n".join(block(tex, m) for m in (
        "bool is_bc(", "bool is_astc(", "VkFormat linear_twin(", "VkFormat widened(", "uint32_t alpha_one(",
        "VkFormat storage_view_format(", "VkFormat image_format_of(", "VkFormat view_format_of(",
        "VkFormat attachment_format(", "bool nvn_format_widened(", "bool alpha_reads_one(", "void widen_rows("))
    out_bpb = re.search(r"\n\s*(const int out_bpb = [^\n]*;)\n", tex)
    if not out_bpb:
        raise SystemExit("vk_texture.cpp: the upload's texel size (const int out_bpb = ...) is not found")
    # (host/nvn_layout.c is C, compiled as C beside the fixture: its compound literals narrow in C++)
    layout_c = "#include <stdint.h>\ntypedef struct { uint8_t bpb, bw, bh; } fmt_t;\n" + block(
        layout, "static fmt_t fmt_of(int f)").replace("static fmt_t fmt_of", "fmt_t fmt_of", 1)
    table = ", ".join(f"{{{v:#x}, {int(v in LEFT_OUT)}}}" for v in sorted(nvn))
    fixture = r'''
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan_core.h>
#include "nvn_api.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s (NVN %#x)\n", __LINE__, #x, at); std::exit(1); } } while (0)
static int at = 0;   // (the NVN format being checked)
// the made-up GPU: every feature for every format but ASTC, which it decodes (vk_format's other route: astc_native below)
static void vkGetPhysicalDeviceFormatProperties(void*, VkFormat, VkFormatProperties* p) {
    p->linearTilingFeatures = p->optimalTilingFeatures = VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT | VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT |
                                                       VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT;
    p->bufferFeatures = VK_FORMAT_FEATURE_UNIFORM_TEXEL_BUFFER_BIT | VK_FORMAT_FEATURE_STORAGE_TEXEL_BUFFER_BIT;
}
static VkFormatProperties format_props(VkFormat f) { VkFormatProperties p; vkGetPhysicalDeviceFormatProperties(nullptr, f, &p); return p; }
struct VkFormatInfo { VkFormat format; bool astc; int block_w, block_h; };
namespace { bool astc_native() { return false; } }
enum class ViewUse { Sample, Attachment, Storage };
typedef struct { uint8_t bpb, bw, bh; } fmt_t;
extern "C" fmt_t fmt_of(int f);   // (host/nvn_layout.c's, compiled as C)
''' + formats + "\nnamespace {\n" + texture + r'''
}  // namespace
// (the texel size of the upload's staging: vk_texture.cpp upload)
static int upload_out_bpb(int widen_from, int src_bpb) { struct { bool astc; } tex{false}; ''' + out_bpb.group(1) + r''' return out_bpb; }
static int vk_bytes(VkFormat f) {
    switch (f) {
''' + sizes + r'''
    default: return 0;
    }
}
struct Px { double c[4]; };
static uint32_t le(const uint8_t* p, int n) { uint32_t v = 0; for (int i = n - 1; i >= 0; i--) v = v << 8 | p[i]; return v; }
static double half(uint32_t h) {
    const int e = h >> 10 & 31, m = h & 1023;
    const double v = e == 0 ? std::ldexp(m, -24) : e == 31 ? (m ? NAN : INFINITY) : std::ldexp(1024 + m, e - 25);
    return h >> 15 ? -v : v;
}
static double unorm(uint32_t v, int bits) { return v / (double)((1u << bits) - 1); }
static double snorm(uint32_t v, int bits) {
    const int32_t s = (int32_t)(v << (32 - bits)) >> (32 - bits);
    return std::fmax(s / (double)((1 << (bits - 1)) - 1), -1.0);
}
static double sint(uint32_t v, int bits) { return (double)((int32_t)(v << (32 - bits)) >> (32 - bits)); }
// NVN's definition of a texel (alpha one where the format has none)
static Px nvn_read(int f, const uint8_t* p) {
    Px x{{0, 0, 0, 1}};
    for (int i = 0; i < 3; i++) {
        const uint32_t v16 = le(p + 2 * i, 2), v32 = le(p + 4 * i, 4);
        switch (f) {
        case NVN_FORMAT_RGB16F: x.c[i] = half(v16); break;
        case NVN_FORMAT_RGB16: x.c[i] = unorm(v16, 16); break;
        case NVN_FORMAT_RGB16SN: x.c[i] = snorm(v16, 16); break;
        case NVN_FORMAT_RGB16UI: x.c[i] = v16; break;
        case NVN_FORMAT_RGB16I: x.c[i] = sint(v16, 16); break;
        case NVN_FORMAT_RGB32UI: x.c[i] = v32; break;
        case NVN_FORMAT_RGB32I: x.c[i] = sint(v32, 32); break;
        default: break;
        }
    }
    const uint32_t w = le(p, 2);
    switch (f) {
    case NVN_FORMAT_BGRA8: case NVN_FORMAT_BGRA8_SRGB:   // (bytes: blue, green, red, alpha)
        x = {{unorm(p[2], 8), unorm(p[1], 8), unorm(p[0], 8), unorm(p[3], 8)}};
        break;
    case NVN_FORMAT_BGR5: case NVN_FORMAT_BGR5A1:   // (from bit 0: blue, green, red, then alpha or a bit unused)
        x = {{unorm(w >> 10 & 31, 5), unorm(w >> 5 & 31, 5), unorm(w & 31, 5), f == NVN_FORMAT_BGR5 ? 1.0 : (double)(w >> 15)}};
        break;
    case NVN_FORMAT_A1BGR5:   // (from bit 0: alpha, blue, green, red)
        x = {{unorm(w >> 11 & 31, 5), unorm(w >> 6 & 31, 5), unorm(w >> 1 & 31, 5), (double)(w & 1)}};
        break;
    default: break;
    }
    return x;
}
// Vulkan's definition of a texel of the formats those are kept in
static Px vk_read(VkFormat f, const uint8_t* p) {
    Px x{};
    for (int i = 0; i < 4; i++) {
        const uint32_t v16 = le(p + 2 * i, 2), v32 = le(p + 4 * i, 4);
        switch (f) {
        case VK_FORMAT_R16G16B16A16_SFLOAT: x.c[i] = half(v16); break;
        case VK_FORMAT_R16G16B16A16_UNORM: x.c[i] = unorm(v16, 16); break;
        case VK_FORMAT_R16G16B16A16_SNORM: x.c[i] = snorm(v16, 16); break;
        case VK_FORMAT_R16G16B16A16_UINT: x.c[i] = v16; break;
        case VK_FORMAT_R16G16B16A16_SINT: x.c[i] = sint(v16, 16); break;
        case VK_FORMAT_R32G32B32A32_UINT: x.c[i] = v32; break;
        case VK_FORMAT_R32G32B32A32_SINT: x.c[i] = sint(v32, 32); break;
        default: break;
        }
    }
    const uint32_t w = le(p, 2);
    switch (f) {
    case VK_FORMAT_B8G8R8A8_UNORM: case VK_FORMAT_B8G8R8A8_SRGB:
        x = {{unorm(p[2], 8), unorm(p[1], 8), unorm(p[0], 8), unorm(p[3], 8)}};
        break;
    case VK_FORMAT_A1R5G5B5_UNORM_PACK16:   // (from bit 15: alpha, red, green, blue)
        x = {{unorm(w >> 10 & 31, 5), unorm(w >> 5 & 31, 5), unorm(w & 31, 5), (double)(w >> 15)}};
        break;
    case VK_FORMAT_R5G5B5A1_UNORM_PACK16:   // (from bit 15: red, green, blue, alpha)
        x = {{unorm(w >> 11 & 31, 5), unorm(w >> 6 & 31, 5), unorm(w >> 1 & 31, 5), (double)(w & 1)}};
        break;
    default: break;
    }
    return x;
}
static bool same(double a, double b) { return a == b || (std::isnan(a) && std::isnan(b)); }
static bool vk_has(VkFormat f) {   // (vk_read knows it)
    uint8_t ones[16]; std::memset(ones, 0x55, sizeof ones);
    const Px x = vk_read(f, ones);
    return x.c[0] != 0 || x.c[1] != 0 || x.c[2] != 0 || x.c[3] != 0;
}
int main() {
    struct Nvn { int value, left_out; };
    static const Nvn all[] = {''' + table + r'''};
    // every format: mapped unless left out; the texel's size as the texture layout's
    for (const Nvn& n : all) {
        at = n.value;
        const VkFormatInfo fi = vk_format(n.value);
        CHECK((fi.format == VK_FORMAT_UNDEFINED) == (n.left_out != 0));
        if (n.left_out || fi.astc || is_depth_format(fi.format)) continue;
        const fmt_t t = fmt_of(n.value);
        int from = 0;
        const VkFormat wide = widened(fi.format, &from);
        CHECK(vk_bytes(fi.format) && vk_bytes(fi.format) == t.bpb && nvn_format_widened(n.value) == (from != 0));
        CHECK(is_bc(fi.format) ? t.bw == 4 && t.bh == 4 : t.bw == 1 && t.bh == 1);
        if (from) CHECK(from == t.bpb && vk_bytes(image_format_of(wide, false)) == upload_out_bpb(from, t.bpb));
    }
    // the formats that were left out: a texture's upload of synthetic texels, read back through its sampled view
    static const int gap[] = {NVN_FORMAT_RGB16F, NVN_FORMAT_RGB16, NVN_FORMAT_RGB16SN, NVN_FORMAT_RGB16UI, NVN_FORMAT_RGB16I,
                              NVN_FORMAT_RGB32UI, NVN_FORMAT_RGB32I, NVN_FORMAT_BGRA8, NVN_FORMAT_BGRA8_SRGB, NVN_FORMAT_BGR5,
                              NVN_FORMAT_BGR5A1, NVN_FORMAT_A1BGR5};
    uint32_t seed = 0x2545F491u;
    int texels = 0;
    for (int f : gap) {
        at = f;
        const VkFormatInfo fi = vk_format(f);
        CHECK(fi.format != VK_FORMAT_UNDEFINED && !fi.astc);
        int from = 0;
        const VkFormat wide = widened(fi.format, &from);
        const VkFormat image = image_format_of(wide, false);
        const int src = fmt_of(f).bpb, out = upload_out_bpb(from, src);
        CHECK(vk_bytes(image) == out);
        const int n = 64;   // (texels: the first all zero bits, the second all one bits, the rest made up)
        std::vector<uint8_t> guest((size_t)n * src), img((size_t)n * out);
        for (size_t i = 0; i < guest.size(); i++) {
            seed = seed * 1664525u + 1013904223u;
            guest[i] = i < (size_t)src ? 0x00 : i < 2u * src ? 0xFF : (uint8_t)(seed >> 24);
        }
        if (from) widen_rows(img.data(), guest.data(), (size_t)n, src, out, alpha_one(wide));   // (the upload's)
        else std::memcpy(img.data(), guest.data(), guest.size());
        const VkFormat view = view_format_of(image, false, false, f, ViewUse::Sample, VK_FORMAT_UNDEFINED);
        CHECK(view == wide && vk_has(view));
        for (int i = 0; i < n; i++, texels++) {
            const Px want = nvn_read(f, guest.data() + (size_t)i * src);
            const Px stored = vk_read(view, img.data() + (size_t)i * out);
            Px got = stored;
            if (alpha_reads_one(f)) got.c[3] = 1;   // (texture_view: the view's swizzle reads alpha as one)
            for (int c = 0; c < 4; c++) {
                if (!same(got.c[c], want.c[c]))
                    std::fprintf(stderr, "texel %d component %d: Vulkan reads %g, NVN %g\n", i, c, got.c[c], want.c[c]);
                CHECK(same(got.c[c], want.c[c]));
            }
            if (from) CHECK(stored.c[3] == 1);   // (widened: the image's own alpha is one)
        }
    }
    // RGB_DXT1: BC1 kept as RGBA_DXT1's format (one image for both), its alpha read as one
    for (int f : {NVN_FORMAT_RGB_DXT1, NVN_FORMAT_RGB_DXT1_SRGB}) {
        at = f;
        const int rgba = f == NVN_FORMAT_RGB_DXT1 ? NVN_FORMAT_RGBA_DXT1 : NVN_FORMAT_RGBA_DXT1_SRGB;
        CHECK(vk_format(f).format == vk_format(rgba).format && is_bc(vk_format(f).format));
        CHECK(alpha_reads_one(f) && !alpha_reads_one(rgba));
        CHECK(view_format_of(image_format_of(vk_format(rgba).format, false), false, false, f, ViewUse::Sample,
                             VK_FORMAT_UNDEFINED) == vk_format(rgba).format);
    }
    std::printf("PASS: %d NVN formats mapped or vertex only, texel sizes as the layout's; %d synthetic texels of %d formats "
                "read as NVN defines them; RGB_DXT1 as RGBA_DXT1 with alpha one\n", (int)(sizeof all / sizeof *all), texels,
                (int)(sizeof gap / sizeof *gap));
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix="nvn-formats-") as tmp:
        cpp, c, obj, exe = (Path(tmp) / n for n in ("fixture.cpp", "layout.c", "layout.o", "fixture.exe"))
        cpp.write_text(fixture, encoding="utf-8")
        c.write_text(layout_c, encoding="utf-8")
        subprocess.run([a.cxx, "-x", "c", "-std=c11", "-Wall", "-Wextra", "-Werror", "-c", str(c), "-o", str(obj)], check=True)
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-I", str(a.headers),
                        "-I", str(ROOT / "gpu/render"), str(cpp), str(obj), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
