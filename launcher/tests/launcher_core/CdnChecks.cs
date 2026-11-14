using System.Text;
using LongshotLauncher.Core;

/// Release files through git-cdn.magicbean.dev (CdnFetcher): which links go to the CDN, the fall back to git.magicbean.dev when
/// the CDN fails (before its bytes, and half way), no fall back for a file that is not the one its release names, a tool's own
/// links tried once each, and LONGSHOT_LAUNCHER_NO_CDN
static partial class Program
{
    /// A server whose files can fail: Status (null: no answer) once FailAt bytes have gone out (0: before any)
    sealed record Served(byte[] Bytes, int? FailAt = null, int? Status = null);

    sealed class FailingFetcher : IFetcher
    {
        public readonly Dictionary<string, Served> Files = new();
        public readonly List<string> Asked = new();

        public Task<string> GetTextAsync(string url, string? accept, CancellationToken cancel)
        {
            Asked.Add(url);
            return Task.FromResult("text of " + url);
        }

        public async Task DownloadAsync(string url, Stream to, Action<long>? progress, CancellationToken cancel)
        {
            Asked.Add(url);
            if (!Files.TryGetValue(url, out var s)) throw new FetchException("not found: " + url, 404);
            for (var at = 0; at < s.Bytes.Length; at += 7)
            {
                if (s.FailAt is { } fail && at >= fail) throw new FetchException("authored failure", s.Status);
                var n = Math.Min(7, s.Bytes.Length - at);
                await to.WriteAsync(s.Bytes.AsMemory(at, n), cancel);
                progress?.Invoke(at + n);
            }
        }
    }

    /// A stream that cannot go back
    sealed class OneWayStream : Stream
    {
        public readonly MemoryStream Inner = new();
        public override bool CanRead => false;
        public override bool CanSeek => false;
        public override bool CanWrite => true;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => Inner.Write(buffer, offset, count);
    }

    static async Task CdnChecks()
    {
        const string release = "https://git.magicbean.dev/MagicBeanDev/Longshot/releases/download/v3.1.0/Longshot-v3.1.0-x86_64.AppImage";
        const string cdnRelease = "https://git-cdn.magicbean.dev/MagicBeanDev/Longshot/releases/download/v3.1.0/Longshot-v3.1.0-x86_64.AppImage";
        const string package = "https://git.magicbean.dev/api/packages/MagicBeanDev/generic/llvm-mingw-windows-x64/20261104/abc-llvm-mingw.zip";
        const string cdnPackage = "https://git-cdn.magicbean.dev/api/packages/MagicBeanDev/generic/llvm-mingw-windows-x64/20261104/abc-llvm-mingw.zip";
        const string upstream = "https://github.com/mstorsjo/llvm-mingw/releases/download/20261104/llvm-mingw-20261104-ucrt-x86_64.zip";

        // (the rewrite: release files and packages of git.magicbean.dev only)
        Require(CdnFetcher.CdnOf(release) == cdnRelease && CdnFetcher.CdnOf(package) == cdnPackage
                && CdnFetcher.CdnOf("https://GIT.magicbean.dev/MagicBeanDev/LongshotLauncher/releases/download/v1.0.0-rc.1/SHA256SUMS")
                   == "https://git-cdn.magicbean.dev/MagicBeanDev/LongshotLauncher/releases/download/v1.0.0-rc.1/SHA256SUMS",
                "A release file and a package go to git-cdn, the same path.");
        Require(CdnFetcher.CdnOf("https://git.magicbean.dev/api/v1/repos/MagicBeanDev/Longshot/releases?limit=50&page=1") == null
                && CdnFetcher.CdnOf("https://git.magicbean.dev/api/v1/repos/MagicBeanDev/Longshot/releases/tags/v3.1.0") == null
                && CdnFetcher.CdnOf("https://git.magicbean.dev/MagicBeanDev/Longshot/releases/tag/v3.1.0") == null
                && CdnFetcher.CdnOf(upstream) == null && CdnFetcher.CdnOf(cdnRelease) == null && CdnFetcher.CdnOf(cdnPackage) == null
                && CdnFetcher.CdnOf("http://git.magicbean.dev/api/packages/x") == null
                && CdnFetcher.CdnOf("https://git.magicbean.dev:8443/api/packages/x") == null
                && CdnFetcher.CdnOf("https://git.magicbean.dev.example/api/packages/x") == null
                && CdnFetcher.CdnOf("https://git.magicbean.dev/releases/download/x") == null
                && CdnFetcher.CdnOf("file:///tmp/api/packages/x") == null,
                "The API, a release's page, another host, a link already on git-cdn, http and another port stay as they are.");

        var bytes = Encoding.UTF8.GetBytes(string.Concat(Enumerable.Range(0, 20).Select(i => $"release file line {i}\n")));
        var other = Encoding.UTF8.GetBytes(string.Concat(Enumerable.Range(0, 20).Select(i => $"release FILE line {i}\n")));
        var server = new FailingFetcher();
        var cdn = new CdnFetcher(server);
        Require(cdn.Enabled, "The CDN is on by default.");

        async Task<byte[]> Get(string url)
        {
            server.Asked.Clear();
            using var to = new MemoryStream();
            await cdn.DownloadAsync(url, to, null, CancellationToken.None);
            return to.ToArray();
        }

        // (from the CDN when it answers; the API and other hosts never go there)
        server.Files[cdnRelease] = new Served(bytes);
        server.Files[release] = new Served(other);
        Require((await Get(release)).SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { cdnRelease }), "A release file from the CDN.");
        server.Asked.Clear();
        var api = "https://git.magicbean.dev/api/v1/repos/MagicBeanDev/Longshot/releases?limit=50&page=1";
        Require(await cdn.GetTextAsync(api, null, CancellationToken.None) == "text of " + api && server.Asked.SequenceEqual(new[] { api }),
                "The API stays on git.magicbean.dev.");
        server.Files[upstream] = new Served(bytes);
        server.Files[cdnPackage] = new Served(bytes);
        Require((await Get(upstream)).SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { upstream })
                && (await Get(cdnPackage)).SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { cdnPackage }),
                "Another host, and a git-cdn link, as they are.");

        // (the CDN fails before any byte: no answer, 403, 404, 5xx, then git.magicbean.dev)
        server.Files[release] = new Served(bytes);
        foreach (var status in new int?[] { null, 403, 404, 500, 503 })
        {
            server.Files[cdnRelease] = new Served(other, 0, status);
            Require((await Get(release)).SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { cdnRelease, release }),
                    $"The CDN's failure ({status?.ToString() ?? "no answer"}) falls back to git.magicbean.dev.");
        }
        server.Files.Remove(cdnRelease);
        Require((await Get(release)).SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { cdnRelease, release }), "A file the CDN lacks.");
        server.Files[cdnRelease] = new Served(other, 0, 400);
        await ThrowsAsync<FetchException>(() => Get(release), "A 400 from the CDN is not a failure of the CDN.");
        Require(server.Asked.SequenceEqual(new[] { cdnRelease }), "A 400 went on to git.magicbean.dev.");
        server.Files[cdnRelease] = new Served(other, 0, 503);
        server.Files[release] = new Served(other, 0, 502);
        try
        {
            await Get(release);
            Require(false, "Both failing was a success.");
        }
        catch (FetchException e) { Require(e.Status == 502 && server.Asked.Count == 2, "Both fail: git.magicbean.dev's failure is the one told."); }
        server.Files[release] = new Served(bytes);

        // (half way: the stream starts again, nothing of the CDN's bytes stays)
        server.Files[cdnRelease] = new Served(other, 70, null);
        var seen = new List<long>();
        server.Asked.Clear();
        using (var to = new MemoryStream())
        {
            to.Write("kept"u8);
            await cdn.DownloadAsync(release, to, seen.Add, CancellationToken.None);
            Require(to.ToArray().SequenceEqual("kept"u8.ToArray().Concat(bytes)) && server.Asked.SequenceEqual(new[] { cdnRelease, release }),
                    "A download the CDN cut short is the server's file, from the stream's start.");
            Require(seen[^1] == bytes.Length && seen.Contains(70), "The progress starts again with the server's download.");
        }
        foreach (var status in new int?[] { 404, 500 })
        {
            server.Files[cdnRelease] = new Served(other, 14, status);
            Require((await Get(release)).SequenceEqual(bytes), $"Cut short with {status}: the server's file only.");
        }
        server.Files[cdnRelease] = new Served(other, 70, null);
        var oneWay = new OneWayStream();
        server.Asked.Clear();
        await ThrowsAsync<FetchException>(() => cdn.DownloadAsync(release, oneWay, null, CancellationToken.None),
                                          "A stream that cannot go back took a second download after the CDN's half.");
        Require(server.Asked.SequenceEqual(new[] { cdnRelease }), "A stream that cannot go back: git.magicbean.dev was asked.");
        server.Files[cdnRelease] = new Served(other, 0, null);
        oneWay = new OneWayStream();
        await cdn.DownloadAsync(release, oneWay, null, CancellationToken.None);
        Require(oneWay.Inner.ToArray().SequenceEqual(bytes), "A stream that cannot go back, the CDN failing before its first byte: the server's file.");

        // (the launcher's update into its file, the CDN cut short: the server's file, checked)
        var root = Folder("cdn");
        var current = Path.Combine(root, "LongshotLauncher.AppImage");
        File.WriteAllText(current, "old");
        server.Files[cdnRelease] = new Served(other, 35, null);
        var staged = await SelfUpdate.DownloadAsync(cdn, new FileRef(release, ShaOf(bytes), bytes.Length), current);
        Require(File.ReadAllBytes(staged).SequenceEqual(bytes), "The launcher's update, the CDN cut short: the whole of the server's file.");
        File.Delete(staged);

        // (not the file its release names: no fall back, the check throws as without the CDN)
        server.Files[cdnRelease] = new Served(other);
        server.Asked.Clear();
        await ThrowsAsync<InvalidDataException>(() => ReleaseManifest.FetchAsync(cdn, new FileRef(release, ShaOf(bytes), bytes.Length), 1 << 20,
                                                                                 CancellationToken.None), "Another file from the CDN was taken.");
        Require(server.Asked.SequenceEqual(new[] { cdnRelease }), "Another file from the CDN went on to git.magicbean.dev.");
        server.Files[cdnRelease] = new Served(bytes.Concat(bytes).ToArray());
        server.Asked.Clear();
        await ThrowsAsync<InvalidDataException>(() => ReleaseManifest.FetchUncheckedAsync(cdn, release, bytes.Length, CancellationToken.None),
                                                "A file larger than expected from the CDN was taken.");
        Require(server.Asked.SequenceEqual(new[] { cdnRelease }), "A file too large from the CDN went on to git.magicbean.dev.");
        server.Files[cdnRelease] = new Served(other);
        server.Asked.Clear();
        await ThrowsAsync<InvalidDataException>(() => SelfUpdate.DownloadAsync(cdn, new FileRef(release, ShaOf(bytes), bytes.Length), current),
                                                "The launcher's update, another file from the CDN, was kept.");
        Require(server.Asked.SequenceEqual(new[] { cdnRelease }) && !File.Exists(SelfUpdate.Staged(current))
                && !File.Exists(SelfUpdate.Staged(current) + ".part"), "Another launcher from the CDN went on, or left a file.");

        // (a builder through Toolchains: the CDN cut short, the checked file starts again; another file is refused)
        var app = Zip(("LongshotBuilder/LongshotBuilder.exe", "MZ", null, 0x1A4), ("LongshotBuilder/tools/nx2/make_game.py", "w", null, 0x1A4),
                      ("LongshotBuilder/tools/python/python.exe", "MZ", null, 0x1A4));
        const string appUrl = "https://git.magicbean.dev/MagicBeanDev/Longshot/releases/download/v3.6.0/LongshotBuilder-v3.6.0-windows-x64.zip";
        var appCdn = CdnFetcher.CdnOf(appUrl)!;
        var otherApp = (byte[])app.Clone();
        otherApp[^30] ^= 1;
        server.Files[appUrl] = new Served(app);
        server.Files[appCdn] = new Served(otherApp, app.Length / 2, null);
        var llvm = Zip(("llvm-mingw-20261104-ucrt-x86_64/bin/clang.exe", "MZ", null, 0x1A4));
        var llvmCdn = cdnPackage.Replace("abc-", ShaOf(llvm) + "-");
        var llvmOrigin = package.Replace("abc-", ShaOf(llvm) + "-");
        server.Files[llvmCdn] = new Served(llvm, 0, 503);
        server.Files[llvmOrigin] = new Served(otherApp);
        server.Files[upstream] = new Served(llvm);
        PartsList Setup(string tag, string toolLinks) => new(ListKind.Setup, tag,
            new List<Part> { new(ShaOf(app), app.Length, ".", null, null, appUrl) }
                .Concat(ToolsLock.Parse($"tool llvm-mingw 20261104 windows-x64 {ShaOf(llvm)} {llvm.Length} LongshotBuilder/tools/llvm-mingw "
                                        + $"llvm-mingw-20261104-ucrt-x86_64 {toolLinks}", "windows-x64")).ToList(), ToolsLock.Run);
        var chains = new Toolchains(Path.Combine(root, "toolchains"), cdn);
        server.Asked.Clear();
        var w = await chains.InstallAsync(Setup("v3.6.0", $"{llvmCdn} {llvmOrigin} {upstream}"));
        Require(File.Exists(Path.Combine(w.ToolsRoot, "llvm-mingw", "bin", "clang.exe")) && File.Exists(w.MakeGame),
                "A builder, the CDN cut short, and a tool from its last link.");
        Require(server.Asked.SequenceEqual(new[] { appCdn, appUrl, llvmCdn, llvmOrigin, upstream }),
                "Each link once, in order (the tool's git-cdn link not tried twice): " + string.Join(", ", server.Asked));
        chains.Prune(Array.Empty<string>());   // (else its parts are kept from v3.6.0, not downloaded)
        server.Asked.Clear();
        await chains.InstallAsync(Setup("v3.6.2", $"{llvmOrigin} {upstream}"));
        Require(server.Asked.SequenceEqual(new[] { appCdn, appUrl, llvmCdn, llvmOrigin, upstream }),
                "A tool listed without its git-cdn link gets it in front: " + string.Join(", ", server.Asked));
        server.Files[appCdn] = new Served(otherApp);
        chains.Prune(Array.Empty<string>());
        server.Asked.Clear();
        await ThrowsAsync<InvalidDataException>(() => chains.InstallAsync(Setup("v3.6.3", $"{llvmOrigin} {upstream}")),
                                                "A builder that is another file from the CDN was installed.");
        Require(server.Asked.SequenceEqual(new[] { appCdn }) && !chains.IsInstalled("v3.6.3"), "Another builder from the CDN went on.");

        // (LONGSHOT_LAUNCHER_NO_CDN=1: everything from git.magicbean.dev, a tool's git-cdn link too)
        Require(!CdnFetcher.EnabledByEnvironment(k => k == CdnFetcher.DisableVariable ? "1" : null)
                && CdnFetcher.EnabledByEnvironment(_ => null) && CdnFetcher.EnabledByEnvironment(k => k == CdnFetcher.DisableVariable ? "0" : null)
                && CdnFetcher.DisableVariable == "LONGSHOT_LAUNCHER_NO_CDN", "LONGSHOT_LAUNCHER_NO_CDN=1 turns the CDN off.");
        var off = new CdnFetcher(server, enabled: false);
        server.Files[cdnRelease] = new Served(other);
        server.Asked.Clear();
        using (var to = new MemoryStream())
        {
            await off.DownloadAsync(release, to, null, CancellationToken.None);
            Require(to.ToArray().SequenceEqual(bytes) && server.Asked.SequenceEqual(new[] { release }), "With the CDN off, git.magicbean.dev only.");
        }
        Require(off.Expand(new[] { llvmCdn, llvmOrigin, upstream }).SequenceEqual(new[] { llvmOrigin, upstream })
                && off.Expand(new[] { cdnRelease }).SequenceEqual(new[] { cdnRelease })
                && cdn.Expand(new[] { llvmCdn, llvmOrigin, upstream }).SequenceEqual(new[] { llvmCdn, llvmOrigin, upstream })
                && cdn.Expand(new[] { llvmOrigin, upstream }).SequenceEqual(new[] { llvmCdn, llvmOrigin, upstream }),
                "A tool's links with the CDN on and off.");
        server.Files[appCdn] = new Served(otherApp);
        server.Files[llvmOrigin] = new Served(llvm);
        server.Asked.Clear();
        await new Toolchains(Path.Combine(root, "toolchains-off"), off).InstallAsync(Setup("v3.6.4", $"{llvmCdn} {llvmOrigin} {upstream}"));
        Require(server.Asked.SequenceEqual(new[] { appUrl, llvmOrigin }), "With the CDN off, no git-cdn link: " + string.Join(", ", server.Asked));
    }
}
