# Saves

What the launcher does with your saves: where Longshot keeps them (one place, shared by every build), importing them from
emulators and from Hookshot, and exporting them. Everything is on the **Saves** page (the *Saves* link on the home, under
the default version). Every copy backs up the save it replaces first, and every copy is refused while Longshot, Hookshot or
an emulator is running, since a running game can write its save again and undo the copy.

The save files are the same in Longshot, Hookshot and the emulators and ports that run the game: `account.sav`,
`option.sav` and one `slot_NN` folder per slot holding `progress.sav` and `caption.sav`. Longshot's own saves guide,
[docs/saves.md in Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot/src/branch/main/docs/saves.md), has the format,
where every emulator keeps its saves, and `scripts/oot_saves.py import|export`, the command line that does what this page
does (for Lichii, Eden, NX2navi and the rest) without the launcher.

## Where Longshot keeps them

| | Where |
|---|---|
| Linux and Steam Deck | `$XDG_DATA_HOME/longshot/save/<user id>/` (default `~/.local/share/longshot/save/`) |
| Windows | `%APPDATA%\Longshot\save\<user id>\`; a portable launcher's in `LongshotLauncher-data\user\save\` beside it |

Every build uses the same saves, on both systems, so a new build or an update starts where you left off, and there is nothing
to copy between builds. On Linux the game finds that folder by itself. On Windows the launcher starts every build with
`--user <that folder>`; a build started on its own (`bin\longshot.exe` double-clicked) still keeps its saves in its own
folder's `user\`, and the launcher brings them in at its next start (below).

Backups go to `%LOCALAPPDATA%\Longshot\oot-save-backups` on Windows and `$XDG_DATA_HOME/oot-save-backups` on Linux, one
folder per copy, named by the time it was made.

## Saves from before (Windows)

Windows builds used to keep their saves each in its own game folder (`<build folder>\user\save\`), and the 2.x Builder's game
in `%USERPROFILE%\Games\Longshot\user\save\`. When the launcher opens, and before it starts a game, it brings those into the
shared folder by itself (`Saves.Gather`):

- **Where it looks:** every build in its list, every Longshot game folder in the builds folder (a version an update replaced
  is no longer listed, but its saves may still be there), and the 2.x Builder's game folder (not for a portable launcher).
- **The newest one is kept.** Of all of them, the shared one included, the save whose newest file was written last becomes
  the shared save; on a tie the shared one stays.
- **Every one is backed up first,** whole, in one folder: `oot-save-backups\gather-<yyyyMMdd-HHmmss>\<game folder name>`
  (`shared` for the one that was already shared). The home says once which save was kept and where the backup is.
- **Nothing is deleted.** Each old `save` folder is renamed `save.moved-<yyyyMMdd-HHmmss>` beside it, so the game no longer
  finds it there.
- **Never while Longshot runs:** the next start tries again. A failure changes nothing and says why.

## Importing

### From an emulator

**Import from emulator** lists the emulators whose saves were found on this PC (Lichii, Eden, Eglantine, Orchid,
PokeDinner, Frizti, NX2navi), with their slots and when they were saved, and copies the one you pick into Longshot's. A
save somewhere else (a portable install, a copy on another drive) is picked with *Choose a folder*. You can import before
starting Longshot for the first time: the launcher creates the save folder for the player Longshot uses. The destination
is always that player's folder, the only one the game opens; another profile folder beside it (a stray one, or a copy
made by hand) is left alone.

The home also offers to import when it finds NX2navi saves. **Import…** opens the emulator picker with NX2navi selected;
pick a profile if there is more than one, then check the source and destination before confirming. **Not now** or a
successful import stops this offer; cancelling leaves it available. The Hookshot offer is remembered separately.
The original saves stay where they are.

NX2navi keeps saves in `<game folder>/profile/save/<account>/`. The launcher looks in
`%LOCALAPPDATA%\Programs\NX2navi\game` and `C:\Games\Ocarina` on Windows, and `~/Games/Ocarina` on Linux.
For portable installs, a custom game folder or an installation on another drive, use **Choose a folder**.

NX2navi writes a save to `profile/save-tx` first. A finished one waiting there (`save-tx/ready-<n>`) is the save it loads
at its next start, so a copy from or to NX2navi is refused until NX2navi has been started and quit once. The rest of
`save-tx` is not a save in waiting and is ignored: `work` (the working copy NX2navi leaves after a quit), `new` and `old`.
A completed import from NX2navi's menu waiting in `profile/save-import` also blocks the copy: that is what NX2navi will
load on its next start. An unfinished `save-import.part` is ignored.

A copy that worked says so: the page that follows names what was copied and where the backup went, and the Saves page
says it again, briefly, when you go back to it.

### From Hookshot

[Hookshot](https://github.com/NotRexed/Hookshot) is the project Longshot was forked from. Its game writes the same save
files in the same layout, so a Hookshot save carries on in Longshot. `Core/HookshotSaves.cs` does the save import.
Compatible game settings have their own import below; the launcher's settings, channels, versions, caches and updates
are not brought over.

It only happens when you ask. **Saves > Import from Hookshot…** opens it, and the home offers it once when Hookshot saves
are found (**Import…** or **Not now**; either answer stops the offer).

**Where it looks.** These places come from Hookshot's source (its `host/nn_fs.c` save root, `scripts/oot_saves.py`, the
2.x Builders' default game folder and its 3.0 launcher's builds folder):

| | Where |
|---|---|
| Linux | `$XDG_DATA_HOME/hookshot/save/<user id>/` (default `~/.local/share/hookshot`): every Hookshot build shares it |
| Windows | `<game folder>\user\save\<user id>\`. The game folder is `%USERPROFILE%\Games\Hookshot` by default, and the version folders Hookshot's launcher made under it are searched too |

For any other place (a portable install, `--user <folder>`, a copy on another drive), use **Choose a folder…** and pick
either the save folder itself or a folder that holds one, such as a Hookshot game folder.

**What is checked.** Before anything is copied, the folder must hold only save files:

- only `account.sav`, `option.sav` and `slot_NN` folders, with nothing else in them;
- no links;
- no empty file, and no file larger than 4 MB;
- at least one slot, with a `progress.sav` in each.

The window lists each save it found, with its slots and when they were last saved. If a save cannot be imported, it says
why.

**What the copy does.**

- **It copies; Hookshot keeps its saves as they were.** Nothing in Hookshot's folders is moved, changed or deleted.
- **Where it goes:** the save folder of Longshot's player (`5a3c9e1f0b7d24680000000000000001`), the only one the game
  opens, whether it is there yet or not. Another profile folder beside it is left alone.
  - In the shared folder above: `$XDG_DATA_HOME/longshot/save/` on Linux, `%APPDATA%\Longshot\save\` on Windows.
- **It never replaces a Longshot save without asking.** When Longshot already has a save there, the window asks first. If
  you say yes, Longshot's save is copied whole to the backup folder before anything is replaced, and the message says
  where the backup is.
- **Nothing is converted.** The save files name no path, folder or program, and Longshot reads Hookshot's format as it
  is, so the files are copied byte for byte.

### Hookshot's game settings

The save import already includes `option.sav`: the game's own options, such as camera and text speed. To also bring over
Hookshot's graphics, controls and game language, choose **Import graphics and controls…** in the Hookshot import window.
This is a separate copy, with its own confirmation and backup.

Choose Hookshot's **game folder** and an installed Longshot version. These settings belong to that build, while saves
are shared. If no Longshot build is installed yet, import the saves now and return for these settings after building the
game. On Linux, Hookshot's shared save folder does not identify its game folder: choose the game folder yourself.

The settings of `hookshot_options.ini` whose format is compatible with Longshot are written into the build's
`longshot_options.ini`: each replaces the same setting's line, or is added at the end. Every other line of that file stays
as it was, such as Compile shaders (`compile_shaders`), V-Sync, the memory budgets, Auto (this PC)'s choices and the
ocarina note bindings. Keys Longshot does not know, and values outside the range of Longshot's menu, are skipped and
listed (Longshot would clamp such a value on load anyway); when a key appears more than once, its last line decides, as in
the game. The file keeps Hookshot's `options_version` (none, when Hookshot's file has none), so Longshot updates Hookshot's
old settings as it would Hookshot's own file. A few of the build's own lines that Longshot reads by that version (Game
speed, Descriptor reuse, Menu shortcut, Aspect ratio, and the Y and ZL keys) are removed when the versions differ for them:
those take Longshot's default. An empty `longshot_options.ini` is filled without asking. `language.txt` is copied when present and recognized; when the
launcher has a game language set (Settings), it becomes the imported one too, since each update writes the launcher's
language into `language.txt`. Existing destination files are backed up whole before they change. The original Hookshot files are never changed. A failed write restores the
destination files; if restoration also fails, the error gives the backup location or identifies the incomplete new files.
The copy is refused while a game or emulator is running, or when a settings file itself is a link. A game or backup
folder reached through a link (a symlinked `~/Games`, a folder in OneDrive) is fine: the paths are compared once resolved.

This does not import shader caches, `env.txt`, launcher or builder preferences, or the legacy `present.txt` and
`mouse_sens.txt` files. It does not change how other installed Longshot builds are configured.

## Exporting

**Export to emulator** copies the build's save into an emulator's save folder (the same emulators as the import), or into
any folder you pick with *Choose a folder*. The emulator's save is backed up first, as for every copy. The launcher does
not export to Hookshot.

To keep a copy of your saves yourself, copy the save folder from the table at the top of this page. Copy it while the game
is closed.

## Tests

The launcher's tests use no real save and nothing from the game:

- `tests/launcher_core/HookshotChecks.cs` runs on fake save folders in `tests/fixtures/hookshot-saves`, made of one-line
  text files.
- The save checks in `tests/launcher_core` follow the cases of Longshot's `tests/test_oot_saves.py`.
- `HookshotSettingsChecks.cs` uses authored INI and language text, including the merge into an existing
  `longshot_options.ini`, replacement backups, failed writes, restoration, skipped values and linked paths.

Settings compatibility was compared on 2026-11-13 against Hookshot
[`363038d8`](https://github.com/brunobaccari/Hookshot/tree/363038d8903009d8ef06a6f6df87c7c5bde370e1)
(`gpu/vk/vk_menu.cpp`, `upscaler_rows.h`, `host/nn_hid.c`) and Longshot `d9648863`. Hookshot writes `options_version=4`;
the import preserves that marker, or its absence, so Longshot applies its own migrations, and removes the build's lines
that those migrations would read differently (`HookshotSettings.Merge`). Earlier markers 0–3 are accepted using
Longshot's legacy reader, but every historical Hookshot release has not been tested. Later versions are refused until
their schema is checked; unknown keys and values out of range are listed and skipped.

The first-import destination is `5a3c9e1f0b7d24680000000000000001`. This comes from Longshot's fixed `user_uid` in
`host/nn_applet.c` and the high-word/low-word folder name in `host/nn_fs.c`, checked against Longshot `d9648863` on 2026-11-13.
If Longshot adds selectable players, this destination rule must follow that change. Tests use text fixtures with different
source profile IDs, and a stray Longshot profile folder, to check that an imported save lands in the folder the game
actually opens. The core test runner's
`--longshot` check also compares the destination ID with Longshot's source.
