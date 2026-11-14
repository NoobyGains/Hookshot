using System.Text;

namespace LongshotLauncher.Core;

/// What git.magicbean.dev says is released, for one product (Product.Longshot: the builders; Product.Launcher: this program),
/// from the repository's Forgejo releases (docs/releases.md):
///   a channel's newest   from the list of published releases (ReleaseManifest.Newest): no file to sign, nothing to replay;
///                        an update is only ever to a newer version (UpdatePolicy, SelfUpdate), so a list that offers an older
///                        one changes nothing
///   a version's files    its release's SHA256SUMS, signed by the release key (SignedSums), which gives each file's SHA-256
///   the builder's tools  the tools.lock a Longshot release has (Windows), checked by its SHA-256, which names each tool's
/// A channel nobody answered for is null (the window says so quietly); a release whose SHA256SUMS fails its signature, or that
/// lacks it, is refused, with the reason in Problem.
public sealed class Releases
{
    public const string Repo = Product.Server + "/MagicBeanDev/Longshot";
    public const string LauncherRepo = Product.Server + "/MagicBeanDev/LongshotLauncher";
    const long MaxSmall = 4 << 20;

    readonly IReadOnlyList<ReleaseKey> keys;
    readonly Func<TimeSpan, CancellationToken, Task> delay;
    readonly Dictionary<string, ReleaseInfo> known = new(StringComparer.Ordinal);

    public IFetcher Fetcher { get; }
    public Platform Platform { get; }
    public Product Product { get; }
    /// Why the last release was refused (null: none was)
    public string? Problem { get; private set; }

    /// delay: the wait between tries (the tests pass none)
    public Releases(IFetcher fetcher, Platform platform, IReadOnlyList<ReleaseKey> keys, Func<TimeSpan, CancellationToken, Task>? delay = null,
                    Product? product = null)
    {
        Fetcher = fetcher;
        Platform = platform;
        Product = product ?? Product.Longshot;
        this.keys = keys;
        this.delay = delay ?? Task.Delay;
    }

    public string ListUrl(int page) => $"{Product.Api}/releases?limit=50&page={page}";

    public string VersionUrl(string tag) =>
        Versions.IsTagName(tag) ? $"{Product.Api}/releases/tags/{tag}" : throw new ArgumentException("Not a version name: " + tag, nameof(tag));

    /// The published releases (the API lists drafts only to who may write the repository: they are dropped here too); null
    /// when the server did not answer
    public async Task<IReadOnlyList<ListedRelease>?> ListAsync(CancellationToken cancel = default)
    {
        var all = new List<ListedRelease>();
        for (var page = 1; page <= 20; page++)
        {
            var text = await TextAsync(ListUrl(page), 2, cancel).ConfigureAwait(false);
            if (text == null) return page == 1 ? null : all;
            IReadOnlyList<ListedRelease> got;
            try { got = ReleaseManifest.ParseList(text); }
            catch (InvalidDataException e)
            {
                Problem = e.Message;
                return null;
            }
            all.AddRange(got.Where(r => !r.Draft));
            if (got.Count < 50) break;
        }
        return all;
    }

    /// A channel's newest version, its files checked; null when the server did not answer, the channel has none, or its
    /// newest release was refused (Problem)
    public async Task<ReleaseInfo?> ChannelAsync(string channel, CancellationToken cancel = default) =>
        (await ChannelsAsync(new[] { channel }, cancel).ConfigureAwait(false))[channel];

    /// Several channels' newest from one fetch of the release list (an update check reads the list once, not once per channel);
    /// each null as ChannelAsync says
    public async Task<IReadOnlyDictionary<string, ReleaseInfo?>> ChannelsAsync(IEnumerable<string> channels, CancellationToken cancel = default)
    {
        var wanted = channels.ToList();
        foreach (var channel in wanted)
            if (!Versions.IsChannel(channel)) throw new ArgumentException("Not a channel: " + channel, nameof(channels));
        var answers = wanted.Distinct().ToDictionary(c => c, _ => (ReleaseInfo?)null);
        var list = await ListAsync(cancel).ConfigureAwait(false);
        if (list == null) return answers;
        foreach (var channel in answers.Keys.ToList())
        {
            if (ReleaseManifest.Newest(list, channel, Product) is not { } tag) continue;
            try { answers[channel] = await VersionAsync(tag, list.First(r => r.Tag == tag), cancel).ConfigureAwait(false); }
            catch (Exception e) when (e is InvalidDataException or FetchException) { Problem = e.Message; }
        }
        return answers;
    }

    public async Task<string?> NewestAsync(string channel, CancellationToken cancel = default) =>
        (await ChannelAsync(channel, cancel).ConfigureAwait(false))?.Version;

    /// A version's release, its files checked against its signed SHA256SUMS. Throws FetchException (no answer, no such
    /// release) or InvalidDataException (refused)
    public async Task<ReleaseInfo> VersionAsync(string tag, CancellationToken cancel = default)
    {
        if (known.TryGetValue(tag, out var have)) return have;
        var text = await TextAsync(VersionUrl(tag), 2, cancel).ConfigureAwait(false)
                   ?? throw new FetchException($"git.magicbean.dev has no {Product.Display} release {tag}, or did not answer.");
        return await VersionAsync(tag, ReleaseManifest.ParseOne(text), cancel).ConfigureAwait(false);
    }

    async Task<ReleaseInfo> VersionAsync(string tag, ListedRelease listed, CancellationToken cancel)
    {
        if (known.TryGetValue(tag, out var have)) return have;
        if (listed.Tag != tag) throw new InvalidDataException($"The release of {tag} is {listed.Tag}'s.");
        if (listed.Draft) throw new InvalidDataException($"{tag} is not published.");
        if (Versions.TrackOf(tag, Product.FirstMajor) != Versions.Nightly && !Versions.IsRelease(tag, Product.FirstMajor))
            throw new InvalidDataException($"{tag} is not a version of {Product.Display}.");
        var sums = listed.Assets.FirstOrDefault(a => a.Name == ReleaseManifest.Sums);
        var sig = listed.Assets.FirstOrDefault(a => a.Name == ReleaseManifest.Sig);
        if (sums.Url == null || sig.Url == null) throw new InvalidDataException($"{tag} has no signed SHA256SUMS.");
        var sumBytes = await ReleaseManifest.FetchUncheckedAsync(Fetcher, sums.Url, SignedSums.MaxBytes, cancel).ConfigureAwait(false);
        var sigBytes = await ReleaseManifest.FetchUncheckedAsync(Fetcher, sig.Url, 4096, cancel).ConfigureAwait(false);
        var release = ReleaseManifest.Build(listed, SignedSums.Open(sumBytes, Encoding.ASCII.GetString(sigBytes), keys), Product);
        known[tag] = release;
        return release;
    }

    /// A Longshot version's Windows builder and tools for Toolchains: the builder's zip unpacked as it is, then each tool of the
    /// release's tools.lock (checked by its SHA-256) as tools.lock says
    public async Task<PartsList> ToolsListAsync(string tag, CancellationToken cancel = default)
    {
        var release = await VersionAsync(tag, cancel).ConfigureAwait(false);
        if (Platform != Platform.Windows) throw new InvalidOperationException("The Linux builder is an AppImage: BuilderAsync.");
        if (!release.Builder.TryGetValue("windows-x64", out var zip)) throw new InvalidDataException($"{tag} has no Windows builder.");
        if (!release.Tools.TryGetValue("windows-x64", out var lockFile)) throw new InvalidDataException($"{tag} has no tools.lock.");
        var lockText = Encoding.UTF8.GetString(await ReleaseManifest.FetchAsync(Fetcher, lockFile, MaxSmall, cancel).ConfigureAwait(false));
        var parts = new List<Part> { new(zip.Sha256, zip.Size, ".", null, null, zip.Url) };
        parts.AddRange(ToolsLock.Parse(lockText, "windows-x64"));
        return new PartsList(ListKind.Setup, tag, parts, ToolsLock.Run);
    }

    /// A Longshot version's builder file for this system (the Linux AppImage)
    public async Task<FileRef> BuilderAsync(string tag, CancellationToken cancel = default)
    {
        var release = await VersionAsync(tag, cancel).ConfigureAwait(false);
        return release.Builder.TryGetValue(ReleaseManifest.PlatformKey(Platform), out var file) ? file
            : throw new InvalidDataException($"{tag} has no builder for {ReleaseManifest.PlatformKey(Platform)}.");
    }

    /// A text, tries times for an answer that may come next time (no answer, a server error); null when none came
    async Task<string?> TextAsync(string url, int tries, CancellationToken cancel)
    {
        for (var attempt = 0; attempt < tries; attempt++)
        {
            try { return await Fetcher.GetTextAsync(url, "application/json", cancel).ConfigureAwait(false); }
            catch (FetchException e) when (!e.Transient) { return null; }
            catch (FetchException) { }
            if (attempt + 1 < tries) await delay(TimeSpan.FromSeconds(2), cancel).ConfigureAwait(false);
        }
        return null;
    }
}
