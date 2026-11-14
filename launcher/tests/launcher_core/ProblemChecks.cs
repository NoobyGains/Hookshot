using HookshotLauncher.Core;

/// launcher/Core/Problems.cs: the messages make_game.py and the game write mapped to a problem and its fix, and a crash found
/// once in a build's newest log. No game, no network.
static partial class Program
{
    static void ProblemChecks()
    {
        // build failures: make_game.py's own messages
        Require(Problems.FromBuild("Files of the builder's own compiler are missing (clang.exe in tools). Your antivirus most likely removed them").Kind == ProblemKind.Antivirus,
                "the antivirus message: Antivirus");
        Require(Problems.FromBuild("This is build 1a2b3c4d. Hookshot supports build e0f3ccfa.").Kind == ProblemKind.WrongGameVersion,
                "another build: WrongGameVersion");
        Require(Problems.FromBuild("Your game dump is incomplete: 12 game files in it are damaged").Kind == ProblemKind.IncompleteDump,
                "an incomplete dump");
        Require(Problems.FromBuild("OSError: [Errno 28] No space left on device").Kind == ProblemKind.DiskFull, "no space: DiskFull");
        var mem = Problems.FromBuild("the system stopped it, most likely because the PC ran out of memory. Close other programs and build again");
        Require(mem.Kind == ProblemKind.BuildMemory && mem.Fixes.Any(f => f.Kind == FixKind.LowerBuildMemory), "out of memory: lower the build memory");
        Require(Problems.FromBuild("something new").Kind == ProblemKind.Unknown, "an unknown message: Unknown, not a wrong fix");
        Require(Problems.FromBuild("The builder's own compiler (tools/llvm-mingw) could not build a test program: x. Unpack the zip again " +
                                   "into a folder your antivirus allows.").Kind == ProblemKind.Antivirus, "the compiler can't build: Antivirus");
        // (messages that name an antivirus, a free space or "not supported" among causes of their own: as make_game.py said them)
        Require(Problems.FromBuild(@"Could not clear C:\Hookshot\work\gen ([WinError 32] in use). A file in it is in use: close any window " +
                                   "showing that folder, wait for your antivirus to finish, then try again.").Kind == ProblemKind.Unknown,
                "a folder in use: not Antivirus");
        Require(Problems.FromBuild(@"The translated game came out cut short twice (code_12.c). Check that the drive with C:\work has free " +
                                   "space, and that no antivirus and no second Hookshot Builder is working in that folder, then update again.").Kind ==
                ProblemKind.Unknown, "cut short twice: not Antivirus, not DiskFull");
        Require(Problems.FromBuild(@"The generated cache path D:\out\cache is not a normal path inside the build folder (symbolic links and " +
                                   "reparse points are not supported). Choose a different output folder.").Kind == ProblemKind.Unknown,
                "a reparse point: not WrongGameVersion");

        // a run's log
        Require(Problems.FromLog(["vk: start", "vk: 2400 presents, 60.0 fps"]) == null, "a clean log: no problem");
        var crash = Problems.FromLog(["vk: start",
            @"CRASH: exception 0xC0000005 (read 0x590, guest 0x0) at C:\Windows\System32\nvoglv64.dll+0x1234",
            "CRASH: host backtrace: nvoglv64.dll+0x1234 hookshot_vk.dll+0x99"], SystemInfo.Nvidia);
        Require(crash is { Kind: ProblemKind.GameCrashed } && crash.Signature == "0xc0000005 nvoglv64.dll+0x1234",
                "a crash: its code and module+offset, no folder, as the signature: " + crash?.Signature);
        Require(crash!.Fixes[0].Link == Problems.DriverPage(SystemInfo.Nvidia), "a crash: NVIDIA's driver page");
        Require(Problems.FromLog(["vk: VK_ERROR_DEVICE_LOST on submit"], SystemInfo.Amd)?.Kind == ProblemKind.GpuLost, "device lost: GpuLost");
        const string noMesh = "vk: this GPU has no mesh shaders: the game's foliage, grass and many effects cannot be drawn";
        Require(Problems.FromLog(["vk: start", noMesh, "vk: 2400 presents, 60.0 fps"]) == null,
                "no mesh shaders alone: a warning the game goes on after, not a problem");
        Require(Problems.FromLog([noMesh, "CRASH: exception 0xc0000005 (read 0x0, guest 0x1) at hookshot+0x10"])?.Kind ==
                ProblemKind.NoMeshShaders, "no mesh shaders, then a crash: NoMeshShaders");
        // (the driver link for the GPU the game ran on, from its log: not the device list's first card, not the vendor passed)
        var hybrid = Problems.FromLog(["vk: device 0: Intel(R) UHD Graphics 770, Vulkan 1.3, driver 0x1, type 1",
            "vk: device 1: NVIDIA GeForce RTX 4070 Ti, Vulkan 1.4, driver 0x2, type 2",
            "vk: NVIDIA GeForce RTX 4070 Ti, Vulkan 1.4, driver 0x2; mesh shaders yes, host memory import yes, pipeline libraries yes",
            "CRASH: exception 0xc0000005 (read 0x0, guest 0x1) at hookshot+0x10"], SystemInfo.Intel);
        Require(hybrid?.Fixes[0].Link == Problems.DriverPage(SystemInfo.Nvidia), "the log's GPU: NVIDIA's driver page, not the iGPU's");
        Require(SystemInfo.VendorOfName("AMD Radeon RX 7900 XTX (RADV NAVI31)") == SystemInfo.Amd &&
                SystemInfo.VendorOfName("Intel(R) Arc(tm) A770 Graphics") == SystemInfo.Intel &&
                SystemInfo.VendorOfName("llvmpipe (LLVM 19.1.7, 256 bits)") == null, "a GPU's maker by its name");

        // a crash found once, in the newest log only, and only a recent one
        var game = Folder("problem-build");
        var log = Path.Combine(game, "hookshot_log.txt");
        File.WriteAllText(log, "vk: NVIDIA GeForce RTX 4070 Ti, Vulkan 1.4, driver 0x1; mesh shaders native, host memory import yes\n" +
                               "opened /home/ann/Games/Hookshot/romfs\nCRASH: exception 0xc0000005 (read 0x0, guest 0x1) at hookshot+0x10\n");
        var found = CrashCheck.Find(game, 0);
        Require(found != null && found.Log == log, "a crashed run's log: found");
        Require(found!.Problem.Fixes[0].Link == Problems.DriverPage(SystemInfo.Nvidia), "a crashed run's log: its GPU's driver page");
        Require(CrashCheck.Find(game, found.WriteTicks) == null, "offered once: not again");
        Require(CrashCheck.Find(game, 0, found.WriteTicks + 1) == null, "a log from before the launcher first looked: not offered");
        File.Move(log, Path.Combine(game, "hookshot_log.1.txt"));
        File.WriteAllText(log, "vk: a clean run\n");
        Require(CrashCheck.Find(game, 0) == null, "played again since without a problem: the run before's crash is not offered");

        // the game's logs/ folder (Hookshot's game folder layout): its log found there, and the newer of the two places wins
        var newer = Folder("problem-build-logs");
        Directory.CreateDirectory(Path.Combine(newer, CrashCheck.LogsFolder));
        var inLogs = Path.Combine(newer, CrashCheck.LogsFolder, "hookshot_log.txt");
        File.WriteAllText(inLogs, "vk: NVIDIA GeForce RTX 4070 Ti, Vulkan 1.4, driver 0x1; mesh shaders native, host memory import yes\n" +
                                  "CRASH: exception 0xc0000005 (read 0x0, guest 0x1) at hookshot+0x10\n");
        var inFolder = CrashCheck.Find(newer, 0);
        Require(inFolder != null && inFolder.Log == inLogs, "a crashed run's log in logs/: found");
        var loose = Path.Combine(newer, "hookshot_log.txt");
        File.WriteAllText(loose, "vk: an older build's run\n");
        File.SetLastWriteTimeUtc(loose, File.GetLastWriteTimeUtc(inLogs).AddMinutes(-5));
        Require(CrashCheck.LogPath(newer) == inLogs, "logs/ and a loose log from before: the newer, logs/");
        File.SetLastWriteTimeUtc(loose, File.GetLastWriteTimeUtc(inLogs).AddMinutes(5));
        Require(CrashCheck.LogPath(newer) == loose && CrashCheck.Find(newer, 0) == null,
                "a loose log newer than logs/ (a build from before ran since): that run's, and it went well");
    }
}
