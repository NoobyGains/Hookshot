using System.Diagnostics;

namespace LongshotLauncher;

/// The Ready screen's Windows shortcuts (Desktop, Start menu): Longshot.lnk starting the launcher with --play, made by the shell's
/// own WScript.Shell through PowerShell (the launcher has no COM interop of its own), or removed when unticked.
/// (Not yet run on Windows: the launcher's first builds were tried on Linux.)
public static class WindowsShortcuts
{
    public static string DesktopLink => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Longshot.lnk");
    public static string StartLink => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Longshot.lnk");

    /// A PowerShell single-quoted string: each quote doubled, the typographic ones too (PowerShell ends a string on ‘ ’ ‚ ‛ as on ',
    /// and a folder named O’Brien would end it early)
    public static string Quote(string s)
    {
        var sb = new System.Text.StringBuilder("'");
        foreach (var c in s)
        {
            if (c is '\'' or '‘' or '’' or '‚' or '‛') sb.Append(c);
            sb.Append(c);
        }
        return sb.Append('\'').ToString();
    }

    /// One shortcut's line of the script
    public static string Line(string link, string target, string arguments, string icon, string description) =>
        $"$l = $s.CreateShortcut({Quote(link)}); $l.TargetPath = {Quote(target)}; $l.Arguments = {Quote(arguments)}; " +
        $"$l.WorkingDirectory = {Quote(Path.GetDirectoryName(target) ?? "")}; $l.IconLocation = {Quote(icon)}; $l.Description = {Quote(description)}; $l.Save()";

    /// The shortcuts' lines run in one hidden PowerShell
    public static void Run(IReadOnlyList<string> lines)
    {
        if (!OperatingSystem.IsWindows() || lines.Count == 0) return;
        var script = string.Join("; ", new[] { "$s = New-Object -ComObject WScript.Shell" }.Concat(lines));
        var si = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (var a in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script }) si.ArgumentList.Add(a);
        using var p = Process.Start(si);
        p?.WaitForExit(15000);
    }

    public static void Write(string launcher, bool desktop, bool start)
    {
        if (!OperatingSystem.IsWindows()) return;
        var lines = new List<string>();
        foreach (var (link, want) in new[] { (DesktopLink, desktop), (StartLink, start) })
        {
            if (!want)
            {
                if (File.Exists(link)) File.Delete(link);
                continue;
            }
            Directory.CreateDirectory(Path.GetDirectoryName(link)!);
            lines.Add(Line(link, launcher, "--play", launcher, "Longshot"));
        }
        Run(lines);
    }

    /// The game's shortcuts that are there made again, starting launcher (after the launcher's own update: Installer.Refresh)
    public static void Refresh(string launcher) => Write(launcher, File.Exists(DesktopLink), File.Exists(StartLink));

    /// The game's shortcuts taken away with the launcher they start (its uninstall)
    public static void RemoveGame()
    {
        if (!OperatingSystem.IsWindows()) return;
        foreach (var link in new[] { DesktopLink, StartLink })
            if (File.Exists(link)) File.Delete(link);
    }
}
