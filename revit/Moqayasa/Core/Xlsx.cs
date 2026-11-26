using System.IO.Compression;
using System.Security;
using System.Text;
using System.Globalization;

namespace Moqayasa.Core;

public enum S { Default = 0, Header = 1, Text = 2, Num = 3, Title = 4, Green = 5, Orange = 6, Red = 7, Group = 8, TotalNum = 9, Int = 10, Note = 11, Input = 12, TotalText = 13 }

public sealed class Cell
{
    public object? Value; public string? Formula; public S Style = S.Text;
    public Cell(object? v, S s = S.Text, string? formula = null) { Value = v; Style = s; Formula = formula; }
}

public sealed class Sheet
{
    public string Name = "";
    public bool Rtl = true;
    public List<double> Widths = new();
    public List<List<Cell>> Rows = new();
    public List<(int r1, int c1, int r2, int c2)> Merges = new();
    public int FreezeRow;   // rows above this stay visible
    public List<Cell> Add(params Cell[] cells) { var r = cells.ToList(); Rows.Add(r); return r; }
}

/// <summary>Minimal .xlsx writer with no dependencies (System.IO.Compression only).</summary>
public static class Xlsx
{
    static string Col(int i) { var s = ""; i++; while (i > 0) { int m = (i - 1) % 26; s = (char)('A' + m) + s; i = (i - m) / 26; } return s; }
    static string Esc(string s) => SecurityElement.Escape(s) ?? "";

    public static void Write(string path, IList<Sheet> sheets)
    {
        if (File.Exists(path)) File.Delete(path);
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        void Put(string name, string content)
        {
            var e = zip.CreateEntry(name); using var st = new StreamWriter(e.Open(), new UTF8Encoding(false)); st.Write(content);
        }
        var ct = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>");
        for (int i = 1; i <= sheets.Count; i++) ct.Append($"<Override PartName=\"/xl/worksheets/sheet{i}.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>");
        ct.Append("</Types>");
        Put("[Content_Types].xml", ct.ToString());
        Put("_rels/.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/></Relationships>");
        var wb = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets>");
        var rel = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">");
        for (int i = 1; i <= sheets.Count; i++)
        {
            var n = new string(sheets[i - 1].Name.Where(c => !"[]:*?/\\".Contains(c)).ToArray()); if (n.Length > 31) n = n.Substring(0, 31);
            wb.Append($"<sheet name=\"{Esc(n)}\" sheetId=\"{i}\" r:id=\"rId{i}\"/>");
            rel.Append($"<Relationship Id=\"rId{i}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet{i}.xml\"/>");
        }
        wb.Append("</sheets></workbook>");
        rel.Append($"<Relationship Id=\"rId{sheets.Count + 1}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>");
        Put("xl/workbook.xml", wb.ToString());
        Put("xl/_rels/workbook.xml.rels", rel.ToString());
        Put("xl/styles.xml", Styles());
        for (int i = 1; i <= sheets.Count; i++) Put($"xl/worksheets/sheet{i}.xml", SheetXml(sheets[i - 1]));
    }

    static string Styles()
    {
        const string font = "Segoe UI";
        string F(bool b = false, string? color = null, int sz = 10, bool it = false) =>
            $"<font>{(b ? "<b/>" : "")}{(it ? "<i/>" : "")}<sz val=\"{sz}\"/>{(color != null ? $"<color rgb=\"FF{color}\"/>" : "")}<name val=\"{font}\"/></font>";
        string Fill(string rgb) => $"<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF{rgb}\"/><bgColor indexed=\"64\"/></patternFill></fill>";
        var fonts = F() + F(true, "FFFFFF", 10) + F(true, null, 16) + F(true) + F(false, "9C5700", 10, true);
        var fills = "<fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill>" +
            Fill("1F4E5F") + Fill("C6EFCE") + Fill("FFE0A8") + Fill("F4B6B0") + Fill("E8EEF1") + Fill("FFF8E1") + Fill("D6E4EA");
        const string borders = "<border><left/><right/><top/><bottom/><diagonal/></border><border><left style=\"thin\"><color rgb=\"FF999999\"/></left><right style=\"thin\"><color rgb=\"FF999999\"/></right><top style=\"thin\"><color rgb=\"FF999999\"/></top><bottom style=\"thin\"><color rgb=\"FF999999\"/></bottom><diagonal/></border>";
        string Xf(int numFmt, int fontId, int fillId, int border, string h, bool wrap = true) =>
            $"<xf numFmtId=\"{numFmt}\" fontId=\"{fontId}\" fillId=\"{fillId}\" borderId=\"{border}\" xfId=\"0\" applyNumberFormat=\"1\" applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\" applyAlignment=\"1\"><alignment horizontal=\"{h}\" vertical=\"center\" wrapText=\"{(wrap ? 1 : 0)}\"/></xf>";
        // numFmt 164 = #,##0.00 ; 165 = #,##0.000
        var xfs = new StringBuilder();
        xfs.Append(Xf(0, 0, 0, 0, "general"));            // 0 default
        xfs.Append(Xf(0, 1, 2, 1, "center"));             // 1 header
        xfs.Append(Xf(0, 0, 0, 1, "right"));              // 2 text
        xfs.Append(Xf(164, 0, 0, 1, "center"));           // 3 num
        xfs.Append(Xf(0, 2, 0, 0, "right", false));       // 4 title
        xfs.Append(Xf(0, 3, 3, 1, "center"));             // 5 green
        xfs.Append(Xf(0, 3, 4, 1, "center"));             // 6 orange
        xfs.Append(Xf(0, 3, 5, 1, "center"));             // 7 red
        xfs.Append(Xf(0, 3, 6, 1, "right"));              // 8 group
        xfs.Append(Xf(164, 3, 8, 1, "center"));           // 9 total num
        xfs.Append(Xf(1, 0, 0, 1, "center"));             // 10 int
        xfs.Append(Xf(0, 4, 0, 0, "right", false));       // 11 note
        xfs.Append(Xf(164, 0, 7, 1, "center"));           // 12 input
        xfs.Append(Xf(0, 3, 8, 1, "right"));              // 13 total text
        return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">" +
            "<numFmts count=\"1\"><numFmt numFmtId=\"164\" formatCode=\"#,##0.00\"/></numFmts>" +
            $"<fonts count=\"5\">{fonts}</fonts><fills count=\"9\">{fills}</fills><borders count=\"2\">{borders}</borders>" +
            "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>" +
            $"<cellXfs count=\"14\">{xfs}</cellXfs></styleSheet>";
    }

    static string SheetXml(Sheet sh)
    {
        var sb = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">");
        sb.Append($"<sheetViews><sheetView workbookViewId=\"0\"{(sh.Rtl ? " rightToLeft=\"1\"" : "")}>");
        if (sh.FreezeRow > 0) sb.Append($"<pane ySplit=\"{sh.FreezeRow}\" topLeftCell=\"A{sh.FreezeRow + 1}\" activePane=\"bottomLeft\" state=\"frozen\"/>");
        sb.Append("</sheetView></sheetViews><sheetFormatPr defaultRowHeight=\"18\"/>");
        if (sh.Widths.Count > 0)
        {
            sb.Append("<cols>");
            for (int i = 0; i < sh.Widths.Count; i++) sb.Append($"<col min=\"{i + 1}\" max=\"{i + 1}\" width=\"{sh.Widths[i].ToString(CultureInfo.InvariantCulture)}\" customWidth=\"1\"/>");
            sb.Append("</cols>");
        }
        sb.Append("<sheetData>");
        for (int r = 0; r < sh.Rows.Count; r++)
        {
            sb.Append($"<row r=\"{r + 1}\">");
            for (int c = 0; c < sh.Rows[r].Count; c++)
            {
                var cell = sh.Rows[r][c]; var refc = $"{Col(c)}{r + 1}"; int st = (int)cell.Style;
                if (cell.Formula != null) sb.Append($"<c r=\"{refc}\" s=\"{st}\"><f>{Esc(cell.Formula)}</f></c>");
                else if (cell.Value is null) sb.Append($"<c r=\"{refc}\" s=\"{st}\"/>");
                else if (cell.Value is string s) sb.Append($"<c r=\"{refc}\" s=\"{st}\" t=\"inlineStr\"><is><t xml:space=\"preserve\">{Esc(s)}</t></is></c>");
                else sb.Append($"<c r=\"{refc}\" s=\"{st}\"><v>{Convert.ToDouble(cell.Value, CultureInfo.InvariantCulture).ToString("R", CultureInfo.InvariantCulture)}</v></c>");
            }
            sb.Append("</row>");
        }
        sb.Append("</sheetData>");
        if (sh.Merges.Count > 0)
        {
            sb.Append($"<mergeCells count=\"{sh.Merges.Count}\">");
            foreach (var m in sh.Merges) sb.Append($"<mergeCell ref=\"{Col(m.c1)}{m.r1 + 1}:{Col(m.c2)}{m.r2 + 1}\"/>");
            sb.Append("</mergeCells>");
        }
        sb.Append("<pageSetup orientation=\"landscape\" fitToHeight=\"0\"/></worksheet>");
        return sb.ToString();
    }
}
