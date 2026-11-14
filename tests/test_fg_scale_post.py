"""The FXAA, Bloom, Colour grade and Retro look rows (gpu/vk/shaders/fg_scale.comp, vk_framegen.cpp framegen_scale), read from
the source: the shader's push constants and the renderer's ScalePush are the same fields in the same order, and the pipelines
are made with ScalePush's size; the rows' names, the looks and the bloom's steps have as many entries as kGrades and
kBloomSteps, and look 0 and bloom 0 leave the picture as it is; none of the four runs on the game's own HDR10 picture (pq);
FXAA takes the window filter's place but not while the loading cover dims the sides; the glow and the grade come after the
sharpen and before the sides. The Retro look (Off, N64, N64 + CRT, saved as retro_look) takes the place of the filter and
FXAA, unsharpened, from the small picture made at its 240 lines, with the softer filter across and the scanlines only for
N64 + CRT; its maths are tests/test_fg_scale_retro.py's. The SPIR-V headers' hash is tests/test_fg_scale_sharpen.py's check. No compiler, no GPU.

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
        for words in ("Not with HDR set to Native", "Changes at once", "Window scaling filter, FXAA and Sharpness"):
            self.assertIn(words, re.sub(r'"\s*"', "", row))
        self.assertTrue(row.rstrip("}").rstrip().endswith("nullptr, false, true"), "no restart, preset_exempt")

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
        self.assertTrue(push.rstrip().endswith("fxaa, retro"), push)
        self.assertIn("const uint32_t rh = std::min(source.h, kRetroLines);", body)
        self.assertIn("const uint32_t rw = std::clamp((uint32_t)std::lround((double)rh * dw / dh), 1u, source.w);", body)
        self.assertIn("const uint32_t smw = retro ? rw : std::max(1u, source.w / 8), smh = retro ? rh : std::max(1u, source.h / 8);",
                      body)

    def test_shader_order(self):
        main = block(self.comp, "void main()")
        self.assertIn("vec3 c = pc.retro != 0 ? retro(uv, d) : pc.fxaa != 0 && pc.cover <= 0.0 ? fxaa(uv) : filtered(uv);", main)
        order = [main.index(s) for s in ("if (pc.sharp > 0.0)", "if (pc.bloom > 0.0)", "if (pc.look != 0)", "if (outside > 0.0) c = mix(")]
        self.assertEqual(order, sorted(order))
        self.assertIn("return clamp(c, 0.0, 1.0);", block(self.comp, "vec3 grade("))

    def test_retro_shader(self):
        # (from the small picture, each of its pixels cut to 5 bits with the dither, dimmed first under the loading cover; the
        # scanlines and corners only for N64 + CRT)
        retro = block(self.comp, "vec3 retro(vec2 uv, ivec2 d)")
        self.assertIn("const ivec2 size = textureSize(small, 0);", retro)
        self.assertIn("retro_pixel(b + ivec2(x, y), size)", retro)
        # (N64 with the linear filter, its dither showing; N64 + CRT softer across, as a TV's analog picture was)
        self.assertIn("const float across = pc.retro == 2 ? 1.5 : 1.0;", retro)
        self.assertIn("const float w = max(1.0 - abs(float(x) - f.x) / across, 0.0);", retro)
        crt = retro[retro.index("if (pc.retro == 2)"):]
        self.assertIn("crt_lines(", crt)
        self.assertNotIn("crt_lines(", retro[:retro.index("if (pc.retro == 2)")])
        self.assertIn("return clamp(c, 0.0, 1.0);", retro)
        texel = block(self.comp, "vec3 retro_pixel(")
        self.assertIn("texelFetch(small, t, 0)", texel)
        self.assertLess(texel.index("dimmed(c, 1.0 - pc.cover)"), texel.index("return n64_colour(c, t);"))
        self.assertNotIn("textureLod(src", retro + texel, "the Retro look reads its small picture, not the full one")


if __name__ == "__main__":
    unittest.main()
