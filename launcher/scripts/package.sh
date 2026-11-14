#!/bin/bash
# The Longshot Launcher as a release ships it (docs/releases.md), both from Linux with the .NET 10 SDK:
#   LongshotLauncher-<tag>-windows-x64-setup.exe     a self-contained single-file program (no .NET to install), which offers to
#                                                    install itself (or run portable) when it is first started
#   LongshotLauncher-<tag>-windows-x64-portable.zip  the same program as LongshotLauncher.exe, with its "portable" file
#   LongshotLauncher-<tag>-x86_64.AppImage           the same for Linux and the Steam Deck, in an AppImage
# Each launcher is one file, so the launcher's own update replaces one file (Core/SelfUpdate.cs; a portable one takes it out of
# the zip). The tag is stamped into the program (-p:LongshotTag), which compares it with its channel's newest.
#
#     scripts/package.sh <tag> <out folder>
#
# The AppImage is packed with the appimagetool and runtime pinned below (downloaded and checked by their SHA-256 into
# <out folder>/../.appimagetool), or APPIMAGETOOL and APPIMAGE_RUNTIME. Nothing of a game is involved.
#
# WINE_CHECK_EXE=<path> also writes there the Windows program built to unpack all of itself to disk when it starts, for CI to start
# under Wine (release.yml): Wine cannot load the shipped program, whose code .NET maps straight from the uncompressed file
# ("Failed to load System.Private.CoreLib.dll ... Incorrect alignment (0x8007046C)"). It is the same code; it is not released.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TAG=${1:?usage: package.sh <tag> <out folder>}
OUT=${2:?usage: package.sh <tag> <out folder>}
# (the same pins as Longshot's scripts/linux/deps.sh)
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
if [[ $TAG =~ ^v([0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?)$ ]]; then version=(-p:Version="${BASH_REMATCH[1]}"); fi

publish() {
    local rid=$1 dir=$2
    shift 2
    "$DOTNET" publish "$ROOT/App/LongshotLauncher.csproj" -c Release -r "$rid" --self-contained "$@" \
        -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=none \
        -p:LongshotTag="$TAG" "${version[@]}" -o "$dir" -nologo
}

# (not compressed inside: a compressed single file unpacks its code into memory when it starts, which antivirus programs'
# machine-learning checks take for a packed dropper: Windows flagged the launcher as a virus. The setup is about twice the size,
# 106 MB rather than 51; the portable zip is the same, 45 MB. The AppImage is compressed by its own format)
publish win-x64 "$WORK/win-x64"
cp "$WORK/win-x64/LongshotLauncher.exe" "$OUT/LongshotLauncher-$TAG-windows-x64-setup.exe"
if [ -n "${WINE_CHECK_EXE:-}" ]; then
    publish win-x64 "$WORK/win-x64-wine" -p:IncludeAllContentForSelfExtract=true
    mkdir -p "$(dirname "$WINE_CHECK_EXE")"
    cp "$WORK/win-x64-wine/LongshotLauncher.exe" "$WINE_CHECK_EXE"
fi
# (the portable zip: the program under its own name and the "portable" file beside it; the same dates in every build)
mkdir -p "$WORK/portable"
cp "$WORK/win-x64/LongshotLauncher.exe" "$WORK/portable/LongshotLauncher.exe"
printf 'This file makes the Longshot Launcher beside it portable: its data stays in the LongshotLauncher-data folder here.\r\n' \
    > "$WORK/portable/portable"
python3 -I - "$WORK/portable" "$OUT/LongshotLauncher-$TAG-windows-x64-portable.zip" <<'PY'
import sys, zipfile
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in ("LongshotLauncher.exe", "portable"):
        info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        with open(src + "/" + name, "rb") as f:
            z.writestr(info, f.read())
PY

publish linux-x64 "$WORK/linux-x64"
app="$WORK/AppDir"
mkdir -p "$app/usr/bin"
cp "$WORK/linux-x64/LongshotLauncher" "$app/usr/bin/LongshotLauncher"
cp "$ROOT/App/Assets/longshot.png" "$app/longshot-launcher.png"
cat > "$app/longshot-launcher.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Longshot
Comment=Install Longshot's builder, build the game from your own copy, and play
Exec=LongshotLauncher
Icon=longshot-launcher
Categories=Game;
Terminal=false
StartupWMClass=longshot-launcher
EOF
cat > "$app/AppRun" <<'EOF'
#!/bin/sh
here=$(dirname "$(readlink -f "$0")")
exec "$here/usr/bin/LongshotLauncher" "$@"
EOF
chmod 755 "$app/AppRun" "$app/usr/bin/LongshotLauncher"
"$app/usr/bin/LongshotLauncher" --self-check | grep -qxF "LongshotLauncher $TAG" ||
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
# (no update information: the launcher updates itself from the signed release files, not with AppImageUpdate)
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$tool" --no-appstream --runtime-file "$runtime" "$app" \
    "$OUT/LongshotLauncher-$TAG-x86_64.AppImage" >&2
chmod 755 "$OUT/LongshotLauncher-$TAG-x86_64.AppImage"
ls -l "$OUT"
