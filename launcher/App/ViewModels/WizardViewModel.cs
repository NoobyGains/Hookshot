using System.Collections.ObjectModel;
using System.Diagnostics;
using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

public enum JobKind { Build, Rebuild, Update }

/// One run of the wizard: what is built (a new version, one you have again, an update of a build), from which game files, into
/// which folder; the version's tools, downloaded in step 1; and the pages of its steps, kept for Back
public sealed class BuildJob
{
    public BuildJob(MainViewModel main, JobKind kind, string channel, string version, BuildEntry? replaces)
    {
        Main = main;
        Kind = kind;
        Channel = channel;
        Version = version;
        Replaces = replaces;
        var s = main.Service;
        InstallDir = kind == JobKind.Rebuild && replaces != null ? replaces.Folder
            : LauncherSettings.FolderFor(s.BuildsFolder, version, p => s.Registry.FindByFolder(p) is { } e && e.Id != replaces?.Id);
    }

    public MainViewModel Main { get; }
    public LauncherService Service => Main.Service;
    public JobKind Kind { get; }
    public string Channel { get; }
    public string Version { get; }
    /// The build an update or a rebuild takes the place of
    public BuildEntry? Replaces { get; }
    public string? From => Kind == JobKind.Update ? Replaces?.Version : null;
    /// The version and the one it replaces as players see them (a nightly: "Nightly 2029 · c544828f", Versions.Shown)
    public string Shown => Versions.Shown(Version);
    public string? ShownFrom => From == null ? null : Versions.Shown(From);
    public string InstallDir { get; set; }
    public FoundGameFile? Picked { get; set; }
    public Toolchain? Tools { get; set; }
    /// The tools were downloaded in step 1 (not already on this PC), and how long that took
    public bool ToolsDownloaded { get; set; }
    public TimeSpan ToolsTime { get; set; }
    public bool AdvancedOpen { get; set; }
    public readonly CancellationTokenSource Cancel = new();

    public FilesStepViewModel? Files { get; set; }
    public SettingsStepViewModel? Settings { get; set; }

    public string Verb => Kind switch { JobKind.Update => "Update to ", JobKind.Rebuild => "Rebuild ", _ => "Build " };
    /// The start button's words: Build, Rebuild or Update to, then the version
    public string StartText => Tr.F(Kind switch { JobKind.Update => "Update to {0}", JobKind.Rebuild => "Rebuild {0}", _ => "Build {0}" }, Shown);

    /// Everything of step 1 stops (the download, the checks): the wizard was left
    public void Stop()
    {
        try { Cancel.Cancel(); }
        catch (ObjectDisposedException) { }
    }
}

/// One game file found on this PC (or browsed, or dropped), and what make_game.py --check said of it
public sealed class GameFileViewModel : ViewModelBase
{
    readonly FilesStepViewModel step;
    GameCheck? check;

    public GameFileViewModel(FilesStepViewModel step, FoundGameFile file)
    {
        this.step = step;
        File = file;
    }

    public FoundGameFile File { get; }
    public string Name => File.Folders ? Tr.F("{0} (romfs and exefs)", File.Name) : File.Name;
    public string Where => File.Where == "Dropped on the window" ? Tr.T("Dropped on the window") : ShownPath.Of(Path.GetDirectoryName(File.Path) ?? File.Path);
    public string? WhereFull => File.Where == "Dropped on the window" ? null : File.Path;

    public GameCheck? Check
    {
        get => check;
        set
        {
            if (!Set(ref check, value)) return;
            RaiseAll(nameof(Checking), nameof(Ok), nameof(Old), nameof(Bad), nameof(ChipText), nameof(Dim), nameof(CanPick), nameof(Tip));
        }
    }

    public bool Checking => check == null;
    public bool Ok => check?.Status == GameCheckStatus.Supported;
    public bool Old => check?.Status == GameCheckStatus.OtherVersion;
    public bool Bad => check?.Status == GameCheckStatus.Unreadable;
    public string ChipText => check?.Status switch
    {
        GameCheckStatus.Supported => Tr.T("Supported version"),
        GameCheckStatus.OtherVersion => Tr.T("Not the supported version"),
        GameCheckStatus.Unreadable => Tr.T("Can't be read"),
        _ => Tr.T("Checking…"),
    };
    public string? Tip => check?.Text;
    public bool Dim => check != null && !Ok;
    public bool CanPick => !Dim;

    public bool IsPicked
    {
        get => step.Picked == this;
        set
        {
            if (value && CanPick) step.Picked = this;
            else Raise();
        }
    }

    public void PickedChanged() => Raise(nameof(IsPicked));
}

/// Step 1, the game files: the version's tools download (Toolchains) while the game files found on this PC are listed, then each
/// is checked with make_game.py --check from those tools. Next once both are done and a supported file is picked
public sealed class FilesStepViewModel : ViewModelBase, IWizardPage
{
    GameFileViewModel? picked;
    double toolsFraction;
    long toolsTotal;
    bool toolsDone, toolsFailed, searching = true;
    string? toolsProblem;
    readonly Stopwatch toolsClock = new();
    bool checking;

    /// tools: start the tools' download (the screenshots show it at a set point instead)
    public FilesStepViewModel(BuildJob job, bool tools = true)
    {
        Job = job;
        job.Files = this;
        BackCommand = new Command(Back);
        NextCommand = new Command(Next, () => CanNext);
        BrowseCommand = new Command(() => _ = BrowseAsync());
        FoldersCommand = new Command(() => _ = FoldersAsync());
        // (only after a failure: a second click while it downloads again starts nothing)
        RetryCommand = new Command(StartTools, () => toolsFailed);
        RequirementsCommand = new Command(() => Main.Host?.Open(SystemRequirements.Url));
        _ = Task.Run(() => SystemRequirements.Check(job.InstallDir)).ContinueWith(task => Ui.Post(() =>
        {
            if (task.IsCompletedSuccessfully) requirements = task.Result;
            else requirements = new(RequirementStatus.Gray, Tr.T("This PC could not be checked"), Tr.T("See the system requirements before building."));
            RaiseAll(nameof(RequirementsSummary), nameof(RequirementsDetail), nameof(RequirementsGreen), nameof(RequirementsYellow), nameof(RequirementsRed), nameof(RequirementsGray));
        }));
        if (tools) StartTools();
        StartSearch();
    }

    RequirementResult requirements = new(RequirementStatus.Gray, Tr.T("Checking this PC…"), Tr.T("Checking OS, memory, storage and Vulkan support."));
    public string RequirementsSummary => requirements.Summary;
    public string RequirementsDetail => requirements.Detail;
    public bool RequirementsGray => requirements.Status == RequirementStatus.Gray;
    public bool RequirementsGreen => requirements.Status == RequirementStatus.Green;
    public bool RequirementsYellow => requirements.Status == RequirementStatus.Yellow;
    public bool RequirementsRed => requirements.Status == RequirementStatus.Red;
    public Command RequirementsCommand { get; }

    public BuildJob Job { get; }
    MainViewModel Main => Job.Main;
    LauncherService Service => Job.Service;
    public int Step => 1;
    public bool Finished => false;

    public ObservableCollection<GameFileViewModel> Files { get; } = new();

    public string Sub => Job.Kind == JobKind.Update
        ? Tr.F("Updating {0} to {1}. The file you built it from is picked; pick another if it moved.", Job.ShownFrom, Job.Shown)
        : Tr.T("Pick your dump of the game. Hookshot reads it on this PC; nothing is uploaded.");

    // ---- the tools ----

    public string ToolsTitle => Tr.F("Builder tools for {0}", Job.Shown);
    public double ToolsFraction { get => toolsFraction; private set => Set(ref toolsFraction, value); }
    public bool ToolsDone => toolsDone;
    public bool ToolsFailed => toolsFailed;
    public bool ToolsBusy => !toolsDone && !toolsFailed;
    /// Downloading with its size known: a bar; before that (finding the version's tools) a spinner, not a bar that does not move
    public bool ToolsMeasured => ToolsBusy && toolsTotal > 0;
    public bool ToolsLooking => ToolsBusy && toolsTotal == 0;

    public string ToolsNote
    {
        get
        {
            if (toolsFailed) return Tr.F("The download stopped: {0}", toolsProblem);
            if (toolsDone)
                return Job.ToolsDownloaded ? Tr.F("Downloaded, {0}. Kept for this version's updates.", Durations.Size(toolsTotal))
                    : Tr.T("Already on this PC. Kept for this version's updates.");
            if (toolsTotal == 0) return Tr.T("Looking for this version's tools…");
            var have = (long)(toolsFraction * toolsTotal);
            var text = Tr.F("{0} of {1}", have >> 20, Durations.Size(toolsTotal));
            var secs = toolsClock.Elapsed.TotalSeconds;
            if (toolsFraction > 0.02 && secs > 2)
            {
                var left = secs / toolsFraction * (1 - toolsFraction);
                text += left < 90 ? Tr.F(", about {0} s left", Math.Max(1, (int)Math.Round(left))) : Tr.F(", about {0} min left", (int)Math.Round(left / 60));
            }
            return text;
        }
    }

    void StartTools()
    {
        toolsFailed = false;
        toolsProblem = null;
        toolsTotal = 0;
        ToolsFraction = 0;
        RaiseTools();
        toolsClock.Restart();
        var token = Job.Cancel.Token;
        Task.Run(async () =>
        {
            try
            {
                var t = await ToolsSource.EnsureAsync(Service.Tools, Service.Releases, Job.Version,
                                                      p => Ui.Post(() => Progress(p)), token);
                Ui.Post(() => ToolsReady(t));
            }
            catch (OperationCanceledException) { }
            catch (Exception e) when (e is FetchException or IOException or InvalidDataException or FormatException or UnauthorizedAccessException
                                          or ArgumentException)
            {
                Ui.Post(() =>
                {
                    toolsFailed = true;
                    toolsProblem = e.Message;
                    RaiseTools();
                });
            }
        }, token);
    }

    void Progress(ToolsDownloadProgress p)
    {
        if (p.Total > 0)
        {
            toolsTotal = p.Total;
            Job.ToolsDownloaded = true;
        }
        ToolsFraction = p.Fraction;
        RaiseAll(nameof(ToolsNote), nameof(ToolsMeasured), nameof(ToolsLooking));
    }

    void ToolsReady(Toolchain t)
    {
        Job.Tools = t;
        Job.ToolsTime = toolsClock.Elapsed;
        toolsDone = true;
        ToolsFraction = 1;
        RaiseTools();
        _ = CheckAllAsync();
    }

    void RaiseTools()
    {
        RaiseAll(nameof(ToolsDone), nameof(ToolsFailed), nameof(ToolsBusy), nameof(ToolsMeasured), nameof(ToolsLooking), nameof(ToolsNote));
        RetryCommand.Changed();
        RaiseNext();
    }

    /// For the screenshots: the tools as if this far into their download
    public void ShowToolsAt(double fraction, long total)
    {
        toolsTotal = total;
        Job.ToolsDownloaded = true;
        toolsDone = fraction >= 1;
        ToolsFraction = fraction;
        RaiseTools();
    }

    // ---- the game files ----

    public bool Searching => searching && Files.Count == 0;
    public bool NothingFound => !searching && Files.Count == 0;

    void StartSearch()
    {
        var remembered = Remembered();
        var token = Job.Cancel.Token;
        Task.Run(() =>
        {
            var found = GameFiles.Find(GameFiles.Places(Service.Platform));
            Ui.Post(() =>
            {
                if (token.IsCancellationRequested) return;
                searching = false;
                if (remembered != null) Add(remembered, pick: true, first: true);
                foreach (var f in found) Add(f, pick: false, first: false);
                RaiseAll(nameof(Searching), nameof(NothingFound));
                if (Job.Tools != null) _ = CheckAllAsync();
            });
        }, token);
    }

    /// The game files this build (an update) or the last build was made from
    FoundGameFile? Remembered()
    {
        var e = Job.Replaces;
        var s = Service.Settings;
        var nup = e?.Nup ?? (e?.Romfs == null ? s.Nup : null);
        if (nup != null && File.Exists(nup)) return GameFiles.FromPath(nup, "Last used");
        var (romfs, exefs) = e?.Romfs != null ? (e.Romfs, e.Exefs) : (s.Romfs, s.Exefs);
        return romfs != null && exefs != null ? GameFiles.FromFolders(romfs, exefs, "Last used") : null;
    }

    GameFileViewModel Add(FoundGameFile f, bool pick, bool first)
    {
        var have = Files.FirstOrDefault(x => BuildRegistry.SameFolder(x.File.Path, f.Path) && x.File.Exefs == f.Exefs);
        if (have == null)
        {
            have = new GameFileViewModel(this, f);
            if (first) Files.Insert(0, have);
            else Files.Add(have);
        }
        if (pick) Picked = have;
        RaiseAll(nameof(Searching), nameof(NothingFound));
        return have;
    }

    /// Each file checked in turn (the check unpacks into one probe folder); the first supported one is picked when none is
    async Task CheckAllAsync()
    {
        if (checking || Job.Tools is not { } tools) return;
        checking = true;
        var token = Job.Cancel.Token;
        try
        {
            while (!token.IsCancellationRequested && Files.FirstOrDefault(f => f.Check == null) is { } next)
            {
                var command = MakeGameCommand.ForCheck(tools, next.File.Source, Service.Platform, Service.Home, LauncherService.LauncherPath, Service.Work);
                var result = await Task.Run(() => MakeGameRun.CheckAsync(command, token), token);
                next.Check = result;
                if (picked == next && !next.Ok) Picked = null;
                if (picked == null && next.Ok) Picked = next;
                RaiseNext();
            }
        }
        catch (OperationCanceledException) { }
        finally { checking = false; }
    }

    public GameFileViewModel? Picked
    {
        get => picked;
        set
        {
            var was = picked;
            if (!Set(ref picked, value)) return;
            was?.PickedChanged();
            value?.PickedChanged();
            Job.Picked = value?.File;
            RaiseNext();
        }
    }

    // ---- Browse, the folders, a drop ----

    async Task BrowseAsync()
    {
        if (Main.Host is not { } host) return;
        var path = await host.PickFileAsync(Tr.T("Your game file (.nup)"), "*.nup");
        if (path == null) return;
        if (GameFiles.FromPath(path, "Browsed") is { } f) Picked = Add(f, pick: true, first: true);
        else Main.ShowToast(Tr.T("That is not a .nup file."));
        _ = CheckAllAsync();
    }

    async Task FoldersAsync()
    {
        if (Main.Host is not { } host) return;
        var first = await host.PickFolderAsync(Tr.T("The game's romfs folder, or the folder holding romfs and exefs"), null);
        if (first == null) return;
        var f = GameFiles.FromPath(first, "Picked");
        if (f == null)
        {
            var exefs = await host.PickFolderAsync(Tr.T("The game's exefs folder"), Path.GetDirectoryName(first));
            if (exefs == null) return;
            f = GameFiles.FromFolders(first, exefs, "Picked");
        }
        if (f != null) Add(f, pick: true, first: true);
        else Main.ShowToast(Tr.T("Those are not the game's romfs and exefs folders."));
        _ = CheckAllAsync();
    }

    public void Dropped(IReadOnlyList<string> paths)
    {
        var any = false;
        foreach (var p in paths)
            if (GameFiles.FromPath(p, "Dropped on the window") is { } f)
            {
                Add(f, pick: true, first: true);
                any = true;
            }
        if (!any) Main.ShowToast(Tr.T("Drop a .nup file, or the folder holding romfs and exefs."));
        _ = CheckAllAsync();
    }

    // ---- Back and Next ----

    public bool CanNext => toolsDone && picked?.Ok == true;

    public string Hint => CanNext ? Tr.T("Ready for the settings.")
        : !toolsDone && picked?.Ok != true ? Tr.T("Next waits for the tools download and a supported game file.")
        : !toolsDone ? Tr.T("Next waits for the tools download.")
        : Tr.T("Pick a supported game file to go on.");

    void RaiseNext()
    {
        RaiseAll(nameof(CanNext), nameof(Hint));
        NextCommand.Changed();
    }

    public Command BackCommand { get; }
    public Command NextCommand { get; }
    public Command BrowseCommand { get; }
    public Command FoldersCommand { get; }
    public Command RetryCommand { get; }

    void Back()
    {
        Job.Stop();
        Main.ShowHome();
    }

    void Next()
    {
        if (!CanNext) return;
        Main.Navigate(Job.Settings ?? new SettingsStepViewModel(Job));
    }
}
