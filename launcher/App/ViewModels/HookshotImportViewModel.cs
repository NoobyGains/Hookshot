using LongshotLauncher.Core;

namespace LongshotLauncher.ViewModels;

/// Import saves from Hookshot (Core/HookshotSaves.cs): the saves found, each with its slots and when they were saved; a folder
/// chosen by hand when none is found; and, when Longshot already has a save there, the question whether to replace it (backed up
/// first). Opened from Saves, or from the home's offer the first time Hookshot saves are found.
public sealed class HookshotImportViewModel : ViewModelBase
{
    public sealed class Source(HookshotImportViewModel owner, HookshotSource source) : ViewModelBase
    {
        public HookshotSource Value => source;
        public string Where => ShownPath.Of(source.Path);
        public string WhereFull => source.Path;
        public string Summary => source.Valid ? SaveText.Long(source.Slots, DateTime.Now) : Tr.F("Cannot be imported: {0}", string.Join("; ", source.Problems));
        public bool Valid => source.Valid;
        public Command ImportCommand { get; } = new(() => owner.Choose(source), () => source.Valid);
    }

    HookshotSource? chosen;
    string? target;
    string? problem;
    bool busy;

    public HookshotImportViewModel(MainViewModel main)
    {
        Main = main;
        CloseCommand = new Command(() => Main.Modal = null);
        PickFolderCommand = new Command(() => _ = PickFolderAsync());
        SettingsCommand = new Command(() => Main.Modal = new HookshotSettingsViewModel(Main));
        ReplaceCommand = new Command(() => Run(overwrite: true));
        KeepCommand = new Command(() => { chosen = null; RaiseAll(nameof(Asking), nameof(Listing)); });
        Load(null);
    }

    public MainViewModel Main { get; }
    SaveEnvironment Env => Main.Service.SaveEnv;

    public List<Source> Sources { get; } = new();
    public bool HasSources => Sources.Count > 0;
    public bool NoSources => Sources.Count == 0;
    public string NoneText => Main.Linux
        ? Tr.T("No Hookshot save in ~/.local/share/hookshot. If yours are somewhere else, choose the folder.")
        : Tr.T("No Hookshot save in Games\\Hookshot in your user folder. If your Hookshot game folder is somewhere else, choose it.");
    public string Sub => Tr.T("Your Hookshot saves are copied into Longshot. They stay in Hookshot as they are.");

    /// Asking: the chosen save would replace a Longshot save
    public bool Asking => chosen != null && target != null;
    public bool Listing => !Asking;
    public string AskText => chosen == null || target == null ? ""
        : Tr.F("Longshot already has a save in {0}. Replace it with Hookshot's ({1})? Longshot's save is backed up first.",
               ShownPath.Of(target), SaveText.Long(chosen.Slots, DateTime.Now));

    public string? Problem
    {
        get => problem;
        set { if (Set(ref problem, value)) Raise(nameof(HasProblem)); }
    }
    public bool HasProblem => problem != null;

    public Command CloseCommand { get; }
    public Command PickFolderCommand { get; }
    public Command SettingsCommand { get; }
    public Command ReplaceCommand { get; }
    public Command KeepCommand { get; }

    void Load(string? folder)
    {
        Sources.Clear();
        Sources.AddRange(HookshotSaves.Find(Env, folder).Select(s => new Source(this, s)));
        if (folder != null && Sources.Count == 0) Problem = Tr.F("No Hookshot save in {0}: choose the folder that holds account.sav and the slot folders, or a Hookshot game folder.", ShownPath.Of(folder));
        RaiseAll(nameof(Sources), nameof(HasSources), nameof(NoSources));
    }

    async Task PickFolderAsync()
    {
        if (Main.Host is not { } host) return;
        var folder = await host.PickFolderAsync(Tr.T("Your Hookshot saves, or your Hookshot game folder"), null);
        if (folder == null) return;
        Problem = null;
        Load(folder);
    }

    void Choose(HookshotSource source)
    {
        Problem = null;
        try
        {
            var to = Saves.ImportTarget(Env);
            chosen = source;
            if (HookshotSaves.WouldReplace(to))
            {
                target = to;
                RaiseAll(nameof(Asking), nameof(Listing), nameof(AskText));
                return;
            }
            target = to;
            Run(overwrite: false);
        }
        catch (SaveFailure e) { Problem = e.Message; }
    }

    void Run(bool overwrite)
    {
        if (busy || chosen == null || target == null) return;
        busy = true;
        try
        {
            if (Saves.ImportTarget(Env) != target)
                throw new SaveFailure(Tr.T("Longshot's save location changed. Choose the Hookshot save again and review the import."));
            var done = HookshotSaves.Import(chosen, target, Env.BackupRoot, overwrite);
            Main.Service.Settings.HookshotSavesAsked = true;
            Main.Home.HookshotOffer = null;
            try { Main.Service.SaveSettings(); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            Main.Modal = null;
            Main.ShowToast(done.Backup != null
                ? Tr.P(done.Slots.Count, "Imported 1 save slot from Hookshot. Longshot's earlier save is in {1}",
                       "Imported {0} save slots from Hookshot. Longshot's earlier save is in {1}", ShownPath.Of(done.Backup))
                : Tr.P(done.Slots.Count, "Imported 1 save slot from Hookshot.", "Imported {0} save slots from Hookshot."));
            Main.Home.Refresh();
            if (Main.Page is SavesViewModel saves) saves.Reload();   // (opened from Saves: its slots are the imported ones now)
        }
        catch (Exception e) when (e is SaveFailure or IOException or UnauthorizedAccessException)
        {
            chosen = null;
            target = null;
            RaiseAll(nameof(Asking), nameof(Listing));
            Problem = e.Message;
        }
        finally
        {
            busy = false;
        }
    }
}
