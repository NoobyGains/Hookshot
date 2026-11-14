using System.Buffers.Binary;
using System.IO.Compression;

/// App/Assets/longshot.ico (scripts/make_icon.py): every size Windows asks for, its 256 the logo, App/Assets/longshot.png
static partial class Program
{
    /// An 8-bit RGBA PNG's pixels (not interlaced: what longshot.png and the icon's 256 are)
    static byte[] PngPixels(byte[] png, int size)
    {
        var data = new MemoryStream();
        for (var at = 8; at < png.Length; at += 12 + BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(at)))
            if (png.AsSpan(at + 4, 4).SequenceEqual("IDAT"u8)) data.Write(png, at + 8, BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(at)));
        var raw = new MemoryStream();
        new ZLibStream(new MemoryStream(data.ToArray()), CompressionMode.Decompress).CopyTo(raw);
        var (bytes, stride) = (raw.ToArray(), size * 4);
        var px = new byte[size * stride];
        for (var i = 0; i < px.Length; i++)
        {
            int y = i / stride, x = i % stride, filter = bytes[y * (stride + 1)];
            int a = x >= 4 ? px[i - 4] : 0, b = y > 0 ? px[i - stride] : 0, c = x >= 4 && y > 0 ? px[i - stride - 4] : 0;
            int p = a + b - c, pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c);
            px[i] = (byte)(bytes[y * (stride + 1) + 1 + x] + filter switch
            {
                0 => 0, 1 => a, 2 => b, 3 => (a + b) / 2,
                _ => pa <= pb && pa <= pc ? a : pb <= pc ? b : c,
            });
        }
        return px;
    }

    static void IconChecks(string repo)
    {
        var ico = File.ReadAllBytes(Path.Combine(repo, "App", "Assets", "longshot.ico"));
        var sizes = Enumerable.Range(0, BinaryPrimitives.ReadUInt16LittleEndian(ico.AsSpan(4))).Select(i => ico[6 + 16 * i] == 0 ? 256 : ico[6 + 16 * i]).ToList();
        Require(sizes.SequenceEqual(new[] { 16, 20, 24, 32, 40, 48, 64, 96, 128, 256 }), "longshot.ico has every size: " + string.Join(", ", sizes));

        // (its 256 against the logo averaged down: the old blue artwork differs by about 21 of 255, the logo by under 1)
        var entry = 6 + 16 * (sizes.Count - 1);
        var icon = PngPixels(ico.AsSpan(BinaryPrimitives.ReadInt32LittleEndian(ico.AsSpan(entry + 12)), BinaryPrimitives.ReadInt32LittleEndian(ico.AsSpan(entry + 8))).ToArray(), 256);
        var logo = PngPixels(File.ReadAllBytes(Path.Combine(repo, "App", "Assets", "longshot.png")), 512);
        double diff = 0;
        for (var i = 0; i < icon.Length; i++)
        {
            int y = i / 1024, x = i % 1024 / 4, ch = i % 4, at = (y * 2 * 512 + x * 2) * 4 + ch;
            diff += Math.Abs((logo[at] + logo[at + 4] + logo[at + 2048] + logo[at + 2052]) / 4.0 - icon[i]) * (ch == 3 ? 1 : icon[i - ch + 3] / 255.0);
        }
        Require(diff / icon.Length < 8, $"longshot.ico's 256 is the logo, longshot.png (differs by {diff / icon.Length:0.0} of 255).");
    }
}
