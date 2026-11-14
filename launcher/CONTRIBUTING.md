# Contributing to the Longshot Launcher

The launcher installs [Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot)'s builder, builds the game on the
player's PC from their own copy, starts it, keeps it and itself up to date, and moves saves. The game, its builder and
their releases live in Longshot's repository; this one holds the launcher, its tests and its own releases. It lives on the
team's Forgejo, [git.magicbean.dev/MagicBeanDev/LongshotLauncher](https://git.magicbean.dev/MagicBeanDev/LongshotLauncher).

## The rule with no exceptions

**No game files, keys, or anything made from them leave your PC**, as in Longshot (its
[CONTRIBUTING.md](https://git.magicbean.dev/MagicBeanDev/Longshot/src/branch/main/CONTRIBUTING.md)): no `.nup`, `romfs`,
`exefs`, `.nso`, `.nca`, `.nsp`, `.xci`, `.nsz`/`.xcz`, no title keys, no build of the game, and **no saves**. The save
tests use fake save folders made of text files (`tests/fixtures/hookshot-saves`, [docs/saves.md](docs/saves.md)); keep it that way. A screenshot of the
launcher is fine.

## Get started

```
git clone --depth 1 https://git.magicbean.dev/MagicBeanDev/LongshotLauncher.git   (jj: jj git clone --colocate --depth 1 ...)
cd LongshotLauncher
dotnet build LongshotLauncher.slnx                     (the .NET 10 SDK, Windows or Linux)
dotnet run --project App
python -I tests/test_launcher_core.py                  (the core's tests: no game, no network, no window)
python -I tests/test_release.py                        (scripts/release.py; needs the openssl command line)
```

`--depth 1` fetches the newest commit only. Pulling, branches and pull requests work as usual; `git log` past it, and cutting a
release (`scripts/release.py` counts and checks commits), need the history: `git fetch --unshallow --tags` once.

Sign in to git.magicbean.dev as for Longshot
(`python -I scripts/forge.py login` in a Longshot checkout: one sign-in covers both).

## Changes and tests

- **Tests read the source.** `tests/launcher_core` compiles `Core/` with no package; the screens' logic it can reach is
  checked there (`ScreenChecks.cs`). A change to the core comes with its check in the same pull request.
- **The release format is shared.** `scripts/release.py`, `cliff.toml`, `docs/releases.md` and `RELEASING.md` are the same
  files in Longshot's repository; a change to one goes to both. `tests/fixtures/release` holds a `SHA256SUMS` signed by
  `scripts/release.py` with a test key, which the launcher's tests check with the launcher's own code.
- **The key.** `Core/ReleaseTrust.cs` lists the public key the launcher trusts; Longshot's `scripts/release_keys.json` must
  list the same one. Never commit a private key (the test key in `tests/fixtures/release` is public on purpose and is
  never trusted).
- **Packages are pinned.** `Directory.Packages.props` pins each package exactly and `packages.lock.json` records what
  they bring; CI restores in locked mode. A package change updates the lock files in the same pull request.
- **Two platforms.** Windows and Linux (and the Steam Deck) from the same code; keep paths portable and UTF-8.

## Commits and pull requests

`main` takes reviewed pull requests only: push a branch to your fork and open the pull request from there
(`jj git push --remote forge-fork -b <branch>`, then the pull request on git.magicbean.dev, or
`fj pr create`; Longshot's [docs/forge.md](https://git.magicbean.dev/MagicBeanDev/Longshot/src/branch/main/docs/forge.md)
has the set-up).

1. One topic per pull request, on a branch named for it (`fix/...`, `feat/...`, `docs/...`).
2. The title is a [Conventional Commit](https://www.conventionalcommits.org/) (`feat(saves): ...`, `fix: ...`): it becomes
   the squash-merged commit on `main` and a line of the next release's notes.
3. Start the description with why the pull request is needed, in one or two plain sentences, then what changed and how it
   was tested. Include screenshots when the change shows on screen.
4. CI (`.forgejo/workflows/ci.yml`) compiles with warnings as errors and runs both tests.

A maintainer reviews and squash-merges it. Releases are tags on `main` ([RELEASING.md](RELEASING.md)): `vX.Y.Z-rc.N`,
then `vX.Y.Z`, and every merge makes a nightly. The title decides the next version: CI refuses a tag lower than the titles
since the last stable call for (a `!` or `BREAKING CHANGE:`: the next major; a `feat`: the next minor; anything else: the
next patch), and git-cliff turns the titles into the release notes. The launcher's numbers start at v1.0.0 and are its own.

## Licensing

The launcher is free software under the [GNU General Public License, version 3 or later](LICENSE), as Longshot is. By
submitting a change you license it under those terms. The Inter font (`App/Assets/Fonts`) keeps its own licence,
`Inter-LICENSE.txt`.
