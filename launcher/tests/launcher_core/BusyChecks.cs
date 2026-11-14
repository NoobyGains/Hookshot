using System.Text.RegularExpressions;
using HookshotLauncher.Core;

/// The buttons whose work takes time (Core/BusyCommand.cs): off from the click until the work ends, a second click starting
/// nothing, on again after a success and after a failure, with the failure kept; and the home's buttons built on it (the launcher's
/// update, the update check and its Try again, Build), checked as the home composes them and in its source
static partial class Program
{
    static async Task BusyChecks(string repo)
    {
        await BusyCommandChecks();
        await HomeBusyChecks();
        HomeBusySourceChecks(repo);
    }

    static async Task BusyCommandChecks()
    {
        // ---- off while it runs, one run per click, on again after it ----
        var gate = new TaskCompletionSource();
        var runs = 0;
        var flips = 0;
        var busy = new BusyCommand(async (b, _) =>
        {
            runs++;
            b.Report("Working…");
            await gate.Task;
        });
        busy.CanExecuteChanged += (_, _) => flips++;
        Require(busy.CanExecute(null) && busy.IsIdle && busy.Status == null && !busy.HasProblem, "A BusyCommand starts idle and on.");
        var first = busy.RunAsync();
        Require(busy.IsBusy && !busy.CanExecute(null) && busy.Status == "Working…" && flips >= 1,
                "While it runs, the button is off (CanExecute false, CanExecuteChanged raised) and says what it does.");
        busy.Execute(null);
        Require(!await busy.RunAsync() && runs == 1, "A second click while it runs starts nothing.");
        gate.SetResult();
        Require(await first && runs == 1, "The run ends as a success.");
        Require(busy.CanExecute(null) && busy.IsIdle && busy.Status == null && busy.Fraction == null && !busy.HasProblem,
                "After a success the button is on again, with no busy text left.");
        busy.Report("late");
        Require(busy.Status == null, "A report that arrives after the end (a download's thread) changes nothing.");

        // ---- a failure: kept, passed on, and the button on again to try once more ----
        Exception? shown = null;
        var fail = true;
        var failing = new BusyCommand(async (_, _) =>
        {
            await Task.Yield();
            if (fail) throw new IOException("the disk is full");
        }, failed: e => shown = e);
        Require(!await failing.RunAsync(), "A failed run reports false.");
        Require(failing.CanExecute(null) && failing.IsIdle && failing.Problem == "the disk is full" && shown is IOException,
                "After a failure the button is on again, the failure kept (Problem) and shown (failed).");
        fail = false;
        Require(await failing.RunAsync() && !failing.HasProblem, "Trying again runs again, and a success clears the failure.");

        // ---- progress: known (a fraction, clamped) or not (no bar) ----
        var step = new TaskCompletionSource();
        var progress = new BusyCommand(async (b, _) =>
        {
            b.Report("Downloading… 40%", 0.4);
            await step.Task;
        });
        var p = progress.RunAsync();
        Require(progress.HasFraction && Math.Abs(progress.Progress - 0.4) < 1e-9, "A known amount shows as a fraction.");
        progress.Report("Downloading…", 7);
        Require(progress.Fraction == 1, "A fraction is kept within 0..1.");
        progress.Report("Checking…");
        Require(!progress.HasFraction && progress.Progress == 0, "An unknown amount has no fraction: a spinner, no bar.");
        step.SetResult();
        await p;

        // ---- cancel: only where the work allows it ----
        var started = new TaskCompletionSource();
        var cancellable = new BusyCommand(async (b, token) =>
        {
            b.Report("Downloading…", 0, canCancel: true);
            started.SetResult();
            await Task.Delay(Timeout.Infinite, token);
        });
        var c = cancellable.RunAsync();
        await started.Task;
        Require(cancellable.CanCancel, "A download can be cancelled.");
        cancellable.Cancel();
        Require(!await c && cancellable.CanExecute(null) && !cancellable.HasProblem, "Cancelled: the button is on again, and a cancel is no failure.");
        var held = new TaskCompletionSource();
        var cancelledToken = false;
        var swap = new BusyCommand(async (b, token) =>
        {
            b.Report("Putting it in place…", canCancel: false);
            await held.Task;
            cancelledToken = token.IsCancellationRequested;
        });
        var sw = swap.RunAsync();
        Require(!swap.CanCancel, "A step that cannot be stopped (the swap) is not cancellable.");
        swap.Cancel();
        held.SetResult();
        Require(await sw && !cancelledToken, "Cancel does nothing to a step that cannot be stopped.");

        // ---- may not start: the can test, and Changed when it changes ----
        var allowed = false;
        var guarded = new BusyCommand((_, _) => Task.CompletedTask, () => allowed);
        var changed = 0;
        guarded.CanExecuteChanged += (_, _) => changed++;
        Require(!guarded.CanExecute(null) && !await guarded.RunAsync(), "A BusyCommand that may not start does not run.");
        allowed = true;
        guarded.Changed();
        Require(changed == 1 && guarded.CanExecute(null), "Changed tells the button to ask again.");
    }

    /// The home as it composes them (HomeViewModel): Build is off while the check runs and while the launcher updates itself, and on
    /// again after each ends, whether it succeeded or failed; Try again is the check itself
    static async Task HomeBusyChecks()
    {
        foreach (var outcome in new[] { "success", "failure" })
        {
            var checkGate = new TaskCompletionSource();
            var updateGate = new TaskCompletionSource();
            var check = new BusyCommand(async (b, _) =>
            {
                b.Report("Checking for updates…");
                await checkGate.Task;
                if (outcome == "failure") throw new InvalidOperationException("no answer");
            });
            var update = new BusyCommand(async (b, _) =>
            {
                b.Report("Downloading the new launcher…", 0, canCancel: true);
                await updateGate.Task;
                if (outcome == "failure") throw new InvalidDataException("not the file its release names");
            }, () => true);
            var retry = check;
            bool CanStartBuild() => !check.IsBusy && !update.IsBusy;
            var newest = "v3.1.0";
            bool CanBuild() => newest != null && CanStartBuild();

            var running = check.RunAsync();
            Require(!check.CanExecute(null) && !retry.CanExecute(null) && !CanBuild(),
                    $"While the check runs ({outcome}): Try again and Build are off.");
            checkGate.SetResult();
            await running;
            Require(check.CanExecute(null) && retry.CanExecute(null) && CanBuild() && (outcome == "success") == !check.HasProblem,
                    $"After the check's {outcome}: Try again and Build are on again.");

            var updating = update.RunAsync();
            Require(!update.CanExecute(null) && !CanBuild() && update.Status == "Downloading the new launcher…",
                    $"While the launcher updates ({outcome}): its button is off, Build is off, and it says what it does.");
            updateGate.SetResult();
            await updating;
            Require(update.CanExecute(null) && CanBuild() && (outcome == "success") == !update.HasProblem,
                    $"After the launcher update's {outcome}: its button and Build are on again.");
        }
    }

    /// The home's source uses the pattern for the buttons checked above
    static void HomeBusySourceChecks(string repo)
    {
        var home = File.ReadAllText(Path.Combine(repo, "App", "ViewModels", "HomeViewModel.cs"));
        Require(Regex.IsMatch(home, @"UpdateLauncherCommand = new BusyCommand\(UpdateLauncherAsync,")
                && home.Contains("public BusyCommand UpdateLauncherCommand"), "The launcher's update is a BusyCommand.");
        Require(Regex.IsMatch(home, @"CheckCommand = new BusyCommand\(CheckAsync\)") && home.Contains("public BusyCommand RetryCheckCommand => CheckCommand;"),
                "The update check is a BusyCommand, and Try again is that check.");
        Require(home.Contains("public bool CanStartBuild => !CheckCommand.IsBusy && !UpdateLauncherCommand.IsBusy;")
                && Regex.IsMatch(home, @"BuildCommand = new Command\(.*, \(\) => NewestDefault != null && CanStartBuild\);"),
                "Build is off while the check runs and while the launcher updates itself.");
        Require(Regex.IsMatch(home, @"CheckCommand\.PropertyChanged \+=.*BusyChanged") && Regex.IsMatch(home, @"UpdateLauncherCommand\.PropertyChanged \+=.*BusyChanged")
                && Regex.IsMatch(home, @"void BusyChanged\(\)\s*\{\s*BuildCommand\.Changed\(\);"),
                "Build is asked again whenever the check or the launcher update starts or ends.");
        var view = File.ReadAllText(Path.Combine(repo, "App", "Views", "HomeView.axaml"));
        Require(view.Contains("IsBusy=\"{Binding UpdateLauncherCommand.IsBusy}\" BusyText=\"{c:T 'Updating…'}\"")
                && view.Contains("Text=\"{Binding UpdateLauncherCommand.Status}\"") && view.Contains("Value=\"{Binding UpdateLauncherCommand.Progress}\"")
                && view.Contains("Command=\"{Binding CancelLauncherUpdateCommand}\""),
                "The launcher's banner shows its update running: the button's spinner, each step, the download's bar, Cancel.");
        Require(view.Contains("Text=\"{Binding CheckCommand.Status}\""), "The home shows the check running.");
        Require(Regex.IsMatch(home, @"CheckForUpdatesCommand = new Command\([\s\S]*?_ = CheckReleasesAsync\(\);[\s\S]*?\}, \(\) => CanStartBuild\);")
                && Regex.IsMatch(home, @"void BusyChanged\(\)\s*\{[^}]*CheckForUpdatesCommand\.Changed\(\);")
                && view.Contains("Command=\"{Binding CheckForUpdatesCommand}\""),
                "Check for updates runs the check, and is off while the check runs and while the launcher updates itself.");
    }
}
