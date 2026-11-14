# Fake Longshot saves

For `tests/launcher_core/LongshotChecks.cs` (the Longshot save importer, `Core/LongshotSaves.cs`, [docs/saves.md](../../../docs/saves.md)). **No real save and nothing
from the game is here**: every file holds one line of text that says it is a fake. The folders are laid out as Longshot lays
out its saves:

- `linux/longshot/save/<user id>/`: `$XDG_DATA_HOME/longshot` on Linux (the test points XDG_DATA_HOME at `linux/`).
- `windows/Roaming/Longshot/save/<user id>/`: `%APPDATA%\Longshot`, the folder the Longshot Launcher starts every build with
  (the test points APPDATA at `windows/Roaming`).
- `windows/Games/Longshot/user/save/<user id>/` and `windows/Games/Longshot/v3.0.0/user/save/<user id>/`: Longshot's
  default game folder on Windows and a version folder under it (the test points HOME at `windows/`).
- `broken/<user id>/`: what the importer must refuse: an empty `account.sav`, a slot without `progress.sav`, a file that is
  no save file.
