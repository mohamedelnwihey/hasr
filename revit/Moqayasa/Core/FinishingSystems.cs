using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Moqayasa.Core;

public sealed class Component
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("ar")] public string Ar { get; set; } = "";
    [JsonPropertyName("en")] public string En { get; set; } = "";
    [JsonPropertyName("kind")] public string Kind { get; set; } = "per_m2";
    [JsonPropertyName("rate")] public double? Rate { get; set; }
    [JsonPropertyName("piece_area")] public double? PieceArea { get; set; }
    [JsonPropertyName("unit")] public string Unit { get; set; } = "";
    [JsonPropertyName("waste")] public double Waste { get; set; }
    [JsonPropertyName("pack_size")] public double? PackSize { get; set; }
    [JsonPropertyName("pack_ar")] public string PackAr { get; set; } = "";
    [JsonPropertyName("pack_en")] public string PackEn { get; set; } = "";
    [JsonPropertyName("source")] public string Source { get; set; } = "";
    [JsonPropertyName("approved")] public bool Approved { get; set; }
    [JsonPropertyName("tags")] public List<string> Tags { get; set; } = new();
    [JsonPropertyName("included_keywords")] public List<string> IncludedKeywords { get; set; } = new();
}

public sealed class FinishSystem
{
    [JsonPropertyName("ar")] public string Ar { get; set; } = "";
    [JsonPropertyName("en")] public string En { get; set; } = "";
    [JsonPropertyName("boq_keywords")] public List<string> BoqKeywords { get; set; } = new();
    [JsonPropertyName("components")] public List<Component> Components { get; set; } = new();
}

public sealed class Rule
{
    [JsonPropertyName("scope")] public string Scope { get; set; } = "";
    [JsonPropertyName("room_match")] public string? RoomMatch { get; set; }
    [JsonPropertyName("exclude")] public string? Exclude { get; set; }
    [JsonPropertyName("system")] public string? System { get; set; }
}

public sealed class Required
{
    [JsonPropertyName("room_match")] public string RoomMatch { get; set; } = "";
    [JsonPropertyName("tags")] public List<string> Tags { get; set; } = new();
    [JsonPropertyName("labels")] public Dictionary<string, List<string>> Labels { get; set; } = new();
}

public sealed class SystemsConfig
{
    [JsonPropertyName("systems")] public Dictionary<string, FinishSystem> Systems { get; set; } = new();
    [JsonPropertyName("assignments")] public List<Rule> Assignments { get; set; } = new();
    [JsonPropertyName("required_items")] public List<Required> RequiredItems { get; set; } = new();

    public static SystemsConfig Load(string path) =>
        JsonSerializer.Deserialize<SystemsConfig>(File.ReadAllText(path)) ?? new SystemsConfig();
}

/// <summary>Finishing systems to purchase quantities, evidence and findings. Same rules as the Python Hasr X-RAY.</summary>
public static class FinishingSystems
{
    static readonly string[] Scopes = { "floor", "wall", "ceiling" };
    static readonly Dictionary<string, (string Ar, string En)> ScopeLabel = new()
    {
        ["floor"] = ("أرضية", "Floor"), ["wall"] = ("حوائط", "Walls"), ["ceiling"] = ("سقف", "Ceiling"),
    };

    static bool Match(string? pattern, string text) =>
        string.IsNullOrEmpty(pattern) || Regex.IsMatch(text, pattern, RegexOptions.IgnoreCase);

    static string? Assign(SystemsConfig cfg, RoomData room, string scope)
    {
        var text = $"{room.Name} {room.LongName}";
        foreach (var r in cfg.Assignments)
        {
            if (r.Scope != scope) continue;
            if (!string.IsNullOrEmpty(r.Exclude) && Match(r.Exclude, text)) continue;
            if (Match(r.RoomMatch, text)) return r.System;
        }
        return null;
    }

    static bool Has(string text, IEnumerable<string> words) =>
        words.Any(w => text.IndexOf(w, StringComparison.OrdinalIgnoreCase) >= 0);

    public static void Analyze(TakeoffResult res, SystemsConfig cfg)
    {
        var totals = new Dictionary<(string Sys, string Comp), (Component C, FinishSystem S, double Net, bool Approved, int Rooms)>();
        var roomSystems = new Dictionary<string, List<string?>>();

        if (res.Rooms.Count == 0)
            res.Findings.Add(new Finding { Status = "red", Where = "(model)",
                Ar = "الموديل مفيهوش غرف (Rooms) أو مساحاتها صفر. أنشئ الغرف في الريفيت وشغّل تاني.",
                En = "The model has no placed Rooms (or their area is zero). Place rooms in Revit and run again." });

        foreach (var room in res.Rooms)
        {
            var where = $"{room.Name} {room.LongName}".Trim() + (string.IsNullOrEmpty(room.Level) ? "" : $" / {room.Level}");
            roomSystems[room.Id] = new();
            foreach (var scope in Scopes)
            {
                var sid = Assign(cfg, room, scope);
                roomSystems[room.Id].Add(sid);
                double bse = scope == "wall" ? room.Perimeter * room.Height : room.Area;
                var baseLabel = scope == "wall" ? "perimeter x height" : "room area";
                var baseNote = scope == "wall" ? "gross wall area, NO deduction for doors/windows" : "from the Room area";
                if (sid is null || !cfg.Systems.TryGetValue(sid, out var sys))
                {
                    res.Findings.Add(new Finding { Status = "red", Where = where,
                        Ar = $"{ScopeLabel[scope].Ar}: مفيش نظام تشطيب محدد للغرفة دي ({bse:0.0} م²).",
                        En = $"{ScopeLabel[scope].En}: no finishing system assigned to this room ({bse:0.0} m2)." });
                    continue;
                }
                var unapproved = new List<string>();
                foreach (var c in sys.Components)
                {
                    double net; string formula;
                    switch (c.Kind)
                    {
                        case "per_m2": net = bse * (c.Rate ?? 0); formula = $"{bse:0.00} m2 x {c.Rate} {c.Unit}/m2"; break;
                        case "piece": net = bse / (c.PieceArea ?? 1); formula = $"{bse:0.00} m2 / {c.PieceArea} m2 per piece"; break;
                        case "per_m_perimeter": net = room.Perimeter * (c.Rate ?? 1); formula = $"perimeter {room.Perimeter:0.00} m x {c.Rate ?? 1} (no door deduction)"; break;
                        default: throw new InvalidOperationException($"unknown component kind {c.Kind}");
                    }
                    if (!c.Approved) unapproved.Add(c.En);
                    res.Evidence.Add(new EvidenceRow { Room = where, Guid = room.Id, Scope = scope, System = sys.En, Component = c.En,
                        BaseLabel = baseLabel, Base = bse, BaseNote = baseNote, Formula = formula, Net = net, Unit = c.Unit,
                        Waste = c.Waste, Source = c.Source, Approved = c.Approved });
                    var key = (sid, c.Id);
                    totals.TryGetValue(key, out var t);
                    totals[key] = (c, sys, t.Net + net, (t.Rooms == 0 || t.Approved) && c.Approved, t.Rooms + 1);
                }
                if (unapproved.Count > 0)
                    res.Findings.Add(new Finding { Status = "orange", Where = where,
                        Ar = $"{ScopeLabel[scope].Ar}: معدلات غير معتمدة في «{sys.Ar}» ({string.Join(", ", unapproved)}). راجعها واعتمدها.",
                        En = $"{ScopeLabel[scope].En}: unapproved rates in '{sys.En}' ({string.Join(", ", unapproved)}). Review and approve." });
            }
        }

        foreach (var req in cfg.RequiredItems)
            foreach (var room in res.Rooms)
            {
                if (!Match(req.RoomMatch, $"{room.Name} {room.LongName}")) continue;
                var tags = new HashSet<string>();
                foreach (var sid in roomSystems[room.Id])
                    if (sid != null && cfg.Systems.TryGetValue(sid, out var s))
                        foreach (var c in s.Components) foreach (var t in c.Tags) tags.Add(t);
                foreach (var tag in req.Tags.Where(t => !tags.Contains(t)))
                {
                    var lab = req.Labels.TryGetValue(tag, out var l) ? l : new List<string> { tag, tag };
                    res.Findings.Add(new Finding { Status = "red", Where = $"{room.Name} {room.LongName}".Trim(),
                        Ar = $"ناقص بند «{lab[0]}» في هذه الغرفة.", En = $"Missing item '{lab[1]}' for this room." });
                }
            }

        foreach (var kv in totals.OrderBy(k => k.Key.Sys, StringComparer.Ordinal).ThenBy(k => k.Key.Comp, StringComparer.Ordinal))
        {
            var (c, s, net, approved, rooms) = kv.Value;
            var gross = net * (1 + c.Waste / 100.0);
            res.Purchase.Add(new PurchaseLine { SystemAr = s.Ar, SystemEn = s.En, Ar = c.Ar, En = c.En, Unit = c.Unit, Net = net, Waste = c.Waste,
                Gross = gross, PackSize = c.PackSize, PackAr = c.PackAr, PackEn = c.PackEn,
                Packs = c.PackSize is > 0 ? (int)Math.Ceiling(gross / c.PackSize.Value - 1e-9) : null, Approved = approved, Rooms = rooms });
        }

        // double-counting check against the takeoff this tool just produced
        var texts = res.Lines.Select(l => $"{l.ItemEn} | {l.ItemAr}").ToList();
        foreach (var sid in totals.Keys.Select(k => k.Sys).Distinct().OrderBy(x => x, StringComparer.Ordinal))
        {
            var sys = cfg.Systems[sid];
            var hit = texts.FirstOrDefault(t => Has(t, sys.BoqKeywords));
            if (hit is null) continue;   // nothing modelled for this system: purchase list stands alone
            foreach (var c in sys.Components.Where(c => c.IncludedKeywords.Count > 0))
                res.Findings.Add(new Finding { Status = "orange", Where = "takeoff",
                    Ar = $"المحصور فيه بند «{hit.Split('|')[1].Trim()}». راجع هل يشمل «{c.Ar}» قبل شراء «{c.Ar}» منفصل.",
                    En = $"The takeoff has '{hit.Split('|')[0].Trim()}'. Check whether it already includes '{c.En}' before buying it separately." });
        }
    }
}
