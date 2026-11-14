using System.Collections.ObjectModel;
using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

/// One version in the home's list
public sealed class BuildItemViewModel : ViewModelBase
{
    readonly HomeViewModel home;
    bool selected;

    public BuildItemViewModel(HomeViewModel home, BuildEntry entry, bool built, string? update, IReadOnlyList<SaveSlot> saves, bool deleting = false)
    {
        this.home = home;
        Entry = entry;
        IsBuilt = built;
        Update = update;
        Saves = saves;
        IsDeleting = deleting;
        SelectCommand = new Command(() => home.Select(this));
        // (a build being deleted: nothing more starts on it, and its delete does not start twice)
        PlayCommand = new Command(() => home.Play(this), () => IsBuilt && !IsDeleting);
        SetDefaultCommand = new Command(() => home.SetDefault(this), () => !IsDeleting);
        DeleteCommand = new Command(() => home.AskDelete(this), () => !IsDeleting);
        UpdateCommand = new Command(() => home.UpdateBuild(this), () => !IsDeleting && home.CanStartBuild);
        SavesCommand = new Command(() => home.Main.ShowSaves(), () => !IsDeleting);
        FolderCommand = new Command(() => home.Main.Host?.Open(Entry.Folder));
    }

    /// Its folder is being deleted (DeleteViewModel): the row says so with a spinner until it goes
    public bool IsDeleting { get; }

    public BuildEntry Entry { get; }
    public IReadOnlyList<SaveSlot> Saves { get; }
    /// The version as players see it (a nightly: "Nightly 2029 · c544828f", Versions.Shown), else the build's name
    public string Version => Entry.Version is { } v ? Versions.Shown(v) : Entry.Name;
    public string Channel => UpdatePolicy.ChannelOf(Entry.Channel, Entry.Version);
    public bool IsRelease => Channel == Versions.Stable;
    public bool IsCandidate => Channel == Versions.Candidate;
    public bool IsNightly => Channel == Versions.Nightly;
    public bool IsDefault => Entry.Default;
    public bool IsBuilt { get; }
    public string? Update { get; }
    public bool HasUpdate => Update != null;
    public string UpdateLine => Update == null ? "" : Tr.F("{0} is out", Versions.Shown(Update));

    /// "Built 3 Nov, 38.4 GB" (no saves count: every build shares them)
    public string Meta
    {
        get
        {
            var bits = new List<string> { Tr.F("Built {0}", Durations.Day(Entry.Updated.LocalDateTime, DateTime.Now)) };
            if (!IsBuilt) bits.Add(Tr.T("not built"));
            if (Entry.Bytes is long b) bits.Add(Durations.Size(b));
            return string.Join(Tr.T(", "), bits);
        }
    }

    public bool IsSelected
    {
        get => selected;
        set
        {
            if (Set(ref selected, value)) RaiseAll(nameof(ShowActions), nameof(ShowOtherActions), nameof(ShowDefaultNote));
        }
    }

    public bool ShowActions => selected;
    public bool ShowOtherActions => selected && !IsDefault;
    public bool ShowDefaultNote => selected && IsDefault;
    public bool ShowRing => !IsDefault;
    public bool ShowMeta => !HasUpdate && !IsDeleting;
    public bool ShowUpdateLine => HasUpdate && !IsDeleting;
    public string DeletingText => Tr.F("Deleting {0}…", Version);
    public bool IsFirst { get; set; }
    public Avalonia.Thickness Separator => IsFirst ? default : new Avalonia.Thickness(0, 1, 0, 0);

    public void RaiseMeta() => Raise(nameof(Meta));

    /// Whether a build can start from it now (the home's checks and the launcher's update)
    public void RaiseCommands() => UpdateCommand.Changed();

    public Command SelectCommand { get; }
    public Command PlayCommand { get; }
    public Command SetDefaultCommand { get; }
    public Command DeleteCommand { get; }
    public Command UpdateCommand { get; }
    public Command SavesCommand { get; }
    public Command FolderCommand { get; }
}

/// Home: Build when there is no build; else the default version on the left (Play, its update, its saves) and every version on
/// the right
public sealed class HomeViewModel : ViewModelBase
{
    string? notice;
    string status = "";
    bool checkAgain, asked;
    readonly HashSet<string> deleting = new();

    public HomeViewModel(MainViewModel main)
    {
        Main = main;
        // (the update check and the launcher's update are BusyCommands: off while they run, with what they are doing on screen)
        CheckCommand = new BusyCommand(CheckAsync);
        UpdateLauncherCommand = new BusyCommand(UpdateLauncherAsync, () => HasLauncherUpdate,
                                                e => Notice = Tr.F("The launcher could not update itself: {0}", e.Message));
        CheckCommand.PropertyChanged += (_, e) => { if (e.PropertyName == nameof(BusyCommand.IsBusy)) BusyChanged(); };
        UpdateLauncherCommand.PropertyChanged += (_, e) => { if (e.PropertyName == nameof(BusyCommand.IsBusy)) BusyChanged(); };
        BuildCommand = new Command(() => StartBuild(Service.DefaultChannel), () => NewestDefault != null && CanStartBuild);
        ChannelCommand = new Command(() => Main.Modal = new ChannelPickerViewModel(Main, Service.DefaultChannel), () => CanStartBuild);
        DismissProblemCommand = new Command(() => Notice = null);
        PlayDefaultCommand = new Command(() => { if (Default is { } d) Play(d); }, () => Default is { IsBuilt: true, IsDeleting: false });
        UpdateDefaultCommand = new Command(() => { if (Default is { } d) UpdateBuild(d); }, () => CanStartBuild && Default?.IsDeleting != true);
        SavesDefaultCommand = new Command(() => Main.ShowSaves());
        CancelLauncherUpdateCommand = new Command(() => UpdateLauncherCommand.Cancel());
        // (not while the launcher updates itself: a check forgets the update it is putting in place)
        CheckForUpdatesCommand = new Command(() =>
        {
            asked = true;
            _ = CheckReleasesAsync();
        }, () => CanStartBuild);
        ImportLongshotCommand = new Command(() => Main.Modal = new LongshotImportViewModel(Main));
        NotNowLongshotCommand = new Command(() =>
        {
            Service.Settings.LongshotSavesAsked = true;
            try { Service.SaveSettings(); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            LongshotOffer = null;
        });
        ImportNx2naviCommand = new Command(() =>
        {
            var page = new SavesViewModel(Main);
            Main.Navigate(page);
            Main.Modal = new SavePickViewModel(page, SaveMode.Import) { Pick = "nx2navi" };
        });
        NotNowNx2naviCommand = new Command(() =>
        {
            Service.Settings.Nx2naviSavesAsked = true;
            try { Service.SaveSettings(); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            Nx2naviOffer = null;
        });
    }

    public MainViewModel Main { get; }
    LauncherService Service => Main.Service;

    public ObservableCollection<BuildItemViewModel> Builds { get; } = new();

    public bool HasBuilds => Builds.Count > 0;
    public bool NoBuilds => Builds.Count == 0;
    public BuildItemViewModel? Default => Builds.FirstOrDefault(b => b.IsDefault);

    // ---- the empty home ----

    public string? NewestDefault => Service.NewestOf(Service.DefaultChannel);
    public string NewestDefaultText => NewestDefault is { } v ? Versions.Shown(v) : "";
    public string DefaultChannel => Service.DefaultChannel;
    public bool DefaultIsRelease => DefaultChannel == Versions.Stable;
    public bool DefaultIsCandidate => DefaultChannel == Versions.Candidate;
    public bool DefaultIsNightly => DefaultChannel == Versions.Nightly;
    public bool KnowsNewest => NewestDefault != null;
    public bool CheckFailed => NewestDefault == null && Service.Checked && !Service.Answered;
    public bool Checking => NewestDefault == null && !Service.Checked;
    /// GitHub answered, and the channel new builds start on has no release yet (a fork's stable before its first release)
    public bool NoneYet => NewestDefault == null && Service.Checked && Service.Answered;
    public string NoneYetText => Tr.T("There is no release on this channel yet.");

    // ---- the default version, on the left ----

    public string HeroVersion => Default?.Version ?? "";
    public string HeroChannel => Default?.Channel ?? Versions.Stable;
    public bool HeroIsRelease => HeroChannel == Versions.Stable;
    public bool HeroIsCandidate => HeroChannel == Versions.Candidate;
    public bool HeroIsNightly => HeroChannel == Versions.Nightly;

    /// "Your default version. Built 3 Nov, English (US), NVIDIA DLSS."
    public string HeroNote
    {
        get
        {
            if (Default is not { } d) return "";
            var e = d.Entry;
            var bits = new List<string>
            {
                Tr.F("Built {0}", Durations.Day(e.Updated.LocalDateTime, DateTime.Now)),
            };
            if (GameFolder.Language(e.Folder) is { } lang) bits.Add(Tr.T(Languages.NameOf(lang)));
            if (e.Dlss ?? GameFolder.HasDlss(e.Folder)) bits.Add("NVIDIA DLSS");
            if (e.Fsr == true) bits.Add("AMD FSR 4");
            if (!d.IsBuilt) bits.Add(Tr.T("not built: its game is missing"));
            return Tr.F("Your default version. {0}.", string.Join(Tr.T(", "), bits));
        }
    }

    public string HeroSaves => Default is { } d ? SaveText.Short(d.Saves, DateTime.Now) : "";
    public bool HeroHasUpdate => Default?.HasUpdate == true;
    public string HeroUpdate => Default is { Update: { } u } d ? Tr.F("{0} is out on the {1} channel.", u, ChannelPickerViewModel.NameOf(d.Channel)) : "";

    /// "3 versions use 116.7 GB in D:\Games\Hookshot."
    public string Footer
    {
        get
        {
            var n = Builds.Count;
            var known = Builds.Where(b => b.Entry.Bytes != null).Sum(b => b.Entry.Bytes!.Value);
            var folder = ShownPath.Of(Service.BuildsFolder);
            return known > 0 ? Tr.P(n, "1 version uses {1} in {2}.", "{0} versions use {1} in {2}.", Durations.Size(known), folder)
                : Tr.P(n, "1 version in {1}.", "{0} versions in {1}.", folder);
        }
    }

    // ---- notices ----

    /// A problem to read (a build that would not start): null for none
    public string? Notice
    {
        get => notice;
        set
        {
            if (Set(ref notice, value)) Raise(nameof(HasNotice));
        }
    }

    public bool HasNotice => notice != null;
    public bool ShowLeftPanel => HasBuilds;

    /// The quiet answer of the update check
    public string Status
    {
        get => status;
        set { if (Set(ref status, value)) Raise(nameof(ShowStatus)); }
    }

    public Command BuildCommand { get; }
    public Command ChannelCommand { get; }
    public Command DismissProblemCommand { get; }
    /// The update check: at start, from Try again, and after the launcher's channel changed in Settings
    public BusyCommand CheckCommand { get; }
    /// Check for updates, under the versions: the same check, for Hookshot's channels and the launcher's own, which says so when
    /// it found nothing new
    public Command CheckForUpdatesCommand { get; }
    /// Try again, on the empty home when the check got no answer: the check itself
    public BusyCommand RetryCheckCommand => CheckCommand;
    public Command PlayDefaultCommand { get; }
    public Command UpdateDefaultCommand { get; }
    public Command SavesDefaultCommand { get; }
    public BusyCommand UpdateLauncherCommand { get; }
    /// Stops the launcher's download (only while it downloads: BusyCommand.CanCancel)
    public Command CancelLauncherUpdateCommand { get; }
    /// The check running with a version already known (Try again after an answer, a channel switch): a line with a spinner; the
    /// empty home's first check has its own (Checking)
    public bool ShowCheckLine => CheckCommand.IsBusy && !Checking;
    /// The check's last answer, when no check runs
    public bool ShowStatus => !CheckCommand.IsBusy && !string.IsNullOrEmpty(status);

    /// A build may start: not while the check may still change what is newest, nor while the launcher replaces itself (it closes
    /// at the end, and a build would stop with it)
    public bool CanStartBuild => !CheckCommand.IsBusy && !UpdateLauncherCommand.IsBusy;

    void BusyChanged()
    {
        BuildCommand.Changed();
        CheckForUpdatesCommand.Changed();
        ChannelCommand.Changed();
        UpdateDefaultCommand.Changed();
        foreach (var b in Builds) b.RaiseCommands();
        RaiseAll(nameof(CanStartBuild), nameof(ShowCheckLine), nameof(ShowStatus));
    }
    public Command ImportLongshotCommand { get; }
    public Command NotNowLongshotCommand { get; }
    public Command ImportNx2naviCommand { get; }
    public Command NotNowNx2naviCommand { get; }

    string? nx2naviOffer;
    public string? Nx2naviOffer
    {
        get => nx2naviOffer;
        set { if (Set(ref nx2naviOffer, value)) Raise(nameof(HasNx2naviOffer)); }
    }
    public bool HasNx2naviOffer => nx2naviOffer != null;

    void OfferNx2navi()
    {
        Nx2naviOffer = null;
        if (Service.Settings.Nx2naviSavesAsked) return;
        try
        {
            var found = Saves.Emulator(Service.SaveEnv).FirstOrDefault(s => s.Owner == "nx2navi" && s.Found);
            if (found == null) return;
            var profiles = found.Profiles.Select(p => Saves.Describe(p.Path)).Where(s => s.Count > 0).ToList();
            if (profiles.Count > 0)
            {
                var folder = ShownPath.Of(found.Folder);
                Nx2naviOffer = profiles.Count > 1
                    ? Tr.P(profiles.Count, "Found saves in 1 profile in {1}. Copy them into Hookshot? The originals stay where they are.",
                           "Found saves in {0} profiles in {1}. Copy them into Hookshot? The originals stay where they are.", folder)
                    : Tr.F("Found {0} in {1}. Copy them into Hookshot? The originals stay where they are.",
                           SaveText.Long(profiles[0], DateTime.Now), folder);
            }
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or SaveFailure) { }
    }

    // ---- the offer to import Longshot's saves (once: until it is answered) ----

    string? longshotOffer;
    public string? LongshotOffer
    {
        get => longshotOffer;
        set { if (Set(ref longshotOffer, value)) Raise(nameof(HasLongshotOffer)); }
    }
    public bool HasLongshotOffer => longshotOffer != null;

    /// Longshot saves on this PC, not offered yet: the home offers to import them
    void OfferLongshot()
    {
        if (Service.Settings.LongshotSavesAsked) return;
        try
        {
            var found = LongshotSaves.Find(Service.SaveEnv).Where(s => s.Valid).ToList();
            if (found.Count > 0)
                LongshotOffer = Tr.F("Found {0} in Longshot. Copy them into Hookshot? Longshot keeps its own.",
                                     SaveText.Long(found[0].Slots, DateTime.Now));
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or SaveFailure) { }
    }

    // ---- the launcher's own update ----

    public bool HasLauncherUpdate => Service.LauncherUpdate != null;
    /// Only a newer one "is out": after the player switched the launcher's channel, its newest can be older than this one, or a
    /// nightly that has no order against a release
    int LauncherUpdateOrder => Service.LauncherUpdate is { } r ? SelfUpdate.Compare(r.Version, Service.OwnTag) : 0;

    public string LauncherUpdateHeading => LauncherUpdateOrder > 0 ? Tr.T("A new launcher is out")
        : Tr.F("Another launcher on the {0} channel", ChannelPickerViewModel.NameOf(Service.LauncherChannel));

    public string LauncherUpdateButton => LauncherUpdateOrder > 0 ? Tr.T("Update the launcher") : Tr.T("Switch to it");

    public string LauncherUpdateText => Service.LauncherUpdate is { } r
        ? LauncherUpdateOrder switch
        {
            > 0 => Tr.F("Hookshot Launcher {0} is out (you have {1}).", Versions.Shown(r.Version), Versions.Shown(Service.OwnTag)),
            < 0 => Tr.F("Hookshot Launcher {0} is available on {1}. It is older than yours ({2}).", Versions.Shown(r.Version),
                        ChannelPickerViewModel.NameOf(Service.LauncherChannel), Versions.Shown(Service.OwnTag)),
            _ => Tr.F("Hookshot Launcher {0} is available on {1} (you have {2}).", Versions.Shown(r.Version),
                      ChannelPickerViewModel.NameOf(Service.LauncherChannel), Versions.Shown(Service.OwnTag)),
        }
        : "";

    /// Downloads the new launcher, checks it, puts it in place and starts it; this one closes. On the banner meanwhile: the button
    /// off ("Updating…"), the download's percentage and bar, then each step; Cancel while it downloads. A failure leaves this one as
    /// it is, says why (Notice) and the button is on again
    async Task UpdateLauncherAsync(BusyCommand busy, CancellationToken cancel)
    {
        busy.Report(Tr.T("Downloading the new launcher…"), 0, canCancel: true);
        await Task.Run(() => Service.UpdateLauncherAsync(
            p => Ui.Post(() => busy.Report(p >= 1 ? Tr.T("Checking the download…") : Tr.F("Downloading the new launcher… {0}%", (int)Math.Round(p * 100)), p, canCancel: p < 1)),
            cancel,
            step => Ui.Post(() => busy.Report(step, canCancel: false))), CancellationToken.None);
        Main.Host?.Close();
    }

    /// The start's own request: --launch names a build (listed if it was not)
    public void Open(StartRequest start)
    {
        var notes = new List<string>();
        if (Service.Registry.Problem is { } broken) notes.Add(Tr.F("The list of builds could not be read (kept as builds.json.broken): {0}", broken));
        if (start.Problem != null) notes.Add(start.Problem);
        if (start.Folder != null && start.Kind == StartKind.Launch)
        {
            Service.Ensure(start.Folder);
        }
        Notice = notes.Count > 0 ? string.Join("\n", notes) : null;
        OfferLongshot();
        OfferNx2navi();
        Refresh();
    }

    public void Refresh()
    {
        var selected = Builds.FirstOrDefault(b => b.IsSelected)?.Entry.Id;
        Builds.Clear();
        var saves = Service.SaveSlots();
        foreach (var b in Service.Registry.Builds)
        {
            var item = new BuildItemViewModel(this, b, Service.IsBuilt(b), Service.UpdateFor(b), saves, deleting.Contains(b.Id));
            item.IsSelected = b.Id == selected;
            item.IsFirst = Builds.Count == 0;
            Builds.Add(item);
        }
        RaiseAll(nameof(HasBuilds), nameof(NoBuilds), nameof(Default), nameof(ShowLeftPanel), nameof(HeroVersion), nameof(HeroChannel),
                 nameof(HeroIsRelease), nameof(HeroIsCandidate), nameof(HeroIsNightly), nameof(HeroNote), nameof(HeroSaves), nameof(HeroHasUpdate),
                 nameof(HeroUpdate), nameof(Footer), nameof(NewestDefault), nameof(NewestDefaultText), nameof(DefaultChannel), nameof(DefaultIsRelease), nameof(DefaultIsCandidate),
                 nameof(DefaultIsNightly), nameof(KnowsNewest), nameof(CheckFailed), nameof(Checking), nameof(NoneYet), nameof(NoneYetText), nameof(ShowCheckLine), nameof(HasLauncherUpdate),
                 nameof(LauncherUpdateText), nameof(LauncherUpdateHeading), nameof(LauncherUpdateButton));
        BuildCommand.Changed();
        PlayDefaultCommand.Changed();
        UpdateDefaultCommand.Changed();
        UpdateLauncherCommand.Changed();
        Service.Measure(() => { foreach (var b in Builds) b.RaiseMeta(); Raise(nameof(Footer)); });
    }

    /// The update check, in the background: a failure is one quiet line, never a stop. Asked while one runs (the launcher's channel
    /// changed in Settings), it runs once more after it, for the new channel
    public async Task CheckReleasesAsync()
    {
        if (CheckCommand.IsBusy)
        {
            checkAgain = true;
            return;
        }
        do
        {
            checkAgain = false;
            await CheckCommand.RunAsync();
        } while (checkAgain);
    }

    async Task CheckAsync(BusyCommand busy, CancellationToken cancel)
    {
        busy.Report(Tr.T("Checking for updates…"));
        var wasAsked = asked;
        asked = false;
        Service.Checked = false;
        Refresh();
        var any = false;
        try
        {
            any = await Service.CheckReleasesAsync();
            Status = any ? "" : Service.Releases.Problem is { } problem
                ? Tr.F("Updates were not checked: {0}", problem)
                : Tr.T("Could not reach GitHub: updates were not checked.");
        }
        catch (Exception e)
        {
            Service.Checked = true;
            Status = Tr.F("Could not check for updates: {0}", e.Message);
        }
        Refresh();
        // (a check someone asked for answers even when nothing is new; an update shows itself: the banner, the Update buttons)
        if (wasAsked && any && !HasLauncherUpdate && !Builds.Any(b => b.HasUpdate))
            Status = Tr.F("Everything is up to date, the launcher too. Checked at {0}.", DateTime.Now.ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture));
    }

    public void Select(BuildItemViewModel b)
    {
        var on = !b.IsSelected;
        foreach (var x in Builds) x.IsSelected = false;
        b.IsSelected = on;
    }

    public void Play(BuildItemViewModel b)
    {
        try
        {
            if (Service.Play(b.Entry) is { } said)
            {
                Notice = said;
                Refresh();
            }
            Main.ShowToast(Tr.F("Starting Hookshot, {0}…", b.Version));
        }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException or InvalidOperationException)
        {
            Notice = Tr.F("{0} could not start: {1}", b.Version, e.Message);
        }
    }

    public void SetDefault(BuildItemViewModel b)
    {
        Service.SetDefault(b.Entry);
        Refresh();
        Main.ShowToast(Tr.F("Play now starts {0}.", b.Version));
    }

    public void AskDelete(BuildItemViewModel b) => Main.Modal = new DeleteViewModel(Main, b);

    /// A build's folder being deleted (tens of GB: seconds to minutes): its row shows it, and nothing starts on it meanwhile
    public void Deleting(BuildEntry b, bool on)
    {
        if (on ? deleting.Add(b.Id) : deleting.Remove(b.Id)) Refresh();
    }

    public void UpdateBuild(BuildItemViewModel b)
    {
        if (b.Update is not { } to) return;
        Main.StartWizard(JobKind.Update, b.Channel, to, b.Entry);
    }

    public void StartBuild(string channel)
    {
        if (Service.NewestOf(channel) is not { } version) return;
        var same = Service.Registry.Builds.FirstOrDefault(b => b.Version == version);
        Main.StartWizard(same != null ? JobKind.Rebuild : JobKind.Build, channel, version, same);
    }
}

/// Choosing what to build: release, rc or nightly, each with its newest version and whether you have it
public sealed class ChannelPickerViewModel : ViewModelBase
{
    string pick;

    public sealed class Row(ChannelPickerViewModel owner, string id, string name, string about, string? version, bool have) : ViewModelBase
    {
        public string Id => id;
        public string Name => Tr.T(name);
        public string About => about;
        public string Version => version == null ? Tr.T(owner.Main.Service.Answered ? "None released yet" : "Not found") : Versions.Shown(version);
        public bool Known => version != null;
        public bool Have => have;
        public bool IsRelease => id == Versions.Stable;
        public bool IsCandidate => id == Versions.Candidate;
        public bool IsNightly => id == Versions.Nightly;
        public string Tag => id;

        public bool IsPicked
        {
            get => owner.Pick == id;
            set
            {
                if (value) owner.Pick = id;
            }
        }

        public void Changed() => Raise(nameof(IsPicked));
    }

    /// A channel's line; the one new builds start on while the player has not picked one says it follows the launcher
    public static string AboutOf(LauncherService service, string id, string about) =>
        service.Settings.DefaultChannel == null && service.DefaultChannel == id
            ? Tr.Sentences(Tr.T(about), Tr.T("It follows the launcher until you pick one in Settings.")) : Tr.T(about);

    /// The channels, in English (Tr.T where shown)
    public static readonly (string Id, string Name, string About)[] All =
    {
        (Versions.Stable, Tr.N("Stable"), Tr.N("The tested version. Best for playing.")),
        (Versions.Candidate, Tr.N("Release candidate"), Tr.N("The next version, to try before it is released.")),
        (Versions.Nightly, Tr.N("Nightly"), Tr.N("The newest development build, with every change of the day.")),
    };

    /// A channel's name in the language in use (stable: Stable); an unknown one as it is
    public static string NameOf(string id) => All.FirstOrDefault(c => c.Id == id).Name is { } name ? Tr.T(name) : id;

    public ChannelPickerViewModel(MainViewModel main, string start)
    {
        Main = main;
        Rows = All.Select(c => new Row(this, c.Id, c.Name, AboutOf(main.Service, c.Id, c.About), main.Service.NewestOf(c.Id), Has(main.Service.NewestOf(c.Id)))).ToList();
        // (a channel with no release yet, a fork's stable most often, is not where the picker starts: the first one that has one)
        pick = main.Service.NewestOf(start) != null ? start : All.Select(c => c.Id).FirstOrDefault(c => main.Service.NewestOf(c) != null) ?? start;
        GoCommand = new Command(Go, () => Version != null);
        CancelCommand = new Command(() => Main.Modal = null);
    }

    bool Has(string? v) => v != null && Main.Service.Registry.Builds.Any(b => b.Version == v);

    public MainViewModel Main { get; }
    public IReadOnlyList<Row> Rows { get; }
    public Command GoCommand { get; }
    public Command CancelCommand { get; }

    public string Pick
    {
        get => pick;
        set
        {
            if (!Set(ref pick, value)) return;
            foreach (var r in Rows) r.Changed();
            RaiseAll(nameof(Again), nameof(GoText));
            GoCommand.Changed();
        }
    }

    string? Version => Main.Service.NewestOf(pick);
    public bool Again => Has(Version);
    public string GoText => Version == null ? Tr.T("Continue") : Tr.F(Again ? "Rebuild {0}" : "Continue with {0}", Versions.Shown(Version));

    void Go()
    {
        Main.Modal = null;
        Main.Home.StartBuild(pick);
    }
}

/// Deleting a build: what goes with it (its folder; never the saves, which every build shares), and who becomes the default
public sealed class DeleteViewModel : ViewModelBase
{
    readonly BuildItemViewModel build;

    public DeleteViewModel(MainViewModel main, BuildItemViewModel build)
    {
        Main = main;
        this.build = build;
        KeepCommand = new Command(() => Main.Modal = null);
        DeleteCommand = new Command(() => _ = DeleteAsync());
    }

    public MainViewModel Main { get; }
    public string Title => Tr.F("Delete {0}?", build.Version);
    bool GameFolderHere => GameFolder.IsGameFolder(build.Entry.Folder, Main.Platform);

    public string Sub => GameFolderHere
        ? build.Entry.Bytes is long b ? Tr.F("This deletes its folder and frees {0}:", Durations.Size(b)) : Tr.T("This deletes its folder:")
        : Tr.T("This takes it off your versions. Its folder is not a Hookshot game folder, so it stays on the disk:");
    public string Folder => ShownPath.Of(build.Entry.Folder);
    public string FolderFull => build.Entry.Folder;

    BuildEntry? Next => Main.Service.Registry.Builds.FirstOrDefault(b => b.Id != build.Entry.Id);
    public bool DefaultNote => build.IsDefault && Next != null;
    public string DefaultText => Next is { } n ? Tr.F("It is your default: Play will start {0} instead.", n.Version is { } v ? Versions.Shown(v) : n.Name) : "";

    public Command KeepCommand { get; }
    public Command DeleteCommand { get; }

    async Task DeleteAsync()
    {
        Main.Modal = null;
        var service = Main.Service;
        var entry = build.Entry;
        var files = GameFolderHere;
        // (a running game holds its files: on Windows the delete would stop half-way through the folder)
        if (files && Saves.Running(service.Platform).Contains(Saves.Hookshot.Display))
        {
            Main.Home.Notice = Tr.F("Close Hookshot first: {0} is not deleted while a game runs.", build.Version);
            return;
        }
        try
        {
            if (files)
            {
                // (tens of GB: off the window's thread, the folder first and the row once it is gone)
                var keep = service.KeepOf(entry);
                Main.ShowToast(Tr.F("Deleting {0}…", build.Version));
                Main.Home.Deleting(entry, true);
                try { await Task.Run(() => BuildRegistry.DeleteFolder(entry.Folder, service.Platform, keep)); }
                finally { Main.Home.Deleting(entry, false); }
            }
            // (the default goes to a release when there is one left, as the mockup: Registry.Remove takes the first otherwise)
            var wasDefault = build.IsDefault;
            service.Remove(entry, deleteFiles: false);
            if (wasDefault && service.Registry.Builds.FirstOrDefault(b => UpdatePolicy.ChannelOf(b.Channel, b.Version) == Versions.Stable) is { } rel)
                service.SetDefault(rel);
            Main.ShowToast(entry.Bytes is long b && files ? Tr.F("Deleted {0}, {1} freed.", build.Version, Durations.Size(b)) : Tr.F("Deleted {0}.", build.Version));
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            Main.Home.Notice = Tr.F("{0} could not be deleted: {1}", entry.Folder, e.Message);
        }
        Main.Home.Refresh();
    }
}
