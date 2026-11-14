using LongshotLauncher.Core;

static partial class Program
{
    static void RequirementsChecks()
    {
        RequirementResult Check(IReadOnlyList<GpuRequirement>? gpus, bool os = true, bool avx = true,
            bool linux = true, int ram = 16, long? disk = 60L << 30) =>
            SystemRequirements.Evaluate(os, ram, 12, avx, linux, disk, gpus);
        var good = new[] { new GpuRequirement(true, 8UL << 30, true) };
        Require(Check([new(true, 4UL << 30, false)]).Detail.Contains("4 GB VRAM")
                && Check([new(true, 4UL << 30, false)]).Detail.Contains("No mesh shaders"), "Details show detected VRAM and the missing feature.");
        Require(Check(good, ram: 32).Detail.Contains("32 GB RAM") && !Check(good, ram: 32).Detail.Contains("16 GB RAM"),
                "Good results show detected RAM instead of a threshold presented as the measurement.");
        Require(Check(good).Detail.Contains("8 GB VRAM") && Check(good).Detail.Contains("Mesh shaders available"), "Good results describe verified GPU capabilities.");
        Require(Check(null).Detail.Contains("could not be checked"), "Unknown results explain which check is unavailable.");
        Require(Check(good).Status == RequirementStatus.Green, "Checked requirements met at inclusive RAM/disk/VRAM thresholds.");
        Require(Check(null).Status == RequirementStatus.Gray, "An unavailable Vulkan loader is unknown, not a pass or failure.");
        Require(Check([new(true, 8UL << 30, false)]).Status == RequirementStatus.Yellow, "Missing mesh shaders is a known limitation.");
        Require(Check([new(true, 8UL << 30)]).Status == RequirementStatus.Gray, "Unknown mesh support is gray.");
        Require(Check(good, ram: 4).Status == RequirementStatus.Yellow, "4 GB RAM is a detected limitation.");
        Require(Check([new(true, 4UL << 30, false)], disk: null).Status == RequirementStatus.Yellow, "Known limitations remain yellow even if another check is unknown.");
        Require(Check(good, ram: 0).Status == RequirementStatus.Gray, "Unavailable RAM is gray.");
        Require(Check([new(true, 0, true)]).Status == RequirementStatus.Gray, "Unavailable GPU memory is gray.");
        Require(Check([]).Status == RequirementStatus.Red, "A successful probe with no hardware GPUs is incompatible.");
        Require(Check(good, os: false).Status == RequirementStatus.Red, "Unsupported OS is red.");
        Require(Check(good, avx: false).Status == RequirementStatus.Red, "Linux AppImage requires AVX2.");
        Require(Check(good, avx: false, linux: false).Status == RequirementStatus.Green, "Windows does not require AVX2.");
        Require(Check(good, ram: 8).Status == RequirementStatus.Yellow, "Low RAM estimates warn without blocking.");
        Require(Check(good, disk: null).Status == RequirementStatus.Gray, "Unknown disk space warns.");
        Require(Check(good, disk: (60L << 30) - 1).Status == RequirementStatus.Yellow, "Less than 60 GiB warns.");
        Require(Check([new(true, 4UL << 30)]).Status == RequirementStatus.Yellow, "4 GiB meets minimum but calls for a lower preset.");
        Require(Check([new(false, 16UL << 30), new(true, 2UL << 30)]).Status == RequirementStatus.Yellow,
            "Vulkan and memory must belong to the same GPU.");
        Require(Check([new(false, 16UL << 30), ..good]).Status == RequirementStatus.Green,
            "An older secondary GPU does not fail a usable GPU.");
        // A laptop: an integrated GPU reporting 3/4 of 31 GB RAM without mesh shaders, and an RTX 4070 Laptop GPU's 8188 MiB.
        var laptop = new GpuRequirement[] { new(true, 23300UL << 20, false, GpuKind.Integrated),
            new(true, 8188UL << 20, true, GpuKind.Discrete) };
        Require(Check(laptop).Status == RequirementStatus.Green && Check(laptop).Detail.Contains("Mesh shaders available")
                && Check(laptop).Detail.Contains("8 GB VRAM"),
            "The discrete GPU the game uses is checked, not an integrated GPU reporting more shared memory.");
        Require(Check([..laptop.Reverse()]).Status == RequirementStatus.Green, "The discrete GPU wins in either order.");
        Require(Check([new(true, 8UL << 30, true, GpuKind.Integrated, 1), new(true, 4UL << 30, false, GpuKind.Integrated, 2)])
                .Detail.Contains("No mesh shaders"), "Between GPUs of one kind, the newer driver is checked, as in the game.");
        Require(Check([new(true, (8UL << 30) - (300UL << 20), true)]).Status == RequirementStatus.Yellow,
            "Well under 8 GB still calls for a lower preset.");
    }
}
