namespace HookshotLauncher.Core;

/// Release files through Cloudflare's edge: a download from git.magicbean.dev of a release file (/&lt;owner&gt;/&lt;repo&gt;/releases/download/...)
/// or a package (/api/packages/...) is tried first at git-cdn.magicbean.dev, the same path (served from the same files, cached), then
/// at git.magicbean.dev when the CDN fails: no answer, a TLS error, a timeout or a stall, or HTTP 403, 404 or 5xx. Anything else
/// goes as it is: the API (release lists, GetTextAsync), other hosts, a link already on git-cdn. A file that is not the one its release
/// names (size, SHA-256) is not a failure of the CDN: it fails as before, the callers' checks unchanged. A download the CDN cut short
/// starts again from the stream's start, so no half of the CDN's file stays in front of the server's; a stream that cannot go back
/// (not seekable) keeps the CDN's failure. HOOKSHOT_LAUNCHER_NO_CDN=1: no CDN, every file from git.magicbean.dev
public sealed class CdnFetcher(IFetcher inner, bool enabled = true) : IFetcher
{
    public const string Origin = "https://git.magicbean.dev", Cdn = "https://git-cdn.magicbean.dev";
    public const string DisableVariable = "HOOKSHOT_LAUNCHER_NO_CDN";

    public bool Enabled { get; } = enabled;

    /// Whether the CDN is on: HOOKSHOT_LAUNCHER_NO_CDN=1 turns it off
    public static bool EnabledByEnvironment(Func<string, string?>? getenv = null) =>
        (getenv ?? Environment.GetEnvironmentVariable)(DisableVariable) != "1";

    /// The CDN's link for a release file or package on git.magicbean.dev; null for any other link
    public static string? CdnOf(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out var u) || u.Scheme != Uri.UriSchemeHttps || !u.IsDefaultPort
            || !string.Equals(u.Host, "git.magicbean.dev", StringComparison.OrdinalIgnoreCase) || u.UserInfo.Length > 0)
            return null;
        var path = u.AbsolutePath;
        var release = path.Split('/') is [_, { Length: > 0 }, { Length: > 0 }, "releases", "download", ..];
        return release || path.StartsWith("/api/packages/", StringComparison.Ordinal) ? Cdn + u.PathAndQuery : null;
    }

    /// A tool's own links (tools.lock: its git-cdn link, the same file on git.magicbean.dev, where it came from), which Toolchains
    /// tries in order through Inner, moving on also when a link gives other bytes: each git.magicbean.dev link with its CDN link in
    /// front when the list lacks it; with the CDN off, a git-cdn link whose git.magicbean.dev twin is listed is left out
    public IReadOnlyList<string> Expand(IReadOnlyList<string> urls)
    {
        if (!Enabled)
            return urls.Where(u => !(u.StartsWith(Cdn + "/", StringComparison.Ordinal) && urls.Contains(Origin + u[Cdn.Length..]))).ToList();
        var links = new List<string>();
        foreach (var u in urls)
        {
            if (CdnOf(u) is { } cdn && !links.Contains(cdn) && !urls.Contains(cdn)) links.Add(cdn);
            if (!links.Contains(u)) links.Add(u);
        }
        return links;
    }

    /// The fetcher this one wraps: a download as it is, with no CDN
    public IFetcher Inner => inner;

    /// Whether the CDN's failure is worth the server's try: no answer (Status null: connection, TLS, timeout, stall), or 403, 404, 5xx
    public static bool FallsBack(FetchException e) => e.Status is null or 403 or 404 or >= 500;

    public Task<string> GetTextAsync(string url, string? accept, CancellationToken cancel) => inner.GetTextAsync(url, accept, cancel);

    public async Task DownloadAsync(string url, Stream to, Action<long>? progress, CancellationToken cancel)
    {
        if (!Enabled || CdnOf(url) is not { } cdn)
        {
            await inner.DownloadAsync(url, to, progress, cancel).ConfigureAwait(false);
            return;
        }
        var start = to.CanSeek ? to.Position : 0;
        long wrote = 0;
        try
        {
            await inner.DownloadAsync(cdn, to, have =>
            {
                wrote = have;
                progress?.Invoke(have);
            }, cancel).ConfigureAwait(false);
            return;
        }
        catch (FetchException e) when (FallsBack(e))
        {
            if (wrote > 0 || (to.CanSeek && to.Position != start))
            {
                if (!to.CanSeek) throw;
                to.SetLength(start);
                to.Position = start;
            }
        }
        await inner.DownloadAsync(url, to, progress, cancel).ConfigureAwait(false);
    }
}
