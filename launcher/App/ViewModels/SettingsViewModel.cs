using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

/// The launcher's settings: the channel new builds start on, where builds go, the build files, the update check. Each version
/// keeps its own build settings (step 2)
public sealed class SettingsViewModel : ViewModelBase
{
    readonly LauncherSettings s;
    long? workBytes;
    bool measuring;

    public sealed class ChannelOption(SettingsViewModel owner, string id, string name, string about, string? version) : ViewModelBase
    {
        public string Id => id;
        public string Name => Tr.T(name);
        public string About => Tr.T(about);
        public string Version => version == null ? Tr.T("Not checked yet") : Versions.Shown(version);

        public bool IsPicked
        {
            get => owner.Channel == id;
            set
            {
                if (value) owner.Channel = id;
            }
        }

        public void Changed() => Raise(nameof(IsPicked));
    }

    /// One of the launcher's own channels (where it updates itself from)
    public sealed class LauncherChannelOption(SettingsViewModel owner, string id, string name) : ViewModelBase
    {
        public string Id => id;
        public string Name => Tr.T(name);

        public bool IsPicked
        {
            get => owner.LauncherChannel == id;
            set
            {
                if (value) owner.LauncherChannel = id;
            }
        }

        public void Changed() => Raise(nameof(IsPicked));
    }

    public SettingsViewModel(MainViewModel main)
    {
        Main = main;
        s = main.Service.Settings;
        Channels = ChannelPickerViewModel.All.Select(c => new ChannelOption(this, c.Id, c.Name, c.About, main.Service.NewestOf(c.Id))).ToList();
        LauncherChannels = ChannelPickerViewModel.All.Select(c => new LauncherChannelOption(this, c.Id, c.Name)).ToList();
        DoneCommand = new Command(Done);
        ChangeBuildsCommand = new Command(() => _ = ChangeBuildsAsync());
        ChangeWorkCommand = new Command(() => _ = ChangeWorkAsync());
        DefaultWorkCommand = new Command(() => { s.Work = null; Save(); RaiseAll(nameof(Work)); MeasureWork(); });
        FreeSpaceCommand = new BusyCommand(FreeSpaceAsync, () => workBytes > 0 && !measuring,
                                           e => Main.ShowToast(Tr.F("The build files could not all be deleted: {0}", e.Message)));
        ReleaseNotesCommand = new Command(() => Main.Host?.Open(Product.Hookshot.Releases));
        AddToMenuCommand = new Command(AddToMenu, () => Program.Layout.File != null);
        RemoveFromMenuCommand = new Command(RemoveFromMenu);
        Languages = new[] { new UiLanguageChoice(null, Tr.T("System language")) }
            .Concat(Tr.All.Select(l => new UiLanguageChoice(l.Code, l.Name))).ToList();
        MeasureWork();
    }

    // ---- the launcher's language: the system's until one is picked; a pick changes the window at once ----

    public sealed record UiLanguageChoice(string? Code, string Name)
    {
        public override string ToString() => Name;
    }

    public IReadOnlyList<UiLanguageChoice> Languages { get; }

    public UiLanguageChoice Language
    {
        get => Languages.FirstOrDefault(l => l.Code == s.UiLanguage) ?? Languages[0];
        set
        {
            if (value == null || value.Code == s.UiLanguage) return;
            s.UiLanguage = value.Code;
            Save();
            Tr.Use(s.UiLanguageOr(Controls.SystemLanguage.Name()));
        }
    }

    // ---- the launcher itself: how it is kept, and on Linux its entry in the applications menu ----

    /// Where this launcher is and how (installed, portable), under the launcher's channels
    public string LauncherHint => Tr.Sentences(Tr.T("The channel the launcher updates itself from. Its releases are its own, apart from Hookshot's."), Program.Layout.Kind switch
    {
        LauncherKind.Installed => Tr.F("Installed for you in {0}; uninstall it from Apps & features.", ShownPath.Of(Path.GetDirectoryName(Program.Layout.File))),
        LauncherKind.Portable => Tr.F("Portable: everything it keeps is in {0}.", ShownPath.Of(Main.Service.Home.Root)),
        _ => "",
    });

    /// The AppImage's own entry in the applications menu (Linux): added, moved along when the AppImage moved, removed
    public bool ShowMenu => Main.Linux;
    string? MenuTarget => Shortcuts.LauncherInMenu();
    public bool InMenu => MenuTarget != null;
    public string AddToMenuText => MenuTarget == null ? Tr.T("Add to applications menu")
        : MenuTarget != Program.Layout.File ? Tr.T("Point the menu entry here") : Tr.T("Write the menu entry again");
    public string MenuHint => Program.Layout.File == null ? Tr.T("Only the AppImage can be added to the menu.")
        : MenuTarget == null ? Tr.T("Adds Hookshot Launcher to your desktop's applications menu, starting this AppImage where it is now.")
        : MenuTarget != Program.Layout.File ? Tr.F("The menu entry starts {0}, not this AppImage.", ShownPath.Of(MenuTarget))
        : Tr.T("Hookshot Launcher is in the applications menu. Moved the AppImage? Add it again from its new place.");
    public Command AddToMenuCommand { get; }
    public Command RemoveFromMenuCommand { get; }

    void AddToMenu()
    {
        if (Program.Layout.File is not { } appImage) return;
        try
        {
            using var icon = Avalonia.Platform.AssetLoader.Open(new Uri("avares://HookshotLauncher/Assets/hookshot.png"));
            using var bytes = new MemoryStream();
            icon.CopyTo(bytes);
            Shortcuts.AddLauncherToMenu(appImage, bytes.ToArray());
            Main.ShowToast(Tr.T("Hookshot Launcher is in the applications menu."));
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { Main.ShowToast(Tr.F("The menu entry could not be written: {0}", e.Message)); }
        RaiseAll(nameof(InMenu), nameof(AddToMenuText), nameof(MenuHint));
    }

    void RemoveFromMenu()
    {
        try
        {
            Shortcuts.RemoveLauncherFromMenu();
            Main.ShowToast(Tr.T("Hookshot Launcher is out of the applications menu."));
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { Main.ShowToast(Tr.F("The menu entry could not be removed: {0}", e.Message)); }
        RaiseAll(nameof(InMenu), nameof(AddToMenuText), nameof(MenuHint));
    }

    public MainViewModel Main { get; }
    public IReadOnlyList<ChannelOption> Channels { get; }
    public IReadOnlyList<LauncherChannelOption> LauncherChannels { get; }

    /// The channel the launcher updates itself from; a change is checked at once
    public string LauncherChannel
    {
        get => Main.Service.LauncherChannel;
        set
        {
            if (value == Main.Service.LauncherChannel || !Versions.IsChannel(value)) return;
            s.LauncherChannel = value;
            Save();
            foreach (var c in LauncherChannels) c.Changed();
            // (new builds follow the launcher's channel while none was picked for them)
            foreach (var c in Channels) c.Changed();
            Raise(nameof(ChannelHint));
            _ = Main.Home.CheckReleasesAsync();
        }
    }

    void Save()
    {
        try { Main.Service.SaveSettings(); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { Main.ShowToast(Tr.F("The settings could not be saved: {0}", e.Message)); }
    }

    public string Channel
    {
        get => Main.Service.DefaultChannel;
        set
        {
            if (value == s.DefaultChannel || !Versions.IsChannel(value)) return;
            s.DefaultChannel = value;
            Save();
            foreach (var c in Channels) c.Changed();
            Raise(nameof(ChannelHint));
        }
    }

    public string ChannelHint =>
        Tr.Sentences(ChannelPickerViewModel.AboutOf(Main.Service, Channel, ChannelPickerViewModel.All.FirstOrDefault(c => c.Id == Channel).About ?? ""),
                     Tr.T("Builds you have keep their own channel."));

    public string BuildsFolder
    {
        get => ShownPath.Of(Main.Service.BuildsFolder);
        set
        {
            s.BuildsFolder = string.IsNullOrWhiteSpace(value) ? null : ShownPath.Typed(value.Trim());
            Save();
            Raise();
        }
    }

    public string Work
    {
        get => ShownPath.Of(Main.Service.Work);
        set
        {
            s.Work = string.IsNullOrWhiteSpace(value) ? null : ShownPath.Typed(value.Trim());
            Save();
            Raise();
            MeasureWork();
        }
    }

    public string WorkNote => FreeSpaceCommand.IsBusy ? Tr.T("Deleting the build files…")
        : measuring ? Tr.T("Measuring the build files…")
        : workBytes is long b && b > 0 ? Tr.F("{0} kept to make updates quicker.", Durations.Size(b)) : Tr.T("Nothing kept yet.");

    /// The update check that a change of the launcher's channel starts (HomeViewModel.CheckCommand): a spinner beside the channels
    public BusyCommand CheckCommand => Main.Home.CheckCommand;

    public bool CheckUpdates
    {
        get => s.CheckUpdates;
        set
        {
            s.CheckUpdates = value;
            Save();
            Raise();
        }
    }

    public string Version => "Hookshot Launcher " + (Main.Service.OwnTag != "dev" ? Versions.Shown(Main.Service.OwnTag)
        : (typeof(SettingsViewModel).Assembly.GetName().Version?.ToString(3) ?? "1.0.0") + " (dev)");

    // ---- About: where it comes from, and whose work it carries ----

    public string AboutFrom => Tr.F("Based on the Magic Bean team's {0} (commit {1}), written by HumanBean and the Longshot contributors. Releases come from {2}.",
                                    Upstream.Name, Upstream.Short, Main.Service.Releases.Product.Repo);
    public string AboutArt => Tr.T("The turning Hookshot and the shield are renders of fan-made 3D models (the Hookshot by DTStheTDS), not taken from the game. Type: Unbounded, JetBrains Mono and Inter, under the SIL Open Font License. Window: Avalonia (MIT).");
    public string AboutLicence => Tr.T("Free software under the GNU General Public License, version 3 or later. An unofficial fan project, not affiliated with Nintendo.");
    public Command SourceCommand => new(() => Main.Host?.Open(Repository.Page(Main.Service.Releases.Product.Repo)));
    public Command UpstreamCommand => new(() => Main.Host?.Open(Upstream.Url));

    public Command DoneCommand { get; }
    public Command ChangeBuildsCommand { get; }
    public Command ChangeWorkCommand { get; }
    public Command DefaultWorkCommand { get; }
    public BusyCommand FreeSpaceCommand { get; }
    public Command ReleaseNotesCommand { get; }

    void MeasureWork()
    {
        var folder = Main.Service.Work;
        measuring = true;
        Raise(nameof(WorkNote));
        FreeSpaceCommand.Changed();
        Task.Run(() =>
        {
            var bytes = Disk.WorkBytes(folder);
            Ui.Post(() =>
            {
                workBytes = bytes;
                measuring = false;
                Raise(nameof(WorkNote));
                FreeSpaceCommand.Changed();
            });
        });
    }

    /// The build files deleted: the next build or update makes them again. Only what make_game made there (Disk.WorkParts): the
    /// folder may be one the player chose, holding other things. Gigabytes: off the window's thread, the link off meanwhile
    async Task FreeSpaceAsync(BusyCommand busy, CancellationToken cancel)
    {
        var folder = Main.Service.Work;
        var freed = workBytes ?? 0;
        Raise(nameof(WorkNote));
        try
        {
            await Task.Run(() => Disk.FreeWork(folder));
            Main.ShowToast(Tr.F("Freed {0} of build files. The next update makes them again.", Durations.Size(freed)));
        }
        finally
        {
            MeasureWork();
        }
    }

    async Task ChangeBuildsAsync()
    {
        if (Main.Host is not { } host) return;
        if (await host.PickFolderAsync(Tr.T("Where builds go"), Main.Service.BuildsFolder) is { } picked) BuildsFolder = Path.GetFullPath(picked);
    }

    async Task ChangeWorkAsync()
    {
        if (Main.Host is not { } host) return;
        if (await host.PickFolderAsync(Tr.T("Where the build files go"), Main.Service.Work) is { } picked) Work = Path.GetFullPath(picked);
    }

    void Done()
    {
        Save();
        Main.ShowHome();
    }
}
