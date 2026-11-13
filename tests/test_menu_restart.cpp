// The Insert menu's rows that take a restart (gpu/vk/menu_restart.h): what is pending, when closing the menu asks to
// restart, and the names the menu lists; the mods a restart would switch, by name, and the restart line's forms.
#include "../gpu/vk/menu_restart.h"

#include <cstdio>

#define CHECK(name, condition) do { if (!(condition)) { std::fprintf(stderr, "FAIL %s at line %d\n", name, __LINE__); return 1; } } while (0)

int main() {
    namespace mr = mkwvk::menu_restart;
    const char* names[] = {"GPU device", "Output resolution", "Profile", "Aspect ratio", "Robust buffers"};
    mr::State st;
    // (the five rows as the game started: Auto, 2048x1152, Off, 16:9, Auto)
    int now[5] = {0, 0, 0, 0, 0};
    for (int v : now) CHECK("a slot each", st.add(v) >= 0);
    CHECK("five slots", st.n == 5);
    CHECK("nothing pending at the start", st.pending(now) == 0 && !st.ask(now));

    // a change: pending, asked at the close
    now[1] = 1;
    st.note(now);
    CHECK("Output resolution pending", st.pending(now) == 2u);
    CHECK("asked at the close", st.ask(now));
    // changed back: nothing pending, not asked
    now[1] = 0;
    st.note(now);
    CHECK("changed back: nothing pending", st.pending(now) == 0 && !st.ask(now));

    // Later: not asked again for the same values
    now[1] = 2, now[3] = 1;
    st.note(now);
    CHECK("two pending", st.pending(now) == (2u | 8u) && st.ask(now));
    st.choose_later(now);
    CHECK("Later: still pending", st.pending(now) == (2u | 8u));
    CHECK("Later: not asked again", !st.ask(now) && !st.ask(now));
    // ... until something changes: then asked again, even once it is back to the values Later was chosen for
    now[3] = 0;
    st.note(now);
    CHECK("Later, then a change: asked", st.ask(now));
    now[3] = 1;
    st.note(now);
    CHECK("changed back to Later's values: still asked", st.ask(now));
    st.choose_later(now);
    CHECK("Later again", !st.ask(now));
    now[1] = 1;   // (a change seen only at the close, not through note)
    CHECK("a change seen at the close: asked", st.ask(now));
    // Later with everything back as it started: nothing to ask, and a new change asks
    now[1] = 0, now[3] = 0;
    st.choose_later(now);
    now[4] = 2;
    st.note(now);
    CHECK("Later with nothing pending, then a change: asked", st.ask(now));

    // the GPU row's start value comes once the cards are counted
    mr::State gpu;
    int g[1] = {3};
    gpu.add(0);
    gpu.restart_value(0, 3);
    CHECK("the GPU's start value again", gpu.pending(g) == 0 && !gpu.ask(g));
    gpu.restart_value(4, 1);   // (no such slot: nothing)
    CHECK("a slot past the rows", gpu.start[0] == 3);
    mr::State full;
    for (int i = 0; i < mr::kMax; i++) full.add(0);
    CHECK("no slot past kMax", full.add(0) == -1);

    // the names, in the rows' order
    CHECK("one name", mr::names(names, 5, 2u) == "Output resolution");
    CHECK("two names", mr::names(names, 5, 2u | 8u) == "Output resolution, Aspect ratio");
    CHECK("the question's", mr::names(names, 5, 2u | 8u, ", ", " and ") == "Output resolution and Aspect ratio");
    CHECK("three, the question's", mr::names(names, 5, 1u | 2u | 16u, ", ", " and ") == "GPU device, Output resolution and Robust buffers");
    CHECK("none", mr::names(names, 5, 0).empty());

    // the Mods tab: what a restart would change, by the mods' names (the list's order now) with On or Off, and the order
    using Mods = std::vector<mr::Mod>;
    using Texts = std::vector<std::string>;
    const Mods start = {{"Textures", true}, {"Randomizer", false}, {"Music", true}};
    mr::ModChanges ch = mr::mod_changes(start, start, "On", "Off");
    CHECK("the mods as they started: nothing", ch.switched.empty() && !ch.moved);
    ch = mr::mod_changes(start, {{"Textures", true}, {"Randomizer", false}, {"Music", false}}, "On", "Off");
    CHECK("one mod off", ch.switched == Texts{"Music (Off)"} && !ch.moved);
    ch = mr::mod_changes(start, {{"Textures", false}, {"Randomizer", true}, {"Music", true}}, "On", "Off");
    CHECK("one off, one on", ch.switched == (Texts{"Textures (Off)", "Randomizer (On)"}) && !ch.moved);
    ch = mr::mod_changes(start, {{"Randomizer", false}, {"Textures", true}, {"Music", true}}, "On", "Off");
    CHECK("the order alone", ch.switched.empty() && ch.moved);
    ch = mr::mod_changes(start, {{"Music", false}, {"Textures", true}, {"Randomizer", true}}, "On", "Off");
    CHECK("moved and switched: in the list's order now", ch.switched == (Texts{"Music (Off)", "Randomizer (On)"}) && ch.moved);
    ch = mr::mod_changes(start, {{"Textures", false}, {"Randomizer", false}, {"Music", true}}, "Ligado", "Desligado");
    CHECK("the switch's words are the menu's", ch.switched == Texts{"Textures (Desligado)"});

    // the restart line's forms, the fullest first (the menu shows the first that fits)
    const Texts two = {"Output resolution", "Profile"};
    CHECK("rows alone: as before", mr::line_forms(two, "2 settings", "", "") ==
                                       (Texts{"Output resolution, Profile", "Output resolution and 1 more", "2 settings"}));
    CHECK("one mod alone: by name, then counted", mr::line_forms({}, "", "Music (Off)", "1 mod") == (Texts{"Music (Off)", "1 mod"}));
    CHECK("two mods alone: counted", mr::line_forms({}, "", "", "2 mods") == Texts{"2 mods"});
    CHECK("the order alone", mr::line_forms({}, "", "the mods' order", "") == Texts{"the mods' order"});
    CHECK("rows and mods: the mods after the rows, as a group",
          mr::line_forms(two, "2 settings", "", "2 mods") ==
              (Texts{"Output resolution, Profile, 2 mods", "Output resolution and 1 more, 2 mods", "2 settings, 2 mods"}));
    CHECK("rows and one mod: its name while it fits, the count before a row gives way",
          mr::line_forms({"Profile"}, "1 setting", "Music (Off)", "1 mod") ==
              (Texts{"Profile, Music (Off)", "Profile, 1 mod", "1 setting, Music (Off)", "1 setting, 1 mod"}));
    // the texts joined as the rows' names are
    const Texts three = {"Output resolution", "Music (Off)", "the mods' order"};
    CHECK("joined for the line", mr::list(three, 3) == "Output resolution, Music (Off), the mods' order");
    CHECK("joined for the question", mr::list(three, 3, ", ", " and ") == "Output resolution, Music (Off) and the mods' order");
    CHECK("the first two", mr::list(three, 2, ", ", " and ") == "Output resolution and Music (Off)");
    CHECK("one, none, and past the end", mr::list(three, 1) == "Output resolution" && mr::list(three, 0).empty() &&
                                             mr::list(three, 9) == mr::list(three, 3));
    std::puts("menu restart: all checks passed");
}
