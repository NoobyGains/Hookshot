using System.Text;
using HookshotLauncher.Core;

/// The launcher kept on the PC: installed or portable (LauncherLayout, Installer), its update keeping its kind and name, a start
/// putting right an update cut short (SelfUpdate.Recover), one launcher per home (InstanceLock), a stalled download, a save copy that
/// fails half way, and the AppImage's own entry in the applications menu. The registry and the shortcuts are fakes: nothing here
/// touches the real ones.
static partial class Program
{
    sealed class FakeRegistry : IUserRegistry
    {
        public readonly Dictionary<string, Dictionary<string, object>> Keys = new();
        public IReadOnlyDictionary<string, object>? Read(string key) => Keys.TryGetValue(key, out var v) ? v : null;
        public void Write(string key, IReadOnlyDictionary<string, object> values)
        {
            if (!Keys.TryGetValue(key, out var k)) Keys[key] = k = new Dictionary<string, object>();
            foreach (var (n, v) in values) k[n] = v;
        }
        public void Delete(string key) => Keys.Remove(key);
    }

    sealed class FakeShortcuts : IShortcutMaker
    {
        public readonly Dictionary<string, string> Links = new();
        public void Make(string link, string target, string? arguments, string icon, string description)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(link)!);
            File.WriteAllText(link, target);
            Links[link] = target;
        }
        public void Remove(string link)
        {
            File.Delete(link);
            Links.Remove(link);
        }
    }

    sealed class FailingShortcuts : IShortcutMaker
    {
        public void Make(string link, string target, string? arguments, string icon, string description) => throw new IOException("blocked");
        public void Remove(string link) { }
    }

    /// A stream that gives a few bytes, then nothing until it is cancelled (a download that stalled half way)
    sealed class StallingStream : Stream
    {
        int given;
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => given; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancel = default)
        {
            if (given < 3)
            {
                await Task.Delay(30, cancel);   // (slower than nothing, faster than the timeout: a slow download goes on)
                buffer.Span[0] = (byte)'x';
                given++;
                return 1;
            }
            await Task.Delay(Timeout.Infinite, cancel);
            return 0;
        }
    }

    static async Task InstallChecks()
    {
        var root = Folder("install");
        var local = Path.Combine(root, "Local ゲーム");
        var appData = Path.Combine(root, "Roaming");
        Func<string, string?> env = k => k switch { "LOCALAPPDATA" => local, "APPDATA" => appData, "HOME" => Path.Combine(root, "home"), _ => null };

        // (where it installs, and what it is from where it runs)
        var installed = Path.Combine(local, "Programs", "HookshotLauncher", "HookshotLauncher.exe");
        Require(LauncherLayout.InstalledExe(env) == installed, "The installed program: %LOCALAPPDATA%\\Programs\\HookshotLauncher\\HookshotLauncher.exe.");
        var downloads = Path.Combine(root, "Downloads");
        Directory.CreateDirectory(downloads);
        var setup = Path.Combine(downloads, "HookshotLauncher-v1.0.0-windows-x64-setup.exe");
        File.WriteAllText(setup, "MZ launcher v1.0.0");
        var plain = LauncherLayout.Of(Platform.Windows, setup, env);
        Require(plain.Kind == LauncherKind.Plain && plain.OffersInstall("v1.0.0", env) && !plain.OffersInstall("dev", env)
                && !plain.OffersInstall("v1.0.0", k => k == LauncherHome.Variable ? root : env(k)) && plain.UpdateKey == "windows-x64"
                && LauncherHome.Resolve(Platform.Windows, env, plain).Root == Path.GetFullPath(Path.Combine(local, "HookshotLauncher")),
                "The download, neither installed nor portable: it offers Install or Run portable (not a build from a checkout), its home the usual one.");
        Require(!LauncherLayout.Of(Platform.Linux, "/apps/x.AppImage", env).OffersInstall("v1.0.0", env), "Linux never offers to install.");

        // (Install: the program copied, the Start menu shortcut, the Apps & features entry; nothing of the real registry)
        var registry = new FakeRegistry();
        var links = new FakeShortcuts();
        var at = InstallPlaces.Of(env);
        Require(at.Program == installed && at.StartMenuLink == Path.Combine(appData, "Microsoft", "Windows", "Start Menu", "Programs", "Hookshot Launcher.lnk")
                && at.Home == Path.GetFullPath(Path.Combine(local, "HookshotLauncher")), "What the installer touches.");
        Directory.CreateDirectory(at.Folder);
        File.WriteAllText(SelfUpdate.Backup(installed), "a leftover");
        Require(Installer.Install(setup, "v1.0.0", at, registry, links) == installed && File.ReadAllText(installed) == "MZ launcher v1.0.0"
                && File.Exists(setup) && !File.Exists(SelfUpdate.Backup(installed))
                && !Directory.EnumerateFiles(at.Folder).Any(f => f.EndsWith(".part", StringComparison.Ordinal)),
                "Install: the program copied whole into place (the download stays), the leftovers of earlier updates gone.");
        var entry = registry.Read(Installer.UninstallKey)!;
        Require(Installer.UninstallKey == @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HookshotLauncher"
                && (string)entry["DisplayName"] == "Hookshot Launcher" && (string)entry["DisplayVersion"] == "1.0.0" && (string)entry["Publisher"] == "The Hookshot contributors" && (string)entry["URLInfoAbout"] == Repository.Page(Repository.Current)
                && (string)entry["DisplayIcon"] == installed + ",0" && (string)entry["UninstallString"] == $"\"{installed}\" --uninstall"
                && entry["NoModify"] is 1 && entry["EstimatedSize"] is int, "The Apps & features entry.");
        Require(links.Links.TryGetValue(at.StartMenuLink, out var target) && target == installed, "The Start menu shortcut starts the installed program.");
        var inst = LauncherLayout.Of(Platform.Windows, installed, env);
        Require(inst.Kind == LauncherKind.Installed && !inst.OffersInstall("v1.0.0", env) && inst.UpdateKey == "windows-x64"
                && LauncherLayout.Of(Platform.Windows, installed.ToUpperInvariant(), env).Kind == LauncherKind.Installed,
                "The installed program knows it is installed (whatever the case of its path), and updates from the setup program.");
        Installer.Register(at, "v1.1.0-rc.1", registry);
        Require((string)registry.Read(Installer.UninstallKey)!["DisplayVersion"] == "1.1.0-rc.1", "The entry follows the launcher's own updates.");
        // (the Start menu shortcut made again at the first start of another version; else left alone, deleted or not)
        File.WriteAllText(at.StartMenuLink, @"C:\a moved-aside HookshotLauncher.exe.old");
        links.Links[at.StartMenuLink] = "stale";
        Require(Installer.Refresh(at, "v1.1.0-rc.2", registry, links) && links.Links[at.StartMenuLink] == installed
                && (string)registry.Read(Installer.UninstallKey)!["DisplayVersion"] == "1.1.0-rc.2", "After an update: the shortcut made again, to the installed program.");
        links.Links[at.StartMenuLink] = "untouched";
        Require(!Installer.Refresh(at, "v1.1.0-rc.2", registry, links) && links.Links[at.StartMenuLink] == "untouched", "The same version again: left alone.");
        links.Remove(at.StartMenuLink);
        Require(!Installer.Refresh(at, "v1.1.0-rc.2", registry, links) && !File.Exists(at.StartMenuLink), "A shortcut the player deleted stays deleted.");
        var failing = new FailingShortcuts();
        Throws<IOException>(() => Installer.Refresh(at, "v1.1.0-rc.3", registry, failing), "A shortcut that cannot be made: the start goes on.");
        Require((string)registry.Read(Installer.UninstallKey)!["DisplayVersion"] == "1.1.0-rc.2" && Installer.Refresh(at, "v1.1.0-rc.3", registry, links)
                && links.Links[at.StartMenuLink] == installed, "...and it is tried again at the next start.");
        File.WriteAllText(setup, "MZ launcher v1.1.0");
        Installer.Install(setup, "v1.1.0", at, registry, links);
        Require(File.ReadAllText(installed) == "MZ launcher v1.1.0" && links.Links.Count == 1, "Installing again replaces the installed program.");

        // (update keeps the kind and the name: the installed program stays HookshotLauncher.exe)
        File.WriteAllBytes(SelfUpdate.Staged(installed), Encoding.UTF8.GetBytes("MZ launcher v1.2.0"));
        SelfUpdate.Swap(installed, SelfUpdate.Staged(installed), Platform.Windows);
        Require(File.ReadAllText(installed) == "MZ launcher v1.2.0" && LauncherLayout.Of(Platform.Windows, installed, env).Kind == LauncherKind.Installed
                && File.ReadAllText(SelfUpdate.Backup(installed)) == "MZ launcher v1.1.0", "An installed launcher's update: still the installed program.");

        // (a crash between the two renames: no program, its .old and .new beside it; the next start puts the old one back)
        File.Move(installed, SelfUpdate.Backup(installed), overwrite: true);
        File.WriteAllText(SelfUpdate.Staged(installed), "MZ launcher v1.3.0");
        Require(SelfUpdate.LeftoverOf(SelfUpdate.Backup(installed)) == installed && SelfUpdate.LeftoverOf(installed) == null,
                "A launcher started from its .old knows the file it is the leftover of.");
        Require(SelfUpdate.Recover(installed) is { } said && said.Contains("cut short") && File.ReadAllText(installed) == "MZ launcher v1.2.0"
                && !File.Exists(SelfUpdate.Backup(installed)) && !File.Exists(SelfUpdate.Staged(installed)),
                "Recover: the .old back in place, the .new gone.");
        File.WriteAllText(SelfUpdate.Staged(installed) + ".part", "half");
        Require(SelfUpdate.Recover(installed) != null && !File.Exists(SelfUpdate.Staged(installed) + ".part") && File.Exists(installed)
                && SelfUpdate.Recover(installed) == null, "Recover: a half download goes; then there is nothing left to do.");

        // (uninstall: the shortcut, the entry and the program go; the data stays unless asked, and builds and save backups never go)
        var home = new LauncherHome(at.Home);
        Directory.CreateDirectory(Path.Combine(home.Toolchains, "v3.0.0"));
        File.WriteAllText(home.Settings, "{}");
        var buildInside = Path.Combine(home.Root, "my builds", "v3.0.0");
        Directory.CreateDirectory(Path.Combine(buildInside, "user", "save"));
        File.WriteAllText(Path.Combine(buildInside, "user", "save", "progress.sav"), "a save");
        var backups = Path.Combine(home.Root, "oot-save-backups");
        Directory.CreateDirectory(backups);
        File.WriteAllText(Path.Combine(backups, "b.sav"), "a backup");
        var running = Installer.Uninstall(at, registry, links, deleteData: false, new[] { buildInside }, running: installed);
        Require(running.Pending == installed && File.Exists(installed) && !Installer.IsRegistered(registry) && !File.Exists(at.StartMenuLink)
                && File.Exists(home.Settings), "Uninstall from the installed program: it is deleted once it has closed; the data kept.");
        Installer.Install(setup, "v1.1.0", at, registry, links);
        var removed = Installer.Uninstall(at, registry, links, deleteData: true, new[] { buildInside, backups }, running: setup);
        Require(removed.Pending == null && !File.Exists(installed) && !Directory.Exists(at.Folder) && registry.Keys.Count == 0 && links.Links.Count == 0,
                "Uninstall: the program and its folder, the entry and the shortcut gone.");
        Require(!File.Exists(home.Settings) && !Directory.Exists(home.Toolchains)
                && File.ReadAllText(Path.Combine(buildInside, "user", "save", "progress.sav")) == "a save" && File.Exists(Path.Combine(backups, "b.sav"))
                && removed.Kept.Contains(Path.GetFullPath(buildInside)), "The data deleted when asked, but never a build inside it nor the save backups.");

        // (portable: the "portable" file beside the program; its data beside it, its update from the portable zip, in place)
        var usb = Path.Combine(root, "USB stick");
        Directory.CreateDirectory(usb);
        var portableExe = Path.Combine(usb, "HookshotLauncher.exe");
        File.WriteAllText(portableExe, "MZ launcher v1.0.0");
        File.WriteAllText(Path.Combine(usb, LauncherLayout.PortableMarker), "");
        var portable = LauncherLayout.Of(Platform.Windows, portableExe, env);
        var portableHome = LauncherHome.Resolve(Platform.Windows, env, portable);
        Require(portable.Kind == LauncherKind.Portable && !portable.OffersInstall("v1.0.0", env) && portable.UpdateKey == ReleaseManifest.WindowsPortable
                && portableHome.Root == Path.Combine(usb, "HookshotLauncher-data") && portableHome.Portable
                && portableHome.PortableBuilds.StartsWith(portableHome.Root, StringComparison.Ordinal)
                && portableHome.PortableSaveBackups.StartsWith(portableHome.Root, StringComparison.Ordinal)
                && LauncherHome.Resolve(Platform.Windows, k => k == LauncherHome.Variable ? root : env(k), portable).Root == Path.GetFullPath(root),
                "Portable: its data, builds and save backups in HookshotLauncher-data beside it (HOOKSHOT_LAUNCHER_HOME still first).");
        var zip = LauncherFiles("v1.1.0")[ReleaseManifest.LauncherFile("v1.1.0", ReleaseManifest.WindowsPortable)];
        var server = new FakeFetcher();
        server.Files["https://x/portable.zip"] = zip;
        var zipRef = new FileRef("https://x/portable.zip", ShaOf(zip), zip.Length);
        var staged = await SelfUpdate.DownloadAsync(server, zipRef, portableExe, zipEntry: LauncherLayout.ProgramName);
        Require(staged == SelfUpdate.Staged(portableExe) && File.ReadAllText(staged) == "MZ launcher v1.1.0"
                && Directory.EnumerateFiles(usb).All(f => !f.EndsWith(".part", StringComparison.Ordinal)), "The program out of the checked portable zip.");
        SelfUpdate.Swap(portableExe, staged, Platform.Windows);
        Require(File.ReadAllText(portableExe) == "MZ launcher v1.1.0" && LauncherLayout.Of(Platform.Windows, portableExe, env).Kind == LauncherKind.Portable,
                "A portable launcher's update: in place, beside its portable file, still portable.");
        await ThrowsAsync<InvalidDataException>(() => SelfUpdate.DownloadAsync(server, zipRef, portableExe, zipEntry: "Other.exe"),
                                                "A zip without the launcher in it was taken.");
        await ThrowsAsync<InvalidDataException>(() => SelfUpdate.DownloadAsync(server, zipRef with { Sha256 = new string('0', 64) }, portableExe,
                                                                                zipEntry: LauncherLayout.ProgramName), "A zip that is not the release's was opened.");
        Require(!File.Exists(SelfUpdate.Staged(portableExe)) && File.ReadAllText(portableExe) == "MZ launcher v1.1.0", "A refused zip left nothing.");

        // (Linux: the AppImage; portable with an <AppImage>.home folder beside it, the AppImage convention)
        var image = Path.Combine(root, "apps", "HookshotLauncher-v1.0.0-x86_64.AppImage");
        Directory.CreateDirectory(Path.GetDirectoryName(image)!);
        File.WriteAllText(image, "ELF");
        var lin = LauncherLayout.Of(Platform.Linux, image, env);
        Require(lin.Kind == LauncherKind.Plain && lin.UpdateKey == "linux-x64" && lin.PortableHome == null, "The AppImage, not portable.");
        Directory.CreateDirectory(image + ".home");
        lin = LauncherLayout.Of(Platform.Linux, image, env);
        Require(lin.Kind == LauncherKind.Portable && LauncherHome.Resolve(Platform.Linux, env, lin).Root == image + ".home" && lin.UpdateKey == "linux-x64",
                "The AppImage with its .home folder: portable, its data there.");

        // (the AppImage's own entry in the applications menu)
        var data = Path.Combine(root, "xdg");
        Func<string, string?> xdg = k => k == "XDG_DATA_HOME" ? data : env(k);
        Require(Shortcuts.LauncherInMenu(xdg) == null, "Not in the menu yet.");
        Shortcuts.AddLauncherToMenu(image, new byte[] { 0x89, (byte)'P', (byte)'N', (byte)'G' }, xdg);
        var (menuEntry, menuIcon) = Shortcuts.LauncherMenuPaths(xdg);
        var desktopText = File.ReadAllText(menuEntry);
        Require(menuEntry == Path.Combine(data, "applications", "hookshot-launcher.desktop") && File.Exists(menuIcon)
                && desktopText.Contains("Exec=" + Shortcuts.Quote(image) + "\n") && desktopText.Contains("Icon=" + menuIcon + "\n")
                && Shortcuts.LauncherInMenu(xdg) == image, "Add to applications menu: the entry starts the AppImage where it is, with its icon.");
        Require(desktopText.Contains("\nStartupWMClass=hookshot-launcher\n"), "The menu entry names the window's class (its app_id and WM_CLASS).");
        Shortcuts.RemoveLauncherFromMenu(xdg);
        Require(!File.Exists(menuEntry) && !File.Exists(menuIcon) && Shortcuts.LauncherInMenu(xdg) == null, "Removed from the menu.");

        LockChecks(root);
        await StallChecks();
        SaveFaultChecks(root);
    }

    // ---- one launcher per home ----

    static void LockChecks(string root)
    {
        var home = Path.Combine(root, "lock home");
        using (var first = InstanceLock.TryAcquire(home, Platform.Linux))
        {
            Require(first != null && InstanceLock.TryAcquire(home, Platform.Linux) == null, "A second launcher on the same home is refused (the flock'd file).");
            Require(InstanceLock.TryAcquire(Path.Combine(root, "other home"), Platform.Linux) is { } other && Dispose(other),
                    "A launcher on another home is not.");
        }
        using (var again = InstanceLock.TryAcquire(home, Platform.Linux)) Require(again != null, "The lock is let go when the first one closes.");

        // (the named mutex, Windows': taken on one thread, refused on another, as two processes would see it)
        Require(InstanceLock.MutexName(home) == InstanceLock.MutexName(home + Path.DirectorySeparatorChar)
                && InstanceLock.MutexName(home).StartsWith(@"Local\HookshotLauncher-", StringComparison.Ordinal)
                && InstanceLock.MutexName(home) != InstanceLock.MutexName(root), "One mutex name per home.");
        if (OperatingSystem.IsWindows())
        {
            using var taken = new ManualResetEventSlim();
            using var done = new ManualResetEventSlim();
            var holder = new Thread(() =>
            {
                using var held = InstanceLock.TryAcquire(home + "-m", Platform.Windows);
                taken.Set();
                done.Wait();
            });
            holder.Start();
            taken.Wait();
            Require(InstanceLock.TryAcquire(home + "-m", Platform.Windows) == null, "A second launcher is refused (the named mutex).");
            done.Set();
            holder.Join();
        }

        // (a second start pokes the first, which brings its window forward)
        using var poked = new ManualResetEventSlim();
        using (InstanceLock.Watch(home, () => poked.Set()))
        {
            InstanceLock.Poke(home);
            Require(poked.Wait(TimeSpan.FromSeconds(10)), "The first launcher hears a second start.");
        }
    }

    static bool Dispose(IDisposable d)
    {
        d.Dispose();
        return true;
    }

    // ---- a download that stalls ----

    static async Task StallChecks()
    {
        using var to = new MemoryStream();
        long have = 0;
        var watch = System.Diagnostics.Stopwatch.StartNew();
        try
        {
            await HttpFetcher.CopyAsync(new StallingStream(), to, n => have = n, TimeSpan.FromMilliseconds(400), CancellationToken.None);
            Require(false, "A stalled download went on for ever.");
        }
        catch (FetchException e)
        {
            Require(e.Transient && have == 3 && watch.Elapsed < TimeSpan.FromSeconds(10) && e.Message.Contains("stalled"),
                    "A download that stops coming fails after the read timeout (a slow one goes on), as a FetchException the mirrors retry.");
        }
        using var cancel = new CancellationTokenSource(TimeSpan.FromMilliseconds(200));
        await ThrowsAsync<OperationCanceledException>(() => HttpFetcher.CopyAsync(new StallingStream(), new MemoryStream(), null, TimeSpan.FromSeconds(30), cancel.Token),
                                                      "Cancel is still Cancel, not a stall.");
    }

    // ---- a save copy that fails half way: the target as it was, the backup named ----

    static void SaveFaultChecks(string root)
    {
        var folder = Path.Combine(root, "save faults");
        var src = Path.Combine(folder, "src");
        var dst = Path.Combine(folder, "dst");
        foreach (var (dir, text) in new[] { (src, "new"), (dst, "old") })
        {
            foreach (var slot in new[] { "slot_00", "slot_01" })
            {
                Directory.CreateDirectory(Path.Combine(dir, slot));
                File.WriteAllText(Path.Combine(dir, slot, "progress.sav"), text + " " + slot);
            }
            File.WriteAllText(Path.Combine(dir, "account.sav"), text + " account");
        }
        Directory.CreateDirectory(Path.Combine(dst, "slot_02"));
        File.WriteAllText(Path.Combine(dst, "slot_02", "progress.sav"), "old slot_02");
        File.WriteAllText(Path.Combine(dst, "keep.txt"), "not a save file");
        string Tree(string d) => string.Join("\n", Directory.EnumerateFiles(d, "*", SearchOption.AllDirectories).Order(StringComparer.Ordinal)
                                                    .Select(f => Path.GetRelativePath(d, f) + "=" + File.ReadAllText(f)));
        var before = Tree(dst);
        var backups = Path.Combine(folder, "backups");
        var when = new DateTime(2026, 11, 12, 20, 0, 0);
        foreach (var (stage, nth) in new[] { ("file", 6), ("file", 9), ("swap", 1) })
        {
            var count = 0;
            Saves.Fault = s =>
            {
                if (s == stage && ++count == nth) throw new IOException("There is not enough space on the disk (authored).");
            };
            try
            {
                Saves.Copy(src, dst, backups, "import", "x", running: () => Array.Empty<string>(), now: () => when);
                Require(false, $"The authored failure ({stage} {nth}) did not stop the copy.");
            }
            catch (SaveFailure e)
            {
                Require(Tree(dst) == before && e.Backup != null && Directory.Exists(e.Backup) && Tree(e.Backup) == before
                        && e.Message.Contains(e.Backup) && e.Message.Contains("Nothing was changed"),
                        $"A copy that fails ({stage} {nth}) leaves the target as it was, and says where its backup is.");
                Require(!Directory.EnumerateDirectories(folder).Any(d => Path.GetFileName(d).StartsWith('.')), "No staging folder left over.");
            }
            finally { Saves.Fault = null; }
        }
        var done = Saves.Copy(src, dst, backups, "import", "x", running: () => Array.Empty<string>(), now: () => when);
        Require(File.ReadAllText(Path.Combine(dst, "slot_00", "progress.sav")) == "new slot_00" && !Directory.Exists(Path.Combine(dst, "slot_02"))
                && File.ReadAllText(Path.Combine(dst, "account.sav")) == "new account" && File.ReadAllText(Path.Combine(dst, "keep.txt")) == "not a save file"
                && done.Backup != null && Tree(done.Backup) == before && !Directory.EnumerateDirectories(folder).Any(d => Path.GetFileName(d).StartsWith('.')),
                "The copy, once nothing fails: the source's slots in place of the target's, its other files kept, the backup whole.");
        // (a copy cut short between its two renames, the PC off: the next copy finds the target aside and puts it back first)
        var aside = Path.Combine(folder, ".dst.hookshot-old");
        Directory.Move(dst, aside);
        Directory.CreateDirectory(Path.Combine(folder, ".dst.hookshot-staging"));
        Saves.Copy(src, Path.Combine(folder, "dst"), backups, "import", "x", running: () => Array.Empty<string>(), now: () => when);
        Require(Directory.Exists(dst) && !Directory.Exists(aside) && File.Exists(Path.Combine(dst, "keep.txt")), "A copy cut short is put right by the next.");
    }
}
