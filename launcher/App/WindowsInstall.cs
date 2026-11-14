using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using LongshotLauncher.Core;
using Microsoft.Win32;

namespace LongshotLauncher;

/// Core's IUserRegistry over the real HKEY_CURRENT_USER (Windows only; the tests use a dictionary)
[SupportedOSPlatform("windows")]
public sealed class UserRegistry : IUserRegistry
{
    public IReadOnlyDictionary<string, object>? Read(string key)
    {
        using var k = Registry.CurrentUser.OpenSubKey(key);
        if (k == null) return null;
        return k.GetValueNames().ToDictionary(n => n, n => k.GetValue(n) ?? "");
    }

    public void Write(string key, IReadOnlyDictionary<string, object> values)
    {
        using var k = Registry.CurrentUser.CreateSubKey(key, writable: true);
        foreach (var (name, value) in values)
        {
            if (value is int dword) k.SetValue(name, dword, RegistryValueKind.DWord);
            else k.SetValue(name, value.ToString() ?? "", RegistryValueKind.String);
        }
    }

    public void Delete(string key) => Registry.CurrentUser.DeleteSubKeyTree(key, throwOnMissingSubKey: false);
}

/// Core's IShortcutMaker through the shell's own WScript.Shell, as the Ready screen's shortcuts (WindowsShortcuts)
public sealed class ShellShortcuts : IShortcutMaker
{
    public void Make(string link, string target, string? arguments, string icon, string description) =>
        WindowsShortcuts.Run(new[] { WindowsShortcuts.Line(link, target, arguments ?? "", icon, description) });

    public void Remove(string link)
    {
        if (File.Exists(link)) File.Delete(link);
    }
}

/// What the Windows install and uninstall do beyond Core's Installer: start the installed copy, delete the running program once
/// it has closed, and the message boxes of a start that has no window
public static class WindowsInstall
{
    /// The program started (the installed one after Install, the new one after an update), with these arguments
    public static void Start(string program, IEnumerable<string> args)
    {
        var start = new ProcessStartInfo(program) { UseShellExecute = false, WorkingDirectory = Path.GetDirectoryName(program)! };
        foreach (var a in args) start.ArgumentList.Add(a);
        using var _ = Process.Start(start);
    }

    /// The running program deleted once this process has ended (Windows does not let a running program delete itself): a hidden
    /// PowerShell waits for this process, deletes the file, then its folder if that is empty
    public static void DeleteAfterExit(string program)
    {
        if (!OperatingSystem.IsWindows()) return;
        var folder = Path.GetDirectoryName(program)!;
        var script = $"Wait-Process -Id {Environment.ProcessId} -ErrorAction SilentlyContinue; " +
                     $"for ($i = 0; $i -lt 20 -and (Test-Path -LiteralPath {WindowsShortcuts.Quote(program)}); $i++) " +
                     $"{{ Remove-Item -LiteralPath {WindowsShortcuts.Quote(program)} -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 250 }}; " +
                     $"if (-not (Get-ChildItem -LiteralPath {WindowsShortcuts.Quote(folder)} -Force)) {{ Remove-Item -LiteralPath {WindowsShortcuts.Quote(folder)} }}";
        var si = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (var a in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", script })
            si.ArgumentList.Add(a);
        using var _ = Process.Start(si);
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int MessageBoxW(IntPtr owner, string text, string caption, uint type);

    [DllImport("user32.dll")]
    static extern bool AllowSetForegroundWindow(int processId);

    /// A message with no window of the launcher's own (a second start, --uninstall while it is open); stderr elsewhere
    public static void Tell(string text)
    {
        if (OperatingSystem.IsWindows()) MessageBoxW(IntPtr.Zero, text, Installer.DisplayName, 0x40 /* MB_ICONINFORMATION */);
        else Console.Error.WriteLine("Longshot: " + text);
    }

    /// Lets the launcher that is already open take the foreground when this start pokes it (Windows keeps it from otherwise)
    public static void LetOthersForward()
    {
        if (OperatingSystem.IsWindows()) AllowSetForegroundWindow(-1 /* ASFW_ANY */);
    }
}
