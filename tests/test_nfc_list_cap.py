"""The NFC folder's list holds the first 256 tag files by name, whatever order the folder gives its files in.

host/nn_nfp.c add_file stopped taking files at NFC_MAX while the folder was still being read, and list_files sorted after
that: past 256 files the menu had whichever 256 the folder gave first, not the first by name, and the launcher's NFC page
could not say which the game would list. add_file now keeps the first NFC_MAX by name as the files come.

tag_ending, by_name and add_file are compiled as they are in the source and fed 300 names in three orders (as sorted, the
other way round, shuffled), with a key file, a file that is no tag's and names that differ only by the letters' case
among them: the list, sorted as list_files sorts it, is the first 256 by name each time, and the same 256.
python -I -B tests/test_nfc_list_cap.py   (needs a C compiler)
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r"""
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NFC_MAX 256
typedef struct {
    char name[128];
    char path[600];
} NfcFile;
static NfcFile nfc_files[NFC_MAX];
static int nfc_n;
/* CUT */
static const char *name_of(int i, char *b, size_t n) {
    /* (300 names: two that differ only by case, the rest in order) */
    if (i == 7) snprintf(b, n, "TAG 0150.bin");
    else if (i == 8) snprintf(b, n, "tag 0150.bin");
    else snprintf(b, n, "Tag %04d.%s", i, i % 3 ? "bin" : "NFC");
    return b;
}
static void fill(int order) {
    static int at[300];
    for (int i = 0; i < 300; i++) at[i] = order == 1 ? 299 - i : i;
    if (order == 2) {
        unsigned seed = 12345;
        for (int i = 299; i > 0; i--) {
            seed = seed * 1103515245u + 12345u;
            const int j = (int)((seed >> 8) % (unsigned)(i + 1)), t = at[i];
            at[i] = at[j], at[j] = t;
        }
    }
    nfc_n = 0;
    add_file("dir", "key_retail.bin");
    add_file("dir", "notes.txt");
    for (int i = 0; i < 300; i++) {
        char b[64];
        add_file("dir", name_of(at[i], b, sizeof b));
    }
    add_file("dir", "KEY_other.BIN");
    qsort(nfc_files, (size_t)nfc_n, sizeof nfc_files[0], by_name);
}
int main(void) {
    static NfcFile first[NFC_MAX], all[300];
    int fails = 0;
    /* what the list should be: all 300 sorted, the first 256 */
    for (int i = 0; i < 300; i++) {
        char b[64];
        name_of(i, b, sizeof b);
        snprintf(all[i].name, sizeof all[i].name, "%.*s", (int)strlen(b) - 4, b);
    }
    qsort(all, 300, sizeof all[0], by_name);
    for (int order = 0; order < 3; order++) {
        fill(order);
        if (nfc_n != NFC_MAX) printf("FAIL order %d: %d listed\n", order, nfc_n), fails++;
        for (int i = 0; i < nfc_n && i < NFC_MAX; i++)
            if (strcmp(nfc_files[i].name, all[i].name)) {
                printf("FAIL order %d: place %d is \"%s\", not \"%s\"\n", order, i, nfc_files[i].name, all[i].name), fails++;
                break;
            }
        if (order == 0) memcpy(first, nfc_files, sizeof first);
        else
            for (int i = 0; i < NFC_MAX; i++)
                if (strcmp(first[i].name, nfc_files[i].name) || strcmp(first[i].path, nfc_files[i].path)) {
                    printf("FAIL order %d: place %d is another file than as sorted\n", order, i), fails++;
                    break;
                }
        for (int i = 0; i < nfc_n; i++)
            if (!strncmp(nfc_files[i].path, "dir", 3) && strstr(nfc_files[i].path, "key_")) printf("FAIL: a key file listed\n"), fails++;
    }
    if (!fails) puts("PASS");
    return fails != 0;
}
"""


def cut(source, start, end):
    a = source.index(start)
    return source[a:source.index(end, a)]


class NfcListCap(unittest.TestCase):
    def test_first_256_by_name(self):
        cc = shutil.which("gcc") or shutil.which("clang")
        if not cc:
            self.skipTest("no C compiler")
        src = (ROOT / "host" / "nn_nfp.c").read_text(encoding="utf-8")
        self.assertIn("#define NFC_MAX 256", src)
        code = cut(src, "static int tag_ending(const char *name) {", "/* The folder listed again, at most once a second (nfc_lk held) */")
        with tempfile.TemporaryDirectory(prefix="hookshot-nfc-cap-") as tmp:
            tmp = Path(tmp)
            (tmp / "t.c").write_text(FIXTURE.replace("/* CUT */", code), encoding="utf-8")
            binary = tmp / ("t.exe" if sys.platform == "win32" else "t")
            build = subprocess.run([cc, "-std=gnu11", "-Wall", "-Werror", str(tmp / "t.c"), "-o", str(binary)], text=True, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_the_folder_is_sorted_after_it_is_read(self):
        src = (ROOT / "host" / "nn_nfp.c").read_text(encoding="utf-8")
        listing = cut(src, "static void list_files(void) {", "/* A tag's bytes from its file")
        self.assertIn("qsort(nfc_files, (size_t)nfc_n, sizeof nfc_files[0], by_name);", listing)
        add = cut(src, "static void add_file(const char *dir, const char *name) {", "/* The folder listed again")
        self.assertNotIn("nfc_n >= NFC_MAX", add, "add_file: full, it no longer just stops (the first by name are kept)")


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=1))
