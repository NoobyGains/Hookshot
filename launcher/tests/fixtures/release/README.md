# A signed release for the tests

`test-key.pem` is a **test key, not a release key**: it is public on purpose, and the launcher never trusts it. Hookshot's
releases are not signed yet, so the launcher has no release key built in (`Core/ReleaseTrust.cs`); this signed release keeps
the signature check working for the day one is. `SHA256SUMS` and `SHA256SUMS.sig` are a release's checksums and their
signature (base64 of the DER ECDSA P-256 signature of `SHA256SUMS`'s exact bytes), which `tests/launcher_core` checks with
the launcher's own code. The files they name were the bytes `not a launcher\n` (`HookshotLauncher-v1.0.0-x86_64.AppImage`)
and `MZ not a launcher\n` (`HookshotLauncher-v1.0.0-windows-x64.exe`).

Made with (any shell with Python 3 and openssl; the Longshot Launcher made its own with its `scripts/release.py`):

```
python -I -c "import hashlib; f=[('HookshotLauncher-v1.0.0-windows-x64.exe', b'MZ not a launcher\n'), ('HookshotLauncher-v1.0.0-x86_64.AppImage', b'not a launcher\n')]; open('SHA256SUMS', 'wb').write(b''.join(('%s  %s\n' % (hashlib.sha256(d).hexdigest(), n)).encode() for n, d in f))"
openssl dgst -sha256 -sign test-key.pem SHA256SUMS | base64 -w0 > SHA256SUMS.sig && echo >> SHA256SUMS.sig
```
