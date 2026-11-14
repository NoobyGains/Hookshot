using System.Text.RegularExpressions;

namespace HookshotLauncher.Core;

/// How much a build log line matters, least detailed first: the details show a level and the ones before it
public enum LogLevel { Error, Warning, Info, Debug, Trace }

/// A build log line's level, as the game writes it (Hookshot's docs/development.md, Log levels): no tag is info; "[trace] ",
/// "[debug] ", "[warn] " or "[error] " after the game's thread tag ("[hos host] [trace] vk: ...") is that level. A build's own
/// "error: " line (@@error, as the details write it) is an error. A game from before the levels has no tags: every line is info.
public static class LogLevels
{
    static readonly Regex Tag = new(@"^(?:\[hos [^\]\r\n]*\] )?\[(error|warn|debug|trace)\] ", RegexOptions.CultureInvariant);

    /// The level picker's choices, in its order
    public static IReadOnlyList<LogLevel> All { get; } = [LogLevel.Error, LogLevel.Warning, LogLevel.Info, LogLevel.Debug, LogLevel.Trace];

    public static LogLevel Of(string line)
    {
        if (line.StartsWith("error: ", StringComparison.Ordinal)) return LogLevel.Error;
        var m = Tag.Match(line);
        if (!m.Success) return LogLevel.Info;
        return m.Groups[1].Value switch
        {
            "error" => LogLevel.Error,
            "warn" => LogLevel.Warning,
            "debug" => LogLevel.Debug,
            _ => LogLevel.Trace,
        };
    }

    public static string Name(LogLevel level) => level switch
    {
        LogLevel.Error => "Errors",
        LogLevel.Warning => "Warnings",
        LogLevel.Info => "Info",
        LogLevel.Debug => "Debug",
        _ => "Trace",
    };
}

/// A build's log: every line with its level, read once as it is added, so showing the details' filtered tail doesn't read the
/// whole log again at each new line. Safe to add to from the build's output threads while the window reads it.
public sealed class BuildLog
{
    readonly List<string> lines = new();
    readonly List<LogLevel> levels = new();

    public void Add(string line)
    {
        var level = LogLevels.Of(line);
        lock (lines)
        {
            lines.Add(line);
            levels.Add(level);
        }
    }

    public int Count { get { lock (lines) return lines.Count; } }

    /// The last `limit` lines, of every level (the bug report's)
    public IReadOnlyList<string> Last(int limit)
    {
        lock (lines) return lines.Skip(Math.Max(0, lines.Count - limit)).ToList();
    }

    /// The last `limit` lines the details show: of level `most` or before it, holding `search` when it isn't blank (any case)
    public IReadOnlyList<string> Tail(LogLevel most, string? search, int limit)
    {
        var find = string.IsNullOrWhiteSpace(search) ? null : search.Trim();
        var tail = new List<string>();
        lock (lines)
            for (var i = lines.Count - 1; i >= 0 && tail.Count < limit; i--)
                if (levels[i] <= most && (find == null || lines[i].Contains(find, StringComparison.OrdinalIgnoreCase)))
                    tail.Add(lines[i]);
        tail.Reverse();
        return tail;
    }
}
