"""The control bridge (host/control.c) against a fake game, over its real transport: tests/control_test.c is built with
host/control.c (HOS_CONTROL_NO_GAME: no game behind it) and drives it as a client. Valid commands, malformed JSON, unknown
commands, oversized lines, clients that disconnect mid-command or never read, too many clients, the socket's mode, a file
in the way (Linux) or the pipe's name and DACL (Windows), quit (on Linux also with the bridge slow to listen,
and with a check failing while the forked bridge serves), and guest memory at each HOS_CONTROL_MEM level. Linux
drives the Unix socket, Windows the named pipe.

python -I -B tests/test_control.py [--cc gcc] [--source-root OTHER_CHECKOUT]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cc", "gcc"]

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    p.add_argument("--source-root", type=Path, default=ROOT, help="compile the bridge and its header from this checkout")
    a = p.parse_args()
    windows = os.name == "nt"
    # (Linux: a short folder, a Unix socket's path is at most 107 bytes: the temporary folder ($TMPDIR) when it is short
    # enough, else /tmp. Windows: the pipes are named after the process)
    short = windows or len(tempfile.gettempdir()) <= 48 or not os.path.isdir("/tmp")
    with tempfile.TemporaryDirectory(prefix="ctl-", dir=None if short else "/tmp") as tmp:
        exe = os.path.join(tmp, "control_test.exe" if windows else "control_test")
        libs = ["-ladvapi32"] if windows else ["-lpthread", "-lm"]
        warnings = ["-Wno-format-truncation"] if "clang" not in Path(a.cc).name else []
        subprocess.run([a.cc, "-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror", "-Wno-missing-field-initializers",
                        "-D_GNU_SOURCE", "-D_CRT_SECURE_NO_WARNINGS", "-DHOS_CONTROL_NO_GAME", "-I", str(a.source_root / "host"),
                        str(ROOT / "tests" / "control_test.c"), str(a.source_root / "host" / "control.c"), "-o", exe]
                       + warnings + libs, check=True)
        # (the general cases, quit, the level unit, and the memory cases at each HOS_CONTROL_MEM level. POSIX, quit's
        # races too: its bridge slow to listen once the socket's file is there, and a check failing once the child serves)
        runs = [([], None), (["quit"], None), (["level"], None),
                (["mem"], None), (["mem"], "ro"), (["mem"], "rw"), (["mem"], "bogus")]
        if not windows:
            runs[2:2] = [(["quit", "slow"], None), (["quit", "fail"], None)]
        for case, mem in runs:
            folder = tempfile.mkdtemp(dir=tmp)
            env = dict(os.environ)
            env.pop("HOS_CONTROL_MEM", None)
            if mem is not None:
                env["HOS_CONTROL_MEM"] = mem
            r = subprocess.run([exe, folder] + case, capture_output=True, text=True, timeout=180, env=env)
            if case == ["quit", "fail"]:   # (its 1, and its output's end: the child, which holds that output too, ended)
                if r.returncode != 1 or "a failure injected" not in r.stderr:
                    print(r.stderr, end="", file=sys.stderr)
                    print("FAIL: control_test quit fail exited %d, not 1 with the injected failure" % r.returncode,
                          file=sys.stderr)
                    return 1
                print("PASS: quit: a check failing once the child serves ends the child with it")
                continue
            print(r.stdout, end="")
            print(r.stderr, end="", file=sys.stderr)
            if r.returncode:
                label = " ".join(case) or "(the cases)"
                print("FAIL: control_test %s%s exited %d" % (label, " HOS_CONTROL_MEM=%s" % mem if mem else "", r.returncode),
                      file=sys.stderr)
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
