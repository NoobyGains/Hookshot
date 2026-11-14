# Contributing to the Hookshot Launcher

The launcher lives in Hookshot's repository, and Hookshot's [CONTRIBUTING.md](../CONTRIBUTING.md) applies to it as to
everything else here, above all **its rule with no exceptions: no game files, keys, saves or anything made from them leave
your PC**. The save tests use fake save folders made of text files (`tests/fixtures/longshot-saves`); keep it that way. A
screenshot of the launcher is fine: `tools/screens` draws every page from made-up builds and saves, with none of your PC's.

What is the launcher's own:

- **Tests read the source.** `tests/launcher_core` compiles `Core/` with no package and checks it; a change to the core comes
  with its check in the same pull request. `python -I tests/test_launcher_core.py` also checks the launcher's copies of
  Hookshot's (`make_game.py`'s languages, the DLSS and FSR 4 licence commits, the player id).
- **It runs make_game.py as the builders do.** A change to `nx2/make_game.py`'s options, `@@` lines or environment changes
  `Core/MakeGameCommand.cs` and `Core/MakeGameProtocol.cs` in the same pull request.
- **One repository for releases.** `Core/Repository.cs` falls back to the builder's repository
  (`tests/test_launcher_repository.py`); the release files' names and channels are in [docs/launcher.md](../docs/launcher.md).
- **No release key yet.** Never commit a private key. The test key in `tests/fixtures/release` is public on purpose and is
  never trusted.
- **Packages are pinned.** `Directory.Packages.props` pins each package exactly and `packages.lock.json` records what they
  bring; CI restores in locked mode. A package change updates the lock files in the same pull request.
- **Two platforms.** Windows and Linux (and the Steam Deck) from the same code; keep paths portable and UTF-8.
- **Every text the window shows is translated** through `Tr` and `Core/Lang/<code>.json` (`python -I scripts/translations.py`).
- **It is the Longshot Launcher's code.** A change worth having there too can go to the Magic Bean team as well; one taken from
  there is adapted as [docs/launcher.md](../docs/launcher.md) says.

The launcher is free software under the [GNU General Public License, version 3 or later](LICENSE). The fonts keep their own
licences (`App/Assets/Fonts/Inter-LICENSE.txt`, `../assets/brand/fonts/OFL-*.txt`).
