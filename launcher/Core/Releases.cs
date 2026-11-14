using System.Text;

namespace HookshotLauncher.Core;

/// What GitHub says is released, for one product (Product.Hookshot: the builders; Product.Launcher: this program), from the
/// repository's releases (docs/launcher.md):
///   a channel's newest   from the list of published releases (ReleaseManifest.Newest), one API call for the three channels; an
///                        update is only ever to a newer version (UpdatePolicy, SelfUpdate), so a list that offers an older one
///                        changes nothing
///   a version's files    its release's SHA256SUMS (signed, once this launcher trusts a key: ReleaseKeys), which gives each file's
///                        SHA-256; for Hookshot, then this system's setup list (checked by it), which gives the version and, on
///                        Windows, each part of the builder with its own SHA-256
/// A channel nobody answered for is null (the window says so quietly); a release whose files fail their checks, or that lacks them,
/// is refused, with the reason in Problem. Only the release list and a release by its tag are API calls (GitHub allows 60 an hour
/// from one address without an account); the files come from github.com's download links.
public sealed class Releases
{
    const long MaxSmall = 4 << 20;
    const int PerPage = 100, MaxPages = 10;

    readonly IReadOnlyList<ReleaseKey> keys;
    readonly Func<TimeSpan, CancellationToken, Task> delay;
    readonly Dictionary<string, ReleaseInfo> known = new(StringComparer.Ordinal);   // (by version: a version's files never change)

    public IFetcher Fetcher { get; }
    public Platform Platform { get; }
    public Product Product { get; }
    /// Why the last release was refused, or the last check failed (null: none was)
    public string? Problem { get; private set; }
    /// The last check read the release list (its channels may still have nothing: a fork's stable before its first release)
    public bool Answered { get; private set; }

    /// delay: the wait between tries (the tests pass none)
    public Releases(IFetcher fetcher, Platform platform, IReadOnlyList<ReleaseKey> keys, Func<TimeSpan, CancellationToken, Task>? delay = null,
                    Product? product = null)
    {
        Fetcher = fetcher;
        Platform = platform;
        Product = product ?? Product.Hookshot;
        this.keys = keys;
        this.delay = delay ?? Task.Delay;
    }

    /// Whether the releases taken are signed (ReleaseKeys): false while Hookshot's are not
    public bool SignaturesRequired => ReleaseKeys.Required(keys);

    public string ListUrl(int page) => $"{Product.RepoApi}/releases?per_page={PerPage}&page={page}";

    public string TagUrl(string tag) =>
        Versions.IsTagName(tag) ? $"{Product.RepoApi}/releases/tags/{tag}" : throw new ArgumentException("Not a release name: " + tag, nameof(tag));

    /// The published releases (the API lists drafts only to who may write the repository: they are dropped here too); null
    /// when the server did not answer
    public async Task<IReadOnlyList<ListedRelease>?> ListAsync(CancellationToken cancel = default)
    {
        var all = new List<ListedRelease>();
        for (var page = 1; page <= MaxPages; page++)
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
            if (got.Count < PerPage) break;
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
        Problem = null;
        var list = await ListAsync(cancel).ConfigureAwait(false);
        Answered = list != null;
        if (list == null) return answers;
        foreach (var channel in answers.Keys.ToList())
        {
            if (ReleaseManifest.Newest(list, channel, Product) is not { } tag) continue;
            try { answers[channel] = await BuildAsync(list.First(r => r.Tag == tag), cancel).ConfigureAwait(false); }
            catch (Exception e) when (e is InvalidDataException or FetchException) { Problem = e.Message; }
        }
        return answers;
    }

    public async Task<string?> NewestAsync(string channel, CancellationToken cancel = default) =>
        (await ChannelAsync(channel, cancel).ConfigureAwait(false))?.Version;

    /// A version's release, its files checked. A nightly's is the rolling nightly's, while it is still that version. Throws
    /// FetchException (no answer, no such release, a nightly the rolling one moved past) or InvalidDataException (refused)
    public async Task<ReleaseInfo> VersionAsync(string version, CancellationToken cancel = default)
    {
        if (known.TryGetValue(version, out var have)) return have;
        if (!Versions.IsTagName(version)) throw new ArgumentException("Not a version name: " + version, nameof(version));
        var tag = Product.TagOf(version);
        var text = await TextAsync(TagUrl(tag), 2, cancel).ConfigureAwait(false)
                   ?? throw new FetchException($"GitHub has no {Product.Display} release {tag} in {Product.Repo}, or did not answer.");
        var release = await BuildAsync(ReleaseManifest.ParseOne(text), cancel).ConfigureAwait(false);
        if (release.Version != version)
            throw new FetchException($"{Versions.Shown(version)} is no longer on GitHub: the nightly is {Versions.Shown(release.Version)} now. " +
                                     "Build the newest nightly instead.", 404);
        return release;
    }

    /// A listed release's files, checked
    async Task<ReleaseInfo> BuildAsync(ListedRelease listed, CancellationToken cancel)
    {
        if (listed.Draft) throw new InvalidDataException($"{listed.Tag} is not published.");
        var tagVersion = Product.VersionOf(listed.Tag);
        if (tagVersion == null && listed.Tag != Product.NightlyTag) throw new InvalidDataException($"{listed.Tag} is not a version of {Product.Display}.");
        if (tagVersion != null && known.TryGetValue(tagVersion, out var have)) return have;
        var sumsAsset = listed.Assets.FirstOrDefault(a => a.Name == ReleaseManifest.Sums);
        var sigAsset = listed.Assets.FirstOrDefault(a => a.Name == ReleaseManifest.Sig);
        if (sumsAsset.Url == null) throw new InvalidDataException($"{listed.Tag} has no SHA256SUMS.");
        if (SignaturesRequired && sigAsset.Url == null) throw new InvalidDataException($"{listed.Tag} has no signed SHA256SUMS.");
        var sumBytes = await ReleaseManifest.FetchUncheckedAsync(Fetcher, sumsAsset.Url, SignedSums.MaxBytes, cancel).ConfigureAwait(false);
        string? sig = null;
        if (SignaturesRequired)
            sig = Encoding.ASCII.GetString(await ReleaseManifest.FetchUncheckedAsync(Fetcher, sigAsset.Url, 4096, cancel).ConfigureAwait(false));
        var sums = SignedSums.Open(sumBytes, sig, keys);
        var empty = new Dictionary<string, FileRef>();
        ReleaseInfo release;
        if (Product.Name == "launcher")
        {
            var version = tagVersion ?? ReleaseManifest.LauncherVersionOf(sums.Keys);
            if (tagVersion == null && Versions.TrackOf(version, Product.FirstMajor) != Versions.Nightly)
                throw new InvalidDataException($"The launcher nightly's files are of {version}, which is not a nightly.");
            var files = new Dictionary<string, FileRef>(StringComparer.Ordinal);
            foreach (var key in ReleaseManifest.LauncherKeys)
                if (ReleaseManifest.File(listed, sums, ReleaseManifest.LauncherFile(version, key)) is { } f) files[key] = f;
            release = new ReleaseInfo(Product.Name, version, listed.Commit, listed.Published, listed.Page, files, empty, empty);
        }
        else
        {
            var listName = SetupList.NameFor(Platform);
            var listFile = ReleaseManifest.File(listed, sums, listName)
                           ?? throw new InvalidDataException($"{listed.Tag} has no {listName} for this system's builder.");
            var text = Encoding.UTF8.GetString(await ReleaseManifest.FetchAsync(Fetcher, listFile, MaxSmall, cancel).ConfigureAwait(false));
            var version = SetupList.Tag(text) ?? throw new InvalidDataException($"{listed.Tag}'s {listName} names no version.");
            if (tagVersion != null ? version != tagVersion : !Versions.IsNightly(version))
                throw new InvalidDataException($"{listed.Tag}'s {listName} is of {version}.");
            var tools = new Dictionary<string, FileRef>(StringComparer.Ordinal);
            var builder = new Dictionary<string, FileRef>(StringComparer.Ordinal);
            PartsList? setup = null;
            if (Platform == Platform.Windows)
            {
                try { setup = SetupList.WithMirrors(SetupList.Parse(text), new[] { Product.Repo, Repository.Default }); }
                catch (FormatException e) { throw new InvalidDataException($"{listed.Tag}'s {listName}: {e.Message}", e); }
                tools["windows-x64"] = listFile;
            }
            else
            {
                var name = ReleaseManifest.AppImageOf(sums.Keys, version)
                           ?? throw new InvalidDataException($"{listed.Tag} has no Linux AppImage of {version}.");
                builder["linux-x64"] = ReleaseManifest.File(listed, sums, name)
                                       ?? throw new InvalidDataException($"{listed.Tag} has no {name}.");
            }
            release = new ReleaseInfo(Product.Name, version, listed.Commit, listed.Published, listed.Page, empty, tools, builder) { Setup = setup };
        }
        release = release with { Tag = listed.Tag, Signed = SignaturesRequired };
        known[release.Version] = release;
        return release;
    }

    /// A Hookshot version's Windows builder and tools for Toolchains: the parts its hookshot-setup.txt names, each checked by its
    /// own SHA-256, unpacked as the builder's setup unpacks them
    public async Task<PartsList> ToolsListAsync(string version, CancellationToken cancel = default)
    {
        if (Platform != Platform.Windows) throw new InvalidOperationException("The Linux builder is an AppImage: BuilderAsync.");
        var release = await VersionAsync(version, cancel).ConfigureAwait(false);
        return release.Setup ?? throw new InvalidDataException($"{version} has no Windows builder.");
    }

    /// A Hookshot version's builder file for this system (the Linux AppImage)
    public async Task<FileRef> BuilderAsync(string version, CancellationToken cancel = default)
    {
        var release = await VersionAsync(version, cancel).ConfigureAwait(false);
        return release.Builder.TryGetValue(ReleaseManifest.PlatformKey(Platform), out var file) ? file
            : throw new InvalidDataException($"{version} has no builder for {ReleaseManifest.PlatformKey(Platform)}.");
    }

    /// A text, tries times for an answer that may come next time (no answer, a server error); null when none came (Problem: why)
    async Task<string?> TextAsync(string url, int tries, CancellationToken cancel)
    {
        for (var attempt = 0; attempt < tries; attempt++)
        {
            try { return await Fetcher.GetTextAsync(url, "application/vnd.github+json", cancel).ConfigureAwait(false); }
            catch (FetchException e) when (!e.Transient)
            {
                if (e.Status != 404) Problem = e.Message;
                return null;
            }
            catch (FetchException e) { Problem = e.Message; }
            if (attempt + 1 < tries) await delay(TimeSpan.FromSeconds(2), cancel).ConfigureAwait(false);
        }
        return null;
    }
}
