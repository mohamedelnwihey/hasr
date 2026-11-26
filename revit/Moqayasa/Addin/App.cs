using System.Reflection;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Moqayasa.Core;

namespace Moqayasa;

public sealed class App : IExternalApplication
{
    public Result OnStartup(UIControlledApplication app)
    {
        const string tab = "مقايسة";
        try { app.CreateRibbonTab(tab); } catch { /* tab exists */ }
        var panel = app.CreateRibbonPanel(tab, "مقايسة");
        var data = new PushButtonData("MoqayasaRun", "تشغيل\nRun", Assembly.GetExecutingAssembly().Location, typeof(RunCommand).FullName)
        { ToolTip = "حصر وتسعير كل عناصر الموديل بضغطة واحدة / Take off and price the whole model in one click" };
        panel.AddItem(data);
        Updater.Start(app);
        return Result.Succeeded;
    }
    public Result OnShutdown(UIControlledApplication app) => Result.Succeeded;
}

[Transaction(TransactionMode.ReadOnly)]
public sealed class RunCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData data, ref string message, ElementSet elements)
    {
        var doc = data.Application.ActiveUIDocument.Document;
        try
        {
            var app = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Moqayasa");
            var docs = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "Moqayasa");
            Directory.CreateDirectory(app); Directory.CreateDirectory(docs);

            // user-editable files, created from the shipped examples on first run and never overwritten
            var dllDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location)!;
            var systemsPath = Path.Combine(app, "systems.json");
            if (!File.Exists(systemsPath)) File.Copy(Path.Combine(dllDir, "systems_example.json"), systemsPath);
            var feedPath = Path.Combine(app, "price_sources.json");
            if (!File.Exists(feedPath)) File.Copy(Path.Combine(dllDir, "price_sources_example.json"), feedPath);
            var pricesPath = Path.Combine(app, "prices.csv");

            var c = new Collector(doc); c.Run();

            var feed = PriceFeedConfig.Load(feedPath);
            var log = new List<string>();
            try { log = PriceFeed.Refresh(feed, DateTime.Today, Fetcher.Get); feed.Save(feedPath); } catch (Exception ex) { log.Add("price feed: " + ex.Message); }
            var prices = Takeoff.LoadPrices(pricesPath);   // only YOUR prices go in; they always win

            var res = Takeoff.Build(doc.Title, c.Elements, c.MaterialAreas, c.Rooms, prices, SystemsConfig.Load(systemsPath));
            int refCount = PriceFeed.ApplyReference(res.Lines, feed);   // reference market prices only for lines you left empty
            res.Notes.Add($"أسعار مرجعية من السوق لـ {refCount} بند (توريد فقط، غير معتمدة). الباقي محتاج عرض سعر. / Reference market prices for {refCount} lines (supply only, unapproved). Others need a quote.");
            foreach (var w in c.Warnings.Take(20)) res.Notes.Add("تحذير / warning: " + w);
            foreach (var l in log) res.Notes.Add("الأسعار / prices: " + l);
            Takeoff.WritePricesTemplate(pricesPath, res.Lines);   // keeps the user's file shape; existing prices are not lost because prices are read first and merged above

            var stamp = DateTime.Now.ToString("yyyyMMdd-HHmm");
            var safe = string.Concat(doc.Title.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch));
            var xlsx = Path.Combine(docs, $"{safe}-{stamp}.xlsx"); var html = Path.Combine(docs, $"{safe}-{stamp}.html");
            double? total = res.Lines.Any(l => l.Price != null) ? Takeoff.Total(res) : (double?)null;
            Report.WriteXlsx(xlsx, res);
            Report.WriteHtml(html, res, total, DateTime.Now.ToString("yyyy-MM-dd HH:mm"));

            int red = res.Findings.Count(f => f.Status == "red");
            var td = new TaskDialog("مقايسة") { MainInstruction = $"تم حصر {res.Lines.Count} بند من {res.Elements.Count} عنصر",
                MainContent = $"ناقص (أحمر): {red}\nللمراجعة: {res.Findings.Count - red}\nالتقارير في: {docs}" };
            td.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "فتح التقرير (HTML)");
            td.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, "فتح ملف Excel");
            var r = td.Show();
            if (r == TaskDialogResult.CommandLink1) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(html) { UseShellExecute = true });
            if (r == TaskDialogResult.CommandLink2) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(xlsx) { UseShellExecute = true });
            return Result.Succeeded;
        }
        catch (Exception ex) { message = ex.Message; return Result.Failed; }
    }
}

/// <summary>Polite fetch for the price feed: identifies itself, 15 s timeout, runs only for sources that are verified and due.</summary>
static class Fetcher
{
    static readonly System.Net.Http.HttpClient Http = Make();
    static System.Net.Http.HttpClient Make()
    {
        var h = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(15) };
        h.DefaultRequestHeaders.UserAgent.ParseAdd("Moqayasa/" + Update.Current + " (+https://github.com/mohamedelnwihey/hasr)");
        return h;
    }
    public static string? Get(string url) => Http.GetStringAsync(url).GetAwaiter().GetResult();
}
