using System.Globalization;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// Hookshot's setup lists, the files a release has for each system's builder (scripts/make_setup_parts.py,
/// scripts/linux/make_parts.py), read as the builder's own setup reads them:
///   hookshot-setup.txt (Windows; builder/setup/setup.c)
///       tag &lt;version&gt;
///       part &lt;sha256&gt; &lt;bytes&gt; &lt;folder under the install&gt; &lt;top folder in the zip to rename, or -&gt; &lt;new name, or -&gt; &lt;url&gt;
///       run &lt;the builder, relative to the install&gt;
///   hookshot-linux.txt (Linux; builder/linux/linux_update.py): its tag line is the version of the release's AppImage, which
///       carries every tool itself, so the launcher reads only that line from it
/// The list itself is checked against the release's SHA256SUMS before it is read; each part is then checked against the SHA-256
/// and size the list gives (Toolchains). Anything setup.c would refuse is refused here too: a name with a ".." part, a root or a
/// backslash, a link that is not https, a part with no size.
public static class SetupList
{
    public const string Windows = "hookshot-setup.txt", Linux = "hookshot-linux.txt";
    /// More parts than any release has had (setup.c takes 16): a list longer than this is not one
    public const int MaxParts = 64;
    static readonly Regex Sha256 = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant);

    /// The list a release has for platform's builder
    public static string NameFor(Platform platform) => platform == Platform.Windows ? Windows : Linux;

    /// The version the list is of (its tag line), or null when it has none that is a version name
    public static string? Tag(string text)
    {
        foreach (var raw in text.Split('\n'))
        {
            var w = raw.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (w.Length >= 2 && w[0] == "tag") return w.Length == 2 && Versions.IsTagName(w[1]) && ToolsLock.NameOk(w[1], false) ? w[1] : null;
        }
        return null;
    }

    /// hookshot-setup.txt as a version's parts (FormatException: not one the setup would take)
    public static PartsList Parse(string text)
    {
        string? tag = null, run = null;
        var parts = new List<Part>();
        foreach (var raw in text.Split('\n'))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#')) continue;
            var w = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            switch (w[0])
            {
                case "tag" when w.Length == 2 && tag == null:
                    tag = w[1];
                    break;
                case "run" when w.Length == 2 && run == null:
                    run = w[1];
                    break;
                case "part":
                    parts.Add(PartOf(w, line));
                    break;
                case "tag" or "run":
                    throw new FormatException("A setup list line the builder's setup does not accept: " + line);
                default:
                    break;   // (setup.c skips a line it does not know: a later list may say more)
            }
        }
        if (tag == null || !Versions.IsTagName(tag) || !ToolsLock.NameOk(tag, false)) throw new FormatException("The setup list names no version.");
        if (run == null || !ToolsLock.NameOk(run, true) || run.Contains('\\')) throw new FormatException("The setup list names no builder to run.");
        if (parts.Count == 0 || parts.Count > MaxParts) throw new FormatException($"The setup list has {parts.Count} parts.");
        return new PartsList(ListKind.Setup, tag, parts, run);
    }

    static readonly Regex PartsLink = new(@"^https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+/releases/download/builder-parts/([A-Za-z0-9._+-]+)$",
                                          RegexOptions.CultureInvariant);

    /// Other places the same part may be, tried when its own link fails (Toolchains): a part on a repository's builder-parts
    /// release, named by its SHA-256, is looked for under the same name on these repositories' builder-parts too (repos: the
    /// launcher's own, then the default). The setup lists of 2026-11 still named two parts on the deleted upstream repository
    /// (NotRexed's), which no longer answer; a part re-uploaded to builder-parts is then found without a new list. Each is
    /// checked by the list's SHA-256 all the same
    public static IReadOnlyList<string> Mirrors(string url, IEnumerable<string> repos)
    {
        if (PartsLink.Match(url) is not { Success: true } m) return Array.Empty<string>();
        return repos.Where(Repository.IsName).Select(r => $"https://github.com/{r}/releases/download/builder-parts/{m.Groups[1].Value}")
            .Where(u => !string.Equals(u, url, StringComparison.OrdinalIgnoreCase)).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
    }

    /// The list's parts with Mirrors' links for each
    public static PartsList WithMirrors(PartsList list, IEnumerable<string> repos)
    {
        var where = repos.ToList();
        return list with { Parts = list.Parts.Select(p => p with { Mirrors = Mirrors(p.Url, where) }).ToList() };
    }

    static Part PartOf(string[] w, string line)
    {
        if (w.Length != 7) throw new FormatException("A setup list line the builder's setup does not accept: " + line);
        string sha = w[1], dest = w[3], from = w[4], to = w[5], url = w[6];
        var ok = Sha256.IsMatch(sha)
                 && long.TryParse(w[2], NumberStyles.None, CultureInfo.InvariantCulture, out var size) && size > 0 && size <= ReleaseManifest.MaxFile
                 && (dest == "." || (ToolsLock.NameOk(dest, true) && !dest.Contains('\\')))
                 && (from == "-") == (to == "-")
                 && (from == "-" || (ToolsLock.NameOk(from, false) && ToolsLock.NameOk(to, false)))
                 && url.StartsWith("https://", StringComparison.Ordinal) && Uri.TryCreate(url, UriKind.Absolute, out _);
        if (!ok) throw new FormatException("A setup list line the builder's setup does not accept: " + line);
        return new Part(sha, long.Parse(w[2], NumberStyles.None, CultureInfo.InvariantCulture), dest,
                        from == "-" ? null : from, to == "-" ? null : to, url);
    }
}
