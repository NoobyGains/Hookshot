"""The FXAA, Bloom, Colour grade and Retro look rows (gpu/vk/shaders/fg_scale.comp, vk_framegen.cpp framegen_scale), read from
the source: the shader's push constants and the renderer's ScalePush are the same fields in the same order, and the pipelines
are made with ScalePush's size; the rows' names, the looks and the bloom's steps have as many entries as kGrades and
kBloomSteps, and look 0 and bloom 0 leave the picture as it is; none of the four runs on the game's own HDR10 picture (pq);
FXAA takes the window filter's place but not while the loading cover dims the sides; the glow and the grade come after the
sharpen and before the sides. The Retro look (Off, N64, N64 + CRT, saved as retro_look) takes the place of the filter and
FXAA, unsharpened, from the small picture made at its 240 lines: N64 with the linear filter, N64 + CRT through crt(), after
Timothy Lottes' CRT shader. N64 + CRT's five rows (CRT scanlines, mask, mask strength, glow, curvature; saved as crt_...)
follow the Retro look, are shown only with N64 + CRT, keep Lottes' defaults where he has them, and reach the shader cut to
their ranges. Their maths are tests/test_fg_scale_retro.py's; the SPIR-V headers' hash is tests/test_fg_scale_sharpen.py's
check. No compiler, no GPU.

python -I -B tests/test_fg_scale_post.py
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
VK = ROOT / "gpu" / "vk"


def block(text, head):
    """head's body, braces matched"""
    i = text.index(head)
    i = text.index("{", i)
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if not depth:
            return text[i:j + 1]
    raise AssertionError("unbalanced " + head)


def fields(decl):
    """(type, name) of a C declaration list like `int mode; float sharp; float x0, x1;`"""
    out = []
    for part in decl.split(";"):
        part = re.sub(r"//[^\n]*", "", part).strip()
        if not part:
            continue
        kind, names = part.split(None, 1)
        out += [(kind, n.strip()) for n in names.split(",")]
    return out


class PostTests(unittest.TestCase):
    def setUp(self):
        self.comp = (VK / "shaders" / "fg_scale.comp").read_text(encoding="utf-8")
        self.fg = (VK / "vk_framegen.cpp").read_text(encoding="utf-8")
        self.menu = (VK / "vk_menu.cpp").read_text(encoding="utf-8")
        self.options = (VK / "vk_menu.h").read_text(encoding="utf-8")
        self.post = (VK / "fg_scale_post.h").read_text(encoding="utf-8")

    def test_push_constants_match(self):
        glsl = re.search(r"layout\(push_constant\) uniform P \{(.*?)\} pc;", self.comp, re.S).group(1)
        cpp = re.search(r"struct ScalePush \{(.*?)\};", self.post, re.S).group(1)
        self.assertEqual(fields(glsl), fields(cpp))
        self.assertTrue(all(kind in ("int", "float") for kind, _ in fields(cpp)), "4-byte scalars only: no padding")
        self.assertEqual(len(re.findall(r"FG_SCALE(?:_PQ)?_COMP_SPV, sizeof FG_SCALE(?:_PQ)?_COMP_SPV, \{S, I, S\}, sizeof\(ScalePush\)\)",
                                        self.fg)), 2, "both pipelines made with ScalePush's size")
        self.assertIn("ScalePush pc{", block(self.fg, "VkImage framegen_scale("))

    def test_tables(self):
        grades, blooms = (int(x) for x in re.search(r"inline constexpr int kGrades = (\d+), kBloomSteps = (\d+);", self.post).groups())
        looks = re.search(r"constexpr float kGradeLooks\[kGrades\]\[4\] = \{(.*?)\};", self.post, re.S).group(1)
        rows = re.findall(r"\{([^{}]*)\}", looks)
        self.assertEqual(len(rows), grades)
        self.assertEqual([float(v.rstrip("f")) for v in rows[0].split(",")], [1.0, 1.0, 0.0, 0.0], "look 0: the picture untouched")
        levels = re.search(r"constexpr float kBloomLevels\[kBloomSteps\] = \{([^}]*)\};", self.post).group(1).split(",")
        self.assertEqual(len(levels), blooms)
        self.assertEqual(float(levels[0].strip().rstrip("f")), 0.0)
        retros = int(re.search(r"inline constexpr int kRetroLooks = (\d+);", self.post).group(1))
        self.assertEqual(int(re.search(r"inline constexpr unsigned kRetroLines = (\d+);", self.post).group(1)), 240,
                         "the Retro look's picture: the Nintendo 64's 240 lines")
        for fn, n in (("tx_grade", grades), ("tx_bloom", blooms), ("tx_retro", retros)):
            names = re.search(r'const char\* %s\(int v\) \{[^\n]*\n    static const char\* t\[\w+\] = \{([^}]*)\}' % fn,
                              self.menu).group(1)
            self.assertEqual(names.count('"') // 2, n, fn)
        self.assertEqual(re.findall(r'"([^"]*)"', re.search(r"const char\* tx_retro\(int v\) \{[^}]*\}", self.menu).group(0)),
                         ["Off", "N64", "N64 + CRT"])
        self.assertIn('{TAB_GRAPHICS, "FXAA", &opts.fxaa, 0, 1, 1, tx_onoff,', self.menu)
        self.assertIn('{TAB_GRAPHICS, "Bloom", &opts.bloom, 0, kBloomSteps - 1, 1, tx_bloom,', self.menu)
        self.assertIn('{TAB_GRAPHICS, "Colour grade", &opts.grade, 0, kGrades - 1, 1, tx_grade,', self.menu)
        self.assertIn('{TAB_GRAPHICS, "Retro look", &opts.retro, 0, kRetroLooks - 1, 1, tx_retro,', self.menu)
        for field in ("int fxaa = 0;", "int bloom = 0;", "int grade = 0;", "int retro = 0;"):
            self.assertIn(field, self.options)
        # (the Retro look's row: in the Detail section after the Colour grade, its help saying what it replaces and that
        # Native HDR has none; it changes at once and leaves the Quality preset alone, as the three above)
        row = block(self.menu, '{TAB_GRAPHICS, "Retro look"')
        self.assertLess(self.menu.index('{TAB_GRAPHICS, "Colour grade"'), self.menu.index('{TAB_GRAPHICS, "Retro look"'))
        for words in ("Not with HDR set to Native", "Changes at once", "Window scaling filter, FXAA and Sharpness", "CRT rows below"):
            self.assertIn(words, re.sub(r'"\s*"', "", row))
        self.assertTrue(row.rstrip("}").rstrip().endswith("nullptr, false, true"), "no restart, preset_exempt")

    # (N64 + CRT's rows, in this order after the Retro look: field, row, its steps' count, its text, its default)
    CRT_ROWS = (("crt_scanlines", "CRT scanlines", "0, kCrtScans - 1, 1, tx_crt_scanlines", 2),
                ("crt_mask", "CRT mask", "0, kCrtMasks - 1, 1, tx_crt_mask", 1),
                ("crt_mask_strength", "CRT mask strength", "10, 100, 10, tx_percent", 30),
                ("crt_glow", "CRT glow", "0, kCrtGlows - 1, 1, tx_crt_glow", 2),
                ("crt_curvature", "CRT curvature", "0, kCrtCurves - 1, 1, tx_crt_curvature", 1))

    def test_crt_rows(self):
        at = self.menu.index('{TAB_GRAPHICS, "Retro look"')
        for field, name, steps, default in self.CRT_ROWS:
            head = '{TAB_GRAPHICS, "%s", &opts.%s, %s,' % (name, field, steps)
            self.assertIn(head, self.menu)
            self.assertGreater(self.menu.index(head), at, "%s follows the Retro look and the row before it" % name)
            at = self.menu.index(head)
            row = " ".join(block(self.menu, head).split())
            self.assertTrue(row.endswith("nullptr, false, true}"), "%s: no restart, preset_exempt" % name)
            self.assertIn("int %s = %d;" % (field, default), self.options)
        # (the steps: as many names as kCrt*; Lottes' own defaults (hardScan -8, bloomAmount 0.15, warpX 0.031 and warpY 0.041)
        # are the middle steps, Off none)
        counts = dict(zip(("scans", "masks", "glows", "curves"), (int(x) for x in re.search(
            r"inline constexpr int kCrtScans = (\d+), kCrtMasks = (\d+), kCrtGlows = (\d+), kCrtCurves = (\d+);", self.post).groups())))
        names = {fn: re.findall(r'"([^"]*)"', re.search(r"const char\* %s\(int v\) \{[^}]*\}" % fn, self.menu).group(0))
                 for fn in ("tx_crt_scanlines", "tx_crt_mask", "tx_crt_glow", "tx_crt_curvature")}
        self.assertEqual(names["tx_crt_scanlines"], ["Off", "Light", "Medium", "Strong"])
        self.assertEqual(names["tx_crt_mask"], ["Off", "Aperture grille", "Slot mask", "Shadow mask"])
        self.assertEqual(names["tx_crt_glow"], ["Off", "Low", "Medium", "High"])
        self.assertEqual(names["tx_crt_curvature"], ["Off", "Subtle", "Strong"])
        self.assertEqual([len(names[f]) for f in ("tx_crt_scanlines", "tx_crt_mask", "tx_crt_glow", "tx_crt_curvature")],
                         [counts["scans"], counts["masks"], counts["glows"], counts["curves"]])

        def floats(name):
            return [float(v.strip().rstrip("f")) for v in re.findall(r"-?[0-9.]+f", re.search(
                r"constexpr float %s\[[^\]]*\](?:\[\d\])? = \{(.*?)\};" % name, self.post, re.S).group(1))]
        scan, glow, curve = floats("kCrtScan"), floats("kCrtGlow"), floats("kCrtCurve")
        self.assertEqual((len(scan), len(glow), len(curve)), (counts["scans"], counts["glows"], counts["curves"] * 3))
        self.assertEqual((scan[0], scan[2]), (0.0, -8.0))
        self.assertEqual(scan, sorted(scan, reverse=True), "each step harder")
        self.assertEqual((glow[0], glow[2]), (0.0, 0.15))
        self.assertEqual(curve[:3], [0.0, 0.0, 0.0])
        self.assertEqual(curve[6:8], [0.031, 0.041], "Strong: Lottes' warpX and warpY")

    def test_crt_rows_shown_with_n64_crt(self):
        shown = block(self.menu, "bool row_shown(int i)")
        cond = re.search(r"\(\((v != &opts\.crt_scanlines[^)]*)\) \|\| opts\.retro == 2\)", shown)
        self.assertTrue(cond, "row_shown: the CRT rows only with Retro look N64 + CRT")
        self.assertEqual(sorted(re.findall(r"&opts\.(\w+)", cond.group(1))), sorted(f for f, *_ in self.CRT_ROWS))
        keys = block(self.menu, "const char* ini_key(const Row& r)")
        names = [name.lower().replace(" ", "_") for name in re.findall(r'\{TAB_\w+,\s*"([^"]+)",\s*&opts\.\w+', self.menu)]
        for field, *_ in self.CRT_ROWS:
            self.assertNotIn("&opts.%s" % field, keys)
            self.assertEqual(names.count(field), 1, "saved as %s, by ini_key's rule" % field)
        # (framegen_scale pushes them for N64 + CRT only, each cut to its range)
        body = block(self.fg, "VkImage framegen_scale(")
        crt = block(body, "if (retro == 2) {")
        for line in ("pc.scan = kCrtScan[std::clamp(opts.crt_scanlines, 0, kCrtScans - 1)];",
                     "pc.mask = std::clamp(opts.crt_mask, 0, kCrtMasks - 1);",
                     "pc.mask_str = std::clamp(opts.crt_mask_strength, 10, 100) / 100.0f;",
                     "pc.glow = kCrtGlow[std::clamp(opts.crt_glow, 0, kCrtGlows - 1)];",
                     "const int curve = std::clamp(opts.crt_curvature, 0, kCrtCurves - 1);",
                     "pc.warp_x = kCrtCurve[curve][0], pc.warp_y = kCrtCurve[curve][1], pc.corner = kCrtCurve[curve][2];"):
            self.assertIn(line, crt)

    def test_saved_key(self):
        # (hookshot_options.ini's key: ini_key's rule for a row it does not name, the name lower case with _ for spaces)
        keys = block(self.menu, "const char* ini_key(const Row& r)")
        self.assertNotIn("&opts.retro", keys, "the Retro look's key is the rule's, retro_look")
        self.assertIn("k[n++] = *p == ' ' ? '_' : (char)tolower(*p);", keys)
        names = re.findall(r'\{TAB_\w+,\s*"([^"]+)",\s*&opts\.\w+', self.menu)
        made = [name.lower().replace(" ", "_") for name in names]
        self.assertEqual(made.count("retro_look"), 1, "one row saved as retro_look")

    def test_not_on_pq_and_runs_when_asked(self):
        body = block(self.fg, "VkImage framegen_scale(")
        self.assertIn("const int look = pq ? 0 :", body)
        self.assertIn("const float bloom = pq ? 0.0f :", body)
        self.assertIn("const int fxaa = !pq && opts.fxaa ? 1 : 0;", body)
        self.assertIn("const int retro = pq ? 0 : std::clamp(opts.retro, 0, kRetroLooks - 1);", body)
        early = re.search(r"if \(!window_filter\(\)([^)]*(?:\([^)]*\))?[^)]*)\)\s*return VK_NULL_HANDLE;", body).group(1)
        for wanted in ("!look", "bloom <= 0.0f", "!fxaa", "!retro"):
            self.assertIn(wanted, early, "the pass is skipped although %s asks for it" % wanted)
        self.assertIn("const bool small_wanted = wide.side == 1 || bloom > 0.0f || retro;", body)
        self.assertIn("{small_wanted ? scale.small.view : src, scale.linear}", body)
        self.assertIn("pc.side = wide.side;", body)
        # (the Retro look: its sharp 0, the push constants' last field; the small picture its 240 lines, no more than the picture)
        push = re.search(r"ScalePush pc\{(.*?)\};", body, re.S).group(1)
        self.assertIn("retro ? 0.0f : opts.sharpness / 100.0f", push)
        self.assertTrue(" ".join(push.split()).endswith("fxaa, retro, 0.0f, 0, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f"), push)
        self.assertIn("const uint32_t rh = std::min(source.h, kRetroLines);", body)
        self.assertIn("const uint32_t rw = std::clamp((uint32_t)std::lround((double)rh * dw / dh), 1u, source.w);", body)
        self.assertIn("const uint32_t smw = retro ? rw : std::max(1u, source.w / 8), smh = retro ? rh : std::max(1u, source.h / 8);",
                      body)

    # (framegen_scale's early-out terms that are rows of the pass's own, and the option each reads: scale_post_wanted must
    # ask each, or do_present makes no view and the pass never runs on the plain window copy)
    EARLY_OUT_ROWS = {"!look": "opts.grade", "bloom <= 0.0f": "opts.bloom", "!fxaa": "opts.fxaa", "!retro": "opts.retro"}

    def test_view_made_for_the_rows(self):
        replay = (VK / "vk_replay.cpp").read_text(encoding="utf-8")
        at = replay.index("direct_view = texture_view(")
        cond = replay[replay.rindex("if (tex && !dev.offscreen && (", 0, at):at]
        self.assertIn("scale_post_wanted()", cond, "do_present makes the view only for the filter, sharpen, HDR and sides")
        wanted = block(self.fg, "bool scale_post_wanted()")
        body = block(self.fg, "VkImage framegen_scale(")
        early = re.search(r"if \(!window_filter\(\)([^)]*(?:\([^)]*\))?[^)]*)\)\s*return VK_NULL_HANDLE;", body).group(1)
        terms = [t.strip() for t in early.split("&&") if t.strip()]
        for term in terms:
            if term in ("!opts.sharpness", "!wide.side", "!wide.cover"):
                continue   # (the sharpen and the sides: do_present's own terms, opts.sharpness and wide_sides_possible)
            self.assertIn(term, self.EARLY_OUT_ROWS, "a new early-out term: add its option to scale_post_wanted and here")
            self.assertIn(self.EARLY_OUT_ROWS[term], wanted)
        self.assertIn("bool scale_post_wanted();", (VK / "vk_framegen.h").read_text(encoding="utf-8"))

    def test_shader_order(self):
        main = block(self.comp, "void main()")
        self.assertIn("vec3 c = pc.retro == 2 ? crt(uv, g, d) : pc.retro != 0 ? retro(uv) : pc.fxaa != 0 && pc.cover <= 0.0 ? "
                      "fxaa(uv) : filtered(uv);", main)
        order = [main.index(s) for s in ("if (pc.sharp > 0.0)", "if (pc.bloom > 0.0)", "if (pc.look != 0)", "if (outside > 0.0) c = mix(")]
        self.assertEqual(order, sorted(order))
        self.assertIn("return clamp(c, 0.0, 1.0);", block(self.comp, "vec3 grade("))

    def test_retro_shader(self):
        # (from the small picture, each of its pixels cut to 5 bits with the dither, dimmed first under the loading cover. N64:
        # the linear filter over the four nearest, its dither showing)
        retro = block(self.comp, "vec3 retro(vec2 uv)")
        self.assertIn("const ivec2 size = textureSize(small, 0);", retro)
        for tap in ("retro_pixel(b, size)", "retro_pixel(b + ivec2(1, 0), size)", "retro_pixel(b + ivec2(0, 1), size)",
                    "retro_pixel(b + ivec2(1, 1), size)"):
            self.assertIn(tap, retro)
        texel = block(self.comp, "vec3 retro_pixel(")
        self.assertIn("texelFetch(small, t, 0)", texel)
        self.assertLess(texel.index("dimmed(c, 1.0 - pc.cover)"), texel.index("return n64_colour(c, t);"))
        # (N64 + CRT: the same pixels, 3 x 3 nearest, each line a beam, the glow from 4 taps, the mask on the window's pixel g,
        # Lottes' curvature, black outside the curved screen; in light, coded back at the end)
        crt = block(self.comp, "vec3 crt(vec2 uv, ivec2 g, ivec2 d)")
        self.assertIn("for (int j = -1; j <= 1; j++)", crt)
        loop = crt[crt.index("for (int j = -1; j <= 1; j++)"):]
        for tap in ("retro_pixel(t + ivec2(-1, j), size)", "retro_pixel(t + ivec2(0, j), size)", "retro_pixel(t + ivec2(1, j), size)"):
            self.assertIn(tap, loop)
        self.assertEqual(crt.count("retro_pixel("), 3)
        self.assertIn("c += crt_beam(line, f.y - float(j), pc.scan);", crt)
        self.assertEqual(crt.count("textureLod(small,"), 4)
        self.assertIn("if (pc.glow > 0.0)", crt)
        self.assertIn("glow *= 1.0 - pc.cover;", crt)
        self.assertIn("c *= crt_mask(g, pc.mask, pc.mask_str);", crt)
        self.assertIn("w *= vec2(1.0 + w.y * w.y * pc.warp_x, 1.0 + w.x * w.x * pc.warp_y);", crt)
        self.assertIn("if (inside <= 0.0) return vec3(0.0);", crt)
        self.assertIn("return crt_code(", crt)
        self.assertLess(crt.index("crt_mask("), crt.index("return crt_code("))
        self.assertNotIn("textureLod(src", retro + texel + crt, "the Retro look reads its small picture, not the full one")


if __name__ == "__main__":
    unittest.main()
