using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

/// A page of the build wizard: its step in the title bar's pill (1 game files, 2 settings, 3 build), and whether step 3 is done
public interface IWizardPage
{
    int Step { get; }
    bool Finished { get; }
}

/// One step of the title bar's pill
public sealed class StepItem(int number, string title) : ViewModelBase
{
    bool done, now;

    public int Number => number;
    public string Title => Tr.T(title);
    public bool IsDone { get => done; set { if (Set(ref done, value)) Raise(nameof(IsTodo)); } }
    public bool IsNow { get => now; set { if (Set(ref now, value)) Raise(nameof(IsTodo)); } }
    public bool IsTodo => !done && !now;
}

/// The window: one page at a time (home, the wizard's steps, settings, saves), a dialog over it, a toast at the bottom
public sealed class MainViewModel : ViewModelBase
{
    object page;
    object? modal;
    string? toast;
    int toastId;
    bool dropping;

    public MainViewModel(LauncherService service, StartRequest start)
    {
        Service = service;
        Home = new HomeViewModel(this);
        page = Home;
        Home.Open(start);
        MinimizeCommand = new Command(() => Host?.Minimize());
        CloseCommand = new Command(() => Host?.Close());
        SettingsCommand = new Command(ShowSettings);
        if (start.Kind == StartKind.Window) OfferCrash();
    }

    /// How long a crash stays news: an older log is not offered (a build last played weeks ago, the launcher not opened since)
    static readonly TimeSpan CrashNews = TimeSpan.FromDays(7);

    /// A build whose last run closed unexpectedly (launcher/Core/Problems.cs CrashCheck): its problem page, once per log. Not at
    /// the first start with the check (the logs already there are old news), and not while a game runs (its log is the live run's)
    void OfferCrash()
    {
        var s = Service.Settings;
        var now = DateTime.UtcNow.Ticks;
        if (s.CrashChecksSince is not { } since)
        {
            s.CrashChecksSince = now;
            SaveSettingsQuietly();
            return;
        }
        try
        {
            if (Saves.Running(Service.Platform).Contains(Saves.Hookshot.Display)) return;
        }
        catch (Exception e) when (e is InvalidOperationException or System.ComponentModel.Win32Exception or UnauthorizedAccessException) { return; }
        var notBefore = Math.Max(since, now - CrashNews.Ticks);
        // (the log names the GPU the game ran on; this is for a log without that line: only one maker here, else none guessed)
        var vendor = Service.Gpus.Count == 1 ? Service.Gpus[0] : null;
        foreach (var b in Service.Registry.Builds)
        {
            var found = CrashCheck.Find(b.Folder, s.SeenCrashLogs.GetValueOrDefault(b.Folder), notBefore, vendor);
            if (found == null) continue;
            s.SeenCrashLogs[b.Folder] = found.WriteTicks;
            SaveSettingsQuietly();
            page = new ProblemPageViewModel(this, found.Problem, ShowHome, crashed: true);
            return;
        }
    }

    void SaveSettingsQuietly()
    {
        try { Service.SaveSettings(); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
    }

    public LauncherService Service { get; }
    public HomeViewModel Home { get; }
    public IWindowHost? Host { get; set; }
    public Platform Platform => Service.Platform;
    public bool Linux => Service.Platform == Platform.Linux;

    public Command MinimizeCommand { get; }
    public Command CloseCommand { get; }
    public Command SettingsCommand { get; }

    public IReadOnlyList<StepItem> Steps { get; } = new[] { new StepItem(1, Tr.N("Game files")), new StepItem(2, Tr.N("Settings")), new StepItem(3, Tr.N("Build")) };

    public object Page
    {
        get => page;
        private set
        {
            if (!Set(ref page, value)) return;
            RefreshSteps();
            RaiseAll(nameof(IsHome), nameof(InWizard));
        }
    }

    public void RefreshSteps()
    {
        var w = page as IWizardPage;
        foreach (var s in Steps)
        {
            s.IsDone = w != null && (s.Number < w.Step || (s.Number == 3 && w.Finished));
            s.IsNow = w != null && s.Number == w.Step && !(s.Number == 3 && w.Finished);
        }
    }

    public bool IsHome => page is HomeViewModel;
    public bool InWizard => page is IWizardPage;

    public object? Modal
    {
        get => modal;
        set
        {
            if (Set(ref modal, value)) Raise(nameof(HasModal));
        }
    }

    public bool HasModal => modal != null;

    public string? Toast
    {
        get => toast;
        private set
        {
            if (Set(ref toast, value)) Raise(nameof(HasToast));
        }
    }

    public bool HasToast => toast != null;

    /// A short line at the bottom of the window, for a few seconds
    public void ShowToast(string text)
    {
        var id = ++toastId;
        Toast = text;
        _ = Task.Delay(2800).ContinueWith(_ => Ui.Post(() => { if (toastId == id) Toast = null; }), TaskScheduler.Default);
    }

    /// A file dragged over the window in step 1: "Drop your game file to check it"
    public bool Dropping
    {
        get => dropping;
        set => Set(ref dropping, value);
    }

    public bool AcceptsDrop => page is FilesStepViewModel;

    public void Drop(IReadOnlyList<string> paths)
    {
        Dropping = false;
        if (page is FilesStepViewModel files) files.Dropped(paths);
    }

    public void Navigate(object to)
    {
        Modal = null;
        Page = to;
    }

    public void ShowHome()
    {
        Home.Refresh();
        Navigate(Home);
    }

    public void ShowSettings() => Navigate(new SettingsViewModel(this));

    public void ShowSaves() => Navigate(new SavesViewModel(this));

    /// The wizard for a version: a new build, building one you have again, or an update of a build (replaces)
    public FilesStepViewModel StartWizard(JobKind kind, string channel, string version, BuildEntry? replaces = null, bool tools = true)
    {
        var job = new BuildJob(this, kind, channel, version, replaces);
        var step = new FilesStepViewModel(job, tools);
        Navigate(step);
        return step;
    }
}
