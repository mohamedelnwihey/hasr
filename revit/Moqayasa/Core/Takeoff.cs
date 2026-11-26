using System.Globalization;

namespace Moqayasa.Core;

public static class Takeoff
{
    static double? Measure(ElementData e, string m) => m switch
    {
        "area" => e.Area, "volume" => e.Volume, "length" => e.Length,
        "weight" => e.WeightKg is null ? null : e.WeightKg / 1000.0,
        "count" => e.Count, _ => null,
    };

    static string UnitOf(string m) => m switch { "area" => "m2", "volume" => "m3", "length" => "m", "weight" => "ton", _ => "count" };

    static string DimSuffix(ElementData e)
    {
        if (e.Width is double w && e.Height is double h && w > 0 && h > 0)
            return $" ({w:0.00}x{h:0.00} m)";
        return "";
    }

    public static TakeoffResult Build(string projectName, IEnumerable<ElementData> elements,
        IEnumerable<MaterialArea> materialAreas, IEnumerable<RoomData> rooms,
        Dictionary<string, double>? prices = null, SystemsConfig? systems = null, string source = "Revit")
    {
        var res = new TakeoffResult { ProjectName = projectName };
        res.Elements.AddRange(elements);
        res.MaterialAreas.AddRange(materialAreas);
        res.Rooms.AddRange(rooms);
        var lines = new Dictionary<string, BoqLine>();
        var missing = new Dictionary<string, int>();
        var unknownCats = new Dictionary<string, int>();

        foreach (var g in res.Elements.GroupBy(e => (e.Category, Name: e.TypeName + DimSuffix(e))))
        {
            var pol = Policy.Find(g.Key.Category);
            if (pol is null) { unknownCats[g.Key.Category] = (unknownCats.TryGetValue(g.Key.Category, out var uc) ? uc : 0) + g.Sum(x => x.Count); continue; }
            bool multi = pol.Measures.Length > 1;
            foreach (var m in pol.Measures)
            {
                double total = 0; int n = 0, miss = 0;
                foreach (var e in g)
                {
                    var v = Measure(e, m);
                    if (v is null || v <= 0) { if (m != "count") miss += e.Count; continue; }
                    total += m == "count" ? e.Count : v.Value; n += e.Count;
                }
                if (miss > 0) missing[$"{pol.ItemEn}: {g.Key.Name} [{m}]"] = miss;
                if (n == 0) continue;
                var unit = UnitOf(m);
                var suffixEn = multi ? $" [{Units.En(unit)}]" : "";
                var suffixAr = multi ? $" [{Units.Ar(unit)}]" : "";
                var nameEn = $"{pol.ItemEn}: {g.Key.Name}{suffixEn}";
                lines[nameEn] = new BoqLine
                {
                    Order = pol.Order, GroupAr = pol.GroupAr, GroupEn = pol.GroupEn,
                    ItemAr = $"{pol.ItemAr}: {g.Key.Name}{suffixAr}", ItemEn = nameEn, Unit = unit,
                    Qty = total, Elements = n, Basis = source, Material = g.Select(x => x.Material).FirstOrDefault(x => !string.IsNullOrEmpty(x)) ?? "",
                };
            }
            // formwork for concrete elements, from geometry
            var fw = g.Where(e => e.FormworkArea is > 0 && Policy.IsConcrete(e.Material)).ToList();
            if (fw.Count > 0)
            {
                var nameEn = $"Formwork: {pol.ItemEn} {g.Key.Name}";
                lines[nameEn] = new BoqLine
                {
                    Order = pol.Order + 5, GroupAr = "شدات خشبية", GroupEn = "Formwork",
                    ItemAr = $"شدة خشبية: {pol.ItemAr} {g.Key.Name}", ItemEn = nameEn, Unit = "m2",
                    Qty = fw.Sum(e => e.FormworkArea!.Value), Elements = fw.Sum(e => e.Count),
                    Basis = "geometry-derived estimate",
                };
            }
        }

        // finishes from material areas
        int ignored = 0; var ignoredNames = new HashSet<string>();
        foreach (var g in res.MaterialAreas.GroupBy(a => (Cls: Policy.ClassifyFinish(a.Material), a.Material, a.HostCategory, a.Painted)))
        {
            if (g.Key.Cls is null) { ignored += g.Count(); if (ignoredNames.Count < 6) ignoredNames.Add(g.Key.Material); continue; }
            var f = Policy.FinishClasses.First(x => x.Cls == g.Key.Cls);
            var host = g.Key.HostCategory switch { "Walls" => ("حوائط", "walls"), "Ceilings" => ("أسقف", "ceilings"), "Floors" => ("أرضيات", "floors"), _ => (g.Key.HostCategory, g.Key.HostCategory.ToLowerInvariant()) };
            var nameEn = $"{f.En}: {g.Key.Material} ({host.Item2})";
            lines[nameEn] = new BoqLine
            {
                Order = 40, GroupAr = "تشطيبات (من الخامات)", GroupEn = "Finishes (from materials)",
                ItemAr = $"{f.Ar}: {g.Key.Material} ({host.Item1})", ItemEn = nameEn, Unit = "m2",
                Qty = g.Sum(a => a.Area), Elements = g.Select(a => a.ElementId).Distinct().Count(), Material = g.Key.Material,
                Basis = g.Key.Painted ? "Paint tool" : "material layer",
            };
        }

        res.Lines.AddRange(lines.Values.OrderBy(l => l.Order).ThenBy(l => l.ItemEn, StringComparer.Ordinal));
        if (prices != null) foreach (var l in res.Lines) if (prices.TryGetValue(l.Key, out var p)) { l.Price = p; l.PriceKind = "manual"; l.PriceNote = "سعرك من prices.csv / your own price"; }

        foreach (var kv in missing.OrderBy(k => k.Key))
            res.Notes.Add($"{kv.Value} عنصر بدون قيمة لـ {kv.Key} (مش داخل الإجمالي) / {kv.Value} elements have no value for {kv.Key} (not in the total)");
        foreach (var kv in unknownCats)
            res.Notes.Add($"فئة غير معروفة: {kv.Key} ({kv.Value}) / unknown category: {kv.Key} ({kv.Value})");
        if (ignored > 0)
            res.Notes.Add($"{ignored} خامة مش متصنفة كتشطيب (مثلا: {string.Join("، ", ignoredNames)}) / {ignored} material entries not recognised as a finish (e.g. {string.Join(", ", ignoredNames)})");
        res.Notes.Add("الكميات من الموديل كما هو. المحصور = المرسوم، ومفيش بنود تنفيذ مش مرسومة إلا في «قائمة المشتريات» (معدلات أمثلة غير معتمدة). / Quantities are what is modelled; anything not drawn appears only in the purchase list (example, unapproved rates).");
        res.Notes.Add("الأسعار من ملفك أو من مصدر موثّق في ملف المصادر. مفيش أسعار مدمجة. البنود بدون سعر خارج الإجمالي. / Prices come from your file or a sourced feed. None are built in. Items with no price are outside the total.");

        if (systems != null) FinishingSystems.Analyze(res, systems);
        return res;
    }

    public static double Total(TakeoffResult r) => r.Lines.Where(l => l.Price != null).Sum(l => l.Qty * l.Price!.Value);

    public static Dictionary<string, double> LoadPrices(string csvPath)
    {
        var d = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        if (!File.Exists(csvPath)) return d;
        foreach (var line in File.ReadLines(csvPath).Skip(1))
        {
            var cells = Csv.Split(line);
            if (cells.Count < 3 || string.IsNullOrWhiteSpace(cells[0]) || string.IsNullOrWhiteSpace(cells[2])) continue;
            if (double.TryParse(cells[2].Replace(",", ""), NumberStyles.Float, CultureInfo.InvariantCulture, out var p)) d[cells[0].Trim()] = p;
        }
        return d;
    }

    /// <summary>Prices file: item, unit, price. Keeps every price the user already typed; adds new items blank.</summary>
    public static void WritePricesTemplate(string path, IEnumerable<BoqLine> lines)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var existing = LoadPrices(path);                       // read BEFORE the file is rewritten
        var items = lines.Select(l => (l.ItemEn, l.Unit)).Distinct().ToList();
        var extra = existing.Keys.Where(k => !items.Any(i => string.Equals(i.ItemEn, k, StringComparison.OrdinalIgnoreCase))).ToList();
        using var w = new StreamWriter(path, false, new System.Text.UTF8Encoding(true));
        w.WriteLine("item,unit,price");
        foreach (var (item, unit) in items)
            w.WriteLine($"{Csv.Quote(item)},{Units.En(unit)},{(existing.TryGetValue(item, out var p) ? p.ToString(CultureInfo.InvariantCulture) : "")}");
        foreach (var k in extra) w.WriteLine($"{Csv.Quote(k)},,{existing[k].ToString(CultureInfo.InvariantCulture)}");
    }
}
public static class Csv
{
    public static string Quote(string s) => s.Contains(',') || s.Contains('"') ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;

    public static List<string> Split(string line)
    {
        var res = new List<string>(); var sb = new System.Text.StringBuilder(); bool q = false;
        for (int i = 0; i < line.Length; i++)
        {
            char c = line[i];
            if (q) { if (c == '"') { if (i + 1 < line.Length && line[i + 1] == '"') { sb.Append('"'); i++; } else q = false; } else sb.Append(c); }
            else if (c == '"') q = true;
            else if (c == ',') { res.Add(sb.ToString()); sb.Clear(); }
            else sb.Append(c);
        }
        res.Add(sb.ToString());
        return res;
    }
}
