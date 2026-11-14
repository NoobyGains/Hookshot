using System.Security.Cryptography;
using System.Text;

namespace HookshotLauncher.Core;

/// One launcher per home at a time: two would install the same toolchain into one folder and write builds.json and settings.json
/// over each other. Windows: a named mutex for the home (Local\HookshotLauncher-&lt;hash of the home&gt;); Linux: &lt;home&gt;/launcher.lock
/// held open with an exclusive flock (FileShare.None), which the system lets go when the process ends, however it ends.
/// A second start pokes the first (Poke: &lt;home&gt;/launcher.show), which brings its window forward, and closes.
public sealed class InstanceLock : IDisposable
{
    public const string LockName = "launcher.lock", PokeName = "launcher.show";

    readonly Mutex? mutex;
    readonly FileStream? file;

    InstanceLock(Mutex? mutex, FileStream? file)
    {
        this.mutex = mutex;
        this.file = file;
    }

    /// The mutex's name for a home: the same for the same folder however it is spelled (case on Windows, a trailing separator)
    public static string MutexName(string root)
    {
        var full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(root)).ToUpperInvariant();
        return @"Local\HookshotLauncher-" + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(full)))[..32];
    }

    /// This launcher's hold on the home; null when another launcher holds it
    public static InstanceLock? TryAcquire(string root, Platform platform)
    {
        Directory.CreateDirectory(root);
        if (platform == Platform.Windows)
        {
            var m = new Mutex(false, MutexName(root));
            try
            {
                if (m.WaitOne(0)) return new InstanceLock(m, null);
            }
            catch (AbandonedMutexException) { return new InstanceLock(m, null); }   // (the last one ended without letting go: it is ours now)
            m.Dispose();
            return null;
        }
        try
        {
            var f = new FileStream(Path.Combine(root, LockName), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            return new InstanceLock(null, f);
        }
        catch (IOException) { return null; }
    }

    /// Asks the launcher that holds the home to bring its window forward
    public static void Poke(string root)
    {
        try { AtomicFile.Write(Path.Combine(root, PokeName), DateTimeOffset.UtcNow.ToString("O", System.Globalization.CultureInfo.InvariantCulture)); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
    }

    /// Calls poked whenever another start pokes this home (on a thread of its own: the caller posts to its UI)
    public static IDisposable Watch(string root, Action poked)
    {
        var w = new FileSystemWatcher(root, PokeName) { NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite };
        w.Created += (_, _) => poked();
        w.Changed += (_, _) => poked();
        w.Renamed += (_, e) => { if (e.Name == PokeName) poked(); };
        w.EnableRaisingEvents = true;
        return w;
    }

    public void Dispose()
    {
        if (mutex != null)
        {
            try { mutex.ReleaseMutex(); } catch (ApplicationException) { }
            mutex.Dispose();
        }
        file?.Dispose();
    }
}
