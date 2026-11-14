# Notes for AI coding agents

The repository's [AGENTS.md](../AGENTS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md) apply here; [CONTRIBUTING.md](CONTRIBUTING.md)
has the launcher's own rules, [README.md](README.md) the layout and the commands, [docs/launcher.md](../docs/launcher.md) where
it came from (the Longshot Launcher), its releases, channels and trust.

What agents trip on:

- **Tests read the source**: run `python -I tests/test_launcher_core.py` (and `python -I ../tests/test_launcher_repository.py`)
  before a pull request, and update a check in the same pull request rather than weakening it. On this PC the checks run with
  no game, no network and no window.
- **Longshot and Hookshot are swapped** from the Longshot Launcher: here Hookshot is the product and Longshot the project saves
  are imported from. A change taken from the Longshot Launcher is adapted as docs/launcher.md says.
- **Never start a build of the game or the game itself** from the launcher in an agent's session; `tools/screens` shows every
  page without either. To look at the real window, give it its own home (`HOOKSHOT_LAUNCHER_HOME`) and `HOME`, `USERPROFILE`,
  `APPDATA` and `LOCALAPPDATA` in a scratch folder: at start it brings the saves of `~/Games/Hookshot` into the shared folder.
- **Never make or commit a real signing key.**
