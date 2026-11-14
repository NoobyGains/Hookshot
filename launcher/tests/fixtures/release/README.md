# A signed release for the tests

`test-key.pem` is a **test key, not the release key**: it is public on purpose, and the launcher never trusts it
(`tests/test_release.py` checks that `ReleaseKeys.BuiltIn` does not list it). `SHA256SUMS` and `SHA256SUMS.sig` are a
release's checksums and their signature, made with it by `scripts/release.py`, which `tests/launcher_core` checks with the
launcher's own code, so both sides keep one format. The files they name were the bytes `not a launcher\n`
(`LongshotLauncher-v1.0.0-x86_64.AppImage`) and `MZ not a launcher\n` (`LongshotLauncher-v1.0.0-windows-x64.exe`).

Made with:

```
printf 'not a launcher\n' > files/LongshotLauncher-v1.0.0-x86_64.AppImage
printf 'MZ not a launcher\n' > files/LongshotLauncher-v1.0.0-windows-x64.exe
python -I scripts/release.py sums files/* --out SHA256SUMS
python -I scripts/release.py sign SHA256SUMS --key test-key.pem --out SHA256SUMS.sig
```
