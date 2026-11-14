namespace LongshotLauncher.Core;

/// Space on the disk: what a folder holds, what is free where a build goes, and what a build needs
public static class Disk
{
    /// What a build needs while it builds: the game folder and the build files (the 2.x Builders' "Needs 45 GB")
    public const long BuildBytes = 45L << 30;

    /// What a build makes in its build files folder (make_game.py --work) that Free up space lets go, as the 2.x Builder's
    /// Storage.Freeable: the compiled objects and their system headers' stamp, the translation, the unpacked exefs and the check's
    /// probe. Never the folder itself: the player may have chosen one that holds other things
    public static readonly IReadOnlyList<string> WorkParts = new[] { "objcache", "sa", "exefs", "probe", "system_headers.txt" };

    /// The bytes Free up space would let go in work
    public static long WorkBytes(string work) => WorkParts.Sum(p =>
    {
        var path = Path.Combine(work, p);
        var file = new FileInfo(path);
        return file.Exists ? (file.LinkTarget == null ? file.Length : 0) : FolderBytes(path);
    });

    /// WorkParts let go (a link among them is removed, never followed); the rest of work stays
    public static void FreeWork(string work)
    {
        foreach (var p in WorkParts)
        {
            var path = Path.Combine(work, p);
            if (Directory.Exists(path) || new DirectoryInfo(path).LinkTarget != null) Toolchains.DeleteTree(path);
            else if (File.Exists(path)) File.Delete(path);
        }
    }

    /// The bytes of the files under folder; links are counted as links, never followed; what cannot be read counts nothing
    public static long FolderBytes(string folder)
    {
        long sum = 0;
        var pending = new Stack<string>();
        pending.Push(folder);
        while (pending.Count > 0)
        {
            var dir = pending.Pop();
            try
            {
                foreach (var entry in new DirectoryInfo(dir).EnumerateFileSystemInfos())
                {
                    if (entry.LinkTarget != null) continue;
                    if (entry is DirectoryInfo d) pending.Push(d.FullName);
                    else if (entry is FileInfo f) sum += f.Length;
                }
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.Security.SecurityException) { }
        }
        return sum;
    }

    /// The free bytes on the drive that holds path (or would: the nearest folder above it that exists); null when unknown
    public static long? FreeBytes(string path)
    {
        try
        {
            var at = Existing(path);
            if (at == null) return null;
            // Unix asks the filesystem that holds the folder itself, so links and mounts are followed by the OS
            if (!OperatingSystem.IsWindows()) return new DriveInfo(at).AvailableFreeSpace;
            // (the mount that holds it: the longest drive root it starts with)
            var drive = DriveInfo.GetDrives()
                .Where(d => { try { return d.IsReady && Within(at, d.RootDirectory.FullName); } catch (IOException) { return false; } })
                .OrderByDescending(d => d.RootDirectory.FullName.Length).FirstOrDefault();
            return drive?.AvailableFreeSpace;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) { return null; }
    }

    /// The nearest folder at or above path that exists, as a full path; on Unix with its links followed, so it names the
    /// mount FreeBytes measures (on Bazzite /home is a link to /var/home); null when none does
    static string? Existing(string path)
    {
        var at = Path.GetFullPath(path);
        while (!Directory.Exists(at))
        {
            var up = Path.GetDirectoryName(at);
            if (up == null || up == at) return null;
            at = up;
        }
        return OperatingSystem.IsWindows() ? at : Real(at);
    }

    /// path with every link along it followed, as realpath does (a link's target may itself pass through links)
    static string Real(string path, int depth = 0)
    {
        if (depth > 40) return path;   // (a loop of links: give up and keep the path as it is)
        var at = "/";
        foreach (var part in path.Split('/', StringSplitOptions.RemoveEmptyEntries))
        {
            var next = Path.Combine(at, part);
            var target = new DirectoryInfo(next).LinkTarget == null ? null : new DirectoryInfo(next).ResolveLinkTarget(true);
            at = target == null ? next : Real(target.FullName, depth + 1);
        }
        return at;
    }

    static bool Within(string path, string root)
    {
        var c = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        // (every separator at the end off, the root's own too: "C:\" is "C:", "/" is "", which holds every path. Path's
        // TrimEndingDirectorySeparator keeps a root's, so on Windows no path was within "C:\" and the free space was unknown)
        var r = root.TrimEnd('/', Path.DirectorySeparatorChar);
        return r.Length == 0 || path.Equals(r, c) || path.StartsWith(r + Path.DirectorySeparatorChar, c);
    }

    /// The drive a path is on, as the window names it: "D:" on Windows, the mount point on Linux ("/" , "/home", "/mnt/games")
    public static string DriveName(string path)
    {
        try
        {
            var full = Path.GetFullPath(path);
            if (OperatingSystem.IsWindows()) return (Path.GetPathRoot(full) ?? full).TrimEnd('\\', '/');
            full = Existing(full) ?? full;   // (the folder FreeBytes measures, its links followed)
            var mount = DriveInfo.GetDrives()
                .Select(d => d.RootDirectory.FullName)
                .Where(r => Within(full, r))
                .OrderByDescending(r => r.Length).FirstOrDefault();
            return mount ?? "/";
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) { return path; }
    }
}
