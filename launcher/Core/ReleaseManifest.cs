using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;

namespace HookshotLauncher.Core;

/// A file a release has: where it is, and its SHA-256 (from the release's signed SHA256SUMS) and size, which the download is
/// checked against
public sealed record FileRef(string Url, string Sha256, long Size);

/// What a release belongs to: Hookshot (its builders, the releases of MagicBeanDev/Hookshot) or the launcher itself (the releases
/// of MagicBeanDev/HookshotLauncher). Each has its own versions and its own three channels (docs/releases.md)
public sealed record Product(string Name, string Display, string Repo, int FirstMajor)
{
    public const string Server = "https://git.magicbean.dev";
    public static readonly Product Hookshot = new("hookshot", "Hookshot", "MagicBeanDev/Hookshot", Versions.FirstMajor);
    public static readonly Product Launcher = new("launcher", "Hookshot Launcher", "MagicBeanDev/HookshotLauncher", Versions.LauncherFirstMajor);

    public string Api => Server + "/api/v1/repos/" + Repo;
}

/// One version's release, its files checked against its signed SHA256SUMS: for each system ("windows-x64", "linux-x64"),
/// Hookshot's builder (Builder: HookshotBuilder-&lt;v&gt;-windows-x64.zip, Hookshot-&lt;v&gt;-x86_64.AppImage) and the Windows builder's
/// tools.lock (Tools), or the launcher's own program (Launcher: also "windows-x64-portable", the portable zip). Notes: the release's page
public sealed record ReleaseInfo(string Product, string Version, string Commit, DateTimeOffset? Published, string? Notes,
                                 IReadOnlyDictionary<string, FileRef> Launcher, IReadOnlyDictionary<string, FileRef> Tools,
                                 IReadOnlyDictionary<string, FileRef> Builder);

/// A release as Forgejo's API lists it (GET /repos/{repo}/releases): its tag, whether it is a draft or a pre-release, its
/// files (name, download link, size), its page and its commit
public sealed record ListedRelease(string Tag, bool Draft, bool Prerelease, DateTimeOffset? Published, string? Page, string Commit,
                                   IReadOnlyList<(string Name, string Url, long Size)> Assets);

/// Reading Forgejo's release list, and the channels from it (scripts/release.py newest has the same rules):
///   stable   the newest vX.Y.Z that is not a draft nor a pre-release
///   rc       the newest vX.Y.Z-rc.N or vX.Y.Z that is not a draft
///   nightly  the newest nightly-&lt;count&gt;-&lt;commit&gt; that is not a draft, by its count
/// A draft is a release CI is still making; a version pulled back to a draft, or deleted, is gone from its channel, which then
/// offers the one before. Anything else in the list (a 2.x tag) is on no channel. (The build tools are generic packages, not
/// releases.)
public static class ReleaseManifest
{
    public const long MaxFile = 16L << 30;
    public const string Sums = "SHA256SUMS", Sig = "SHA256SUMS.sig", ToolsLock = "tools.lock";

    public static string PlatformKey(Platform platform) => platform == Platform.Windows ? "windows-x64" : "linux-x64";

    /// The launcher's files, by key: the Windows program as its setup (the program itself, which offers to install itself when it
    /// is first started), the same program in a zip with its "portable" file, and the AppImage (scripts/package.sh)
    public const string WindowsPortable = "windows-x64-portable";
    public static readonly IReadOnlyList<string> LauncherKeys = new[] { "windows-x64", WindowsPortable, "linux-x64" };

    /// The file names a release of product has, per system (scripts/package.sh, Hookshot's release workflow)
    public static string LauncherFile(string version, string key) => key switch
    {
        "windows-x64" => $"HookshotLauncher-{version}-windows-x64-setup.exe",
        WindowsPortable => $"HookshotLauncher-{version}-windows-x64-portable.zip",
        _ => $"HookshotLauncher-{version}-x86_64.AppImage",
    };

    public static string BuilderFile(string version, string platform) =>
        platform == "windows-x64" ? $"HookshotBuilder-{version}-windows-x64.zip" : $"Hookshot-{version}-x86_64.AppImage";

    public static IReadOnlyList<ListedRelease> ParseList(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            return doc.RootElement.EnumerateArray().Select(Listed).ToList();
        }
        catch (Exception e) when (e is JsonException or KeyNotFoundException or InvalidOperationException or FormatException)
        {
            throw new InvalidDataException("The release list cannot be read: " + e.Message, e);
        }
    }

    public static ListedRelease ParseOne(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            return Listed(doc.RootElement);
        }
        catch (Exception e) when (e is JsonException or KeyNotFoundException or InvalidOperationException or FormatException)
        {
            throw new InvalidDataException("The release cannot be read: " + e.Message, e);
        }
    }

    static string? Opt(JsonElement e, string name) =>
        e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    static bool Flag(JsonElement e, string name) => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True;

    static ListedRelease Listed(JsonElement r)
    {
        var assets = new List<(string, string, long)>();
        if (r.TryGetProperty("assets", out var list) && list.ValueKind == JsonValueKind.Array)
            foreach (var a in list.EnumerateArray())
                if (Opt(a, "name") is { } name && Opt(a, "browser_download_url") is { } url && url.StartsWith("https://", StringComparison.Ordinal))
                    assets.Add((name, url, a.GetProperty("size").GetInt64()));
        DateTimeOffset? published = Opt(r, "published_at") is { } p
            && DateTimeOffset.TryParse(p, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var when) ? when : null;
        var page = Opt(r, "html_url") is { } h && h.StartsWith("https://", StringComparison.Ordinal) ? h : null;
        return new ListedRelease(Opt(r, "tag_name") ?? "", Flag(r, "draft"), Flag(r, "prerelease"), published, page,
                                 Opt(r, "target_commitish") ?? "", assets);
    }

    /// What a channel offers from the list, null when nothing
    public static string? Newest(IEnumerable<ListedRelease> list, string channel, Product product)
    {
        var published = list.Where(r => !r.Draft && Versions.IsTagName(r.Tag)).ToList();
        IEnumerable<string> tags = channel switch
        {
            Versions.Nightly => published.Where(r => Versions.TrackOf(r.Tag, product.FirstMajor) == Versions.Nightly).Select(r => r.Tag),
            Versions.Candidate => published.Where(r => Versions.IsRelease(r.Tag, product.FirstMajor)).Select(r => r.Tag),
            Versions.Stable => published.Where(r => !r.Prerelease && Versions.IsRelease(r.Tag, product.FirstMajor)
                                                    && Versions.TrackOf(r.Tag, product.FirstMajor) == Versions.Stable).Select(r => r.Tag),
            _ => throw new ArgumentException("Not a channel: " + channel, nameof(channel)),
        };
        string? best = null;
        foreach (var t in tags)
            if (best == null || Versions.Newer(t, best, product.FirstMajor)) best = t;
        return best;
    }

    /// The release's files, each with the SHA-256 its signed SHA256SUMS gives; a file the list does not name is not taken
    public static ReleaseInfo Build(ListedRelease r, IReadOnlyDictionary<string, string> sums, Product product)
    {
        var assets = r.Assets.ToDictionary(a => a.Name, a => a, StringComparer.Ordinal);
        Dictionary<string, FileRef> Pick(Func<string, string> name, IEnumerable<string>? keys = null)
        {
            var files = new Dictionary<string, FileRef>(StringComparer.Ordinal);
            foreach (var platform in keys ?? new[] { "windows-x64", "linux-x64" })
            {
                var n = name(platform);
                if (assets.TryGetValue(n, out var a) && sums.TryGetValue(n, out var sha))
                {
                    if (a.Size < 0 || a.Size > MaxFile) throw new InvalidDataException($"{n}: a size out of range.");
                    files[platform] = new FileRef(a.Url, sha, a.Size);
                }
            }
            return files;
        }
        var empty = new Dictionary<string, FileRef>();
        if (product.Name == Product.Launcher.Name)
            return new ReleaseInfo(product.Name, r.Tag, r.Commit, r.Published, r.Page, Pick(p => LauncherFile(r.Tag, p), LauncherKeys), empty, empty);
        var tools = new Dictionary<string, FileRef>(StringComparer.Ordinal);
        if (assets.TryGetValue(ToolsLock, out var lockFile) && sums.TryGetValue(ToolsLock, out var lockSha))
            tools["windows-x64"] = new FileRef(lockFile.Url, lockSha, lockFile.Size);
        return new ReleaseInfo(product.Name, r.Tag, r.Commit, r.Published, r.Page, empty, tools, Pick(p => BuilderFile(r.Tag, p)));
    }

    /// A small file a release has, into memory, checked for its size and SHA-256
    public static async Task<byte[]> FetchAsync(IFetcher fetcher, FileRef file, long max, CancellationToken cancel)
    {
        if (file.Size > max) throw new InvalidDataException($"{file.Url} is larger than expected.");
        var data = await FetchUncheckedAsync(fetcher, file.Url, file.Size, cancel).ConfigureAwait(false);
        if (data.LongLength != file.Size || Convert.ToHexStringLower(SHA256.HashData(data)) != file.Sha256)
            throw new InvalidDataException($"{file.Url} is not the file its release names (size or SHA-256).");
        return data;
    }

    /// A small file into memory, no larger than max (SHA256SUMS and its signature, which the signature itself checks)
    public static async Task<byte[]> FetchUncheckedAsync(IFetcher fetcher, string url, long max, CancellationToken cancel)
    {
        using var bytes = new MemoryStream();
        await fetcher.DownloadAsync(url, bytes, have =>
        {
            if (have > max) throw new InvalidDataException($"{url} is larger than expected.");
        }, cancel).ConfigureAwait(false);
        return bytes.ToArray();
    }
}
