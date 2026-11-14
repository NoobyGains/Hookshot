using System.Text.RegularExpressions;

namespace LongshotLauncher.Core;

/// One Hookshot save folder found (or chosen): where it was looked for, its profile (the user id folder), its slots with when each
/// was saved, and what is wrong with it (empty: it can be imported)
public sealed record HookshotSource(string Where, string Profile, string Path, IReadOnlyList<SaveSlot> Slots, IReadOnlyList<string> Problems)
{
    public bool Valid => Problems.Count == 0;
}

/// The one bridge from Hookshot (docs/saves.md): its saves, copied into Longshot's. Hookshot is the project Longshot was
/// forked from, and its game writes the same save files in the same layout, so nothing in them is converted: no path, name or id
/// is written inside a save. The originals are only read, never moved, changed or deleted.
///   Linux    $XDG_DATA_HOME/hookshot/save/&lt;user id&gt;/ (default ~/.local/share/hookshot): every Hookshot build shares it
///   Windows  &lt;game folder&gt;\user\save\&lt;user id&gt;\, the game folder %USERPROFILE%\Games\Hookshot by default, or one folder per
///            version under it (Hookshot's own launcher put them there); any other folder is chosen by hand
/// A save folder holds account.sav, option.sav and slot_NN\ folders with progress.sav and caption.sav (Longshot's docs/saves.md). Anything
/// else in it, a link, an empty file or one far larger than a save is, refuses the import: the files are checked, not copied blindly.
public static class HookshotSaves
{
    public static readonly SaveProgram Program = new("hookshot", "Hookshot",
        new Dictionary<Platform, string[]> { [Platform.Linux] = new[] { "{data}/hookshot" }, [Platform.Windows] = new[] { "{home}/Games/Hookshot" } },
        new[] { "hookshot" }, Array.Empty<string>());

    /// A save file is a few kilobytes; anything above this is not one
    public const long MaxSaveFile = 4 << 20;
    static readonly Regex SlotName = new("^slot_[0-9]{2,3}$", RegexOptions.CultureInvariant);
    static readonly string[] ProfileFiles = { "account.sav", "option.sav" };
    static readonly string[] SlotFiles = { "progress.sav", "caption.sav" };

    /// The folders Hookshot keeps saves in on this PC, in the order shown: its data folder (Linux), its default game folder and
    /// each version folder in it (Windows)
    public static IReadOnlyList<string> Roots(SaveEnvironment env)
    {
        var roots = new List<string>();
        foreach (var root in env.FoldersOf(Program))
        {
            roots.Add(root);
            if (env.Platform != Platform.Windows || !Directory.Exists(root)) continue;
            try
            {
                roots.AddRange(Directory.EnumerateDirectories(root).Where(d => Directory.Exists(System.IO.Path.Combine(d, "user", "save")))
                                        .OrderBy(d => d, StringComparer.Ordinal));
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        }
        return roots;
    }

    /// Every Hookshot save found: in the usual places, or (folder) only under the folder the player chose
    public static IReadOnlyList<HookshotSource> Find(SaveEnvironment env, string? folder = null)
    {
        var found = new List<HookshotSource>();
        foreach (var root in folder != null ? new[] { System.IO.Path.GetFullPath(folder) } : Roots(env))
        {
            if (!Directory.Exists(root)) continue;
            IReadOnlyList<SaveProfile> profiles;
            try { profiles = Saves.Find(root); }
            catch (SaveFailure) { continue; }
            foreach (var p in profiles)
                if (!found.Any(f => f.Path == p.Path)) found.Add(new HookshotSource(root, p.Id, p.Path, Saves.Describe(p.Path), Validate(p.Path)));
        }
        return found;
    }

    /// What keeps a save folder from being imported (none: it is a save): only the save files, each a plain file of a save's size,
    /// at least one slot, and a progress.sav in every slot
    public static IReadOnlyList<string> Validate(string profile)
    {
        var problems = new List<string>();
        void Check(FileSystemInfo f)
        {
            if (f.LinkTarget != null || f.Attributes.HasFlag(FileAttributes.ReparsePoint)) problems.Add($"{f.Name} is a link");
            else if (f is FileInfo file && (file.Length == 0 || file.Length > MaxSaveFile))
                problems.Add($"{f.Name} is {(file.Length == 0 ? "empty" : "too large to be a save")}");
        }
        try
        {
            var dir = new DirectoryInfo(profile);
            if (dir.LinkTarget != null) return new[] { "The save folder is a link" };
            var slots = 0;
            foreach (var entry in dir.EnumerateFileSystemInfos())
            {
                if (entry is DirectoryInfo slot && SlotName.IsMatch(slot.Name))
                {
                    Check(slot);
                    if (slot.LinkTarget != null) continue;
                    slots++;
                    var hasProgress = false;
                    foreach (var f in slot.EnumerateFileSystemInfos())
                    {
                        if (f is not FileInfo || !SlotFiles.Contains(f.Name)) problems.Add($"{slot.Name}/{f.Name} is not a save file");
                        else
                        {
                            Check(f);
                            hasProgress |= f.Name == "progress.sav";
                        }
                    }
                    if (!hasProgress) problems.Add($"{slot.Name} has no progress.sav");
                }
                else if (entry is FileInfo && ProfileFiles.Contains(entry.Name)) Check(entry);
                else problems.Add($"{entry.Name} is not a save file");
            }
            if (slots == 0) problems.Add("There is no save slot");
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            problems.Add("It cannot be read: " + e.Message);
        }
        return problems;
    }

    /// Whether importing into target would replace a Longshot save (then the player is asked first)
    public static bool WouldReplace(string target) => Directory.Exists(target) && Saves.IsSaveFolder(target);

    /// Copies a checked Hookshot save into target. A Longshot save there is replaced only with overwrite (the player said so), and
    /// is copied whole to the backup folder first (Saves.Copy). Refused (SaveFailure): a save that does not pass Validate, a
    /// replace not agreed to, a game or Hookshot running
    public static SaveCopy Import(HookshotSource source, string target, string backupRoot, bool overwrite,
                                  Func<IReadOnlyList<string>>? running = null, Func<DateTime>? now = null)
    {
        var problems = Validate(source.Path);
        if (problems.Count > 0)
            throw new SaveFailure("This is not a Hookshot save that can be imported: " + string.Join("; ", problems) + ". Nothing was copied.");
        if (WouldReplace(target) && !overwrite)
            throw new SaveFailure("Longshot already has a save there. Say to replace it (it is backed up first), or keep it.", SaveRefusal.Exists);
        return Saves.Copy(source.Path, target, backupRoot, "hookshot", source.Profile, running: running, now: now);
    }
}
