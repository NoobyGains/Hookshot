"""Run the actual menu keyboard poll against the host's actual keyboard policy.
Regression: Deck B arrives as a native confirm plus Steam's injected Escape.
The menu must not accept Escape when Keyboard Auto suppresses gameplay keys.
No game, controller or desktop is accessed.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    menu = (ROOT / 'gpu/vk/vk_menu.cpp').read_text()
    tick = menu[menu.index('void menu_tick() {'):]
    poll = tick[tick.index('    enum { K_N ='):tick.index('    // (hookshot) the gamepads')]
    hid = (ROOT / 'host/nn_hid.c').read_text()
    policy = block(hid, 'static int keyboard_counts(')
    api = (ROOT / 'gpu/vk/vk_api.h').read_text()
    backend = (ROOT / 'host/rx_backend.c').read_text()
    assert 'int (*keyboard_counts)(int key);' in api
    assert 'int hos_keyboard_counts(int vk) { return keyboard_counts(vk); }' in hid
    # (rx_backend.c fills MkwVkHost by position: hos_keyboard_counts follows the host function of the field before it)
    fields = re.findall(r"\(\*(\w+)\)\(", api[api.index("float (*wide_cover)(void);"):api.index("} MkwVkHost;")])
    assert fields[fields.index("keyboard_counts") - 1] == "mods_save", fields
    assert 'hos_mods_save, hos_keyboard_counts,' in backend
    assert '(keyboard_enabled[i] && held[i])' in tick, 'suppressed arrows must not repeat'
    source = r'''
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
using LONG = int;
using HWND = int;
using DWORD = unsigned;
enum { VK_INSERT=45, VK_UP=38, VK_DOWN=40, VK_LEFT=37, VK_RIGHT=39,
       VK_ESCAPE=27, VK_F1=112, VK_RETURN=13, VK_DELETE=46, VK_BACK=8,
       VK_TAB=9, VK_PRIOR=33, VK_NEXT=34, VK_HOME=36, VK_END=35,
       HOS_OPT_KEYBOARD=87 };
static LONG pad_count_now;
static int mode, current_key, pending_key;
static bool focused=true, pad_last;
static int rx_option(int id, int fallback) { return id==HOS_OPT_KEYBOARD ? mode : fallback; }
// POLICY
static int GetForegroundWindow() { return 1; }
static DWORD GetCurrentProcessId() { return 1; }
static void GetWindowThreadProcessId(HWND, DWORD *pid) { *pid=focused ? 1 : 2; }
static int GetAsyncKeyState(int key) { return current_key==key ? 0x8000 : 0; }
static int take_key_press(int key) {
    if (pending_key!=key) return 0;
    pending_key=0;
    return 1;
}
static struct { int menu_shortcut=2; } opts;
static struct Host { int (*take_key_press)(int); int (*keyboard_counts)(int); } h, *host=&h;
static bool tick_key(int key, bool queued) {
    current_key=queued ? 0 : key; pending_key=queued ? key : 0;
    h.take_key_press=queued ? take_key_press : nullptr;
    h.keyboard_counts=keyboard_counts;
    // POLL
    if (pending_key) { std::fputs("FAIL: suppressed queued key was not consumed\n",stderr); std::exit(1); }
    return key==VK_ESCAPE ? press[5] : key==VK_RETURN ? press[7] : key==VK_TAB ? press[12] : key==VK_UP ? press[1] : key==VK_F1 ? press[6] : press[0];
}
int main() {
    for (bool queued : {false,true}) {
        for (int key : {VK_ESCAPE,VK_RETURN,VK_TAB,VK_UP}) {
            tick_key(0,queued);
            mode=0; pad_count_now=1;
            if (tick_key(key,queued)) {
                std::fprintf(stderr,"FAIL: Auto with controller accepted menu key %d (%s path)\n",key,queued?"queued":"polled"); return 1;
            }
            tick_key(0,queued); mode=1;
            if (!tick_key(key,queued)) { std::fputs("FAIL: On did not restore menu keyboard input\n",stderr); return 1; }
            tick_key(0,queued); mode=2; pad_count_now=0;
            if (tick_key(key,queued)) { std::fputs("FAIL: Off accepted menu keyboard input\n",stderr); return 1; }
            tick_key(0,queued); mode=0;
            if (!tick_key(key,queued)) { std::fputs("FAIL: Auto without controller rejected keyboard\n",stderr); return 1; }
        }
        mode=2; pad_count_now=1;
        for (int key : {VK_F1,VK_INSERT}) {
            tick_key(0,queued);
            if (!tick_key(key,queued)) { std::fputs("FAIL: emergency menu shortcut blocked\n",stderr); return 1; }
        }
        tick_key(0,queued); focused=false;
        if (tick_key(VK_F1,queued)) { std::fputs("FAIL: unfocused window accepted shortcut\n",stderr); return 1; }
        focused=true;
    }
    std::puts("PASS: menu keys obey host Auto/On/Off policy; queued events drain; emergency shortcuts remain");
}
'''.replace('// POLICY', policy).replace('    // POLL', poll)
    with tempfile.TemporaryDirectory(prefix='keyboard-menu-', dir=os.environ.get('TMPDIR')) as folder:
        src = Path(folder) / 'fixture.cpp'
        exe = Path(folder) / 'fixture'
        src.write_text(source)
        subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
