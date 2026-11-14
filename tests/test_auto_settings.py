"""Compile and run the Quality preset Auto (this PC)'s rules (gpu/vk/auto_settings.h; no game/GPU), and check that the menu and
the renderer still use them: the preset row reaches Auto, a first start starts on it, and the hardware is read once the window is
known.

python -I -B tests/test_auto_settings.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "g++"]

ROOT = Path(__file__).resolve().parents[1]


def need(where, text, needles):
    for needle in needles:
        if needle not in text:
            raise SystemExit(where + " no longer has: " + needle)


def body(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def check_source():
    menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
    need("vk_menu.cpp", menu, ['{TAB_GRAPHICS, "Quality preset", &opts.preset, 0, 6, 1, tx_preset,', '"Auto (this PC)"',
                               "if (first) opts.preset = kAutoPreset;",
                               "::auto_settings::choose(hw)", "if (fp == auto_for)", 'fprintf(f, "auto_for=%016llx\\n"',
                               # (save() keeps the lines it does not write: each auto_ key must be one it writes, or the old
                               # line, kept after the new one, wins at the next start)
                               '|| key == "memory_budget" || key == "auto_for" ||',
                               'key == "auto_tuned" || key == "auto_output" || key == "auto_steps";',
                               # (the measured tuning in play: from the replay's windows, finished once for this PC, its steps
                               # kept across restarts)
                               "::auto_settings::tune(tuning,", 'fprintf(f, "auto_tuned=%016llx\\n"', 'fprintf(f, "auto_steps=%d,%d\\n"',
                               'if (!strcmp(line, "auto_steps"))',
                               # (the hardware changed: the exempt rows the player set under Auto stay theirs)
                               "apply_auto(!first);", "apply_auto(false);"])
    need("vk_menu.h", (ROOT / "gpu/vk/vk_menu.h").read_text(encoding="utf-8"), ["constexpr int kAutoPreset = 6;"])
    if "constexpr int kAutoPreset" in menu:
        raise SystemExit("vk_menu.cpp defines kAutoPreset again: vk_menu.h has it")
    # (the upscaler set before the tier's rows: apply_preset snaps the Render resolution to it)
    auto = body(menu, "void apply_auto(bool keep_own) {")
    if not auto.index("opts.dlss = c.upscaler;") < auto.index("apply_preset(c.tier);"):
        raise SystemExit("apply_auto: opts.dlss must be set before apply_preset")
    # (Auto never sets the Output resolution: host/hos_main.c reads it at boot, before the card is known, so a size chosen here
    # only applied at the next start, and a new install's first close of the menu asked to restart for it)
    if "output_res" in auto or "output_w" in (ROOT / "gpu/vk/auto_settings.h").read_text(encoding="utf-8"):
        raise SystemExit("apply_auto: Auto sets the Output resolution (a new install's first menu close asks to restart)")
    if 'fprintf(f, "auto_output=' in menu:
        raise SystemExit("save(): auto_output= is written again (Auto sets no Output resolution)")
    # (the CPU holding the frame rate ends the tuning for this run only: no auto_tuned for it)
    tune = body(menu, "void menu_auto_tune(double gpu_ms, double draws, double fps) {")
    need("menu_auto_tune", tune, ["::auto_settings::resolution_for(c, ur::engine(u), v,"])
    cpu = tune[tune.index("verdict == ::auto_settings::CPU_BOUND) {"):]
    cpu = cpu[:cpu.index("} else {")]
    if "auto_tuned" in cpu or "return;" not in cpu:
        raise SystemExit("menu_auto_tune: the CPU-bound verdict must end this run's tuning without auto_tuned")
    # (the tiers' own Render resolution in auto_settings.h is apply_preset's)
    preset = body(menu, "void apply_preset(int p) {")
    own = {int(n): int(r) for n, r in re.findall(r"case (\d): //[^\n]*\n\s*opts\.resolution = (\d);", preset)}
    rules = (ROOT / "gpu/vk/auto_settings.h").read_text(encoding="utf-8")
    table = re.search(r"constexpr int kTierResolution\[\] = \{([^}]*)\};", rules)
    if not table or len(own) != 5:
        raise SystemExit("auto_settings.h kTierResolution or apply_preset's cases not found")
    values = [int(x) for x in table.group(1).split(",")]
    if any(values[p] != own[p] for p in own):
        raise SystemExit("auto_settings.h kTierResolution %s is not apply_preset's %s" % (values, own))
    main = (ROOT / "gpu/vk/vk_main.cpp").read_text(encoding="utf-8")
    need("vk_main.cpp", main, ["auto_profile();   // (the Quality preset Auto (this PC)", "menu_auto_for_gpu(p, hw);",
                               "hw.mesh_native = dev.mesh_capable;", "hw.mesh_as_compute = dev.mesh_capable && !dev.mesh_shader;"])
    # (the card's mesh shaders from its feature query, before the Mesh shaders mode turns them off for this run)
    if not main.index("dev.mesh_capable = m.meshShader && m.taskShader;") < main.index(
            "if (mesh_mode_used == 2) dev.mesh_shader = false;"):
        raise SystemExit("vk_main.cpp: dev.mesh_capable must be read before the Mesh shaders mode is applied")
    need("vk_replay.cpp", (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8"), ["menu_auto_tune(gpu_ms, draws, 120.0 / secs);"])
    api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
    need("vk_api.h", api, ["#define MKWVK_WINDOW_VERSION 3", "void (*desktop_size)(void *window, int *width, int *height);"])
    host = (ROOT / "host/posix/display_sdl.c").read_text(encoding="utf-8")
    need("host/posix/display_sdl.c", host, ["refresh_mhz, desktop_size};"])
    check_deck_profile(menu, main, auto)


def check_deck_profile(menu, main, auto):
    """The Steam Deck profile: decided as the card is picked, before the device and its first command buffer (the recorder's
    mode), from RX_VK_STEAM_DECK, steam_deck= and the Deck found; Auto sets its Frame generation and VRAM budget; the precompile
    keeps no graphics pipeline ready with it, and says none were built"""
    need("vk_menu.cpp", menu, ['if (!strcmp(line, "steam_deck")) steam_deck_saved = env_value_off(eq + 1) ? 0 : 1;',
                               "int menu_steam_deck() { return steam_deck_saved; }"])
    need("apply_auto", auto, ["::auto_settings::deck_settings(c.vram_auto, keep_own, auto_deck_turned);",
                              "!(deck.restore_cap && opts.vram_budget == 0);",
                              'if (deck.apply && c.framegen >= 0 && !getenv("RX_VK_FRAMEGEN_MULT")) opts.framegen = c.framegen;',
                              "if (own_budget || deck.apply) {", "opts.vram_budget = own_budget ? vram_budget : 0;"])
    chooses = body(menu, "void menu_auto_for_gpu(const VkPhysicalDeviceProperties& props, ::auto_settings::Hardware hw) {")
    if not chooses.index("auto_deck_turned = ::auto_settings::deck_turned(auto_for, hw, props.vendorID, props.deviceID);") < \
            chooses.index("apply_auto(!first);"):
        raise SystemExit("menu_auto_for_gpu: whether the profile turned must be known before apply_auto")
    pick = main[main.index("bool pick_device() {"):]
    pick = pick[:pick.index("\n}\n")]
    if not pick.index("menu_init();") < pick.index("vkGetPhysicalDeviceProperties(dev.physical, &dev.props);") < \
            pick.index("deck_profile_decide();"):
        raise SystemExit("pick_device: the Steam Deck profile must be decided once the options are read and the card known")
    if main.index("deck_profile_decide();") > main.index("bool create_device() {"):
        raise SystemExit("vk_main.cpp: deck_profile_decide must come before create_device (the recorder's mode, first vkCmd*)")
    decide = body(main, "void deck_profile_decide() {")
    need("deck_profile_decide", decide, ['const char* env = getenv("RX_VK_STEAM_DECK");',
                                         "::auto_settings::deck_mode(env, menu_steam_deck())",
                                         'if (!getenv("RX_VK_RECORDER"))', "recorder_profile_thread()"])
    need("auto_profile", body(main, "void auto_profile() {"), ["hw.handheld = handheld_found(p);", "hw.deck = deck_profile_now;"])
    # (the profile by the Deck's APU alone: SteamDeck=1 is Steam's Deck-style session, on other handhelds too)
    found = body(main, "bool deck_found(const VkPhysicalDeviceProperties& p) {")
    if "SteamDeck" in found or "0x163F" not in found or "0x1435" not in found:
        raise SystemExit("deck_found: the Steam Deck by its APU (0x163F, 0x1435), not SteamDeck=1")
    replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
    need("recorder_profile_thread", body(replay, "bool recorder_profile_thread() {"), ["!::mkwvk::rec::parallel_configured() &&"])
    recorder = (ROOT / "gpu/vk/vk_recorder.h").read_text(encoding="utf-8")
    need("vk_recorder.h", recorder, ['if (const char* e = getenv("RX_VK_RECORDER")) return e;', "const char* e = requested();",
                                     "requested(), getenv(\"RX_VK_PARALLEL\"));"])
    draw = (ROOT / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
    need("precompile_graphics_none", body(draw, "bool precompile_graphics_none() {"),
         ['if (env_on("HOOKSHOT_PREPARE_ONLY")) return false;', 'getenv("RX_VK_PRECOMPILE_GRAPHICS")', "return deck_profile_on();"])
    run = body(draw, "void precompile_run(void (*progress)(size_t done, size_t total)) {")
    if not run.index("if (!note_file) notes_open_locked(&notes);") < run.index("notes.clear();") < \
            run.index("for (const auto& n : notes) wanted.insert(n->prog), wanted_variants.insert(mix(n->prog, n->variant));"):
        raise SystemExit("precompile_run: graphics none must drop the notes after they are noted and before their programs load")
    need("precompile_run", run, ["!graphics_none) precompile_built_write(graphics_n);"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="g++")
    args = parser.parse_args()
    check_source()
    with tempfile.TemporaryDirectory(prefix="auto-settings-") as tmp:
        exe = Path(tmp) / "auto-settings"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "tests/test_auto_settings.cpp"), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
