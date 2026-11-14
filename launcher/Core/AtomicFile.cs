using System.Text;

namespace LongshotLauncher.Core;

/// A file written whole or not at all: into a temporary file of its own beside it (&lt;name&gt;.&lt;random&gt;.tmp, so two writers never
/// share one), flushed to the disk, then renamed over the old one. A failed write leaves the old file and no temporary one
static class AtomicFile
{
    public static void Write(string path, string text) => Write(path, new UTF8Encoding(false).GetBytes(text));

    public static void Write(string path, byte[] bytes)
    {
        var full = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        var tmp = $"{full}.{Guid.NewGuid():N}.tmp";
        try
        {
            using (var f = new FileStream(tmp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                f.Write(bytes);
                f.Flush(flushToDisk: true);
            }
            File.Move(tmp, full, overwrite: true);
        }
        finally
        {
            try { File.Delete(tmp); } catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
        }
    }
}
