namespace Moqayasa.Core;

public static class Units
{
    public static string Ar(string u) => u switch
    {
        "m2" => "م²", "m3" => "م³", "m" => "م.ط", "count" => "عدد", "ton" => "طن", _ => u,
    };
    public static string En(string u) => u switch { "m2" => "m²", "m3" => "m³", "m" => "m", "count" => "No.", "ton" => "ton", _ => u };
}

/// <summary>What gets quantified for each category, and in which order (architectural, structural, finishes, furniture, services).</summary>
public sealed record CategoryPolicy(string Key, int Order, string GroupAr, string GroupEn, string ItemAr, string ItemEn, string[] Measures);

public static class Policy
{
    private const string Arch = "أعمال معمارية", ArchEn = "Architectural";
    private const string Str = "أعمال إنشائية", StrEn = "Structural";
    private const string Furn = "فرش ونجارة", FurnEn = "Furniture and joinery";
    private const string Svc = "تجهيزات وخدمات", SvcEn = "Fixtures and services";

    public static readonly CategoryPolicy[] Categories =
    {
        new("Walls", 10, Arch, ArchEn, "حوائط", "Walls", new[] { "area", "volume", "length" }),
        new("CurtainWalls", 11, Arch, ArchEn, "حوائط ستائرية", "Curtain walls", new[] { "area", "count" }),
        new("Doors", 12, Arch, ArchEn, "أبواب", "Doors", new[] { "count" }),
        new("Windows", 13, Arch, ArchEn, "شبابيك", "Windows", new[] { "count" }),
        new("Floors", 14, Arch, ArchEn, "أرضيات وبلاطات", "Floors", new[] { "area", "volume" }),
        new("Ceilings", 15, Arch, ArchEn, "أسقف معلقة", "Ceilings", new[] { "area" }),
        new("Roofs", 16, Arch, ArchEn, "أسقف وأسطح", "Roofs", new[] { "area", "volume" }),
        new("Stairs", 17, Arch, ArchEn, "سلالم", "Stairs", new[] { "count", "volume" }),
        new("Ramps", 18, Arch, ArchEn, "منحدرات", "Ramps", new[] { "count", "area" }),
        new("Railings", 19, Arch, ArchEn, "درابزين", "Railings", new[] { "length" }),
        new("Columns", 20, Arch, ArchEn, "أعمدة معمارية", "Architectural columns", new[] { "count", "volume" }),
        new("StructuralColumns", 30, Str, StrEn, "أعمدة إنشائية", "Structural columns", new[] { "count", "volume", "length" }),
        new("StructuralFraming", 31, Str, StrEn, "كمرات وإطارات", "Structural framing", new[] { "count", "volume", "length" }),
        new("StructuralFoundation", 32, Str, StrEn, "أساسات", "Foundations", new[] { "count", "volume", "area" }),
        new("Rebar", 33, Str, StrEn, "حديد تسليح", "Reinforcement", new[] { "weight", "length" }),
        new("Furniture", 50, Furn, FurnEn, "فرش", "Furniture", new[] { "count" }),
        new("Casework", 51, Furn, FurnEn, "نجارة وكاونترات", "Casework", new[] { "count", "length" }),
        new("PlumbingFixtures", 60, Svc, SvcEn, "أدوات صحية", "Plumbing fixtures", new[] { "count" }),
        new("LightingFixtures", 61, Svc, SvcEn, "وحدات إضاءة", "Lighting fixtures", new[] { "count" }),
        new("ElectricalFixtures", 62, Svc, SvcEn, "تجهيزات كهربائية", "Electrical fixtures", new[] { "count" }),
        new("GenericModels", 63, Svc, SvcEn, "عناصر عامة", "Generic models", new[] { "count" }),
    };

    public static CategoryPolicy? Find(string key) => Categories.FirstOrDefault(c => c.Key == key);

    // Material classes recognised from the material NAME (what the model itself says).
    public static readonly (string Cls, string Ar, string En, string[] Words)[] FinishClasses =
    {
        ("paint", "دهانات", "Paint", new[] { "paint", "دهان", "emulsion", "بلاستيك", "طلاء" }),
        ("gypsum", "جبس بورد", "Gypsum board", new[] { "gypsum", "جبس", "plasterboard", "drywall", "gyp" }),
        ("plaster", "بياض / محارة", "Plaster", new[] { "plaster", "بياض", "محارة", "render", "stucco" }),
        ("tile", "بلاط / سيراميك / بورسلين", "Tiles", new[] { "tile", "ceramic", "porcelain", "بلاط", "سيراميك", "بورسلين" }),
        ("stone", "رخام / حجر", "Stone and marble", new[] { "marble", "granite", "stone", "رخام", "جرانيت", "حجر" }),
        ("wood", "خشب / باركيه", "Wood and parquet", new[] { "wood", "parquet", "timber", "oak", "خشب", "باركيه" }),
    };

    public static string? ClassifyFinish(string material)
    {
        var m = (material ?? "").ToLowerInvariant();
        foreach (var f in FinishClasses)
            if (f.Words.Any(w => m.Contains(w.ToLowerInvariant()))) return f.Cls;
        return null;
    }

    public static readonly string[] ConcreteWords = { "concrete", "خرسان", "reinforced", "مسلح", "r.c." };
    public static bool IsConcrete(string material) =>
        ConcreteWords.Any(w => (material ?? "").ToLowerInvariant().Contains(w));
}
