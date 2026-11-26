using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Moqayasa.Core;

/// <summary>
/// One priced item and where its price comes from. Nothing here ships a price:
/// a source only becomes "verified" after a person has opened the page and confirmed the rule reads the right number.
/// </summary>
public sealed class PriceSource
{
    [JsonPropertyName("item")] public string Item { get; set; } = "";            // matches BoqLine.ItemEn (or a purchase component)
    [JsonPropertyName("vendor")] public string Vendor { get; set; } = "";
    [JsonPropertyName("url")] public string Url { get; set; } = "";
    [JsonPropertyName("regex")] public string Regex { get; set; } = "";           // group 1 = the number as printed on the page
    [JsonPropertyName("unit_factor")] public double UnitFactor { get; set; } = 1; // page price x factor = price per BOQ unit
    [JsonPropertyName("currency")] public string Currency { get; set; } = "EGP";
    [JsonPropertyName("refresh")] public string Refresh { get; set; } = "weekly"; // daily | weekly | monthly | manual
    [JsonPropertyName("verified")] public bool Verified { get; set; }
    [JsonPropertyName("last_price")] public double? LastPrice { get; set; }
    [JsonPropertyName("last_updated")] public string? LastUpdated { get; set; }   // yyyy-MM-dd
    [JsonPropertyName("note")] public string Note { get; set; } = "";
}

public sealed class PriceFeedConfig
{
    [JsonPropertyName("sources")] public List<PriceSource> Sources { get; set; } = new();
    static readonly JsonSerializerOptions Opt = new() { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };
    public static PriceFeedConfig Load(string path) => File.Exists(path) ? JsonSerializer.Deserialize<PriceFeedConfig>(File.ReadAllText(path)) ?? new() : new();
    public void Save(string path) => File.WriteAllText(path, JsonSerializer.Serialize(this, Opt));
}

public static class PriceFeed
{
    public static int Days(string refresh) => refresh switch { "daily" => 1, "weekly" => 7, "monthly" => 30, _ => int.MaxValue };

    public static bool Due(PriceSource s, DateTime today)
    {
        if (!s.Verified || string.IsNullOrEmpty(s.Url) || s.Refresh == "manual") return false;
        if (!DateTime.TryParseExact(s.LastUpdated, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var d)) return true;
        return (today.Date - d.Date).TotalDays >= Days(s.Refresh);
    }

    /// <summary>Pure extraction: reads the first number captured by the rule. Arabic-Indic digits and thousands separators handled.</summary>
    public static double? Extract(string html, PriceSource s)
    {
        if (string.IsNullOrEmpty(s.Regex)) return null;
        var m = System.Text.RegularExpressions.Regex.Match(html, s.Regex, RegexOptions.Singleline);
        if (!m.Success || m.Groups.Count < 2) return null;
        var t = new string(m.Groups[1].Value.Select(c => c >= '٠' && c <= '٩' ? (char)('0' + (c - '٠')) : c).ToArray()).Replace(",", "").Replace("٬", "").Trim();
        return double.TryParse(t, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v * s.UnitFactor : null;
    }

    /// <summary>Refresh the due, verified sources. fetch is injectable so tests never touch the network. Failures keep the old price.</summary>
    public static List<string> Refresh(PriceFeedConfig cfg, DateTime today, Func<string, string?> fetch)
    {
        var log = new List<string>(); var cache = new Dictionary<string, string?>();
        foreach (var s in cfg.Sources.Where(x => Due(x, today)))
        {
            string? html;
            try { if (!cache.TryGetValue(s.Url, out html)) { html = fetch(s.Url); cache[s.Url] = html; } } catch (Exception ex) { log.Add($"{s.Item}: fetch failed ({ex.Message}), kept old price"); continue; }
            var v = html is null ? null : Extract(html, s);
            if (v is null || v <= 0) { log.Add($"{s.Item}: rule did not match, kept old price"); continue; }
            s.LastPrice = Math.Round(v.Value, 2); s.LastUpdated = today.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            log.Add($"{s.Item}: {s.LastPrice} {s.Currency} from {s.Vendor}");
        }
        return log;
    }

    /// <summary>Feed prices fill only items the user has not priced by hand. Hand prices (prices.csv) always win.</summary>
    public static Dictionary<string, double> Merge(Dictionary<string, double> manual, PriceFeedConfig cfg)
    {
        var d = new Dictionary<string, double>(manual, StringComparer.OrdinalIgnoreCase);
        foreach (var s in cfg.Sources.Where(x => x.Verified && x.LastPrice is > 0 && !d.ContainsKey(x.Item))) d[s.Item] = s.LastPrice!.Value;
        return d;
    }
}
