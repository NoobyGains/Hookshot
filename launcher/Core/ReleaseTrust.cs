using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace LongshotLauncher.Core;

/// A public key the launcher takes releases from: ECDSA P-256, its SubjectPublicKeyInfo. Id: the first 8 bytes of the SHA-256
/// of the SubjectPublicKeyInfo, in hex (scripts/release.py's key_id)
public sealed record ReleaseKey(string Id, byte[] Spki)
{
    public static ReleaseKey FromSpki(string spkiBase64)
    {
        var spki = Convert.FromBase64String(spkiBase64);
        using var ec = ECDsa.Create();
        ec.ImportSubjectPublicKeyInfo(spki, out _);
        if (ec.KeySize != 256) throw new FormatException("A release key is ECDSA P-256.");
        return new ReleaseKey(KeyId(spki), spki);
    }

    /// A PEM public key ("-----BEGIN PUBLIC KEY-----", openssl's)
    public static ReleaseKey FromPem(string pem)
    {
        using var ec = ECDsa.Create();
        ec.ImportFromPem(pem);
        return FromSpki(Convert.ToBase64String(ec.ExportSubjectPublicKeyInfo()));
    }

    public static string KeyId(byte[] spki) => Convert.ToHexStringLower(SHA256.HashData(spki).AsSpan(0, 8));
}

/// The key this launcher trusts (docs/releases.md, "Signing"): one release key, which signs every release of Longshot and of
/// the launcher, in CI. Rotating it is a launcher release that lists the new key beside the old one, then, once that launcher
/// is out, releases signed with the new key (RELEASING.md, "Rotate the key"). Longshot's scripts/release_keys.json lists the same.
public static class ReleaseKeys
{
    /// The keys built in. None yet: a maintainer makes it (scripts/release.py keygen; RELEASING.md, One-time setup) and lists
    /// it here. Until then this launcher takes no release from the server, and says so.
    public static readonly IReadOnlyList<ReleaseKey> BuiltIn = new ReleaseKey[]
    {
        // the release key, id 5e18330371d7f5aa (scripts/release.py keygen, 2026-11-13, RELEASING.md One-time setup)
        ReleaseKey.FromSpki("MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE5PKAyo4V9MLugswS3bMuUstnNAeNqaQBHbrDfpyhHu58osA/N8hEFI7WXqMwFh1oUFYfLaCe+AkTQ5IlTWirCQ=="),
    };

    /// A PEM public key file trusted too, for trying out a release signed with a test key (scripts/release.py keygen); never
    /// set for players
    public const string TrustVariable = "LONGSHOT_LAUNCHER_TRUST";

    public static IReadOnlyList<ReleaseKey> Current(Func<string, string?>? getenv = null)
    {
        getenv ??= Environment.GetEnvironmentVariable;
        if (getenv(TrustVariable) is not { Length: > 0 } path) return BuiltIn;
        try { return BuiltIn.Append(ReleaseKey.FromPem(File.ReadAllText(path))).ToList(); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException or CryptographicException or FormatException)
        {
            return BuiltIn;
        }
    }
}

/// A release's SHA256SUMS ("&lt;64 hex&gt;  &lt;name&gt;" lines, sha256sum's format) and SHA256SUMS.sig (base64 of the DER ECDSA
/// P-256 signature of SHA256SUMS's exact bytes), as scripts/release.py sums and sign write them. One signature by a trusted
/// key is enough; the names it gives are then each file's SHA-256, which every download is checked against.
public static class SignedSums
{
    public const int MaxBytes = 1 << 20;
    static readonly Regex Line = new(@"^([0-9a-f]{64}) [ *]([^/\\]+)$", RegexOptions.CultureInvariant);

    /// {name: sha256}; InvalidDataException when no trusted key signed the list, or it cannot be read
    public static IReadOnlyDictionary<string, string> Open(byte[] sums, string sig, IReadOnlyList<ReleaseKey> keys)
    {
        if (sums.Length > MaxBytes || sig.Length > 4096) throw new InvalidDataException("SHA256SUMS is too large.");
        if (keys.Count == 0) throw new InvalidDataException("This launcher trusts no release key yet, so it takes no release.");
        byte[] der;
        try { der = Convert.FromBase64String(sig.Trim()); }
        catch (FormatException e) { throw new InvalidDataException("SHA256SUMS.sig cannot be read.", e); }
        var signed = false;
        foreach (var key in keys)
        {
            using var ec = ECDsa.Create();
            ec.ImportSubjectPublicKeyInfo(key.Spki, out _);
            if (ec.VerifyData(sums, der, HashAlgorithmName.SHA256, DSASignatureFormat.Rfc3279DerSequence)) { signed = true; break; }
        }
        if (!signed) throw new InvalidDataException("The release's SHA256SUMS is not signed by a key this launcher trusts.");
        var files = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var raw in Encoding.UTF8.GetString(sums).Split('\n'))
        {
            var line = raw.TrimEnd('\r');
            if (line.Length == 0) continue;
            var m = Line.Match(line);
            if (!m.Success) throw new InvalidDataException("Not a SHA256SUMS line: " + line);
            if (!files.TryAdd(m.Groups[2].Value, m.Groups[1].Value)) throw new InvalidDataException("SHA256SUMS names a file twice.");
        }
        return files;
    }
}
