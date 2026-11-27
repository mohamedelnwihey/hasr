using System.Text.Json;
using System.Text.Json.Serialization;

namespace Moqayasa.Core;

/// <summary>version.json in the hasr repo: {"version":"0.5.4","changelog_ar":"...","changelog_en":"...","download":"https://..."}</summary>
public sealed class UpdateInfo
{
    [JsonPropertyName("version")] public string Version { get; set; } = "";
    [JsonPropertyName("changelog_ar")] public string ChangelogAr { get; set; } = "";
    [JsonPropertyName("changelog_en")] public string ChangelogEn { get; set; } = "";
    [JsonPropertyName("download")] public string Download { get; set; } = "";
}

public static class Update
{
    public const string Current = "0.5.4";
    public const string VersionUrl = "https://raw.githubusercontent.com/mohamedelnwihey/hasr/main/version.json";

    public static UpdateInfo? Parse(string? json)
    {
        try { return string.IsNullOrWhiteSpace(json) ? null : JsonSerializer.Deserialize<UpdateInfo>(json); } catch { return null; }
    }

    public static Version? V(string? s) => System.Version.TryParse((s ?? "").Trim().TrimStart('v', 'V'), out var v) ? v : null;

    /// <summary>True only for a well-formed newer version that the user has not skipped and that has an https download link.</summary>
    public static bool ShouldOffer(UpdateInfo? info, string current, string? skipped)
    {
        if (info is null) return false;
        var n = V(info.Version); var c = V(current);
        if (n is null || c is null || n <= c) return false;
        if (!string.IsNullOrEmpty(skipped) && V(skipped) is Version sk && n <= sk) return false;
        return info.Download.StartsWith("https://", StringComparison.OrdinalIgnoreCase);
    }
}
