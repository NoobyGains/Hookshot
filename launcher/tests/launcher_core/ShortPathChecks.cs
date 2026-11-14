using System.Runtime.InteropServices;
using System.Text;
using HookshotLauncher.Core;

/// A launcher started from, or given, a folder by its 8.3 short name (Windows: C:\Users\RUNNER~1\..., GitHub's runners' TEMP; any
/// long folder name on a volume that keeps short names) is the same launcher as from the long name: its layout and its home, and
/// above all its refusals to delete a folder that holds another build, which compare paths. Skipped where the volume keeps no
/// short names (and off Windows)
static partial class Program
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true, EntryPoint = "GetShortPathNameW")]
    static extern uint GetShortPathName(string longPath, StringBuilder shortPath, uint size);

    static string? ShortName(string path)
    {
        var buffer = new StringBuilder(1024);
        var n = GetShortPathName(path, buffer, (uint)buffer.Capacity);
        return n == 0 || n >= buffer.Capacity ? null : buffer.ToString();
    }

    static void ShortPathChecks()
    {
        if (!OperatingSystem.IsWindows()) return;
        var root = Folder("short paths");
        var longRoot = Path.Combine(root, "A folder with a long name");
        Directory.CreateDirectory(longRoot);
        var shortRoot = ShortName(longRoot);
        if (shortRoot == null || string.Equals(shortRoot, longRoot, StringComparison.OrdinalIgnoreCase))
        {
            Console.WriteLine("short paths: this volume keeps no 8.3 names, so they were not checked here");
            return;
        }
        Func<string, string?> env = k => k switch
        {
            "LOCALAPPDATA" => Path.Combine(longRoot, "Local"), "APPDATA" => Path.Combine(longRoot, "Roaming"),
            "HOME" or "USERPROFILE" => Path.Combine(longRoot, "Home"), _ => null,
        };

        // (a portable launcher started by its short name: portable, its data in the one folder beside it)
        var usb = Path.Combine(longRoot, "USB stick");
        Directory.CreateDirectory(usb);
        File.WriteAllText(Path.Combine(usb, "HookshotLauncher.exe"), "MZ launcher");
        File.WriteAllText(Path.Combine(usb, LauncherLayout.PortableMarker), "");
        var fromShort = LauncherLayout.Of(Platform.Windows, Path.Combine(shortRoot, "USB stick", "HookshotLauncher.exe"), env);
        Require(fromShort.Kind == LauncherKind.Portable
                && LauncherHome.Resolve(Platform.Windows, env, fromShort).Root == Path.Combine(usb, LauncherLayout.PortableData),
                "A portable launcher started by its folder's short name keeps its data in the same folder as by the long name.");

        // (the installed launcher, started by the short name of its folder, is the installed one)
        var installed = LauncherLayout.InstalledExe(env);
        Directory.CreateDirectory(Path.GetDirectoryName(installed)!);
        File.WriteAllText(installed, "MZ launcher");
        var installedShort = Path.Combine(ShortName(Path.GetDirectoryName(installed)!)!, LauncherLayout.ProgramName);
        Require(LauncherLayout.Of(Platform.Windows, installedShort, env).Kind == LauncherKind.Installed,
                "The installed launcher started by its folder's short name is the installed one.");

        // (Delete never takes a folder that holds a kept build, whichever form of the name either is given in)
        var outer = Path.Combine(longRoot, "Games", "Hookshot build");
        var inner = Path.Combine(outer, "v2.3.0");
        foreach (var f in new[] { outer, inner })
        {
            Directory.CreateDirectory(Path.Combine(f, "bin"));
            File.WriteAllText(Path.Combine(f, GameFolder.StampName), "version=v2.3.0\n");
        }
        var outerShort = ShortName(outer)!;
        var innerShort = ShortName(inner)!;
        Throws<IOException>(() => BuildRegistry.DeleteFolder(outer, Platform.Windows, new[] { innerShort }, env),
                            "A folder holding a kept build (named short) was deleted by its long name.");
        Throws<IOException>(() => BuildRegistry.DeleteFolder(outerShort, Platform.Windows, new[] { inner }, env),
                            "A folder holding a kept build (named long) was deleted by its short name.");
        Require(Directory.Exists(inner) && Saves.Real(outerShort) == Saves.Real(outer) && Saves.Inside(Saves.Real(outer), Saves.Real(innerShort)),
                "Short and long names of one folder are one folder to the saves' checks too.");
    }
}
