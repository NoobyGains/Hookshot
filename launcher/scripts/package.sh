#!/bin/bash
# The Hookshot Launcher as a release ships it (docs/launcher.md), both from Linux with the .NET 10 SDK:
#   HookshotLauncher-<tag>-windows-x64-setup.exe     a self-contained single-file program (no .NET to install), which offers to
#                                                    install itself (or run portable) when it is first started
#   HookshotLauncher-<tag>-windows-x64-portable.zip  the same program as HookshotLauncher.exe, with its "portable" file
#   HookshotLauncher-<tag>-x86_64.AppImage           the same for Linux and the Steam Deck, in an AppImage
# Each launcher is one file, so the launcher's own update replaces one file (Core/SelfUpdate.cs; a portable one takes it out of
# the zip). The tag is stamped into the program (-p:HookshotTag), which compares it with its channel's newest; and, with
# HOOKSHOT_REPOSITORY=<owner/name> (CI: the repository it runs in), the repository whose releases it follows (-p:HookshotRepository,
# Core/Repository.cs), so a fork's launcher follows the fork.
#
#     launcher/scripts/package.sh <tag> <out folder>
#
# The AppImage is packed with the appimagetool and runtime pinned below (downloaded and checked by their SHA-256 into
# <out folder>/../.appimagetool), or APPIMAGETOOL and APPIMAGE_RUNTIME. Nothing of a game is involved.
#
# WINE_CHECK_EXE=<path> also writes there the Windows program built to unpack all of itself to disk when it starts, for CI to start
# under Wine (.github/workflows/launcher.yml): Wine cannot load the shipped program, whose code .NET maps straight from the uncompressed file
# ("Failed to load System.Private.CoreLib.dll ... Incorrect alignment (0x8007046C)"). It is the same code; it is not released.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TAG=${1:?usage: package.sh <tag> <out folder>}
OUT=${2:?usage: package.sh <tag> <out folder>}
# (the same pins as Hookshot's scripts/linux/deps.sh)
APPIMAGETOOL_VERSION=1.9.1
APPIMAGETOOL_SHA256=ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0
APPIMAGE_RUNTIME_VERSION=20251108
APPIMAGE_RUNTIME_SHA256=2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d
[[ $TAG =~ ^[0-9A-Za-z._+-]{1,128}$ ]] || { echo "not a version name: $TAG" >&2; exit 1; }
DOTNET=${DOTNET:-dotnet}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
WORK=$(mktemp -d)
# (a single-file publish for a system adds that system's runtime packs to the restore, which packages.lock.json, made for the plain
# build CI checks, does not list; the restore writes them in. The files are put back as they were: the packages themselves are
# pinned exactly in launcher/Directory.Packages.props)
locks=(App/packages.lock.json Core/packages.lock.json)
for f in "${locks[@]}"; do mkdir -p "$WORK/locks/$(dirname "$f")"; cp "$ROOT/$f" "$WORK/locks/$f"; done
cleanup() {
    for f in "${locks[@]}"; do cp "$WORK/locks/$f" "$ROOT/$f"; done
    rm -rf "$WORK"
}
trap cleanup EXIT

# (a release's MSBuild version is its tag without the v; a nightly keeps the projects' own, its tag says which it is)
version=()
repository=()
if [ -n "${HOOKSHOT_REPOSITORY:-}" ]; then
    [[ $HOOKSHOT_REPOSITORY =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || { echo "not owner/name: $HOOKSHOT_REPOSITORY" >&2; exit 1; }
    repository=(-p:HookshotRepository="$HOOKSHOT_REPOSITORY")
fi
if [[ $TAG =~ ^v([0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?)$ ]]; then version=(-p:Version="${BASH_REMATCH[1]}"); fi

publish() {
    local rid=$1 dir=$2
    shift 2
    "$DOTNET" publish "$ROOT/App/HookshotLauncher.csproj" -c Release -r "$rid" --self-contained "$@" \
        -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=none \
        -p:HookshotTag="$TAG" "${version[@]}" "${repository[@]}" -o "$dir" -nologo
}

# (not compressed inside: a compressed single file unpacks its code into memory when it starts, which antivirus programs'
# machine-learning checks take for a packed dropper: Windows flagged the launcher as a virus. The setup is about twice the size,
# 106 MB rather than 51; the portable zip is the same, 45 MB. The AppImage is compressed by its own format)
publish win-x64 "$WORK/win-x64"
cp "$WORK/win-x64/HookshotLauncher.exe" "$OUT/HookshotLauncher-$TAG-windows-x64-setup.exe"
if [ -n "${WINE_CHECK_EXE:-}" ]; then
    publish win-x64 "$WORK/win-x64-wine" -p:IncludeAllContentForSelfExtract=true
    mkdir -p "$(dirname "$WINE_CHECK_EXE")"
    cp "$WORK/win-x64-wine/HookshotLauncher.exe" "$WINE_CHECK_EXE"
fi
# (the portable zip: the program under its own name and the "portable" file beside it; the same dates in every build)
mkdir -p "$WORK/portable"
cp "$WORK/win-x64/HookshotLauncher.exe" "$WORK/portable/HookshotLauncher.exe"
printf 'This file makes the Hookshot Launcher beside it portable: its data stays in the HookshotLauncher-data folder here.\r\n' \
    > "$WORK/portable/portable"
python3 -I - "$WORK/portable" "$OUT/HookshotLauncher-$TAG-windows-x64-portable.zip" <<'PY'
import sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in ("HookshotLauncher.exe", "portable"):
        info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        with open(src + "/" + name, "rb") as f:
            z.writestr(info, f.read())
PY

publish linux-x64 "$WORK/linux-x64"
app="$WORK/AppDir"
mkdir -p "$app/usr/bin"
cp "$WORK/linux-x64/HookshotLauncher" "$app/usr/bin/HookshotLauncher"
cp "$ROOT/App/Assets/hookshot.png" "$app/hookshot-launcher.png"
cat > "$app/hookshot-launcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Hookshot
Comment=Install Hookshot's builder, build the game from your own copy, and play
Exec=HookshotLauncher
Icon=hookshot-launcher
Categories=Game;
Terminal=false
StartupWMClass=hookshot-launcher
EOF
cat > "$app/AppRun" <<'EOF'
#!/bin/sh
here=$(dirname "$(readlink -f "$0")")
exec "$here/usr/bin/HookshotLauncher" "$@"
EOF
chmod 755 "$app/AppRun" "$app/usr/bin/HookshotLauncher"
"$app/usr/bin/HookshotLauncher" --self-check | grep -qxF "HookshotLauncher $TAG" ||
    { echo "the Linux launcher does not answer --self-check with $TAG" >&2; exit 1; }

tool=${APPIMAGETOOL:-}
runtime=${APPIMAGE_RUNTIME:-}
if [ -z "$tool" ] || [ -z "$runtime" ]; then
    tools="$OUT/../.appimagetool"
    mkdir -p "$tools"
    tool="$tools/appimagetool-$APPIMAGETOOL_VERSION"
    runtime="$tools/runtime-x86_64-$APPIMAGE_RUNTIME_VERSION"
    [ -f "$tool" ] || curl -fsSL --retry 5 -o "$tool" \
        "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-x86_64.AppImage"
    [ -f "$runtime" ] || curl -fsSL --retry 5 -o "$runtime" \
        "https://github.com/AppImage/type2-runtime/releases/download/$APPIMAGE_RUNTIME_VERSION/runtime-x86_64"
    printf '%s  %s\n%s  %s\n' "$APPIMAGETOOL_SHA256" "$tool" "$APPIMAGE_RUNTIME_SHA256" "$runtime" | sha256sum -c - >&2
    chmod 755 "$tool"
fi
# (no update information: the launcher updates itself from its release's checked files, not with AppImageUpdate)
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$tool" --no-appstream --runtime-file "$runtime" "$app" \
    "$OUT/HookshotLauncher-$TAG-x86_64.AppImage" >&2
chmod 755 "$OUT/HookshotLauncher-$TAG-x86_64.AppImage"
ls -l "$OUT"
