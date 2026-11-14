using System.Diagnostics;
using System.Text;
using System.Text.RegularExpressions;

namespace LongshotLauncher.Core;

/// A program that runs the game and keeps its saves (scripts/oot_saves.py Program): where it keeps its data on each platform,
/// in the order tried ({data}, {home}, {appdata}, {localappdata}), its process names (lower case, no .exe) and other names
public sealed record SaveProgram(string Name, string Display, IReadOnlyDictionary<Platform, string[]> Folders, string[] Processes, string[] Aliases);

/// One profile's save folder (account.sav, option.sav, slot_NN/): its id (the folder above it that names the profile)
public sealed record SaveProfile(string Id, string Path);

/// A slot and when its progress.sav was last written (null: no progress.sav in it)
public sealed record SaveSlot(string Name, DateTime? Saved);

/// Where one program's (or one build's) saves were found: the data folder searched and its profiles; Problem: why none
public sealed record SaveSet(string Owner, string Display, string? Folder, IReadOnlyList<SaveProfile> Profiles, string? Problem)
{
    public bool Found => Profiles.Count > 0;
}

/// What a copy did (or, dry, would do): Backup is the copy of the target taken first (null: the target had nothing yet)
public sealed record SaveCopy(string Source, string Target, string? Backup, IReadOnlyList<string> Slots, IReadOnlyList<string> Files, bool KeptSettings, bool Dry);

/// What Saves.Gather did: the save every build uses now (From: the user folder it came from; WasShared: it was the shared one
/// already), the old user folders whose save was moved aside, and the backup of every one of them, the shared one's too
public sealed record SaveGathered(string From, bool WasShared, IReadOnlyList<string> Moved, string Backup);

/// A copy refused, and why (oot_saves.Fail)
public sealed class SaveFailure(string message, SaveRefusal reason = SaveRefusal.Other, IReadOnlyList<string>? who = null, string? backup = null)
    : Exception(message)
{
    /// The backup a failed copy made before it stopped (the target is as it was; this is a second copy of it), for the window to
    /// show; null when there was none
    public string? Backup { get; } = backup;

    /// Why the copy was refused, for the window to say it its own way (the message says it the script's way)
    public SaveRefusal Reason { get; } = reason;
    /// Running: what runs; Waiting: the program whose save waits
    public IReadOnlyList<string> Who { get; } = who ?? Array.Empty<string>();
}

/// Running: a game or an emulator runs; Waiting: NX2navi has a commit or menu import waiting; Exists: the copy would replace a
/// save the player has not agreed to replace (HookshotSaves.Import); Other: anything else
public enum SaveRefusal { Other, Running, Waiting, Exists }

/// The environment the save folders are worked out from: the platform and its variables (HOME, XDG_DATA_HOME, APPDATA,
/// LOCALAPPDATA), so the tests point them all into one temporary folder as tests/test_oot_saves.py does
public sealed record SaveEnvironment(Platform Platform, Func<string, string?> Getenv)
{
    public static SaveEnvironment Current() => new(Platforms.Current, Environment.GetEnvironmentVariable);

    string Home => Getenv("HOME") is { Length: > 0 } h ? h : Getenv("USERPROFILE") is { Length: > 0 } u ? u
                   : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

    /// oot_saves.data_home
    public string Data => Getenv("XDG_DATA_HOME") is { Length: > 0 } x ? x : Path.Combine(Home, ".local", "share");

    string AppData => Getenv("APPDATA") is { Length: > 0 } a ? a : Path.Combine(Home, "AppData", "Roaming");
    string LocalAppData => Getenv("LOCALAPPDATA") is { Length: > 0 } a ? a : Path.Combine(Home, "AppData", "Local");

    /// Where the backups go instead of BackupRoot's default (a portable launcher's own folder); null: the default
    public string? BackupFolder { get; init; }

    /// (Windows) Longshot's user folder instead of LongshotUser's default (a portable launcher's own folder); null: the default
    public string? UserFolder { get; init; }

    /// Longshot's user folder, the same for every build (the game's --user: save\&lt;user id&gt;\, its cache and its temp). On
    /// Windows %APPDATA%\Longshot, which the launcher starts every build with; on Linux $XDG_DATA_HOME/longshot, where the game
    /// keeps it by itself
    public string LongshotUser => Path.GetFullPath(Platform == Platform.Windows
        ? UserFolder ?? Path.Combine(AppData, "Longshot")
        : Path.Combine(Data, "longshot"));

    /// oot_saves.default_backup_dir: the script's and the launcher's backups in one place
    public string BackupRoot => BackupFolder ?? (Platform == Platform.Windows
        ? Path.Combine(LocalAppData, "Longshot", "oot-save-backups")
        : Path.Combine(Data, "oot-save-backups"));

    /// oot_saves.folders: a program's data folders on this platform, in the order they are tried
    public IReadOnlyList<string> FoldersOf(SaveProgram program) =>
        program.Folders.TryGetValue(Platform, out var list)
            ? list.Select(t => Path.GetFullPath(t.Replace("{data}", Data).Replace("{home}", Home).Replace("{appdata}", AppData)
                                                 .Replace("{localappdata}", LocalAppData).Replace('/', Path.DirectorySeparatorChar))).ToList()
            : Array.Empty<string>();
}

/// The game's saves, the same files in Longshot and in the emulators and ports that run it (Longshot's docs/saves.md): found, summed up and
/// copied one way after a backup. A port of scripts/oot_saves.py, rule for rule (each piece names the function it mirrors), so
/// that the launcher needs no Python and no installed tools for it. Every build shares one save folder
/// (SaveEnvironment.LongshotUser: save\&lt;user id&gt;\ in %APPDATA%\Longshot on Windows, $XDG_DATA_HOME/longshot on Linux). Windows
/// builds kept their own in their game folder (&lt;folder&gt;\user) before: Gather brings those into the shared one.
public static class Saves
{
    public const string Title = "0400486024DEC000";
    public const string NoAccount = "0000000000000000";
    // Longshot's host/nn_applet.c returns this one user; an emulator's profile id is not read by the game.
    public const string UserId = "5a3c9e1f0b7d24680000000000000001";

    static Dictionary<Platform, string[]> On(string[] linux, string[] windows) => new() { [Platform.Linux] = linux, [Platform.Windows] = windows };

    // (oot_saves.EDEN, LICHII, EMULATORS, LONGSHOT, FOLDER; their sources are in Longshot's docs/saves.md)
    static readonly string[] EdenLinux = { "{data}/eden" }, EdenWindows = { "{appdata}/eden" };
    public static readonly IReadOnlyList<SaveProgram> Emulators = new[]
    {
        // (Lichii has a data folder of its own since its build 150, 2026-11-10; a build from before keeps its saves in Eden's)
        new SaveProgram("lichii", "Lichii", On(new[] { "{data}/lichii" }.Concat(EdenLinux).ToArray(), new[] { "{appdata}/lichii" }.Concat(EdenWindows).ToArray()),
                        new[] { "lichii" }, Array.Empty<string>()),
        new SaveProgram("frizti", "Frizti (Fritchii)", On(EdenLinux, EdenWindows), new[] { "lichii", "fritchii" }, new[] { "fritchii" }),
        new SaveProgram("orchid", "Orchid", On(EdenLinux, EdenWindows), new[] { "orchid" }, Array.Empty<string>()),
        new SaveProgram("pokedinner", "PokeDinner", On(EdenLinux, EdenWindows), new[] { "eglantine" }, Array.Empty<string>()),
        new SaveProgram("eden", "Eden", On(EdenLinux, EdenWindows), new[] { "eden" }, Array.Empty<string>()),
        new SaveProgram("eglantine", "Eglantine", On(new[] { "{data}/eglantine" }, new[] { "{appdata}/eglantine" }), new[] { "eglantine" }, Array.Empty<string>()),
        new SaveProgram("nx2navi", "NX2navi", On(new[] { "{home}/Games/Ocarina" }, new[] { "{localappdata}/Programs/NX2navi/game", "C:/Games/Ocarina" }),
                        new[] { "nx2navi", "ocarina" }, Array.Empty<string>()),
    };
    public static readonly SaveProgram Longshot = new("longshot", "Longshot", On(new[] { "{data}/longshot" }, new[] { "{appdata}/Longshot" }), new[] { "longshot" }, Array.Empty<string>());
    public static readonly SaveProgram Folder = new("folder", "the folder", On(Array.Empty<string>(), Array.Empty<string>()), Array.Empty<string>(), Array.Empty<string>());

    // (oot_saves.LAYOUTS: where the save folders sit under a data folder; "<id>" is one folder per profile. A folder deeper down
    // the same path is accepted too; the first layout that finds a profile wins)
    static readonly string[][] Layouts =
    {
        new[] { "nand", "user", "save", "account", "<id>", Title, "0" },   // (Eden's newer layout: used first when it exists)
        new[] { "nand", "user", "save", NoAccount, "<id>", Title },        // (Eden and its forks: Lichii, Eglantine, ...)
        new[] { "profile", "save", "<id>" },                                // (NX2navi's game folder)
        new[] { "user", "save", "<id>" },                                   // (a Windows Longshot game folder of before, Hookshot's)
        new[] { "save", "<id>" },                                           // (Longshot's data folder)
    };

    // ---- finding them ----

    /// oot_saves.subdirs: the folders in path, sorted; none when it cannot be read
    static List<string> Subdirs(string path)
    {
        try { return Directory.EnumerateDirectories(path).Select(System.IO.Path.GetFileName).OfType<string>().OrderBy(n => n, StringComparer.Ordinal).ToList(); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException) { return new List<string>(); }
    }

    /// oot_saves.slots
    public static IReadOnlyList<string> SlotNames(string path) => Subdirs(path).Where(n => n.StartsWith("slot_", StringComparison.Ordinal)).ToList();

    /// oot_saves.is_save_folder
    public static bool IsSaveFolder(string path) => File.Exists(System.IO.Path.Combine(path, "account.sav")) || SlotNames(path).Count > 0;

    static string Base(string path) => System.IO.Path.GetFileName(System.IO.Path.TrimEndingDirectorySeparator(path));

    static string Up(string path) => System.IO.Path.GetDirectoryName(System.IO.Path.TrimEndingDirectorySeparator(path)) ?? path;

    /// oot_saves.walk
    static IEnumerable<(string? Key, string Path)> Walk(string root, ArraySegment<string> parts, string? key)
    {
        if (parts.Count == 0)
        {
            yield return (key, root);
            yield break;
        }
        foreach (var n in Subdirs(root))
        {
            if (parts[0] == "<id>")
                foreach (var x in Walk(System.IO.Path.Combine(root, n), parts[1..], n)) yield return x;
            else if (string.Equals(n, parts[0], StringComparison.OrdinalIgnoreCase))
                foreach (var x in Walk(System.IO.Path.Combine(root, n), parts[1..], key)) yield return x;
        }
    }

    /// oot_saves.find_saves: the game's save folders under root, one per profile id, in the order found; root may be the save
    /// folder itself
    public static IReadOnlyList<SaveProfile> Find(string root)
    {
        var norm = System.IO.Path.TrimEndingDirectorySeparator(System.IO.Path.GetFullPath(root));
        var titleFolder = Base(norm).ToUpperInvariant() == Title;
        if (IsSaveFolder(norm) || (titleFolder && !Subdirs(norm).Contains("0")))
        {
            var key = norm;
            while (Base(key).ToUpperInvariant() is Title or "0" && Up(key) != key) key = Up(key);
            return new[] { new SaveProfile(Base(key) is { Length: > 0 } b ? b : norm, norm) };
        }
        var found = new List<SaveProfile>();
        foreach (var layout in Layouts)
        {
            var idpos = Array.IndexOf(layout, "<id>");
            for (var start = 0; start < layout.Length; start++)
            {
                // (below the title id folder, only the title id folder itself is a place to start)
                if (layout.Contains(Title) && !layout[start..].Contains(Title) && !titleFolder) continue;
                string? key = null;
                if (start > idpos)   // (root is at or below the <id> folder: the id is a folder above it)
                {
                    var up = norm;
                    for (var i = 0; i < start - idpos - 1; i++) up = Up(up);
                    key = Base(up);
                }
                foreach (var (k, path) in Walk(norm, new ArraySegment<string>(layout, start, layout.Length - start), key))
                {
                    // (a folder the layout names, the title id folder, counts as soon as it is there: the game may not have saved yet.
                    // A profile folder counts only when it holds a save: Eden's profile folders do not)
                    if ((layout[^1] != "<id>" || IsSaveFolder(path)) && k != null && found.All(f => f.Id != k && f.Path != path))
                        found.Add(new SaveProfile(k, path));
                }
            }
        }
        return found;
    }

    /// oot_saves.locate: (folder, profiles) for program: the override when given, else the first of its folders with saves
    public static (string Folder, IReadOnlyList<SaveProfile> Profiles) Locate(SaveProgram program, string? folder, SaveEnvironment env)
    {
        if (folder != null)
        {
            if (!Directory.Exists(folder)) throw new SaveFailure($"No folder at {folder}.");
            var found = Find(folder);
            if (found.Count == 0)
                throw new SaveFailure($"No Ocarina of Time save under {folder} (a folder with account.sav and slot_*, or {Title} under an " +
                                      "emulator's nand/user/save): start the game there once and save.");
            return (folder, found);
        }
        var tried = env.FoldersOf(program);
        foreach (var d in tried)
            if (Directory.Exists(d) && Find(d) is { Count: > 0 } found) return (d, found);
        throw new SaveFailure($"No {program.Display} save found (looked in {(tried.Count > 0 ? string.Join(", ", tried) : "no default folder")}): " +
                              $"start the game in {program.Display} once and save, or choose its folder.");
    }

    /// oot_saves.pick: the one profile, or the one asked for; several and none asked for is an error that lists them
    public static SaveProfile Pick(IReadOnlyList<SaveProfile> found, string name, string? wanted = null)
    {
        if (wanted != null)
            return found.FirstOrDefault(p => string.Equals(p.Id, wanted, StringComparison.OrdinalIgnoreCase))
                   ?? throw new SaveFailure($"{name} has no profile {wanted}; it has: {string.Join(", ", found.Select(p => p.Id).Order(StringComparer.Ordinal))}");
        if (found.Count > 1)
            throw new SaveFailure($"{name} has Ocarina of Time saves in {found.Count} profiles, so pick one:" +
                                  string.Concat(found.OrderBy(p => p.Id, StringComparer.Ordinal).Select(p => $"\n  {p.Id}  {p.Path}")));
        return found.Count == 1 ? found[0] : throw new SaveFailure($"{name} has no save.");
    }

    /// oot_saves.program_named: an emulator by its name or another name
    public static SaveProgram Named(string name) =>
        Emulators.FirstOrDefault(p => p.Name == name.ToLowerInvariant() || p.Aliases.Contains(name.ToLowerInvariant()))
        ?? throw new SaveFailure($"Unknown emulator {name}: use one of {string.Join(", ", Emulators.Select(p => p.Name))}, or choose a folder.");

    /// oot_saves.pending_commit: NX2navi writes a save to profile/save-tx first and moves it into profile/save/&lt;account&gt; after;
    /// while a finished commit waits there (save-tx/ready-&lt;n&gt;, n from 1), that is the save the game loads next. The rest of
    /// save-tx is not a save in waiting (NX2navi's runtime/fs_host.c, "save transactions"): work/ is the working copy, which a
    /// quit leaves behind (the exit waits for a commit but does not unmount the save) and the next start deletes; new/ is an unfinished
    /// commit, rolled back; old/ is the save a commit replaced, on its way to save-backup. The menu's completed import in
    /// profile/save-import also replaces the current save at the next start (fs_host.c import_pending); save-import.part does not
    public static string? PendingCommit(string save)
    {
        var parent = Up(System.IO.Path.TrimEndingDirectorySeparator(System.IO.Path.GetFullPath(save)));
        if (Base(parent).ToLowerInvariant() != "save") return null;
        var import = System.IO.Path.Combine(Up(parent), "save-import");
        if (Directory.Exists(import)) return import;
        var tx = System.IO.Path.Combine(Up(parent), "save-tx");
        return Subdirs(tx).Any(IsFinishedCommit) ? tx : null;
    }

    /// fs_host.c ready_number: "ready-" and a number above 0, nothing else
    static bool IsFinishedCommit(string name) =>
        name.StartsWith("ready-", StringComparison.Ordinal) && name.Length > 6 && name[6..].All(char.IsAsciiDigit)
        && ulong.TryParse(name[6..], System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out var n)
        && n is > 0 and <= uint.MaxValue;

    /// oot_saves.describe: each slot and when its progress.sav was written (local time)
    public static IReadOnlyList<SaveSlot> Describe(string path) =>
        SlotNames(path).Select(s =>
        {
            var p = System.IO.Path.Combine(path, s, "progress.sav");
            return new SaveSlot(s, File.Exists(p) ? File.GetLastWriteTime(p) : null);
        }).ToList();

    // ---- by build, and everything at once (oot_saves.list_all) ----

    /// Longshot's saves, the same for every build: in SaveEnvironment.LongshotUser (save\&lt;user id&gt;)
    public static SaveSet Shared(SaveEnvironment env)
    {
        var user = env.LongshotUser;
        var found = Directory.Exists(user) ? Find(user) : Array.Empty<SaveProfile>();
        return new SaveSet("longshot", "Longshot", user, found, found.Count == 0 ? $"No Longshot save in {user} yet." : null);
    }

    /// Where Longshot's save of a profile goes when there is none yet: &lt;LongshotUser&gt;\save\&lt;id&gt;
    public static string SharedSavePath(SaveEnvironment env, string profile) => System.IO.Path.Combine(env.LongshotUser, "save", profile);

    /// Where an import goes: the save of the one user the game opens (UserId: host/nn_applet.c's user_uid, which host/nn_fs.c
    /// names save\&lt;high word&gt;&lt;low word&gt;), whether it is there yet or not. Another profile folder in save\ (a stray one, a copy
    /// made by hand) is never read by the game, so an import never goes there and never has to choose between them
    public static string ImportTarget(SaveEnvironment env) => SharedSavePath(env, UserId);

    /// Every emulator's saves, grouped by the folder they come from (the emulators that share Eden's folder in one group), as
    /// list_all shows them: a group with nothing names the folders it looked in
    public static IReadOnlyList<SaveSet> Emulator(SaveEnvironment env)
    {
        var groups = new List<(string Key, string? Folder, List<SaveProgram> Programs, IReadOnlyList<string> Tried)>();
        foreach (var program in Emulators)
        {
            var tried = env.FoldersOf(program);
            var used = tried.FirstOrDefault(d => Directory.Exists(d) && Find(d).Count > 0);
            var key = used ?? "\0" + string.Join("\0", tried);
            var at = groups.FindIndex(g => g.Key == key);
            if (at < 0) groups.Add((key, used, new List<SaveProgram> { program }, tried));
            else groups[at].Programs.Add(program);
        }
        return groups.Select(g =>
        {
            var display = string.Join(" / ", g.Programs.Select(p => p.Display));
            return g.Folder != null
                ? new SaveSet(g.Programs[0].Name, display, g.Folder, Find(g.Folder), null)
                : new SaveSet(g.Programs[0].Name, display, null, Array.Empty<SaveProfile>(),
                              "Nothing in " + (g.Tried.Count > 0 ? string.Join(", ", g.Tried) : "(no default folder)"));
        }).ToList();
    }

    // ---- is a game running (oot_saves.process_names, running_games) ----

    /// {process name: what it belongs to}
    public static IReadOnlyDictionary<string, string> ProcessNames()
    {
        var names = new Dictionary<string, string>(StringComparer.Ordinal);
        var order = new List<string>();
        foreach (var program in Emulators.Prepend(Longshot).Append(HookshotSaves.Program))
            foreach (var p in program.Processes)
                if (names.TryGetValue(p, out var was)) names[p] = was + " or " + program.Display;
                else
                {
                    names[p] = program.Display;
                    order.Add(p);
                }
        return names;
    }

    /// What is running, from the processes' names: on Windows the image names (with or without .exe), on Linux each process's
    /// comm and the file name of its argv[0] (an AppImage named after the program counts)
    public static IReadOnlyList<string> RunningFrom(Platform platform, IEnumerable<string> candidates)
    {
        var known = ProcessNames();
        var names = new SortedSet<string>(StringComparer.Ordinal);
        var appImage = new Regex("^(" + string.Join("|", known.Keys.Select(Regex.Escape)) + @")[-_.].*\.appimage$", RegexOptions.CultureInvariant);
        foreach (var candidate in candidates)
        {
            var low = candidate.ToLowerInvariant();
            if (platform == Platform.Windows)
            {
                var image = low.EndsWith(".exe", StringComparison.Ordinal) ? low[..^4] : low;
                if (known.TryGetValue(image, out var w)) names.Add(w);
                continue;
            }
            if (known.TryGetValue(low, out var name)) names.Add(name);
            else if (appImage.Match(low) is { Success: true } m) names.Add(known[m.Groups[1].Value]);
        }
        return names.ToList();
    }

    /// The games running on this PC now, this launcher left out (its AppImage may be named Longshot-...AppImage)
    public static IReadOnlyList<string> Running(Platform platform)
    {
        var own = Environment.ProcessId;
        var candidates = new List<string>();
        if (platform == Platform.Windows)
        {
            foreach (var p in Process.GetProcesses())
                using (p)
                    if (p.Id != own) candidates.Add(p.ProcessName);
        }
        else
        {
            IEnumerable<string> pids;
            try { pids = Directory.EnumerateDirectories("/proc").Select(System.IO.Path.GetFileName).OfType<string>().Where(n => n.All(char.IsAsciiDigit)).ToList(); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { pids = Array.Empty<string>(); }
            foreach (var pid in pids)
            {
                if (pid == own.ToString(System.Globalization.CultureInfo.InvariantCulture)) continue;
                try
                {
                    var argv0 = File.ReadAllText($"/proc/{pid}/cmdline", Encoding.UTF8).Split('\0')[0];
                    candidates.Add(File.ReadAllText($"/proc/{pid}/comm", Encoding.UTF8).Trim());
                    candidates.Add(System.IO.Path.GetFileName(argv0));
                }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            }
        }
        return RunningFrom(platform, candidates);
    }

    // ---- the copy (oot_saves.run, copy_saves, refuse_links) ----

    static bool IsLink(FileSystemInfo info) => info.LinkTarget != null || info.Attributes.HasFlag(FileAttributes.ReparsePoint);

    /// oot_saves.refuse_links: a save from someone else is only files and folders: a link in it would copy what it points to
    static void RefuseLinks(string path)
    {
        FileSystemInfo root = Directory.Exists(path) ? new DirectoryInfo(path) : new FileInfo(path);
        if (!root.Exists && root.LinkTarget == null) return;
        if (IsLink(root)) throw new SaveFailure($"{path} is a link: a save holds only files and folders, so nothing was copied.");
        if (root is not DirectoryInfo dir) return;
        foreach (var child in dir.EnumerateFileSystemInfos())
        {
            if (IsLink(child)) throw new SaveFailure($"{child.FullName} is a link: a save holds only files and folders, so nothing was copied.");
            if (child is DirectoryInfo) RefuseLinks(child.FullName);
        }
    }

    /// The tests' way to make a copy fail where a full disk or a locked file would: called with "file" before each file is copied
    /// and "swap" between the two renames that put the copy in place; whatever it throws is what the copy meets
    internal static Action<string>? Fault { get; set; }

    static void CopyTree(string from, string to, Func<string, bool>? skip = null, bool faults = true)
    {
        Directory.CreateDirectory(to);
        foreach (var f in Directory.EnumerateFiles(from))
        {
            if (skip?.Invoke(System.IO.Path.GetFileName(f)) == true) continue;
            if (faults) Fault?.Invoke("file");
            File.Copy(f, System.IO.Path.Combine(to, System.IO.Path.GetFileName(f)));
        }
        foreach (var d in Directory.EnumerateDirectories(from))
            if (skip?.Invoke(System.IO.Path.GetFileName(d)) != true) CopyTree(d, System.IO.Path.Combine(to, System.IO.Path.GetFileName(d)), null, faults);
    }

    static void DeleteTree(string path)
    {
        try { if (Directory.Exists(path)) Directory.Delete(path, recursive: true); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
    }

    /// Where a copy into target is made before it takes target's place, and where target waits during the swap: beside it (one
    /// disk, so each move is a rename), hidden, one name per target, so that what a copy cut short left is found by the next one
    static (string Staging, string Aside) Beside(string target)
    {
        var parent = System.IO.Path.GetDirectoryName(target)!;
        var name = Base(target);
        return (System.IO.Path.Combine(parent, $".{name}.longshot-staging"), System.IO.Path.Combine(parent, $".{name}.longshot-old"));
    }

    /// path with every link on the way resolved (a symlinked ~/Games, a junction, the folder itself), the parts not there yet
    /// kept as they are: two paths to one folder compare equal, whichever links they pass through
    internal static string Real(string path) => Real(path, 0);

    static string Real(string path, int depth)
    {
        var full = System.IO.Path.TrimEndingDirectorySeparator(System.IO.Path.GetFullPath(path));
        var root = System.IO.Path.GetPathRoot(full) ?? "";
        var real = root;
        foreach (var part in full[root.Length..].Split(System.IO.Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries))
        {
            real = System.IO.Path.Combine(real, part);
            if (depth >= 40) continue;   // (a loop of links: left as it is from there)
            try { if (new DirectoryInfo(real).ResolveLinkTarget(true) is { } t) real = Real(t.FullName, depth + 1); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        }
        return real.Length == 0 ? full : System.IO.Path.TrimEndingDirectorySeparator(real);
    }

    internal static bool Inside(string root, string path)
    {
        var c = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
        return path.Equals(root, c) || path.StartsWith(root + System.IO.Path.DirectorySeparatorChar, c);
    }

    /// oot_saves.run (after the two sides are picked) and copy_saves: src's slots, account.sav and option.sav (not with
    /// keepSettings) into dst, which loses its own slots; dst is copied whole to &lt;backupRoot&gt;/&lt;command&gt;-&lt;name&gt;-&lt;yyyyMMdd-HHmmss&gt;
    /// first. Refused (SaveFailure) when the two are one folder, NX2navi still has a save waiting on either side, a game runs
    /// (running: the names; not asked on a dry run), the backup would go inside dst, src has no slot, or src holds a link.
    /// force skips the waiting save and the running game. dst is made when it is not there yet (a build that has no save).
    public static SaveCopy Copy(string src, string dst, string backupRoot, string command, string name, bool keepSettings = false,
                                bool dryRun = false, bool force = false, Func<IReadOnlyList<string>>? running = null, Func<DateTime>? now = null)
    {
        if (Real(src) == Real(dst)) throw new SaveFailure($"{src} is both the source and the target.");
        // (a copy cut short between its two renames, the PC off: dst waits beside itself, and goes back first)
        if (!dryRun && !Directory.Exists(dst) && Beside(System.IO.Path.GetFullPath(dst)).Aside is var left && Directory.Exists(left))
            Directory.Move(left, System.IO.Path.GetFullPath(dst));
        if (!force)
            foreach (var side in new[] { src, dst })
                if (PendingCommit(side) is { } tx)
                    throw new SaveFailure($"NX2navi still has a save waiting in {tx}, which it loads instead of {side}: start NX2navi and quit it from " +
                                          "the game, then copy.", SaveRefusal.Waiting, new[] { "NX2navi" });
        if (!dryRun && !force && (running ?? (() => Running(Platforms.Current)))() is { Count: > 0 } busy)
            throw new SaveFailure($"Close {string.Join(" and ", busy)} first: a running game can write its save again and undo the copy.",
                                  SaveRefusal.Running, busy);
        var stamp = (now ?? (() => DateTime.Now))().ToString("yyyyMMdd-HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        var backup = System.IO.Path.Combine(backupRoot, $"{command}-{name}-{stamp}");
        var at = backup;
        for (var n = 2; Directory.Exists(at) || File.Exists(at); n++) at = $"{backup}-{n}";   // (two copies in the same second)
        backup = at;

        if (Inside(Real(dst), Real(backup))) throw new SaveFailure($"Choose a backup folder outside the target save folder ({dst}).");
        var names = SlotNames(src);
        if (names.Count == 0) throw new SaveFailure($"{src} has no slot_* folders: nothing to copy.");
        foreach (var s in names) RefuseLinks(System.IO.Path.Combine(src, s));
        foreach (var f in new[] { "account.sav", "option.sav" }) RefuseLinks(System.IO.Path.Combine(src, f));
        var files = new[] { "account.sav", "option.sav" }.Where(f => File.Exists(System.IO.Path.Combine(src, f))).ToList();
        if (keepSettings) files.Remove("option.sav");
        var had = Directory.Exists(dst);
        var result = new SaveCopy(src, dst, had ? backup : null, names, files, keepSettings, dryRun);
        if (dryRun) return result;

        // (never less than before: dst is backed up, the new save is made whole in a folder beside it, and only then does it take
        // dst's place, by two renames. Any failure on the way leaves dst as it was, and says where the backup is)
        var target = had ? Real(dst) : System.IO.Path.GetFullPath(dst);
        var (staging, aside) = Beside(target);
        DeleteTree(staging);
        DeleteTree(aside);
        if (had)
        {
            try
            {
                Directory.CreateDirectory(System.IO.Path.GetDirectoryName(backup)!);
                CopyTree(target, backup);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                DeleteTree(backup);
                throw new SaveFailure($"{dst} could not be backed up ({e.Message}), so nothing was copied: it is as it was.");
            }
        }
        var slotsAndFiles = new HashSet<string>(files, StringComparer.Ordinal);
        try
        {
            if (had) CopyTree(target, staging, n => n.StartsWith("slot_", StringComparison.Ordinal) || slotsAndFiles.Contains(n));
            else Directory.CreateDirectory(System.IO.Path.GetDirectoryName(target)!);
            Directory.CreateDirectory(staging);
            foreach (var s in names) CopyTree(System.IO.Path.Combine(src, s), System.IO.Path.Combine(staging, s));
            foreach (var f in files)
            {
                Fault?.Invoke("file");
                File.Copy(System.IO.Path.Combine(src, f), System.IO.Path.Combine(staging, f), overwrite: true);
            }
            if (had)
            {
                Directory.Move(target, aside);
                try
                {
                    Fault?.Invoke("swap");
                    Directory.Move(staging, target);
                }
                catch (Exception) when (!Directory.Exists(target))
                {
                    Directory.Move(aside, target);
                    throw;
                }
                DeleteTree(aside);
            }
            else Directory.Move(staging, target);
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            DeleteTree(staging);
            var kept = !had || Directory.Exists(target) || Restore(backup, target);
            var where = had ? $" A backup of it is in {backup}." : "";
            throw new SaveFailure(kept
                ? $"The copy failed ({e.Message}). Nothing was changed: {dst} is as it was.{where}"
                : $"The copy failed ({e.Message}) and {dst} could not be put back by itself.{where} Copy it back from there.",
                backup: had ? backup : null);
        }
        return result;
    }

    /// The backup copied back to target, when the swap lost it; false when that failed too
    static bool Restore(string backup, string target)
    {
        try
        {
            CopyTree(backup, target, faults: false);
            return true;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { return false; }
    }

    /// Import (an emulator's save into Longshot) and export (Longshot's save into an emulator), as oot_saves.run picks the two sides:
    /// Longshot's one profile, the emulator's (profile: when it has several); folder: the emulator's folder instead of where it is
    /// looked for (a portable user folder, NX2navi's game folder, any folder holding a save)
    public static SaveCopy ImportExport(bool import, SaveProgram other, string? folder, SaveEnvironment env, string? profile = null,
                                        bool keepSettings = false, bool dryRun = false, bool force = false, string? backupRoot = null,
                                        Func<IReadOnlyList<string>>? running = null, Func<DateTime>? now = null)
    {
        var build = Shared(env);
        var em = Locate(other, folder, env).Profiles;
        var emulator = Pick(em, other.Display, profile);
        if (!import && !build.Found) throw new SaveFailure((build.Problem ?? "No Longshot save found.") + " Start Longshot once and save first.");
        var hs = import ? ImportTarget(env) : Pick(build.Profiles, "Longshot").Path;
        var (src, dst) = import ? (emulator.Path, hs) : (hs, emulator.Path);
        return Copy(src, dst, backupRoot ?? env.BackupRoot, import ? "import" : "export", other.Name, keepSettings, dryRun, force, running, now);
    }

    // ---- Windows: the saves each build kept in its own folder, into the shared one ----

    /// The user folders where Windows builds kept their saves before they shared one (Gather takes them in): each build's own
    /// (&lt;folder&gt;\user, until the launcher started every build with --user) and the 2.x Builder's game folder's, oldBuilder
    /// (%USERPROFILE%\Games\Longshot; null for a portable launcher, which writes nothing outside its own folder). None on Linux,
    /// where the game has always shared them
    public static IReadOnlyList<string> OldUserFolders(SaveEnvironment env, IEnumerable<string> buildFolders, string? oldBuilder)
    {
        if (env.Platform != Platform.Windows) return Array.Empty<string>();
        var shared = System.IO.Path.TrimEndingDirectorySeparator(env.LongshotUser);
        var list = new List<string>();
        foreach (var f in oldBuilder == null ? buildFolders : buildFolders.Append(oldBuilder))
        {
            var user = System.IO.Path.TrimEndingDirectorySeparator(System.IO.Path.GetFullPath(System.IO.Path.Combine(f, "user")));
            if (!user.Equals(shared, StringComparison.OrdinalIgnoreCase) && !list.Contains(user, StringComparer.OrdinalIgnoreCase)) list.Add(user);
        }
        return list;
    }

    /// When a save folder's adventure was last saved: its newest progress.sav, in any profile and slot (DateTime.MinValue when it
    /// has none). Only progress counts: a game that just started writes account.sav and option.sav before anything is played
    static DateTime LastProgress(string save)
    {
        try
        {
            return Directory.EnumerateFiles(save, "progress.sav", SearchOption.AllDirectories).Select(File.GetLastWriteTimeUtc)
                            .DefaultIfEmpty(DateTime.MinValue).Max();
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { return DateTime.MinValue; }
    }

    static bool HasSave(string user) => Directory.Exists(System.IO.Path.Combine(user, "save")) && Find(user).Count > 0;

    static bool IsLinked(string path) => (Directory.Exists(path) || File.Exists(path)) && IsLink(new DirectoryInfo(path));

    /// The per-player files the game keeps beside save\ in its user folder (host/nn_hid.c, gpu/render/rx_present_fx.cpp): brought
    /// along with the save that is kept, when the shared folder has none of its own yet
    static readonly string[] PlayerFiles = { "mouse_sens.txt", "present.txt" };

    /// The saves of the old user folders (OldUserFolders) into the shared one, so that every build plays the same adventure. The
    /// save with the newest progress of them all, the shared one's included, is kept (its newest progress.sav; a tie keeps the
    /// shared one, so a save an old build just made, with nothing played, never replaces it): it becomes the shared save\. Every
    /// one of them is backed up whole first, in one folder (&lt;backups&gt;/gather-&lt;yyyyMMdd-HHmmss&gt;/&lt;name&gt;), and each old folder's
    /// save\ is then renamed save.moved-&lt;stamp&gt;, so the game does not find it there again and nothing is deleted. An old folder
    /// that is a link, or holds one as its user\ or save\ (a player's own synced folder, or the shared one itself), is the
    /// player's own arrangement and is left alone. Null when no old folder has a save, or while Longshot runs (the next start
    /// tries again). A failure changes nothing (SaveFailure). An old save that cannot be renamed (a file in use) is taken in
    /// again at the next start, where it ties with the shared one and loses
    public static SaveGathered? Gather(SaveEnvironment env, IReadOnlyList<string> oldUsers, Func<IReadOnlyList<string>>? running = null,
                                       Func<DateTime>? now = null)
    {
        if (env.Platform != Platform.Windows) return null;
        var shared = env.LongshotUser;
        var sharedSave = System.IO.Path.Combine(shared, "save");
        var sharedReal = Real(sharedSave);
        var old = oldUsers.Where(u => HasSave(u) && !IsLinked(u) && !IsLinked(System.IO.Path.Combine(u, "save"))
                                      && !Inside(sharedReal, Real(System.IO.Path.Combine(u, "save"))) && !Inside(Real(System.IO.Path.Combine(u, "save")), sharedReal))
                          .ToList();
        if (old.Count == 0) return null;
        if ((running ?? (() => Running(Platforms.Current)))().Any(n => n.Contains(Longshot.Display, StringComparison.Ordinal))) return null;

        // (a gather cut short between its two renames, the PC off: the shared save waits beside itself, and goes back first)
        var (staging, aside) = Beside(sharedSave);
        if (!Directory.Exists(sharedSave) && Directory.Exists(aside)) Directory.Move(aside, sharedSave);

        // (each one named in the backup for its game folder: "v3.0.0-rc.1", or "Longshot" for the 2.x Builder's)
        var sides = new List<(string User, string Name)>();
        if (HasSave(shared)) sides.Add((shared, "shared"));
        foreach (var u in old)
        {
            var name = Base(Up(u)) is { Length: > 0 } b ? b : "build";
            var unique = name;
            for (var n = 2; sides.Any(s => s.Name.Equals(unique, StringComparison.OrdinalIgnoreCase)); n++) unique = $"{name} ({n})";
            sides.Add((u, unique));
        }
        var kept = sides.OrderByDescending(s => LastProgress(System.IO.Path.Combine(s.User, "save"))).First();   // (stable: the shared one first)

        var stamp = (now ?? (() => DateTime.Now))().ToString("yyyyMMdd-HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        var backup = System.IO.Path.Combine(env.BackupRoot, "gather-" + stamp);
        for (var n = 2; Directory.Exists(backup) || File.Exists(backup); n++) backup = System.IO.Path.Combine(env.BackupRoot, $"gather-{stamp}-{n}");
        try
        {
            foreach (var (user, name) in sides) CopyTree(System.IO.Path.Combine(user, "save"), System.IO.Path.Combine(backup, name));
            // (what a gather cut short left aside while a new shared save was made since: backed up too, before it goes)
            if (Directory.Exists(aside)) CopyTree(aside, System.IO.Path.Combine(backup, "shared (set aside)"));
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            DeleteTree(backup);
            throw new SaveFailure($"The saves could not be backed up ({e.Message}), so none was moved: they are as they were.");
        }

        if (kept.User != shared)
        {
            DeleteTree(staging);
            DeleteTree(aside);
            try
            {
                Directory.CreateDirectory(shared);
                CopyTree(System.IO.Path.Combine(kept.User, "save"), staging);
                if (Directory.Exists(sharedSave))
                {
                    Directory.Move(sharedSave, aside);
                    try
                    {
                        Fault?.Invoke("swap");
                        Directory.Move(staging, sharedSave);
                    }
                    catch (Exception) when (!Directory.Exists(sharedSave))
                    {
                        Directory.Move(aside, sharedSave);
                        throw;
                    }
                    DeleteTree(aside);
                }
                else Directory.Move(staging, sharedSave);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                DeleteTree(staging);
                throw new SaveFailure($"The saves could not be moved ({e.Message}). Nothing was changed; a backup of them all is in {backup}.", backup: backup);
            }
            foreach (var f in PlayerFiles)
            {
                var from = System.IO.Path.Combine(kept.User, f);
                var to = System.IO.Path.Combine(shared, f);
                try { if (File.Exists(from) && !File.Exists(to)) File.Copy(from, to); }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            }
        }

        var moved = new List<string>();
        foreach (var u in old)
        {
            var to = System.IO.Path.Combine(u, "save.moved-" + stamp);
            for (var n = 2; Directory.Exists(to) || File.Exists(to); n++) to = System.IO.Path.Combine(u, $"save.moved-{stamp}-{n}");
            try
            {
                Directory.Move(System.IO.Path.Combine(u, "save"), to);
                moved.Add(u);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        }
        return new SaveGathered(kept.User, kept.User == shared, moved, backup);
    }
}
