namespace LongshotLauncher.Core;

/// A save folder summed up as the window writes it: "3 slots, saved yesterday 22:14" (Long) or "3 saves, last yesterday 22:14"
public static class SaveText
{
    public static DateTime? Last(IReadOnlyList<SaveSlot> slots) => slots.Select(s => s.Saved).Where(t => t != null).Max();

    public static string Long(IReadOnlyList<SaveSlot> slots, DateTime now)
    {
        if (slots.Count == 0) return Tr.T("No saves yet");
        return Last(slots) is { } t ? Tr.P(slots.Count, "1 slot, saved {1}", "{0} slots, saved {1}", Durations.When(t, now))
            : Tr.P(slots.Count, "1 slot", "{0} slots");
    }

    public static string Short(IReadOnlyList<SaveSlot> slots, DateTime now)
    {
        if (slots.Count == 0) return Tr.T("No saves yet");
        return Last(slots) is { } t ? Tr.P(slots.Count, "1 save, last {1}", "{0} saves, last {1}", Durations.When(t, now))
            : Tr.P(slots.Count, "1 save", "{0} saves");
    }

    /// "3 save slots", "1 save slot", "no saves" (a row of the home's list)
    public static string Count(int slots) => slots == 0 ? Tr.T("no saves") : Tr.P(slots, "1 save slot", "{0} save slots");

    /// What the home says once Saves.Gather brought the builds' own saves together: which one every version plays now, and where
    /// the backup of them all is
    public static string Gathered(SaveGathered g)
    {
        return g.WasShared
            ? Tr.F("Every Longshot version now uses the same saves: the shared ones, which were the newest. All of them are backed up in {0}.", g.Backup)
            : Tr.F("Every Longshot version now uses the same saves: the newest, from {0}. All of them are backed up in {1}.",
                   System.IO.Path.GetDirectoryName(g.From), g.Backup);
    }

    /// A slot's number from its folder's name: slot_00 is 1
    public static int Number(string slotName) =>
        slotName.StartsWith("slot_", StringComparison.Ordinal) && int.TryParse(slotName[5..], System.Globalization.NumberStyles.None,
            System.Globalization.CultureInfo.InvariantCulture, out var n) ? n + 1 : 0;
}
