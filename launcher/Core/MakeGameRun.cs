using System.Diagnostics;
using System.Globalization;

namespace HookshotLauncher.Core;

public enum GameCheckStatus { Supported, OtherVersion, Unreadable }

/// make_game.py --check's answer, in plain words: the supported version, another version of the game, or files it could not read
public sealed record GameCheck(GameCheckStatus Status, string Text)
{
    public bool Ok => Status == GameCheckStatus.Supported;

    /// The answer from the check's stdout lines, the last line it wrote to stderr and its exit code (the 2.x Builder's
    /// Runner.Check): @@check ok, @@check bad (another version), @@error or nothing said (the files could not be read: the
    /// stderr line says why)
    public static GameCheck Read(IEnumerable<string> stdout, string? lastError, int exitCode)
    {
        GameCheck? answer = null;
        foreach (var line in stdout)
            switch (MakeGameProtocol.Parse(line))
            {
                case MakeGameLine.Check { Ok: true } c:
                    answer = new GameCheck(GameCheckStatus.Supported, c.Text);
                    break;
                case MakeGameLine.Check c:
                    answer = new GameCheck(GameCheckStatus.OtherVersion, c.Text);
                    break;
                case MakeGameLine.Error e:
                    answer = new GameCheck(GameCheckStatus.Unreadable, e.Text);
                    break;
            }
        return answer ?? new GameCheck(GameCheckStatus.Unreadable,
            string.IsNullOrWhiteSpace(lastError) ? Tr.F("The build tools stopped without saying why (exit code {0}).", exitCode) : lastError.Trim());
    }
}

/// make_game.py run: its stdout and stderr line by line, and its whole process tree stopped when the run is cancelled
public static class MakeGameRun
{
    /// The program run to its end; each line handed over as it comes (from a pool thread). Cancelling kills the process and
    /// everything it started (the compilers), then throws OperationCanceledException
    public static async Task<int> RunAsync(ProcessStartInfo start, Action<string> stdout, Action<string> stderr, CancellationToken cancel = default)
    {
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.UseShellExecute = false;
        using var p = new Process { StartInfo = start };
        var outDone = new TaskCompletionSource();
        var errDone = new TaskCompletionSource();
        p.OutputDataReceived += (_, e) =>
        {
            if (e.Data == null) outDone.TrySetResult();
            else stdout(e.Data);
        };
        p.ErrorDataReceived += (_, e) =>
        {
            if (e.Data == null) errDone.TrySetResult();
            else stderr(e.Data);
        };
        p.Start();
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        using (cancel.Register(() =>
               {
                   try { p.Kill(entireProcessTree: true); }
                   catch (Exception e) when (e is InvalidOperationException or System.ComponentModel.Win32Exception or NotSupportedException) { }
               }))
        {
            await p.WaitForExitAsync(CancellationToken.None).ConfigureAwait(false);
            await Task.WhenAll(outDone.Task, errDone.Task).WaitAsync(TimeSpan.FromSeconds(5), CancellationToken.None)
                .ContinueWith(_ => { }, TaskScheduler.Default).ConfigureAwait(false);
        }
        cancel.ThrowIfCancellationRequested();
        return p.ExitCode;
    }

    /// make_game.py --check run, and its answer
    public static async Task<GameCheck> CheckAsync(MakeGameCommand command, CancellationToken cancel = default)
    {
        var lines = new List<string>();
        string? lastError = null;
        try
        {
            var code = await RunAsync(command.StartInfo(), l => { lock (lines) lines.Add(l); },
                                      l => { if (!string.IsNullOrWhiteSpace(l)) lastError = l; }, cancel).ConfigureAwait(false);
            lock (lines) return GameCheck.Read(lines.ToList(), lastError, code);
        }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException or InvalidOperationException)
        {
            return new GameCheck(GameCheckStatus.Unreadable, Tr.F("The build tools could not start: {0}", e.Message));
        }
    }
}

/// What a build should take on this PC before it starts, by stage. Measured on one PC (two player builds of nightly-56 on a
/// Ryzen 9 7900X, 24 threads, and an RTX 3090: Hookshot's docs/development.md, "Build times"; measure again when the build
/// changes) and scaled by this PC's threads for the stages that use every thread (the lift, the compile, the shaders). The
/// others read and write files and keep the measured time. A thread past the cores is worth less than a core, so the scale
/// goes as (24 / threads)^0.85 rather than in step: 8 threads about 2.5 times as long, 32 about 0.8
public static class BuildForecast
{
    public const int ReferenceThreads = 24;
    static readonly Dictionary<string, (double Seconds, bool Parallel)> Reference = new()
    {
        ["download"] = (10, false), ["read"] = (76, false), ["lift"] = (57, true), ["compile"] = (305, true), ["finish"] = (66, false),
        [MakeGameProtocol.ShadersStage] = (311, true),
    };

    /// A stage's seconds on a PC with this many threads (0 for a stage it does not know)
    public static double Seconds(string stage, int threads)
    {
        if (!Reference.TryGetValue(stage, out var r)) return 0;
        return r.Parallel ? r.Seconds * Math.Pow(ReferenceThreads / (double)Math.Clamp(threads, 1, 256), 0.85) : r.Seconds;
    }

    /// The whole build's seconds: download, the tools' download first; shaders, the shaders prepared now
    public static double Total(bool download, bool shaders, int threads) =>
        new[] { "download", "read", "lift", "compile", "finish", MakeGameProtocol.ShadersStage }
            .Where(id => (download || id != "download") && (shaders || id != MakeGameProtocol.ShadersStage))
            .Sum(id => Seconds(id, threads));
}

/// A build's times: how long each stage took (or has run), and how long the whole build has left, from BuildProgress and a clock.
/// Before the build has gone far, the time left is BuildForecast's for this PC. As stages end, it learns this PC's pace: the
/// stages still to come are the forecast scaled by how long the finished stages took against theirs (a stage that kept an
/// earlier build's work, BuildStage.Kept, says nothing of the pace and is left out). A running stage counts down from the rate
/// its own progress moves at, from when it began to move (the read's progress is only its last check, after minutes of
/// unpacking; the shaders' begins once the game has started), and the compile counts down from make_game's own estimate (@@eta,
/// from what earlier builds measured on this PC), which build.py says only as a file ends
public sealed class BuildClock
{
    readonly Dictionary<string, TimeSpan> started = new();
    readonly Dictionary<string, TimeSpan> took = new();
    readonly Dictionary<string, TimeSpan> still = new();   // (a running stage's last moment at no progress: its progress moves from there)
    readonly int threads;
    TimeSpan begun = TimeSpan.MinValue;
    TimeSpan last;
    int etaLines;
    TimeSpan etaAt;

    /// threads: the CPU threads the build may use (0: this PC's)
    public BuildClock(int threads = 0) => this.threads = threads > 0 ? threads : SystemInfo.Threads();

    static double Fraction(BuildProgress p, BuildStage s) => s.Weight > 0 ? Math.Clamp((p.Overall - s.Start) / s.Weight, 0, 1) : 0;

    /// The progress seen at now (a monotonic time: a Stopwatch's elapsed)
    public void Observe(BuildProgress p, TimeSpan now)
    {
        if (begun == TimeSpan.MinValue) begun = now;
        last = now;
        if (p.EtaLines != etaLines)
        {
            etaLines = p.EtaLines;
            etaAt = now;
        }
        foreach (var s in p.Stages)
        {
            if (s.State == StageState.Running && !started.ContainsKey(s.Id)) started[s.Id] = now;
            if (s.State == StageState.Running && Fraction(p, s) == 0) still[s.Id] = now;
            if (s.State is StageState.Done or StageState.Skipped && started.TryGetValue(s.Id, out var from) && !took.ContainsKey(s.Id))
                took[s.Id] = now - from;
        }
    }

    /// A stage's time: what it took, or how long it has run; null before it started
    public TimeSpan? Of(string id) =>
        took.TryGetValue(id, out var t) ? t : started.TryGetValue(id, out var from) ? last - from : null;

    public TimeSpan Elapsed => begun == TimeSpan.MinValue ? TimeSpan.Zero : last - begun;

    /// This PC's pace against the forecast: the finished stages' time over their forecast (the download is the network's, not
    /// the PC's, and a stage that kept an earlier build's work took seconds where the forecast has minutes: both are left out).
    /// 1 until 30 forecast seconds have finished; kept within 0.25..4
    public double Pace(BuildProgress p)
    {
        double actual = 0, forecast = 0;
        foreach (var s in p.Stages)
        {
            if (s.State != StageState.Done || s.Id == "download" || s.Kept || !took.TryGetValue(s.Id, out var t)) continue;
            actual += t.TotalSeconds;
            forecast += BuildForecast.Seconds(s.Id, threads);
        }
        return forecast >= 30 ? Math.Clamp(actual / forecast, 0.25, 4) : 1;
    }

    /// The seconds left
    public double? SecondsLeft(BuildProgress p)
    {
        if (p.Finished) return 0;
        var pace = Pace(p);
        double left = 0;
        foreach (var s in p.Stages)
        {
            if (s.State is StageState.Done or StageState.Skipped) continue;
            var expected = BuildForecast.Seconds(s.Id, threads) * pace;
            if (s.State != StageState.Running)
            {
                left += expected;
                continue;
            }
            var ran = Of(s.Id)?.TotalSeconds ?? 0;
            var fraction = Fraction(p, s);
            // (the compile: build.py's @@eta less the time since it said it. Run out (the link after the last file, or a PC slower
            // than the times it knows), the compile's own progress says the rest)
            var countdown = s.Id == "compile" && p.Eta is double eta ? eta - (last - etaAt).TotalSeconds : 0;
            // (the compile's progress counts its files' work from its start, the first file ending minutes in; the other stages'
            // progress covers their last part, from when it began to move)
            var moving = s.Id != "compile" && still.TryGetValue(s.Id, out var from) ? (last - from).TotalSeconds : ran;
            if (countdown > 0) left += countdown;
            else if (fraction >= 0.1 && moving >= 10) left += moving / fraction * (1 - fraction);
            else if (s.Id == "compile" && p.Eta != null) left += expected * 0.1;   // (its countdown out, its progress not yet telling)
            else left += Math.Max(expected - ran, expected * 0.1);
        }
        return left;
    }

    /// A stage that has not started, or is running: about how long it takes in all on this PC, at the pace so far
    public double? Estimate(BuildProgress p, BuildStage stage) => BuildForecast.Seconds(stage.Id, threads) * Pace(p);
}

/// Times and sizes as the window writes them
public static class Durations
{
    /// m:ss (h:mm:ss past an hour)
    public static string Clock(TimeSpan t)
    {
        var s = (long)Math.Round(Math.Max(0, t.TotalSeconds));
        return s >= 3600
            ? string.Create(CultureInfo.InvariantCulture, $"{s / 3600}:{s / 60 % 60:00}:{s % 60:00}")
            : string.Create(CultureInfo.InvariantCulture, $"{s / 60}:{s % 60:00}");
    }

    /// "Under a minute", "About 12 min", "About 1 h 20 min"
    public static string About(double seconds)
    {
        if (seconds < 60) return Tr.T("Under a minute");
        var m = (long)Math.Round(seconds / 60);
        if (m < 60) return Tr.F("About {0} min", m);
        return m % 60 == 0 ? Tr.F("About {0} h", m / 60) : Tr.F("About {0} h {1} min", m / 60, m % 60);
    }

    /// "~4 min" for a stage still to come
    public static string Roughly(double seconds) => Tr.F("~{0} min", Math.Max(1, (long)Math.Round(seconds / 60)));

    /// When something was saved or built, as the home writes it: "today 18:02", "yesterday 22:14", "6 Nov", "6 Nov 2025"
    public static string When(DateTime t, DateTime now)
    {
        var day = t.Date;
        if (day == now.Date) return Tr.F("today {0}", t.ToString("HH:mm", CultureInfo.InvariantCulture));
        if (day == now.Date.AddDays(-1)) return Tr.F("yesterday {0}", t.ToString("HH:mm", CultureInfo.InvariantCulture));
        return Date(t, now);
    }

    static readonly string[] Months =
    {
        Tr.N("Jan"), Tr.N("Feb"), Tr.N("Mar"), Tr.N("Apr"), Tr.N("May"), Tr.N("Jun"),
        Tr.N("Jul"), Tr.N("Aug"), Tr.N("Sep"), Tr.N("Oct"), Tr.N("Nov"), Tr.N("Dec"),
    };

    /// "6 Nov", or "6 Nov 2025" in another year, in the language in use (its order and its month's name)
    static string Date(DateTime t, DateTime now)
    {
        var month = Tr.T(Months[t.Month - 1]);
        return t.Year == now.Year ? Tr.F("{0} {1}", t.Day, month) : Tr.F("{0} {1} {2}", t.Day, month, t.Year);
    }

    /// The day only: "today", "yesterday", "3 Nov"
    public static string Day(DateTime t, DateTime now)
    {
        if (t.Date == now.Date) return Tr.T("today");
        if (t.Date == now.Date.AddDays(-1)) return Tr.T("yesterday");
        return Date(t, now);
    }

    /// "38.4 GB", "340 MB"
    public static string Size(long bytes) =>
        bytes >= 1L << 30 ? string.Create(CultureInfo.InvariantCulture, $"{bytes / (double)(1L << 30):0.0} GB")
        : string.Create(CultureInfo.InvariantCulture, $"{Math.Max(0, bytes) >> 20} MB");
}
