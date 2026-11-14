using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;

namespace HookshotLauncher.Core;

/// The launcher updating itself (docs/launcher.md, "Releases and channels"). It is one file on both systems, a
/// self-contained single-file program on Windows and an AppImage on Linux, so an update is one file, whatever that file is named:
///   1. download the release's launcher of this kind (LauncherLayout.UpdateKey: the setup program, the program out of the portable
///      zip, or the AppImage) beside this one as &lt;name&gt;.new, checked for its size and SHA-256 (the signed release names both);
///   2. start it with --self-check, which must answer with the version the release names, so a file that does not run on this
///      PC is never put in place;
///   3. swap: this file becomes &lt;name&gt;.old (kept for --rollback), the new one takes its name, so the file keeps the name it was
///      installed or started as (an installed launcher stays HookshotLauncher.exe, a portable one stays beside its "portable" file);
///   4. start the new one, and close.
/// A crash between the two renames of step 3 on Windows is put right at the next start (Recover).
/// Only a newer version on the launcher's own track is offered; a build from a checkout ("dev") never updates itself.
public static class SelfUpdate
{
    public const string TagKey = "HookshotTag";
    public const string CheckArgument = "--self-check", RollbackArgument = "--rollback";

    /// This launcher's version: the tag the release build stamped (-p:HookshotTag=, an AssemblyMetadata), else "dev"
    public static string OwnTag(Assembly? assembly = null) =>
        (assembly ?? Assembly.GetEntryAssembly())?.GetCustomAttributes<AssemblyMetadataAttribute>()
        .FirstOrDefault(a => a.Key == TagKey)?.Value is { Length: > 0 } tag && Versions.IsTagName(tag) ? tag : "dev";

    /// What --self-check prints
    public static string CheckLine(string tag) => "HookshotLauncher " + tag;

    /// The launcher's channel: the one the player chose, else its own version's track (a build from a checkout follows stable)
    public static string ChannelOf(string own, string? chosen) =>
        Versions.IsChannel(chosen) ? chosen! : Versions.TrackOf(own, Versions.LauncherFirstMajor);

    /// The version to update the launcher to from its channel's newest: a newer one on its own track, or, after the player chose
    /// another channel, that channel's newest; never for a build from a checkout ("dev"), never one with no launcher for this system
    public static string? UpdateTo(string own, ReleaseInfo? newest, Platform platform, string? channel = null, string? key = null)
    {
        if (newest == null || newest.Version == own || !newest.Launcher.ContainsKey(key ?? ReleaseManifest.PlatformKey(platform))) return null;
        var track = Versions.TrackOf(own, Versions.LauncherFirstMajor);
        var isVersion = Versions.IsRelease(own, Versions.LauncherFirstMajor) || track == Versions.Nightly;
        if (!isVersion) return null;
        if (channel != null && channel != track && !(channel == Versions.Candidate && track == Versions.Stable)) return newest.Version;
        return Versions.Newer(newest.Version, own, Versions.LauncherFirstMajor) ? newest.Version : null;
    }

    /// How an offered launcher compares with this one, for the home's banner: newer, older (after the player switched to a channel
    /// whose newest is behind this one), or neither (a nightly against a release: no order between them)
    public static int Compare(string offered, string own) =>
        Versions.Newer(offered, own, Versions.LauncherFirstMajor) ? 1 : Versions.Newer(own, offered, Versions.LauncherFirstMajor) ? -1 : 0;

    /// The file this launcher runs from: the AppImage on Linux ($APPIMAGE), else the program itself, whatever it is named (the
    /// download's HookshotLauncher-&lt;v&gt;-windows-x64-setup.exe, the installed HookshotLauncher.exe, a renamed copy); null when it is
    /// not one that can replace itself (dotnet run: dotnet.exe; a dll)
    public static string? CurrentFile(Platform platform, Func<string, string?>? getenv = null, string? processPath = null)
    {
        getenv ??= Environment.GetEnvironmentVariable;
        processPath ??= Environment.ProcessPath;
        if (platform == Platform.Linux)
            return getenv("APPIMAGE") is { Length: > 0 } appImage && appImage.StartsWith('/') ? appImage : null;   // (a Linux path, whatever system reads it)
        if (processPath == null) return null;
        // (either separator: the name is read the same on any system)
        var name = processPath.Split('/', '\\')[^1];
        return name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) && !name.Equals("dotnet.exe", StringComparison.OrdinalIgnoreCase)
            ? processPath : null;
    }

    /// What a start finds left of an update cut short (the PC lost power, the launcher was killed), put right: with no current
    /// file but its .old, the .old goes back (Windows: the old one had been moved aside, the new one not yet in); a .new or its
    /// .part left over goes. Returns what was done, null when nothing was left over
    public static string? Recover(string current)
    {
        string? done = null;
        var backup = Backup(current);
        if (!File.Exists(current) && File.Exists(backup))
        {
            File.Move(backup, current);
            done = $"The last update of the launcher was cut short; the launcher before it is back as {Path.GetFileName(current)}.";
        }
        foreach (var left in new[] { Staged(current), Staged(current) + ".part", Staged(current) + ".zip.part" })
        {
            if (!File.Exists(left)) continue;
            File.Delete(left);
            done ??= "The files of an update cut short were removed.";
        }
        return done;
    }

    /// The file of the launcher a leftover is of: &lt;name&gt; for &lt;name&gt;.old or &lt;name&gt;.new (a launcher started from one of them,
    /// when its own file is gone); null for any other file
    public static string? LeftoverOf(string file) =>
        file.EndsWith(".old", StringComparison.OrdinalIgnoreCase) || file.EndsWith(".new", StringComparison.OrdinalIgnoreCase) ? file[..^4] : null;

    public static string Staged(string current) => current + ".new";
    public static string Backup(string current) => current + ".old";

    /// The release's launcher for this system into &lt;current&gt;.new, checked; its path. Executable on Linux. zipEntry: the file is a
    /// zip (the portable one), checked as a whole, and the launcher is that entry of it
    public static async Task<string> DownloadAsync(IFetcher fetcher, FileRef file, string current, Action<double>? progress = null,
                                                   CancellationToken cancel = default, string? zipEntry = null)
    {
        var staged = Staged(current);
        var part = staged + (zipEntry != null ? ".zip.part" : ".part");
        try
        {
            using (var to = new FileStream(part, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                await fetcher.DownloadAsync(file.Url, to, have =>
                {
                    if (have > file.Size) throw new InvalidDataException("The new launcher is larger than its release says.");
                    progress?.Invoke(file.Size == 0 ? 1 : have / (double)file.Size);
                }, cancel).ConfigureAwait(false);
                to.Flush(flushToDisk: true);
            }
            string sha;
            using (var f = File.OpenRead(part))
            {
                if (f.Length != file.Size) throw new InvalidDataException("The new launcher is not the size its release says.");
                sha = Convert.ToHexStringLower(await SHA256.HashDataAsync(f, cancel).ConfigureAwait(false));
            }
            if (sha != file.Sha256) throw new InvalidDataException("The new launcher is not the file its release names (SHA-256).");
            if (zipEntry != null)
            {
                var program = staged + ".part";
                try
                {
                    Unzip(part, zipEntry, program);
                    File.Move(program, staged, overwrite: true);
                }
                finally { File.Delete(program); }
                return staged;
            }
            if (!OperatingSystem.IsWindows())
                File.SetUnixFileMode(part, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute | UnixFileMode.GroupRead
                                           | UnixFileMode.GroupExecute | UnixFileMode.OtherRead | UnixFileMode.OtherExecute);
            File.Move(part, staged, overwrite: true);
            return staged;
        }
        finally
        {
            File.Delete(part);
        }
    }

    /// The one entry of a checked zip (the portable launcher's program) into to; refused when the zip does not have it, or it is
    /// larger than any launcher
    static void Unzip(string zip, string entry, string to)
    {
        using var archive = System.IO.Compression.ZipFile.OpenRead(zip);
        var e = archive.Entries.FirstOrDefault(x => x.FullName == entry)
                ?? throw new InvalidDataException($"The portable launcher's zip has no {entry}.");
        if (e.Length > 1L << 30) throw new InvalidDataException($"The portable launcher's {entry} is larger than any launcher.");
        using (var from = e.Open())
        using (var file = new FileStream(to, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            from.CopyTo(file);
            file.Flush(flushToDisk: true);
        }
        if (new FileInfo(to).Length != e.Length) throw new InvalidDataException($"The portable launcher's {entry} did not unpack whole.");
    }

    /// Starts staged with --self-check: true when it answers CheckLine(tag) and ends well within timeout
    public static async Task<bool> SelfCheckAsync(string staged, string tag, TimeSpan timeout)
    {
        var start = new ProcessStartInfo(staged) { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        start.ArgumentList.Add(CheckArgument);
        // (its own AppImage, not this one's: the AppImage runtime sets APPIMAGE for the program it starts)
        start.Environment.Remove("APPIMAGE");
        start.Environment.Remove("APPDIR");
        using var cancel = new CancellationTokenSource(timeout);
        try
        {
            using var p = Process.Start(start);
            if (p == null) return false;
            var output = p.StandardOutput.ReadToEndAsync(cancel.Token);
            _ = p.StandardError.ReadToEndAsync(cancel.Token);
            await p.WaitForExitAsync(cancel.Token).ConfigureAwait(false);
            return p.ExitCode == 0 && (await output.ConfigureAwait(false)).Split('\n').Any(l => l.Trim() == CheckLine(tag));
        }
        catch (OperationCanceledException) { return false; }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException or InvalidOperationException) { return false; }
    }

    /// The new launcher in place of the current one, the current one kept as &lt;current&gt;.old. On Linux the current file is
    /// copied aside and the new one renamed over it, one rename, so there is never a moment without it (the running AppImage keeps
    /// its own, unlinked file). Windows does not let a running program be overwritten, only renamed: it goes aside first, and comes
    /// back if the new one cannot take its place.
    public static void Swap(string current, string staged, Platform platform)
    {
        var backup = Backup(current);
        if (platform == Platform.Linux)
        {
            File.Copy(current, backup + ".part", overwrite: true);
            File.Move(backup + ".part", backup, overwrite: true);
            File.Move(staged, current, overwrite: true);
            return;
        }
        File.Move(current, backup, overwrite: true);
        try { File.Move(staged, current); }
        catch (Exception) when (!File.Exists(current))
        {
            File.Move(backup, current);
            throw;
        }
    }

    /// The launcher kept by the last update back in place (--rollback); false when none was kept
    public static bool Rollback(string current, Platform platform)
    {
        var backup = Backup(current);
        if (!File.Exists(backup)) return false;
        var aside = current + ".rolledback";
        if (platform == Platform.Linux)
        {
            File.Copy(current, aside, overwrite: true);
            File.Move(backup, current, overwrite: true);
            return true;
        }
        File.Move(current, aside, overwrite: true);
        try { File.Move(backup, current); }
        catch (Exception) when (!File.Exists(current))
        {
            File.Move(aside, current);
            throw;
        }
        return true;
    }
}
