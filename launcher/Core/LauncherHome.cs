namespace LongshotLauncher.Core;

/// The launcher's own folder: %LOCALAPPDATA%\LongshotLauncher on Windows, ${XDG_DATA_HOME:-~/.local/share}/longshot/launcher on
/// Linux, LONGSHOT_LAUNCHER_HOME on both; a portable launcher's is beside it (LauncherLayout.PortableHome). Everything in it is
/// the launcher's.
public sealed class LauncherHome
{
    public const string Variable = "LONGSHOT_LAUNCHER_HOME";

    public string Root { get; }

    public LauncherHome(string root) => Root = Path.GetFullPath(root);

    /// Portable: this home is a portable launcher's, beside it (the default builds folder and the save backups are in it too)
    public bool Portable { get; init; }

    public static LauncherHome Resolve(Platform platform, Func<string, string?>? getenv = null, LauncherLayout? layout = null)
    {
        getenv ??= Environment.GetEnvironmentVariable;
        if (getenv(Variable) is { Length: > 0 } set) return new LauncherHome(set);
        if (layout?.PortableHome is { } portable) return new LauncherHome(portable) { Portable = true };
        if (platform == Platform.Windows) return new LauncherHome(Path.Combine(LauncherLayout.LocalAppData(getenv), "LongshotLauncher"));
        var data = getenv("XDG_DATA_HOME") is { Length: > 0 } x ? x : Path.Combine(Home(getenv), ".local", "share");
        return new LauncherHome(Path.Combine(data, "longshot", "launcher"));
    }

    internal static string Home(Func<string, string?> getenv) =>
        getenv("HOME") is { Length: > 0 } h ? h : Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

    public string Builds => Path.Combine(Root, "builds.json");
    public string Settings => Path.Combine(Root, "settings.json");
    public string Toolchains => Path.Combine(Root, "toolchains");
    /// make_game.py's --work unless the player chose another: the build files, kept between builds for a faster rebuild
    public string Work => Path.Combine(Root, "work");
    /// NVIDIA's DLSS SDK, fetched by make_game.py --fetch-ngx-sdk (LONGSHOT_NGX_SDK), and AMD's FSR runtime (LONGSHOT_FFX_SDK)
    public string NgxSdk => Path.Combine(Root, "ngx-sdk");
    public string FfxSdk => Path.Combine(Root, "ffx-sdk");
    /// A portable launcher's default builds folder and save backups (an installed one's are the system's: LauncherSettings,
    /// SaveEnvironment.BackupRoot)
    public string PortableBuilds => Path.Combine(Root, "builds");
    public string PortableSaveBackups => Path.Combine(Root, "save-backups");
    /// (Windows) A portable launcher's Longshot user folder, its saves, which every build it starts shares (SaveEnvironment.UserFolder)
    public string PortableUser => Path.Combine(Root, "user");
}
