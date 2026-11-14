using System.Runtime.InteropServices;
using System.Runtime.Intrinsics.X86;

namespace HookshotLauncher.Core;

public enum RequirementStatus { Gray, Green, Yellow, Red }
public sealed record RequirementResult(RequirementStatus Status, string Summary, string Detail);

/// Local, advisory checks against the published requirements. Never blocks downloading or building.
public static class SystemRequirements
{
    public static string Url => Repository.Page(Repository.Current) + "#what-you-need";   // (the readme's "What you need")
    public static RequirementResult Evaluate(bool supportedOs, int memoryGb, int threads, bool avx2,
        bool linux, long? freeBytes, IReadOnlyList<GpuRequirement>? gpus)
    {
        var observed = new List<string>();
        var failures = new List<string>();
        var warnings = new List<string>();
        var unknown = new List<string>();
        if (!supportedOs) failures.Add(Tr.T("Requires 64-bit Windows 10/11 or Linux with glibc 2.35+"));
        if (memoryGb > 0) observed.Add(Tr.F("{0} GB RAM", memoryGb));
        if (memoryGb <= 0) unknown.Add(Tr.T("RAM could not be checked"));
        else if (memoryGb < 16) warnings.Add(Tr.T("16 GB RAM minimum"));
        if (threads <= 0) unknown.Add(Tr.T("CPU thread count could not be checked"));
        else if (threads < 6) warnings.Add(Tr.F("{0} CPU threads; a 6-core CPU is suggested", threads));
        if (linux && !avx2) failures.Add(Tr.T("The Linux AppImage requires AVX2"));
        if (freeBytes is null) unknown.Add(Tr.T("Free disk space could not be checked"));
        else if (freeBytes < 60L << 30) warnings.Add(Tr.F("{0} GB free; about 60 GB needed for building", FormattableString.Invariant($"{freeBytes.Value / (double)(1L << 30):0.#}")));
        if (gpus is null) unknown.Add(Tr.T("GPU support could not be checked; requires Vulkan 1.3 and 4 GB VRAM"));
        else if (!gpus.Any(g => g.Vulkan13)) failures.Add(Tr.T("No Vulkan 1.3 GPU found; check your graphics driver"));
        else
        {
            // Check the GPU the game will use (Hookshot's pick_device in gpu/vk/vk_main.cpp): a discrete GPU over an
            // integrated one, then the newer driver. Never combine different cards' capabilities. An integrated GPU
            // reports a share of system RAM as its memory, so ranking by memory picks it over a laptop's own card.
            var gpu = gpus.Where(g => g.Vulkan13)
                .OrderByDescending(g => g.Kind).ThenByDescending(g => g.DriverVersion).First();
            observed.Add("Vulkan 1.3");
            if (gpu.MemoryBytes > 0) observed.Add(Tr.F("{0} GB VRAM", FormattableString.Invariant($"{gpu.MemoryBytes / (double)(1UL << 30):0.#}")));
            if (gpu.MeshShaders == true) observed.Add(Tr.T("Mesh shaders available"));
            if (gpu.MemoryBytes == 0) unknown.Add(Tr.T("GPU memory could not be checked"));
            else if (!AtLeastGb(gpu.MemoryBytes, 4)) warnings.Add(Tr.T("4 GB VRAM minimum; shared memory may differ"));
            else if (!AtLeastGb(gpu.MemoryBytes, 8)) warnings.Add(Tr.T("8 GB VRAM recommended"));
            if (gpu.MeshShaders == false) warnings.Add(Tr.T("No mesh shaders; using the slower compute fallback"));
            else if (gpu.MeshShaders is null) unknown.Add(Tr.T("Mesh shader support could not be checked"));
        }
        var status = failures.Count > 0 ? RequirementStatus.Red : warnings.Count > 0 ? RequirementStatus.Yellow
            : unknown.Count > 0 ? RequirementStatus.Gray : RequirementStatus.Green;
        var summary = status switch
        {
            RequirementStatus.Red => Tr.T("Compatibility issue found"),
            RequirementStatus.Yellow => Tr.T("Limited hardware"),
            RequirementStatus.Gray => Tr.T("Some requirements are unknown"),
            _ => Tr.T("Checked requirements met"),
        };
        var detail = string.Join(" · ", observed.Concat(failures).Concat(warnings).Concat(unknown));
        return new(status, summary, detail + (detail.EndsWith('.') || detail.EndsWith('。') ? "" : Tr.T(".")));
    }

    // A card sold as 8 GB reports a little less as its memory heap (an RTX 4070 Laptop GPU: 8188 MiB), so the thresholds
    // allow 256 MiB under the marketed size.
    static bool AtLeastGb(ulong bytes, int gb) => bytes >= ((ulong)gb << 30) - (256UL << 20);

    public static RequirementResult Check(string folder)
    {
        bool linux = OperatingSystem.IsLinux();
        bool os = RuntimeInformation.OSArchitecture == Architecture.X64 &&
            (OperatingSystem.IsWindowsVersionAtLeast(10) || linux && GlibcSupported());
        return Evaluate(os, SystemInfo.MemoryGb(), SystemInfo.Threads(), Avx2.IsSupported, linux,
            Disk.FreeBytes(folder), VulkanRequirements.Read());
    }

    static bool GlibcSupported()
    {
        try { return Version.TryParse(Marshal.PtrToStringAnsi(gnu_get_libc_version()), out var v) && v >= new Version(2, 35); }
        catch (Exception e) when (e is DllNotFoundException or EntryPointNotFoundException) { return false; }
    }
    [DllImport("libc.so.6")] static extern IntPtr gnu_get_libc_version();
}

/// Ordered as the game prefers them: VkPhysicalDeviceType discrete over integrated over the rest.
public enum GpuKind { Other, Integrated, Discrete }
public sealed record GpuRequirement(bool Vulkan13, ulong MemoryBytes, bool? MeshShaders = null,
    GpuKind Kind = GpuKind.Other, uint DriverVersion = 0);

/// Queries the installed Vulkan loader without external utilities or a Vulkan package.
internal static class VulkanRequirements
{
    [StructLayout(LayoutKind.Sequential)] struct InstanceInfo
    {
        public uint Type; public IntPtr Next; public uint Flags; public IntPtr Application;
        public uint LayerCount; public IntPtr Layers; public uint ExtensionCount; public IntPtr Extensions;
    }
    [StructLayout(LayoutKind.Sequential)] struct ApplicationInfo
    {
        public uint Type; public IntPtr Next; public IntPtr Name; public uint Version;
        public IntPtr Engine; public uint EngineVersion; public uint ApiVersion;
    }
    [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate IntPtr GetProc(IntPtr instance, [MarshalAs(UnmanagedType.LPStr)] string name);
    [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate int Create(ref InstanceInfo info, IntPtr allocator, out IntPtr instance);
    [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate void Destroy(IntPtr instance, IntPtr allocator);
    [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate int Enumerate(IntPtr instance, ref uint count, IntPtr devices);
    [UnmanagedFunctionPointer(CallingConvention.Winapi)] delegate void Properties(IntPtr device, IntPtr properties);

    public static IReadOnlyList<GpuRequirement>? Read()
    {
        IntPtr library = IntPtr.Zero, instance = IntPtr.Zero, devices = IntPtr.Zero, buffer = IntPtr.Zero, application = IntPtr.Zero;
        Destroy? destroy = null;
        try
        {
            if (!NativeLibrary.TryLoad(OperatingSystem.IsWindows() ? "vulkan-1.dll" : "libvulkan.so.1", out library)) return null;
            T Function<T>(string name) where T : Delegate => Marshal.GetDelegateForFunctionPointer<T>(NativeLibrary.GetExport(library, name));
            var create = Function<Create>("vkCreateInstance");
            destroy = Function<Destroy>("vkDestroyInstance");
            var enumerate = Function<Enumerate>("vkEnumeratePhysicalDevices");
            var properties = Function<Properties>("vkGetPhysicalDeviceProperties");
            var memory = Function<Properties>("vkGetPhysicalDeviceMemoryProperties");
            application = Marshal.AllocHGlobal(Marshal.SizeOf<ApplicationInfo>());
            Marshal.StructureToPtr(new ApplicationInfo { ApiVersion = (1u << 22) | (1u << 12) }, application, false);
            var info = new InstanceInfo { Type = 1, Application = application };
            bool featuresSupported = create(ref info, IntPtr.Zero, out instance) == 0;
            if (!featuresSupported)
            {
                info.Application = IntPtr.Zero; // Older loaders still allow an API/memory check.
                if (create(ref info, IntPtr.Zero, out instance) != 0) return null;
            }
            var featuresPointer = featuresSupported ? Function<GetProc>("vkGetInstanceProcAddr")(instance, "vkGetPhysicalDeviceFeatures2") : IntPtr.Zero;
            var features = featuresPointer == IntPtr.Zero ? null : Marshal.GetDelegateForFunctionPointer<Properties>(featuresPointer);
            uint count = 0;
            if (enumerate(instance, ref count, IntPtr.Zero) != 0 || count > 64) return null;
            devices = Marshal.AllocHGlobal((int)count * IntPtr.Size);
            if (enumerate(instance, ref count, devices) != 0) return null;
            buffer = Marshal.AllocHGlobal(4096);
            var result = new List<GpuRequirement>();
            for (int i = 0; i < count; i++)
            {
                var device = Marshal.ReadIntPtr(devices, i * IntPtr.Size);
                properties(device, buffer);
                // VkPhysicalDeviceProperties: apiVersion, driverVersion, vendorID, deviceID, deviceType.
                uint api = (uint)Marshal.ReadInt32(buffer);
                uint driver = (uint)Marshal.ReadInt32(buffer, 4);
                int type = Marshal.ReadInt32(buffer, 16);
                // CPU software renderers are not suitable game GPUs.
                if (type == 4) continue;
                var kind = type switch { 1 => GpuKind.Integrated, 2 => GpuKind.Discrete, _ => GpuKind.Other };
                memory(device, buffer);
                uint heaps = (uint)Marshal.ReadInt32(buffer, 260);
                // The largest device-local heap, as the game measures VRAM: AMD without resizable BAR lists its
                // CPU-visible 256 MiB of VRAM as a heap of its own, which a sum would count twice.
                ulong bytes = 0;
                for (int h = 0; h < Math.Min(heaps, 16); h++)
                    if ((Marshal.ReadInt32(buffer, 264 + h * 16 + 8) & 1) != 0)
                        bytes = Math.Max(bytes, (ulong)Marshal.ReadInt64(buffer, 264 + h * 16));
                bool? mesh = null;
                if (features != null)
                {
                    // VkPhysicalDeviceFeatures2 -> VkPhysicalDeviceMeshShaderFeaturesEXT.
                    // Structure IDs and field offsets follow the Vulkan headers (64-bit ABI).
                    Marshal.Copy(new byte[1024], 0, buffer, 1024);
                    Marshal.WriteInt32(buffer, 1000059000);
                    Marshal.WriteIntPtr(buffer, 8, buffer + 512);
                    Marshal.WriteInt32(buffer, 512, 1000328000);
                    features(device, buffer);
                    // taskShader and meshShader: the game uses mesh shaders only with both.
                    mesh = Marshal.ReadInt32(buffer, 512 + 16) != 0 && Marshal.ReadInt32(buffer, 512 + 20) != 0;
                }
                result.Add(new(api >= ((1u << 22) | (3u << 12)), bytes, mesh, kind, driver));
            }
            return result;
        }
        catch (Exception e) when (e is DllNotFoundException or EntryPointNotFoundException or BadImageFormatException) { return null; }
        finally
        {
            if (application != IntPtr.Zero) Marshal.FreeHGlobal(application);
            if (buffer != IntPtr.Zero) Marshal.FreeHGlobal(buffer);
            if (devices != IntPtr.Zero) Marshal.FreeHGlobal(devices);
            if (instance != IntPtr.Zero) destroy?.Invoke(instance, IntPtr.Zero);
            if (library != IntPtr.Zero) NativeLibrary.Free(library);
        }
    }
}
