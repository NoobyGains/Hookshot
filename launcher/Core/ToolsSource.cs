namespace HookshotLauncher.Core;

/// How far the step 1 download is: Fraction 0..1 of Total bytes (all of the version's parts)
public sealed record ToolsDownloadProgress(double Fraction, long Total);

/// A version's builder and build tools for the wizard's first step: the installed ones, else its release's (Windows: the builder's
/// zip and the tools of its tools.lock; Linux: its AppImage and the tools of the tools.lock inside it), checked against the release's signed SHA256SUMS, installed with
/// Toolchains
public static class ToolsSource
{
    /// extract: how a Linux AppImage is unpacked (by default its own --appimage-extract; the tests pass theirs)
    public static async Task<Toolchain> EnsureAsync(Toolchains chains, Releases releases, string tag,
                                                    Action<ToolsDownloadProgress>? progress = null, CancellationToken cancel = default,
                                                    Func<string, string, CancellationToken, Task>? extract = null)
    {
        if (chains.Find(tag) is { } have)
        {
            progress?.Invoke(new ToolsDownloadProgress(1, 0));
            return have;
        }
        if (releases.Platform != Platform.Windows)   // (Linux: the release's AppImage, then the tools its tools.lock names)
        {
            var image = await releases.BuilderAsync(tag, cancel).ConfigureAwait(false);
            progress?.Invoke(new ToolsDownloadProgress(0, image.Size));
            return await chains.InstallAppImageAsync(tag, image, extract, p => progress?.Invoke(new ToolsDownloadProgress(p.Fraction, image.Size)),
                                                     cancel).ConfigureAwait(false);
        }
        var list = await releases.ToolsListAsync(tag, cancel).ConfigureAwait(false);
        var total = list.Parts.Sum(p => p.Size);
        progress?.Invoke(new ToolsDownloadProgress(0, total));
        return await chains.InstallAsync(list, p => progress?.Invoke(new ToolsDownloadProgress(p.Fraction, total)), cancel).ConfigureAwait(false);
    }
}
