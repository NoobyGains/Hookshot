"""Game-free: host/mods.c's mod list for the Insert menu's Mods page, on made-up folders and files (no game data).

The player turns mods on and off and sets their load order in the menu, which keeps the choice in mods/hookshot-mods.ini
instead of renaming the player's folders. host/mods.c as it is, over real folders, with a harness that prints what the menu is
given (hos_mods_info, hos_mods_shared), routes files (hos_mods_romfs) and saves a choice (hos_mods_save):

- without the file: every mod on, in name order (the one that sorts last wins a file both have, as before); mods in a folder
  named with '-' or '_' listed last, off, the existing log lines kept, and one line a mod (place, on or off, files);
- the file's parsing: a BOM, CRLF, comments, blank lines, names in any case and with '\\', a name alone (on), a value that is
  none of on/off (part of the name), a name given twice (the first counts), a line for a folder that is not there (kept, and
  logged), a line for a folder off by its name (no say);
- the order: the file's mods first in its order, then the others by name, the renamed ones last; a later mod wins a shared
  file, an off one serves nothing;
- the files two mods both have (on or off), and a log line for two mods on that share files;
- hos_mods_save: the file it writes (its header, the lines in the order given, kept lines after), read back at the next start
  as written; a list that is not every mod once refused with the file left as it was; no part file left behind; names that
  start with ';' (written after "./") and names holding '=' round-trip;
- no mods folder, and an empty one.

python -I -B tests/test_mods_list.py [--cc gcc]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]

HEADER = ("; Hookshot's mod list. The Insert menu's Mods page (Gameplay, Mods) writes it; edit it with the game closed.\n"
          "; A line a mod: its folder in the mods folder ('/' between folders), then = on or = off.\n"
          "; The lines are the load order: when two mods have the same file, the one lower down wins.\n"
          "; Mods not named here load after these, in name order. A folder whose name starts with - or _ stays off.\n")

HARNESS = r'''#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void hos_log(const char *f, ...) { va_list ap; va_start(ap, f); printf("log: "); vprintf(f, ap); printf("\n"); va_end(ap); }
int hos_prompts_romfs(const char *key, const char *mod, char *out, size_t cap) { (void)key, (void)mod, (void)out, (void)cap; return 0; }
void hos_mods_init(const char *image_path);
int hos_mods_romfs(const char *rel, char *out, size_t cap);
int hos_mods_info(int index, const char **name, int *on, int *files, int *renamed, int *exefs);
int hos_mods_shared(int a, int b);
int hos_mods_save(const int *order, const int *on, int n);
static int list(const char *s, int *out) {   /* "2,0,1" */
    int n = 0;
    for (char *end; *s; s = *end ? end + 1 : end) out[n++] = (int)strtol(s, &end, 10);
    return n;
}
int main(int argc, char **argv) {
    hos_mods_init(NULL);
    const char *name;
    int on, files, renamed, exefs, n = 0;
    for (; hos_mods_info(n, &name, &on, &files, &renamed, &exefs); n++)
        printf("mod %d|%s|%d|%d|%d|%d\n", n, name, on, files, renamed, exefs);
    for (int a = 0; a < n; a++)
        for (int b = 0; b < n; b++)
            if (hos_mods_shared(a, b) != hos_mods_shared(b, a)) printf("asymmetric %d %d\n", a, b);
            else if (a < b && hos_mods_shared(a, b)) printf("shared %d %d %d\n", a, b, hos_mods_shared(a, b));
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "save") && i + 2 < argc) {
            int order[64], ons[64];
            const int k = list(argv[i + 1], order), m = list(argv[i + 2], ons);
            printf("saved %d\n", k == m ? hos_mods_save(order, ons, k) : -1);
            i += 2;
            continue;
        }
        char out[4096] = "";
        printf("open %s|%s\n", argv[i], hos_mods_romfs(argv[i], out, sizeof out) ? out : "(the game's)");
    }
    return 0;
}
'''

# host/posix's file calls, for Linux (as tests/test_mods_size_table.py takes them)
POSIX_PIECES = ["static DWORD error_of(int e) {", "static void slashes(char *dst, size_t cap, const char *src) {",
                "DWORD GetFileAttributesA(LPCSTR name) {", "static BOOL find_next(HFind *f, WIN32_FIND_DATAA *fd) {",
                "HANDLE FindFirstFileA(LPCSTR pattern, WIN32_FIND_DATAA *fd) {",
                "BOOL FindNextFileA(HANDLE h, WIN32_FIND_DATAA *fd) {", "BOOL FindClose(HANDLE h) {",
                "BOOL MoveFileExA(LPCSTR from, LPCSTR to, DWORD flags) {"]


def check(cond, what):
    if not cond:
        raise SystemExit("FAIL: " + what)


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def build(cc, tmp, host):
    src = tmp / "src"
    src.mkdir()
    (src / "mods.c").write_bytes((host / "mods.c").read_bytes())   # (beside a hos.h of the test's: hos_log)
    (src / "hos.h").write_text("#pragma once\n#include <stddef.h>\n#include <stdint.h>\nvoid hos_log(const char *f, ...);\n",
                               encoding="utf-8")
    (tmp / "main.c").write_text(HARNESS, encoding="utf-8")
    exe = tmp / ("fixture.exe" if os.name == "nt" else "fixture")
    args = [cc, "-std=gnu11", "-Wall", "-Wextra", "-Wno-unused-function",
            "-Wno-format-truncation", "-I", str(host)]   # (MAX_PATH snprintf's, as mods.c always had)
    sources = [str(src / "mods.c"), str(tmp / "main.c")]
    if os.name == "nt":
        args.append("-Werror")   # (Linux: host/posix's stand-ins come in with mods.c, and are not this check's)
    else:
        posix = (host / "posix/win32_posix.c").read_text(encoding="utf-8")
        pieces = [block(posix, m) for m in POSIX_PIECES]
        pieces.insert(1, "static BOOL fail_errno(void) { last_error = error_of(errno); return FALSE; }\n"
                         "enum { H_THREAD = 0x48540001, H_EVENT, H_SEMA, H_TIMER, H_FILE, H_FIND };\n"
                         "typedef struct { int type; } HObj;\n"
                         "static int is(HANDLE h, int type) { return h && h != INVALID_HANDLE_VALUE && (uintptr_t)h > 0x10000 && "
                         "((HObj *)h)->type == type; }")
        pieces.insert(4, "typedef struct { HObj h; DIR *d; char dir[PATH_MAX], pat[256]; } HFind;")
        (tmp / "posix.c").write_text("#include <windows.h>\n#include <dirent.h>\n#include <errno.h>\n#include <fnmatch.h>\n"
                                     "#include <limits.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                                     "#include <string.h>\n#include <sys/stat.h>\n#include <unistd.h>\n"
                                     "static DWORD last_error;\n" + "\n".join(pieces) + "\n"
                                     "DWORD GetModuleFileNameA(HMODULE m, LPSTR out, DWORD cap) { (void)m; "
                                     "return (DWORD)snprintf(out, cap, \"/nonexistent/hookshot\"); }\n", encoding="utf-8")
        args += ["-D_GNU_SOURCE", "-I", str(host / "posix"), "-Wno-unused-parameter"]
        sources.append(str(tmp / "posix.c"))
    subprocess.run(args + sources + ["-o", str(exe)], check=True)
    return exe


class Fixture:
    def __init__(self, exe, top):
        self.exe, self.top = exe, top
        self.mods = top / "mods"

    def make(self, tree):
        """tree: {"mod/romfs/a.txt": "content", "folder/": None}"""
        for rel, data in tree.items():
            p = self.mods / rel
            if data is None:
                p.mkdir(parents=True, exist_ok=True)
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data, encoding="utf-8")

    def ini(self, data):
        (self.mods / "hookshot-mods.ini").write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def run(self, *args, mods=None):
        env = dict(os.environ, HOS_MODS=str(mods or self.mods))
        out = subprocess.run([str(self.exe), *args], env=env, check=True, capture_output=True, text=True, timeout=60,
                             encoding="utf-8").stdout
        r = {"mods": [], "shared": {}, "open": {}, "log": [], "saved": None}
        for line in out.splitlines():
            if line.startswith("mod "):
                i, name, on, files, renamed, exefs = line[4:].split("|")
                r["mods"].append((name, int(on), int(files), int(renamed), int(exefs)))
            elif line.startswith("shared "):
                a, b, n = map(int, line[7:].split())
                r["shared"][(r["mods"][a][0], r["mods"][b][0])] = n
            elif line.startswith("open "):
                rel, _, what = line[5:].partition("|")
                what = what.replace("\\", "/")
                r["open"][rel] = what if what == "(the game's)" else os.path.relpath(what, self.mods).replace("\\", "/").split("/romfs/")[0]
            elif line.startswith("log: "):
                r["log"].append(line[5:].replace("\\", "/"))
            elif line.startswith("saved "):
                r["saved"] = int(line[6:])
            else:
                raise SystemExit("FAIL: the harness said %r" % line)
        return r


TREE = {
    "b-mod/romfs/ui/SHARED.TXT": "b's shared",   # (the same file as a-mod's UI/shared.txt: keys are lower case)
    "b-mod/romfs/UI/b.txt": "b",
    "a-mod/romfs/UI/shared.txt": "a's shared",
    "a-mod/romfs/a.txt": "a",
    "_off/romfs/x.txt": "off by its name",
    "-off2/romfs/y.txt": "off by its name too",
    "contents/0100/deep/romfs/d.txt": "deep",
    "notamod/x/file.txt": "not a mod: no romfs or exefs",
    "_old/inner/romfs/z.txt": "a mod in a folder off by its name",
    "exe-only/exefs/main.ips": "exefs only",
}


def names(r):
    return [m[0] for m in r["mods"]]


def no_ini(fx):
    r = fx.run("UI/shared.txt", "a.txt", "UI/b.txt", "x.txt", "z.txt", "d.txt")
    check(names(r) == ["a-mod", "b-mod", "contents/0100/deep", "exe-only", "-off2", "_off", "_old/inner"],
          "no file: the order is not the names', the renamed last: %s" % names(r))
    check(r["mods"][0] == ("a-mod", 1, 2, 0, 0) and r["mods"][1] == ("b-mod", 1, 2, 0, 0) and
          r["mods"][2] == ("contents/0100/deep", 1, 1, 0, 0) and r["mods"][3] == ("exe-only", 1, 0, 0, 1),
          "no file: the mods on, their files and exefs: %s" % r["mods"])
    check(r["mods"][4:] == [("-off2", 0, 1, 1, 0), ("_off", 0, 1, 1, 0), ("_old/inner", 0, 1, 1, 0)],
          "the folders off by their names: listed, off, their files counted: %s" % r["mods"][4:])
    check(r["open"] == {"UI/shared.txt": "b-mod", "a.txt": "a-mod", "UI/b.txt": "b-mod", "x.txt": "(the game's)",
                        "z.txt": "(the game's)", "d.txt": "contents/0100/deep"},
          "no file: the one that sorts last wins, an off mod serves nothing: %s" % r["open"])
    check(r["shared"] == {("a-mod", "b-mod"): 1}, "the files two mods both have: %s" % r["shared"])
    log = r["log"]
    root = str(fx.mods).replace("\\", "/")
    for line in ("%s/_off is off (its name starts with _)" % root, "%s/-off2 is off (its name starts with -)" % root,
                 "%s/_old is off (its name starts with _)" % root,
                 "exe-only: exefs patches are left out (the code is compiled ahead of time)",
                 "a-mod: 2 RomFS files", "b-mod: 2 RomFS files", "4 mods from %s: 5 RomFS entries" % root,
                 "#1 a-mod: on, 2 RomFS files", "#2 b-mod: on, 2 RomFS files", "#3 contents/0100/deep: on, 1 RomFS files",
                 "#4 exe-only: on, 0 RomFS files", "-off2: off (its folder's name starts with - or _), 1 RomFS files",
                 "_old/inner: off (its folder's name starts with - or _), 1 RomFS files",
                 "a-mod and b-mod have 1 files in common: b-mod's load (it comes later)"):
        check("mods: " + line in log, "no file: the log has no line %r:\n%s" % (line, "\n".join(log)))
    check(not any("hookshot-mods.ini" in l for l in log), "no file, but the log names it")
    check(not any("_old/inner is off" in l for l in log), "a folder inside one off by its name logged as off itself")


def with_ini(fx):
    fx.ini(b"\xef\xbb\xbf; my list\r\n\r\n  B-MOD = on \r\na-mod=off\r\nmissing/mod = off\r\ncontents\\0100\\deep\r\n"
           b"a-mod = on\r\n_off = on\r\n")
    r = fx.run("UI/shared.txt", "a.txt", "x.txt")
    check(names(r) == ["b-mod", "a-mod", "contents/0100/deep", "exe-only", "-off2", "_off", "_old/inner"],
          "the file's order, then the others by name: %s" % names(r))
    check([m[1] for m in r["mods"]] == [1, 0, 1, 1, 0, 0, 0], "on and off as the file says: %s" % r["mods"])
    check(r["open"] == {"UI/shared.txt": "b-mod", "a.txt": "(the game's)", "x.txt": "(the game's)"},
          "an off mod serves nothing, a renamed one stays off whatever the file says: %s" % r["open"])
    check(r["shared"] == {("b-mod", "a-mod"): 1}, "the files shared, an off mod's too: %s" % r["shared"])
    log = r["log"]
    for line in ("hookshot-mods.ini names missing/mod, which is not in the mods folder: kept for when it is back",
                 "hookshot-mods.ini: 5 mods named, 2 of them off", "#1 b-mod: on, 2 RomFS files",
                 "#2 a-mod: off (hookshot-mods.ini), 2 RomFS files", "3 mods from %s: 4 RomFS entries" % str(fx.mods).replace("\\", "/")):
        check("mods: " + line in log, "with the file: the log has no line %r:\n%s" % (line, "\n".join(log)))
    check(not any("names _off" in l for l in log), "a line for a folder off by its name logged as missing")
    check(not any("in common" in l for l in log), "a conflict logged with one of the two off")
    check(not any(l.startswith("a-mod: ") for l in log), "an off mod's files logged as loaded")
    # the order turned round: a-mod later, so its file wins
    fx.ini("b-mod = on\na-mod = on\n")
    r = fx.run("UI/shared.txt", "UI/b.txt")
    check(names(r)[:2] == ["b-mod", "a-mod"] and r["open"] == {"UI/shared.txt": "a-mod", "UI/b.txt": "b-mod"},
          "the later mod in the file's order wins: %s %s" % (names(r), r["open"]))
    check("mods: b-mod and a-mod have 1 files in common: a-mod's load (it comes later)" in r["log"], "\n".join(r["log"]))
    # values: yes/no/1/0/true/false, any case; a value that is none of them is part of the name (a bare name: on)
    fx.ini("a-mod = NO\nb-mod=0\ncontents/0100/deep = True\nexe-only = maybe\n")
    r = fx.run()
    check([m[1] for m in r["mods"][:4]] == [0, 0, 1, 1] and names(r)[:4] == ["a-mod", "b-mod", "contents/0100/deep", "exe-only"],
          "values and an unknown one: %s" % r["mods"])
    check("mods: hookshot-mods.ini names exe-only = maybe, which is not in the mods folder: kept for when it is back" in r["log"],
          "an unknown value is not taken as the name's: %s" % r["log"])


def saving(fx):
    fx.ini("B-MOD = on\na-mod = off\nmissing/mod = off\ncontents/0100/deep\n_off = on\n")
    before = (fx.mods / "hookshot-mods.ini").read_bytes()
    r = fx.run()
    check(names(r)[:4] == ["b-mod", "a-mod", "contents/0100/deep", "exe-only"], "before saving: %s" % names(r))
    # not every mod once: refused, the file as it was
    for order, on in (("0,0,1,2", "1,1,1,1"), ("0,1", "1,1"), ("0,1,2,4", "1,1,1,1"), ("0,1,2,-1", "1,1,1,1"),
                      ("0,1,2,3,4", "1,1,1,1,1")):
        r = fx.run("save", order, on)
        check(r["saved"] == 0, "save %s %s was taken" % (order, on))
        check((fx.mods / "hookshot-mods.ini").read_bytes() == before, "a refused save changed the file")
    # exe-only first, a-mod on, b-mod off: the menu's choice
    r = fx.run("save", "3,1,0,2", "1,1,0,1")
    check(r["saved"] == 1, "a save was refused: %s" % r["log"])
    text = (fx.mods / "hookshot-mods.ini").read_text(encoding="utf-8")
    want = HEADER + ("exe-only = on\na-mod = on\nB-MOD = off\ncontents/0100/deep = on\n"
                     "; Not in the mods folder now, kept for when they are back:\nmissing/mod = off\n_off = on\n")
    want = want.replace("B-MOD", "b-mod")   # (the folder's own name, not the file's spelling)
    check(text == want, "the file written:\n%s\nnot:\n%s" % (text, want))
    check("mods: hookshot-mods.ini written for the next start: 4 mods, 1 of them off" in r["log"], "\n".join(r["log"]))
    check(not any(p.name.endswith(".new") for p in fx.mods.iterdir()), "a part file was left behind")
    # this run's list is this run's: the save is for the next start
    check(names(r)[:4] == ["b-mod", "a-mod", "contents/0100/deep", "exe-only"], "the save changed this run's list")
    # the next start reads it back as written
    r = fx.run("UI/shared.txt")
    check(names(r)[:4] == ["exe-only", "a-mod", "b-mod", "contents/0100/deep"] and [m[1] for m in r["mods"][:4]] == [1, 1, 0, 1],
          "the next start's list: %s" % r["mods"])
    check(r["open"] == {"UI/shared.txt": "a-mod"}, "the next start's files: %s" % r["open"])


def odd_names(fx):
    fx.make({";semi/romfs/s.txt": "s", "a=b/romfs/e.txt": "e"})
    if os.name != "nt":   # (a name starting with a space: Linux only, Windows' shell trims them)
        fx.make({" lead/romfs/l.txt": "l"})
    r = fx.run()
    n = len(r["mods"])
    want = ([" lead"] if os.name != "nt" else []) + [";semi", "a=b"]
    check(names(r) == want, "odd names, in name order: %s" % names(r))
    order = ",".join(str(i) for i in reversed(range(n)))
    on = ",".join("0" if i == 0 else "1" for i in range(n))
    r = fx.run("save", order, on)
    check(r["saved"] == 1, "odd names: not saved: %s" % r["log"])
    text = (fx.mods / "hookshot-mods.ini").read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if not l.startswith(";")]
    want_lines = ["a=b = off", "./;semi = on"] + (["./ lead = on"] if os.name != "nt" else [])
    check(lines == want_lines, "odd names written as %s" % lines)
    r = fx.run("e.txt", "s.txt")
    check(names(r) == list(reversed(want)) and [m[1] for m in r["mods"]] == [0] + [1] * (n - 1),
          "odd names read back: %s" % r["mods"])
    check(r["open"] == {"e.txt": "(the game's)", "s.txt": ";semi"}, "odd names' files: %s" % r["open"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    p.add_argument("--source", type=Path, default=ROOT / "host", help="host source directory to exercise")
    a = p.parse_args()
    if not shutil.which(a.cc):
        raise SystemExit("SKIP: no %s" % a.cc)
    with tempfile.TemporaryDirectory(prefix="mods-list-") as tmp:
        tmp = Path(tmp)
        exe = build(a.cc, tmp, a.source)
        for i, case in enumerate((no_ini, with_ini, saving)):
            top = tmp / ("case%d" % i)
            fx = Fixture(exe, top)
            fx.make(TREE)
            case(fx)
        fx = Fixture(exe, tmp / "odd")
        fx.mods.mkdir(parents=True)
        odd_names(fx)
        # no mods folder: nothing, not even a line; an empty one: "none"
        fx = Fixture(exe, tmp / "none")
        r = fx.run("a.txt")
        check(r["mods"] == [] and r["log"] == [] and r["open"] == {"a.txt": "(the game's)"}, "no mods folder: %s" % r)
        fx.mods.mkdir(parents=True)
        r = fx.run("save", "0", "1")
        check(r["mods"] == [] and r["saved"] == 0 and len(r["log"]) == 1 and r["log"][0].startswith("mods: none in "),
              "an empty mods folder: %s" % r)
        check(not (fx.mods / "hookshot-mods.ini").exists(), "a save with no mods wrote the file")
    print("ok: the mod list without and with hookshot-mods.ini (its parsing, order, off mods, renamed folders), the files "
          "two mods share, the log's lines, hos_mods_save's file and its refusals, odd names, no and an empty mods folder")


if __name__ == "__main__":
    main()
