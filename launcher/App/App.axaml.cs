using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using LongshotLauncher.Core;
using LongshotLauncher.ViewModels;

namespace LongshotLauncher;

public sealed class App : Application
{
    IDisposable? pokes;

    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.ShutdownMode = ShutdownMode.OnLastWindowClose;
            Tr.Use(LauncherSettings.Load(Program.Home.Settings).UiLanguageOr(Controls.SystemLanguage.Name()));
            // (--uninstall: its own small window; the Windows download's first start: Install or Run portable, then the launcher)
            if (Program.Uninstalling) desktop.MainWindow = SetupWindows.Uninstall(desktop);
            else if (Program.Layout.OffersInstall(SelfUpdate.OwnTag(), Environment.GetEnvironmentVariable))
                desktop.MainWindow = SetupWindows.Offer(desktop, () => OpenMain(desktop, show: true));
            else OpenMain(desktop, show: false);
            desktop.Exit += (_, _) => pokes?.Dispose();
        }
        base.OnFrameworkInitializationCompleted();
    }

    /// The launcher's window, on Program.Home. show: it is opened after the start (after "Run portable"), not by the start itself
    void OpenMain(IClassicDesktopStyleApplicationLifetime desktop, bool show)
    {
        var service = LauncherService.Open();
        var main = new MainViewModel(service, Program.Start);
        if (Program.Recovered is { } recovered) main.Home.Notice = main.Home.Notice is { } n ? n + "\n" + recovered : recovered;
        // (Windows: the saves each build kept in its own folder, brought into the one every build shares now; said once)
        if (LauncherService.GatherSaid(service.GatherSaves()) is { } said)
        {
            main.Home.Notice = main.Home.Notice is { } n ? n + "\n" + said : said;
            main.Home.Refresh();
        }
        var window = new MainWindow { DataContext = main };
        desktop.MainWindow = window;
        if (show) window.Show();
        // (another start of the launcher on this home pokes it: the window comes forward)
        try
        {
            pokes = InstanceLock.Watch(service.Home.Root, () => Ui.Post(() =>
            {
                if (window.WindowState == WindowState.Minimized) window.WindowState = WindowState.Normal;
                window.Activate();
            }));
        }
        catch (Exception e) when (e is IOException or ArgumentException or PlatformNotSupportedException) { }
        // (the update check: at start unless turned off in the settings or offline; with nothing built it is needed to know what to
        // build)
        var offline = Environment.GetEnvironmentVariable("LONGSHOT_LAUNCHER_OFFLINE") == "1";
        if (!offline && (service.Settings.CheckUpdates || service.Registry.Builds.Count == 0))
            _ = main.Home.CheckReleasesAsync();
        else service.Checked = true;
    }
}
