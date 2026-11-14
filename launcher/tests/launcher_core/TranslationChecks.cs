using HookshotLauncher.Core;

/// Core/Tr.cs: the launcher's languages, the system's language as it names it, the catalogs' fallbacks and plural forms, and the
/// catalogs embedded (scripts/translations.py checks their texts against the sources)
static partial class Program
{
    static void TranslationChecks()
    {
        Require(Tr.All.Select(l => l.Code).SequenceEqual(Languages.All.Select(l => l.Code)),
                "The launcher speaks the game's languages (Tr.All has Languages.All's codes, in its order).");

        foreach (var (name, want) in new (string?, string?)[]
                 {
                     ("de", "de"), ("de-DE", "de"), ("de_AT.UTF-8", "de"), ("en_US.UTF-8", "en-US"), ("en", "en-US"), ("en-AU", "en-GB"),
                     ("en_GB", "en-GB"), ("fr_FR.UTF-8", "fr"), ("fr-CA", "fr-CA"), ("fr_CA.UTF-8@euro", "fr-CA"), ("es-ES", "es"),
                     ("es", "es"), ("es-MX", "es-419"), ("es_AR", "es-419"), ("es-419", "es-419"), ("pt-PT", "pt-BR"), ("pt_BR", "pt-BR"),
                     ("zh-CN", "zh-Hans"), ("zh_SG", "zh-Hans"), ("zh-TW", "zh-Hant"), ("zh-HK", "zh-Hant"), ("zh-Hant-TW", "zh-Hant"),
                     ("zh-hans", "zh-Hans"), ("ja_JP.UTF-8", "ja"), ("ko-KR", "ko"), ("ru_RU", "ru"), ("pl", "pl"), ("nl_BE", "nl"),
                     ("it_CH", "it"), ("C", null), ("POSIX", null), ("C.UTF-8", null), ("sv-SE", null), ("", null), (null, null),
                 })
            Require(Tr.Pick(name) == want, $"The system's {name ?? "null"} is the launcher's {want ?? "none"}.");

        string? Env(Dictionary<string, string> vars) => Tr.FromEnvironment(n => vars.GetValueOrDefault(n));
        Require(Env(new() { ["LANG"] = "de_DE.UTF-8" }) == "de", "LANG names the system's language.");
        Require(Env(new() { ["LANG"] = "de_DE.UTF-8", ["LC_MESSAGES"] = "ja_JP.UTF-8" }) == "ja", "LC_MESSAGES comes before LANG.");
        Require(Env(new() { ["LANG"] = "de_DE.UTF-8", ["LC_ALL"] = "fr_CA.UTF-8" }) == "fr-CA", "LC_ALL comes before both.");
        Require(Env(new() { ["LANGUAGE"] = "sv:nl:de", ["LANG"] = "de_DE.UTF-8" }) == "nl", "LANGUAGE's list: its first spoken language.");
        Require(Env(new() { ["LANG"] = "C.UTF-8" }) == null && Env(new()) == null, "C, or no locale: none (English).");

        var settings = new LauncherSettings();
        Require(settings.UiLanguageOr("pl_PL") == "pl" && settings.UiLanguageOr(null) == Tr.English && settings.UiLanguageOr("sv") == Tr.English,
                "No language picked: the system's when the launcher speaks it, else English.");
        settings.UiLanguage = "ja";
        Require(settings.UiLanguageOr("pl_PL") == "ja", "A picked language comes before the system's.");
        var path = Path.Combine(Folder("tr"), "settings.json");
        settings.UiLanguage = "klingon";
        settings.Save(path);
        Require(LauncherSettings.Load(path).UiLanguage == null, "A saved language the launcher does not speak is read as none picked.");
        settings.UiLanguage = "zh-TW";
        settings.Save(path);
        Require(LauncherSettings.Load(path).UiLanguage == "zh-Hant", "A saved language is kept as Tr.All's code.");

        Require(Tr.ChainOf("fr-CA").SequenceEqual(new[] { "fr-CA", "fr" }) && Tr.ChainOf("es-419").SequenceEqual(new[] { "es-419", "es" })
                && Tr.ChainOf("en-GB").SequenceEqual(new[] { "en-GB" }) && Tr.ChainOf(Tr.English).Count == 0 && Tr.ChainOf("de").SequenceEqual(new[] { "de" }),
                "A regional catalog falls back to its language's, then to the English.");

        foreach (var (code, n, want) in new (string, long, string)[]
                 {
                     ("en-US", 1, "one"), ("en-US", 0, "other"), ("en-US", 2, "other"), ("de", 1, "one"), ("nl", 21, "other"),
                     ("fr", 0, "one"), ("fr", 1, "one"), ("fr", 2, "other"), ("fr-CA", 1_000_000, "many"), ("pt-BR", 0, "one"), ("pt-BR", 2, "other"),
                     ("es", 1, "one"), ("es-419", 0, "other"), ("it", 1, "one"), ("it", 3, "other"),
                     ("ru", 1, "one"), ("ru", 2, "few"), ("ru", 4, "few"), ("ru", 5, "many"), ("ru", 11, "many"), ("ru", 12, "many"),
                     ("ru", 21, "one"), ("ru", 22, "few"), ("ru", 25, "many"), ("ru", 111, "many"), ("ru", 0, "many"),
                     ("pl", 1, "one"), ("pl", 2, "few"), ("pl", 5, "many"), ("pl", 12, "many"), ("pl", 21, "many"), ("pl", 22, "few"), ("pl", 0, "many"),
                     ("ja", 1, "other"), ("ko", 2, "other"), ("zh-Hans", 1, "other"), ("zh-Hant", 5, "other"),
                 })
        {
            Require(Tr.PluralOf(code, n) == want, $"{n} in {code} takes the {want} form.");
            Require(Tr.PluralCategories(code).Contains(want), $"{code}'s catalogs give the {want} form.");
        }

        var catalog = Tr.Parse("""
            { "@note": "not a text", "Hello": "Hallo", "{0} of {1}": "{1} von {0}", "Broken {0}": "Kaputt {0} {",
              "{0} files": { "one": "eine Datei", "other": "{0} Dateien" } }
            """);
        Require(catalog.Texts.Count == 3 && !catalog.Texts.ContainsKey("@note") && catalog.Plurals["{0} files"]["one"] == "eine Datei",
                "A catalog: texts, a count's forms, and notes left out.");

        // (the catalogs themselves, as embedded: each of Tr.All's languages but English has one, and each parses)
        var embedded = Tr.Embedded().ToHashSet();
        foreach (var (code, _) in Tr.All.Where(l => l.Code != Tr.English))
            Require(embedded.Contains(code) && Tr.Load(code) is { } c && (c.Texts.Count > 0 || c.Plurals.Count > 0),
                    $"Core/Lang/{code}.json is embedded, and reads.");

        Require(Tr.Sentences("One.", "Two.") == "One. Two." && Tr.Sentences("一。", "二。") == "一。二。" && Tr.Sentences("", "Two.", "") == "Two.",
                "Sentences: a space between them, none after a full-width stop.");

        Tr.Use("de");
        Require(Tr.Current == "de" && Tr.T("Cancel") != "Cancel" && Tr.T("No such text, so it stays") == "No such text, so it stays",
                "A text in German; one with no translation in English.");
        Require(Tr.F("Slot {0}", 3).Contains('3') && Tr.P(1, "1 slot", "{0} slots") != Tr.P(2, "1 slot", "{0} slots"),
                "A text's parts filled in; a count's form follows the count.");
        Tr.Use("fr-CA");
        Require(Tr.Current == "fr-CA" && Tr.T("Cancel") == (Tr.Load("fr-CA")!.Texts.GetValueOrDefault("Cancel") ?? Tr.Load("fr")!.Texts["Cancel"]),
                "Canadian French reads its own catalog, then French's.");
        Tr.Use("klingon");
        Require(Tr.Current == Tr.English && Tr.T("Cancel") == "Cancel" && Tr.P(1, "1 slot", "{0} slots") == "1 slot"
                && Tr.P(2, "1 slot", "{0} slots") == "2 slots", "An unknown language is English.");
        Tr.Use(null);
    }
}
