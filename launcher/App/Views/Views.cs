using Avalonia.Controls;

namespace LongshotLauncher.Views;

// The pages and dialogs: each its .axaml, bound to its view model (compiled bindings); no logic here but where the view scrolls

public sealed partial class HomeView : UserControl { public HomeView() => InitializeComponent(); }
public sealed partial class FilesStepView : UserControl { public FilesStepView() => InitializeComponent(); }
public sealed partial class SettingsStepView : UserControl
{
    public SettingsStepView()
    {
        InitializeComponent();
        // (opening Advanced scrolls the step's content, never the footer, to show it: the mockup's revealAdvanced)
        DataContextChanged += (_, _) =>
        {
            if (DataContext is ViewModels.SettingsStepViewModel vm)
                vm.PropertyChanged += (_, e) =>
                {
                    if (e.PropertyName == nameof(vm.AdvancedOpen) && vm.AdvancedOpen)
                        Avalonia.Threading.Dispatcher.UIThread.Post(() => Body.ScrollToEnd(), Avalonia.Threading.DispatcherPriority.Background);
                };
        };
    }

    /// For the screenshots: the content scrolled to its end, as opening Advanced leaves it
    public void ScrollToEnd() => Body.ScrollToEnd();
}
public sealed partial class BuildStepView : UserControl
{
    ViewModels.BuildStepViewModel? vm;

    public BuildStepView()
    {
        InitializeComponent();
        // (the details follow the log as a terminal does: while at the bottom, a new line scrolls them there again; scrolled up
        // to read, they stay where they are (the view model holds the text still) until scrolled back down. Opening them, or
        // another level or search, starts at the bottom)
        LogScroll.ScrollChanged += (_, e) =>
        {
            if (vm is not { } m) return;
            // (one event per layout pass, a new line's growth and the reader's wheel together: a move up that isn't the clamp
            // of a shrinking text is the reader's)
            if (e.OffsetDelta.Y < 0 && e.ExtentDelta.Y >= 0) m.Following = false;
            else if (e.ExtentDelta.Y == 0 && e.OffsetDelta.Y != 0) m.Following = AtBottom();
            if (m.Following && e.ExtentDelta.Y != 0) FollowLater();
        };
        DataContextChanged += (_, _) =>
        {
            if (vm != null) vm.PropertyChanged -= Changed;   // (the page's view is reused for the next build: the last one let go)
            vm = DataContext as ViewModels.BuildStepViewModel;
            if (vm != null) vm.PropertyChanged += Changed;
        };
    }

    bool AtBottom() => LogScroll.Offset.Y + LogScroll.Viewport.Height >= LogScroll.Extent.Height - 4;

    /// To the bottom once the text is laid out, unless the reader scrolled up in the meantime
    void FollowLater() =>
        Avalonia.Threading.Dispatcher.UIThread.Post(() => { if (vm?.Following == true) LogScroll.ScrollToEnd(); },
                                                    Avalonia.Threading.DispatcherPriority.Background);

    void Changed(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (vm is not { } m) return;
        if ((e.PropertyName == nameof(m.ShowLog) && m.ShowLog) || e.PropertyName is nameof(m.Level) or nameof(m.Search))
        {
            m.Following = true;
            FollowLater();
        }
    }
}

public sealed partial class ReadyView : UserControl { public ReadyView() => InitializeComponent(); }
public sealed partial class ProblemView : UserControl { public ProblemView() => InitializeComponent(); }
public sealed partial class ProblemPageView : UserControl { public ProblemPageView() => InitializeComponent(); }
public sealed partial class SettingsView : UserControl { public SettingsView() => InitializeComponent(); }
public sealed partial class SavesView : UserControl { public SavesView() => InitializeComponent(); }
public sealed partial class SavesConfirmView : UserControl { public SavesConfirmView() => InitializeComponent(); }
public sealed partial class SavesResultView : UserControl { public SavesResultView() => InitializeComponent(); }
public sealed partial class ChannelPickerView : UserControl { public ChannelPickerView() => InitializeComponent(); }
public sealed partial class DeleteView : UserControl { public DeleteView() => InitializeComponent(); }
public sealed partial class LicenceView : UserControl { public LicenceView() => InitializeComponent(); }
public sealed partial class StopBuildView : UserControl { public StopBuildView() => InitializeComponent(); }
public sealed partial class SavePickView : UserControl { public SavePickView() => InitializeComponent(); }
public sealed partial class HookshotImportView : UserControl { public HookshotImportView() => InitializeComponent(); }
public sealed partial class HookshotSettingsView : UserControl { public HookshotSettingsView() => InitializeComponent(); }
