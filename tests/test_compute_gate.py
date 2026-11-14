# SPDX-License-Identifier: GPL-3.0-or-later
"""How many of the GPU driver's compute compiles run at once (gpu/vk/compute_gate.h, used by gpu/vk/vk_draw.cpp).

The shader preparation ran one driver compile on every worker: half the CPUs in its first part, 16 in the warm, every CPU in
the precompile. Mesa's Intel driver holds gigabytes while it compiles one of the game's large compute programs, so on an
Iris Xe PC with 32 GB the preparation was killed for memory, in the build's last step and at every start of the game. The
gate lets one compile start at once, and one more only while the weights of those running and its own (a compile held to 32
lanes weighs more) fit in what was available, and its weight is available now.

Compile and run the rule and the gate (tests/compute_gate_test.cpp): the budget the available memory gives, one compile always
let through, one more only while its weight fits and the memory is there, never more than an asked limit, every compile given
its turn, a stop that ends a wait.
And the source: every compile of a game compute program goes through the gate (cached_compute, and prepare_run's own call),
a create call that only asks the caches takes no turn, and the gate is on by default on Mesa's Intel driver alone.
No game or GPU is needed.

python -I -B tests/test_compute_gate.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]


def function(source, head):
    """A function's text, from its head to the first line that closes it at column 0"""
    start = source.index(head)
    return source[start:source.index("\n}\n", start) + 3]


def check_source():
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    cached = function(draw, "VkResult cached_compute(const VkComputePipelineCreateInfo* ci, VkPipeline* pl) {")
    if cached.index("const ComputeTurn turn(*ci);") > cached.index("create_cached(guarded_compute_held, ci, pl)"):
        raise SystemExit("cached_compute compiles before it has its turn at the gate")
    if "if (!turn.ok()) return" not in cached:
        raise SystemExit("cached_compute compiles after a wait that was stopped")
    # (the driver's compile of a game compute program is guarded_compute_held: only cached_compute (through create_cached) and
    # prepare_run's warm reach it, each with a turn. A new caller would compile beside the gate. guarded_compute itself is
    # reached through the two wrappers (guarded_compute_held, extern_guarded_compute) and by the renderer's own shaders, made
    # from their fixed SPIR-V with no pipeline cache, which are not game programs and are not gated)
    callers = {"guarded_compute": [], "guarded_compute_held": []}
    for m in re.finditer(r"(?<!\w)(guarded_compute(?:_held)?)\b", draw):
        line = draw[draw.rfind("\n", 0, m.start()) + 1:draw.index("\n", m.start())].strip()
        if line.startswith(("VkResult guarded_compute", "__declspec(noinline) VkResult guarded_compute(", "//", "///")):
            continue
        if "//" in line and line.index("//") < line.index(m.group(1)):
            continue   # (named in a comment after code)
        callers[m.group(1)].append(line)
    if sorted(callers["guarded_compute_held"]) != sorted(["return create_cached(guarded_compute_held, ci, pl);",
                                                          "if (turn.ok() && guarded_compute_held(pcache, &ci, &pl) == VK_SUCCESS && pl) {"]):
        raise SystemExit("guarded_compute_held is reached by something else than the two gated callers: %r"
                         % callers["guarded_compute_held"])
    wrappers = [line for line in callers["guarded_compute"] if line == "return guarded_compute(cache, ci, pl);"]
    own = [line for line in callers["guarded_compute"] if "guarded_compute(VK_NULL_HANDLE, " in line]
    if len(wrappers) != 2 or len(wrappers) + len(own) != len(callers["guarded_compute"]):
        raise SystemExit("guarded_compute is reached beside the gate with a pipeline cache (a game compute program?): %r"
                         % callers["guarded_compute"])
    for other in sorted((ROOT / "gpu/vk").glob("*.cpp")):
        for m in re.finditer(r"extern_guarded_compute\(([^,]*),", other.read_text(encoding="utf-8")):
            if m.group(1).strip() not in ("VK_NULL_HANDLE", "VkPipelineCache cache"):
                raise SystemExit("%s: extern_guarded_compute is given a pipeline cache (a game compute program?)" % other.name)
    prepare = function(draw, "bool prepare_run(void (*progress)(size_t done, size_t total), bool background, bool refresh_states) {")
    if prepare.index("const ComputeTurn turn(ci);") > prepare.index("guarded_compute_held(pcache, &ci, &pl)"):
        raise SystemExit("prepare_run's warm compiles before it has its turn at the gate")
    # (Intel's lock on Windows, IntelDriverGate, is taken inside the turn: a worker holding it while it waited for a turn would
    # block the compiles that have theirs, and those hold the memory it waits for)
    for body, name in ((cached, "cached_compute"), (prepare, "prepare_run's warm")):
        if body.index("ComputeTurn turn(") > body.index("IntelDriverGate gate"):
            raise SystemExit(name + " takes Intel's lock before its turn at the gate: the two can wait on each other")
    turn = draw[draw.index("struct ComputeTurn {"):draw.index("VkResult cached_compute(")]
    for needle, why in (("VK_PIPELINE_CREATE_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT) ? nullptr : &compute_compiles()",
                         "a create call that only asks the caches waits for a turn (a dispatch asks on the replay's thread)"),
                        ("gate->enter(weight, memory_available_mb, [] { return prepare_stopped(); })",
                         "a wait at the gate does not end when the preparation is stopped, or does not read the memory"),
                        ("gate->leave(weight);", "a turn is not given back, or not its weight"),
                        ("weight(compute_gate::weight(compute_pinned(ci), compute_described.phis, compute_described.fallback))",
                         "a compile is not weighed by whether it is held to 32 lanes, its size and whether it is a mesh fallback stage"),
                        ("if (compute_gate::trims(gated, held_ms)) malloc_trim(0);",
                         "a long compile no longer hands the memory it freed back to the system"),
                        ("began = std::chrono::steady_clock::now();   // (the turn is taken: the compile starts)",
                         "the compile's time counts its wait at the gate")):
        if needle not in turn:
            raise SystemExit(why)
    # (ComputeTurn reads what compute_pipeline_info or the mesh fallback described last on this thread: the back end's own
    # pipelines (vk_fsr3.cpp, vk_fsr4.cpp, some held to 32 or 64 lanes) come in with none, or they would be weighed, refused
    # (compute_refused) and logged as that game program)
    shared = function(draw, "VkResult shared_compute_pipeline(const VkComputePipelineCreateInfo* ci, VkPipeline* out) {")
    if shared.find("compute_described = {};") < 0 or shared.index("compute_described = {};") > shared.index("cached_compute(ci, out)"):
        raise SystemExit("shared_compute_pipeline reaches the gate with the description of the game program this thread made last")
    if turn.index("prepare_compiled();") > turn.index("compiling.erase(mine);"):
        raise SystemExit("a compile leaves the active list before the watchdog hears it ended: the short timeout can race the completion")
    if turn.index("gate->leave(weight);") > turn.index("malloc_trim(0);"):
        raise SystemExit("the memory is handed back before the turn is: the next compile waits for it")
    gate = function(draw, "compute_gate::Gate& compute_compiles() {")
    for needle, why in (('getenv("RX_VK_COMPUTE_AT_ONCE")', "the switch is gone"),
                        ("gate.set(n, false);", "an asked limit also looks at the memory"),
                        ("} else if (dev.driver_id == VK_DRIVER_ID_INTEL_OPEN_SOURCE_MESA) {",
                         "the gate's default is no longer Mesa's Intel driver alone, where it was measured"),
                        ("gate.set(0, true, budget);", "the default does not look at the memory"),
                        ("compute_gate::budget_for(avail)", "the default budget is not the memory's")):
        if needle not in gate:
            raise SystemExit(why)
    if gate.count("gate.set(") != 2:
        raise SystemExit("the gate is set somewhere else: any other GPU must keep no limit unless RX_VK_COMPUTE_AT_ONCE asks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="compute-gate-") as tmp:
        exe = Path(tmp) / "compute-gate"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-D_CRT_SECURE_NO_WARNINGS", "-pthread",
                        str(ROOT / "tests/compute_gate_test.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True, timeout=120)


if __name__ == "__main__":
    main()
