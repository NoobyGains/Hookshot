"""Pair the real program-life clock with the host clock once; no game or GPU."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
from pathlib import Path
import runpy
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif
bool enabled;
int env_reads, host_reads, life_reads, logs;
std::vector<int> order;
std::string line;
std::atomic<bool> programs_life_flag{false};
bool env_on(const char*) { env_reads++; return enabled; }
int64_t now_ns() { life_reads++; order.push_back(1); return 12345678901LL; }
int64_t host_now_ns() {
    order.push_back(host_reads ? 2 : 0);
    return 9007199254740993LL + 200 * host_reads++;
}
struct Host { int64_t (*now_ns)(); } value{host_now_ns};
Host* host;
void logf(const char* fmt, ...) {
    order.push_back(3); logs++;
    char text[512];
    va_list args; va_start(args, fmt);
    std::vsnprintf(text, sizeof text, fmt, args); va_end(args);
    line = text;
}
@BODY@
int main(int argc, char** argv) {
#ifdef _WIN32
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
#endif
    if (argc != 2) return 2;
    const bool before_init = std::strcmp(argv[1], "before-init") == 0;
    enabled = before_init || std::strcmp(argv[1], "on") == 0;
    host = before_init ? nullptr : &value;
    if (before_init) {
        for (int i = 0; i < 8; i++)
            if (programs_life_on() || programs_life_flag || env_reads || host_reads || life_reads || logs) return 7;
        host = &value; // A premature census must not cache logging off for a later valid initialization.
    }
    for (int i = 0; i < 8; i++)
        if (programs_life_on() != enabled || programs_life_flag != enabled) return 3;
    if (env_reads != 1 || host_reads != (enabled ? 2 : 0) || life_reads != (enabled ? 1 : 0) || logs != (enabled ? 1 : 0)) {
        std::fputs("clock anchor: wrong once/off call counts\n", stderr); return 4;
    }
    if (enabled && (order != std::vector<int>{0, 1, 2, 3} || line !=
        "vk: program life: clock host_before_ns 9007199254740993 life_ns 12345678901 host_after_ns 9007199254741193")) {
        std::fputs("clock anchor: wrong bracket order or integer timestamps\n", stderr); return 5;
    }
    if (!enabled && (!order.empty() || !line.empty())) return 6;
    std::printf("PASS clock anchor %s\n", argv[1]);
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--source", type=Path, default=ROOT / "gpu/vk/vk_programs.cpp")
    args = parser.parse_args()
    block = runpy.run_path(str(ROOT / "tests/test_frame_trace_waits.py"))["block"]
    body = block(args.source.read_text(encoding="utf-8"), "bool programs_life_on()")
    with tempfile.TemporaryDirectory(prefix="program-life-clock-") as tmp:
        cpp, exe = Path(tmp) / "check.cpp", Path(tmp) / "check.exe"
        cpp.write_text(FIXTURE.replace("@BODY@", body), encoding="utf-8")
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)],
                       check=True, timeout=120)
        for mode in ("off", "on", "before-init"):
            result = subprocess.run([str(exe), mode], capture_output=True, text=True, timeout=10)
            if result.returncode or f"PASS clock anchor {mode}" not in result.stdout:
                raise SystemExit(result.stderr or result.stdout or "clock fixture failed")
            print(result.stdout.strip())


if __name__ == "__main__":
    main()
