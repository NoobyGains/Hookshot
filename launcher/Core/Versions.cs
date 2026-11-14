using System.Globalization;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// The channels and the version order (docs/releases.md), the same for Hookshot's releases and the launcher's own: a stable is
/// vX.Y.Z, a release candidate vX.Y.Z-rc.N, a nightly nightly-&lt;commit count&gt;-&lt;commit&gt;. Hookshot's numbers start at v3.0.0, the
/// launcher's at v1.0.0 (FirstMajor). Nothing else is a version: it is on no track and never ordered.
/// tests/test_launcher_core.py holds the vectors it is checked against.
public static class Versions
{
    /// The three channels: stable (vX.Y.Z), rc (vX.Y.Z-rc.N, and the stables: the newest of both) and nightly (from main)
    public const string Stable = "stable", Candidate = "rc", Nightly = "nightly";
    public static readonly IReadOnlyList<string> Channels = new[] { Stable, Candidate, Nightly };

    static readonly Regex NightlyName = new(@"^nightly-([0-9]{1,9})-([0-9a-f]{8})(-dirty)?$", RegexOptions.CultureInvariant);
    static readonly Regex ReleaseName = new(@"^v(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$", RegexOptions.CultureInvariant);
    static readonly Regex TagName = new(@"^[0-9A-Za-z._+-]{1,128}$", RegexOptions.CultureInvariant);

    /// The first major version of each product: Hookshot (the game and its builder) starts at v3.0.0, the launcher at v1.0.0.
    /// A number below it is no version of that product (not the 2.x numbers Hookshot was forked from)
    public const int FirstMajor = 3, LauncherFirstMajor = 1;

    public static bool IsChannel(string? channel) => channel is Stable or Candidate or Nightly;

    /// A build's track from its version: nightly-2029-c544828f (nightly-&lt;commit count&gt;-&lt;commit&gt;) is the nightly; v3.1.0-rc.1 a
    /// release candidate; anything else (and no version) a release
    public static string TrackOf(string? version, int firstMajor = FirstMajor) =>
        version == null ? Stable
        : NightlyKey(version) != null ? Nightly
        : IsRelease(version, firstMajor) && version.Contains('-') ? Candidate
        : Stable;

    /// A release tag, vX.Y.Z or vX.Y.Z-rc.N from v3.0.0 on (not a nightly's name)
    public static bool IsRelease(string? tag, int firstMajor = FirstMajor) => ReleaseKey(tag, firstMajor) != null;

    /// A name a version folder may have (the setup lists' rule): [0-9A-Za-z._+-]{1,128}, not "." or ".."
    public static bool IsTagName(string? tag) => tag != null && TagName.IsMatch(tag) && tag != "." && tag != "..";

    /// A version as players see it: nightly-2029-c544828f as "Nightly 2029 · c544828f" (-dirty kept), any other as it is.
    /// Files and logs keep the version itself
    public static string Shown(string? version) =>
        version != null && NightlyName.Match(version) is { Success: true } m
            ? $"Nightly {m.Groups[1].Value} \u00b7 {m.Groups[2].Value}{m.Groups[3].Value}"
            : version ?? "";

    /// A nightly's place in the nightly order (null: no nightly): nightly-&lt;count&gt;-&lt;commit&gt; by its count, -dirty after the
    /// build of its own commit
    static long[]? NightlyKey(string? v)
    {
        if (v == null) return null;
        var m = NightlyName.Match(v);
        if (m.Success)
            return new[] { long.Parse(m.Groups[1].Value, NumberStyles.None, CultureInfo.InvariantCulture), m.Groups[3].Success ? 1 : 0 };
        return null;
    }

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

    /// a newer than b: both vX.Y.Z[-rc.N] in semver order (v3.1.0-rc.1 &lt; v3.1.0-rc.2 &lt; v3.1.0), or both nightlies in the
    /// nightly order (NightlyKey). A nightly and a release are not ordered (a nightly's name has no version in it): false both
    /// ways, as when either is not a version
    public static bool Newer(string? a, string? b, int firstMajor = FirstMajor)
    {
        var na = NightlyKey(a);
        var nb = NightlyKey(b);
        var x = na ?? (nb == null ? ReleaseKey(a, firstMajor) : null);
        var y = nb ?? (na == null ? ReleaseKey(b, firstMajor) : null);
        if (x == null || y == null) return false;
        for (var i = 0; i < x.Length; i++)
            if (x[i] != y[i]) return x[i] > y[i];
        return false;
    }

    /// The order Newer defines, for sorting: versions before names that are none, which keep their order among themselves
    public static int Compare(string? a, string? b) => Newer(a, b) ? 1 : Newer(b, a) ? -1 : 0;
}
