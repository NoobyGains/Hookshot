# Fake Hookshot saves

For `tests/launcher_core/HookshotChecks.cs` (the Hookshot save importer, `Core/HookshotSaves.cs`, [docs/saves.md](../../../docs/saves.md)). **No real save and nothing
from the game is here**: every file holds one line of text that says it is a fake. The folders are laid out as Hookshot lays
out its saves:

- `linux/hookshot/save/<user id>/`: `$XDG_DATA_HOME/hookshot` on Linux (the test points XDG_DATA_HOME at `linux/`).
- `windows/Games/Hookshot/user/save/<user id>/` and `windows/Games/Hookshot/v3.0.0/user/save/<user id>/`: Hookshot's
  default game folder on Windows and a version folder under it (the test points HOME at `windows/`).
- `broken/<user id>/`: what the importer must refuse: an empty `account.sav`, a slot without `progress.sav`, a file that is
  no save file.
