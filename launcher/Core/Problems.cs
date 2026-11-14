using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace LongshotLauncher.Core;

/// What went wrong, in the words a player needs, and what they can do about it: from a build that stopped (make_game.py's last
/// message, ProblemViewModel) or a game that closed unexpectedly (its log, CrashCheck). Matched on the messages make_game.py and
/// the game write, so a new message shows as Unknown rather than as a wrong fix.
public enum ProblemKind
{
    Unknown,
    Antivirus,          // the antivirus removed the build tools' own compiler
    WrongGameVersion,   // the game files are another build than the supported one
    IncompleteDump,     // the dump has damaged files with nothing to put in their place
    DiskFull,           // no room left on the drive the build writes to
    BuildMemory,        // the PC ran out of memory while compiling
    NoMeshShaders,      // the game closed unexpectedly on a graphics card or driver with no mesh shaders
    GpuLost,            // the graphics driver stopped answering (device lost)
    GameCrashed,        // the game closed with a crash report in its log
}

/// What a fix button does (the screen decides how)
public enum FixKind { None, PickOtherFiles, ChooseOtherFolder, LowerBuildMemory, DriverPage, BuildAgain }

public sealed record Fix(FixKind Kind, string Label, string? Link = null);

/// A problem as the screens show it. Headline, Detail and each Fix's Label are the English, marked for the catalogs (Tr.N): a
/// screen shows them in the player's language (Tr.T). Signature: what identifies the same crash on another PC (the exception and
/// where it happened, never a path), for grouping reports; null for a build problem
public sealed record Problem(ProblemKind Kind, string Headline, string Detail, IReadOnlyList<Fix> Fixes, string? Signature = null);

public static partial class Problems
{
    static readonly Fix BuildAgain = new(FixKind.BuildAgain, Tr.N("Build again"));

    /// The driver download page for a maker (SystemInfo's names); null for another
    public static string? DriverPage(string? vendor) => vendor switch
    {
        SystemInfo.Nvidia => "https://www.nvidia.com/Download/index.aspx",
        SystemInfo.Amd => "https://www.amd.com/en/support/download/drivers.html",
        SystemInfo.Intel => "https://www.intel.com/content/www/us/en/download-center/home.html",
        _ => null,
    };

    static Fix DriverFix(string? vendor) =>
        DriverPage(vendor) is { } link ? new Fix(FixKind.DriverPage, Tr.N("Get the latest graphics driver"), link)
                                       : new Fix(FixKind.None, Tr.N("Update your graphics driver"));

    /// A build that stopped: why, make_game.py's last message (or the launcher's own). Only the messages that mean one thing
    /// are matched: make_game.py's "Could not clear ... wait for your antivirus to finish" (a folder in use), "came out cut short
    /// twice ... free space, and that no antivirus" and the reparse points' "not supported" (another output folder) name causes
    /// of their own, and show as make_game.py said them (Unknown)
    public static Problem FromBuild(string why)
    {
        var w = why ?? "";
        bool Has(string s) => w.Contains(s, StringComparison.OrdinalIgnoreCase);
        // (make_game.py check_cpu: the compiler's files are gone; check_mingw: the compiler is not there or can't build)
        if (Has("antivirus most likely removed") || Has("a folder your antivirus allows"))
            return new Problem(ProblemKind.Antivirus, Tr.N("Your antivirus removed some of Longshot's files"),
                Tr.N("This is a false alarm: Longshot's build tools aren't signed, so some antivirus programs flag them. Restore the " +
                "files from your antivirus's quarantine (Windows Security: Protection history) and allow Longshot's folder, then " +
                "build again."), [BuildAgain]);
        // (make_game.py check_supported_build and --check: "This is build 1a2b3c4d. Longshot supports build e0f3ccfa.")
        if (Has("Longshot supports build"))
            return new Problem(ProblemKind.WrongGameVersion, Tr.N("These game files are a different version"),
                Tr.N("Longshot needs Ocarina of Time with update 2.0.0 installed (program 0400486024DEC000, update v131072). Pick " +
                "the files of that version, or dump your game again with the update."), [new Fix(FixKind.PickOtherFiles, Tr.N("Pick other game files"))]);
        if (Has("dump is incomplete") || Has("still has") && Has("damaged file"))
            return new Problem(ProblemKind.IncompleteDump, Tr.N("Your game dump is incomplete"),
                Tr.N("Some of the game's files are damaged or missing (a complete dump is about 23.8 GB). Dump the game again and " +
                "build from the new dump."), [new Fix(FixKind.PickOtherFiles, Tr.N("Pick other game files"))]);
        // (the system's own words: Linux's ENOSPC, Windows' ERROR_DISK_FULL)
        if (Has("No space left") || Has("not enough space") || Has("disk full"))
            return new Problem(ProblemKind.DiskFull, Tr.N("The drive is full"),
                Tr.N("The build needs about 45 GB free while it runs. Free up space on that drive, or build to another drive."),
                [new Fix(FixKind.ChooseOtherFolder, Tr.N("Build to another folder")), BuildAgain]);
        if (Has("ran out of memory") || Has("MemoryError") || Has("out of memory"))
            return new Problem(ProblemKind.BuildMemory, Tr.N("Your PC ran out of memory while building"),
                Tr.N("Close other programs, or set Build memory lower in step 2's Advanced, then build again: what was built so far " +
                "is kept."), [new Fix(FixKind.LowerBuildMemory, Tr.N("Use less memory")), BuildAgain]);
        return new Problem(ProblemKind.Unknown, Tr.N("The build stopped"),
            Tr.N("Something went wrong that Longshot doesn't recognise yet."), [BuildAgain]);
    }

    [GeneratedRegex(@"CRASH: exception (0x[0-9a-fA-F]+) \((read|write)[^)]*\) at (\S+)")]
    private static partial Regex CrashLine();

    /// The GPU the game ran on (gpu/vk/vk_main.cpp, after the device is made): "vk: NVIDIA GeForce RTX 4070 Ti, Vulkan 1.4, driver
    /// 0x..; mesh shaders yes, ...". Not the list of every device before it ("vk: device 0: <name>, Vulkan 1.3, driver 0x.., type 2")
    [GeneratedRegex(@"vk: (?!device \d+: )(.+?), Vulkan \d+\.\d+, driver ")]
    private static partial Regex GpuLine();

    /// A run that closed unexpectedly, from its log's lines (oldest first); null when the log shows no crash. vendor: the
    /// graphics card's maker when the log doesn't name the GPU the game ran on, for the driver link
    public static Problem? FromLog(IEnumerable<string> lines, string? vendor = null)
    {
        string? crash = null, module = null, gpu = null;
        bool lost = false, noMesh = false;
        foreach (var line in lines)
        {
            if (crash == null && CrashLine().Match(line) is { Success: true } m)
            {
                crash = m.Groups[1].Value.ToLowerInvariant();
                module = m.Groups[3].Value;
            }
            if (GpuLine().Match(line) is { Success: true } g) gpu = g.Groups[1].Value;
            if (line.Contains("device lost", StringComparison.OrdinalIgnoreCase) ||
                line.Contains("VK_ERROR_DEVICE_LOST", StringComparison.Ordinal)) lost = true;
            if (line.Contains("this GPU has no mesh shaders", StringComparison.Ordinal)) noMesh = true;
        }
        // (the GPU that ran, not the first card Linux lists: a laptop's iGPU, or nothing on Windows)
        if (gpu != null) vendor = SystemInfo.VendorOfName(gpu);
        // (no mesh shaders alone is a warning: the game logs it at every start and goes on, vk_main.cpp. It is the likely cause
        // only of a run that then crashed or lost the device)
        if (!lost && crash == null) return null;
        if (noMesh)
            return new Problem(ProblemKind.NoMeshShaders, Tr.N("Your graphics card can't draw this game"),
                Tr.N("It, or its driver, has no mesh shaders, which the game needs. An NVIDIA RTX 20 series or newer, an AMD Radeon " +
                "RX 6000 or newer, or an Intel Arc card can. If your card is one of those, update its driver."), [DriverFix(vendor)],
                Signature(crash, module, lost ? "device lost" : null));
        if (lost)
            return new Problem(ProblemKind.GpuLost, Tr.N("The graphics driver stopped responding"),
                Tr.N("This is often fixed by the latest graphics driver."), [DriverFix(vendor)], Signature(crash, module, "device lost"));
        return new Problem(ProblemKind.GameCrashed, Tr.N("The game closed unexpectedly"),
            Tr.N("If it happens again at the same place, the latest graphics driver is worth a try."), [DriverFix(vendor)],
            Signature(crash, module, null));
    }

    /// The same crash on any PC: the exception code and the module and offset it happened at (the module's name only: no
    /// folder), or what was lost
    static string Signature(string? code, string? module, string? what)
    {
        var where = module == null ? "" : Path.GetFileName(module.Replace('\\', '/'));
        var parts = new[] { code, where.Length > 0 ? where : null, what }.Where(p => !string.IsNullOrEmpty(p));
        return string.Join(" ", parts).Trim().ToLower(CultureInfo.InvariantCulture);
    }
}

/// Whether the last run of a build closed unexpectedly: its newest log (logs/longshot_log.txt, or longshot_log.txt beside the
/// game from a build before Longshot's game folder layout) shows a crash the launcher has not shown yet. Only the newest: a run since then went well (the player has played since), and a log the game rotated is not
/// offered. The caller leaves it out while a game runs (that log is the live run's)
public static class CrashCheck
{
    public sealed record Found(Problem Problem, string Log, long WriteTicks);

    /// The game's log, in its build's folder
    public const string LogName = "longshot_log.txt";

    /// Where the game's logs are: logs/ in its build's folder (Longshot's host/game_layout.c, from nightly-127 on)
    public const string LogsFolder = "logs";

    /// The game's log of its last run: logs/longshot_log.txt, or longshot_log.txt beside the game where a build from before
    /// the logs/ folder wrote it (the newer of the two, should both be there: the game moves the loose one into logs/ at
    /// its first start, and keeps it where it is when one of that name is there already); null when there is none
    public static string? LogPath(string buildFolder)
    {
        string? newest = null;
        var newestTicks = long.MinValue;
        foreach (var path in new[] { Path.Combine(buildFolder, LogsFolder, LogName), Path.Combine(buildFolder, LogName) })
        {
            if (!File.Exists(path)) continue;
            var ticks = File.GetLastWriteTimeUtc(path).Ticks;
            if (ticks > newestTicks) (newest, newestTicks) = (path, ticks);
        }
        return newest;
    }

    /// The most of one log read (and a report carries): its end, where the problem is
    public const int LogTailBytes = 192 * 1024;

    /// The end of a file, at most max bytes, from the start of a line
    public static string Tail(string path, int max = LogTailBytes)
    {
        using var f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        var start = Math.Max(0, f.Length - max);
        f.Seek(start, SeekOrigin.Begin);
        var text = new StreamReader(f, Encoding.UTF8).ReadToEnd();
        if (start > 0 && text.IndexOf('\n') is var nl and >= 0) text = "[the log's start left out]\n" + text[(nl + 1)..];
        return text;
    }

    /// seenTicks: the log's write time (UTC ticks) already handled (settings); notBeforeTicks: a log written before then is not
    /// offered (before the launcher first looked, or too long ago to be news)
    public static Found? Find(string buildFolder, long seenTicks, long notBeforeTicks = 0, string? vendor = null)
    {
        try
        {
            if (LogPath(buildFolder) is not { } path) return null;
            var ticks = File.GetLastWriteTimeUtc(path).Ticks;
            if (ticks <= seenTicks || ticks < notBeforeTicks) return null;
            return Problems.FromLog(Tail(path).Split('\n'), vendor) is { } p ? new Found(p, path, ticks) : null;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { return null; }
    }
}
