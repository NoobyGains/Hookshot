using System.Globalization;
using System.Text;
using System.Text.Json;

namespace LongshotLauncher.Core;

/// The launcher's own words in the player's language: each text is looked up by its English (Lang/&lt;code&gt;.json, embedded), a
/// regional catalog falling back to its language's (fr-CA to fr), and anything missing to the English. Separate from the
/// game's language (Languages, make_game.py's --language), though the codes are the same.
public static class Tr
{
    /// The languages the launcher speaks, each named in itself; the game's languages (Languages.All), so the two lists match
    public static readonly IReadOnlyList<(string Code, string Name)> All = new[]
    {
        ("en-US", "English (US)"), ("en-GB", "English (UK)"), ("fr", "Français (France)"), ("fr-CA", "Français (Canada)"),
        ("de", "Deutsch"), ("it", "Italiano"), ("es", "Español (España)"), ("es-419", "Español (Latinoamérica)"),
        ("pt-BR", "Português (Brasil)"), ("nl", "Nederlands"), ("pl", "Polski"), ("ru", "Русский"), ("ja", "日本語"),
        ("ko", "한국어"), ("zh-Hans", "简体中文"), ("zh-Hant", "繁體中文"),
    };

    public const string English = "en-US";

    /// A catalog's texts: a translation, or for a count its forms by CLDR plural category ("one", "few", "many", "other")
    public sealed class Catalog
    {
        public readonly Dictionary<string, string> Texts = new(StringComparer.Ordinal);
        public readonly Dictionary<string, Dictionary<string, string>> Plurals = new(StringComparer.Ordinal);
    }

    static readonly Dictionary<string, Catalog?> loaded = new(StringComparer.Ordinal);
    static readonly object gate = new();
    static string current = English;
    static Catalog?[] chain = Array.Empty<Catalog?>();

    /// The language in use (one of All's codes)
    public static string Current => current;

    /// After a change of language: the window's texts are asked for again
    public static event Action? Changed;

    /// Use a language: one of All's codes, or what Pick makes of another; unknown, English
    public static void Use(string? code)
    {
        var picked = Pick(code) ?? English;
        lock (gate)
        {
            current = picked;
            chain = ChainOf(picked).Select(Load).ToArray();
        }
        Changed?.Invoke();
    }

    /// The code in All for a language as saved, or as the system names it (de-DE, pt_BR.UTF-8, zh-TW, es-MX); null when the launcher
    /// does not speak it
    public static string? Pick(string? name)
    {
        if (string.IsNullOrWhiteSpace(name)) return null;
        var n = name.Trim().Split('.', '@')[0].Replace('_', '-');
        if (n is "C" or "POSIX") return null;
        foreach (var (c, _) in All)
            if (string.Equals(c, n, StringComparison.OrdinalIgnoreCase)) return c;
        var parts = n.Split('-');
        var language = parts[0].ToLowerInvariant();
        var rest = parts.Skip(1).Select(p => p.ToUpperInvariant()).ToArray();
        string? region = rest.FirstOrDefault(p => p.Length == 2 || p.Length == 3 && p.All(char.IsAsciiDigit));
        return language switch
        {
            "en" => region is null or "US" ? "en-US" : "en-GB",
            "fr" => region == "CA" ? "fr-CA" : "fr",
            "es" => region is null or "ES" ? "es" : "es-419",
            "pt" => "pt-BR",
            "zh" => rest.Contains("HANT") || region is "TW" or "HK" or "MO" ? "zh-Hant" : "zh-Hans",
            _ => All.Any(l => l.Code == language) ? language : null,
        };
    }

    /// The system's language from its locale variables (LC_ALL, LC_MESSAGES, LANG; LANGUAGE's list first), in All; null: none spoken
    public static string? FromEnvironment(Func<string, string?> getenv)
    {
        foreach (var each in (getenv("LANGUAGE") ?? "").Split(':', StringSplitOptions.RemoveEmptyEntries))
            if (Pick(each) is { } listed) return listed;
        foreach (var name in new[] { "LC_ALL", "LC_MESSAGES", "LANG" })
            if (getenv(name) is { Length: > 0 } value) return Pick(value);
        return null;
    }

    /// The catalogs a language reads, most particular first (fr-CA, then fr); English has none
    public static IReadOnlyList<string> ChainOf(string code) => code switch
    {
        English => Array.Empty<string>(),
        "en-GB" => new[] { "en-GB" },
        "fr-CA" => new[] { "fr-CA", "fr" },
        "es-419" => new[] { "es-419", "es" },
        _ => new[] { code },
    };

    /// Sentences one after the other: a space between them, but none after a full stop that needs none (。！？)
    public static string Sentences(params string[] each)
    {
        var all = new StringBuilder();
        foreach (var one in each)
        {
            if (one.Length == 0) continue;
            if (all.Length > 0 && !"。！？".Contains(all[^1])) all.Append(' ');
            all.Append(one);
        }
        return all.ToString();
    }

    /// A text kept in English where it is (a log line, a key), and translated where it is shown (T): marks it for the catalogs
    public static string N(string english) => english;

    /// The text in the language in use
    public static string T(string english)
    {
        foreach (var c in chain)
            if (c != null && c.Texts.TryGetValue(english, out var t)) return t;
        return english;
    }

    /// A text with its parts ({0}, {1}...) filled in, in the language in use; a translation whose parts do not fit, the English
    public static string F(string english, params object?[] args)
    {
        var text = T(english);
        try { return string.Format(CultureInfo.InvariantCulture, text, args); }
        catch (FormatException) { return string.Format(CultureInfo.InvariantCulture, english, args); }
    }

    /// A count's text: English's one or other ({0} the count), the language in use's form for it; other args are {1}...
    public static string P(long count, string one, string other, params object?[] args)
    {
        var all = new object?[args.Length + 1];
        all[0] = count;
        args.CopyTo(all, 1);
        var category = PluralOf(current, count);
        foreach (var c in chain)
            if (c != null && c.Plurals.TryGetValue(other, out var forms))
            {
                var text = forms.GetValueOrDefault(category) ?? forms.GetValueOrDefault("other");
                if (text == null) break;
                try { return string.Format(CultureInfo.InvariantCulture, text, all); }
                catch (FormatException) { break; }
            }
        return string.Format(CultureInfo.InvariantCulture, count == 1 ? one : other, all);
    }

    /// CLDR's plural category of a whole number in a language: the forms a catalog gives a count
    public static string PluralOf(string code, long n)
    {
        var language = code.Split('-')[0];
        var abs = Math.Abs(n);
        long mod10 = abs % 10, mod100 = abs % 100;
        return language switch
        {
            "ja" or "ko" or "zh" => "other",
            "fr" or "pt" => abs is 0 or 1 ? "one" : abs != 0 && abs % 1_000_000 == 0 ? "many" : "other",
            "ru" => mod10 == 1 && mod100 != 11 ? "one" : mod10 is >= 2 and <= 4 && mod100 is < 12 or > 14 ? "few" : "many",
            "pl" => abs == 1 ? "one" : mod10 is >= 2 and <= 4 && mod100 is < 12 or > 14 ? "few" : "many",
            "es" or "it" => abs == 1 ? "one" : abs != 0 && abs % 1_000_000 == 0 ? "many" : "other",
            _ => abs == 1 ? "one" : "other",
        };
    }

    /// The categories a language's counts take: what each of its catalog's plural entries must give
    public static IReadOnlyList<string> PluralCategories(string code) => code.Split('-')[0] switch
    {
        "ja" or "ko" or "zh" => new[] { "other" },
        "ru" or "pl" => new[] { "one", "few", "many", "other" },
        "fr" or "pt" or "es" or "it" => new[] { "one", "many", "other" },
        _ => new[] { "one", "other" },
    };

    /// A catalog from its JSON: an object of English to text, a count's entry an object of category to text
    public static Catalog Parse(string json)
    {
        var catalog = new Catalog();
        using var doc = JsonDocument.Parse(json, new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true });
        foreach (var p in doc.RootElement.EnumerateObject())
        {
            if (p.Name.StartsWith('@')) continue;
            if (p.Value.ValueKind == JsonValueKind.String) catalog.Texts[p.Name] = p.Value.GetString()!;
            else if (p.Value.ValueKind == JsonValueKind.Object)
                catalog.Plurals[p.Name] = p.Value.EnumerateObject().Where(f => f.Value.ValueKind == JsonValueKind.String)
                    .ToDictionary(f => f.Name, f => f.Value.GetString()!, StringComparer.Ordinal);
        }
        return catalog;
    }

    /// A language's own catalog, as embedded (Lang/&lt;code&gt;.json); null when there is none or it cannot be read
    public static Catalog? Load(string code)
    {
        lock (gate)
        {
            if (loaded.TryGetValue(code, out var known)) return known;
            Catalog? catalog = null;
            try
            {
                using var stream = typeof(Tr).Assembly.GetManifestResourceStream("Lang." + code + ".json");
                if (stream != null)
                {
                    using var reader = new StreamReader(stream);
                    catalog = Parse(reader.ReadToEnd());
                }
            }
            catch (Exception e) when (e is JsonException or IOException) { }
            loaded[code] = catalog;
            return catalog;
        }
    }

    /// The catalogs embedded, by code
    public static IEnumerable<string> Embedded() =>
        typeof(Tr).Assembly.GetManifestResourceNames().Where(n => n.StartsWith("Lang.", StringComparison.Ordinal) && n.EndsWith(".json", StringComparison.Ordinal))
            .Select(n => n["Lang.".Length..^".json".Length]);
}
