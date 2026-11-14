using System.Text.Json;

namespace HookshotLauncher.Core;

/// What the build wizard remembers (&lt;home&gt;/settings.json): the game files last picked, the build's options and the channel new
/// builds start on. A license flag is true only once its license was accepted on its tick.
public sealed class LauncherSettings
{
    /// 2: defaultChannel is null until the player picks one (format 1 wrote "stable" for everyone; Load reads it as not picked)
    public const int CurrentFormat = 2;
    public int Format { get; set; } = CurrentFormat;
    public string? Nup { get; set; }
    public string? Romfs { get; set; }
    public string? Exefs { get; set; }
    public string? Language { get; set; }
    /// The launcher's own language (Tr.All's code), apart from the game's (Language); null: the system's, else English
    public string? UiLanguage { get; set; }
    public bool Dlss { get; set; }
    public bool DlssLicense { get; set; }
    public bool Fsr { get; set; }
    public bool FsrLicense { get; set; }
    /// (Linux) The AMD FSR 4 notice read: nothing of AMD's is downloaded there, so no licence is accepted, and FsrLicense is left
    /// as it was (a launcher home shared with Windows must not take this for AMD's licence)
    public bool FsrLinuxNotice { get; set; }
    public bool PrepareShaders { get; set; } = true;
    /// Build memory in GB (HOOKSHOT_MEM_LIMIT_GB); null: Automatic
    public int? MemoryGb { get; set; }
    /// Build workers (HOOKSHOT_JOBS / --jobs); null: Automatic
    public int? BuildWorkers { get; set; }
    /// make_game.py's --work; null: the launcher's own (LauncherHome.Work)
    public string? Work { get; set; }
    /// The channel new builds start on, as the player picked it in Settings; null: not picked, so it follows the launcher (BuildChannel)
    public string? DefaultChannel { get; set; }
    /// The channel the launcher updates itself from (its own releases, apart from Hookshot's); null: its own version's track
    public string? LauncherChannel { get; set; }
    /// The player answered the offer to import Longshot's saves (imported, or Not now): it is not offered again at start
    public bool LongshotSavesAsked { get; set; }
    /// The player answered the offer to import NX2navi's saves (imported, or Not now)
    public bool Nx2naviSavesAsked { get; set; }
    /// Where new builds go, each version in its own folder; null: DefaultBuildsFolder
    public string? BuildsFolder { get; set; }
    /// Ask GitHub for each channel's newest version when the launcher starts
    public bool CheckUpdates { get; set; } = true;
    /// Each build folder's log already shown on the problem page, by its write time: a crash is shown once
    public Dictionary<string, long> SeenCrashLogs { get; set; } = new();
    /// When the launcher first looked for crashes (UTC ticks; null: not yet): a log from before then is not offered, so the first
    /// start with the check doesn't bring up a crash from weeks ago
    public long? CrashChecksSince { get; set; }

    /// The channel new builds start on: the one the player picked, else the launcher's own (a nightly launcher builds nightlies, an rc
    /// launcher release candidates; LauncherChannel when set, else its own version's track)
    public string BuildChannel(string ownTag) => DefaultChannel ?? SelfUpdate.ChannelOf(ownTag, LauncherChannel);

    /// The folder builds go in when none was chosen: make_game.py's own default game folder's parent, ~/Games/Hookshot
    /// (%USERPROFILE%\Games\Hookshot on Windows)
    public static string DefaultBuildsFolder(Func<string, string?>? getenv = null) =>
        Path.Combine(LauncherHome.Home(getenv ?? Environment.GetEnvironmentVariable), "Games", "Hookshot");

    public string BuildsFolderOrDefault(Func<string, string?>? getenv = null) =>
        string.IsNullOrWhiteSpace(BuildsFolder) ? DefaultBuildsFolder(getenv) : BuildsFolder;

    /// A new build's folder: the version's name in the builds folder, with " (2)" and so on when that is taken by something that
    /// is not the build being replaced
    public static string FolderFor(string buildsFolder, string version, Func<string, bool>? taken = null)
    {
        taken ??= p => Directory.Exists(p) || File.Exists(p);
        var name = Versions.IsTagName(version) ? version : "Hookshot";
        var path = Path.Combine(buildsFolder, name);
        for (var n = 2; taken(path); n++) path = Path.Combine(buildsFolder, $"{name} ({n})");
        return path;
    }

    /// The launcher's language: the one picked, else the system's (its name for it: de-DE, pt_BR.UTF-8), else English
    public string UiLanguageOr(string? system) => UiLanguage ?? Tr.Pick(system) ?? Tr.English;

    /// The saved settings, or the defaults when there are none or they cannot be read
    public static LauncherSettings Load(string path)
    {
        try
        {
            var s = JsonSerializer.Deserialize(File.ReadAllText(path), CoreJson.Default.LauncherSettings) ?? new LauncherSettings();
            if (s.Format < CurrentFormat)
            {
                // (format 1 saved its own default, "stable", for every player who never picked: that one is not a pick)
                if (s.DefaultChannel == Versions.Stable) s.DefaultChannel = null;
                s.Format = CurrentFormat;
            }
            return s.Checked();
        }
        catch (Exception e) when (e is JsonException or IOException or UnauthorizedAccessException or NotSupportedException)
        {
            return new LauncherSettings();
        }
    }

    LauncherSettings Checked()
    {
        if (DefaultChannel != null && !Versions.IsChannel(DefaultChannel)) DefaultChannel = null;
        if (LauncherChannel != null && !Versions.IsChannel(LauncherChannel)) LauncherChannel = null;
        UiLanguage = Tr.Pick(UiLanguage);
        if (MemoryGb is <= 0) MemoryGb = null;
        if (BuildWorkers is <= 0) BuildWorkers = null;
        if (!DlssLicense) Dlss = false;   // (a tick saved before its license was accepted is not one)
        if (!FsrLicense && !FsrLinuxNotice) Fsr = false;
        SeenCrashLogs ??= new();
        return this;
    }

    public void Save(string path) => AtomicFile.Write(path, JsonSerializer.Serialize(Checked(), CoreJson.Default.LauncherSettings));
}
