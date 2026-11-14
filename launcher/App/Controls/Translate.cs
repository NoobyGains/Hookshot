using System.ComponentModel;
using Avalonia.Data;
using LongshotLauncher.Core;

namespace LongshotLauncher.Controls;

/// A text of the window's in the player's language: Text="{c:T 'Release notes'}", the English as in Lang/&lt;code&gt;.json. It
/// follows a change of language at once
public sealed class TExtension(string text)
{
    public string Text => text;

    public object ProvideValue(IServiceProvider services) =>
        new ReflectionBinding(nameof(TranslatedText.Value)) { Source = TranslatedText.Of(text), Mode = BindingMode.OneWay };
}

/// The system's language as it names it: Windows' display language (de-DE; the first of the user's preferred UI languages
/// the launcher has), elsewhere the locale variables'; null: none known
public static class SystemLanguage
{
    const uint MuiLanguageName = 0x8;

    [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    [return: System.Runtime.InteropServices.MarshalAs(System.Runtime.InteropServices.UnmanagedType.Bool)]
    static extern bool GetUserPreferredUILanguages(uint flags, out uint count, [System.Runtime.InteropServices.Out] char[]? names,
        ref uint size);

    public static string? Name()
    {
        if (!OperatingSystem.IsWindows()) return Tr.FromEnvironment(Environment.GetEnvironmentVariable);
        try
        {
            uint size = 0;
            if (!GetUserPreferredUILanguages(MuiLanguageName, out _, null, ref size) || size == 0) return null;
            var names = new char[size];
            if (!GetUserPreferredUILanguages(MuiLanguageName, out _, names, ref size)) return null;
            // A list of names, each ended by a NUL, the list by another: de-DE\0en-US\0\0
            var list = new string(names, 0, (int)Math.Min(size, (uint)names.Length));
            foreach (var each in list.Split('\0', StringSplitOptions.RemoveEmptyEntries))
                if (Tr.Pick(each) is { } listed) return listed;
            return null;
        }
        catch (Exception e) when (e is DllNotFoundException or EntryPointNotFoundException) { return null; }
    }
}

/// One English text and its translation, which the bindings of every view showing it share
public sealed class TranslatedText : INotifyPropertyChanged
{
    static readonly Dictionary<string, TranslatedText> all = new(StringComparer.Ordinal);
    static readonly PropertyChangedEventArgs valueChanged = new(nameof(Value));

    static TranslatedText() => Tr.Changed += () => ViewModels.Ui.Post(() =>
    {
        foreach (var t in all.Values) t.PropertyChanged?.Invoke(t, valueChanged);
    });

    readonly string english;

    TranslatedText(string english) => this.english = english;

    public static TranslatedText Of(string english)
    {
        if (!all.TryGetValue(english, out var t)) all[english] = t = new TranslatedText(english);
        return t;
    }

    public string Value => Tr.T(english);

    public event PropertyChangedEventHandler? PropertyChanged;
}
