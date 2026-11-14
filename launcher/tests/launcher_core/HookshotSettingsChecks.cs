using LongshotLauncher.Core;

static partial class Program
{
    static void HookshotSettingsChecks()
    {
        var root = Folder("hookshot-settings");
        var source = Path.Combine(root, "Hookshot");
        var target = Path.Combine(root, "Longshot");
        var backups = Path.Combine(root, "backups");
        Directory.CreateDirectory(source);
        Directory.CreateDirectory(target);
        var ini = "# settings\noptions_version=4\nquality_preset=0\noutput_res=2560x1440\nresolution=1\nframe_generation=0\n" +
                  "frame_rate_cap=3\nmouse_sensitivity=125\npad_a=1\nkey_zl=90,2\nmesh_shaders=1\nunknown_future=1\n";
        File.WriteAllText(Path.Combine(source, "hookshot_options.ini"), ini);
        File.WriteAllText(Path.Combine(source, "language.txt"), "# language\npt-br\n");
        File.WriteAllText(Path.Combine(source, "hookshot_env.txt"), "RX_TEST=1\n");
        var originalSource = Tree(source);
        var none = () => (IReadOnlyList<string>)Array.Empty<string>();
        var when = () => new DateTime(2026, 11, 13, 15, 0, 0);
        var preview = HookshotSettings.Import(source, target, backups, overwrite: false, dryRun: true, running: () => new[] { "Hookshot" }, now: when);
        Require(preview.Files.SequenceEqual(new[] { "longshot_options.ini", "language.txt" }) && preview.Backup == null
                && preview.SkippedKeys.SequenceEqual(new[] { "mesh_shaders", "unknown_future" }) && !Directory.Exists(backups) && !Directory.EnumerateFiles(target).Any(),
                "Settings preview lists compatible files and omitted keys without writing or refusing a running game.");
        Require(HookshotSettings.FilesIn(source).SequenceEqual(preview.Files), "Settings source files match the import preview.");
        Throws<SaveFailure>(() => HookshotSettings.Import(source, target, backups, false, running: () => new[] { "Hookshot" }), "Settings imported while Hookshot runs.");
        Require(!Directory.EnumerateFiles(target).Any(), "A running game's refused settings import writes nothing.");
        HookshotSettings.Import(source, target, backups, false, running: none, now: when);
        var migrated = File.ReadAllText(Path.Combine(target, "longshot_options.ini"));
        Require(migrated.Contains("options_version=4\n") && migrated.Contains("output_res=2560x1440\n") && migrated.Contains("key_zl=90,2\n")
                && !migrated.Contains("mesh_shaders") && !migrated.Contains("unknown_future") && !File.Exists(Path.Combine(target, "hookshot_env.txt"))
                && File.ReadAllText(Path.Combine(target, "language.txt")) == "pt-BR\n" && Tree(source) == originalSource,
                "Graphics, controls and normalized language imported; source untouched, unknown keys and environment not copied.");

        // (the build's own lines, Longshot's settings Hookshot does not have and keys the launcher does not know, are kept in
        // their place; an imported key replaces its line's value, and the imported keys the file lacks go at the end)
        File.WriteAllText(Path.Combine(target, "longshot_options.ini"),
                          "options_version=6\ncompile_shaders=1\nmouse_sensitivity=250\nvsync=2\nnote_up=4\n# mine\nfuture_longshot_key=7\n");
        File.WriteAllText(Path.Combine(target, "language.txt"), "fr\n");
        var originalTarget = Tree(target);
        Throws<SaveFailure>(() => HookshotSettings.Import(source, target, backups, false, running: none), "Existing settings replaced without consent.");
        Require(Tree(target) == originalTarget && !Directory.Exists(backups), "Refused replacement leaves settings and backups alone.");
        var replaced = HookshotSettings.Import(source, target, backups, true, running: none, now: when);
        Require(replaced.Backup != null && Tree(replaced.Backup) == originalTarget && Tree(source) == originalSource,
                "Replacing settings backs up the whole old INI and language first, preserving the source.");
        Require(File.ReadAllText(Path.Combine(target, "longshot_options.ini")) ==
                "options_version=4\ncompile_shaders=1\nmouse_sensitivity=125\nvsync=2\nnote_up=4\n# mine\nfuture_longshot_key=7\n" +
                "quality_preset=0\noutput_res=2560x1440\nresolution=1\nframe_generation=0\nframe_rate_cap=3\npad_a=1\nkey_zl=90,2\n"
                && replaced.Language == "pt-BR",
                "The import merges into the build's longshot_options.ini: compile_shaders, vsync and unknown lines kept, imported keys replaced or added.");
        Require(HookshotSettings.Merge("vsync=2\r\nvolume=10\r\n", new[] { ("volume", "50"), ("hdr", "1") }) == "vsync=2\r\nvolume=50\r\nhdr=1\r\n"
                && HookshotSettings.Merge(null, new[] { ("volume", "50") }) == "volume=50\n"
                && HookshotSettings.Merge(" volume = 10 \nvolume=20\nnot a line\n", new[] { ("volume", "50") }) == "volume=50\nvolume=50\nnot a line\n",
                "The merge keeps the file's line ends, replaces every line of an imported key and keeps lines it cannot read.");
        // (the merged file is read under Hookshot's options_version: a file without one removes the build's marker, so that
        // Longshot migrates Hookshot's rows as a file from before the marker, and the build's own lines a migration between the
        // two versions would move are removed, so they take Longshot's default instead of being moved again)
        Require(HookshotSettings.Merge("options_version=6\nvsync=2\n", new[] { ("game_speed", "0") }) == "vsync=2\ngame_speed=0\n"
                && HookshotSettings.Merge("options_version=6\nvsync=2\nmenu_shortcut=0\nultrawide=0\ndescriptor_reuse=0\ngame_speed=0\nkey_y=89\nkey_x=88\n",
                                          new[] { ("volume", "50") }) == "vsync=2\nkey_x=88\nvolume=50\n",
                "A Hookshot file without options_version keeps the build's marker, or build lines its migrations would move.");
        Require(HookshotSettings.Merge("options_version=6\nmenu_shortcut=0\nultrawide=0\ndescriptor_reuse=0\nkey_y=89\nvsync=2\n",
                                       new[] { ("options_version", "4"), ("volume", "50") })
                == "options_version=4\ndescriptor_reuse=0\nkey_y=89\nvsync=2\nvolume=50\n"
                && HookshotSettings.Merge("options_version=6\nmenu_shortcut=1\nultrawide=1\n", new[] { ("options_version", "4"), ("menu_shortcut", "0") })
                == "options_version=4\nmenu_shortcut=0\n"
                && HookshotSettings.Merge("game_speed=0\ndescriptor_reuse=0\nkey_zl=90\nmenu_shortcut=0\n", new[] { ("options_version", "4"), ("volume", "50") })
                == "menu_shortcut=0\noptions_version=4\nvolume=50\n",
                "Build lines read differently under the imported options_version were kept, or Hookshot's own rows were dropped.");
        Require(HookshotSettings.Merge("", new[] { ("volume", "50") }) == "volume=50\n", "An empty options file does not merge as a new one.");

        File.WriteAllText(Path.Combine(target, "longshot_options.ini"), "old graphics\n");
        File.WriteAllText(Path.Combine(target, "language.txt"), "de\n");
        originalTarget = Tree(target);
        HookshotSettings.Fault = name => { if (name == "language.txt") throw new IOException("test disk full"); };
        try { Throws<SaveFailure>(() => HookshotSettings.Import(source, target, backups, true, running: none, now: when), "Settings disk failure was not reported."); }
        finally { HookshotSettings.Fault = null; }
        Require(Tree(target) == originalTarget && Tree(source) == originalSource, "A second-file write failure restores both settings files.");

        var newTarget = Path.Combine(root, "new-build");
        Directory.CreateDirectory(newTarget);
        var countBefore = Directory.EnumerateDirectories(backups).Count();
        HookshotSettings.Fault = name => { if (name == "language.txt") throw new IOException("test disk full"); };
        try { Throws<SaveFailure>(() => HookshotSettings.Import(source, newTarget, backups, false, running: none, now: when), "A new build's failed import was not reported."); }
        finally { HookshotSettings.Fault = null; }
        Require(!Directory.EnumerateFiles(newTarget).Any() && Directory.EnumerateDirectories(backups).Count() == countBefore && Tree(source) == originalSource,
                "A failed first import removes its new files, creates no backup, and preserves Hookshot.");
        HookshotSettings.Fault = name =>
        {
            if (name != "language.txt") return;
            Directory.CreateDirectory(Path.Combine(newTarget, name));
            throw new IOException("test destination changed");
        };
        try
        {
            HookshotSettings.Import(source, newTarget, backups, false, running: none, now: when);
            throw new Exception("An incomplete settings rollback was not reported.");
        }
        catch (SaveFailure e)
        {
            Require(e.Backup == null && e.Message.Contains("New, incomplete settings") && !e.Message.Contains("from the backup"),
                    "A failed rollback of new files does not point at a nonexistent backup.");
        }
        finally { HookshotSettings.Fault = null; }
        Directory.Delete(Path.Combine(newTarget, "language.txt"));
        var blockedBackup = Path.Combine(root, "backup-is-a-file");
        File.WriteAllText(blockedBackup, "not a folder");
        Throws<SaveFailure>(() => HookshotSettings.Import(source, target, blockedBackup, true, running: none), "An impossible backup did not stop the import.");
        Require(Tree(target) == originalTarget, "A backup failure leaves the destination unchanged.");

        foreach (var bad in new[] { "options_version=5\nvolume=50\n", "not an INI line\n" })
        {
            File.WriteAllText(Path.Combine(source, "hookshot_options.ini"), bad);
            var backupCount = Directory.EnumerateDirectories(backups).Count();
            Throws<SaveFailure>(() => HookshotSettings.Import(source, target, backups, true, running: none), "An invalid or future settings file imported.");
            Require(Tree(target) == originalTarget && Directory.EnumerateDirectories(backups).Count() == backupCount, "Invalid settings create no backup or target changes.");
        }
        // (a value out of the range of Longshot's menu does not stop the import: the key is listed and left out, as an unknown one)
        File.WriteAllText(Path.Combine(source, "hookshot_options.ini"),
                          "options_version=4\nvolume=999\noutput_res=99999x99999\npad_a=99\ntext_speed=2\nfuture_row=1\n");
        var skipping = HookshotSettings.Import(source, target, backups, true, dryRun: true, running: none);
        Require(skipping.Files.Contains("longshot_options.ini") && skipping.SkippedKeys.SequenceEqual(new[] { "future_row", "output_res", "pad_a", "volume" })
                && Tree(target) == originalTarget, "Out-of-range values are listed with the unknown keys, and the preview writes nothing.");
        var skipTarget = Path.Combine(root, "skip-target");
        Directory.CreateDirectory(skipTarget);
        File.WriteAllText(Path.Combine(skipTarget, "longshot_options.ini"), "volume=40\npad_a=3\n");
        var skipped = HookshotSettings.Import(source, skipTarget, backups, true, running: none, now: when);
        Require(File.ReadAllText(Path.Combine(skipTarget, "longshot_options.ini")) == "volume=40\npad_a=3\noptions_version=4\ntext_speed=2\n"
                && skipped.SkippedKeys.Contains("volume"),
                "An out-of-range Hookshot value leaves the build's own value, and the valid keys are imported.");
        // (the last line of a key is the one used, as the game reads them: imported with its last value, or skipped and listed)
        File.WriteAllText(Path.Combine(source, "hookshot_options.ini"),
                          "options_version=4\nvolume=50\nvolume=999\ntext_speed=9\ntext_speed=2\n");
        var lastLine = Path.Combine(root, "last-line-target");
        Directory.CreateDirectory(lastLine);
        var last = HookshotSettings.Import(source, lastLine, backups, false, running: none, now: when);
        Require(last.SkippedKeys.SequenceEqual(new[] { "volume" }) && File.ReadAllText(Path.Combine(lastLine, "longshot_options.ini")) == "options_version=4\ntext_speed=2\n",
                "A key's last line decides whether it is imported or skipped, not an earlier one.");
        File.WriteAllBytes(Path.Combine(source, "hookshot_options.ini"), new byte[HookshotSettings.MaxFileSize + 1]);
        Throws<SaveFailure>(() => HookshotSettings.FilesIn(source), "An oversized settings file imported.");
        File.WriteAllBytes(Path.Combine(source, "hookshot_options.ini"), new byte[] { 0xff, 0xfe, 0 });
        Throws<SaveFailure>(() => HookshotSettings.FilesIn(source), "Non UTF-8 settings imported.");
        File.WriteAllText(Path.Combine(source, "hookshot_options.ini"), ini);
        File.WriteAllText(Path.Combine(source, "language.txt"), "not-a-language\n");
        Throws<SaveFailure>(() => HookshotSettings.FilesIn(source), "An unsupported game language imported.");
        File.WriteAllText(Path.Combine(source, "language.txt"), "pt-BR\n");
        Throws<SaveFailure>(() => HookshotSettings.Import(source, target, source, true, running: none), "A backup was put into Hookshot's folder.");
        // (an empty longshot_options.ini has nothing to keep: imported into without a backup or the overwrite consent)
        var emptyTarget = Path.Combine(root, "empty-target");
        Directory.CreateDirectory(emptyTarget);
        File.WriteAllText(Path.Combine(emptyTarget, "longshot_options.ini"), "");
        var intoEmpty = HookshotSettings.Import(source, emptyTarget, backups, false, running: none, now: when);
        Require(intoEmpty.Backup == null && File.ReadAllText(Path.Combine(emptyTarget, "longshot_options.ini")) ==
                "options_version=4\nquality_preset=0\noutput_res=2560x1440\nresolution=1\nframe_generation=0\nframe_rate_cap=3\nmouse_sensitivity=125\npad_a=1\nkey_zl=90,2\n"
                && File.ReadAllText(Path.Combine(emptyTarget, "language.txt")) == "pt-BR\n", "An empty longshot_options.ini refused the import.");
        if (!OperatingSystem.IsWindows())
        {
            var beforeLinks = Tree(source);
            File.Delete(Path.Combine(source, "language.txt"));
            File.CreateSymbolicLink(Path.Combine(source, "language.txt"), Path.Combine(target, "language.txt"));
            Throws<SaveFailure>(() => HookshotSettings.FilesIn(source), "A linked source settings file imported.");
            File.Delete(Path.Combine(source, "language.txt"));
            File.WriteAllText(Path.Combine(source, "language.txt"), "pt-BR\n");
            var linkedFile = Path.Combine(root, "linked-file-target");
            Directory.CreateDirectory(linkedFile);
            File.CreateSymbolicLink(Path.Combine(linkedFile, "longshot_options.ini"), Path.Combine(source, "hookshot_options.ini"));
            Throws<SaveFailure>(() => HookshotSettings.Import(source, linkedFile, backups, true, running: none), "A linked target settings file was written through.");

            // (a link on the way to a folder, as a symlinked ~/Games or a linked game folder, is resolved and the folders compared)
            var alias = Path.Combine(root, "parent-alias");
            Directory.CreateSymbolicLink(alias, root);
            var linkedSource = Path.Combine(root, "linked-source");
            Directory.CreateSymbolicLink(linkedSource, source);
            Require(HookshotSettings.FilesIn(Path.Combine(alias, "Hookshot")).SequenceEqual(HookshotSettings.FilesIn(source))
                    && HookshotSettings.FilesIn(linkedSource).SequenceEqual(HookshotSettings.FilesIn(source)),
                    "A game folder under a linked parent, or linked itself, was refused.");
            Throws<SaveFailure>(() => HookshotSettings.Import(source, Path.Combine(alias, "Hookshot"), backups, true, running: none), "A target alias overwrote Hookshot's own files.");
            Throws<SaveFailure>(() => HookshotSettings.Import(linkedSource, source, backups, true, running: none), "A source alias overwrote Hookshot's own files.");
            Throws<SaveFailure>(() => HookshotSettings.Import(source, target, Path.Combine(alias, "Hookshot"), true, running: none), "A backup went into Hookshot's folder through a link.");
            Throws<SaveFailure>(() => HookshotSettings.Import(source, target, Path.Combine(alias, "Longshot", "backups"), true, running: none), "A backup went into the target through a link.");
            Require(Tree(source) == beforeLinks && Tree(target) == originalTarget, "Linked aliases leave source and destination untouched.");

            var linkedBackup = Path.Combine(root, "linked-backup");
            Directory.CreateSymbolicLink(linkedBackup, backups);
            var through = HookshotSettings.Import(linkedSource, Path.Combine(alias, "Longshot"), linkedBackup, true, running: none, now: when);
            Require(through.Target == Saves.Real(target) && through.Backup != null && Path.GetDirectoryName(through.Backup) == Saves.Real(backups)
                    && Tree(through.Backup) == originalTarget && File.ReadAllText(Path.Combine(target, "language.txt")) == "pt-BR\n" && Tree(source) == beforeLinks,
                    "An import through linked source, target and backup folders writes into the real folders and backs up first.");
        }
    }
}
