"""The pipeline tour (scripts/pipeline_tour.py), without the game: the Debug tab's action numbers and the teleport list it reads
from the source, its route, the presses it sends, the switches and options it runs with, its command line, its counts and merge of
the pipeline state lists, the memory guard, and the bridge driving: a fake control bridge (a Unix socket served from a thread, as
tests/test_hookshot_ctl.py's stand-in serves one) that answers the way host/control.c does, refusing, cancelling and timing out
where the game would, with the real client (scripts/hookshot_ctl.py Bridge) in between.

The tour teleports through the bridge by the destination's index and switches the age through it (host/control.c, host/hos_main.c),
and gives the items through the live input file's "!cheat <action>" lines (host/nn_hid.c), whose numbers are the Insert menu's
(gpu/vk/oot_cheat_items.h): a renumbered action or a reordered teleport list must not send the tour somewhere else.
Synthetic data only. Linux only (the bridge's Unix socket).

python -I -B tests/test_pipeline_tour.py
"""
import importlib.util
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

RUN_ALL_SKIP = {"windows": "the tour runs on Linux (/proc, the bridge's Unix socket): checked on Linux"}

ROOT = Path(__file__).resolve().parents[1]
TOUR = ROOT / "scripts" / "pipeline_tour.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fail(why):
    raise SystemExit("pipeline tour: " + why)


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def source(tour, a):
    """What the tour reads from the source, and what it relies on there"""
    main_c, hid, menu, ctl_c = text("host/hos_main.c"), text("host/nn_hid.c"), text("gpu/vk/vk_menu.cpp"), text("host/control.c")
    # the bridge: a teleport by index is the Debug tab's OOT_TELEPORT_ACTION + index, the age switch OOT_AGE_ACTION
    if "action = OOT_TELEPORT_ACTION + asked - 1" not in main_c or "action = OOT_AGE_ACTION" not in main_c:
        fail("host/hos_main.c no longer takes the bridge's teleport and age switch as the Debug tab's actions")
    for cmd in ("teleport", "age", "status", "wait", "sequence", "press", "quit"):
        if '!strcmp(cmd, "%s")' % cmd not in ctl_c:
            fail("host/control.c has no %s command" % cmd)
    if '\\"game\\":{\\"event\\":%s,\\"loading\\":%s,\\"age\\":\\"%s\\"}' not in ctl_c:
        fail("host/control.c's status no longer says the game's event, loading and age, which the tour waits on")
    if 'strcmp(units, "hos")' not in ctl_c:
        fail("host/control.c's sequence no longer takes HOS_INPUT_SCRIPT's units (the tour's presses)")
    if 'j_get(d, req, "steps")' not in ctl_c:
        fail("host/control.c's sequence no longer takes steps, which the client sends a HOS_INPUT_SCRIPT press as (hos_steps)")
    if '"refused"' not in ctl_c or '"cancelled"' not in ctl_c:
        fail("host/control.c no longer replies refused or cancelled")
    # the refusals asking again cannot change are named in the game's words
    whys = re.findall(r'teleport\.why = (?:child \? )?"([^"]+)"', main_c)
    if not whys:
        fail("host/hos_main.c's teleport refusals not found")
    for why in whys:
        permanent = any(p in why for p in tour.PERMANENT)
        transient = any(w in why for w in ("event is playing", "map is loading", "in progress", "not there yet"))
        if permanent == transient:
            fail("a teleport refusal neither asked again nor given up on, or both: %r" % why)
    # the live input: "!cheat <action>", the Debug tab's actions (the inventory)
    if not re.search(r'if \(!strncmp\(line, "!cheat ", 7\)\) __atomic_store_n\(&hos_oot_live_action, atoi\(line \+ 7\)', hid):
        fail("host/nn_hid.c's live input no longer reads \"!cheat <action>\"")
    if "cheat_action.store(1000 + teleport_choice)" not in menu or a["teleport"] != 1000:
        fail("the menu's teleport action and OOT_TELEPORT_ACTION (%d) differ" % a["teleport"])
    if "cheat_action.store(999)" not in menu or a["age"] != 999:
        fail("the menu's age action and OOT_AGE_ACTION (%d) differ" % a["age"])
    # the teleports: one for each destination, in its order; the adult-only ones those without a child map
    table = main_c.split("oot_destinations[] = {", 1)[1].split("\n};", 1)[0]
    entries = re.findall(r"\{(NULL|\"[^\"]*\"),.*?\},\s*/\* ([^*]+) \*/", table, re.S)
    if [label for _, label in entries] != [name for name, _ in a["teleports"]]:
        fail("the teleport names and host/hos_main.c's destinations differ:\n%s\n%s" % (
            [label for _, label in entries], [name for name, _ in a["teleports"]]))
    for (child, label), (_, adult_only) in zip(entries, a["teleports"]):
        if (child == "NULL") != adult_only:
            fail("%s: adult only in the menu %s, no child map in the table %s" % (label, adult_only, child == "NULL"))
    if len(a["bancs"]) != len(a["teleports"]) or any((child is None) != only for (child, _), (_, only) in zip(a["bancs"], a["teleports"])):
        fail("the destinations' maps and the teleport list differ")
    if not 0 < a["dungeons"] < len(a["teleports"]):
        fail("the teleport list's Dungeons section not found (vk_menu.cpp teleport_sections)")
    main_time = re.search(r"action >= (\d+) && action < (\d+)\) \{\s*oot_set_time\(c, action - (\d+)\)", main_c)
    if not main_time or int(main_time.group(1)) != tour.TIME_ACTION or int(main_time.group(2)) < tour.TIME_ACTION + 23:
        fail("host/hos_main.c's clock action is not TIME_ACTION + hour")
    # the inventory: the item list's order is the action's index; kinds 0 (unlock) and 1 (a quantity)
    names = list(a["items"])
    for must in ("Item_Bomb", "Item_Longshot", "Item_Arrow_Fire", "Item_DinFire", "Weapon_Range_Bow", "Item_Ocarina_Time"):
        if must not in a["items"]:
            fail("%s is not in the inventory list" % must)
    if a["items"][names[0]][0] != 0 or a["items"]["Item_Bomb"][1] != 1 or a["items"]["Item_Longshot"][1] != 0:
        fail("the inventory's indices or kinds are read wrong: %s" % list(a["items"].items())[:16])
    unlock = tour.items_unlock(a)
    count = len(re.findall(r'OOT_ITEM\("', text("gpu/vk/oot_cheat_items.h")))
    by_index = {i: name for name, (i, _) in a["items"].items()}
    for n in unlock:
        item, op = divmod(n - a["item"], 256)
        if not 0 <= item < count or item not in by_index or not (op == 200 or 0 < op - 64 <= 63):
            fail("an inventory action out of range: %d" % n)
    if any(n.startswith(tour.QUEST_ITEMS) for n in [by_index[(x - a["item"]) // 256] for x in unlock]):
        fail("the quest items (the story's flags) are given")
    # the switches the tour sets are ones the game reads, and the options its menu writes
    env_src = "".join(text(p) for p in ("host/nn_vi.c", "host/nn_hid.c", "host/pad_sdl.c", "host/nn_audio.c", "host/hos_main.c",
                                        "host/nn_applet.c", "host/discord_rpc.c", "host/display.c")) + menu + \
        "".join(p.read_text(encoding="utf-8", errors="replace") for p in (ROOT / "gpu" / "vk").glob("*.cpp"))
    for name in list(tour.BASE_ENV) + ["HOS_SKIP_OPENING", "HOS_CONTROL", "HOS_INPUT_LIVE", "HOS_WINDOW_SIZE", "HOS_WINDOW_NOACTIVATE",
                                       "RX_VK_SHOTS"]:
        if '"%s"' % name not in env_src and name not in ("HOS_CONTROL",):
            fail("%s: no switch of that name in the game's source" % name)
    keys = {"output_res", "vsync", "resolution", "frame_rate_cap", "upscaling", "dlss", "handheld_profile", "ultrawide"}
    for row in re.findall(r'\{TAB_[A-Z]+, "([^"]+)", &opts\.', menu):
        keys.add(row.lower().replace(" ", "_"))
    for key in tour.BASE_INI:
        if key not in keys:
            fail("%s: no Insert menu row writes it to hookshot_options.ini" % key)
    if tour.BASE_INI["frame_rate_cap"] != "6" or "Uncapped" not in re.search(r"tx_fps_cap\(int v\) \{(.*?)\}", menu, re.S).group(1).split(",")[6]:
        fail("frame_rate_cap=6 is not Uncapped")


def routes(tour, a):
    """The route: a new game first, every destination as child (but the adult-only ones) and as adult, the age switched once"""
    steps = tour.route(a)
    if steps[0] != ("newgame",) or ("items",) not in steps:
        fail("the route does not start with a new game and the items")
    visits = [(s[1], s[2]) for s in steps if s[0] == "visit"]
    for i, (name, adult_only) in enumerate(a["teleports"]):
        for age in ("child", "adult"):
            want = not (age == "child" and adult_only) and (age, name) not in tour.LEFT_OUT
            if ((age, i) in visits) != want:
                fail("%s (%s) is %s the route" % (name, age, "not in" if want else "in"))
    ages = [k for k, s in enumerate(steps) if s == ("age",)]
    if len(ages) != 1 or any(s[0] == "visit" and s[1] == "adult" for s in steps[:ages[0]]):
        fail("the age is not switched once, before the adult stops")
    for part in ("child", "adult"):
        plan = tour.plan_stops(a, part)
        if not plan or any(age != part for age, _ in plan):
            fail("the %s part visits other ages" % part)
    for age, name in tour.LEFT_OUT:
        if name not in [n for n, _ in a["teleports"]]:
            fail("a left-out stop names no destination: %s" % name)
    if len(tour.plan_stops(a, "all")) != len(tour.plan_stops(a, "child")) + len(tour.plan_stops(a, "adult")):
        fail("the child and adult parts are not the whole route")
    for part in ("child-dungeons", "adult-dungeons"):
        if not tour.plan_stops(a, part) or any(i < a["dungeons"] for _, i in tour.plan_stops(a, part)):
            fail("%s visits the overworld" % part)
    for age in ("child", "adult"):   # (a stop the game does not teleport out of goes last in its age)
        names = [a["teleports"][i][0] for g, i in tour.plan_stops(a, "all") if g == age]
        for last in tour.LAST:
            if last in names and names.index(last) != len(names) - 1 - sum(1 for n in names[names.index(last) + 1:] if n in tour.LAST):
                fail("%s is not last in the %s's stops" % (last, age))
    resumed = tour.plan_stops(a, "child", first="Market")
    if a["teleports"][resumed[0][1]][0] != "Market" or len(resumed) >= len(tour.plan_stops(a, "child")):
        fail("--first Market does not start the route there")
    for part in tour.PARTS:   # (the runs of 8 stops cover the part's route, each starting where the one before ended)
        runs = tour.chunks(a, part, 8)
        covered = sum((tour.plan_stops(a, part, stops, first) for first, stops in runs), [])
        if covered != tour.plan_stops(a, part):
            fail("the %s part's runs of 8 stops are not its route" % part)
    if tour.chunks(a, "opening", 8) != [(None, None)]:
        fail("the opening part is not one run")
    if len([s for s in tour.route(a, stops=3) if s[0] == "visit"]) != 3:
        fail("--stops 3 is not three stops")
    over = tour.route(a, "gameover")
    if over[-1][0] != "gameover" or a["teleports"][over[-1][1]][0] != tour.GAME_OVER_AT:
        fail("the gameover part does not go to %s" % tour.GAME_OVER_AT)


def presses(tour):
    """The presses: buttons host/nn_hid.c knows, in its <seconds>:<button>[+<button>][/<ms>] form, each within its step's span"""
    hid = text("host/nn_hid.c")
    known = set(re.findall(r'\{"([A-Z]+)", (?:B_|-1)', hid))
    if not {"A", "B", "PLUS", "ZL", "ZR", "LUP", "RLEFT"} <= known:
        fail("host/nn_hid.c's button names not read: %s" % sorted(known))
    texts = [(tour.LOOK, tour.LOOK_SPAN), (tour.ACT, tour.ACT_SPAN), (tour.PAUSE_TOUR, tour.PAUSE_SPAN), (tour.DIVE, tour.DIVE_SPAN),
             (tour.UNDERWATER_GEAR, tour.GEAR_SPAN), (tour.BOOTS_OFF, tour.BOOTS_SPAN)]
    texts += [tour.pause_pick(k) for k in range(25)] + [(u, 1.0) for u in tour.UNSTICK]
    for script, span in texts:
        for press in script.split(","):
            m = re.fullmatch(r"([\d.]+):([A-Z+]+)(?:/(\d+))?", press)
            if not m or not set(m.group(2).split("+")) <= known:
                fail("a press nn_hid.c does not read: %s" % press)
            if float(m.group(1)) + int(m.group(3) or 200) / 1000 > span + 1e-6:
                fail("a press past its step's span (%g s): %s" % (span, press))
    if len({tour.pause_pick(k)[0] for k in range(20)}) != 20:
        fail("the item picks do not differ from stop to stop")
    if any("A" in p.split(":", 1)[1].split("/")[0].split("+") for p in tour.ACT.split(",")):
        fail("the item use presses A (next to someone it starts a conversation)")


def cli(tour, a):
    """The command line: every command parses, a dry run prints the route, the switches and the tour's runs"""
    p = tour.parser()
    r = p.parse_args(["run", "--game", "g", "--out", "o"])
    if (r.part, r.name, r.nice, r.env, r.ini, r.skip_opening) != ("all", "play", 5, [], [], False):
        fail("run's defaults: %s" % r)
    t = p.parse_args(["tour", "--game", "g", "--out", "o", "--publish"])
    if t.parts != "opening,child-overworld,dungeons,adult-overworld" or t.chunk != 8 or t.nice != 19 or not t.publish:
        fail("tour's defaults: %s" % t)
    for parts in t.parts.split(","):
        if parts not in tour.PARTS:
            fail("a default part that is not one: %s" % parts)
    for argv in (["run", "--game", "g", "--out", "o", "--part", "nope"], ["frobnicate"]):
        try:
            with open(os.devnull, "w") as null:
                old, sys.stderr = sys.stderr, null
                try:
                    p.parse_args(argv)
                finally:
                    sys.stderr = old
            fail("%s taken" % argv)
        except SystemExit as e:
            if e.code != 2:
                raise
    try:
        tour.tour(p.parse_args(["tour", "--game", "g", "--out", "o", "--parts", "child,nope"]))
        fail("a tour with an unknown part ran")
    except SystemExit as e:
        if "nope" not in str(e):
            raise
    ran = subprocess.run([sys.executable, "-I", str(TOUR), "run", "--game", "x", "--out", "x", "--dry-run", "--part", "child",
                          "--stops", "3"], capture_output=True, text=True)
    lines = ran.stdout.splitlines()
    if ran.returncode or lines[0] != "newgame" or not lines[1].startswith("items: ") or len(lines) != 5 or \
            lines[2] != "visit %s (child): teleport 0" % a["teleports"][0][0]:
        fail("run --dry-run: %s%s" % (ran.stdout, ran.stderr))
    # the switches: fast and headless by default; a window, the Game Over's hearts, the opening, --env over them
    env = tour.run_env(p.parse_args(["run", "--game", "g", "--out", "o"]))
    for k, v in (("HOS_HEADLESS", "1"), ("HOS_FPS_MAX", "1000"), ("HOS_FPS_STEP", "0"), ("HOS_NO_PACING", "1"),
                 ("HOS_OUTPUT_RES", "640x360"), ("RX_VK_FRAMEGEN", "0"), ("HOS_SKIP_OPENING", "0"), ("HOS_OOT_PROTECT_HEARTS", "1")):
        if env.get(k) != v:
            fail("the run's %s is %s, not %s" % (k, env.get(k), v))
    env = tour.run_env(p.parse_args(["run", "--game", "g", "--out", "o", "--window", "960x540", "--part", "gameover",
                                     "--skip-opening", "--env", "HOS_AUDIO=-", "--env", "RX_VK_FORCE_MESH_FALLBACK=1"]))
    if "HOS_HEADLESS" in env or env.get("HOS_WINDOW_SIZE") != "960x540" or env["HOS_OOT_PROTECT_HEARTS"] != "0" or \
            env["HOS_SKIP_OPENING"] != "1" or "HOS_AUDIO" in env or env.get("RX_VK_FORCE_MESH_FALLBACK") != "1":
        fail("the run's switches: %s" % env)
    # the tour's runs: the opening watched once, by its own part; the next game of a part where the last one ended
    t = p.parse_args(["tour", "--game", "g", "--out", "o", "--cpus", "6-11", "--env", "X=1", "--mem", "soft_mb=5000"])
    t.copy, t.out_dir = "/g-tour", "/o"
    cmd = tour.run_command(t, "dungeons", "play-dungeons-1", "Fire Temple (child)", 3, True)
    want = ["run", "--game", "/g-tour", "--out", "/o", "--name", "play-dungeons-1", "--part", "dungeons", "--nice", "19", "--env", "X=1",
            "--mem", "soft_mb=5000", "--first", "Fire Temple (child)", "--stops", "3", "--skip-opening", "--cpus", "6-11"]
    if cmd[3:] != want:
        fail("the tour's run: %s" % cmd[3:])
    if tour.cpu_list("0-3,12-13,20") != {0, 1, 2, 3, 12, 13, 20}:
        fail("cpu_list")


def lists(tour, states, rec):
    """The counts and the merge, through nx2/pipeline_states.py (whatever its format); the options file; the report; --publish"""
    head = states.MAGIC + struct.pack("<I", states.SIZE)
    with tempfile.TemporaryDirectory() as d:
        one, two, out = (os.path.join(d, n) for n in ("one.bin", "two.bin", "out.bin"))
        open(one, "wb").write(head + rec(1, 2, 3) + rec(1, 2, 4))
        open(two, "wb").write(head + rec(1, 2, 4) + rec(5, 0, 3))
        n, programs, recs = tour.list_counts(states, one)
        if (n, programs, len(recs)) != (2, 1, 2):
            fail("list_counts: %d pipelines, %d programs, expected 2 and 1" % (n, programs))
        if tour.list_counts(states, os.path.join(d, "none.bin"))[:2] != (0, 0):
            fail("a missing list is not empty")
        ran = subprocess.run([sys.executable, "-I", str(TOUR), "merge", "--out", out, one, two], capture_output=True, text=True)
        if ran.returncode or "1 not in the lists before it" not in ran.stdout:
            fail("merge: %s%s" % (ran.stdout, ran.stderr))
        if states.read(out) != [rec(1, 2, 3), rec(1, 2, 4), rec(5, 0, 3)]:
            fail("merge did not write the three different pipelines in order")
        ini = os.path.join(d, "hookshot_options.ini")
        open(ini, "w").write("dlss=1\nhdr=0\n")
        old = tour.set_ini(ini, [("hdr", "1"), ("handheld_profile", "1")])
        if old != "dlss=1\nhdr=0\n" or open(ini).read() != "dlss=1\nhdr=1\nhandheld_profile=1\n":
            fail("set_ini: %r" % open(ini).read())
        report = tour.write_report(d, [{"stop": "a", "seconds": 1, "pipelines": 2, "programs": 1, "new": 2},
                                       {"stop": "b", "seconds": 2, "pipelines": 3, "programs": 2, "new": 1}],
                                   {"name": "t", "seconds": 2, "env": {"X": "1"}, "ini": [], "completed": False, "error": "x"})
        if "3 pipelines" not in report or "NOT COMPLETED: x" not in report or not os.path.exists(os.path.join(d, "report.json")):
            fail("the report: %s" % report)
    # --publish: the tour's source written by nx2/pipeline_states.py tour, its note from what the runs' bridges said
    with tempfile.TemporaryDirectory() as d:
        part = os.path.join(d, "run-child")
        os.makedirs(part)
        open(os.path.join(part, "states.bin"), "wb").write(head + rec(1, 2, 3) + rec(5, 0, 3))
        json.dump({"meta": {"seconds": 120, "env": {"HOS_OUTPUT_RES": "640x360"}, "version": "v9.9.9-1-gabc",
                            "renderer": "Vulkan: Some GPU 9000, driver 1.2.3"}, "stops": []},
                  open(os.path.join(part, "report.json"), "w"))
        sources = os.path.join(d, "sources")
        os.makedirs(sources)
        if tour.publish([os.path.join(part, "states.bin")], [part], ["child"], sources):
            fail("publish failed")
        note = open(os.path.join(sources, "tour.md"), encoding="utf-8").read()
        if states.read(os.path.join(sources, "tour.bin.xz")) != [rec(1, 2, 3), rec(5, 0, 3)]:
            fail("publish did not write the parts' pipelines")
        for want in ("Some GPU 9000", "v9.9.9-1-gabc", "640x360", "parts child", "frame_rate_cap=6"):
            if want not in note:
                fail("the tour's note lacks %r:\n%s" % (want, note))


# ---- a fake bridge ----

class FakeGame:
    """The game as its bridge shows it (docs/control.md): frames advance with the waits, the title, then Link after some A
    presses, events that end, teleports refused while an event plays, a map that is not left, and the age switch"""
    def __init__(self, bancs):
        self.bancs, self.frame, self.map, self.age, self.event_until, self.loading = bancs, 100, None, "child", 0, False
        self.title_at, self.a_presses, self.pending, self.requests, self.lock = 300, 0, None, [], threading.Lock()
        self.refuse = {}     # (index: refusals still to give)
        self.stuck = set()   # (indices sent but never arriving)
        self.inputs = []

    def advance(self, n):
        self.frame += n
        if self.pending and self.frame >= self.pending[1]:
            self.map, self.loading, self.event_until, self.pending = self.pending[0], False, self.frame + 40, None
        if self.map is None and self.a_presses >= 3:
            self.map, self.event_until = "LinkHouse", self.frame + 200

    def answer(self, req):
        with self.lock:
            self.requests.append(req)
            cmd, r = req.get("cmd"), {"id": req.get("id"), "ok": True}
            event = self.frame < self.event_until or self.loading
            if cmd == "status":
                self.advance(1)
                r.update(state="play" if self.map else "menu" if self.frame >= self.title_at else "intro",
                         draws=400.0 if self.frame >= self.title_at else 5.0, map=self.map, version="v0.0.0-test",
                         renderer="Vulkan: Fake GPU, driver 1")
                if self.map:
                    r["game"] = {"event": event, "loading": self.loading, "age": self.age}
            elif cmd == "press":
                self.advance(1)
                if req.get("buttons") == "A" and self.frame >= self.title_at:
                    self.a_presses += 1
                r.update(queued=1, frames=req.get("frames", 8))
            elif cmd == "sequence":
                # (as host/control.c takes it: steps in frames, which the client sends a script in HOS_INPUT_SCRIPT's units
                # as (scripts/hookshot_ctl.py hos_steps), or such a script with units hos)
                if isinstance(req.get("steps"), list) and "script" not in req and req.get("units") in (None, "frames"):
                    steps = req["steps"]
                elif isinstance(req.get("script"), str) and req.get("units") == "hos":
                    steps = [{"at": round(float(p.split(":")[0]) * 60),
                              "frames": round(float((p.split("/") + ["200"])[1]) * 60 / 1000)} for p in req["script"].split(",")]
                else:
                    return {"id": req.get("id"), "ok": False, "error": "bad_request", "message": "steps or a hos script"}
                self.inputs.append(steps)
                start = self.frame
                self.advance(max(st["at"] + st["frames"] for st in steps) + 1)
                r.update(start=start, end=self.frame)
            elif cmd == "wait":
                if req["event"] == "present":
                    self.advance(req.get("frames", 1))
                elif req["event"] == "frame":
                    self.advance(max(0, req["frame"] - self.frame))
                elif req["event"] in ("map", "loading_end"):
                    if not self.pending or self.pending[1] == float("inf"):
                        self.advance(int(req.get("timeout", 60) * 60))
                        return {"id": req["id"], "ok": False, "frame": self.frame, "error": "timeout", "message": "not met"}
                    self.advance(self.pending[1] - self.frame)
                    if req["event"] == "map":
                        r["map"] = self.map
                r.update(state="play", waited=1)
            elif cmd in ("teleport", "age"):
                self.advance(2)
                to = req.get("to")
                key = to if cmd == "teleport" else "age"
                if self.refuse.get(key):
                    self.refuse[key] -= 1
                    r = {"id": req["id"], "ok": False, "error": "refused",
                         "message": "the game refused the teleport: an event is playing (a cutscene, a map change's)"}
                elif event:
                    r = {"id": req["id"], "ok": False, "error": "refused",
                         "message": "the game refused the teleport: an event is playing (a cutscene, a map change's)"}
                elif cmd == "age":
                    if self.age == to:
                        r.update(age=to, sent=False)
                    else:
                        self.age, self.loading = to, True
                        self.pending = (self.map, self.frame + 90)
                        r.update(age=to, sent=True, map=self.map, accepted=True)
                else:
                    child, adult = self.bancs[to]
                    target = child if self.age == "child" else adult
                    if target is None:
                        r = {"id": req["id"], "ok": False, "error": "refused",
                             "message": "the game refused the teleport: this destination has no map for the child"}
                    else:
                        self.pending = (target, float("inf") if to in self.stuck else self.frame + 120)
                        self.loading = to not in self.stuck
                        r.update(teleport=to, sent=True, map=target, accepted=to not in self.stuck)
            elif cmd == "quit":
                r["quitting"] = True
            else:
                r = {"id": req.get("id"), "ok": False, "error": "unknown_cmd", "message": cmd}
            r["frame"] = self.frame
            return r


def serve(fake, path):
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(2)

    def one(c):
        f = c.makefile("rwb", buffering=0)
        for raw in f:
            r = fake.answer(json.loads(raw))
            f.write(b'{"event":"present","sub":0,"frame":1,"fps":60,"state":"play"}\n')   # (an event first: skipped)
            f.write((json.dumps(r) + "\n").encode())

    def loop():
        while True:
            c, _ = srv.accept()
            threading.Thread(target=one, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv


def bridge_driving(tour, a, states, rec):
    """The run's steps against the fake bridge: a new game to control, the items through the live file, a teleport refused and
    asked again, a stop with no map for the age missed and said so, a map that is not left given up on, the age switched"""
    short = len(tempfile.gettempdir()) <= 48 or not os.path.isdir("/tmp")
    with tempfile.TemporaryDirectory(prefix="tour-", dir=None if short else "/tmp") as d:
        fake = FakeGame(a["bancs"])
        path = os.path.join(d, "control.sock")
        srv = serve(fake, path)
        ctl = tour.ctl_module()
        b = ctl.Bridge(path, 5)
        live = os.path.join(d, "live.txt")
        open(live, "w").close()
        lst = os.path.join(d, tour.LIST)
        open(lst, "wb").write(states.MAGIC + struct.pack("<I", states.SIZE) + rec(1, 2, 3))
        g = tour.Game(b, d, lst, live, cheat_gap=0)
        phases = tour.new_game(g)
        if set(phases) != {"title", "player", "control"} or fake.map != "LinkHouse" or fake.frame < fake.event_until:
            fail("new game: %s, in %s at frame %d (its event until %d)" % (phases, fake.map, fake.frame, fake.event_until))
        if not any(r.get("cmd") == "press" and r.get("wait") is False for r in fake.requests):
            fail("the title's A is not pressed through the bridge")
        # a teleport refused twice (an event playing) and asked again; then in the map, its arrival's event over
        child_stop = next(i for i, (c, _) in enumerate(a["bancs"]) if c)
        fake.refuse[child_stop] = 2
        st = tour.teleport(g, child_stop, a["bancs"][child_stop][0], "child")
        if st["map"] != a["bancs"][child_stop][0] or fake.map != st["map"] or st["event"] or st["loading"]:
            fail("the teleport did not arrive: %s" % st)
        if sum(1 for r in fake.requests if r.get("cmd") == "teleport") != 3:
            fail("a refused teleport is not asked again")
        # every request the tour sent is one the bridge has, with its arguments
        for r in fake.requests:
            if r["cmd"] == "teleport" and not isinstance(r.get("to"), int):
                fail("a teleport not by the destination's index: %s" % r)
        # the presses go as HOS_INPUT_SCRIPT's units, which the client sends as steps in frames, the reply once they are over
        before = fake.frame
        g.press(tour.LOOK)
        if fake.inputs[-1] != ctl.hos_steps(tour.LOOK) or fake.frame - before < int((tour.LOOK_SPAN - 0.2) * 60):
            fail("the look around is not one sequence over its span")
        # the items: the Debug tab's actions in the live file, one a line
        g.cheat(a["item"] + 200)
        g.cheat(a["item"] + 256 + 124)
        if open(live).read() != "!cheat %d\n!cheat %d\n" % (a["item"] + 200, a["item"] + 256 + 124):
            fail("the live file: %r" % open(live).read())
        # an adult-only stop as the child: refused for good, a Failed at once (one try)
        adult_only = next(i for i, (c, _) in enumerate(a["bancs"]) if c is None)
        n = len(fake.requests)
        try:
            tour.teleport(g, adult_only, a["bancs"][adult_only][1], "child")
            fail("a teleport with no map for the age arrived")
        except tour.Failed as e:
            if "no map" not in str(e):
                raise
        if sum(1 for r in fake.requests[n:] if r.get("cmd") == "teleport") != 1:
            fail("a refusal for good is asked again")
        # a map that is not left (the Haunted Wasteland: sent, never moved): given up on after five sends
        other = next(i for i, (c, _) in enumerate(a["bancs"]) if c and i != child_stop)
        fake.stuck.add(other)
        n = len(fake.requests)
        try:
            tour.map_change(g, "teleport", lambda st: st["map"] == a["bancs"][other][0], 10 ** 9, arrive_s=1, to=other)
            fail("a teleport that never moved arrived")
        except tour.Failed as e:
            if "five times" not in str(e):
                raise
        if sum(1 for r in fake.requests[n:] if r.get("cmd") == "teleport") != 5:
            fail("an unmoved teleport is not sent five times")
        fake.stuck.clear()
        fake.pending = None
        # the age: switched, reloaded, then the adult's map; asked again for the adult: nothing to do
        st = tour.switch_age(g, "adult")
        if st["age"] != "adult" or fake.age != "adult":
            fail("the age switch: %s" % st)
        st = tour.switch_age(g, "adult")
        if st["age"] != "adult":
            fail("the age switch to the age Link is: %s" % st)
        # an adult stop now arrives at its adult map
        st = tour.teleport(g, adult_only, a["bancs"][adult_only][1], "adult")
        if st["map"] != a["bancs"][adult_only][1]:
            fail("the adult's teleport: %s" % st)
        # the settle: no new pipeline for the quiet frames, then on
        before = fake.frame
        g.settle(150, 600)
        if not 150 <= fake.frame - before <= 200:
            fail("settle took %d frames, wanted about 150" % (fake.frame - before))
        g.steps.close()
        tour.stop_game(None, b)
        b.close()
        srv.close()


def memory_guard(tour, a):
    """The memory guard: /proc's numbers read, a game not started without memory (waiting, then giving up), a running one
    stopped past its limits, and the tour going on from where a stopped game was"""
    info = "MemTotal: 31000000 kB\nMemAvailable: %d kB\nSwapTotal: 60000000 kB\nSwapFree: %d kB\n"
    free, swap = tour.meminfo(info % (10 * 1048576, 60000000 - 2 * 1048576))
    if abs(free - 10) > 1e-9 or abs(swap - 2) > 1e-9:
        fail("meminfo: %s %s" % (free, swap))
    if tour.meminfo("MemTotal: 1 kB\n") != (None, None):
        fail("meminfo without MemAvailable")
    if tour.held_mb("VmRSS:\t9000000 kB\nRssAnon:\t1048576 kB\nRssFile:\t5000000 kB\nRssShmem:\t2097152 kB\n") != 3072:
        fail("held_mb is not anonymous + shared memory (the file pages can be dropped)")
    mem = dict(tour.MEM)
    if tour.start_problem(mem, (mem["min_free_gb"] + 1, 0)) is not None or tour.start_problem(mem, (None, None)) is not None:
        fail("a game may not start with memory free")
    if not tour.start_problem(mem, (mem["min_free_gb"] - 1, 0)) or not tour.start_problem(mem, (20, mem["max_swap_gb"] + 1)):
        fail("a game starts without memory or with swap full")
    if tour.run_problem(mem, (10, 1), mem["hard_mb"] - 1) is not None:
        fail("a game within its limits stopped")
    for info, held in (((10, 1), mem["hard_mb"] + 1), ((mem["floor_gb"] - 0.5, 1), 1000), ((10, mem["max_swap_gb"] + 5), 1000)):
        if not tour.run_problem(mem, info, held):
            fail("a game past a limit not stopped: %s, %s MB" % (info, held))
    if not mem["soft_mb"] < mem["hard_mb"] < mem["scope_gb"] * 1024 or mem["min_free_gb"] <= mem["floor_gb"]:
        fail("the limits are out of order: %s" % mem)
    now, looks = [0.0], iter([(2, 0), (2, 0), (12, 0)])
    sleep = lambda s: now.__setitem__(0, now[0] + s)
    if tour.wait_memory(dict(mem, wait_s=100), read=lambda: next(looks), sleep=sleep, clock=lambda: now[0], say=lambda *x, **k: 0):
        fail("wait_memory gave up though the memory came")
    now[0] = 0.0
    why = tour.wait_memory(dict(mem, wait_s=100), read=lambda: (1, 0), sleep=sleep, clock=lambda: now[0], say=lambda *x, **k: 0)
    if not why or now[0] < 100 or now[0] > 120:
        fail("wait_memory did not give up after its wait (%s, %s s)" % (why, now[0]))
    if tour.scope_prefix(dict(mem, scope_gb=0)) != []:
        fail("a scope though scope_gb is 0")
    ok = type("R", (), {"returncode": 0})
    bad = type("R", (), {"returncode": 1})
    if tour.shutil.which("systemd-run") and not os.environ.get("OOT_NO_SCOPE"):
        pre = tour.scope_prefix(mem, run=lambda *x, **k: ok)
        if pre[:3] != ["systemd-run", "--user", "--scope"] or "MemoryMax=%dG" % mem["scope_gb"] not in pre or pre[-1] != "--":
            fail("the scope: %s" % pre)
        if tour.scope_prefix(mem, run=lambda *x, **k: bad) != []:
            fail("a scope that does not start is used")
    plan = ["%s (%s)" % (a["teleports"][i][0], age) for age, i in tour.plan_stops(a, "child-overworld")]
    calls = []

    def start(script):
        def run(first, stops, k):
            calls.append((first, stops))
            return script[k]
        return run
    first_chunk = tour.chunks(a, "child-overworld", 4)
    tour.part_runs(a, "child-overworld", 4, start([(4, {"memory_stop": "x", "memory_soft": True, "left": plan[2:4]})] +
                                                  [(0, {})] * 20), say=lambda *x, **k: 0)
    if calls[:3] != [first_chunk[0], (plan[2], 2), first_chunk[1]] or len(calls) != len(first_chunk) + 1:
        fail("the tour does not go on from where the guard ended a game: %s" % calls[:4])
    calls.clear()
    hard = (4, {"memory_stop": "x", "memory_soft": False, "left": plan[1:4]})
    tour.part_runs(a, "child-overworld", 4, start([hard, hard] + [(0, {})] * 20), say=lambda *x, **k: 0)
    if calls[:3] != [first_chunk[0], (plan[1], 3), (plan[2], 2)]:
        fail("a stop the guard ended twice is not left out: %s" % calls[:3])
    calls.clear()
    out = tour.part_runs(a, "child-overworld", 4, start([(0, {}), (3, {"memory_wait": "x", "left": plan[4:8]})] + [(0, {})] * 20),
                         say=lambda *x, **k: 0)
    if out[-1] != (1, 3) or len(calls) != 2:
        fail("a part goes on after a game could not start for memory: %s" % out)
    calls.clear()
    tour.part_runs(a, "child-overworld", 4, start([(1, {})] + [(0, {})] * 20), say=lambda *x, **k: 0)
    if len(calls) != 1:
        fail("a part goes on after a failed game")
    args = type("A", (), {"mem": ["soft_mb=5000", "floor_gb=2.5"], "no_mem_guard": False})()
    m = tour.mem_settings(args)
    if m["soft_mb"] != 5000 or m["floor_gb"] != 2.5 or m["hard_mb"] != tour.MEM["hard_mb"]:
        fail("--mem: %s" % m)
    if tour.mem_settings(type("A", (), {"mem": [], "no_mem_guard": True})()) is not None:
        fail("--no-mem-guard still guards")
    try:
        tour.mem_settings(type("A", (), {"mem": ["nope=1"], "no_mem_guard": False})())
        fail("--mem with an unknown key taken")
    except SystemExit as e:
        if "nope" not in str(e):
            raise
    src = TOUR.read_text(encoding="utf-8")
    if "threading" in src:
        fail("the tour runs games at once (one game can hold 14 GB)")
    if "raise MemoryStop(why)" not in src or "wait_memory(mem)" not in src:
        fail("the run does not check memory")


def worth(tour, states, rec):
    """value: the steps a run's list was sliced into, what each alone adds, and the cut of those adding too little"""
    with tempfile.TemporaryDirectory() as d:
        r = [rec(i, 0, 3) for i in range(1, 40)]
        open(os.path.join(d, "states.bin"), "wb").write(states.MAGIC + struct.pack("<I", states.SIZE) + b"".join(r[:30]))
        rows = [{"stop": "new game: x", "took": 50, "pipelines": 10}, {"stop": "A", "took": 20, "pipelines": 22,
                 "marks": [["arrive", 15], ["look", 20]]}, {"stop": "B", "took": 30, "pipelines": 30}]
        json.dump({"meta": {}, "stops": rows}, open(os.path.join(d, "report.json"), "w"))
        steps = tour.run_steps(states, d)
        (r2,), _ = states.as_v2([r], force=True)
        if [(k, len(v)) for k, _, v in steps] != [("new game: x", 10), ("A", 12), ("B", 8)] or steps[1][2] != set(r2[10:22]):
            fail("run_steps: %s" % [(k, len(v)) for k, _, v in steps])
        sub = tour.run_steps(states, d, sub=True)
        if [(k, len(v)) for k, _, v in sub] != [("new game: x", 10), ("A / arrive", 5), ("A / look", 5), ("A / settle", 2), ("B", 8)]:
            fail("run_steps --sub: %s" % [(k, len(v)) for k, _, v in sub])
    s = lambda *ids: {i for i in ids}
    runs = [[("new game: x", 50, s(1)), ("B", 20, s(2, 3, 4)), ("D", 10, s(1, 2))],
            [("new game: x", 50, s(1)), ("C", 40, s(2, 3, 4)), ("E", 10, s(*range(10, 30)))]]
    rows = {r["step"]: r for r in tour.worth(runs, against=s(4), floor=2)}
    if not rows["new game: x"]["kept"] or rows["D"]["kept"] or not rows["E"]["kept"] or rows["E"]["only"] != 20:
        fail("worth: %s" % rows)
    if rows["B"]["kept"] == rows["C"]["kept"] or not rows["B"]["kept"]:   # (the slower of two equal steps goes)
        fail("worth: of two steps meeting the same pipelines not the faster kept: %s" % rows)
    if rows["B"]["beyond"] != 2 or rows["B"]["only"] != 2:
        fail("worth: the players' lists not taken away: %s" % rows["B"])


def main():
    tour = load("pipeline_tour", TOUR)
    a = tour.actions()
    states = tour.state_tool()

    def rec(vs, fs, topo):
        r = bytearray(states.SIZE)
        struct.pack_into("<QQ", r, 0, vs, fs)
        struct.pack_into("<I", r, 44, topo)
        return bytes(r)

    source(tour, a)
    routes(tour, a)
    presses(tour)
    cli(tour, a)
    lists(tour, states, rec)
    bridge_driving(tour, a, states, rec)
    memory_guard(tour, a)
    worth(tour, states, rec)
    print("pipeline tour: source, route, presses, command line, lists, bridge, memory guard and worth ok")


if __name__ == "__main__":
    main()
