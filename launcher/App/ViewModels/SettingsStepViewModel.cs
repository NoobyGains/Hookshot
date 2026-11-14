using HookshotLauncher.Core;

namespace HookshotLauncher.ViewModels;

public sealed record Choice(int? Value, string Label);

public sealed record LanguageChoice(string Code, string Name);

/// Step 2, the build settings (LauncherSettings, remembered for the next build): the saves it shares, DLSS and FSR 4 with
/// their licences, the game folder and the space it needs, the language, the shaders, and under Advanced the build's memory,
/// workers and build files
public sealed class SettingsStepViewModel : ViewModelBase, IWizardPage
{
    readonly LauncherSettings s;
    long? free;

    public SettingsStepViewModel(BuildJob job)
    {
        Job = job;
        job.Settings = this;
        s = job.Service.Settings;
        var memory = SystemInfo.MemoryGb();
        var threads = SystemInfo.Threads();
        MemoryGb = memory;
        Threads = threads;
        // (the 2.x Builder's choices: Automatic, then every 4 GB of the PC's, every CPU thread)
        MemoryChoices = new[] { new Choice(null, Tr.T("Automatic")) }
            .Concat(Enumerable.Range(1, Math.Max(1, (memory + 3) / 4)).Select(i => new Choice(i * 4, Tr.F("{0} GB", i * 4)))).ToList();
        WorkerChoices = new[] { new Choice(null, Tr.T("Automatic")) }
            .Concat(Enumerable.Range(1, Math.Max(1, threads)).Select(i => new Choice(i, Tr.F("{0} at once", i)))).ToList();
        LanguageChoices = Languages.All.Select(l => new LanguageChoice(l.Code, Tr.T(l.Name))).ToList();
        BackCommand = new Command(() => job.Main.Navigate(job.Files ?? new FilesStepViewModel(job)));
        StartCommand = new Command(Start, () => !Short);
        ChangeInstallCommand = new Command(() => _ = ChangeInstallAsync());
        ChangeWorkCommand = new Command(() => _ = ChangeWorkAsync());
        AdvancedCommand = new Command(() => AdvancedOpen = !AdvancedOpen);
        Measure();
    }

    public BuildJob Job { get; }
    MainViewModel Main => Job.Main;
    public int Step => 2;
    public bool Finished => false;
    public bool Linux => Main.Linux;
    public bool Windows => !Main.Linux;
    public int MemoryGb { get; }
    public int Threads { get; }

    void Save()
    {
        try { Job.Service.SaveSettings(); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
    }

    // ---- saves ----

    /// (every build uses the same saves: said once there is a build, so nobody looks for a way to move them; not for a rebuild)
    public bool ShowSharedSaves => Job.Kind != JobKind.Rebuild && Job.Service.Registry.Builds.Count > 0;

    public string SharedDesc => Tr.F("Every version uses the same saves: {0}.", SaveText.Long(Job.Service.SaveSlots(), DateTime.Now));

    // ---- upscaling ----

    public bool DlssYourGpu => Job.Service.Gpus.Contains(SystemInfo.Nvidia);
    public bool FsrYourGpu => Job.Service.Gpus.Contains(SystemInfo.Amd);

    public bool Dlss
    {
        get => s.Dlss;
        set
        {
            if (value == s.Dlss) return;
            if (value && !s.DlssLicense)
            {
                Main.Modal = new LicenceViewModel(Main, true, Linux, () => { s.DlssLicense = true; s.Dlss = true; Save(); RaiseUpscalers(); },
                                                  RaiseUpscalers);
                Raise();
                return;
            }
            s.Dlss = value;
            Save();
            RaiseUpscalers();
        }
    }

    /// AMD's licence (Windows) or the Linux notice (FsrLinuxNotice), whichever this platform asks for before FSR 4 is on
    bool FsrKnown => Linux ? s.FsrLinuxNotice : s.FsrLicense;

    /// (Linux) This version's tools can build FSR 4: they carry AMD's FSR API headers (MakeGameCommand.FsrBuilds). Unknown
    /// tools (not found yet) are taken as able: the build says so in its log if they were not
    public bool FsrBuildable => Windows || Job.Tools is not { } tools || MakeGameCommand.FsrBuilds(tools, Platform.Linux);

    public bool Fsr
    {
        get => s.Fsr && FsrKnown && FsrBuildable;
        set
        {
            if (value == Fsr || (value && !FsrBuildable)) return;
            if (value && !FsrKnown)
            {
                Main.Modal = new LicenceViewModel(Main, false, Linux, () =>
                {
                    if (Linux) s.FsrLinuxNotice = true;
                    else s.FsrLicense = true;
                    s.Fsr = true;
                    Save();
                    RaiseUpscalers();
                }, RaiseUpscalers);
                Raise();
                return;
            }
            s.Fsr = value;
            Save();
            RaiseUpscalers();
        }
    }

    public bool DlssAccepted => s.Dlss;
    public string DlssLine => s.Dlss ? "" : s.DlssLicense ? Tr.T("Licence accepted earlier.") : Tr.T("Shows NVIDIA's licence first.");
    // (Linux: nothing of AMD's is downloaded, so there is no licence to accept; the player's own library goes beside the game)
    public bool FsrAccepted => s.Fsr && Windows;
    public string FsrLine => Linux
        ? (!FsrBuildable ? Tr.T("This version can't build it on Linux yet.") :
           Fsr ? Tr.T("Put amd_fidelityfx_upscaler_vk.so beside the game.") : Tr.T("Needs your own Vulkan FSR 4 library."))
        : Fsr ? "" : s.FsrLicense ? Tr.T("Licence accepted earlier.") : Tr.T("Shows AMD's licence first.");

    void RaiseUpscalers() =>
        RaiseAll(nameof(Dlss), nameof(Fsr), nameof(DlssAccepted), nameof(DlssLine), nameof(FsrAccepted), nameof(FsrLine), nameof(FsrBuildable),
                 nameof(Estimate));

    // ---- install ----

    public string InstallDir => ShownPath.Of(Job.InstallDir);
    public string InstallDirFull => Job.InstallDir;

    async Task ChangeInstallAsync()
    {
        if (Main.Host is not { } host) return;
        var picked = await host.PickFolderAsync(Tr.F("Where to install {0}", Job.Shown), Path.GetDirectoryName(Job.InstallDir));
        if (picked == null) return;
        // (a folder that holds other things gets the version's own folder in it; an empty one, or a game folder, is used as it is)
        var full = Path.GetFullPath(picked);
        var used = !Directory.Exists(full) || !Directory.EnumerateFileSystemEntries(full).Any() || GameFolder.IsGameFolder(full, Main.Platform)
            ? full : LauncherSettings.FolderFor(full, Job.Version, p => Job.Service.Registry.FindByFolder(p) is { } e && e.Id != Job.Replaces?.Id);
        Job.InstallDir = used;
        RaiseAll(nameof(InstallDir), nameof(InstallDirFull));
        Measure();
    }

    /// The free space where the game goes (null: unknown, taken as enough)
    public long? Free
    {
        get => free;
        set
        {
            free = value;
            RaiseAll(nameof(Free), nameof(Short), nameof(MeterText), nameof(MeterFraction), nameof(Estimate), nameof(SpaceWarning), nameof(ShowEstimate));
            StartCommand.Changed();
        }
    }

    public string Drive => Disk.DriveName(Job.InstallDir);
    void Measure() => Free = Disk.FreeBytes(Job.InstallDir);

    public bool Short => free is long f && f < Disk.BuildBytes;
    public double MeterFraction => free is long f && f > 0 ? Math.Min(1, Disk.BuildBytes / (double)f) : 0;
    public string MeterText => free is not long f ? Tr.F("Needs {0} GB", Disk.BuildBytes >> 30)
        : Short ? Tr.F("Needs {0} GB, only {1} GB free on {2}", Disk.BuildBytes >> 30, f >> 30, Drive)
        : Tr.F("Needs {0} GB, {1} GB free on {2}", Disk.BuildBytes >> 30, f >> 30, Drive);

    // ---- the game ----

    public IReadOnlyList<LanguageChoice> LanguageChoices { get; }

    public LanguageChoice Language
    {
        get => LanguageChoices.FirstOrDefault(l => l.Code == Languages.Normalize(s.Language)) ?? LanguageChoices[0];
        set
        {
            if (value == null) return;
            s.Language = value.Code;
            Save();
            Raise();
        }
    }

    public bool Prepare
    {
        get => s.PrepareShaders;
        set
        {
            s.PrepareShaders = value;
            Save();
            RaiseAll(nameof(Prepare), nameof(PrepareDesc), nameof(Estimate));
        }
    }

    public string PrepareDesc => s.PrepareShaders ? Tr.T("Adds about 8 min here, so the game starts smoothly.") : Tr.T("The game prepares them at its first start.");

    // ---- advanced ----

    public bool AdvancedOpen
    {
        get => Job.AdvancedOpen;
        set
        {
            Job.AdvancedOpen = value;
            RaiseAll(nameof(AdvancedOpen), nameof(AdvancedDesc));
        }
    }

    public IReadOnlyList<Choice> MemoryChoices { get; }
    public IReadOnlyList<Choice> WorkerChoices { get; }

    public Choice Memory
    {
        get => MemoryChoices.FirstOrDefault(c => c.Value == s.MemoryGb) ?? MemoryChoices[0];
        set
        {
            if (value == null) return;
            s.MemoryGb = value.Value;
            Save();
            RaiseAll(nameof(Memory), nameof(MemoryDesc), nameof(AdvancedDesc));
        }
    }

    public Choice Workers
    {
        get => WorkerChoices.FirstOrDefault(c => c.Value == s.BuildWorkers) ?? WorkerChoices[0];
        set
        {
            if (value == null) return;
            s.BuildWorkers = value.Value;
            Save();
            RaiseAll(nameof(Workers), nameof(WorkersDesc), nameof(AdvancedDesc));
        }
    }

    // (make_game's automatic: the compilers take what memory is free (nx2/build.py MemoryGate); one per CPU thread, as it allows)
    public string MemoryDesc => s.MemoryGb == null ? Tr.F("Whatever is free of {0} GB, leaving room for your other programs.", MemoryGb)
        : Tr.T("The compilers may use this much, even if other programs need it.");
    public string WorkersDesc => s.BuildWorkers == null ? Tr.F("{0} of {1} at once, as the memory allows.", Threads, Threads)
        : Tr.T("Compilers running at once. Each needs about 2 GB.");
    public string Work => ShownPath.Of(Job.Service.Work);
    public string WorkFull => Job.Service.Work;

    public string AdvancedDesc => AdvancedOpen ? Tr.T("For a PC that slows down or runs out of memory while building.")
        : Tr.F("Memory {0}, {1}, build files on {2}",
               s.MemoryGb is int m ? Tr.F("{0} GB", m) : Tr.F("automatic of {0} GB", MemoryGb),
               s.BuildWorkers is int w ? Tr.P(w, "1 worker", "{0} workers") : Tr.F("{0} of {1} workers (automatic)", Threads, Threads),
               Disk.DriveName(WorkFull));

    async Task ChangeWorkAsync()
    {
        if (Main.Host is not { } host) return;
        var picked = await host.PickFolderAsync(Tr.T("Where the build files go"), WorkFull);
        if (picked == null) return;
        s.Work = Path.GetFullPath(picked);
        Save();
        RaiseAll(nameof(Work), nameof(WorkFull), nameof(AdvancedDesc));
    }

    // ---- the footer ----

    public bool ShowEstimate => !Short;
    public string SpaceWarning => Tr.F("{0} is too full for the build. Change the game folder.", Drive);
    // (this PC's estimate from its CPU threads: BuildForecast, measured on nightly-56; the build step then corrects it as it goes)
    public string Estimate => Tr.F(s.PrepareShaders ? "{0} on this PC, shaders included" : "{0} on this PC",
                                   Durations.About(BuildForecast.Total(download: true, s.PrepareShaders, BuildThreads(s))));

    /// The threads a build may use: the Build workers setting, else the PC's
    public static int BuildThreads(LauncherSettings settings) =>
        settings.BuildWorkers is int w and > 0 ? Math.Min(w, SystemInfo.Threads()) : SystemInfo.Threads();
    public string StartText => Job.StartText;
    public bool IsUpdate => Job.Kind == JobKind.Update;

    public Command BackCommand { get; }
    public Command StartCommand { get; }
    public Command ChangeInstallCommand { get; }
    public Command ChangeWorkCommand { get; }
    public Command AdvancedCommand { get; }

    void Start()
    {
        if (Short || Job.Picked == null || Job.Tools == null) return;
        var file = Job.Picked;
        // (the game files are remembered for the next build)
        if (file.Folders && file.Source is BuildSource.Folders f)
        {
            s.Nup = null;
            s.Romfs = f.Romfs;
            s.Exefs = f.Exefs;
        }
        else
        {
            s.Nup = file.Path;
            s.Romfs = s.Exefs = null;
        }
        Save();
        Main.Navigate(new BuildStepViewModel(Job));
    }
}

/// NVIDIA's licence for DLSS, or AMD's for FSR 4, shown when the switch is turned on: Accept keeps it on (and is remembered)
public sealed class LicenceViewModel : ViewModelBase
{
    readonly Action accepted, declined;

    public LicenceViewModel(MainViewModel main, bool nvidia, bool linux, Action accepted, Action declined)
    {
        Main = main;
        Nvidia = nvidia;
        this.accepted = accepted;
        this.declined = declined;
        Linux = linux;
        Text = nvidia ? DlssText(linux) : linux ? FsrLinuxText : FsrText;
        AcceptCommand = new Command(() => { Main.Modal = null; this.accepted(); });
        DeclineCommand = new Command(() => { Main.Modal = null; this.declined(); });
    }

    public MainViewModel Main { get; }
    public bool Nvidia { get; }
    public bool Linux { get; }
    public string AcceptText => !Nvidia && Linux ? Tr.T("Turn on") : Tr.T("Accept");
    public string Title => Nvidia ? Tr.T("NVIDIA's licence for DLSS") : Linux ? Tr.T("AMD FSR 4 on Linux") : Tr.T("AMD's licence for FSR 4");
    public string Sub => !Nvidia && Linux
        ? Tr.T("Nothing is downloaded: AMD publishes no FSR 4 runtime for Linux. Nothing of AMD's comes with Hookshot.")
        : Nvidia ? Tr.T("The build downloads NVIDIA's DLSS SDK under this licence. Nothing of NVIDIA's comes with Hookshot.")
        : Tr.T("The build downloads AMD's FSR 4 runtime under this licence. Nothing of AMD's comes with Hookshot.");
    public string Text { get; }
    public Command AcceptCommand { get; }
    public Command DeclineCommand { get; }

    // (the 2.x Builders' texts: builder/HookshotBuilder/MainWindow.xaml.cs DlssLicense and FsrLicense, builder/linux DLSS_LICENSE)
    // (the licences' addresses and the files' names stay as they are in every language)
    static string DlssText(bool linux) =>
        Tr.F("NVIDIA DLSS is NVIDIA's, not Hookshot's. With it on, the build downloads NVIDIA's DLSS SDK (release {0}) from " +
             "{1}, under NVIDIA's own license, the NVIDIA RTX SDKs license:", "v310.9.16", "github.com/NVIDIA/DLSS") + "\n\n" +
        "https://github.com/NVIDIA/DLSS/blob/9981c6350dc58c0ce21f024fd65e31e851c31689/LICENSE.txt\n\n" +
        Tr.F("Its files stay on this PC (in the launcher's {0} folder, and {1} in the game folder's {2} folder). " +
             "Hookshot never includes or shares them: never share a game folder built with them.", "ngx-sdk",
             linux ? "libnvidia-ngx-dlss.so, libnvidia-ngx-dlssg.so" : "nvngx_dlss.dll, nvngx_dlssg.dll", "ngx");

    static string FsrText =>
        Tr.F("AMD FSR 4 is AMD's, not Hookshot's. With it on, the build downloads AMD's FSR runtime for Vulkan ({0}: {1}, signed by AMD) " +
             "from {2}, each file checked against its SHA-256, under AMD's FSR SDK license:", "FidelityFX SDK v2.4.0",
             "amd_fidelityfx_loader_vk.dll, amd_fidelityfx_upscaler_vk.dll", "github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK") + "\n\n" +
        "https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/7539ae8b6568ad29ed78a753404351daf3b5cca7/Kits/FidelityFX/docs/license.md\n\n" +
        Tr.F("Its files stay on this PC (in the launcher's {0} folder, and the two DLLs with {1} in the game folder).", "ffx-sdk", "LICENSE-AMD-FSR-SDK.md");

    // (Linux: Hookshot's README, AMD FSR 4. The build compiles the Vulkan back end with AMD's MIT FSR API headers; the library
    // is the player's, loaded by the game at its start)
    static string FsrLinuxText =>
        Tr.F("AMD FSR 4 is AMD's, not Hookshot's. AMD publishes its FSR 4 runtime for Windows only, so on Linux the build downloads " +
             "nothing: it compiles the game's Vulkan renderer with FSR 4 in it (a few minutes longer), and FSR 4 runs once you put a " +
             "Vulkan FSR 4 library, {0}, beside the game (in its folder or its bin folder). Where you get " +
             "it and under which terms is yours to check.", "amd_fidelityfx_upscaler_vk.so") + "\n\n" +
        Tr.T("Without it, the game's Upscaler row says AMD's files were not found and offers the other upscalers.");
}
