using System.Text;

namespace LongshotLauncher.Core;

/// The shortcuts a build's Ready screen makes: on the desktop and in the Start menu (Windows) or the applications menu (Linux).
/// They start the launcher with --play (the default build's game, so they follow "Play starts this version" and an update's
/// new folder), or --play &lt;folder&gt; for one build. Linux writes freedesktop .desktop files here; Windows' .lnk files are
/// written by the window (the shell makes them)
public static class Shortcuts
{
    public const string Name = "Longshot";

    /// A .desktop entry that starts launcher --play [folder]
    public static string DesktopEntry(string launcher, string? folder, string? icon)
    {
        var sb = new StringBuilder();
        sb.Append("[Desktop Entry]\nType=Application\nName=").Append(Name).Append('\n');
        sb.Append("Comment=Longshot\n");
        sb.Append("Exec=").Append(Quote(launcher)).Append(" --play");
        if (folder != null) sb.Append(' ').Append(Quote(folder));
        sb.Append('\n');
        if (folder != null) sb.Append("Path=").Append(folder).Append('\n');
        if (icon != null) sb.Append("Icon=").Append(icon).Append('\n');
        sb.Append("Terminal=false\nCategories=Game;\n");
        return sb.ToString();
    }

    /// An Exec argument quoted as the desktop entry specification says: in double quotes, with " ` $ \ escaped (and % doubled).
    /// The file's own string escapes are read before the quoting, so each of those backslashes is written twice (a literal \ is
    /// four): GLib does not start an Exec line holding \" or \$
    public static string Quote(string arg)
    {
        var sb = new StringBuilder("\"");
        foreach (var c in arg)
        {
            if (c is '"' or '`' or '$') sb.Append(@"\\").Append(c);
            else if (c == '\\') sb.Append(@"\\\\");
            else if (c == '%') sb.Append("%%");
            else sb.Append(c);
        }
        return sb.Append('"').ToString();
    }

    /// Where the two Linux shortcuts go: ~/Desktop/longshot.desktop and $XDG_DATA_HOME/applications/longshot.desktop
    public static (string Desktop, string Menu) LinuxPaths(Func<string, string?>? getenv = null)
    {
        getenv ??= Environment.GetEnvironmentVariable;
        var home = LauncherHome.Home(getenv);
        var data = getenv("XDG_DATA_HOME") is { Length: > 0 } x ? x : Path.Combine(home, ".local", "share");
        return (Path.Combine(home, "Desktop", "longshot.desktop"), Path.Combine(data, "applications", "longshot.desktop"));
    }

    /// The Linux shortcuts made (or removed) as the two ticks say; the desktop one only when there is a Desktop folder
    public static void WriteLinux(string launcher, string? folder, bool desktop, bool menu, string? icon = null, Func<string, string?>? getenv = null)
    {
        var (d, m) = LinuxPaths(getenv);
        var text = DesktopEntry(launcher, folder, icon);
        foreach (var (path, want) in new[] { (d, desktop), (m, menu) })
        {
            if (!want)
            {
                if (File.Exists(path)) File.Delete(path);
                continue;
            }
            if (path == d && !Directory.Exists(Path.GetDirectoryName(path))) continue;
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            AtomicFile.Write(path, text);
            if (!OperatingSystem.IsWindows())
                File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute | UnixFileMode.GroupRead | UnixFileMode.OtherRead);
        }
    }

    // ---- the launcher itself in the Linux applications menu (Settings, "Add to applications menu") ----

    /// (also the window's Wayland app_id and X11 WM_CLASS, Program, and the entries' StartupWMClass: a taskbar finds the entry's icon)
    public const string LauncherEntryName = "longshot-launcher";

    /// Where the launcher's own menu entry and its icon go: $XDG_DATA_HOME/applications/longshot-launcher.desktop and
    /// $XDG_DATA_HOME/icons/hicolor/512x512/apps/longshot-launcher.png
    public static (string Entry, string Icon) LauncherMenuPaths(Func<string, string?>? getenv = null)
    {
        getenv ??= Environment.GetEnvironmentVariable;
        var data = getenv("XDG_DATA_HOME") is { Length: > 0 } x ? x : Path.Combine(LauncherHome.Home(getenv), ".local", "share");
        return (Path.Combine(data, "applications", LauncherEntryName + ".desktop"),
                Path.Combine(data, "icons", "hicolor", "512x512", "apps", LauncherEntryName + ".png"));
    }

    /// The launcher's own .desktop entry: the AppImage where it is now, with no arguments (the window)
    public static string LauncherEntry(string appImage, string icon) =>
        "[Desktop Entry]\nType=Application\nName=Longshot Launcher\n" +
        "Comment=Install Longshot's builder, build the game from your own copy, and play\n" +
        "Exec=" + Quote(appImage) + "\n" +
        "TryExec=" + appImage + "\n" +
        "Icon=" + icon + "\nTerminal=false\nCategories=Game;\nStartupWMClass=" + LauncherEntryName + "\n";

    /// Whether the launcher is in the applications menu, and the AppImage its entry starts (null when it is not there)
    public static string? LauncherInMenu(Func<string, string?>? getenv = null)
    {
        var (entry, _) = LauncherMenuPaths(getenv);
        if (!File.Exists(entry)) return null;
        return File.ReadAllLines(entry).FirstOrDefault(l => l.StartsWith("TryExec=", StringComparison.Ordinal))?["TryExec=".Length..];
    }

    /// The launcher added to the applications menu (its entry and its icon, png), pointing at appImage; again after it moved
    public static void AddLauncherToMenu(string appImage, byte[] png, Func<string, string?>? getenv = null)
    {
        var (entry, icon) = LauncherMenuPaths(getenv);
        AtomicFile.Write(icon, png);
        AtomicFile.Write(entry, LauncherEntry(appImage, icon));
        if (!OperatingSystem.IsWindows())
            File.SetUnixFileMode(entry, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute | UnixFileMode.GroupRead | UnixFileMode.OtherRead);
    }

    public static void RemoveLauncherFromMenu(Func<string, string?>? getenv = null)
    {
        var (entry, icon) = LauncherMenuPaths(getenv);
        File.Delete(entry);
        File.Delete(icon);
    }
}
