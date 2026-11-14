"""The launcher's core library (Core/): tests/launcher_core compiles its sources and checks them over authored inputs, with
no game, no network and no window. The version vectors (TRACKS, ORDER, UNORDERED) are this file's own; the signed release files
are tests/fixtures/release's (made by scripts/release.py). Its scratch folder is named "ゲーム Zélda 🎮", as tests/test_utf8_paths.py's.

    python -I tests/test_launcher_core.py [--dotnet <dotnet>] [--strict] [--hookshot <checkout of MagicBeanDev/Hookshot>]

With --hookshot it also checks what the launcher copies from Hookshot: make_game.py's languages, the SDK commits the DLSS and
FSR 4 licence texts name, and the first-import player ID (CI checks out Hookshot's main for it).

With no dotnet here the check is skipped (exit 0, saying why), unless --strict.
"""
import argparse
import ast
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_ARGS = ["--dotnet", "{dotnet}"]


# The version order the launcher keeps (Core/Versions.cs, docs/releases.md): (version, channel). Hookshot's versions
# start at v3.0.0: what came before is no version, on no track
TRACKS = [
    ("v3.0.0", "stable"), ("v3.1.0", "stable"), ("v10.0.0", "stable"),
    ("v3.1.0-rc.1", "rc"), ("v3.1.0-rc.12", "rc"),
    ("nightly-2029-c544828f", "nightly"), ("nightly-2029-c544828f-dirty", "nightly"), ("nightly-1-00000000", "nightly"),
    # (not a nightly's name: the count, then 8 lowercase hex; nor git describe's, nor a version before 3.0.0)
    ("nightly-2029", "stable"), ("nightly-2029-c544828", "stable"), ("nightly-2029-C544828F", "stable"),
    ("nightly-x-c544828f", "stable"), ("nightly-1234567890-c544828f", "stable"),
    ("v3.1.0-rc.1-3-g1a2b3c4", "stable"), ("v2.1.0-rc.1", "stable"), ("v2.0.7", "stable"),
]
# newer, older (semver: a release candidate before its release, rc.N by number; nightlies by their count, a changed
# checkout after the build of its commit)
ORDER = [
    ("v3.1.0-rc.2", "v3.1.0-rc.1"), ("v3.1.0-rc.10", "v3.1.0-rc.9"), ("v3.1.0", "v3.1.0-rc.2"), ("v3.1.0-rc.1", "v3.0.14"),
    ("v3.0.10", "v3.0.9"), ("v4.0.0-rc.1", "v3.9.9"), ("v10.0.0", "v9.0.0"),
    ("nightly-2030-0a1b2c3d", "nightly-2029-c544828f"), ("nightly-10000-aaaaaaaa", "nightly-9999-bbbbbbbb"),
    ("nightly-2029-c544828f-dirty", "nightly-2029-c544828f"),
]
# neither newer than the other: a nightly and a release or release candidate (a nightly's name has no version in it), the
# numbers before 3.0.0 and git describe's names, and a name that is no version
UNORDERED = [
    ("nightly-2029-c544828f", "v3.1.0"), ("nightly-2029-c544828f", "v3.1.0-rc.3"), ("nightly-1-aaaaaaaa", "v3.0.1"),
    ("v3.1.0", "v2.9.0"), ("v3.0.0", "v2.2.0-rc.1"), ("v3.1.0-rc.3-248-gc544828f", "v3.1.0"),
    ("nightly-2029-c544828f", "dev"), ("v3.1.0", "dev"), ("nightly-2029-c544828f", "nightly"),
]

def vectors():
    return {"tracks": TRACKS, "order": ORDER, "unordered": UNORDERED}


def check_languages(hookshot):
    """Core/Languages.cs lists Hookshot's make_game.py LANGUAGES, in its order (the codes --language takes)"""
    tree = ast.parse((hookshot / "nx2" / "make_game.py").read_text(encoding="utf-8"))
    want = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "LANGUAGES")
    source = (ROOT / "Core" / "Languages.cs").read_text(encoding="utf-8")
    body = source[source.index("All = new[]"):source.index("};", source.index("All = new[]"))]
    have = re.findall(r'\("([^"]+)", "([^"]+)"\)', body)
    if have != [tuple(x) for x in want]:
        raise SystemExit("Core/Languages.cs differs from make_game.py's LANGUAGES:\n%s\n%s" % (have, want))


def check_licences(hookshot):
    """The DLSS and FSR 4 licences the launcher shows before a build fetches the SDKs link the commits scripts/ngx_sdk.py and
    scripts/ffx_sdk.py fetch (CONTRIBUTING.md: a change to the pinned release changes the licence text the player accepts)"""
    source = (ROOT / "App" / "ViewModels" / "SettingsStepViewModel.cs").read_text(encoding="utf-8")
    for script in ("ngx_sdk.py", "ffx_sdk.py"):
        tree = ast.parse((hookshot / "scripts" / script).read_text(encoding="utf-8"))
        commit = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
                      and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "COMMIT")
        if commit not in source:
            raise SystemExit("App/ViewModels/SettingsStepViewModel.cs's licence text does not name scripts/%s's COMMIT %s"
                             % (script, commit))


def check_save_user(hookshot):
    """A first import must use the player the game opens, not the emulator's profile ID."""
    host = (hookshot / "host" / "nn_applet.c").read_text(encoding="utf-8")
    uid = re.search(r"user_uid\[2\]\s*=\s*\{\s*0x([0-9a-fA-F]+)ULL,\s*0x([0-9a-fA-F]+)ULL\s*\}", host)
    if uid is None:
        raise SystemExit("Hookshot's user_uid changed: review the first-import save destination.")
    expected = f"{int(uid[2], 16):016x}{int(uid[1], 16):016x}"
    source = (ROOT / "Core" / "Saves.cs").read_text(encoding="utf-8")
    if f'UserId = "{expected}"' not in source:
        raise SystemExit("Core/Saves.cs's UserId differs from Hookshot's player: " + expected)


def check_translations():
    """The catalogs' texts are the window's, with their placeholders and plural forms (scripts/translations.py). A text a catalog
    lacks shows in English: said, not a failure"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import translations
    _, faults, lacking = translations.check()
    for code, texts in lacking.items():
        if texts:
            print("translations: Core/Lang/%s.json lacks %d texts (they show in English)" % (code, len(texts)))
    if faults:
        raise SystemExit("translations (python -I scripts/translations.py):\n" + "\n".join(faults[:40]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--hookshot", type=Path, default=None)
    args = parser.parse_args()
    check_translations()
    if args.hookshot:
        check_languages(args.hookshot)
        check_licences(args.hookshot)
        check_save_user(args.hookshot)
    elif args.strict:
        raise SystemExit("--strict needs --hookshot <checkout of MagicBeanDev/Hookshot>")
    dotnet = args.dotnet or shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet")
                                                       if (Path.home() / ".dotnet" / "dotnet").is_file() else None)
    if not dotnet:
        if args.strict:
            raise SystemExit("no dotnet found (pass --dotnet)")
        print("skipped: no dotnet here (pass --dotnet <path>)")
        return
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
    if not env.get("DOTNET_ROOT") and os.path.isabs(dotnet):
        env["DOTNET_ROOT"] = os.path.dirname(os.path.realpath(dotnet))
    with tempfile.TemporaryDirectory(prefix="launcher-core-") as folder:
        root = Path(folder)
        (root / "vectors.json").write_text(json.dumps(vectors(), ensure_ascii=False), encoding="utf-8")
        out = root / "build"
        subprocess.run([dotnet, "build", str(ROOT / "tests" / "launcher_core" / "LauncherCoreTests.csproj"), "--configuration", "Release",
                        "--artifacts-path", str(out), "--disable-build-servers", "-nologo", "-v:q"], cwd=root, env=env, check=True)
        dll = next((out / "bin").rglob("LauncherCoreTests.dll"))
        scratch = root / "ゲーム Zélda 🎮"
        subprocess.run([dotnet, str(dll), str(root / "vectors.json"), str(ROOT / "tests" / "fixtures"), str(scratch)],
                       cwd=root, env=env, check=True, timeout=300)


if __name__ == "__main__":
    sys.exit(main())
