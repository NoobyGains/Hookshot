using System.Globalization;
using Avalonia;
using Avalonia.Headless;
using Avalonia.Threading;
using HookshotLauncher;
using HookshotLauncher.Core;
using HookshotLauncher.ViewModels;

// The launcher's pages drawn with no screen, each into a PNG: the docs' pictures (docs/images/launcher) and CI's check that every
// page draws. Everything it shows is made up here, in a scratch folder: no build, no game file, no save of this PC, no network.
//     dotnet run --project launcher/tools/screens -c Release -- <out folder> [<language code>]
if (args.Length is < 1 or > 2)
{
    Console.Error.WriteLine("usage: screens <out folder> [language]");
    return 2;
}
var outDir = Path.GetFullPath(args[0]);
Directory.CreateDirectory(outDir);
// (no page transitions and no turning: each picture is the page as it stands; and no check of this PC's releases)
Environment.SetEnvironmentVariable("HOOKSHOT_LAUNCHER_REDUCED_MOTION", "1");
Environment.SetEnvironmentVariable("HOOKSHOT_LAUNCHER_OFFLINE", "1");
// (HOOKSHOT_SCREENS_SCRATCH: where the made-up builds and saves go, shown in the pictures' paths; a temporary folder otherwise)
var scratch = Path.Combine(Environment.GetEnvironmentVariable("HOOKSHOT_SCREENS_SCRATCH") is { Length: > 0 } at ? at : Path.GetTempPath(),
                           "hookshot-screens-" + Environment.ProcessId.ToString(CultureInfo.InvariantCulture));
Directory.CreateDirectory(scratch);

AppBuilder.Configure<App>().UseSkia().UseHeadless(new AvaloniaHeadlessPlatformOptions { UseHeadlessDrawing = false }).SetupWithoutStarting();
Tr.Use(args.Length > 1 ? args[1] : "en");

var failures = 0;
try
{
    Screens.Run(outDir, scratch, ref failures);
}
finally
{
    try { Directory.Delete(scratch, recursive: true); }
    catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
}
Console.WriteLine(failures == 0 ? "screens: every page drawn" : $"screens: {failures} pages failed");
return failures == 0 ? 0 : 1;

static class Screens
{
    const string Nightly = "v2.3.0-rc.9-4-ge47baf3f", Candidate = "v2.3.0-rc.9";

    public static void Run(string outDir, string scratch, ref int failures)
    {
        var builds = Path.Combine(scratch, "Games", "Hookshot");
        var appData = Path.Combine(scratch, "AppData", "Roaming");
        Func<string, string?> env = k => k switch
        {
            "HOME" or "USERPROFILE" => scratch,
            "APPDATA" => appData,
            "LOCALAPPDATA" => Path.Combine(scratch, "AppData", "Local"),
            "XDG_DATA_HOME" => Path.Combine(scratch, ".local", "share"),
            _ => null,
        };
        FakeSave(Path.Combine(appData, "Hookshot", "save", Saves.UserId), 3);
        FakeSave(Path.Combine(appData, "Longshot", "save", "00112233445566778899aabbccddeeff"), 2);

        // (the first start: nothing built yet, GitHub's answer in)
        var empty = Service(Path.Combine(scratch, "home-empty"), env, builds);
        Shoot(outDir, "home-first-start", empty, main => { }, ref failures);

        // (two versions built: a nightly, the default, with an update, and a release candidate)
        var service = Service(Path.Combine(scratch, "home"), env, builds);
        var nightly = FakeBuild(service, Path.Combine(builds, Nightly), Nightly, "nightly", makeDefault: true);
        FakeBuild(service, Path.Combine(builds, Candidate), Candidate, "rc");
        service.SetNewest("nightly", "v2.3.0-rc.9-7-g0a1b2c3d");
        service.Registry.Save();
        Shoot(outDir, "home", service, main => main.Home.Refresh(), ref failures);
        Shoot(outDir, "channel-picker", service, main => main.Modal = new ChannelPickerViewModel(main, "nightly"), ref failures);

        // (the wizard: step 1 with the builder downloading and a game file found, step 2, step 3 in the compile)
        Shoot(outDir, "wizard-1-game-files", service, main =>
        {
            var step = main.StartWizard(JobKind.Build, "nightly", "v2.3.0-rc.9-7-g0a1b2c3d", tools: false);
            Pump(() => !step.Searching);
            step.Files.Clear();
            var file = new GameFileViewModel(step, new FoundGameFile(Path.Combine(scratch, "Downloads", "Ocarina.nup"), "Downloads",
                                                                     7_650_000_000, new DateTime(2026, 11, 2), false))
            {
                Check = new GameCheck(GameCheckStatus.Supported, "The supported version (build e0f3ccfa)."),
            };
            step.Files.Add(file);
            file.IsPicked = true;
            step.ShowToolsAt(0.62, 545_000_000);
            // (this PC's own memory, graphics card and free space are not the pictures' business: a PC that meets them)
            Pump(() => !step.RequirementsGray);
            typeof(FilesStepViewModel).GetField("requirements", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!
                .SetValue(step, new RequirementResult(RequirementStatus.Green, "This PC meets the requirements",
                                                      "32 GB RAM · Vulkan 1.3 · 12 GB VRAM · Mesh shaders available · 210 GB free"));
            foreach (var name in new[] { "RequirementsSummary", "RequirementsDetail", "RequirementsGreen", "RequirementsGray" })
                typeof(ViewModelBase).GetMethod("Raise", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance,
                                                new[] { typeof(string) })!.Invoke(step, new object?[] { name });
        }, ref failures);
        Shoot(outDir, "wizard-2-settings", service, main =>
        {
            var job = new BuildJob(main, JobKind.Build, "nightly", "v2.3.0-rc.9-7-g0a1b2c3d", null);
            main.Navigate(new SettingsStepViewModel(job));
        }, ref failures);
        Shoot(outDir, "wizard-3-build", service, main =>
        {
            var job = new BuildJob(main, JobKind.Build, "nightly", "v2.3.0-rc.9-7-g0a1b2c3d", null);
            var build = new BuildStepViewModel(job, start: false);
            main.Navigate(build);
            var at = TimeSpan.Zero;
            var lines = new List<(string, TimeSpan)>();
            void Say(string line, double seconds) => lines.Add((line, at += TimeSpan.FromSeconds(seconds)));
            Say("@@stage read Reading your game files", 2);
            Say("@@progress 1", 40);
            Say("@@stage lift Translating the game to PC code", 1);
            Say("@@progress 1", 200);
            Say("@@stage compile Compiling", 1);
            Say("@@plan 588 588", 1);
            for (var i = 0; i < 230; i++) Say($"@@file mod_{i:000}.c 2.1 new", 1.2);
            Say("@@progress 0.39", 1);
            Say("@@eta 412", 1);
            build.Replay(lines);
        }, ref failures);

        // (the saves: Hookshot's, which every version shares; and the import from Longshot)
        Shoot(outDir, "saves", service, main => main.ShowSaves(), ref failures);
        Shoot(outDir, "saves-import-longshot", service, main =>
        {
            main.ShowSaves();
            main.Modal = new LongshotImportViewModel(main);
        }, ref failures);

        // (the launcher's settings, and its About at the end)
        Shoot(outDir, "settings", service, main => main.ShowSettings(), ref failures);
        Shoot(outDir, "settings-about", service, main => main.ShowSettings(), ref failures, window =>
        {
            foreach (var scroller in Avalonia.VisualTree.VisualExtensions.GetVisualDescendants(window).OfType<Avalonia.Controls.ScrollViewer>())
                scroller.ScrollToEnd();
        });
        _ = nightly;
    }

    static LauncherService Service(string home, Func<string, string?> env, string builds)
    {
        var service = LauncherService.Open(Platform.Windows, new LauncherHome(home));
        service.SaveEnv = new SaveEnvironment(Platform.Windows, env);
        service.Settings.BuildsFolder = builds;
        service.Settings.Work = Path.Combine(Path.GetDirectoryName(builds)!, "Hookshot build files");
        service.Gpus = Array.Empty<string>();
        service.SetNewest("stable", "v2.2.0");
        service.SetNewest("rc", Candidate);
        service.SetNewest("nightly", Nightly);
        service.Checked = true;
        return service;
    }

    static BuildEntry FakeBuild(LauncherService service, string folder, string version, string channel, bool makeDefault = false)
    {
        Directory.CreateDirectory(Path.Combine(folder, "bin"));
        File.WriteAllText(Path.Combine(folder, "bin", "hookshot.exe"), "not the game: a picture's stand-in\n");
        File.WriteAllText(Path.Combine(folder, GameFolder.StampName), $"version={version}\n");
        var entry = service.Registry.Add(folder, version, channel, makeDefault: makeDefault);
        entry.Bytes = 3_400_000_000;
        return entry;
    }

    static void FakeSave(string profile, int slots)
    {
        Directory.CreateDirectory(profile);
        File.WriteAllText(Path.Combine(profile, "account.sav"), "FAKE SAVE: not a game file\n");
        File.WriteAllText(Path.Combine(profile, "option.sav"), "FAKE SAVE: not a game file\n");
        for (var i = 0; i < slots; i++)
        {
            var slot = Path.Combine(profile, $"slot_{i:00}");
            Directory.CreateDirectory(slot);
            File.WriteAllText(Path.Combine(slot, "progress.sav"), "FAKE SAVE: not a game file\n");
            File.WriteAllText(Path.Combine(slot, "caption.sav"), "FAKE SAVE: not a game file\n");
            File.SetLastWriteTime(Path.Combine(slot, "progress.sav"), new DateTime(2026, 11, 12 - i, 21, 40 - i * 7, 0));
        }
    }

    /// The jobs of the UI thread run until done says so (or about 20 s)
    static void Pump(Func<bool> done)
    {
        for (var i = 0; i < 400 && !done(); i++)
        {
            Dispatcher.UIThread.RunJobs();
            Thread.Sleep(50);
        }
        Dispatcher.UIThread.RunJobs();
    }

    /// The UI thread's jobs, and what work in the background posts back to it, run for a moment
    static void Settle()
    {
        for (var i = 0; i < 12; i++)
        {
            Dispatcher.UIThread.RunJobs();
            Thread.Sleep(25);
        }
    }

    static void Shoot(string outDir, string name, LauncherService service, Action<MainViewModel> show, ref int failures,
                      Action<MainWindow>? then = null)
    {
        try
        {
            var main = new MainViewModel(service, StartRequest.Parse(Array.Empty<string>()));
            var window = new MainWindow { DataContext = main };
            window.Show();
            show(main);
            Settle();
            if (then != null)
            {
                then(window);
                Settle();
            }
            for (var i = 0; i < 3; i++)
            {
                Dispatcher.UIThread.RunJobs();
                AvaloniaHeadlessPlatform.ForceRenderTimerTick();
            }
            var frame = window.CaptureRenderedFrame() ?? throw new InvalidOperationException("nothing was drawn");
            var path = Path.Combine(outDir, name + ".png");
            frame.Save(path, new Avalonia.Media.Imaging.PngBitmapEncoderOptions());
            window.Close();
            Console.WriteLine($"{name}: {frame.PixelSize.Width}x{frame.PixelSize.Height}");
        }
        catch (Exception e)
        {
            failures++;
            Console.Error.WriteLine($"{name}: FAILED {e}");
        }
    }
}
