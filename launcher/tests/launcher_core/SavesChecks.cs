using HookshotLauncher.Core;

/// launcher/Core/Saves.cs over tests/test_oot_saves.py's vectors (the same folders, the same expectations), so the launcher and
/// scripts/oot_saves.py agree. Fake saves made here only: HOME, XDG_DATA_HOME, APPDATA and LOCALAPPDATA all point into one folder.
static class SavesChecks
{
    public static int Count;
    const string Uid = "0123456789abcdef0123456789abcdef";
    const string Profile = "FEDCBA9876543210FEDCBA9876543210";
    const string Account = "00112233445566778899aabbccddeeff";

    static void Require(bool ok, string message)
    {
        if (!ok) throw new Exception("saves: " + message);
        Count++;
    }

    static void Fails(Action action, string contains, string message)
    {
        try { action(); }
        catch (SaveFailure e)
        {
            Require(e.Message.Contains(contains), $"{message} (said: {e.Message})");
            return;
        }
        throw new Exception("saves: not refused: " + message);
    }

    static string P(params string[] parts) => Path.Combine(parts);

    static void MakeSave(string folder, string tag, params string[] slots)
    {
        if (slots.Length == 0) slots = new[] { "slot_00", "slot_01" };
        Directory.CreateDirectory(folder);
        File.WriteAllText(P(folder, "account.sav"), "account-" + tag);
        File.WriteAllText(P(folder, "option.sav"), "option-" + tag);
        foreach (var s in slots.Where(s => s != "-"))
        {
            Directory.CreateDirectory(P(folder, s));
            File.WriteAllText(P(folder, s, "progress.sav"), "progress-" + tag + s);
            File.WriteAllText(P(folder, s, "caption.sav"), "caption-" + tag + s);
        }
    }

    static string Tree(string folder) =>
        !Directory.Exists(folder) ? "" : string.Join("\n", Directory.EnumerateFiles(folder, "*", SearchOption.AllDirectories)
            .Select(f => Path.GetRelativePath(folder, f) + "=" + File.ReadAllText(f)).Order(StringComparer.Ordinal));

    static string EdenSave(string data, string profile = Profile) => P(data, "nand", "user", "save", Saves.NoAccount, profile, Saves.Title);

    sealed class Case
    {
        public readonly string Tmp, Home, Data, AppData, LocalAppData, Hs, Li, Backups;
        public readonly SaveEnvironment Linux, Windows;
        public IReadOnlyList<string> Busy = Array.Empty<string>();

        public Case(string root, string name)
        {
            Tmp = P(root, name);
            Home = P(Tmp, "home");
            Data = P(Home, ".local", "share");
            AppData = P(Home, "AppData", "Roaming");
            LocalAppData = P(Home, "AppData", "Local");
            Hs = P(Data, "hookshot", "save", Uid);
            Li = EdenSave(P(Data, "eden"));
            Backups = P(Tmp, "backups");
            MakeSave(Hs, "HS");
            MakeSave(Li, "LI", "slot_00");
            string? Env(string k) => k switch
            {
                "HOME" or "USERPROFILE" => Home, "XDG_DATA_HOME" => Data, "APPDATA" => AppData, "LOCALAPPDATA" => LocalAppData, _ => null,
            };
            Linux = new SaveEnvironment(Platform.Linux, Env);
            Windows = new SaveEnvironment(Platform.Windows, Env);
        }

        public IReadOnlyList<string> BackupDirs() =>
            Directory.Exists(Backups) ? Directory.EnumerateDirectories(Backups).Order(StringComparer.Ordinal).ToList() : Array.Empty<string>();

        /// oot_saves.main import|export with the name or folder: Hookshot's side on Linux
        public SaveCopy Run(bool import, string? name, string? folder = null, string? profile = null, bool keep = false, bool dry = false, bool force = false)
        {
            var other = name == null ? Saves.Folder : Saves.Named(name);
            var hs = Saves.Pick(Saves.Locate(Saves.Hookshot, null, Linux).Profiles, "Hookshot");
            var em = Saves.Pick(Saves.Locate(other, folder, Linux).Profiles, other.Display, profile);
            var (src, dst) = import ? (em.Path, hs.Path) : (hs.Path, em.Path);
            return Saves.Copy(src, dst, Backups, import ? "import" : "export", other.Name, keep, dry, force, () => Busy);
        }
    }

    public static void Run(string root)
    {
        Discovery(root);
        Copies(root);
        FirstImports(root);
        Nx2navi(root);
        Guard(root);
        Builds(root);
    }

    static void Discovery(string root)
    {
        // (test_every_entry_on_linux)
        var c = new Case(root, "linux");
        MakeSave(EdenSave(P(c.Data, "eglantine")), "EG");
        var nx = P(c.Home, "Games", "Ocarina", "profile", "save", Account);
        MakeSave(nx, "NX");
        var expect = new Dictionary<string, string>
        {
            ["lichii"] = c.Li, ["frizti"] = c.Li, ["orchid"] = c.Li, ["pokedinner"] = c.Li, ["eden"] = c.Li,
            ["eglantine"] = EdenSave(P(c.Data, "eglantine")), ["nx2navi"] = nx,
        };
        Require(expect.Keys.Order().SequenceEqual(Saves.Emulators.Select(p => p.Name).Order()), "Every emulator of the script.");
        foreach (var program in Saves.Emulators)
            Require(Saves.Locate(program, null, c.Linux).Profiles.Select(p => p.Path).SequenceEqual(new[] { expect[program.Name] }), program.Name + " on Linux");
        Require(Saves.Locate(Saves.Hookshot, null, c.Linux).Profiles.SequenceEqual(new[] { new SaveProfile(Uid, c.Hs) }), "Hookshot on Linux");

        // (test_every_entry_on_windows)
        var w = new Case(root, "windows");
        var winLi = EdenSave(P(w.AppData, "eden"));
        var winEg = EdenSave(P(w.AppData, "eglantine"));
        var winNx = P(w.LocalAppData, "Programs", "NX2navi", "game", "profile", "save", Account);
        foreach (var f in new[] { winLi, winEg, winNx }) MakeSave(f, "W");
        var wexpect = new Dictionary<string, string>
        {
            ["lichii"] = winLi, ["frizti"] = winLi, ["orchid"] = winLi, ["pokedinner"] = winLi, ["eden"] = winLi, ["eglantine"] = winEg, ["nx2navi"] = winNx,
        };
        foreach (var program in Saves.Emulators)
            Require(Saves.Locate(program, null, w.Windows).Profiles.Select(p => p.Path).SequenceEqual(new[] { wexpect[program.Name] }), program.Name + " on Windows");
        Fails(() => Saves.Locate(Saves.Hookshot, null, w.Windows), "No Hookshot save found", "Windows: no shared save yet");
        Require(!Saves.Shared(w.Windows).Found && Saves.Shared(w.Windows).Problem != null, "Windows: no shared save yet, and why.");
        var game = P(w.Tmp, "Hookshot");
        MakeSave(P(game, "user", "save", Uid), "W");
        Require(Saves.Locate(Saves.Hookshot, game, w.Windows).Profiles.SequenceEqual(new[] { new SaveProfile(Uid, P(game, "user", "save", Uid)) }),
                "A Windows game folder of before, chosen.");
        var winShared = P(w.AppData, "Hookshot", "save", Uid);
        MakeSave(winShared, "S");
        Require(w.Windows.HookshotUser == P(w.AppData, "Hookshot") && Saves.Locate(Saves.Hookshot, null, w.Windows).Profiles.Single().Path == winShared
                && Saves.Shared(w.Windows).Profiles.Single().Path == winShared && Saves.SharedSavePath(w.Windows, Uid) == winShared,
                "Windows: the save every build shares, in %APPDATA%\\Hookshot.");
        Require((w.Windows with { UserFolder = P(w.Tmp, "usb", "user") }).HookshotUser == P(w.Tmp, "usb", "user")
                && w.Linux.HookshotUser == P(w.Data, "hookshot") && (w.Linux with { UserFolder = P(w.Tmp, "usb", "user") }).HookshotUser == P(w.Data, "hookshot")
                && Saves.Shared(w.Linux).Profiles.Single().Path == w.Hs, "A portable launcher's own user folder (Windows); on Linux the game's own.");

        // (test_lichii_s_own_folder_first)
        var l = new Case(root, "lichii-own");
        var own = EdenSave(P(l.Data, "lichii"));
        MakeSave(own, "L2", "slot_02");
        var located = Saves.Locate(Saves.Named("lichii"), null, l.Linux);
        Require(located.Folder == P(l.Data, "lichii") && located.Profiles.SequenceEqual(new[] { new SaveProfile(Profile, own) }), "Lichii's own folder first.");
        foreach (var name in new[] { "frizti", "orchid", "pokedinner", "eden" })
            Require(Saves.Locate(Saves.Named(name), null, l.Linux).Profiles.Single().Path == l.Li, name + " stays in Eden's folder");
        var winOwn = EdenSave(P(l.AppData, "lichii"));
        var winEden = EdenSave(P(l.AppData, "eden"));
        MakeSave(winOwn, "W2");
        MakeSave(winEden, "W1");
        Require(Saves.Locate(Saves.Named("lichii"), null, l.Windows).Profiles.Single().Path == winOwn
                && Saves.Locate(Saves.Named("orchid"), null, l.Windows).Profiles.Single().Path == winEden, "The same on Windows.");
        var groups = Saves.Emulator(l.Linux);
        Require(groups.Any(g => g.Display == "Lichii" && g.Folder == P(l.Data, "lichii"))
                && groups.Any(g => g.Display == "Frizti (Fritchii) / Orchid / PokeDinner / Eden" && g.Folder == P(l.Data, "eden"))
                && groups.Any(g => g.Display == "Eglantine" && !g.Found && g.Problem!.StartsWith("Nothing in")),
                "The list's groups with Lichii's own folder (test_list_with_lichii_s_own_folder).");
        var shared = Saves.Emulator(c.Linux);
        Require(shared.Any(g => g.Display == "Lichii / Frizti (Fritchii) / Orchid / PokeDinner / Eden" && g.Found)
                && shared.Any(g => g.Display == "NX2navi" && g.Profiles.Single().Id == Account), "The list's groups (test_list).");

        // (test_lichii_s_own_folder_without_a_save_leaves_the_older_one)
        var e = new Case(root, "lichii-empty");
        Directory.CreateDirectory(P(e.Data, "lichii", "nand", "user", "save"));
        Require(Saves.Locate(Saves.Named("lichii"), null, e.Linux).Profiles.Single().Path == e.Li, "An empty Lichii folder leaves Eden's.");

        // (test_aliases_of_names)
        Require(Saves.Named("Fritchii") == Saves.Named("frizti"), "Fritchii is Frizti.");
        Fails(() => Saves.Named("ryujinx"), "Unknown emulator", "An unknown emulator.");

        // (test_deeper_and_shallower_folders)
        var eden = P(c.Data, "eden");
        foreach (var r in new[] { eden, P(eden, "nand"), P(eden, "nand", "user", "save"), Path.GetDirectoryName(Path.GetDirectoryName(c.Li))!, Path.GetDirectoryName(c.Li)!, c.Li })
            Require(Saves.Find(r).SequenceEqual(new[] { new SaveProfile(Profile, c.Li) }), "Found from " + r);
        foreach (var r in new[] { P(c.Data, "hookshot"), Path.GetDirectoryName(c.Hs)!, c.Hs })
            Require(Saves.Find(r).SequenceEqual(new[] { new SaveProfile(Uid, c.Hs) }), "Found from " + r);

        // (test_empty_title_folder_is_a_target)
        var empty = EdenSave(P(c.Tmp, "portable", "user"), "11111111111111111111111111111111");
        Directory.CreateDirectory(empty);
        Require(Saves.Find(P(c.Tmp, "portable", "user")).SequenceEqual(new[] { new SaveProfile("11111111111111111111111111111111", empty) })
                && Saves.Find(empty).SequenceEqual(new[] { new SaveProfile("11111111111111111111111111111111", empty) }), "An empty title folder is a target.");

        // (test_eden_newer_layout)
        var newer = P(c.Tmp, "newer");
        const string uuid = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
        var save = P(newer, "nand", "user", "save", "account", uuid, Saves.Title, "0");
        MakeSave(save, "NEW");
        foreach (var r in new[] { newer, Path.GetDirectoryName(save)!, save })
            Require(Saves.Find(r).SequenceEqual(new[] { new SaveProfile(uuid, save) }), "Eden's newer layout from " + r);

        // (test_unrelated_folders_are_not_saves, test_missing_folders)
        Directory.CreateDirectory(P(c.Tmp, "junk", "a", "0"));
        Directory.CreateDirectory(P(c.Tmp, "junk", "b", "save", Uid));
        Require(Saves.Find(P(c.Tmp, "junk")).Count == 0, "Unrelated folders are not saves.");
        Fails(() => Saves.Locate(Saves.Folder, P(c.Tmp, "nothing"), c.Linux), "No folder", "A missing folder.");
        Directory.CreateDirectory(P(c.Tmp, "empty"));
        Fails(() => Saves.Locate(Saves.Folder, P(c.Tmp, "empty"), c.Linux), "No Ocarina of Time save", "An empty folder.");
        var noEg = new Case(root, "no-eglantine");
        Fails(() => Saves.Locate(Saves.Named("eglantine"), null, noEg.Linux), P(noEg.Data, "eglantine"), "Where Eglantine was looked for.");

        // (test_ambiguous_profiles_listed)
        var a = new Case(root, "ambiguous");
        const string other = "11111111111111111111111111111111";
        MakeSave(EdenSave(P(a.Data, "eden"), other), "O");
        var before = Tree(a.Li);
        try
        {
            a.Run(false, "lichii");
            throw new Exception("saves: two profiles were not refused");
        }
        catch (SaveFailure f)
        {
            Require(f.Message.Contains(Profile) && f.Message.Contains(other) && Tree(a.Li) == before && a.BackupDirs().Count == 0, "Two profiles: listed, nothing copied.");
        }
        a.Run(false, "lichii", profile: other.ToLowerInvariant());
        Require(Tree(EdenSave(P(a.Data, "eden"), other)) == Tree(a.Hs), "The profile asked for.");

        // (describe: the slots and when each was saved)
        File.SetLastWriteTime(P(c.Hs, "slot_01", "progress.sav"), new DateTime(2026, 11, 1, 12, 30, 0));
        var slots = Saves.Describe(c.Hs);
        Require(slots.Select(s => s.Name).SequenceEqual(new[] { "slot_00", "slot_01" }) && slots[1].Saved == new DateTime(2026, 11, 1, 12, 30, 0), "The slots and their times.");
    }

    static void Copies(string root)
    {
        // (test_export)
        var c = new Case(root, "export");
        var before = Tree(c.Li);
        var done = c.Run(false, "lichii");
        var backup = c.BackupDirs().Single();
        Require(Tree(c.Li) == Tree(c.Hs) && Path.GetFileName(backup).StartsWith("export-lichii-") && Tree(backup) == before && done.Backup == backup,
                "Export: the copy and its backup, whose path is said.");
        // (test_import)
        var i = new Case(root, "import");
        before = Tree(i.Hs);
        i.Run(true, "orchid");
        Require(Tree(i.Hs) == Tree(i.Li) && !Tree(i.Hs).Contains("slot_01") && Path.GetFileName(i.BackupDirs().Single()).StartsWith("import-orchid-")
                && Tree(i.BackupDirs().Single()) == before, "Import: the target's own slots go.");
        // (test_lichii_s_copy_goes_to_its_own_folder)
        var o = new Case(root, "own");
        var own = EdenSave(P(o.Data, "lichii"));
        MakeSave(own, "L2", "slot_02");
        before = Tree(o.Li);
        o.Run(false, "lichii");
        Require(Tree(own) == Tree(o.Hs) && Tree(o.Li) == before, "Lichii's copy goes to its own folder.");
        // (test_from_a_save_folder_and_a_data_folder)
        var f = new Case(root, "from");
        var otherSave = P(f.Tmp, "backup of a save");
        MakeSave(otherSave, "F", "slot_03");
        f.Run(true, null, otherSave);
        Require(Tree(f.Hs) == Tree(otherSave), "From a save folder.");
        var portable = P(f.Tmp, "Lichii", "user");
        MakeSave(EdenSave(portable), "P", "slot_04");
        f.Run(true, null, portable);
        Require(Tree(f.Hs) == Tree(EdenSave(portable)) && f.BackupDirs().All(b => Path.GetFileName(b).StartsWith("import-folder-")), "From a portable user folder.");
        // (test_to_a_folder)
        var t = new Case(root, "to");
        var target = EdenSave(P(t.Tmp, "Eglantine", "user"));
        Directory.CreateDirectory(target);
        t.Run(false, "eglantine", P(t.Tmp, "Eglantine", "user"));
        Require(Tree(target) == Tree(t.Hs), "To a portable folder whose game never saved.");
        // (test_links_in_a_save_refused)
        if (!OperatingSystem.IsWindows())
        {
            var k = new Case(root, "links");
            var secret = P(k.Tmp, "secret.txt");
            File.WriteAllText(secret, "not a save");
            before = Tree(k.Hs);
            var makers = new Action<string>[]
            {
                d => { File.Delete(P(d, "slot_00", "progress.sav")); File.CreateSymbolicLink(P(d, "slot_00", "progress.sav"), secret); },
                d => { File.Delete(P(d, "account.sav")); File.CreateSymbolicLink(P(d, "account.sav"), secret); },
                d => Directory.CreateSymbolicLink(P(d, "slot_00", "deep"), k.Tmp),
            };
            for (var n = 0; n < makers.Length; n++)
            {
                var linked = P(k.Tmp, "linked-" + n);
                MakeSave(linked, "L", "slot_00");
                makers[n](linked);
                Fails(() => k.Run(true, null, linked), "is a link", "A link in a save.");
                Require(Tree(k.Hs) == before, "A refused link changed nothing.");
            }
            Require(File.ReadAllText(secret) == "not a save", "The link's target is untouched.");
        }
        // (test_same_folder_refused, test_backup_inside_target_refused_before_copy)
        var s = new Case(root, "same");
        Fails(() => s.Run(true, null, s.Hs), "both the source and the target", "One folder both ways.");
        before = Tree(s.Hs);
        foreach (var dry in new[] { false, true })
        {
            Fails(() => Saves.Copy(s.Li, s.Hs, P(s.Hs, "backups"), "import", "folder", dryRun: dry, running: () => s.Busy),
                  "outside the target save folder", "A backup inside the target.");
            Require(!Directory.Exists(P(s.Hs, "backups")) && Tree(s.Hs) == before, "Nothing copied for a backup inside the target.");
        }
        // (test_keep_settings)
        var ks = new Case(root, "keep");
        ks.Run(false, "lichii", keep: true);
        Require(File.ReadAllText(P(ks.Li, "option.sav")) == "option-LI" && File.ReadAllText(P(ks.Li, "account.sav")) == "account-HS"
                && File.ReadAllText(P(ks.Li, "slot_01", "progress.sav")) == "progress-HSslot_01", "Keep settings: option.sav stays.");
        // (test_dry_run_changes_nothing)
        var d = new Case(root, "dry");
        var both = Tree(d.Hs) + Tree(d.Li);
        d.Busy = new[] { "Lichii" };
        var dry2 = d.Run(false, "lichii", dry: true);
        Require(dry2.Dry && Tree(d.Hs) + Tree(d.Li) == both && d.BackupDirs().Count == 0 && dry2.Slots.SequenceEqual(new[] { "slot_00", "slot_01" }),
                "A dry run says and changes nothing.");
        // (test_source_without_slots)
        var n2 = new Case(root, "noslots");
        foreach (var slot in new[] { "slot_00", "slot_01" }) Directory.Delete(P(n2.Hs, slot), true);
        before = Tree(n2.Li);
        Fails(() => n2.Run(false, "lichii"), "no slot_* folders", "A source with no slots.");
        Require(Tree(n2.Li) == before, "Nothing copied from no slots.");
    }

    static void Nx2navi(string root)
    {
        var c = new Case(root, "nx2navi");
        var game = P(c.Home, "Games", "Ocarina");
        var nx = P(game, "profile", "save", Account);
        MakeSave(nx, "NX", "slot_05");
        File.WriteAllBytes(P(game, "profile", "account.uid"), new byte[16]);
        Directory.CreateDirectory(P(game, "profile", "save-tx"));
        // (what NX2navi leaves in save-tx that is not a save in waiting, runtime/fs_host.c: the working copy a quit leaves,
        // an unfinished commit, the save a commit replaced, and names that are not a finished commit's)
        var tx = P(game, "profile", "save-tx");
        MakeSave(P(tx, "work"), "WORK", "slot_05");
        MakeSave(P(tx, "new"), "NEW", "slot_05");
        MakeSave(P(tx, "old"), "OLD", "slot_05");
        MakeSave(P(game, "profile", "save-import.part"), "PART", "slot_05");
        foreach (var name in new[] { "ready-0", "ready-", "ready-1x", "Ready-1", "ready-99999999999" }) MakeSave(P(tx, name), "NOT", "slot_05");
        File.WriteAllText(P(tx, "ready-2"), "a file, not a folder");
        Require(Saves.PendingCommit(nx) == null, "A working copy, an unfinished commit or an old save in save-tx is no save waiting.");
        // (test_both_ways)
        c.Run(true, "nx2navi");
        Require(Tree(c.Hs) == Tree(nx), "From NX2navi.");
        MakeSave(P(c.Hs, "slot_00"), "Z", "-");
        c.Run(false, "nx2navi", game);
        Require(Tree(nx) == Tree(c.Hs) && File.ReadAllBytes(P(game, "profile", "account.uid")).Length == 16, "To NX2navi's game folder.");
        // (test_waiting_save_refused)
        MakeSave(P(tx, "ready-0000000003"), "READY", "slot_05");
        var before = Tree(c.Hs) + Tree(nx);
        var backups = c.BackupDirs().Count;
        foreach (var import in new[] { true, false })
            Fails(() => c.Run(import, "nx2navi"), "save-tx", "A save waiting in save-tx.");
        Require(Tree(c.Hs) + Tree(nx) == before && c.BackupDirs().Count == backups && Saves.PendingCommit(nx) == P(game, "profile", "save-tx"),
                "Nothing copied while NX2navi has a save waiting.");
        c.Run(true, "nx2navi", force: true);
        Require(Tree(c.Hs) == Tree(nx), "Forced.");
        Directory.Delete(P(tx, "ready-0000000003"), recursive: true);
        var pendingImport = P(game, "profile", "save-import");
        MakeSave(pendingImport, "IMPORT", "slot_04");
        before = Tree(c.Hs) + Tree(game);
        backups = c.BackupDirs().Count;
        Require(Saves.PendingCommit(nx) == pendingImport, "NX2navi's completed menu import waits for the next start.");
        foreach (var import in new[] { true, false })
            Fails(() => c.Run(import, "nx2navi"), "save-import", "A menu import waiting in NX2navi.");
        Require(Tree(c.Hs) + Tree(game) == before && c.BackupDirs().Count == backups,
                "Nothing copied while NX2navi has a menu import waiting.");
    }

    static void Guard(string root)
    {
        // (test_refuses_while_running, test_force)
        var c = new Case(root, "guard");
        c.Busy = new[] { "Hookshot" };
        var before = Tree(c.Hs) + Tree(c.Li);
        Fails(() => c.Run(false, "lichii"), "Hookshot", "A running game.");
        Require(Tree(c.Hs) + Tree(c.Li) == before && c.BackupDirs().Count == 0, "Nothing copied while a game runs.");
        c.Busy = new[] { "Lichii" };
        c.Run(false, "lichii", force: true);
        Require(Tree(c.Li) == Tree(c.Hs), "Forced while running.");

        // (test_every_process_name_on_windows)
        var names = Saves.ProcessNames();
        foreach (var program in Saves.Emulators.Prepend(Saves.Hookshot))
            foreach (var p in program.Processes) Require(names[p].Contains(program.Display), "The process names of " + program.Name);
        var images = names.Keys.Select((p, i) => i % 2 == 1 ? p.ToUpperInvariant() + ".exe" : p + ".exe").Append("notepad.exe");
        Require(Saves.RunningFrom(Platform.Windows, images).SequenceEqual(names.Values.Distinct().Order(StringComparer.Ordinal)), "Every program's process on Windows.");
        // (test_linux_processes_and_appimages: each process's comm, and its argv[0]'s file name)
        var linux = new[] { "orchid", "orchid", "AppRun", "eglantine-linux-x86_64.AppImage", "ocarina", "ocarina", "bash", "bash" };
        Require(Saves.RunningFrom(Platform.Linux, linux).SequenceEqual(new[] { "NX2navi", "Orchid", "PokeDinner or Eglantine" }), "Linux processes and AppImages.");
        Require(Saves.RunningFrom(Platform.Linux, new[] { "Hookshot.AppImage", "HookshotLauncher" }).Count == 0, "The launcher itself is not the game.");
    }

    static void FirstImports(string root)
    {
        foreach (var platform in new[] { Platform.Linux, Platform.Windows })
        foreach (var custom in new[] { false, true })
        {
            var c = new Case(root, $"first-nx2navi-{platform}-{custom}");
            Directory.Delete(c.Hs, recursive: true);
            var env = platform == Platform.Linux ? c.Linux : c.Windows;
            var game = custom ? P(c.Tmp, "portable game") : platform == Platform.Linux
                ? P(c.Home, "Games", "Ocarina") : P(c.LocalAppData, "Programs", "NX2navi", "game");
            var folder = custom ? game : null;
            var source = P(game, "profile", "save", Profile);
            MakeSave(source, "FIRST", "slot_03");
            File.WriteAllBytes(P(game, "profile", "account.uid"), new byte[16]);
            var progress = P(source, "slot_03", "progress.sav");
            var bytes = new byte[] { 0, 255, 128, 42, 13, 10 };
            File.WriteAllBytes(progress, bytes);
            var sourceBefore = Tree(game);
            var target = Saves.ImportTarget(env);
            Require(target == P(env.HookshotUser, "save", "5a3c9e1f0b7d24680000000000000001")
                    && !Directory.Exists(target), "First import: the fixed user Hookshot reads, without writing a folder.");
            Require(Saves.Locate(Saves.Named("nx2navi"), folder, env).Profiles.Single().Path == source,
                    "First import: NX2navi's default or custom game folder on either platform.");

            SaveCopy Copy(bool dry = false) => Saves.ImportExport(true, Saves.Named("nx2navi"), folder, env,
                dryRun: dry, backupRoot: c.Backups, running: () => c.Busy);
            c.Busy = new[] { "NX2navi" };
            Fails(() => Copy(), "Close NX2navi", "First import refuses a running NX2navi.");
            Require(!Directory.Exists(target) && c.BackupDirs().Count == 0 && Tree(game) == sourceBefore,
                    "A refused first import writes nothing.");
            var preview = Copy(dry: true);
            Require(preview.Target == target && preview.Backup == null && !Directory.Exists(target) && c.BackupDirs().Count == 0,
                    "A first import's preview names the target without making it or a backup.");
            c.Busy = Array.Empty<string>();
            Fails(() => Saves.ImportExport(false, Saves.Named("nx2navi"), folder, env, backupRoot: c.Backups, running: () => c.Busy),
                  "Start Hookshot once", "Export still requires a Hookshot save.");
            foreach (var pending in new[] { P(game, "profile", "save-tx", "ready-1"), P(game, "profile", "save-import") })
            {
                MakeSave(pending, "WAITING", "slot_02");
                var before = Tree(game);
                try
                {
                    Copy();
                    throw new Exception("First import ignored NX2navi's pending save.");
                }
                catch (SaveFailure e)
                {
                    Require(e.Reason == SaveRefusal.Waiting && e.Who.SequenceEqual(new[] { "NX2navi" })
                            && e.Message.Contains(Path.GetFileName(pending) == "save-import" ? pending : Path.GetDirectoryName(pending)!),
                            "First import names NX2navi's pending commit or menu import.");
                }
                Require(!Directory.Exists(target) && c.BackupDirs().Count == 0 && Tree(game) == before,
                        "A pending NX2navi save refuses first import without changing either side.");
                Directory.Delete(pending, recursive: true);
            }

            var first = Copy();
            Require(first.Backup == null && Tree(target) == Tree(source)
                    && File.ReadAllBytes(P(target, "slot_03", "progress.sav")).SequenceEqual(bytes)
                    && File.ReadAllBytes(progress).SequenceEqual(bytes) && Tree(game) == sourceBefore,
                    "First import: every file copied, source bytes untouched, no backup of an absent target.");
            MakeSave(target, "PLAYED", "slot_08");
            var targetBefore = Tree(target);
            var second = Copy();
            Require(second.Backup != null && Tree(second.Backup) == targetBefore && Tree(target) == Tree(source)
                    && !Directory.Exists(P(target, "slot_08")) && Tree(game) == sourceBefore,
                    "A later import backs up the target whole and replaces its slots, leaving the source alone.");

            var secondSource = P(game, "profile", "save", Account);
            MakeSave(secondSource, "SECOND");
            var bothBefore = Tree(game) + Tree(target);
            var backups = c.BackupDirs().Count;
            Fails(() => Copy(), "pick one", "Several NX2navi profiles require a choice.");
            Require(Tree(game) + Tree(target) == bothBefore && c.BackupDirs().Count == backups,
                    "An ambiguous NX2navi profile writes nothing.");
            Saves.ImportExport(true, Saves.Named("nx2navi"), folder, env, profile: Account,
                               backupRoot: c.Backups, running: () => c.Busy);
            Require(Tree(target) == Tree(secondSource), "The NX2navi profile the player chose is imported.");

            // (a second Hookshot profile folder, one the game never opens: the import still goes into the fixed user, and leaves it)
            var stray = P(env.HookshotUser, "save", Uid);
            MakeSave(stray, "STRAY");
            var strayBefore = Tree(stray);
            Require(Saves.ImportTarget(env) == target, "Another Hookshot profile moved the import away from the user the game opens.");
            var beside = Saves.ImportExport(true, Saves.Named("nx2navi"), folder, env, profile: Account,
                                            backupRoot: c.Backups, running: () => c.Busy);
            Require(beside.Target == target && Tree(target) == Tree(secondSource) && Tree(stray) == strayBefore,
                    "An import beside a stray Hookshot profile goes into the fixed user and leaves the stray one alone.");
        }
    }

    static void Builds(string root)
    {
        // (import and export: the save every build shares, on Windows as on Linux)
        var c = new Case(root, "builds");
        MakeSave(EdenSave(P(c.AppData, "eden")), "WE", "slot_07");
        Fails(() => Saves.ImportExport(false, Saves.Named("lichii"), null, c.Windows, backupRoot: c.Backups, running: () => c.Busy),
              "Start Hookshot once", "Windows: Hookshot never saved yet.");
        var shared = Saves.SharedSavePath(c.Windows, Saves.UserId);
        MakeSave(shared, "S");
        Saves.ImportExport(true, Saves.Named("lichii"), null, c.Windows, backupRoot: c.Backups, running: () => c.Busy);
        Require(Tree(shared) == Tree(EdenSave(P(c.AppData, "eden"))), "Import into Windows' shared save.");
        Saves.ImportExport(false, Saves.Named("eden"), null, c.Linux, backupRoot: c.Backups, running: () => c.Busy);
        Require(Tree(c.Li) == Tree(c.Hs), "Export from Linux's shared save.");
        Gather(root);
    }

    /// Every file of a folder written at that time
    static void Age(string folder, DateTime when)
    {
        foreach (var f in Directory.EnumerateFiles(folder, "*", SearchOption.AllDirectories)) File.SetLastWriteTime(f, when);
    }

    static void Gather(string root)
    {
        // (Windows: the saves each build kept in its own folder, and the 2.x Builder's, into the one every build shares)
        var c = new Case(root, "gather");
        var builds = P(c.Home, "Games", "Hookshot");   // (the 2.x Builder's game folder, the launcher's builds folder in it)
        var a = P(builds, "v3.0.0-rc.1");
        var b = P(builds, "v3.0.0-rc.2");
        var old = Saves.OldUserFolders(c.Windows, new[] { a, b, a + Path.DirectorySeparatorChar }, builds);
        Require(old.SequenceEqual(new[] { P(a, "user"), P(b, "user"), P(builds, "user") }), "The old user folders: each build's once, then the 2.x Builder's.");
        Require(Saves.OldUserFolders(c.Linux, new[] { a }, builds).Count == 0, "None on Linux: the game has always shared them there.");
        Require(Saves.OldUserFolders(c.Windows with { UserFolder = P(a, "user") }, new[] { a, b }, null).SequenceEqual(new[] { P(b, "user") }),
                "Never the shared folder itself; no 2.x Builder's for a portable launcher.");
        Require(Saves.Gather(c.Windows, old, () => c.Busy) == null && Saves.Gather(c.Linux, old, () => c.Busy) == null, "Nothing to gather.");

        // (the folder the Hookshot Builder last built into, from its builder-settings.json: only a full path to a game folder)
        var settings = P(c.LocalAppData, "HookshotBuilder", "builder-settings.json");
        Require(Saves.BuilderGameFolder(c.Windows) == null, "No Hookshot Builder settings: no folder.");
        var chosen = P(c.Home, "D-drive", "Hookshot");
        Directory.CreateDirectory(P(chosen, "bin"));
        File.WriteAllText(P(chosen, GameFolder.StampName), "version=v2.2.0\n");
        Directory.CreateDirectory(Path.GetDirectoryName(settings)!);
        File.WriteAllText(settings, System.Text.Json.JsonSerializer.Serialize(new Dictionary<string, object?> { ["Out"] = chosen, ["Dlss"] = false }));
        Require(Saves.BuilderGameFolder(c.Windows) == chosen && Saves.BuilderGameFolder(c.Linux) == null, "The Builder's chosen game folder (Windows only).");
        foreach (var bad in new[] { "{\"Out\": \"relative\\\\Hookshot\"}", "{\"Out\": 3}", "not json", "[]", "{\"Out\": \"" + P(c.Home, "nothing").Replace("\\", "\\\\") + "\"}" })
        {
            File.WriteAllText(settings, bad);
            Require(Saves.BuilderGameFolder(c.Windows) == null, "A Builder setting that is no game folder was taken: " + bad);
        }
        File.Delete(settings);

        var when = new DateTime(2026, 11, 13, 9, 0, 0);
        var sharedSave = P(c.Windows.HookshotUser, "save");
        MakeSave(P(builds, "user", "save", Uid), "OLD");
        MakeSave(P(a, "user", "save", Uid), "A");
        MakeSave(P(b, "user", "save", Uid), "B");
        File.WriteAllText(P(a, "user", "mouse_sens.txt"), "2.5");
        Age(P(builds, "user", "save"), when.AddDays(-30));
        Age(P(a, "user", "save"), when.AddDays(-1));
        Age(P(b, "user", "save"), when.AddDays(-2));
        var treeA = Tree(P(a, "user", "save"));
        Require(Saves.Gather(c.Windows, old, () => new[] { "Hookshot" }) == null && Directory.Exists(P(a, "user", "save")) && !Directory.Exists(sharedSave),
                "Not while Hookshot runs: the next start tries again.");
        var g = Saves.Gather(c.Windows, old, () => new[] { "Lichii" }, () => when)!;
        Require(g.From == P(a, "user") && !g.WasShared && Tree(sharedSave) == treeA, "The newest save becomes the shared one (an emulator may run).");
        Require(File.ReadAllText(P(c.Windows.HookshotUser, "mouse_sens.txt")) == "2.5", "The kept save's own settings come along (mouse_sens.txt).");
        Require(g.Moved.SequenceEqual(old) && old.All(u => !Directory.Exists(P(u, "save")) && Directory.Exists(P(u, "save.moved-20261113-090000"))),
                "Each old save renamed aside: the game no longer finds it, nothing is deleted.");
        Require(Path.GetFileName(g.Backup) == "gather-20261113-090000" && Path.GetDirectoryName(g.Backup) == c.Windows.BackupRoot
                && Tree(P(g.Backup, "v3.0.0-rc.1")) == treeA && Tree(P(g.Backup, "Hookshot")) != "" && Tree(P(g.Backup, "v3.0.0-rc.2")) != "",
                "Every one backed up first, each named for its game folder.");
        Require(SaveText.Gathered(g).Contains(a) && SaveText.Gathered(g).Contains(g.Backup), "What the home says: where the save came from, and the backup.");
        Require(Saves.Gather(c.Windows, old, () => c.Busy) == null, "Done once: nothing left to gather.");

        // (an old build started on its own, without --user, saves in its folder again: the newer one wins, the shared one backed up)
        MakeSave(P(b, "user", "save", Uid), "B2");
        Age(sharedSave, when.AddDays(-1));
        Age(P(b, "user", "save"), when);
        var g2 = Saves.Gather(c.Windows, old, () => c.Busy, () => when.AddHours(1))!;
        Require(g2.From == P(b, "user") && Tree(sharedSave) == Tree(P(b, "user", "save.moved-20261113-100000")) && Tree(P(g2.Backup, "shared")) == treeA,
                "A newer save in a build's own folder wins; the shared one is backed up.");

        // (an older one: the shared save stays, the old one goes aside)
        var kept = Tree(sharedSave);
        MakeSave(P(a, "user", "save", Uid), "A3");
        Age(P(a, "user", "save"), when.AddDays(-5));
        Age(sharedSave, when);
        var g3 = Saves.Gather(c.Windows, old, () => c.Busy, () => when.AddHours(2))!;
        Require(g3.WasShared && g3.From == c.Windows.HookshotUser && Tree(sharedSave) == kept && !Directory.Exists(P(a, "user", "save"))
                && SaveText.Gathered(g3).Contains("shared"), "An older save: the shared one kept, the old one moved aside.");

        // (a swap that fails: the shared save and the old one as they were, the backup kept)
        MakeSave(P(a, "user", "save", Uid), "A4");
        Age(P(a, "user", "save"), when.AddDays(1));
        Saves.Fault = s => { if (s == "swap") throw new IOException("disk full"); };
        try { Fails(() => Saves.Gather(c.Windows, old, () => c.Busy, () => when.AddHours(3)), "Nothing was changed", "A gather that fails half way."); }
        finally { Saves.Fault = null; }
        Require(Tree(sharedSave) == kept && Directory.Exists(P(a, "user", "save")) && !Directory.Exists(P(c.Windows.HookshotUser, ".save.hookshot-old")),
                "After a failed gather: the shared save and the old one as they were.");

        // (a shared save a gather cut short left aside, while a new one was made since: backed up before it goes)
        var aside = P(c.Windows.HookshotUser, ".save.hookshot-old");
        MakeSave(P(aside, Uid), "ASIDE");
        var asideTree = Tree(aside);
        var g4 = Saves.Gather(c.Windows, old, () => c.Busy, () => when.AddHours(4))!;
        Require(g4.From == P(a, "user") && Tree(P(g4.Backup, "shared (set aside)")) == asideTree && !Directory.Exists(aside),
                "What a gather cut short left aside is backed up too.");

        // (an old build started on its own makes a save with nothing played: it never replaces the shared one)
        var keptNow = Tree(sharedSave);
        Directory.CreateDirectory(P(b, "user", "save", Uid));
        File.WriteAllText(P(b, "user", "save", Uid, "account.sav"), "fresh");
        File.WriteAllText(P(b, "user", "save", Uid, "option.sav"), "fresh");
        var g5 = Saves.Gather(c.Windows, old, () => c.Busy, () => when.AddHours(5))!;
        Require(g5.WasShared && Tree(sharedSave) == keptNow && !Directory.Exists(P(b, "user", "save")),
                "A save with nothing played yet never replaces the shared one; it goes aside.");

        // (a user\save that is a link, the player's own arrangement or the shared folder itself, is left alone)
        var linked = P(c.Tmp, "linked");
        Directory.CreateDirectory(P(linked, "user"));
        Directory.CreateSymbolicLink(P(linked, "user", "save"), sharedSave);
        Require(Saves.Gather(c.Windows, new[] { P(linked, "user") }, () => c.Busy, () => when.AddHours(6)) == null
                && Tree(sharedSave) == keptNow && Directory.Exists(P(linked, "user", "save")), "A linked save folder is never gathered nor renamed.");
    }
}
