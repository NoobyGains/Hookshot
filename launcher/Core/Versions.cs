using System.Globalization;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// The channels and the version order (docs/launcher.md), for Hookshot's releases and the launcher's own:
///   stable   vX.Y.Z
///   rc       vX.Y.Z-rc.N (and every stable: the newest of both)
///   nightly  Hookshot's: git describe --long's name for main's commit, v2.3.0-rc.8-2-gf33ca75d (a fork with no tags of its own:
///            v0.0.0-0-g179d8124, or the commit alone, 179d8124, which its Linux AppImage is named by), the version in the
///            nightly's setup list (the builder's Updater.TrackOf: "-&lt;count&gt;-g&lt;commit&gt;" is the nightly). The launcher's:
///            nightly-&lt;commit count&gt;-&lt;commit&gt;, as the Longshot Launcher names its own
/// Hookshot's numbers start at v2.0.0 (the first with the builder the launcher installs), the launcher's at v1.0.0 (FirstMajor).
/// Nothing else is a version: it is on no track and never ordered. tests/test_launcher_core.py holds the vectors.
public static class Versions
{
    /// The three channels: stable (vX.Y.Z), rc (vX.Y.Z-rc.N, and the stables: the newest of both) and nightly (from main)
    public const string Stable = "stable", Candidate = "rc", Nightly = "nightly";
    public static readonly IReadOnlyList<string> Channels = new[] { Stable, Candidate, Nightly };

    static readonly Regex NightlyName = new(@"^nightly-([0-9]{1,9})-([0-9a-f]{8})(-dirty)?$", RegexOptions.CultureInvariant);
    static readonly Regex DescribeName = new(@"^v([0-9]{1,9})\.([0-9]{1,9})\.([0-9]{1,9})(?:-rc\.([0-9]{1,9}))?-([0-9]{1,9})-g([0-9a-f]{7,40})(-dirty)?$",
                                             RegexOptions.CultureInvariant);
    static readonly Regex CommitName = new(@"^[0-9a-f]{7,40}$", RegexOptions.CultureInvariant);
    static readonly Regex ReleaseName = new(@"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$", RegexOptions.CultureInvariant);
    static readonly Regex TagName = new(@"^[0-9A-Za-z._+-]{1,128}$", RegexOptions.CultureInvariant);

    /// The first major version of each product: Hookshot (the game and its builder) from v2.0.0, the launcher from v1.0.0. A number
    /// below it is no version of that product
    public const int FirstMajor = 2, LauncherFirstMajor = 1;

    public static bool IsChannel(string? channel) => channel is Stable or Candidate or Nightly;

    /// A nightly's name: the launcher's nightly-&lt;count&gt;-&lt;commit&gt;, git describe's for Hookshot's, or a commit alone
    public static bool IsNightly(string? version) =>
        version != null && (NightlyName.IsMatch(version) || DescribeName.IsMatch(version) || CommitName.IsMatch(version));

    /// A build's track from its version: a nightly's name is the nightly; v2.3.0-rc.1 a release candidate; anything else (and no
    /// version) a release
    public static string TrackOf(string? version, int firstMajor = FirstMajor) =>
        version == null ? Stable
        : IsNightly(version) ? Nightly
        : IsRelease(version, firstMajor) && version.Contains('-') ? Candidate
        : Stable;

    /// A release tag, vX.Y.Z or vX.Y.Z-rc.N from the product's first major on (not a nightly's name)
    public static bool IsRelease(string? tag, int firstMajor = FirstMajor) => ReleaseKey(tag, firstMajor) != null;

    /// A name a version folder may have (the setup lists' rule): [0-9A-Za-z._+-]{1,128}, not "." or ".."
    public static bool IsTagName(string? tag) => tag != null && TagName.IsMatch(tag) && tag != "." && tag != "..";

    /// A version as players see it: nightly-2029-c544828f as "Nightly 2029 · c544828f", v2.3.0-rc.8-2-gf33ca75d as
    /// "Nightly v2.3.0-rc.8+2 · f33ca75d" (a fork's v0.0.0-0-g179d8124 and 179d8124 as "Nightly · 179d8124"), -dirty kept, any other
    /// as it is. Files and logs keep the version itself
    public static string Shown(string? version)
    {
        if (version == null) return "";
        if (NightlyName.Match(version) is { Success: true } n) return $"Nightly {n.Groups[1].Value} · {n.Groups[2].Value}{n.Groups[3].Value}";
        if (DescribeName.Match(version) is { Success: true } d)
        {
            var commit = d.Groups[6].Value[..Math.Min(8, d.Groups[6].Value.Length)] + d.Groups[7].Value;
            var tagged = d.Groups[1].Value != "0" || d.Groups[2].Value != "0" || d.Groups[3].Value != "0";
            var name = version[..version.LastIndexOf("-g", StringComparison.Ordinal)];
            var bare = name[..name.LastIndexOf('-')];
            return tagged ? $"Nightly {bare}+{d.Groups[5].Value} · {commit}" : $"Nightly · {commit}";
        }
        if (CommitName.IsMatch(version)) return $"Nightly · {version[..Math.Min(8, version.Length)]}";
        return version;
    }

    /// A nightly's place in the nightly order (null: no ordered nightly). The launcher's by its count; Hookshot's by the release it
    /// follows, then its count; -dirty after the build of its own commit. The first number is the kind: the two never compare. A
    /// commit alone has no place
    static long[]? NightlyKey(string? v)
    {
        if (v == null) return null;
        if (NightlyName.Match(v) is { Success: true } m)
            return new[] { 1, Whole(m.Groups[1].Value), m.Groups[3].Success ? 1 : 0 };
        if (DescribeName.Match(v) is { Success: true } d)
            return new[] { 2, Whole(d.Groups[1].Value), Whole(d.Groups[2].Value), Whole(d.Groups[3].Value),
                           d.Groups[4].Success ? Whole(d.Groups[4].Value) : long.MaxValue, Whole(d.Groups[5].Value), d.Groups[7].Success ? 1 : 0 };
        return null;
    }

    static long Whole(string s) => long.Parse(s, NumberStyles.None, CultureInfo.InvariantCulture);

    static long[]? ReleaseKey(string? v, int firstMajor)
    {
        if (v == null) return null;
        var m = ReleaseName.Match(v);
        if (!m.Success) return null;
        var key = new long[4];
        for (var i = 0; i < 3; i++)
            if (!long.TryParse(m.Groups[i + 1].Value, NumberStyles.None, CultureInfo.InvariantCulture, out key[i])) return null;
        key[3] = long.MaxValue;
        if (m.Groups[4].Success && !long.TryParse(m.Groups[4].Value, NumberStyles.None, CultureInfo.InvariantCulture, out key[3])) return null;
        return key[0] >= firstMajor ? key : null;
    }

    /// a newer than b: both vX.Y.Z[-rc.N] in semver order (v2.3.0-rc.1 &lt; v2.3.0-rc.2 &lt; v2.3.0), or both nightlies of one kind in
    /// the nightly order (NightlyKey). A nightly and a release are not ordered (the rolling nightly is not a release): false both
    /// ways, as when either is not a version, or both are a fork's nightlies with no release before them (v0.0.0-0-g...)
    public static bool Newer(string? a, string? b, int firstMajor = FirstMajor)
    {
        long[]? x, y;
        if (IsNightly(a) || IsNightly(b))
        {
            x = NightlyKey(a);
            y = NightlyKey(b);
            if (x == null || y == null || x[0] != y[0] || x.Length != y.Length) return false;
        }
        else
        {
            x = ReleaseKey(a, firstMajor);
            y = ReleaseKey(b, firstMajor);
            if (x == null || y == null) return false;
        }
        for (var i = 0; i < x.Length; i++)
            if (x[i] != y[i]) return x[i] > y[i];
        return false;
    }

    /// The order Newer defines, for sorting: versions before names that are none, which keep their order among themselves
    public static int Compare(string? a, string? b) => Newer(a, b) ? 1 : Newer(b, a) ? -1 : 0;
}
