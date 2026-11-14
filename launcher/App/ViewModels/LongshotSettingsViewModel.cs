using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

/// Longshot's compatible settings copied into one installed Hookshot version, separately from saves.
public sealed class LongshotSettingsViewModel : ViewModelBase
{
    string? sourceFolder;
    BuildEntry? target;
    LongshotSettingsCopy? preview;
    IReadOnlyList<string> files = Array.Empty<string>();
    string? problem;
    bool busy;
    readonly bool severalSources;

    public LongshotSettingsViewModel(MainViewModel main)
    {
        Main = main;
        BackCommand = new Command(() => Main.Modal = new LongshotImportViewModel(Main));
        CloseCommand = new Command(() => Main.Modal = null);
        PickFolderCommand = new Command(() => _ = PickFolderAsync());
        ImportCommand = new Command(Import, () => CanImport);
        Targets = main.Service.Registry.Builds.Where(main.Service.IsBuilt).ToList();
        // (no version chosen for the player: the import changes the one they pick, and Import waits for that choice)
        target = null;
        var roots = LongshotSaves.Roots(main.Service.SaveEnv)
            .Where(r => File.Exists(Path.Combine(r, "longshot_options.ini")) || File.Exists(Path.Combine(r, "language.txt")))
            .ToList();
        severalSources = roots.Count > 1;
        sourceFolder = roots.Count == 1 ? roots[0] : null;
        Refresh();
    }

    public MainViewModel Main { get; }
    public IReadOnlyList<BuildEntry> Targets { get; }
    public bool HasTargets => Targets.Count > 0;
    public bool NoTargets => !HasTargets;
    public string SourcePath => ShownPath.Of(sourceFolder);
    public bool HasSource => sourceFolder != null;
    public string SourceHint => severalSources
        ? Tr.T("Several Longshot folders have settings. Choose the game folder you want to import from.")
        : Tr.T("Choose your Longshot game folder, which holds longshot_options.ini or language.txt.");
    public string TargetPath => ShownPath.Of(Target?.Folder);
    public bool HasTarget => Target != null;
    public bool NeedsTarget => HasTargets && !HasTarget;
    public string FilesText => files.Count > 0 ? Tr.F("Files to import: {0}.", string.Join(", ", files)) : "";
    public bool HasFiles => files.Count > 0;
    public string BackupText => preview?.Backup is { } backup
        ? Tr.F("Existing files will be backed up in {0}.", ShownPath.Of(backup))
        : Tr.T("There are no matching Hookshot files to back up.");
    public bool HasPreview => preview != null;
    public string SkippedText => preview is { SkippedKeys.Count: > 0 } copy
        ? Tr.P(copy.SkippedKeys.Count, "1 Longshot option is unknown to Hookshot or has a value it does not take, and will be skipped: {1}.",
               "{0} Longshot options are unknown to Hookshot or have a value it does not take, and will be skipped: {1}.",
               string.Join(", ", copy.SkippedKeys))
        : "";
    public bool HasSkipped => preview?.SkippedKeys.Count > 0;
    /// (make_game.py writes the launcher's game language, when one is set, into language.txt at each update: the imported one
    /// becomes the launcher's too, or the next update would undo it)
    string? LanguageChange => preview?.Language is { } imported && Languages.Normalize(Main.Service.Settings.Language) is { } current
                              && current != imported ? imported : null;
    public string LanguageText => LanguageChange is { } language
        ? Tr.F("The launcher's game language also becomes {0}, so updating this version keeps it. Other versions take it when they are next updated.",
               Tr.T(Languages.NameOf(language)))
        : "";
    public bool HasLanguageText => LanguageChange != null;
    public string? Problem => problem;
    public bool HasProblem => problem != null;
    public bool CanImport => !busy && preview != null;

    public BuildEntry? Target
    {
        get => target;
        set
        {
            if (Set(ref target, value)) Refresh();
        }
    }

    public Command BackCommand { get; }
    public Command CloseCommand { get; }
    public Command PickFolderCommand { get; }
    public Command ImportCommand { get; }

    async Task PickFolderAsync()
    {
        if (Main.Host is not { } host) return;
        var folder = await host.PickFolderAsync(Tr.T("Your Longshot game folder"), sourceFolder);
        if (folder == null) return;
        sourceFolder = folder;
        Refresh();
    }

    void Refresh()
    {
        problem = null;
        preview = null;
        files = Array.Empty<string>();
        try
        {
            if (sourceFolder != null)
            {
                files = LongshotSettings.FilesIn(sourceFolder);
                if (Target != null)
                    preview = LongshotSettings.Import(sourceFolder, Target.Folder, Main.Service.SaveEnv.BackupRoot, overwrite: false, dryRun: true);
            }
        }
        catch (Exception e) when (e is SaveFailure or IOException or UnauthorizedAccessException) { problem = e.Message; }
        Changed();
    }

    void Import()
    {
        if (!CanImport || sourceFolder == null || Target == null) return;
        busy = true;
        problem = null;
        Changed();
        try
        {
            if (!Main.Service.IsBuilt(Target)) throw new SaveFailure(Tr.T("This Hookshot version is no longer built. Build it before importing settings."));
            var language = LanguageChange;
            var done = LongshotSettings.Import(sourceFolder, Target.Folder, Main.Service.SaveEnv.BackupRoot, overwrite: true);
            if (language != null && done.Language == language)
            {
                Main.Service.Settings.Language = language;
                try { Main.Service.SaveSettings(); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            }
            Main.Modal = null;
            Main.ShowToast(done.Backup != null
                ? Tr.F("Imported Longshot settings into {0}. The earlier files are in {1}.", Target.Name, ShownPath.Of(done.Backup))
                : Tr.F("Imported Longshot settings into {0}.", Target.Name));
            Main.Home.Refresh();
        }
        catch (Exception e) when (e is SaveFailure or IOException or UnauthorizedAccessException)
        {
            problem = e is SaveFailure { Backup: { } backup } ? Tr.Sentences(e.Message, Tr.F("Backup: {0}.", ShownPath.Of(backup))) : e.Message;
        }
        finally
        {
            busy = false;
            Changed();
        }
    }

    void Changed()
    {
        RaiseAll(nameof(SourcePath), nameof(HasSource), nameof(TargetPath), nameof(HasTarget), nameof(NeedsTarget), nameof(FilesText), nameof(HasFiles),
                 nameof(BackupText), nameof(HasPreview), nameof(SkippedText), nameof(HasSkipped), nameof(LanguageText), nameof(HasLanguageText), nameof(Problem), nameof(HasProblem), nameof(CanImport));
        ImportCommand.Changed();
    }
}
