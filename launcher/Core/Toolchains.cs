using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace LongshotLauncher.Core;

/// How far an install is: Fraction 0..1 of the bytes of all its parts (a part kept from another version counts as done)
public sealed record ToolchainProgress(double Fraction, int Part, int Parts, string Text);

/// One installed version's build tools: nx2/make_game.py under ToolsRoot, and the Python that runs it
public sealed record Toolchain(string Tag, string Folder, ListKind Kind, string? Run)
{
    /// Windows: the setup's LongshotBuilder/tools beside its builder; Linux: the AppImage's usr/share/longshot
    public string ToolsRoot => Kind == ListKind.Setup
        ? Path.Combine(Folder, Path.GetDirectoryName(Run ?? "LongshotBuilder/x")!.Replace('/', Path.DirectorySeparatorChar), "tools")
        : Path.Combine(Folder, "usr", "share", "longshot");

    /// Linux: the AppImage's usr/lib/longshot (the prebuilt Vulkan back end, and beside it tools.lock's emsdk, sysroot, FFmpeg and
    /// SDL2, unpacked there by InstallAppImageAsync; an older AppImage carries them itself. builder/linux/AppRun)
    public string LibRoot => Path.Combine(Folder, "usr", "lib", "longshot");

    public string Python => Kind == ListKind.Setup
        ? Path.Combine(ToolsRoot, "python", "python.exe")
        : Path.Combine(Folder, "usr", "python", "bin", "python3");

    public string MakeGame => Path.Combine(ToolsRoot, "nx2", "make_game.py");
}

/// The build tools of each version the launcher builds with, in &lt;home&gt;/toolchains/&lt;tag&gt;/, from the version's parts (its
/// release's builder and the tools of its tools.lock).
/// Each part is checked for its size and SHA-256 before it is unpacked; a part another installed version already has (the same
/// SHA-256, unpacked the same way) is linked or copied from it instead of downloaded. A version is unpacked into &lt;tag&gt;.part and
/// renamed once complete, so a failed or cancelled install leaves nothing that looks installed.
public sealed class Toolchains
{
    public const string RecordName = "toolchain.json";
    public const string SysrootPart = "usr/lib/longshot/sysroot";   // (its rooted links are rebased inside it)
    const string Downloads = ".downloads";

    readonly string root;
    readonly IFetcher fetcher;

    public Toolchains(string root, IFetcher fetcher)
    {
        this.root = root;
        this.fetcher = fetcher;
    }

    public string Root => root;

    public string PathOf(string tag) =>
        Versions.IsTagName(tag) ? Path.Combine(root, tag) : throw new ArgumentException("Not a version name: " + tag, nameof(tag));

    public Toolchain? Find(string tag)
    {
        if (!Versions.IsTagName(tag)) return null;
        var record = Read(Path.Combine(root, tag));
        return record == null ? null : new Toolchain(tag, Path.Combine(root, tag), record.Kind, record.Run);
    }

    public bool IsInstalled(string tag) => Find(tag) != null;

    public IReadOnlyList<string> Installed()
    {
        if (!Directory.Exists(root)) return Array.Empty<string>();
        return Directory.EnumerateDirectories(root).Select(Path.GetFileName).OfType<string>()
            .Where(n => Versions.IsTagName(n) && !n.EndsWith(".part", StringComparison.Ordinal) && Read(Path.Combine(root, n)) != null)
            .OrderBy(n => n, StringComparer.Ordinal).ToList();
    }

    /// Every version folder (and leftover staging or download) that keep does not name; the names removed
    public IReadOnlyList<string> Prune(IEnumerable<string> keep)
    {
        var kept = new HashSet<string>(keep, StringComparer.Ordinal);
        var removed = new List<string>();
        if (!Directory.Exists(root)) return removed;
        foreach (var dir in Directory.EnumerateDirectories(root))
        {
            var name = Path.GetFileName(dir);
            var stale = name == Downloads || name.EndsWith(".part", StringComparison.Ordinal);
            if (!stale && (!Versions.IsTagName(name) || kept.Contains(name))) continue;
            DeleteTree(dir);
            removed.Add(name);
        }
        return removed;
    }

    public async Task<Toolchain> InstallAsync(PartsList list, Action<ToolchainProgress>? progress = null, CancellationToken cancel = default)
    {
        var dest = PathOf(list.Tag);
        var staging = dest + ".part";
        Directory.CreateDirectory(root);
        if (new DirectoryInfo(staging).LinkTarget != null) throw new IOException("The tools' staging folder is a symbolic link: " + staging);
        if (Directory.Exists(staging)) DeleteTree(staging);
        Directory.CreateDirectory(staging);
        var downloads = Path.Combine(root, Downloads);
        var total = Math.Max(1, list.Parts.Sum(p => p.Size));
        long done = 0;
        var sources = Others(list.Tag);
        var record = new Record { Tag = list.Tag, Kind = list.Kind, Run = list.Run };
        try
        {
            for (var i = 0; i < list.Parts.Count; i++)
            {
                cancel.ThrowIfCancellationRequested();
                var part = list.Parts[i];
                var entries = new List<Entry>();
                if (Reuse(part, sources, staging, entries))
                    progress?.Invoke(new ToolchainProgress((done += part.Size) / (double)total, i + 1, list.Parts.Count,
                                                           $"Part {i + 1} of {list.Parts.Count} unchanged: kept from an installed version"));
                else
                {
                    Directory.CreateDirectory(downloads);
                    var zip = Path.Combine(downloads, part.Sha + ".zip.part");
                    var before = done;
                    try
                    {
                        progress?.Invoke(new ToolchainProgress(done / (double)total, i + 1, list.Parts.Count,
                                                               $"Downloading part {i + 1} of {list.Parts.Count} ({part.Size >> 20} MB)"));
                        await Download(part, zip, have => progress?.Invoke(new ToolchainProgress(
                            (before + Math.Min(have, part.Size)) / (double)total, i + 1, list.Parts.Count,
                            $"Downloading part {i + 1} of {list.Parts.Count} ({have >> 20} of {part.Size >> 20} MB)")), cancel);
                        cancel.ThrowIfCancellationRequested();
                        Unpack(zip, part, staging, entries);
                    }
                    finally
                    {
                        File.Delete(zip);
                    }
                    done += part.Size;
                    progress?.Invoke(new ToolchainProgress(done / (double)total, i + 1, list.Parts.Count, $"Part {i + 1} of {list.Parts.Count} ready"));
                }
                record.Parts.Add(new RecordPart
                {
                    Sha = part.Sha, Size = part.Size, Dest = part.Dest, From = part.From, To = part.To, Url = part.Url, Entries = entries,
                });
            }
            CheckLinksInside(staging);
            using (var f = new FileStream(Path.Combine(staging, RecordName), FileMode.CreateNew, FileAccess.Write))
                JsonSerializer.Serialize(f, record, CoreJson.Default.Record);
            cancel.ThrowIfCancellationRequested();   // (the last moment: from here the new folder takes the old one's place)
        }
        catch
        {
            DeleteTree(staging);
            throw;
        }
        if (Directory.Exists(dest)) DeleteTree(dest);
        Directory.Move(staging, dest);
        TryDeleteEmpty(downloads);
        return new Toolchain(list.Tag, dest, list.Kind, list.Run);
    }

    // ---- reuse ----

    List<(string Folder, Record Record)> Others(string tag)
    {
        var found = new List<(string, Record)>();
        foreach (var name in Installed())
            if (name != tag && Read(Path.Combine(root, name)) is { } r) found.Add((Path.Combine(root, name), r));
        return found;
    }

    static bool Reuse(Part part, List<(string Folder, Record Record)> sources, string staging, List<Entry> entries)
    {
        foreach (var (folder, record) in sources)
        {
            var old = record.Parts.FirstOrDefault(p => p.AsPart().Same(part));
            if (old == null || old.Entries.Count == 0) continue;
            if (!old.Entries.All(e => Exists(Path.Combine(folder, Native(e.Path)), e.Link != null))) continue;
            var made = new List<string>();
            try
            {
                foreach (var e in old.Entries)
                {
                    var target = Path.Combine(staging, Native(e.Path));
                    EnsureParent(staging, target);
                    if (e.Link != null) Symlink(staging, e.Link, target);
                    else FileLinks.LinkOrCopy(Path.Combine(folder, Native(e.Path)), target);
                    made.Add(target);
                    entries.Add(e);
                }
                return true;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                foreach (var m in made) File.Delete(m);
                entries.Clear();
            }
        }
        return false;
    }

    static bool Exists(string path, bool link)
    {
        var info = new FileInfo(path);
        return link ? info.LinkTarget != null : info.Exists && info.LinkTarget == null;
    }

    // ---- download and unpack ----

    /// The part from its link, else from each of its mirrors in turn: the first whose bytes are the ones the list names
    async Task Download(Part part, string zip, Action<long> progress, CancellationToken cancel)
    {
        Exception? last = null;
        IReadOnlyList<string> urls = new[] { part.Url }.Concat(part.Mirrors ?? Array.Empty<string>()).ToList();
        var through = fetcher;
        if (part.Mirrors is { Count: > 0 } && fetcher is CdnFetcher cdn)
        {
            // (a tool's own links, git-cdn's among them: each tried as it is, in order, so that no link is tried twice)
            urls = cdn.Expand(urls);
            through = cdn.Inner;
        }
        foreach (var url in urls)
        {
            try
            {
                await DownloadFrom(through, url, part.Sha, part.Size, zip, progress, cancel);
                return;
            }
            catch (Exception e) when (e is FetchException or InvalidDataException) { last = e; }
        }
        throw last!;
    }

    static async Task DownloadFrom(IFetcher fetcher, string url, string sha, long size, string path, Action<long> progress, CancellationToken cancel)
    {
        await using var file = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None);
        await using var checking = new CheckedStream(file, size);
        await fetcher.DownloadAsync(url, checking, progress, cancel);
        if (checking.Length != size)
            throw new InvalidDataException($"A part of the tools did not download completely ({checking.Length} of {size} bytes).");
        if (!CryptographicOperations.FixedTimeEquals(checking.Hash(), Convert.FromHexString(sha)))
            throw new InvalidDataException("A part of the tools did not download correctly (its checksum differs).");
    }

    /// The Linux builder of a release: its AppImage, checked by its size and SHA-256, unpacked (extract: the AppImage's own
    /// --appimage-extract, run in a folder, making squashfs-root there) into &lt;tag&gt;.part, then the build tools of the
    /// tools.lock inside it (its linux-x64 lines, covered by the AppImage's checksum) unpacked beside it at their dests, as on
    /// Windows: each checked by its size and SHA-256, or kept from another installed version. Renamed once complete. An
    /// AppImage with no tools.lock inside carries its own tools: nothing else is downloaded
    public async Task<Toolchain> InstallAppImageAsync(string tag, FileRef file, Func<string, string, CancellationToken, Task>? extract = null,
                                                      Action<ToolchainProgress>? progress = null, CancellationToken cancel = default)
    {
        if (!Versions.IsTagName(tag)) throw new ArgumentException("Not a version name: " + tag, nameof(tag));
        var dest = PathOf(tag);
        var work = dest + ".part";
        Directory.CreateDirectory(root);
        if (Directory.Exists(work)) DeleteTree(work);
        Directory.CreateDirectory(work);
        try
        {
            var image = Path.Combine(work, "builder.AppImage");
            // (the builder first, then its tools: its share of the bar until its tools.lock says how much more there is)
            const double builderShare = 0.4;
            progress?.Invoke(new ToolchainProgress(0, 1, 1, $"Downloading the builder ({file.Size >> 20} MB)"));
            await DownloadFrom(fetcher, file.Url, file.Sha256, file.Size, image, have => progress?.Invoke(new ToolchainProgress(
                Math.Min(have, file.Size) / (double)Math.Max(1, file.Size) * builderShare, 1, 1,
                $"Downloading the builder ({have >> 20} of {file.Size >> 20} MB)")), cancel);
            if (!OperatingSystem.IsWindows()) File.SetUnixFileMode(image, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            progress?.Invoke(new ToolchainProgress(builderShare, 1, 1, "Unpacking the builder"));
            await (extract ?? ExtractAppImage)(image, work, cancel);
            var tree = Path.Combine(work, "squashfs-root");
            if (!File.Exists(Path.Combine(tree, "AppRun"))) throw new InvalidDataException("The builder's AppImage has no AppRun.");
            File.Delete(image);
            CheckLinksInside(tree);
            var record = new Record { Tag = tag, Kind = ListKind.Linux };
            record.Parts.Add(new RecordPart { Sha = file.Sha256, Size = file.Size, Dest = ".", Url = file.Url });
            var lockFile = Path.Combine(tree, Native(LinuxToolsLock));
            if (File.Exists(lockFile) && new FileInfo(lockFile).LinkTarget == null)
            {
                var parts = ToolsLock.Parse(await File.ReadAllTextAsync(lockFile, cancel), ReleaseManifest.PlatformKey(Platform.Linux));
                await InstallTools(tag, parts, tree, Path.Combine(root, Downloads), record, builderShare, progress, cancel);
                CheckLinksInside(tree);
            }
            using (var f = new FileStream(Path.Combine(tree, RecordName), FileMode.CreateNew, FileAccess.Write))
                JsonSerializer.Serialize(f, record, CoreJson.Default.Record);
            cancel.ThrowIfCancellationRequested();
            if (Directory.Exists(dest)) DeleteTree(dest);
            Directory.Move(tree, dest);
        }
        finally
        {
            if (Directory.Exists(work)) DeleteTree(work);
        }
        progress?.Invoke(new ToolchainProgress(1, 1, 1, "The builder is ready"));
        return new Toolchain(tag, dest, ListKind.Linux, null);
    }

    /// The tools.lock a Linux builder carries (builder/linux/AppRun, scripts/linux/appimage.sh)
    public const string LinuxToolsLock = "usr/share/longshot/tools.lock";

    /// Each part into tree (a Linux builder's), kept from another installed version when one has it, else downloaded and
    /// unpacked; recorded for the next version's reuse. The bar goes from start to 1 by the parts' bytes
    async Task InstallTools(string tag, IReadOnlyList<Part> parts, string tree, string downloads, Record record, double start,
                            Action<ToolchainProgress>? progress, CancellationToken cancel)
    {
        var sources = Others(tag);
        var total = Math.Max(1, parts.Sum(p => p.Size));
        long done = 0;
        double At(long bytes) => start + (1 - start) * Math.Min(bytes, total) / total;
        for (var i = 0; i < parts.Count; i++)
        {
            cancel.ThrowIfCancellationRequested();
            var part = parts[i];
            var entries = new List<Entry>();
            var where = part.To == null ? part.Dest : part.Dest + "/" + part.To;
            if (Directory.Exists(Path.Combine(tree, Native(where)))) { done += part.Size; continue; }   // (a builder that carries it still)
            if (Reuse(part, sources, tree, entries))
                progress?.Invoke(new ToolchainProgress(At(done += part.Size), i + 1, parts.Count,
                                                       $"Build tool {i + 1} of {parts.Count} unchanged: kept from an installed version"));
            else
            {
                Directory.CreateDirectory(downloads);
                var zip = Path.Combine(downloads, part.Sha + ".zip.part");
                var before = done;
                try
                {
                    progress?.Invoke(new ToolchainProgress(At(done), i + 1, parts.Count,
                                                           $"Downloading build tool {i + 1} of {parts.Count} ({part.Size >> 20} MB)"));
                    await Download(part, zip, have => progress?.Invoke(new ToolchainProgress(At(before + Math.Min(have, part.Size)), i + 1,
                        parts.Count, $"Downloading build tool {i + 1} of {parts.Count} ({have >> 20} of {part.Size >> 20} MB)")), cancel);
                    cancel.ThrowIfCancellationRequested();
                    Unpack(zip, part, tree, entries);
                }
                finally
                {
                    File.Delete(zip);
                }
                done += part.Size;
            }
            record.Parts.Add(new RecordPart
            {
                Sha = part.Sha, Size = part.Size, Dest = part.Dest, From = part.From, To = part.To, Url = part.Url, Entries = entries,
            });
        }
        TryDeleteEmpty(downloads);
    }

    static async Task ExtractAppImage(string image, string folder, CancellationToken cancel)
    {
        var si = new System.Diagnostics.ProcessStartInfo(image, "--appimage-extract")
        {
            WorkingDirectory = folder, UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true,
        };
        si.Environment.Remove("APPIMAGE");
        si.Environment.Remove("APPDIR");
        using var p = System.Diagnostics.Process.Start(si) ?? throw new IOException("The builder's AppImage did not start.");
        var output = p.StandardOutput.ReadToEndAsync(cancel);
        var error = p.StandardError.ReadToEndAsync(cancel);
        await p.WaitForExitAsync(cancel);
        await Task.WhenAll(output, error);
        if (p.ExitCode != 0) throw new IOException($"The builder's AppImage could not be unpacked ({p.ExitCode}): {error.Result.Trim()}");
    }

    static string Native(string rel) => rel.Replace('/', Path.DirectorySeparatorChar);

    /// A zip entry's name: relative, '/' between its parts, none of them "..", no drive or backslash
    static string ZipName(string name)
    {
        if (!ToolsLock.SafeName(name) || name.Contains('\\') || name.Contains(':') || name.Split('/').Any(p => p == "."))
            throw new InvalidDataException("A part of the tools has a path outside its folder: " + name);
        return name;
    }

    static void Unpack(string zipPath, Part part, string staging, List<Entry> entries)
    {
        var rooted = new List<(string Target, string Rel, string LinkTo)>();
        var dest = part.Dest == "." ? staging : Path.Combine(staging, Native(part.Dest));
        using (var zip = ZipFile.OpenRead(zipPath))
            foreach (var entry in zip.Entries)
            {
                var name = entry.FullName;
                if (name.EndsWith('/')) continue;
                ZipName(name);
                if (part.From != null)
                {
                    // (a tool's archive may hold more than its folder: only the folder is taken, tools.lock's prefix)
                    if (!name.StartsWith(part.From + "/", StringComparison.Ordinal)) continue;
                    name = part.To + name[part.From.Length..];
                }
                var rel = part.Dest == "." ? name : part.Dest + "/" + name;
                var target = Path.Combine(staging, Native(rel));
                EnsureParent(staging, target);
                var mode = (entry.ExternalAttributes >> 16) & 0xFFFF;
                if ((mode & 0xF000) == 0xA000)
                {
                    string linkTo;
                    using (var reader = new StreamReader(entry.Open())) linkTo = reader.ReadToEnd();
                    if (linkTo.StartsWith('/'))
                    {
                        // (released sysroots hold /lib links rooted inside the sysroot; other parts must not have absolute links)
                        if (part.Dest != SysrootPart) throw new InvalidDataException($"A part of the tools has an absolute link: {name} -> {linkTo}");
                        rooted.Add((target, rel, linkTo));
                        continue;
                    }
                    Symlink(staging, linkTo, target);
                    entries.Add(new Entry { Path = rel, Link = linkTo });
                    continue;
                }
                using (var from = entry.Open())
                using (var to = new FileStream(target, FileMode.CreateNew, FileAccess.Write))
                    from.CopyTo(to);
                if (!OperatingSystem.IsWindows() && (mode & 0x1FF) != 0)   // (the modes the parts are made with: none group- or world-writable)
                    File.SetUnixFileMode(target, (mode & 0x49) != 0
                        ? UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute | UnixFileMode.GroupRead
                          | UnixFileMode.GroupExecute | UnixFileMode.OtherRead | UnixFileMode.OtherExecute
                        : UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.GroupRead | UnixFileMode.OtherRead);
                entries.Add(new Entry { Path = rel });
            }
        // (a sysroot link may name a file a later link makes: until none is left, or none can be made)
        while (rooted.Count > 0)
        {
            var pending = new List<(string Target, string Rel, string LinkTo)>();
            foreach (var r in rooted)
            {
                if (r.LinkTo.StartsWith("//", StringComparison.Ordinal)) throw new InvalidDataException("Not a rooted sysroot link: " + r.LinkTo);
                var destination = Path.GetFullPath(Path.Combine(dest, Native(r.LinkTo.TrimStart('/'))));
                if (!Inside(dest, destination)) throw new InvalidDataException($"A sysroot link leaves its root: {r.Rel} -> {r.LinkTo}");
                if (!File.Exists(destination) && !Directory.Exists(destination)) { pending.Add(r); continue; }
                var relative = Path.GetRelativePath(Path.GetDirectoryName(r.Target)!, destination).Replace(Path.DirectorySeparatorChar, '/');
                Symlink(staging, relative, r.Target);
                entries.Add(new Entry { Path = r.Rel, Link = relative });
            }
            if (pending.Count == rooted.Count)
                throw new InvalidDataException("Sysroot links have missing or circular targets: " + string.Join(", ", pending.Select(p => p.Rel)));
            rooted = pending;
        }
    }

    static bool Inside(string root, string path)
    {
        var full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root));
        var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        return path.Equals(full, comparison) || path.StartsWith(full + Path.DirectorySeparatorChar, comparison);
    }

    /// The folders up to target's, made under root; never through a link a part made
    static void EnsureParent(string root, string target)
    {
        var parent = Path.GetDirectoryName(Path.GetFullPath(target))!;
        if (!Inside(root, parent)) throw new InvalidDataException("A part of the tools would write outside its folder: " + target);
        var rel = Path.GetRelativePath(Path.GetFullPath(root), parent);
        var at = Path.GetFullPath(root);
        if (rel == ".") return;
        foreach (var piece in rel.Split(Path.DirectorySeparatorChar))
        {
            at = Path.Combine(at, piece);
            var info = new DirectoryInfo(at);
            if (info.LinkTarget != null || new FileInfo(at).LinkTarget != null)
                throw new InvalidDataException("A part of the tools would write through a symbolic link: " + at);
            if (File.Exists(at)) throw new InvalidDataException("A part of the tools has a file where a folder goes: " + at);
            if (!info.Exists) info.Create();
        }
    }

    /// linux_update._symlink: a relative link whose ".." come first, landing inside the staging folder
    static void Symlink(string root, string linkTo, string target)
    {
        var parts = linkTo.Split('/');
        var ups = 0;
        while (ups < parts.Length && parts[ups] == "..") ups++;
        if (parts.Skip(ups).Contains("..") || linkTo.StartsWith('/') || linkTo.Contains('\\'))
            throw new InvalidDataException($"A link in the tools climbs after a name: {target} -> {linkTo}");
        var destination = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(target)!, Native(linkTo)));
        if (!Inside(root, destination)) throw new InvalidDataException($"A link in the tools leaves its folder: {target} -> {linkTo}");
        File.CreateSymbolicLink(target, linkTo);
    }

    /// Every link in the finished folder resolves inside it, whatever order the parts made them in
    static void CheckLinksInside(string staging)
    {
        var options = new EnumerationOptions { RecurseSubdirectories = true, AttributesToSkip = 0, IgnoreInaccessible = false };
        foreach (var path in Directory.EnumerateFileSystemEntries(staging, "*", options))
        {
            var info = new FileInfo(path);
            if (info.LinkTarget == null) continue;
            var final = info.ResolveLinkTarget(returnFinalTarget: true);
            if (final == null || !Inside(staging, Path.GetFullPath(final.FullName)))
                throw new InvalidDataException("A link in the tools leaves its folder: " + path);
        }
    }

    // ---- the record each version keeps of its parts: what reuse reads ----

    static Record? Read(string folder)
    {
        try
        {
            using var f = File.OpenRead(Path.Combine(folder, RecordName));
            return JsonSerializer.Deserialize(f, CoreJson.Default.Record);
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or JsonException) { return null; }
    }

    /// A folder and everything in it; a link in it is removed, never followed
    public static void DeleteTree(string dir)
    {
        var info = new DirectoryInfo(dir);
        if (info.LinkTarget != null) { info.Delete(); return; }
        if (!info.Exists) return;
        foreach (var child in info.EnumerateFileSystemInfos())
        {
            if (child is DirectoryInfo d && d.LinkTarget == null) DeleteTree(d.FullName);
            else
            {
                if (!OperatingSystem.IsWindows() || child.LinkTarget != null) { child.Delete(); continue; }
                child.Attributes = FileAttributes.Normal;
                child.Delete();
            }
        }
        info.Delete();
    }

    static void TryDeleteEmpty(string dir)
    {
        try { if (Directory.Exists(dir) && !Directory.EnumerateFileSystemEntries(dir).Any()) Directory.Delete(dir); }
        catch (IOException) { }
    }

    internal sealed class Record
    {
        public int Format { get; set; } = 1;
        public string Tag { get; set; } = "";
        [JsonConverter(typeof(JsonStringEnumConverter<ListKind>))]
        public ListKind Kind { get; set; }
        public string? Run { get; set; }
        public List<RecordPart> Parts { get; set; } = new();
    }

    internal sealed class RecordPart
    {
        public string Sha { get; set; } = "";
        public long Size { get; set; }
        public string Dest { get; set; } = ".";
        public string? From { get; set; }
        public string? To { get; set; }
        public string Url { get; set; } = "";
        public List<Entry> Entries { get; set; } = new();

        public Part AsPart() => new(Sha, Size, Dest, From, To, Url);
    }

    /// One file a part put in the version's folder, relative with '/'; Link: a symbolic link's target
    internal sealed class Entry
    {
        public string Path { get; set; } = "";
        public string? Link { get; set; }
    }

    /// The bytes written through it, counted and hashed, and stopped past the size the list says
    sealed class CheckedStream : Stream
    {
        readonly Stream inner;
        readonly long limit;
        readonly IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        long length;

        public CheckedStream(Stream inner, long limit)
        {
            this.inner = inner;
            this.limit = limit;
        }

        public byte[] Hash() => hash.GetHashAndReset();

        void Count(ReadOnlySpan<byte> data)
        {
            length += data.Length;
            if (length > limit) throw new InvalidDataException("A part of the tools is larger than its list says.");
            hash.AppendData(data);
        }

        public override void Write(byte[] buffer, int offset, int count) => Write(buffer.AsSpan(offset, count));

        public override void Write(ReadOnlySpan<byte> buffer)
        {
            Count(buffer);
            inner.Write(buffer);
        }

        public override async ValueTask WriteAsync(ReadOnlyMemory<byte> buffer, CancellationToken cancel = default)
        {
            Count(buffer.Span);
            await inner.WriteAsync(buffer, cancel);
        }

        public override Task WriteAsync(byte[] buffer, int offset, int count, CancellationToken cancel) =>
            WriteAsync(buffer.AsMemory(offset, count), cancel).AsTask();

        // (seekable only back to its start, with what it had counted dropped: a download started again, CdnFetcher's fallback)
        public override bool CanRead => false;
        public override bool CanSeek => inner.CanSeek;
        public override bool CanWrite => true;
        public override long Length => length;
        public override long Position { get => length; set => Seek(value, SeekOrigin.Begin); }
        public override void Flush() => inner.Flush();
        public override Task FlushAsync(CancellationToken cancel) => inner.FlushAsync(cancel);
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        public override long Seek(long offset, SeekOrigin origin) =>
            (origin == SeekOrigin.Current ? length + offset : offset) == length ? length : throw new NotSupportedException();

        public override void SetLength(long value)
        {
            if (value != 0 || !inner.CanSeek) throw new NotSupportedException();
            inner.SetLength(0);
            inner.Position = 0;
            hash.GetHashAndReset();
            length = 0;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) hash.Dispose();
            base.Dispose(disposing);
        }
    }
}
