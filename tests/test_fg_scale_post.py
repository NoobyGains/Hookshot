"""The FXAA, Bloom and Colour grade rows (gpu/vk/shaders/fg_scale.comp, vk_framegen.cpp framegen_scale), read from the source:
the shader's push constants and the renderer's ScalePush are the same fields in the same order, and the pipelines are made
with ScalePush's size; the rows' names, the looks and the bloom's steps have as many entries as kGrades and kBloomSteps, and
look 0 and bloom 0 leave the picture as it is; none of the three runs on the game's own HDR10 picture (pq); FXAA takes the
window filter's place but not while the loading cover dims the sides; the glow and the grade come after the sharpen and
before the sides. The SPIR-V headers' hash is tests/test_fg_scale_sharpen.py's check. No compiler, no GPU.

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
        for fn, n in (("tx_grade", grades), ("tx_bloom", blooms)):
            names = re.search(r'const char\* %s\(int v\) \{\n    static const char\* t\[\w+\] = \{([^}]*)\}' % fn, self.menu).group(1)
            self.assertEqual(names.count('"') // 2, n, fn)
        self.assertIn('{TAB_GRAPHICS, "FXAA", &opts.fxaa, 0, 1, 1, tx_onoff,', self.menu)
        self.assertIn('{TAB_GRAPHICS, "Bloom", &opts.bloom, 0, kBloomSteps - 1, 1, tx_bloom,', self.menu)
        self.assertIn('{TAB_GRAPHICS, "Colour grade", &opts.grade, 0, kGrades - 1, 1, tx_grade,', self.menu)
        for field in ("int fxaa = 0;", "int bloom = 0;", "int grade = 0;"):
            self.assertIn(field, self.options)

    def test_not_on_pq_and_runs_when_asked(self):
        body = block(self.fg, "VkImage framegen_scale(")
        self.assertIn("const int look = pq ? 0 :", body)
        self.assertIn("const float bloom = pq ? 0.0f :", body)
        self.assertIn("const int fxaa = !pq && opts.fxaa ? 1 : 0;", body)
        early = re.search(r"if \(!window_filter\(\)([^)]*(?:\([^)]*\))?[^)]*)\)\s*return VK_NULL_HANDLE;", body).group(1)
        for wanted in ("!look", "bloom <= 0.0f", "!fxaa"):
            self.assertIn(wanted, early, "the pass is skipped although %s asks for it" % wanted)
        self.assertIn("const bool small_wanted = wide.side == 1 || bloom > 0.0f;", body)
        self.assertIn("{small_wanted ? scale.small.view : src, scale.linear}", body)
        self.assertIn("pc.side = wide.side;", body)

    def test_shader_order(self):
        main = block(self.comp, "void main()")
        self.assertIn("vec3 c = pc.fxaa != 0 && pc.cover <= 0.0 ? fxaa(uv) : filtered(uv);", main)
        order = [main.index(s) for s in ("if (pc.sharp > 0.0)", "if (pc.bloom > 0.0)", "if (pc.look != 0)", "if (outside > 0.0) c = mix(")]
        self.assertEqual(order, sorted(order))
        self.assertIn("return clamp(c, 0.0, 1.0);", block(self.comp, "vec3 grade("))


if __name__ == "__main__":
    unittest.main()
