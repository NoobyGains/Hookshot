using System.ComponentModel;
using System.Windows.Input;

namespace LongshotLauncher.Core;

/// A button's action that takes time (a check, a download, a delete): from the click until it ends the button is off
/// (CanExecute false, so a second click starts nothing), says what it is doing (Status, and Fraction when the amount is known) and
/// can be stopped when the work allows it (Cancel). A failure is kept (Problem) and passed to failed, and the button is on again
/// to try once more. Started on the window's thread; Report from another thread goes through the window's thread first (Ui.Post)
public sealed class BusyCommand : ICommand, INotifyPropertyChanged
{
    readonly Func<BusyCommand, CancellationToken, Task> run;
    readonly Func<bool>? can;
    readonly Action<Exception>? failed;
    CancellationTokenSource? cancel;
    bool busy, cancellable;
    string? status, problem;
    double? fraction;

    /// run: the work, given this command (to Report) and the token Cancel cancels; can: whether it may start now, apart from
    /// running already; failed: what the screen shows of a failure (else only Problem)
    public BusyCommand(Func<BusyCommand, CancellationToken, Task> run, Func<bool>? can = null, Action<Exception>? failed = null)
    {
        this.run = run;
        this.can = can;
        this.failed = failed;
    }

    public event EventHandler? CanExecuteChanged;
    public event PropertyChangedEventHandler? PropertyChanged;

    /// Running: the button is off and shows Status
    public bool IsBusy => busy;
    public bool IsIdle => !busy;
    /// What it is doing now ("Downloading the new launcher… 42%"); null when idle
    public string? Status => status;
    /// How far it is (0..1) when the amount is known; null when not (a spinner alone, never a bar that does not move)
    public double? Fraction => fraction;
    public bool HasFraction => fraction != null;
    public double Progress => fraction ?? 0;
    /// The last run's failure, until the next run
    public string? Problem => problem;
    public bool HasProblem => problem != null;
    /// Whether the work can be stopped now (a download can; putting a file in place cannot)
    public bool CanCancel => busy && cancellable;

    public bool CanExecute(object? parameter) => !busy && (can?.Invoke() ?? true);

    public void Execute(object? parameter) => _ = RunAsync();

    /// Runs the work unless it runs already or may not start. True when it ran to its end; false when it did not start, failed
    /// (Problem) or was cancelled
    public async Task<bool> RunAsync()
    {
        if (!CanExecute(null)) return false;
        var mine = new CancellationTokenSource();
        cancel = mine;
        busy = true;
        cancellable = false;
        problem = null;
        Changed();
        try
        {
            await run(this, mine.Token);
            return true;
        }
        catch (OperationCanceledException) when (mine.IsCancellationRequested)
        {
            return false;
        }
        catch (Exception e)
        {
            problem = e.Message;
            failed?.Invoke(e);
            return false;
        }
        finally
        {
            busy = false;
            cancellable = false;
            status = null;
            fraction = null;
            cancel = null;
            mine.Dispose();
            Changed();
        }
    }

    /// What the work is doing now, and how far when that is known; cancellable: whether Cancel can stop it from here. Ignored
    /// once the work has ended (a late report from a download's thread)
    public void Report(string? text, double? done = null, bool? canCancel = null)
    {
        if (!busy) return;
        status = text;
        fraction = done is { } d ? Math.Clamp(double.IsFinite(d) ? d : 0, 0, 1) : null;
        if (canCancel is { } c) cancellable = c;
        Raise(nameof(Status), nameof(Fraction), nameof(HasFraction), nameof(Progress), nameof(CanCancel));
    }

    /// Stops the work where it allows it (CanCancel)
    public void Cancel()
    {
        if (CanCancel) cancel?.Cancel();
    }

    /// Whether it may start has changed (can's answer), or it started or ended
    public void Changed()
    {
        Raise(nameof(IsBusy), nameof(IsIdle), nameof(Status), nameof(Fraction), nameof(HasFraction), nameof(Progress), nameof(Problem),
              nameof(HasProblem), nameof(CanCancel));
        CanExecuteChanged?.Invoke(this, EventArgs.Empty);
    }

    void Raise(params string[] names)
    {
        foreach (var n in names) PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(n));
    }
}
