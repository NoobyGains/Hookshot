using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

/// Import saves from Longshot (Core/LongshotSaves.cs): the saves found, each with its slots and when they were saved; a folder
/// chosen by hand when none is found; and, when Hookshot already has a save there, the question whether to replace it (backed up
/// first). Opened from Saves, or from the home's offer the first time Longshot saves are found.
public sealed class LongshotImportViewModel : ViewModelBase
{
    public sealed class Source(LongshotImportViewModel owner, LongshotSource source) : ViewModelBase
    {
        public LongshotSource Value => source;
        public string Where => ShownPath.Of(source.Path);
        public string WhereFull => source.Path;
        public string Summary => source.Valid ? SaveText.Long(source.Slots, DateTime.Now) : Tr.F("Cannot be imported: {0}", string.Join("; ", source.Problems));
        public bool Valid => source.Valid;
        public Command ImportCommand { get; } = new(() => owner.Choose(source), () => source.Valid);
    }

    LongshotSource? chosen;
    string? target;
    string? problem;
    bool busy;

    public LongshotImportViewModel(MainViewModel main)
    {
        Main = main;
        CloseCommand = new Command(() => Main.Modal = null);
        PickFolderCommand = new Command(() => _ = PickFolderAsync());
        SettingsCommand = new Command(() => Main.Modal = new LongshotSettingsViewModel(Main));
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
        ? Tr.T("No Longshot save in ~/.local/share/longshot. If yours are somewhere else, choose the folder.")
        : Tr.T("No Longshot save in Games\\Longshot in your user folder. If your Longshot game folder is somewhere else, choose it.");
    public string Sub => Tr.T("Your Longshot saves are copied into Hookshot. They stay in Longshot as they are.");

    /// Asking: the chosen save would replace a Hookshot save
    public bool Asking => chosen != null && target != null;
    public bool Listing => !Asking;
    public string AskText => chosen == null || target == null ? ""
        : Tr.F("Hookshot already has a save in {0}. Replace it with Longshot's ({1})? Hookshot's save is backed up first.",
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
        Sources.AddRange(LongshotSaves.Find(Env, folder).Select(s => new Source(this, s)));
        if (folder != null && Sources.Count == 0) Problem = Tr.F("No Longshot save in {0}: choose the folder that holds account.sav and the slot folders, or a Longshot game folder.", ShownPath.Of(folder));
        RaiseAll(nameof(Sources), nameof(HasSources), nameof(NoSources));
    }

    async Task PickFolderAsync()
    {
        if (Main.Host is not { } host) return;
        var folder = await host.PickFolderAsync(Tr.T("Your Longshot saves, or your Longshot game folder"), null);
        if (folder == null) return;
        Problem = null;
        Load(folder);
    }

    void Choose(LongshotSource source)
    {
        Problem = null;
        try
        {
            var to = Saves.ImportTarget(Env);
            chosen = source;
            if (LongshotSaves.WouldReplace(to))
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
                throw new SaveFailure(Tr.T("Hookshot's save location changed. Choose the Longshot save again and review the import."));
            var done = LongshotSaves.Import(chosen, target, Env.BackupRoot, overwrite);
            Main.Service.Settings.LongshotSavesAsked = true;
            Main.Home.LongshotOffer = null;
            try { Main.Service.SaveSettings(); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            Main.Modal = null;
            Main.ShowToast(done.Backup != null
                ? Tr.P(done.Slots.Count, "Imported 1 save slot from Longshot. Hookshot's earlier save is in {1}",
                       "Imported {0} save slots from Longshot. Hookshot's earlier save is in {1}", ShownPath.Of(done.Backup))
                : Tr.P(done.Slots.Count, "Imported 1 save slot from Longshot.", "Imported {0} save slots from Longshot."));
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
