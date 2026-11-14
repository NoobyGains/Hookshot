using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using HookshotLauncher.Core;

namespace HookshotLauncher;

/// The two small windows of the Windows launcher's own installer (Installer): the first start's "Install or Run portable", and
/// --uninstall's. Made in code, in the launcher's look (App.axaml's brushes and button classes)
public static class SetupWindows
{
    static IBrush Brush(string key) =>
        Application.Current?.TryFindResource(key, out var b) == true && b is IBrush brush ? brush : Brushes.Gray;

    static TextBlock Text(string text, double size = 13, string ink = "InkSoft", FontWeight weight = FontWeight.Normal) => new()
    {
        Text = text, FontSize = size, Foreground = Brush(ink), FontWeight = weight, TextWrapping = TextWrapping.Wrap,
    };

    static Button Button(string text, string? classes, Action click)
    {
        var b = new Button { Content = text, MinWidth = 120, HorizontalContentAlignment = HorizontalAlignment.Center };
        if (classes != null) b.Classes.Add(classes);
        b.Click += (_, _) => click();
        return b;
    }

    static Window Frame(StackPanel body) => new()
    {
        Title = Installer.DisplayName,
        Width = 520,
        SizeToContent = SizeToContent.Height,
        CanResize = false,
        WindowStartupLocation = WindowStartupLocation.CenterScreen,
        Background = Brush("Page"),
        Content = new Border { Padding = new Thickness(28, 24), Child = body },
    };

    static StackPanel Buttons(params Control[] buttons)
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 12, 0, 0) };
        foreach (var b in buttons) row.Children.Add(b);
        return row;
    }

    /// The first start of the Windows download: Install (then the installed copy starts, and this one ends) or Run portable (the
    /// "portable" file beside it, then the launcher's window: opened)
    public static Window Offer(IClassicDesktopStyleApplicationLifetime desktop, Action opened)
    {
        var folder = LauncherLayout.InstallFolder(Environment.GetEnvironmentVariable);
        var problem = Text("", 12, "Bad");
        problem.IsVisible = false;
        var body = new StackPanel { Spacing = 10 };
        Window window = Frame(body);
        void Failed(Exception e)
        {
            problem.Text = e.Message;
            problem.IsVisible = true;
        }
        body.Children.Add(Text(Tr.T("Install the Hookshot Launcher?"), 20, "Ink", FontWeight.SemiBold));
        body.Children.Add(Text(Tr.F("Install puts it in {0}, with a Start menu shortcut and an entry in Apps & features to uninstall it. " +
                                    "It is for you alone: no administrator rights are needed.", folder)));
        body.Children.Add(Text(Tr.T("Run portable keeps it where it is: everything it saves goes in a HookshotLauncher-data folder beside it, and " +
                                    "nothing is written anywhere else (no shortcut, no registry). A file named portable beside it remembers the choice."), 12, "InkFaintText"));
        body.Children.Add(problem);
        body.Children.Add(Buttons(
            Button(Tr.T("Run portable"), null, () =>
            {
                try
                {
                    if (!Program.BecomePortable())
                    {
                        desktop.Shutdown();
                        return;
                    }
                    opened();
                    window.Close();
                }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidOperationException) { Failed(e); }
            }),
            Button(Tr.T("Install"), "primary", () =>
            {
                try
                {
                    Program.Install();
                    desktop.Shutdown();
                }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidOperationException or PlatformNotSupportedException
                                              or System.ComponentModel.Win32Exception or System.Security.SecurityException) { Failed(e); }
            })));
        return window;
    }

    /// --uninstall: what goes and what stays, the data kept unless the box is ticked; then the program is deleted once this closes
    public static Window Uninstall(IClassicDesktopStyleApplicationLifetime desktop)
    {
        var at = InstallPlaces.Of();
        var body = new StackPanel { Spacing = 10 };
        var window = Frame(body);
        var data = new CheckBox
        {
            Content = Text(Tr.F("Also delete the launcher's data in {0}: its list of builds, its settings, the downloaded builder tools and the " +
                                "build files. Builds inside it are kept.", at.Home), 12),
        };
        data.Classes.Add("tick");
        var heading = Text(Tr.T("Uninstall the Hookshot Launcher?"), 20, "Ink", FontWeight.SemiBold);
        var about = Text(Tr.T("This removes the launcher, its Start menu shortcut, the Hookshot shortcuts it made, and its entry in Apps & features. " +
                              "Your builds (the game folders) and your saves stay where they are."));
        var problem = Text("", 12, "Bad");
        problem.IsVisible = false;
        Button? go = null, cancel = null;
        go = Button(Tr.T("Uninstall"), "bad", () =>
        {
            try
            {
                var keep = Keep(at);
                var removed = OperatingSystem.IsWindows()
                    ? Installer.Uninstall(at, new UserRegistry(), new ShellShortcuts(), data.IsChecked == true, keep, Environment.ProcessPath)
                    : throw new PlatformNotSupportedException("Only the Windows launcher uninstalls itself.");
                WindowsShortcuts.RemoveGame();
                Program.ReleaseLock();
                if (removed.Pending != null) WindowsInstall.DeleteAfterExit(removed.Pending);
                heading.Text = Tr.T("The Hookshot Launcher is uninstalled");
                about.Text = removed.Kept.Count > 0
                    ? Tr.F("Kept, because they hold builds or saves: {0}.", string.Join(", ", removed.Kept))
                    : data.IsChecked == true ? Tr.T("Its data is deleted too. Your builds and saves are where they were.") : Tr.F("Its data is still in {0}.", at.Home);
                data.IsVisible = false;
                problem.IsVisible = false;
                go!.IsVisible = false;
                cancel!.Content = Tr.T("Close");
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or PlatformNotSupportedException or System.Security.SecurityException
                                          or System.ComponentModel.Win32Exception)
            {
                problem.Text = Tr.F("The launcher could not be uninstalled: {0}", e.Message);
                problem.IsVisible = true;
            }
        });
        cancel = Button(Tr.T("Cancel"), null, () => desktop.Shutdown());
        body.Children.Add(heading);
        body.Children.Add(about);
        body.Children.Add(data);
        body.Children.Add(problem);
        body.Children.Add(Buttons(cancel, go));
        return window;
    }

    /// What deleting the data must leave: every build's game folder, the folder new builds go in, and the save backups
    static List<string> Keep(InstallPlaces at)
    {
        var home = new LauncherHome(at.Home);
        var keep = BuildRegistry.Load(home.Builds).Builds.Select(b => b.Folder).ToList();
        var settings = LauncherSettings.Load(home.Settings);
        keep.Add(settings.BuildsFolderOrDefault());
        keep.Add(SaveEnvironment.Current().BackupRoot);
        return keep;
    }
}
