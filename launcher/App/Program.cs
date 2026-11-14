using Avalonia;
using HookshotLauncher.Core;

namespace HookshotLauncher;

static class Program
{
    /// The start's request (CommandLine.cs)
    public static StartRequest Start { get; private set; } = StartRequest.Parse(Array.Empty<string>());
    /// The arguments as given, for the copy started after Install
    public static IReadOnlyList<string> Args { get; private set; } = Array.Empty<string>();
    /// This launcher's file and kind (installed, portable), and its home
    public static LauncherLayout Layout { get; private set; } = new(Platforms.Current, null, LauncherKind.Plain);
    public static LauncherHome Home { get; private set; } = LauncherHome.Resolve(Platforms.Current);
    /// --uninstall: the window asks, then takes the installed launcher away (Installer)
    public static bool Uninstalling { get; private set; }
    /// What the start put right of an update cut short (SelfUpdate.Recover), for the home to say; null: nothing
    public static string? Recovered { get; private set; }

    static InstanceLock? hold;

    [STAThread]
    public static int Main(string[] args)
    {
        // (the launcher's own update: a new launcher answers --self-check before it is put in place; --rollback puts back the one the
        // last update replaced. SelfUpdate.cs)
        if (args is [SelfUpdate.CheckArgument])
        {
            Console.WriteLine(SelfUpdate.CheckLine(SelfUpdate.OwnTag()));
            return 0;
        }
        var platform = Platforms.Current;
        // (started from the .old or .new an update cut short left, its own file gone: that file is put back and started instead)
        if (SelfUpdate.CurrentFile(platform) is { } file && SelfUpdate.LeftoverOf(file) is { } own && !File.Exists(own))
        {
            try
            {
                SelfUpdate.Recover(own);
                if (File.Exists(own))
                {
                    WindowsInstall.Start(own, args);
                    return 0;
                }
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.ComponentModel.Win32Exception) { }
        }
        if (args is [SelfUpdate.RollbackArgument]) return Rollback();
        Args = args;
        Layout = LauncherLayout.Current(platform);
        Home = LauncherHome.Resolve(platform, null, Layout);
        Start = StartRequest.Parse(args);
        if (Start.Kind == StartKind.Play) return PlayWithoutWindow(Start);
        Uninstalling = platform == Platform.Windows && Start.Ignored.Contains(Installer.UninstallArgument);

        // (one launcher per home: a second start brings the first one's window forward and ends)
        if (!TakeLock())
        {
            if (Uninstalling) WindowsInstall.Tell("The Hookshot Launcher is open. Close it, then uninstall it.");
            else
            {
                WindowsInstall.LetOthersForward();
                InstanceLock.Poke(Home.Root);
                Console.Error.WriteLine("Hookshot: the launcher is already open; its window was brought forward.");
            }
            return 0;
        }
        if (platform == Platform.Windows && !Uninstalling && Start.Ignored.Contains(Installer.InstallArgument)) return InstallNow();
        if (Layout.File is { } current)
        {
            try { Recovered = SelfUpdate.Recover(current); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        }
        // (an installed launcher's Apps & features entry follows its own updates; after one, its Start menu shortcut and the game's
        // shortcuts are made again, so none is left pointing at the program the update moved aside: Installer.Refresh)
        if (OperatingSystem.IsWindows() && Layout.Kind == LauncherKind.Installed && SelfUpdate.OwnTag() != "dev")
        {
            try
            {
                var registry = new UserRegistry();
                if (Installer.IsRegistered(registry) && Installer.Refresh(InstallPlaces.Of(), SelfUpdate.OwnTag(), registry, new ShellShortcuts()))
                    WindowsShortcuts.Refresh(LauncherService.LauncherPath);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.Security.SecurityException
                                          or System.ComponentModel.Win32Exception or InvalidOperationException) { }
        }
        try { return BuildAvaloniaApp().StartWithClassicDesktopLifetime(args); }
        finally { ReleaseLock(); }
    }

    static bool TakeLock()
    {
        try { hold = InstanceLock.TryAcquire(Home.Root, Layout.Platform); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { hold = null; return true; }   // (a home it cannot write: the window says so later)
        return hold != null;
    }

    /// The home let go (before another launcher is started on it: after an update, after Install)
    public static void ReleaseLock()
    {
        hold?.Dispose();
        hold = null;
    }

    /// "Run portable": the "portable" file beside the program, and the home beside it from now on. False when that home is held
    /// by another launcher already (it is poked)
    public static bool BecomePortable()
    {
        var file = Layout.File ?? throw new InvalidOperationException("This launcher was not started from its own file.");
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(file)!, LauncherLayout.PortableMarker),
                          "This file makes the Hookshot Launcher beside it portable: its data stays in the HookshotLauncher-data folder here.\r\n");
        ReleaseLock();
        Layout = LauncherLayout.Current(Layout.Platform);
        Home = LauncherHome.Resolve(Layout.Platform, null, Layout);
        if (TakeLock()) return true;
        InstanceLock.Poke(Home.Root);
        return false;
    }

    /// "Install" (or --install): this program installed (Installer), then the installed copy started with the same arguments
    public static string Install()
    {
        if (!OperatingSystem.IsWindows()) throw new PlatformNotSupportedException("Only the Windows launcher installs itself.");
        var file = Layout.File ?? throw new InvalidOperationException("This launcher was not started from its own file.");
        var at = InstallPlaces.Of();
        var installed = Installer.Install(file, SelfUpdate.OwnTag(), at, new UserRegistry(), new ShellShortcuts());
        ReleaseLock();
        WindowsInstall.Start(installed, Args.Where(a => a != Installer.InstallArgument));
        return installed;
    }

    static int InstallNow()
    {
        try
        {
            Install();
            return 0;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidOperationException or System.ComponentModel.Win32Exception
                                      or System.Security.SecurityException)
        {
            WindowsInstall.Tell("The launcher could not be installed: " + e.Message);
            return 1;
        }
    }

    public static AppBuilder BuildAvaloniaApp() => AppBuilder.Configure<App>().UsePlatformDetect()
        .UseWaylandWithFallback()   // (native Wayland when there is a compositor: through XWayland, a scaled desktop draws the window blurry)
        // (the window's app_id and WM_CLASS: the name of the launcher's .desktop entries, so that a taskbar or dock shows their icon)
        .With(new WaylandPlatformOptions { AppId = Shortcuts.LauncherEntryName })
        .With(new X11PlatformOptions { WmClass = Shortcuts.LauncherEntryName })
        .LogToTrace();

    static int Rollback()
    {
        var platform = Platforms.Current;
        if (SelfUpdate.CurrentFile(platform) is not { } current)
        {
            Console.Error.WriteLine("Hookshot: --rollback works from the launcher's own file (its .exe, or the AppImage).");
            return 1;
        }
        try
        {
            if (!SelfUpdate.Rollback(current, platform))
            {
                Console.Error.WriteLine("Hookshot: no earlier launcher was kept beside " + current + ".");
                return 1;
            }
            Console.WriteLine("Hookshot: the earlier launcher is back in place. Start it again.");
            return 0;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine("Hookshot: the earlier launcher could not be put back: " + e.Message);
            return 1;
        }
    }

    /// --play [folder]: that build's game, else the default build's, with no window
    static int PlayWithoutWindow(StartRequest start)
    {
        try
        {
            var service = LauncherService.Open();
            var folder = start.Folder ?? service.Registry.Default?.Folder;
            if (folder == null || !GameFolder.IsBuilt(folder, service.Platform))
            {
                Console.Error.WriteLine("Hookshot: no built game to start. Open the launcher and build one, or pass its folder.");
                return 1;
            }
            service.PlayFolder(Path.GetFullPath(folder));
            return 0;
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.ComponentModel.Win32Exception)
        {
            Console.Error.WriteLine("Hookshot: the game could not start: " + e.Message);
            return 1;
        }
    }
}
