using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace LongshotLauncher.Core;

public sealed record HookshotSettingsCopy(string Source, string Target, IReadOnlyList<string> Files, string? Backup,
                                         IReadOnlyList<string> SkippedKeys, string? Language = null);

/// The settings a Hookshot game folder can bring into one Longshot build. Saves and the shared user folder are separate.
public static class HookshotSettings
{
    public const int MaxFileSize = 64 << 10;
    static readonly UTF8Encoding Utf8 = new(false, true);
    static readonly string[] TargetFiles = { "longshot_options.ini", "language.txt" };
    static readonly HashSet<string> Buttons = new("a b x y ls rs l r zl zr plus minus left up right down".Split(' '), StringComparer.Ordinal);
    static readonly HashSet<string> Keys = new(Buttons.Concat("move_up move_down move_left move_right cam_up cam_down cam_left cam_right".Split(' ')), StringComparer.Ordinal);
    static readonly Regex KeyName = new("^[a-z][a-z0-9_-]{0,63}$", RegexOptions.CultureInvariant);
    static readonly Dictionary<string, (int Min, int Max)> Ranges = new(StringComparer.Ordinal)
    {
        ["quality_preset"] = (0, 5), ["fullscreen"] = (0, 1), ["gpu_device"] = (0, 8),
        ["frame_generation"] = (0, 8), ["frame_pacing"] = (0, 1), ["frame_rate_cap"] = (0, 5),
        ["hdr"] = (0, 2), ["hdr_paper_white"] = (80, 400), ["hdr_peak_brightness"] = (400, 4000),
        ["nvidia_reflex"] = (0, 2), ["amd_anti-lag_2"] = (0, 1), ["dlss"] = (0, 5), ["dlss_model"] = (0, 3),
        ["resolution"] = (0, 9), ["dynamic_resolution"] = (0, 1), ["upscaling"] = (0, 2), ["sharpness"] = (0, 100),
        ["anisotropic_filtering"] = (0, 4), ["handheld_profile"] = (0, 1), ["ultrawide"] = (0, 1),
        ["ultrawide_menus"] = (0, 2), ["robust_buffers"] = (0, 2), ["volume"] = (0, 100),
        ["mute_in_background"] = (0, 1), ["audio_output"] = (0, 2), ["fps_counter"] = (0, 1),
        ["menu_size"] = (0, 3), ["game_speed"] = (0, 1), ["text_speed"] = (0, 3), ["text_size"] = (0, 4),
        ["microphone"] = (0, 18), ["discord_status"] = (0, 1), ["controller_in_background"] = (0, 1),
        ["mouse_camera"] = (0, 1), ["disable_camera_centering"] = (0, 1), ["mouse_sensitivity"] = (10, 500),
        ["invert_mouse_vertical"] = (0, 1), ["invert_camera_x"] = (0, 1), ["invert_camera_y"] = (0, 1),
        ["stick_dead_zone"] = (0, 5), ["rumble_strength"] = (0, 150), ["motion_controls"] = (0, 1),
        ["motion_sensitivity_x"] = (10, 600), ["motion_sensitivity_y"] = (10, 300),
        ["invert_motion_x"] = (0, 1), ["invert_motion_y"] = (0, 1), ["motion_deadzone"] = (0, 2),
        ["layout_preset"] = (0, 3), ["button_prompts"] = (0, 5), ["menu_shortcut"] = (0, 2),
        ["debug_tools"] = (0, 1), ["descriptor_reuse"] = (0, 1), ["sampler_cache"] = (0, 1),
    };

    static StringComparison Comparison => OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;

    /// A game or backup folder with the links on the way to it resolved, as Saves does (Saves.Real): a builds folder under a
    /// symlinked ~/Games or OneDrive is fine. Only the settings files themselves are refused as links (ReadFile)
    static string Folder(string path, bool mustExist = true)
    {
        var real = Saves.Real(path);
        if (mustExist && !Directory.Exists(real)) throw new SaveFailure($"No game folder at {path}.");
        if (File.Exists(real)) throw new SaveFailure($"{path} is a file, not a folder. Nothing was copied.");
        return real;
    }

    /// emptyOk: the build's own file, which may be empty (nothing to keep, nothing to back up); a Hookshot file must have content
    static byte[]? ReadFile(string path, bool emptyOk = false)
    {
        var info = new FileInfo(path);
        if (info.LinkTarget != null || (info.Exists && info.Attributes.HasFlag(FileAttributes.ReparsePoint)))
            throw new SaveFailure($"{info.Name} is a link: nothing was copied.");
        if (Directory.Exists(path)) throw new SaveFailure($"{info.Name} is a folder, not a settings file.");
        if (!info.Exists) return null;
        if ((info.Length == 0 && !emptyOk) || info.Length > MaxFileSize) throw new SaveFailure($"{info.Name} is empty or too large to be a settings file.");
        return File.ReadAllBytes(path);
    }

    static string Text(byte[] bytes, string name)
    {
        try
        {
            var text = Utf8.GetString(bytes).TrimStart('\uFEFF');
            if (text.Any(c => c == '\0' || (char.IsControl(c) && c is not '\r' and not '\n' and not '\t')))
                throw new SaveFailure($"{name} contains invalid text.");
            return text;
        }
        catch (DecoderFallbackException) { throw new SaveFailure($"{name} is not UTF-8 text."); }
    }

    static bool Integer(string value, int min, int max) =>
        int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var v) && v >= min && v <= max;

    static bool OutputSize(string value)
    {
        if (Integer(value, 0, 5)) return true;   // (the indices saved before output_res held the size itself)
        var sides = value.Split('x', 'X');
        if (sides.Length != 2 || !int.TryParse(sides[0], out var w) || !int.TryParse(sides[1], out var h)) return false;
        if (w == 0 && h == 0) return true;
        w &= ~7;
        h &= ~7;
        return w >= 640 && h >= 360 && (long)w * h <= 5120L * 2880 && (long)w * 4 >= (long)h * 5 && (long)w * 9 <= (long)h * 48;
    }

    /// What a Hookshot game folder brings: its compatible options, in its order (null: no hookshot_options.ini, or nothing in
    /// it Longshot takes), its game language (null: no language.txt), and the keys left out (unknown to Longshot, or a value
    /// outside the launcher's copy of its rows, which Longshot would clamp on load anyway: the build keeps its own value). Refused
    /// (SaveFailure) only for what is not a settings file at all, or a newer options_version than was checked
    sealed record Found(IReadOnlyList<(string Key, string Value)>? Options, string? Language, IReadOnlyList<string> Skipped)
    {
        public IReadOnlyList<string> Files => (Options != null ? new[] { "longshot_options.ini" } : Array.Empty<string>())
                                               .Concat(Language != null ? new[] { "language.txt" } : Array.Empty<string>()).ToArray();
    }

    static Found Load(string folder)
    {
        var skipped = new HashSet<string>(StringComparer.Ordinal);
        List<(string Key, string Value)>? options = null;
        if (ReadFile(Path.Combine(folder, "hookshot_options.ini")) is { } ini)
        {
            var kept = new Dictionary<string, string>(StringComparer.Ordinal);
            var order = new List<string>();
            foreach (var raw in Text(ini, "hookshot_options.ini").Split('\n'))
            {
                var line = raw.Trim();
                if (line.Length == 0 || line[0] is '#' or ';') continue;
                var eq = line.IndexOf('=');
                if (eq <= 0 || !KeyName.IsMatch(line[..eq].Trim())) throw new SaveFailure("hookshot_options.ini has an invalid setting line.");
                var key = line[..eq].Trim();
                var value = line[(eq + 1)..].Trim();
                bool valid;
                if (key == "options_version")
                {
                    // shortcut: schema checked at Hookshot v4, with Longshot's legacy reader; review before accepting a newer format.
                    if (!Integer(value, 0, 4)) throw new SaveFailure("This Hookshot settings version has not been checked for Longshot. Nothing was copied.");
                    valid = true;
                }
                else if (Ranges.TryGetValue(key, out var range)) valid = Integer(value, range.Min, range.Max);
                else if (key == "output_res") valid = OutputSize(value);
                else if (key == "microphone_device") valid = Utf8.GetByteCount(value) <= 60 && !value.Any(char.IsControl);
                else if ((key.StartsWith("key_", StringComparison.Ordinal) && Keys.Contains(key[4..])) ||
                         (key.StartsWith("pad_", StringComparison.Ordinal) && Buttons.Contains(key[4..])))
                {
                    var values = value.Split(',');
                    var pad = key.StartsWith("pad_", StringComparison.Ordinal);
                    valid = values.Length is 1 or 2 && values.All(v => Integer(v.Trim(), pad ? -1 : 0, pad ? 16 : 255));
                }
                else valid = false;
                // (the last line of a key is the one used, as the game reads them all in turn: an earlier line of it is forgotten,
                // so a key is imported with its last value, or listed as skipped when that last value is the one left out)
                if (!valid)
                {
                    skipped.Add(key);   // (unknown, or out of range: listed and left out, as Longshot would clamp or ignore it)
                    if (kept.Remove(key)) order.Remove(key);
                    continue;
                }
                skipped.Remove(key);
                if (!kept.ContainsKey(key)) order.Add(key);
                kept[key] = value;
            }
            if (kept.Keys.Any(k => k != "options_version")) options = order.Select(k => (Key: k, Value: kept[k])).ToList();
        }
        string? language = null;
        if (ReadFile(Path.Combine(folder, "language.txt")) is { } text)
        {
            var code = Text(text, "language.txt").Split('\n').Select(l => l.Trim()).FirstOrDefault(l => l.Length > 0 && !l.StartsWith('#'));
            language = Languages.Normalize(code) ?? throw new SaveFailure("language.txt has no supported game language. Nothing was copied.");
        }
        if (options == null && language == null) throw new SaveFailure("No compatible Hookshot settings in that folder. Choose the Hookshot game folder.");
        return new Found(options, language, skipped.Order(StringComparer.Ordinal).ToArray());
    }

    /// The rows Longshot reads by the options_version of their file: a line of the key in a file older than Since (no
    /// options_version line at all: -1) holds the old default, whether chosen or not, and is moved on load. game_speed: realtime=1
    /// without the line (gpu/vk/vk_menu.cpp menu_init's !v2); key_y and key_zl: the mouse's buttons added (host/nn_hid.c
    /// binds_load); descriptor_reuse, menu_shortcut, ultrawide: menu_init's version < 4, 5, 6 (and vk_draw.cpp menu_env_on,
    /// host/hos_wide_size.h hos_aspect_on). Checked against Longshot's options_version 6
    static readonly (string Key, int Since)[] Migrated =
    {
        ("game_speed", 0), ("key_y", 3), ("key_zl", 3), ("descriptor_reuse", 4), ("menu_shortcut", 5), ("ultrawide", 6),
    };

    /// A settings line's key (null: a blank line, a comment or a line without one) and value
    static (string? Key, string Value) Line(string line)
    {
        line = line.Trim();
        if (line.Length == 0 || line[0] is '#' or ';') return (null, "");
        var eq = line.IndexOf('=');
        return eq > 0 ? (line[..eq].Trim(), line[(eq + 1)..].Trim()) : (null, "");
    }

    /// An options_version as Longshot reads it (atoi: 0 when it is not a number)
    static int OptionsVersion(string value) => int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var v) ? v : 0;

    /// The build's own longshot_options.ini with the imported keys in it: the file's lines kept, in their order (Longshot's
    /// own settings, such as make_game.py's compile_shaders, vsync, the budgets, auto_*, note_* bindings, and any key it does not
    /// know), each imported key's value put in place of the old one, and the imported keys the file does not have yet added at
    /// the end, as make_game.py's write_compile_level and the menu's own save keep the lines they do not write.
    /// The merged file is read under Hookshot's options_version, so that Longshot migrates the imported rows as it would
    /// Hookshot's own file: the imported marker replaces the build's, and without one the build's options_version lines are
    /// removed (a file from before the marker). Every line kept means the same under that version: a line of the build's own
    /// (not imported) whose key Longshot migrates (Migrated) between the build's version and the imported one is removed, so
    /// that the row takes Longshot's current default rather than being moved again (an options_version 6 menu_shortcut=0,
    /// Insert or F1, read under 4 would become Insert, F1 or Esc). The other kept lines are of keys no migration reads
    internal static string Merge(string? existing, IReadOnlyList<(string Key, string Value)> imported)
    {
        var values = imported.ToDictionary(kv => kv.Key, kv => kv.Value, StringComparer.Ordinal);
        var eol = existing?.Contains("\r\n") == true ? "\r\n" : "\n";
        var lines = (existing ?? "").Split('\n').Select(l => l.TrimEnd('\r')).ToList();
        if (lines.Count > 0 && lines[^1].Length == 0) lines.RemoveAt(lines.Count - 1);   // (the last line's end)
        var had = -1;   // (the build's options_version: its last line's, as Longshot reads it; -1 without one)
        foreach (var line in lines)
            if (Line(line) is ("options_version", var v)) had = OptionsVersion(v);
        var now = values.TryGetValue("options_version", out var marker) ? OptionsVersion(marker) : -1;
        var drop = new HashSet<string>(Migrated.Where(m => !values.ContainsKey(m.Key) && (had < m.Since) != (now < m.Since)).Select(m => m.Key),
                                       StringComparer.Ordinal);
        if (now < 0) drop.Add("options_version");
        var merged = new List<string>();
        var replaced = new HashSet<string>(StringComparer.Ordinal);
        foreach (var line in lines)
        {
            var key = Line(line).Key;
            if (key == null)
            {
                merged.Add(line);
                continue;
            }
            if (drop.Contains(key)) continue;
            if (values.TryGetValue(key, out var value))
            {
                merged.Add(key + "=" + value);
                replaced.Add(key);
            }
            else merged.Add(line);
        }
        foreach (var (key, value) in imported)
            if (!replaced.Contains(key)) merged.Add(key + "=" + value);
        return string.Join(eol, merged) + eol;
    }

    public static IReadOnlyList<string> FilesIn(string gameFolder) => Load(Folder(gameFolder)).Files;

    /// A preview writes nothing. A real import backs up the existing files, then writes Hookshot's settings into them: the
    /// imported keys into the build's longshot_options.ini, its other lines kept (Merge), and language.txt replaced.
    public static HookshotSettingsCopy Import(string sourceGameFolder, string targetGameFolder, string backupRoot, bool overwrite,
                                             bool dryRun = false, Func<IReadOnlyList<string>>? running = null, Func<DateTime>? now = null)
    {
        var source = Folder(sourceGameFolder);
        var target = Folder(targetGameFolder);
        if (source.Equals(target, Comparison)) throw new SaveFailure("The Hookshot and Longshot game folders must differ.");
        var found = Load(source);
        var previous = TargetFiles.Select(n => (Name: n, Bytes: ReadFile(Path.Combine(target, n), emptyOk: true)))
                                  .Where(f => f.Bytes != null).ToDictionary(f => f.Name, f => f.Bytes!, StringComparer.Ordinal);
        var files = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        if (found.Options != null)
        {
            var existing = previous.TryGetValue("longshot_options.ini", out var old) ? Text(old, "longshot_options.ini") : null;
            files.Add("longshot_options.ini", Utf8.GetBytes(Merge(existing, found.Options)));
        }
        if (found.Language != null) files.Add("language.txt", Utf8.GetBytes(found.Language + "\n"));
        // (an empty file has no settings to replace: imported into without asking, and restored as it was if a write fails)
        var replacing = files.Keys.Any(n => previous.TryGetValue(n, out var bytes) && bytes.Length > 0);
        if (!dryRun && replacing && !overwrite) throw new SaveFailure("Longshot already has settings there. Back them up and replace them, or keep them.", SaveRefusal.Exists);
        if (!dryRun && (running ?? (() => Saves.Running(Platforms.Current)))() is { Count: > 0 } busy)
            throw new SaveFailure($"Close {string.Join(" and ", busy)} before importing settings.", SaveRefusal.Running, busy);
        var stamp = (now ?? (() => DateTime.Now))().ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture);
        backupRoot = Folder(backupRoot, mustExist: false);
        var backup = Path.Combine(backupRoot, "hookshot-settings-" + stamp);
        for (var n = 2; Directory.Exists(backup) || File.Exists(backup); n++) backup = Path.Combine(backupRoot, $"hookshot-settings-{stamp}-{n}");
        if (Saves.Inside(source, backup) || Saves.Inside(target, backup)) throw new SaveFailure("Choose a backup folder outside both game folders.");
        var result = new HookshotSettingsCopy(source, target, files.Keys.ToArray(), replacing ? backup : null, found.Skipped, found.Language);
        if (dryRun) return result;
        if (replacing)
        {
            try
            {
                foreach (var (name, bytes) in previous) AtomicFile.Write(Path.Combine(backup, name), bytes);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                throw new SaveFailure($"The settings could not be backed up ({e.Message}). Nothing was copied.");
            }
        }
        try
        {
            foreach (var (name, bytes) in files)
            {
                Fault?.Invoke(name);
                AtomicFile.Write(Path.Combine(target, name), bytes);
            }
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            var restored = true;
            foreach (var name in files.Keys)
                try
                {
                    if (previous.TryGetValue(name, out var bytes)) AtomicFile.Write(Path.Combine(target, name), bytes);
                    else File.Delete(Path.Combine(target, name));
                }
                catch (Exception restore) when (restore is IOException or UnauthorizedAccessException) { restored = false; }
            var recovery = result.Backup != null ? "Restore them from the backup."
                : $"New, incomplete settings may remain in {target}. Remove those imported files before retrying.";
            throw new SaveFailure(restored ? $"The settings could not be imported ({e.Message}). Longshot's settings are as they were."
                                          : $"The settings could not be imported or fully restored ({e.Message}). {recovery}", backup: result.Backup);
        }
        return result;
    }

    internal static Action<string>? Fault { get; set; }
}
