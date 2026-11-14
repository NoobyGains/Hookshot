using System.Globalization;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// One part of a version's tools: a zip checked by its SHA-256 and size, unpacked under Dest of the version's folder.
/// From/To: only the zip's folder From is taken, renamed To (tools.lock's prefix, made the last name of its dest).
/// Mirrors: other links to the same bytes, tried when Url fails or gives others (tools.lock's fallbacks: where each tool came from).
public sealed record Part(string Sha, long Size, string Dest, string? From, string? To, string Url, IReadOnlyList<string>? Mirrors = null)
{
    /// The same part for reuse: the same bytes, unpacked to the same place in the same way
    public bool Same(Part other) => other.Sha == Sha && other.Dest == Dest && other.From == From && other.To == To;
}

/// What made a version's tools: Setup, the Windows builder's zip and its tools.lock; Linux, the AppImage and the tools.lock in it
public enum ListKind { Setup, Linux }

/// A version's parts. Run: the Windows builder, relative to the install
public sealed record PartsList(ListKind Kind, string Tag, IReadOnlyList<Part> Parts, string? Run);

/// Hookshot's tools.lock (docs/releases.md, "tools.lock"; scripts/tools.py and builder/setup/setup.c read it the same way):
///     tool &lt;name&gt; &lt;version&gt; &lt;system&gt; &lt;sha256&gt; &lt;size&gt; &lt;dest&gt; &lt;prefix&gt; &lt;url&gt; [&lt;url&gt; ...]
/// Each tool is a part of a builder's install (windows-x64: the Windows builder's; linux-x64: beside the unpacked Linux AppImage,
/// from the tools.lock inside it): its archive's &lt;prefix&gt; folder ("-": all of it) becomes &lt;dest&gt;.
/// The first URL is tried first (Hookshot's copy, a generic package of the MagicBeanDev organization), the others (where the
/// archive came from) when it fails or gives other bytes. A tool another
/// installed version has (the same SHA-256, unpacked the same way) is taken from it, not downloaded again (Toolchains).
public static class ToolsLock
{
    /// The builder in the release zip, beside its tools (the setup's run line)
    public const string Run = "HookshotBuilder/HookshotBuilder.exe";
    static readonly Regex Sha256 = new("^[0-9a-f]{64}$", RegexOptions.CultureInvariant);
    static readonly Regex Name = new("^[a-z0-9][a-z0-9._-]{0,63}$", RegexOptions.CultureInvariant);

    /// setup.c's list_name_ok: letters, digits and . _ + - (and with path, / or \ between the parts), no "." or ".." part, no root
    public static bool NameOk(string s, bool path)
    {
        if (s.Length == 0 || s[0] is '/' or '\\') return false;
        foreach (var c in s)
            if (!(char.IsAsciiLetterOrDigit(c) || c is '.' or '_' or '+' or '-' || (path && c is '/' or '\\'))) return false;
        foreach (var piece in path ? s.Split('/', '\\') : new[] { s })
            if (piece is "" or "." or "..") return false;
        return true;
    }

    /// A relative zip name with no ".." part
    public static bool SafeName(string s) =>
        s.Length > 0 && !s.StartsWith('/') && !s.Split('/').Contains("..");

    public static IReadOnlyList<Part> Parse(string text, string system)
    {
        var parts = new List<Part>();
        foreach (var raw in text.Split('\n'))
        {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith('#')) continue;
            var w = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (w[0] != "tool" || w.Length < 9) throw new FormatException("Not a tools.lock line: " + line);
            string name = w[1], sys = w[3], sha = w[4], dest = w[6], prefix = w[7];
            if (!Name.IsMatch(name) || !Sha256.IsMatch(sha) || !NameOk(dest, true) || dest.Contains('\\')
                || (prefix != "-" && (!NameOk(prefix, true) || prefix.Contains('\\')))
                || !long.TryParse(w[5], NumberStyles.None, CultureInfo.InvariantCulture, out var size) || size <= 0
                || w.Skip(8).Any(u => !u.StartsWith("https://", StringComparison.Ordinal)))
                throw new FormatException("A tools.lock line the builder does not accept: " + line);
            if (sys != system) continue;
            // (as a part: unpacked into dest's parent, its prefix folder renamed to dest's last name)
            var slash = dest.LastIndexOf('/');
            var parent = slash < 0 ? "." : dest[..slash];
            var leaf = dest[(slash + 1)..];
            parts.Add(prefix == "-"
                ? new Part(sha, size, dest, null, null, w[8], w.Skip(9).ToList())
                : new Part(sha, size, parent, prefix, leaf, w[8], w.Skip(9).ToList()));
        }
        return parts;
    }
}
