using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Threading;

namespace HookshotLauncher.Controls;

/// The 3D Hookshot turning: one frame at a time of assets/hookshot_turn.png, the sprite sheet the game's loading screen turns
/// (48 frames of one turn, 8 to a row, 256 pixels each, transparent; assets/brand/README.md says how it was rendered). It turns
/// while Spinning and the control is on screen, at Fps; it stands at its first frame when it is not, when the desktop asks for
/// less motion (Motion.Reduced), and in a screenshot (Frame set by hand). The sheet is read once for every turntable
public sealed class Turntable : Control
{
    public const int Columns = 8, Rows = 6, Frames = Columns * Rows, Cell = 256;
    static readonly Lazy<Bitmap> Sheet = new(() => new Bitmap(AssetLoader.Open(new Uri("avares://HookshotLauncher/Assets/hookshot_turn.png"))));

    public static readonly StyledProperty<bool> SpinningProperty = AvaloniaProperty.Register<Turntable, bool>(nameof(Spinning), true);
    public static readonly StyledProperty<double> FpsProperty = AvaloniaProperty.Register<Turntable, double>(nameof(Fps), 20);
    public static readonly StyledProperty<int> FrameProperty = AvaloniaProperty.Register<Turntable, int>(nameof(Frame));

    /// Whether it turns (the build page binds it to the build running)
    public bool Spinning { get => GetValue(SpinningProperty); set => SetValue(SpinningProperty, value); }
    /// Frames a second: 20 is one turn in 2.4 s
    public double Fps { get => GetValue(FpsProperty); set => SetValue(FpsProperty, value); }
    /// The frame shown, 0 to 47
    public int Frame { get => GetValue(FrameProperty); set => SetValue(FrameProperty, ((value % Frames) + Frames) % Frames); }

    DispatcherTimer? timer;

    static Turntable()
    {
        AffectsRender<Turntable>(FrameProperty);
    }

    public Turntable()
    {
        RenderOptions.SetBitmapInterpolationMode(this, BitmapInterpolationMode.HighQuality);
    }

    protected override void OnAttachedToVisualTree(VisualTreeAttachmentEventArgs e)
    {
        base.OnAttachedToVisualTree(e);
        Update();
    }

    protected override void OnDetachedFromVisualTree(VisualTreeAttachmentEventArgs e)
    {
        Stop();
        base.OnDetachedFromVisualTree(e);
    }

    protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
    {
        base.OnPropertyChanged(change);
        if (change.Property == SpinningProperty || change.Property == FpsProperty || change.Property == IsVisibleProperty) Update();
    }

    void Update()
    {
        var turn = Spinning && IsVisible && !Motion.Reduced && VisualRoot != null && Fps > 0;
        if (!turn)
        {
            Stop();
            return;
        }
        if (timer != null) timer.Interval = TimeSpan.FromSeconds(1 / Math.Clamp(Fps, 1, 60));
        else
        {
            timer = new DispatcherTimer(TimeSpan.FromSeconds(1 / Math.Clamp(Fps, 1, 60)), DispatcherPriority.Render, (_, _) => Frame++);
            timer.Start();
        }
    }

    void Stop()
    {
        timer?.Stop();
        timer = null;
    }

    protected override Size MeasureOverride(Size available) => new(double.IsFinite(Width) ? Width : 128, double.IsFinite(Height) ? Height : 128);

    public override void Render(DrawingContext context)
    {
        var sheet = Sheet.Value;
        var f = Frame;
        var source = new Rect(f % Columns * Cell, f / Columns * Cell, Cell, Cell);
        var side = Math.Min(Bounds.Width, Bounds.Height);
        var dest = new Rect((Bounds.Width - side) / 2, (Bounds.Height - side) / 2, side, side);
        context.DrawImage(sheet, source, dest);
    }
}
