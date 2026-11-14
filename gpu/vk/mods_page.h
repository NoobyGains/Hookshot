/* The Insert menu's Mods page (vk_menu.cpp: Gameplay, Mods) as plain code: the mods host/mods.c found (MkwVkHost.mod) and the
   player's choice for the next start, each on or off and the load order (MkwVkHost.mods_save keeps it in
   mods/hookshot-mods.ini, so no folder of the player's is renamed); whether that differs from this run (a restart is pending),
   the mods on that share files with one (MkwVkHost.mod_shared), and the lines the page shows. No Vulkan, no menu:
   tests/test_mods_page.py checks it. */
#pragma once

#include <algorithm>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace mkwvk::mods_page {

struct Mod {
    std::string name;        // its folder in the mods folder, '/' between folders
    int index = 0;           // the host's: its place in this run's load order (the renamed ones last)
    bool on_start = false;   // loaded in this run
    bool on = false;         // chosen for the next start
    int files = 0;           // its RomFS files
    bool renamed = false;    // off by its folder's name ('-' or '_' first): not the page's to turn on, nor to move
    bool exefs = false;      // it has an exefs folder, left out
};

struct List {
    std::vector<Mod> mods;   // in the next start's load order (a later one wins a file both have), the renamed ones last

    int size() const { return (int)mods.size(); }
    /// How many the player can turn on and off and move: those before the first renamed one
    int movable() const {
        int n = 0;
        while (n < size() && !mods[n].renamed) n++;
        return n;
    }
    int on_count() const {
        int n = 0;
        for (const Mod& m : mods) n += m.on;
        return n;
    }
    /// The next start differs from this run: a mod turned on or off, or the order changed
    bool pending() const {
        for (int i = 0; i < size(); i++)
            if (mods[i].index != i || mods[i].on != mods[i].on_start) return true;
        return false;
    }
    /// The choice as one number, for the restart question's slot (menu_restart.h compares numbers): 0 while it is this run's,
    /// else one from the order and each mod's on or off, so that a different choice after Later asks again
    int key() const {
        if (!pending()) return 0;
        uint32_t h = 2166136261u;
        for (const Mod& m : mods) h = (h ^ (uint32_t)(m.index * 2 + (m.on ? 1 : 0))) * 16777619u;
        return (int)(h & 0x7fffffff) | 1;
    }
    /// Whether the mod at `at` loads differently at the next start: turned on or off, or at another place
    bool changed(int at) const { return at >= 0 && at < size() && (mods[at].index != at || mods[at].on != mods[at].on_start); }
    /// The mod at `at` on or off for the next start; false when nothing changed (a renamed one, no such mod, already so)
    bool set(int at, bool on) {
        if (at < 0 || at >= movable() || mods[at].on == on) return false;
        mods[at].on = on;
        return true;
    }
    bool toggle(int at) { return at >= 0 && at < size() && set(at, !mods[at].on); }
    /// The mod at `at` a place earlier (dir < 0) or later (dir > 0) in the order, among the movable ones: its new place (`at`
    /// itself when it cannot go that way)
    int move(int at, int dir) {
        const int n = movable(), to = at + (dir < 0 ? -1 : 1);
        if (at < 0 || at >= n || to < 0 || to >= n) return at;
        std::swap(mods[at], mods[to]);
        return to;
    }
    /// For MkwVkHost.mods_save: the movable mods' host indexes in the next start's order, and whether each loads
    void choice(std::vector<int>* order, std::vector<int>* on) const {
        order->clear(), on->clear();
        for (int i = 0; i < movable(); i++) order->push_back(mods[i].index), on->push_back(mods[i].on ? 1 : 0);
    }
};

/// Another mod on for the next start that has some of the same files as one that is on too: its place, how many files, and
/// whether the first one's load (it comes later in the order)
struct Clash {
    int other, files;
    bool wins;
};
/// The mods on for the next start that share files with the one at `at` (none while it is off), in the list's order. shared(a,
/// b): how many files two mods both have, by the host's indexes (MkwVkHost.mod_shared)
template <class Shared>
std::vector<Clash> clashes(const List& l, int at, Shared&& shared) {
    std::vector<Clash> out;
    if (at < 0 || at >= l.size() || !l.mods[at].on) return out;
    for (int i = 0; i < l.size(); i++) {
        if (i == at || !l.mods[i].on) continue;
        const int n = shared(l.mods[at].index, l.mods[i].index);
        if (n > 0) out.push_back({i, n, i < at});
    }
    return out;
}

/// "1st", "2nd", "3rd", "4th", "11th", "21st"
inline std::string ordinal(int n) {
    const int ten = n % 100, one = n % 10;
    const char* tail = ten >= 11 && ten <= 13 ? "th" : one == 1 ? "st" : one == 2 ? "nd" : one == 3 ? "rd" : "th";
    return std::to_string(n) + tail;
}
inline std::string files_text(int n) { return std::to_string(n) + (n == 1 ? " file" : " files"); }
/// The last folder of a name ("contents/0100F2C0115B6000/Playable Zelda": "Playable Zelda")
inline std::string last_folder(const std::string& name) {
    const size_t slash = name.find_last_of('/');
    return slash == std::string::npos ? name : name.substr(slash + 1);
}
/// What the list calls a mod: the last folder of its name (the deep layouts' contents/<title id>/ is in the help), the whole
/// name when another mod's last folder is the same
inline std::string label(const List& l, int at) {
    if (at < 0 || at >= l.size()) return "";
    const std::string mine = last_folder(l.mods[at].name);
    for (int i = 0; i < l.size(); i++)
        if (i != at && last_folder(l.mods[i].name) == mine) return l.mods[at].name;
    return mine;
}
/// The line under a mod's name in the list: its files, and the mod on that shares the most of them with it (who wins them),
/// or how many mods do
template <class Shared>
std::string detail(const List& l, int at, Shared&& shared) {
    if (at < 0 || at >= l.size()) return "";
    const Mod& m = l.mods[at];
    std::string t = files_text(m.files);
    if (m.renamed) return "Off by its folder's name, " + t;
    if (m.exefs) t += ", exefs left out";
    const std::vector<Clash> c = clashes(l, at, shared);
    if (c.size() == 1) {
        const Clash& k = c[0];
        t += ", " + std::to_string(k.files) + " also in " + label(l, k.other) + (k.wins ? ": this one wins" : ", which wins");
    } else if (c.size() > 1) {
        t += ", files also in " + std::to_string(c.size()) + " other mods";
    }
    return t;
}
/// The help beside the list for the mod at `at`: where it loads and what that means, or why it is off
inline std::string help(const List& l, int at) {
    if (at < 0 || at >= l.size()) return "";
    const Mod& m = l.mods[at];
    const std::string files = files_text(m.files) + " in its romfs folder, each replacing the game's file of the same path or "
                              "adding one.";
    std::string t;
    if (m.renamed)
        t = "Off by its folder's name: a folder whose name starts with - or _ is left out, with the mods in it. Rename it "
            "without them to turn the mod on here. " + files;
    else if (!m.on)
        t = "Off: the game starts without it. " + files;
    else
        t = "Loads " + ordinal(at + 1) + " of the " + std::to_string(l.movable()) + " mods; when two mods on have the same "
            "file, the one lower in the list wins it. " + files;
    if (m.exefs) t += " Its exefs patches are left out: Hookshot compiles the game's code ahead of time.";
    return t;
}
/// The line set off under the help: the mods on that share files with this one, and whose files load (empty: none)
template <class Shared>
std::string clash_text(const List& l, int at, Shared&& shared) {
    const std::vector<Clash> c = clashes(l, at, shared);
    std::string t;
    const int said = (int)std::min<size_t>(c.size(), 4);
    for (int i = 0; i < said; i++) {
        const Clash& k = c[i];
        if (!t.empty()) t += " ";
        t += std::to_string(k.files) + (k.files == 1 ? " file is" : " files are") + " also in " + label(l, k.other) +
             (k.wins ? ", higher in the list: this mod's load." : ", lower in the list: its load instead.");
    }
    if ((int)c.size() > said) t += " And " + std::to_string((int)c.size() - said) + " more mods share files with it.";
    return t;
}

} // namespace mkwvk::mods_page
