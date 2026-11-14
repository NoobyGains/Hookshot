using System.Security.Cryptography;
using LongshotLauncher.Core;

/// The Hookshot save importer (Core/HookshotSaves.cs) over tests/fixtures/hookshot-saves, fake saves only, copied into the scratch
/// folder first: found where Hookshot keeps them on each system, summed up, checked, copied (never moved), never replacing a
/// Longshot save without the player's yes, and backing that save up first when it does.
static partial class Program
{
    const string Id1 = "0123456789abcdef0123456789abcdef", Id2 = "fedcba9876543210fedcba9876543210";

    static void CopyDir(string from, string to)
    {
        Directory.CreateDirectory(to);
        foreach (var f in Directory.EnumerateFiles(from)) File.Copy(f, Path.Combine(to, Path.GetFileName(f)));
        foreach (var d in Directory.EnumerateDirectories(from)) CopyDir(d, Path.Combine(to, Path.GetFileName(d)));
    }

    /// Every file under a folder with its SHA-256, to see that nothing in it changed
    static string Tree(string folder) => string.Join("\n", Directory.EnumerateFiles(folder, "*", SearchOption.AllDirectories)
        .Select(f => Path.GetRelativePath(folder, f).Replace('\\', '/') + " " + Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(f))))
        .Order(StringComparer.Ordinal));

    static void HookshotChecks(string fixtures)
    {
        var root = Folder("hookshot");
        CopyDir(Path.Combine(fixtures, "hookshot-saves"), root);
        var none = () => (IReadOnlyList<string>)Array.Empty<string>();
        var when = () => new DateTime(2026, 11, 12, 10, 0, 0);

        // (Linux: $XDG_DATA_HOME/hookshot/save/<id>)
        var linuxData = Path.Combine(root, "linux");
        var linux = new SaveEnvironment(Platform.Linux, k => k switch { "XDG_DATA_HOME" => linuxData, "HOME" => Path.Combine(root, "home"), _ => null });
        var found = HookshotSaves.Find(linux);
        Require(found.Count == 1 && found[0].Profile == Id1 && found[0].Valid && found[0].Slots.Select(s => s.Name).SequenceEqual(new[] { "slot_00", "slot_01" })
                && found[0].Slots.All(s => s.Saved != null), "Linux: Hookshot's save, with its slots and when they were saved.");
        var hookshotBefore = Tree(Path.Combine(linuxData, "hookshot"));

        var target = Saves.ImportTarget(linux);
        Require(target == Path.Combine(linuxData, "longshot", "save", Saves.UserId) && !HookshotSaves.WouldReplace(target),
                "Linux: a new save in the fixed profile Longshot reads, regardless of the source profile.");
        var backups = Path.Combine(root, "backups");
        var first = HookshotSaves.Import(found[0], target, backups, overwrite: false, none, when);
        Require(first.Backup == null && first.Slots.SequenceEqual(new[] { "slot_00", "slot_01" })
                && File.ReadAllText(Path.Combine(target, "slot_01", "progress.sav")) == File.ReadAllText(Path.Combine(found[0].Path, "slot_01", "progress.sav"))
                && File.Exists(Path.Combine(target, "option.sav")) && File.Exists(Path.Combine(target, "slot_00", "caption.sav")),
                "The slots, account.sav and option.sav copied.");
        Require(Tree(Path.Combine(linuxData, "hookshot")) == hookshotBefore, "Hookshot's own saves changed.");

        // (a Longshot save there: refused without a yes, untouched; with it, backed up first, then replaced)
        File.WriteAllText(Path.Combine(target, "slot_01", "progress.sav"), "played on in Longshot");
        var longshotBefore = Tree(target);
        Require(HookshotSaves.WouldReplace(target) && Saves.ImportTarget(linux) == target, "The same profile is found again.");
        try
        {
            HookshotSaves.Import(found[0], target, backups, overwrite: false, none, when);
            throw new Exception("A Longshot save was replaced without asking.");
        }
        catch (SaveFailure e) when (e.Reason == SaveRefusal.Exists) { checks++; }
        Require(Tree(target) == longshotBefore, "A refused import changed Longshot's save.");
        var second = HookshotSaves.Import(found[0], target, backups, overwrite: true, none, when);
        Require(second.Backup != null && File.ReadAllText(Path.Combine(second.Backup, "slot_01", "progress.sav")) == "played on in Longshot"
                && File.ReadAllText(Path.Combine(target, "slot_01", "progress.sav")) != "played on in Longshot",
                "Replacing backs Longshot's save up first.");
        Require(Tree(Path.Combine(linuxData, "hookshot")) == hookshotBefore, "Hookshot's own saves changed by a replace.");
        try
        {
            HookshotSaves.Import(found[0], target, backups, overwrite: true, () => new[] { "Hookshot" }, when);
            throw new Exception("An import ran while Hookshot was running.");
        }
        catch (SaveFailure e) when (e.Reason == SaveRefusal.Running) { checks++; }
        Require(Saves.ProcessNames().TryGetValue("hookshot", out var who) && who == "Hookshot", "A running Hookshot is seen.");

        // A Longshot profile folder the game never opens (here one with Hookshot's own id) is not a target: the import still
        // goes into the fixed user, and leaves that folder alone.
        var stray = Saves.SharedSavePath(linux, Id1);
        CopyDir(found[0].Path, stray);
        File.WriteAllText(Path.Combine(stray, "slot_01", "progress.sav"), "a copy by hand");
        var strayBefore = Tree(stray);
        Require(Saves.ImportTarget(linux) == target, "Another Longshot profile moved the import away from the user the game opens.");
        var third = HookshotSaves.Import(found[0], Saves.ImportTarget(linux), backups, overwrite: true, none, when);
        Require(third.Target == target && Tree(stray) == strayBefore && Tree(Path.Combine(linuxData, "hookshot")) == hookshotBefore,
                "An import beside another Longshot profile goes into the fixed user and changes neither that profile nor Hookshot.");

        // (Windows: the default game folder, and a version folder in it; the import goes into the save every build shares)
        var home = Path.Combine(root, "windows");
        var windows = new SaveEnvironment(Platform.Windows, k => k switch { "HOME" => home, "USERPROFILE" => home, "APPDATA" => Path.Combine(home, "Roaming"), _ => null });
        var win = HookshotSaves.Find(windows);
        Require(win.Count == 2 && win.Select(s => s.Profile).SequenceEqual(new[] { Id1, Id2 }) && win.All(s => s.Valid)
                && win[1].Slots.Single().Name == "slot_02", "Windows: Games\\Hookshot and its version folders.");
        Require(Saves.ImportTarget(windows) == Path.Combine(home, "Roaming", "Longshot", "save", Saves.UserId),
                "Windows: into the shared save, %APPDATA%\\Longshot\\save, with no build needed.");

        // (a folder chosen by hand: a game folder, or the save folder itself)
        Require(HookshotSaves.Find(linux, Path.Combine(home, "Games", "Hookshot", "v3.0.0")).Single().Profile == Id2
                && HookshotSaves.Find(linux, Path.Combine(linuxData, "hookshot", "save", Id1)).Single().Valid
                && HookshotSaves.Find(linux, Path.Combine(root, "nothing here")).Count == 0, "A folder chosen by hand.");

        // (checked, not copied blindly)
        var broken = HookshotSaves.Find(linux, Path.Combine(root, "broken")).Single();
        Require(!broken.Valid && broken.Problems.Contains("account.sav is empty") && broken.Problems.Contains("slot_00 has no progress.sav")
                && broken.Problems.Contains("notes.txt is not a save file"), "The problems of a broken save: " + string.Join("; ", broken.Problems));
        var brokenTarget = Path.Combine(root, "broken-target");
        Throws<SaveFailure>(() => HookshotSaves.Import(broken, brokenTarget, backups, overwrite: true, none, when), "A broken save was imported.");
        Require(!Directory.Exists(brokenTarget), "A refused import wrote something.");
        var big = Path.Combine(root, "big", Id1);
        CopyDir(found[0].Path, big);
        File.WriteAllBytes(Path.Combine(big, "slot_00", "progress.sav"), new byte[HookshotSaves.MaxSaveFile + 1]);
        File.WriteAllText(Path.Combine(big, "slot_00", "screenshot.png"), "x");
        Require(HookshotSaves.Validate(big).Contains("progress.sav is too large to be a save")
                && HookshotSaves.Validate(big).Contains("slot_00/screenshot.png is not a save file"), "A file too large, a file that is no save file.");
        if (!OperatingSystem.IsWindows())
        {
            var linked = Path.Combine(root, "linked", Id1);
            CopyDir(found[0].Path, linked);
            File.Delete(Path.Combine(linked, "option.sav"));
            File.CreateSymbolicLink(Path.Combine(linked, "option.sav"), "/etc/hostname");
            Require(HookshotSaves.Validate(linked).Contains("option.sav is a link"), "A link in a save.");
        }
    }
}
