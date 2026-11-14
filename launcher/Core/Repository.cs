using System.Reflection;
using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// The GitHub repository Hookshot's releases and the launcher's own come from, as owner/name. The same rule as the builder's
/// (builder/HookshotBuilder/Repository.cs, nx2/version.py repository()): the repository the release was built in, stamped by its
/// CI (-p:HookshotRepository=$GITHUB_REPOSITORY, an AssemblyMetadata of the program), else notquiteog/Hookshot. So a fork's
/// launcher follows that fork's releases, as its builder does. HOOKSHOT_LAUNCHER_REPOSITORY=&lt;owner/name&gt; points a build from a
/// checkout at another repository's releases, for trying one out. tests/test_launcher_repository.py holds Default to the
/// builder's.
public static class Repository
{
    public const string Default = "notquiteog/Hookshot";
    public const string StampKey = "HookshotRepository";
    public const string Variable = "HOOKSHOT_LAUNCHER_REPOSITORY";
    static readonly Regex Name = new("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", RegexOptions.CultureInvariant);
    static readonly Lazy<string> current = new(() => Resolve(Environment.GetEnvironmentVariable, Assembly.GetEntryAssembly()));

    /// This launcher's repository
    public static string Current => current.Value;

    /// owner/name as the builder accepts it (letters, digits and - for the owner; . _ - too for the name)
    public static bool IsName(string? name) => name != null && Name.IsMatch(name) && !name.EndsWith("/.", StringComparison.Ordinal)
                                                 && !name.EndsWith("/..", StringComparison.Ordinal);

    /// HOOKSHOT_LAUNCHER_REPOSITORY when it is a name, else the stamp the release build made, else Default
    public static string Resolve(Func<string, string?> getenv, Assembly? assembly)
    {
        if (getenv(Variable)?.Trim() is { } set && IsName(set)) return set;
        var stamp = assembly?.GetCustomAttributes<AssemblyMetadataAttribute>().FirstOrDefault(a => a.Key == StampKey)?.Value?.Trim();
        return IsName(stamp) ? stamp! : Default;
    }

    /// The repository's page on GitHub
    public static string Page(string repo) => "https://github.com/" + repo;
}
