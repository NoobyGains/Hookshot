"""The host's log writer, extracted unmodified from host/hos_thread.c, with the CRT stream calls as spies.

stderr is unbuffered, so each line was a write of its own: 30-90 a second in play, each extending the log file, which kept a
slow game disk busy. The writer now waits a little after a line and writes the lines of that time in one write
(HOS_LOG_BATCH_MS, default 250). Checked: the lines of that time go in one write, in order; with no setting a line waits about
250 ms; 0 keeps the old timing; a queue half full goes out without the wait; a way out (log_flush) writes what waits, once.
And log_flush takes the two locks in the writer's order (log_lock, then log_write_lock): the other way round a flush and the
writer could each hold the lock the other waited for, and the game's logging threads stopped with them.
Windows only (SRW locks, threads).

python -I -B tests/test_log_batch.py [--cc gcc] [--source host/hos_thread.c]
"""
import argparse
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

RUN_ALL_ARGS = ["--cc", "gcc"]
RUN_ALL_SKIP = {"linux": "the Windows log writer: SRW locks and threads"}

ROOT = Path(__file__).resolve().parents[1]
# (the batch case on a 1 s wait: its 120 ms of lines and checks stay well inside it on a busy runner)
CASES = {"batch": "1000", "default": None, "off": "0", "burst": "2000", "flush": "2000"}


def log_block(source):
    start_marker = "#if defined(_WIN32) && !defined(__EMSCRIPTEN__)\nstatic SRWLOCK log_lock"
    end_marker = "\n#else\nstatic int log_queue("
    if source.count(start_marker) != 1 or source.count(end_marker) != 1:
        raise SystemExit("FAIL: the Windows log queue block of host/hos_thread.c was not found")
    start = source.index(start_marker) + len("#if defined(_WIN32) && !defined(__EMSCRIPTEN__)\n")
    return source[start:source.index(end_marker)]


def lock_order(source, head):
    """The order a function of the log block first takes log_lock and log_write_lock in"""
    if source.count(head) != 1:
        raise SystemExit("FAIL: %s was not found in host/hos_thread.c" % head.strip())
    body = source[source.index(head):]
    body = body[:body.index("\n}\n")]
    order = []
    for m in re.finditer(r"AcquireSRWLockExclusive\(&(log_lock|log_write_lock)\)", body):
        if m.group(1) not in order:
            order.append(m.group(1))
    return order


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default=os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang") or "gcc")
    p.add_argument("--source", type=Path, default=ROOT / "host/hos_thread.c")
    a = p.parse_args()
    source = a.source.read_text(encoding="utf-8")
    block = log_block(source)
    writer = lock_order(block, "static DWORD WINAPI log_main(void *p) {")
    flush = lock_order(block, "static void log_flush(void) {")
    if writer != ["log_lock", "log_write_lock"] or flush != writer:
        print("FAIL: log_flush takes the locks as %s, the writer as %s: a flush and the writer can wait on each other for good"
              % (" then ".join(flush), " then ".join(writer)))
        return 1
    if os.name != "nt":
        print("skipped: the Windows log writer")
        return 0
    template = (ROOT / "tests/log_batch_test.c").read_text(encoding="utf-8")
    fixture = template.replace("/* ACTUAL_LOG */", block)
    failed = []
    with tempfile.TemporaryDirectory(prefix="hookshot-log-batch-") as temp:
        c_file, exe = Path(temp) / "fixture.c", Path(temp) / "fixture.exe"
        c_file.write_text(fixture, encoding="utf-8")
        cmd = [a.cc, "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror", "-include", str(ROOT / "gpu/vk/compat/hookshot_env.h"),
               str(c_file), "-o", str(exe)]   # (env_on, the switches' rule)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode:
            print(result.stdout + result.stderr)
            return 1
        for case, ms in CASES.items():
            env = {k: v for k, v in os.environ.items() if k not in ("HOS_LOG_BATCH_MS", "HOS_LOG_SYNC")}
            if ms is not None:
                env["HOS_LOG_BATCH_MS"] = ms
            # (each case a fresh process: the writer reads its setting once)
            run = subprocess.run([str(exe), case], capture_output=True, text=True, timeout=30, env=env)
            sys.stdout.write(run.stdout)
            if run.returncode:
                sys.stdout.write(run.stderr)
                failed.append(case)
    if failed:
        print("FAIL: " + ", ".join(failed))
        return 1
    print("all %d cases passed" % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
