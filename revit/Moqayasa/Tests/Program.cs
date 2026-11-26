using System.Text.Json;
using Moqayasa.Core;

int fails = 0, passes = 0;
void Check(bool ok, string what) { if (ok) passes++; else { fails++; Console.WriteLine("FAIL: " + what); } }
bool Near(double a, double b, double t = 1e-6) => Math.Abs(a - b) < t;

var sysPath = Path.Combine(AppContext.BaseDirectory, "systems_example.json");
var cfg = SystemsConfig.Load(sysPath);

// ---- hand-computed checks
{
    var els = new List<ElementData>
    {
        new() { Id = "d1", Category = "Doors", TypeName = "D1", Width = 0.9, Height = 2.1 },
        new() { Id = "d2", Category = "Doors", TypeName = "D1", Width = 0.9, Height = 2.1 },
        new() { Id = "d3", Category = "Doors", TypeName = "D2", Width = 1.0, Height = 2.1 },
        new() { Id = "c1", Category = "StructuralColumns", TypeName = "C30x60", Volume = 0.54, Length = 3.0, Material = "Concrete C30" },
        new() { Id = "c2", Category = "StructuralColumns", TypeName = "C30x60", Volume = 0.54, Length = 3.0, Material = "Concrete C30" },
        new() { Id = "rb", Category = "Rebar", TypeName = "T16", Length = 100, WeightKg = 157.8 },
        new() { Id = "f1", Category = "Furniture", TypeName = "Sofa" },
        new() { Id = "x1", Category = "Weird", TypeName = "?" },
    };
    var r = Takeoff.Build("T", els, new List<MaterialArea>(), new List<RoomData>(), null, null);
    var doors = r.Lines.Where(l => l.ItemEn.StartsWith("Doors")).ToList();
    Check(doors.Count == 2, "doors split by type/size (2 lines)");
    Check(Near(doors.Sum(l => l.Qty), 3), "3 doors total");
    var col = r.Lines.First(l => l.ItemEn.StartsWith("Structural columns") && l.Unit == "m3");
    Check(Near(col.Qty, 1.08), "columns volume 2x0.54 = 1.08");
    var rb = r.Lines.First(l => l.ItemEn.StartsWith("Reinforcement") && l.Unit == "ton");
    Check(Near(rb.Qty, 0.1578), "rebar 157.8 kg = 0.1578 ton");
    Check(r.Notes.Any(n => n.Contains("Weird")), "unknown category reported");
    var prices = new Dictionary<string, double> { [col.ItemEn] = 100 };
    var r2 = Takeoff.Build("T", els, new List<MaterialArea>(), new List<RoomData>(), prices, null);
    Check(Near(Takeoff.Total(r2), 108), "total = 1.08 x 100 priced items only");
}
{   // purchase: 1 room 4x5, floor 20 m2, perimeter 18, height 3 -> wall 54 m2
    var room = new RoomData { Id = "r1", Name = "101", LongName = "Living", Level = "L1", Area = 20, Perimeter = 18, Height = 3 };
    var r = Takeoff.Build("T", new List<ElementData>(), new List<MaterialArea>(), new List<RoomData> { room }, null, cfg);
    Check(r.Purchase.Count > 0, "purchase list produced");
    Check(r.Evidence.Count > 0 && r.Evidence.All(e => e.Guid == "r1"), "evidence per number");
    Check(r.Purchase.All(p => p.Gross + 1e-9 >= p.Net), "gross >= net (waste applied)");
    Check(r.Purchase.All(p => !p.Approved), "all example rates unapproved");
    Check(r.Findings.Any(f => f.Status == "orange"), "unapproved rates flagged orange");
    var wallNet = r.Evidence.Where(e => e.Scope == "wall").Select(e => e.Base).Distinct().ToList();
    Check(wallNet.Count == 1 && Near(wallNet[0], 54), "wall base 18 x 3 = 54");
    var floorNet = r.Evidence.Where(e => e.Scope == "floor").Select(e => e.Base).Distinct().ToList();
    Check(floorNet.Count == 1 && Near(floorNet[0], 20), "floor base 20");
}
{   // no rooms -> red
    var r = Takeoff.Build("T", new List<ElementData>(), new List<MaterialArea>(), new List<RoomData>(), null, cfg);
    Check(r.Findings.Any(f => f.Status == "red"), "no rooms is a red finding");
}
// ---- price feed (no network)
{
    var src = new PriceSource { Item = "Cement", Vendor = "Test vendor", Url = "http://x", Regex = "price:\\s*([\\d,\\.]+)", UnitFactor = 20, Verified = true, Refresh = "weekly" };
    Check(Near(PriceFeed.Extract("<b>price: 1,234.5 EGP</b>", src)!.Value, 24690), "extract with comma and factor");
    Check(Near(PriceFeed.Extract("price: ٣٠٠", src)!.Value, 6000), "arabic-indic digits");
    Check(PriceFeed.Extract("nothing", src) is null, "no match -> null");
    var cfgF = new PriceFeedConfig { Sources = { src } };
    var today = new DateTime(2026, 11, 26);
    Check(PriceFeed.Due(src, today), "never fetched is due");
    var log = PriceFeed.Refresh(cfgF, today, _ => "price: 10");
    Check(src.LastPrice == 200 && src.LastUpdated == "2026-11-26", "refresh stores price and date");
    Check(!PriceFeed.Due(src, today.AddDays(3)), "weekly not due after 3 days");
    Check(PriceFeed.Due(src, today.AddDays(7)), "weekly due after 7 days");
    PriceFeed.Refresh(cfgF, today.AddDays(8), _ => "layout changed");
    Check(src.LastPrice == 200, "failed match keeps old price");
    PriceFeed.Refresh(cfgF, today.AddDays(8), _ => throw new Exception("down"));
    Check(src.LastPrice == 200, "network failure keeps old price");
    src.Verified = false; src.LastUpdated = "2020-01-01";
    Check(!PriceFeed.Due(src, today), "unverified source never fetched");
    src.Verified = true;
    var merged = PriceFeed.Merge(new Dictionary<string, double> { ["Cement"] = 5 }, cfgF);
    Check(Near(merged["Cement"], 5), "hand price wins over feed");
}
{   // prices file keeps typed prices across runs
    var f = Path.Combine(Path.GetTempPath(), "mq_prices_test.csv"); File.Delete(f);
    var ln = new List<BoqLine> { new() { ItemEn = "Doors: D1", Unit = "count" } };
    Takeoff.WritePricesTemplate(f, ln);
    File.WriteAllText(f, "item,unit,price\n\"Doors: D1\",No.,500\n");
    Takeoff.WritePricesTemplate(f, ln);
    Check(Takeoff.LoadPrices(f).TryGetValue("Doors: D1", out var kept) && kept == 500, "typed price survives rewrite");
}
{   // every shipped price source must read a number from the saved real-page rows
    var feedCfg = PriceFeedConfig.Load(Path.Combine(AppContext.BaseDirectory, "price_sources_example.json"));
    var rows = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "fixtures", "qsmind_rows.html"));
    Check(feedCfg.Sources.Count >= 20, "example feed has sources");
    foreach (var s in feedCfg.Sources) Check(PriceFeed.Extract(rows, s) is double v && v > 0, "rule reads a price: " + s.Item);
    Check(feedCfg.Sources.All(s => s.LastPrice is null), "no price is shipped in the example feed");
    var ezz = feedCfg.Sources.First(s => s.Item == "Rebar (Ezz)");
    Check(PriceFeed.Extract(rows, ezz) == 40850.0, "Ezz rebar row reads 40,850");
}

// ---- reference prices + update check
{
    var els = new List<ElementData>
    {
        new() { Id = "c1", Category = "StructuralColumns", TypeName = "C30x60", Volume = 2.0, Material = "Concrete C30" },
        new() { Id = "rb", Category = "Rebar", TypeName = "T16", Length = 100, WeightKg = 2000 },
        new() { Id = "d1", Category = "Doors", TypeName = "D1", Width = 0.9, Height = 2.1 },
    };
    var mats = new List<MaterialArea>
    {
        new() { ElementId = "w1", HostCategory = "Floors", Material = "Porcelain 60x60", Area = 10 },
        new() { ElementId = "w2", HostCategory = "Walls", Material = "Gypsum board 12mm", Area = 28.8 },
    };
    var feed = new PriceFeedConfig { Sources = {
        new PriceSource { Item = "Rebar (Ezz)", Vendor = "V", Verified = true, LastPrice = 50000, LastUpdated = "2026-11-26", Currency = "EGP", UnitNote = "ton" },
        new PriceSource { Item = "Ready-mix concrete 300", Vendor = "V", Verified = true, LastPrice = 2000, LastUpdated = "2026-11-26" },
        new PriceSource { Item = "Porcelain tiles 60x60", Vendor = "V", Verified = true, LastPrice = 300, LastUpdated = "2026-11-26" },
        new PriceSource { Item = "Gypsum boards 1.2x2.4", Vendor = "V", Verified = true, LastPrice = 288, LastUpdated = "2026-11-26", UnitNote = "board" },
        new PriceSource { Item = "HDF moulded internal door", Vendor = "V", Verified = false, LastPrice = 999 },
    } };
    var r = Takeoff.Build("T", els, mats, new List<RoomData>(), new Dictionary<string, double>(), null);
    int n = PriceFeed.ApplyReference(r.Lines, feed);
    var conc = r.Lines.First(l => l.ItemEn.StartsWith("Structural columns") && l.Unit == "m3");
    var rb = r.Lines.First(l => l.ItemEn.StartsWith("Reinforcement") && l.Unit == "ton");
    var tile = r.Lines.First(l => l.ItemEn.StartsWith("Tiles"));
    var gyp = r.Lines.First(l => l.ItemEn.StartsWith("Gypsum"));
    var door = r.Lines.First(l => l.ItemEn.StartsWith("Doors"));
    Check(n == 4, "4 reference prices applied, got " + n);
    Check(conc.Price == 2000 && conc.PriceKind == "reference" && conc.PriceNote.Contains("غير معتمد") && conc.PriceNote.Contains("2026-11-26"), "concrete reference price with source/date note");
    Check(rb.Price == 50000, "rebar per ton");
    Check(tile.Price == 300 && Near(gyp.Price!.Value, 100), "tile per m2, gypsum board price / 2.88 m2 = 100");
    Check(door.Price is null && door.PriceKind == "", "unsourced item stays empty (needs quote)");
    var manual = new Dictionary<string, double> { [conc.ItemEn] = 1234 };
    var r2 = Takeoff.Build("T", els, mats, new List<RoomData>(), manual, null);
    PriceFeed.ApplyReference(r2.Lines, feed);
    var c2 = r2.Lines.First(l => l.ItemEn.StartsWith("Structural columns") && l.Unit == "m3");
    Check(c2.Price == 1234 && c2.PriceKind == "manual", "your own price always wins over reference");
    var x = Path.Combine(Path.GetTempPath(), "mq_ref.xlsx"); Report.WriteXlsx(x, r);
    Check(new FileInfo(x).Length > 2000, "xlsx with reference columns written");

    var info = Update.Parse("{\"version\":\"0.6.0\",\"changelog_ar\":\"x\",\"download\":\"https://example.com/z\"}");
    Check(Update.ShouldOffer(info, "0.5.4", null), "newer version offered");
    Check(!Update.ShouldOffer(info, "0.6.0", null) && !Update.ShouldOffer(info, "0.7.0", null), "same or older not offered");
    Check(!Update.ShouldOffer(info, "0.5.4", "0.6.0"), "skipped version not offered");
    Check(Update.ShouldOffer(info, "0.5.4", "0.5.9"), "older skip does not hide a newer version");
    Check(!Update.ShouldOffer(Update.Parse("garbage"), "0.5.4", null) && !Update.ShouldOffer(null, "0.5.4", null), "bad json: silent");
    Check(!Update.ShouldOffer(Update.Parse("{\"version\":\"0.9\",\"download\":\"http://x\"}"), "0.5.4", null), "non-https download refused");
    Check(Update.ShouldOffer(Update.Parse("{\"version\":\"v0.10.0\",\"download\":\"https://x\"}"), "0.9.0", null), "0.10 > 0.9 numerically");
}

Console.WriteLine($"core checks: {passes} passed, {fails} failed");
// ---- fixture mode: Tests <fixture.json> <outdir> [prices.csv]
if (args.Length >= 2)
{
    var opt = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
    var fx = JsonSerializer.Deserialize<Fixture>(File.ReadAllText(args[0]), opt)!;
    var prices = args.Length > 2 ? Takeoff.LoadPrices(args[2]) : new Dictionary<string, double>();
    var res = Takeoff.Build(fx.Project, fx.Elements, fx.MaterialAreas, fx.Rooms, prices, cfg);
    Directory.CreateDirectory(args[1]);
    Report.WriteXlsx(Path.Combine(args[1], "moqayasa.xlsx"), res);
    Report.WriteHtml(Path.Combine(args[1], "moqayasa.html"), res, prices.Count > 0 ? Takeoff.Total(res) : null, "fixture run");
    Console.WriteLine($"fixture: {res.Lines.Count} lines, {res.Purchase.Count} purchase, {res.Findings.Count} findings -> {args[1]}");
}
return fails == 0 ? 0 : 1;

record Fixture(string Project, List<ElementData> Elements, List<RoomData> Rooms, List<MaterialArea> MaterialAreas);
