using System.Globalization;
using System.Net;
using System.Text;

namespace Moqayasa.Core;

public static class Report
{
    static string N(double v) => v.ToString("#,##0.00", CultureInfo.InvariantCulture);
    static S St(string s) => s == "green" ? S.Green : s == "red" ? S.Red : S.Orange;
    static string StAr(string s) => s == "green" ? "تمام" : s == "red" ? "ناقص" : "راجع";

    public static void WriteXlsx(string path, TakeoffResult r)
    {
        var sheets = new List<Sheet>();

        // 1. BOQ with price column + formulas
        var boq = new Sheet { Name = "المقايسة", FreezeRow = 3, Widths = { 6, 22, 40, 40, 8, 12, 9, 14, 16, 36, 58 } };
        boq.Add(new Cell($"مقايسة / Bill of Quantities — {r.ProjectName}", S.Title));
        boq.Add(new Cell("الأخضر = سعرك. البرتقالي = سعر سوق مرجعي من مصدر موثّق (توريد فقط، غير معتمد، راجع المصدر والتاريخ). بدون سعر = محتاج عرض سعر وخارج الإجمالي.", S.Note));
        boq.Add(new Cell("م", S.Header), new Cell("المجموعة", S.Header), new Cell("البند", S.Header), new Cell("Item", S.Header), new Cell("الوحدة", S.Header),
            new Cell("الكمية", S.Header), new Cell("عدد العناصر", S.Header), new Cell("سعر الوحدة", S.Header), new Cell("الإجمالي", S.Header), new Cell("أساس الحساب", S.Header), new Cell("مصدر السعر", S.Header));
        int first = boq.Rows.Count + 1;
        foreach (var l in r.Lines)
        {
            int row = boq.Rows.Count + 1;
            boq.Add(new Cell(l.Order, S.Int), new Cell(l.GroupAr, S.Text), new Cell(l.ItemAr, S.Text), new Cell(l.ItemEn, S.Text), new Cell(Units.Ar(l.Unit), S.Text),
                new Cell(Math.Round(l.Qty, 3), S.Num), new Cell(l.Elements, S.Int),
                new Cell(l.Price, S.Input), new Cell(null, S.Num, $"IF(H{row}=\"\",\"\",F{row}*H{row})"), new Cell(l.Basis, S.Text),
                new Cell(l.PriceKind == "manual" ? "سعرك (prices.csv)" : l.PriceKind == "reference" ? l.PriceNote : "محتاج عرض سعر / needs quote", l.PriceKind == "manual" ? S.Green : S.Orange));
        }
        int last = boq.Rows.Count;
        boq.Add(new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("الإجمالي (البنود المسعّرة فقط)", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText),
            new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell(null, S.TotalNum, $"SUM(I{first}:I{last})"), new Cell("", S.TotalText), new Cell("", S.TotalText));
        boq.Add(new Cell("", S.Text), new Cell("", S.Text), new Cell("منه: بنود بأسعار سوق مرجعية غير معتمدة (توريد فقط)", S.Orange), new Cell("", S.Text), new Cell("", S.Text),
            new Cell("", S.Text), new Cell("", S.Text), new Cell("", S.Text), new Cell(null, S.Num, $"SUMIF(K{first}:K{last},\"سعر سوق*\",I{first}:I{last})"), new Cell("", S.Text), new Cell("", S.Text));
        sheets.Add(boq);

        // 2. purchase list
        var pur = new Sheet { Name = "قائمة المشتريات", FreezeRow = 3, Widths = { 24, 32, 9, 12, 9, 12, 8, 14, 16, 14, 16, 12 } };
        pur.Add(new Cell("قائمة المشتريات (مع الهالك) / Purchase list", S.Title));
        pur.Add(new Cell("معدلات الهالك والتغليف أمثلة غير معتمدة إلا لو معلّمة «معتمد». ما يظهر هنا مش في المحصور من الموديل.", S.Note));
        pur.Add(new Cell("النظام", S.Header), new Cell("المكوّن", S.Header), new Cell("الوحدة", S.Header), new Cell("صافي", S.Header), new Cell("هالك %", S.Header), new Cell("إجمالي للشراء", S.Header),
            new Cell("عدد الغرف", S.Header), new Cell("العبوة", S.Header), new Cell("عدد العبوات", S.Header), new Cell("سعر العبوة", S.Header), new Cell("الإجمالي", S.Header), new Cell("الحالة", S.Header));
        int pf = pur.Rows.Count + 1;
        foreach (var p in r.Purchase)
        {
            int row = pur.Rows.Count + 1;
            pur.Add(new Cell(p.SystemAr, S.Text), new Cell(p.Ar, S.Text), new Cell(p.Unit, S.Text), new Cell(p.Net, S.Num), new Cell(p.Waste, S.Num), new Cell(p.Gross, S.Num), new Cell(p.Rooms, S.Int),
                new Cell(p.PackSize is null ? "" : $"{p.PackAr}", S.Text), new Cell(p.Packs is int k ? (double)k : null, S.Int), new Cell(p.PricePerPack, S.Input),
                new Cell(null, S.Num, $"IF(OR(J{row}=\"\",I{row}=\"\"),\"\",I{row}*J{row})"), new Cell(p.Approved ? "معتمد" : "مثال غير معتمد", p.Approved ? S.Green : S.Orange));
        }
        pur.Add(new Cell("", S.TotalText), new Cell("الإجمالي", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText), new Cell("", S.TotalText),
            new Cell(null, S.TotalNum, $"SUM(K{pf}:K{pur.Rows.Count})"), new Cell("", S.TotalText));
        sheets.Add(pur);

        // 3. findings
        var fnd = new Sheet { Name = "إيه اللي ناقص", FreezeRow = 3, Widths = { 10, 36, 80, 60 } };
        fnd.Add(new Cell("الفحص: إيه اللي ناقص", S.Title));
        fnd.Add(new Cell("أخضر = تمام، برتقالي = راجع، أحمر = ناقص", S.Note));
        fnd.Add(new Cell("الحالة", S.Header), new Cell("المكان", S.Header), new Cell("الملاحظة", S.Header), new Cell("Note", S.Header));
        foreach (var f in r.Findings.OrderBy(f => f.Status == "red" ? 0 : f.Status == "orange" ? 1 : 2))
            fnd.Add(new Cell(StAr(f.Status), St(f.Status)), new Cell(f.Where, S.Text), new Cell(f.Ar, S.Text), new Cell(f.En, S.Text));
        if (r.Findings.Count == 0) fnd.Add(new Cell("تمام", S.Green), new Cell("", S.Text), new Cell("مفيش ملاحظات.", S.Text), new Cell("No findings.", S.Text));
        sheets.Add(fnd);

        // 4. element details
        var det = new Sheet { Name = "تفاصيل العناصر", FreezeRow = 1, Widths = { 18, 14, 36, 16, 22, 10, 10, 10, 10, 10, 12, 8 } };
        det.Add(new Cell("المعرّف", S.Header), new Cell("الفئة", S.Header), new Cell("النوع", S.Header), new Cell("الدور", S.Header), new Cell("الخامة", S.Header),
            new Cell("مساحة م²", S.Header), new Cell("حجم م³", S.Header), new Cell("طول م", S.Header), new Cell("عرض", S.Header), new Cell("ارتفاع", S.Header), new Cell("وزن كجم", S.Header), new Cell("عدد", S.Header));
        foreach (var e in r.Elements)
            det.Add(new Cell(e.Id, S.Text), new Cell(e.Category, S.Text), new Cell(e.TypeName, S.Text), new Cell(e.Level, S.Text), new Cell(e.Material, S.Text),
                new Cell(e.Area, S.Num), new Cell(e.Volume, S.Num), new Cell(e.Length, S.Num), new Cell(e.Width, S.Num), new Cell(e.Height, S.Num), new Cell(e.WeightKg, S.Num), new Cell(e.Count, S.Int));
        sheets.Add(det);

        // 5. evidence
        var ev = new Sheet { Name = "دليل الأرقام", FreezeRow = 1, Widths = { 30, 10, 26, 30, 18, 12, 36, 44, 12, 8, 8 } };
        ev.Add(new Cell("الغرفة", S.Header), new Cell("النطاق", S.Header), new Cell("النظام", S.Header), new Cell("المكوّن", S.Header), new Cell("أساس القياس", S.Header), new Cell("القيمة", S.Header),
            new Cell("ملاحظة", S.Header), new Cell("المعادلة", S.Header), new Cell("صافي", S.Header), new Cell("الوحدة", S.Header), new Cell("معتمد", S.Header));
        foreach (var x in r.Evidence)
            ev.Add(new Cell(x.Room, S.Text), new Cell(x.Scope, S.Text), new Cell(x.System, S.Text), new Cell(x.Component, S.Text), new Cell(x.BaseLabel, S.Text), new Cell(x.Base, S.Num),
                new Cell(x.BaseNote, S.Text), new Cell(x.Formula, S.Text), new Cell(x.Net, S.Num), new Cell(x.Unit, S.Text), new Cell(x.Approved ? "نعم" : "لا", x.Approved ? S.Green : S.Orange));
        sheets.Add(ev);

        // 6. notes
        var nt = new Sheet { Name = "ملاحظات", Widths = { 140 } };
        nt.Add(new Cell("ملاحظات وحدود", S.Title));
        foreach (var n in r.Notes) nt.Add(new Cell(n, S.Text));
        sheets.Add(nt);

        Xlsx.Write(path, sheets);
    }

    public static void WriteHtml(string path, TakeoffResult r, double? total, string generated)
    {
        string E(string s) => WebUtility.HtmlEncode(s ?? "");
        var sb = new StringBuilder();
        sb.Append(@"<!doctype html><html lang=""ar"" dir=""rtl""><head><meta charset=""utf-8""><meta name=""viewport"" content=""width=device-width,initial-scale=1"">
<title>مقايسة</title><style>
:root{--ink:#14262e;--teal:#1f4e5f;--sand:#f6f1e7;--line:#d9d2c3;--g:#2e8b57;--o:#d98a1a;--r:#c0392b}
*{box-sizing:border-box}
body{margin:0;background:var(--sand);color:var(--ink);font-family:'IBM Plex Sans Arabic','Noto Naskh Arabic','Segoe UI','Tahoma',sans-serif;line-height:1.6}
header{background:linear-gradient(135deg,#123642,#1f4e5f);color:#fff;padding:28px 40px}
header h1{margin:0;font-size:34px;letter-spacing:0}header p{margin:4px 0 0;opacity:.8;font-size:14px}
main{max-width:1180px;margin:-24px auto 40px;padding:0 24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}
.card{background:#fff;border-radius:14px;padding:16px 18px;box-shadow:0 2px 10px #0001}
.card b{display:block;font-size:26px;color:var(--teal)}.card span{font-size:13px;color:#667}
h2{margin:30px 0 10px;font-size:20px;border-inline-start:5px solid var(--teal);padding-inline-start:10px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px #0001;font-size:14px}
th{background:var(--teal);color:#fff;text-align:center;padding:9px 8px;font-weight:600}
td{padding:7px 10px;border-bottom:1px solid #eee;vertical-align:top}td.n{text-align:center;font-variant-numeric:tabular-nums;white-space:nowrap}
tr.g td{background:#e8eef1;font-weight:700}
.pill{display:inline-block;padding:2px 12px;border-radius:99px;color:#fff;font-size:12px;font-weight:700}
.green{background:var(--g)}.orange{background:var(--o)}.red{background:var(--r)}
.note{background:#fff8e1;border:1px solid #f0dca0;border-radius:10px;padding:10px 14px;font-size:13px;margin:8px 0}
footer{text-align:center;color:#778;font-size:12px;padding:20px}
@media print{header{background:#fff;color:#000}.card{box-shadow:none;border:1px solid #ccc}}
</style></head><body>");
        sb.Append($"<header><h1>مقايسة</h1><p>{E(r.ProjectName)} · {E(generated)}</p></header><main>");
        int red = r.Findings.Count(f => f.Status == "red"), org = r.Findings.Count(f => f.Status == "orange");
        sb.Append("<div class=\"cards\">");
        sb.Append($"<div class=\"card\"><b>{r.Lines.Count}</b><span>بند محصور</span></div>");
        sb.Append($"<div class=\"card\"><b>{r.Elements.Sum(e => e.Count)}</b><span>عنصر من الموديل</span></div>");
        sb.Append($"<div class=\"card\"><b>{red}</b><span>ناقص (أحمر)</span></div>");
        sb.Append($"<div class=\"card\"><b>{org}</b><span>للمراجعة (برتقالي)</span></div>");
        sb.Append($"<div class=\"card\"><b>{(total is double t ? N(t) : "—")}</b><span>الإجمالي (البنود المسعّرة فقط)</span></div></div>");
        sb.Append("<div class=\"note\">الأسعار والمعدلات الظاهرة أمثلة غير معتمدة ما لم تتعلّم «معتمد». مفيش أسعار مدمجة في الأداة.</div>");

        sb.Append("<h2>المقايسة</h2><table><tr><th>م</th><th>البند</th><th>الوحدة</th><th>الكمية</th><th>عناصر</th><th>سعر الوحدة</th><th>الإجمالي</th><th>مصدر السعر</th></tr>");
        string grp = "";
        foreach (var l in r.Lines)
        {
            if (l.GroupAr != grp) { grp = l.GroupAr; sb.Append($"<tr class=\"g\"><td colspan=\"8\">{E(grp)}</td></tr>"); }
            sb.Append($"<tr><td class=\"n\">{l.Order}</td><td>{E(l.ItemAr)}<br><small>{E(l.ItemEn)}</small></td><td class=\"n\">{E(Units.Ar(l.Unit))}</td><td class=\"n\">{N(l.Qty)}</td><td class=\"n\">{l.Elements}</td>" +
                $"<td class=\"n\">{(l.Price is double p ? N(p) : "—")}</td><td class=\"n\">{(l.Price is double p2 ? N(p2 * l.Qty) : "—")}</td><td><small>{E(l.PriceKind == "manual" ? "سعرك" : l.PriceKind == "reference" ? l.PriceNote : "محتاج عرض سعر")}</small></td></tr>");
        }
        sb.Append("</table>");
        if (r.Purchase.Count > 0)
        {
            sb.Append("<h2>قائمة المشتريات (مع الهالك)</h2><table><tr><th>النظام</th><th>المكوّن</th><th>صافي</th><th>هالك</th><th>للشراء</th><th>العبوات</th><th>الحالة</th></tr>");
            foreach (var p in r.Purchase)
                sb.Append($"<tr><td>{E(p.SystemAr)}</td><td>{E(p.Ar)}</td><td class=\"n\">{N(p.Net)} {E(p.Unit)}</td><td class=\"n\">{p.Waste:0.#}%</td><td class=\"n\">{N(p.Gross)} {E(p.Unit)}</td><td class=\"n\">{(p.Packs is int k ? k + " × " + E(p.PackAr) : "—")}</td><td class=\"n\"><span class=\"pill {(p.Approved ? "green" : "orange")}\">{(p.Approved ? "معتمد" : "مثال")}</span></td></tr>");
            sb.Append("</table>");
        }
        sb.Append("<h2>إيه اللي ناقص</h2><table><tr><th>الحالة</th><th>المكان</th><th>الملاحظة</th></tr>");
        foreach (var f in r.Findings.OrderBy(f => f.Status == "red" ? 0 : f.Status == "orange" ? 1 : 2).Take(200))
            sb.Append($"<tr><td class=\"n\"><span class=\"pill {E(f.Status)}\">{StAr(f.Status)}</span></td><td>{E(f.Where)}</td><td>{E(f.Ar)}</td></tr>");
        if (r.Findings.Count == 0) sb.Append("<tr><td class=\"n\"><span class=\"pill green\">تمام</span></td><td></td><td>مفيش ملاحظات.</td></tr>");
        sb.Append("</table><h2>ملاحظات</h2>");
        foreach (var n in r.Notes) sb.Append($"<div class=\"note\">{E(n)}</div>");
        sb.Append("</main><footer>مقايسة · جزء من مشروع حصر (Hasr) مفتوح المصدر · MIT</footer></body></html>");
        File.WriteAllText(path, sb.ToString(), new UTF8Encoding(true));
    }
}
