"""scripts/windows/launch-hdr.ps1 writes keys and values the menu still reads.

The script sets rows of hookshot_options.ini from outside the game, so a row renamed or a range changed in
gpu/vk/vk_menu.cpp would make it write a line the game ignores, or a value that means something else. This reads the
keys the script sets and checks each against the menu's rows: the key is one ini_key() gives a row, and the value the
script writes is inside that row's range and, for the rows it sets by number, still has the meaning the script
expects. It also checks the DISPLAYCONFIG numbers the HDR switch is made with against wingdi.h's. No game, GPU or
PowerShell is needed.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
script = (ROOT / "scripts/windows/launch-hdr.ps1").read_text(encoding="utf-8")
menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")


def check(ok, what):
    if not ok:
        raise SystemExit("FAIL: " + what)


# --- the menu's rows: {TAB_X, "Name", &opts.field, min, max, step, text function, ...
rows = {}
for name, field, low, high, text in re.findall(
        r'\{TAB_\w+,\s*"([^"]+)",\s*&opts\.(\w+),\s*(-?\d+),\s*([^,]+),\s*-?\d+,\s*(\w+)', menu):
    rows.setdefault(field, (name, int(low), high.strip(), text))
start = menu.index("const char* ini_key(const Row& r)")
body = menu[start:menu.index("\n}", start)]
named = dict(re.findall(r'r\.value == &opts\.(\w+)\) return "(\w+)"', body))
check("*p == ' ' ? '_' : (char)tolower(*p)" in body, "ini_key no longer makes a key from the row's name in lower case")
keys = {}
for field, (name, low, high, text) in rows.items():
    keys.setdefault(named.get(field, name.replace(" ", "_").lower()), (field, low, high, text))


def table(function):
    """The strings a tx_ function picks from, in order."""
    at = menu.index("const char* %s(int v)" % function)
    return re.findall(r'"([^"]*)"', menu[at:menu.index("}", menu.index("{", menu.index("{", at) + 1))])


# --- the keys the script sets
written = set(re.findall(r"\$keys\.(\w+)\s*=", script)) | set(re.findall(r"\$keys = @\{\s*(\w+)\s*=", script))
expected = {"hdr", "hdr_paper_white", "hdr_peak_brightness", "dlss", "frame_generation", "frame_pacing",
            "nvidia_reflex", "vsync"}
check(written == expected, "the script sets %s, this check knows %s" % (sorted(written), sorted(expected)))
for key in sorted(written):
    check(key in keys, "%s is not a key the menu saves a row under" % key)

# --- the values it writes still mean what it says
check(table("tx_vsync")[:3] == ["Auto", "On", "Off"] and "$keys.vsync = 2" in script, "V-Sync: 2 is no longer Off")
check(table("tx_framegen")[:3] == ["Off", "Auto", "2x"] and len(table("tx_framegen")) == 9 and
      "[ValidateRange(0, 8)][int]$FrameGen" in script, "Frame generation is no longer Off, Auto, 2x to 8x as 0 to 8")
hdr = keys["hdr"]
check((hdr[1], hdr[2]) == (0, "2") and "elseif ($Expanded) { 1 } else { 2 }" in script,
      "HDR is no longer 0 Off, 1 Expanded, 2 Native")
check(re.search(r"Expanded: the game's SDR picture.*Native: the game's own HDR", menu, re.S) is not None,
      "the HDR row's description no longer names Expanded then Native")
upscalers = re.search(r'name\[ur::kUpscalers\] = \{([^}]*)\}', menu)
check(upscalers is not None and re.findall(r'"([^"]*)"', upscalers.group(1))[2] == "DLAA" and "$keys.dlss = 2" in script,
      "the Upscaler row's 2 is no longer DLAA")
for key, parameter in (("hdr_peak_brightness", "PeakNits"), ("hdr_paper_white", "PaperWhite")):
    low, high = keys[key][1], int(keys[key][2])
    check("[ValidateRange(%d, %d)][int]$%s" % (low, high, parameter) in script,
          "-%s's range is not the %s row's %d to %d" % (parameter, key, low, high))
for key in ("frame_pacing", "nvidia_reflex"):
    check(keys[key][1] <= 1 <= int(keys[key][2]) and "$keys.%s = 1" % key in script, "%s: 1 is out of the row's range" % key)

# --- the display calls: wingdi.h's DISPLAYCONFIG_DEVICE_INFO_TYPE numbers and QDC_ONLY_ACTIVE_PATHS
for number, what in ((2, "r.h.type = 2;"),                        # GET_TARGET_NAME
                     (9, "r.h.type = 9;"),                        # GET_ADVANCED_COLOR_INFO
                     (15, "r.h.type = 15;"),                      # GET_ADVANCED_COLOR_INFO_2
                     (16, "? 16u : 10u"),                         # SET_HDR_STATE, else SET_ADVANCED_COLOR_STATE
                     (2, "QueryDisplayConfig(2,")):
    check(what in script, "the display call with %d is gone or changed: %s" % (number, what))
check("n.mode == 2" in script and "(n.value >> 4) & 1" in script,
      "HDR on is DISPLAYCONFIG_ADVANCED_COLOR_MODE_HDR (2), offered is bit 4 (highDynamicRangeSupported)")
# (the game writes its file whole when it closes: a write while it runs would be lost)
check("Get-Process hookshot" in script, "the script no longer refuses while the game runs")
print("OK: launch-hdr.ps1 writes %d keys the menu reads" % len(written))
