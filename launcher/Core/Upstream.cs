namespace HookshotLauncher.Core;

/// What this launcher is based on: the Magic Bean team's Longshot Launcher (GPL-3.0-or-later), taken whole at Commit and made the
/// Hookshot Launcher (docs/launcher.md says what changed, and how its later changes are taken). Settings' About names it;
/// launcher/README.md and docs/launcher.md name the same commit (tests/test_launcher_core.py)
public static class Upstream
{
    public const string Name = "Longshot Launcher";
    public const string Url = "https://git.magicbean.dev/MagicBeanDev/LongshotLauncher";
    public const string Commit = "9b3d202b0e6398bfa88bfbc3b86295f0decd4d4c";
    public static string Short => Commit[..8];
}
