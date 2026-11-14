using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// A file a release has: where it is, and its SHA-256 (from the release's SHA256SUMS) and size, which the download is checked
/// against
public sealed record FileRef(string Url, string Sha256, long Size);

/// What a release belongs to: Hookshot (its builders) or the launcher itself. Both are released from the same GitHub repository
/// (Repository.Current), each with its own versions and its own three channels (docs/launcher.md):
///   Hookshot  tags vX.Y.Z and vX.Y.Z-rc.N; its nightly is the rolling release "nightly", whose version is in its setup lists
///   launcher  tags launcher-vX.Y.Z and launcher-vX.Y.Z-rc.N; its nightly is the rolling release "launcher-nightly", whose version
///             (nightly-&lt;count&gt;-&lt;commit&gt;) is in its files' names
/// TagPrefix: what a version's tag has before the version; NightlyTag: the rolling nightly's tag
public sealed record Product(string Name, string Display, string Repo, int FirstMajor, string TagPrefix, string NightlyTag)
{
    public const string Api = "https://api.github.com";
    public static Product Hookshot => For(Repository.Current, "hookshot");
    public static Product Launcher => For(Repository.Current, "launcher");

    /// One of the two products, released from repo
    public static Product For(string repo, string name) => name == "launcher"
        ? new Product("launcher", "Hookshot Launcher", repo, Versions.LauncherFirstMajor, "launcher-", "launcher-nightly")
        : new Product("hookshot", "Hookshot", repo, Versions.FirstMajor, "", "nightly");

    public string RepoApi => Api + "/repos/" + Repo;
    public string Releases => Repository.Page(Repo) + "/releases";

    /// The tag a version's files are on: the rolling nightly's for a nightly, else its own
    public string TagOf(string version) => Versions.IsNightly(version) ? NightlyTag : TagPrefix + version;

    /// The version a tag names (null: the rolling nightly, whose version is in its files, or a tag of the other product)
    public string? VersionOf(string tag)
    {
        if (tag == NightlyTag || !tag.StartsWith(TagPrefix, StringComparison.Ordinal)) return null;
        var v = tag[TagPrefix.Length..];
        return Versions.IsRelease(v, FirstMajor) ? v : null;
    }
}

/// One version's release, its files checked against its SHA256SUMS: for each system ("windows-x64", "linux-x64"), Hookshot's
/// builder (Tools["windows-x64"]: hookshot-setup.txt, whose parts are Setup; Builder["linux-x64"]: the AppImage), or the launcher's
/// own program (Launcher: also "windows-x64-portable", the portable zip). Notes: the release's page. Tag: the GitHub release the files
/// are on (the rolling nightly's for a nightly). Signed: its SHA256SUMS was signed by a key this launcher trusts (ReleaseKeys)
public sealed record ReleaseInfo(string Product, string Version, string Commit, DateTimeOffset? Published, string? Notes,
                                 IReadOnlyDictionary<string, FileRef> Launcher, IReadOnlyDictionary<string, FileRef> Tools,
                                 IReadOnlyDictionary<string, FileRef> Builder)
{
    public string Tag { get; init; } = Version;
    public bool Signed { get; init; }
    /// Windows: the builder's parts, from the release's hookshot-setup.txt (null for the launcher, and on Linux)
    public PartsList? Setup { get; init; }
}

/// A release as GitHub's API lists it (GET /repos/{repo}/releases): its tag, whether it is a draft or a pre-release, its files
/// (name, download link, size), its page and its commit (or branch)
public sealed record ListedRelease(string Tag, bool Draft, bool Prerelease, DateTimeOffset? Published, string? Page, string Commit,
                                   IReadOnlyList<(string Name, string Url, long Size)> Assets);

/// Reading GitHub's release list, and the channels from it:
///   stable   the newest &lt;prefix&gt;vX.Y.Z that is not a draft nor a pre-release (Hookshot's fork may have none yet: then none)
///   rc       the newest &lt;prefix&gt;vX.Y.Z-rc.N or &lt;prefix&gt;vX.Y.Z that is not a draft
///   nightly  the product's rolling nightly release, when it is there and not a draft
/// A draft is a release CI is still making; a version pulled back to a draft, or deleted, is gone from its channel, which then
/// offers the one before. Anything else in the list (builder-parts, linux-parts, upstream's rolling rc, the other product's tags)
/// is on no channel.
public static class ReleaseManifest
{
    public const long MaxFile = 16L << 30;
    public const string Sums = "SHA256SUMS", Sig = "SHA256SUMS.sig";

    public static string PlatformKey(Platform platform) => platform == Platform.Windows ? "windows-x64" : "linux-x64";

    /// The launcher's files, by key: the Windows program as its setup (the program itself, which offers to install itself when it
    /// is first started), the same program in a zip with its "portable" file, and the AppImage (.github/workflows/launcher.yml)
    public const string WindowsPortable = "windows-x64-portable";
    public static readonly IReadOnlyList<string> LauncherKeys = new[] { "windows-x64", WindowsPortable, "linux-x64" };

    public static string LauncherFile(string version, string key) => key switch
    {
        "windows-x64" => $"HookshotLauncher-{version}-windows-x64-setup.exe",
        WindowsPortable => $"HookshotLauncher-{version}-windows-x64-portable.zip",
        _ => $"HookshotLauncher-{version}-x86_64.AppImage",
    };

    static readonly Regex LauncherName = new(@"^HookshotLauncher-(.+)-(?:windows-x64-setup\.exe|windows-x64-portable\.zip|x86_64\.AppImage)$",
                                             RegexOptions.CultureInvariant);

    /// The version a rolling launcher nightly's files are named with: every launcher file SHA256SUMS names must name the same one
    public static string LauncherVersionOf(IEnumerable<string> names)
    {
        var versions = names.Select(n => LauncherName.Match(n)).Where(m => m.Success).Select(m => m.Groups[1].Value).Distinct().ToList();
        if (versions.Count != 1) throw new InvalidDataException(versions.Count == 0 ? "The release has no launcher." : "The release's launchers are of different versions.");
        return versions[0];
    }

    /// Hookshot's Linux builder in a release, among the names SHA256SUMS gives: the AppImage named for the version
    /// (scripts/linux/appimage.sh, &lt;project&gt;-&lt;version&gt;-x86_64.AppImage); for a git describe version, the one named for its
    /// commit alone (a fork with no tags may name it so, Hookshot-179d8124-x86_64.AppImage). Null when none, or more than one,
    /// fits: an AppImage of another version is never taken for this one
    public static string? AppImageOf(IEnumerable<string> names, string version)
    {
        var all = names.Where(n => n.EndsWith("-x86_64.AppImage", StringComparison.Ordinal)).ToList();
        string? Named(string v)
        {
            var name = new Regex("^[A-Za-z0-9._+-]+-" + Regex.Escape(v) + @"-x86_64\.AppImage$", RegexOptions.CultureInvariant);
            var found = all.Where(n => name.IsMatch(n)).ToList();
            return found.Count == 1 ? found[0] : null;
        }
        var commit = Regex.Match(version, @"-g([0-9a-f]{7,40})(-dirty)?$", RegexOptions.CultureInvariant);
        return Named(version) ?? (commit.Success ? Named(commit.Groups[1].Value + commit.Groups[2].Value) : null);
    }

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

    /// The tag of what a channel offers from the list, null when nothing
    public static string? Newest(IEnumerable<ListedRelease> list, string channel, Product product)
    {
        var published = list.Where(r => !r.Draft && Versions.IsTagName(r.Tag)).ToList();
        if (channel == Versions.Nightly)
            return published.Any(r => r.Tag == product.NightlyTag) ? product.NightlyTag : null;
        IEnumerable<(string Tag, string Version)> tags = channel switch
        {
            Versions.Candidate => published.Select(r => (r.Tag, V: product.VersionOf(r.Tag))).Where(t => t.V != null).Select(t => (t.Tag, t.V!)),
            Versions.Stable => published.Where(r => !r.Prerelease).Select(r => (r.Tag, V: product.VersionOf(r.Tag)))
                .Where(t => t.V != null && Versions.TrackOf(t.V, product.FirstMajor) == Versions.Stable).Select(t => (t.Tag, t.V!)),
            _ => throw new ArgumentException("Not a channel: " + channel, nameof(channel)),
        };
        (string Tag, string Version)? best = null;
        foreach (var t in tags)
            if (best == null || Versions.Newer(t.Version, best.Value.Version, product.FirstMajor)) best = t;
        return best?.Tag;
    }

    /// The files a release has that SHA256SUMS names, with the SHA-256 it gives; one it does not name is not taken
    public static FileRef? File(ListedRelease r, IReadOnlyDictionary<string, string> sums, string name)
    {
        var a = r.Assets.FirstOrDefault(x => x.Name == name);
        if (a.Url == null || !sums.TryGetValue(name, out var sha)) return null;
        if (a.Size < 0 || a.Size > MaxFile) throw new InvalidDataException($"{name}: a size out of range.");
        return new FileRef(a.Url, sha, a.Size);
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

    /// A small file into memory, no larger than max (SHA256SUMS and its signature)
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
