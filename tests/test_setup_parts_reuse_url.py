"""A reused setup part is served from this repository's builder-parts when that release has the file, and a part whose only
release is gone is an error that names the file to upload (scripts/make_setup_parts.py served_from)

python -I -B tests/test_setup_parts_reuse_url.py
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import make_setup_parts  # noqa: E402

GONE = "https://github.com/NotRexed/Hookshot/releases/download/builder-parts/HookshotBuilder-emsdk-b4c8fc476654.zip"
UP = "https://github.com/notquiteog/Hookshot/releases/download/builder-parts/HookshotBuilder-cpm-6f93a2427b13.zip"
BASE = "https://github.com/NoobyGains/Hookshot/releases/download/builder-parts"
SHA = "b4c8fc476654d7657806180039b3a96050c104cf6a93dab1cc5c027277ece368"


def line(url):
    return "part %s 120100315 . - - %s" % (SHA, url)


class ServedFrom(unittest.TestCase):
    def test_moved_to_base_when_base_has_it(self):
        here = BASE + "/HookshotBuilder-emsdk-b4c8fc476654.zip"
        got = make_setup_parts.served_from(line(GONE), BASE, check=lambda u: u == here)
        self.assertEqual(got, line(here))

    def test_base_preferred_even_when_the_old_one_answers(self):
        here = BASE + "/HookshotBuilder-cpm-6f93a2427b13.zip"
        got = make_setup_parts.served_from(line(UP), BASE, check=lambda u: True)
        self.assertEqual(got.split()[6], here)

    def test_kept_when_only_its_own_release_has_it(self):
        got = make_setup_parts.served_from(line(UP), BASE, check=lambda u: u == UP)
        self.assertEqual(got, line(UP))

    def test_gone_everywhere_is_none(self):
        self.assertIsNone(make_setup_parts.served_from(line(GONE), BASE, check=lambda u: False))

    def test_checksum_and_size_never_change(self):
        here = BASE + "/HookshotBuilder-emsdk-b4c8fc476654.zip"
        got = make_setup_parts.served_from(line(GONE), BASE, check=lambda u: u == here).split()
        self.assertEqual(got[:6], line(GONE).split()[:6])

    def test_main_uses_it_for_reused_parts(self):
        src = (Path(__file__).resolve().parents[1] / "scripts" / "make_setup_parts.py").read_text(encoding="utf-8")
        body = src[src.index("def main():"):]
        self.assertIn("served_from(reuse[name], base)", body)
        self.assertNotIn("lines.append(reuse[name])", body)


if __name__ == "__main__":
    unittest.main()
