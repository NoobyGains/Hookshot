using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// A public key the launcher takes releases from: ECDSA P-256, its SubjectPublicKeyInfo. Id: the first 8 bytes of the SHA-256
/// of the SubjectPublicKeyInfo, in hex (the Longshot Launcher's scripts/release.py key_id)
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

/// The keys this launcher trusts (docs/launcher.md, "Signing"). Hookshot's releases are not signed yet ("a signed Builder" is on
/// the roadmap), so none is built in, and SignedSums then takes a release's SHA256SUMS as GitHub serves it over https, unsigned:
/// every file is still checked against it. The day a release key exists, its public half goes here; from then on every release
/// must carry a SHA256SUMS.sig made with it, and one without is refused. (The Longshot Launcher's own key is not carried over:
/// it signs Longshot's releases, never Hookshot's.)
public static class ReleaseKeys
{
    /// The keys built in: none yet (above)
    public static readonly IReadOnlyList<ReleaseKey> BuiltIn = Array.Empty<ReleaseKey>();

    /// A PEM public key file trusted too, for trying out a release signed with a test key; never set for players. Set, it also
    /// turns the signature check on: a release must then be signed by it
    public const string TrustVariable = "HOOKSHOT_LAUNCHER_TRUST";

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

    /// Whether releases must be signed: as soon as this launcher trusts a key
    public static bool Required(IReadOnlyList<ReleaseKey> keys) => keys.Count > 0;
}

/// A release's SHA256SUMS ("&lt;64 hex&gt;  &lt;name&gt;" lines, sha256sum's format) and, when the launcher trusts a key, SHA256SUMS.sig
/// (base64 of the DER ECDSA P-256 signature of SHA256SUMS's exact bytes, `openssl dgst -sha256 -sign`). With a trusted key, one
/// signature by it is needed; with none (Hookshot's releases today: ReleaseKeys) the list is taken unsigned, and the signature, if
/// any, is not read. Either way the names it gives are then each file's SHA-256, which every download is checked against.
public static class SignedSums
{
    public const int MaxBytes = 1 << 20;
    static readonly Regex Line = new(@"^([0-9a-f]{64}) [ *]([^/\\]+)$", RegexOptions.CultureInvariant);

    /// {name: sha256}; InvalidDataException when the list cannot be read, or a trusted key is required and none signed it
    public static IReadOnlyDictionary<string, string> Open(byte[] sums, string? sig, IReadOnlyList<ReleaseKey> keys)
    {
        if (sums.Length > MaxBytes || sig?.Length > 4096) throw new InvalidDataException("SHA256SUMS is too large.");
        if (ReleaseKeys.Required(keys))
        {
            if (sig == null) throw new InvalidDataException("The release has no SHA256SUMS.sig, and this launcher takes only signed releases.");
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
        }
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
