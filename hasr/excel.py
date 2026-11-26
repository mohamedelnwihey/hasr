"""Write a bilingual (Arabic-first) formatted BOQ workbook."""

from __future__ import annotations

from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .items import UNITS
from .extract import STATUS_GEOMETRY, STATUS_NO_QUANTITY, STATUS_OK, STATUS_UNCLASSIFIED

HEADER_FILL = PatternFill("solid", fgColor="1F4E5F")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
TITLE_FONT = Font(bold=True, size=16)
NOTE_FONT = Font(italic=True, color="9C5700")
THIN = Side(style="thin", color="999999")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)

STATUS_LABELS = {
    STATUS_OK: ("تم", "ok"),
    STATUS_GEOMETRY: ("تقديرية من المجسم", "geometry-derived estimate"),
    STATUS_NO_QUANTITY: ("بدون كمية في الملف", "no quantity in file"),
    STATUS_UNCLASSIFIED: ("غير مصنّف", "unclassified"),
}


def _style_header(ws, row, ncols):
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER
    ws.row_dimensions[row].height = 30


def _fmt_qty(value, unit_key):
    if unit_key == "count":
        return round(value)
    return round(value, 3)


def _source_label(stats):
    """Per-row origin of the quantity, compact: ملف / هندسي / مختلط.

    The full legend lives in the notes section under the table.
    """
    f_n, g_n = stats["file_n"], stats["geo_n"]
    if f_n and g_n:
        return f"مختلط ({f_n}+{g_n})"
    if g_n:
        return f"هندسي ({g_n})"
    return f"ملف ({f_n})"


def _coverage_label(stats):
    """How many classified elements of this row carry any quantity."""
    have = stats["file_n"] + stats["geo_n"]
    total = have + stats["missing_n"]
    return f"{have}/{total}"


def _print_setup(ws):
    ws.sheet_view.rightToLeft = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def write_boq(project_name, schema, unit_note, records, lines, unclassified, no_qty, geometry, out_path, source_name="", prices=None, extras=None):
    wb = Workbook()

    # --- Sheet 1: BOQ summary (Arabic-first, right-to-left) ---
    ws = wb.active
    ws.title = "جدول الكميات"
    _print_setup(ws)

    ws.cell(row=1, column=1, value="جدول حصر الكميات (BOQ)").font = TITLE_FONT
    ws.cell(row=2, column=1, value=f"المشروع / Project: {project_name or source_name}")
    ws.cell(row=3, column=1, value=f"التاريخ / Date: {date.today().isoformat()}   |   IFC: {schema}")

    header = ["م", "البند (عربي)", "Item (English)", "الوحدة", "الكمية الإجمالية",
              "المصدر", "التغطية"]
    if prices is not None:
        header += ["سعر الوحدة", "الإجمالي"]
    row = 5
    for i, h in enumerate(header, start=1):
        ws.cell(row=row, column=i, value=h)
    _style_header(ws, row, len(header))

    sorted_lines = sorted(lines.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    for idx, ((item_ar, item_en, unit_key), stats) in enumerate(sorted_lines, start=1):
        row += 1
        unit_ar, unit_en = UNITS.get(unit_key, (unit_key, unit_key))
        source = _source_label(stats)
        coverage = _coverage_label(stats)
        values = [idx, item_ar, item_en, f"{unit_ar} ({unit_en})",
                  _fmt_qty(stats["qty"], unit_key), source, coverage]
        for col, v in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col, value=v)
            cell.border = BORDER
            cell.alignment = RIGHT if col in (2, 3) else CENTER
            if col == 5 and unit_key != "count":
                cell.number_format = "#,##0.000"
            if col in (6, 7):
                cell.font = NOTE_FONT if "هندسي" in str(v) or "تقديري" in str(v) else Font()
        if prices is not None:
            price = prices.get(item_en.lower()) if item_en.lower() in prices else prices.get(item_ar)
            pc = ws.cell(row=row, column=8, value=price)
            tc = ws.cell(row=row, column=9,
                         value=f"=E{row}*H{row}" if price is not None else "")
            for c in (pc, tc):
                c.border = BORDER
                c.alignment = CENTER
                c.number_format = "#,##0.00"
    if prices is not None:
        row += 1
        ws.cell(row=row, column=8, value="الإجمالي الكلي").font = Font(bold=True)
        tot = ws.cell(row=row, column=9, value=f"=SUM(I6:I{row - 1})")
        tot.font = Font(bold=True)
        tot.number_format = "#,##0.00"
        for c in (ws.cell(row=row, column=8), tot):
            c.border = BORDER
            c.alignment = CENTER

    # --- Notes section: what did NOT make it into the totals, said out loud ---
    # Notes are merged across the table width with wrap so they never run past
    # the print bounds (RTL sheets otherwise clip them at the left edge).
    ncols = 9 if prices is not None else 7
    row += 2
    ws.cell(row=row, column=1, value="ملاحظات / Notes").font = Font(bold=True, size=12)
    row += 1

    def _note(text):
        nonlocal row
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        cell = ws.cell(row=row, column=1, value=text)
        cell.font = NOTE_FONT
        cell.alignment = Alignment(horizontal="right", vertical="top", wrap_text=True)
        # rough height: ~110 chars per visual line at these column widths
        ws.row_dimensions[row].height = max(18, 16 * (1 + len(text) // 110))
        row += 1

    _note("المصدر: ملف = كمية من ملف IFC نفسه، هندسي = تقديرية محسوبة من المجسم، مختلط = الاثنان معًا "
          "(عدد العناصر بين القوسين) / Source: file = quantity from the IFC itself, "
          "geometry = estimated from element geometry, mixed = both (element counts in brackets)")
    _note(f"عناصر غير مصنّفة مستبعدة من الإجماليات (راجع شيت التفاصيل): {len(unclassified)}"
          f" / Unclassified elements excluded from totals (see detail sheet): {len(unclassified)}")
    if no_qty:
        types = ", ".join(sorted({r.ifc_type for r in no_qty}))
        _note(f"عناصر بدون كميات في ملف IFC (لم تدخل الإجماليات): {len(no_qty)} — {types}"
              f" / Elements with no quantities in the IFC (not in totals): {len(no_qty)} — {types}")
    else:
        _note("كل العناصر المصنّفة لها كميات / All classified elements carry quantities")
    if geometry:
        _note(f"بنود بكميات تقديرية محسوبة من المجسم (لا توجد كميات في الملف): {len(geometry)} عنصر"
              f" / Lines with geometry-derived ESTIMATED quantities (no quantities in file): {len(geometry)} elements")
    if prices is not None:
        _note("البنود بدون سعر لم تدخل الإجمالي الكلي. الأسعار من ملف المستخدم وليست من البرنامج"
              " / Items with no price are not in the grand total. Prices come from the user's file, not from Hasr")
    if unit_note:
        _note(f"تنبيه الوحدات / Unit note: {unit_note}")

    widths = [6, 38, 46, 12, 17, 16, 12] + ([14, 16] if prices is not None else [])
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # --- Sheet 2: element detail (audit trail) ---
    ws2 = wb.create_sheet("تفاصيل العناصر")
    _print_setup(ws2)
    detail_header = [
        "#", "النوع", "الاسم", "الدور", "الخامة", "البند", "الوحدة", "الكمية", "الحالة", "GUID",
    ]
    for i, h in enumerate(detail_header, start=1):
        ws2.cell(row=1, column=i, value=h)
    _style_header(ws2, 1, len(detail_header))

    for idx, rec in enumerate(records, start=1):
        unit_ar = UNITS.get(rec.unit_key, (rec.unit_key, ""))[0] if rec.unit_key else ""
        item = f"{rec.item_ar} / {rec.item_en}" if rec.item_ar else ""
        status_ar, status_en = STATUS_LABELS.get(rec.status, (rec.status, rec.status))
        values = [
            idx,
            rec.ifc_type,
            rec.name,
            rec.storey,
            rec.material,
            item,
            unit_ar,
            (_fmt_qty(rec.value, rec.unit_key) if rec.value is not None else ""),
            f"{status_ar} / {status_en}",
            rec.guid,
        ]
        for col, v in enumerate(values, start=1):
            cell = ws2.cell(row=idx + 1, column=col, value=v)
            cell.border = BORDER

    for i, w in enumerate([5, 18, 26, 14, 20, 40, 10, 12, 24, 40], start=1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    _extra_sheets(wb, records, extras)
    wb.save(out_path)
    return out_path


def _table(ws, header, rows, widths):
    _print_setup(ws)
    for i, h in enumerate(header, start=1):
        ws.cell(row=1, column=i, value=h)
    _style_header(ws, 1, len(header))
    for r, vals in enumerate(rows, start=2):
        for c, v in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=c, value=v)
            cell.border = BORDER
            cell.alignment = RIGHT if isinstance(v, str) else CENTER
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _extra_sheets(wb, records, extras):
    """Per-storey pivot, door/window schedule, room schedule, assumptions."""
    # per-storey pivot: item x storey (always, no geometry needed)
    cells, storeys = {}, []
    for r in records:
        if r.status not in (STATUS_OK, STATUS_GEOMETRY) or r.value is None or not r.item_ar:
            continue
        st = r.storey or "(بدون دور)"
        if st not in storeys:
            storeys.append(st)
        key = (r.item_ar, r.item_en, r.unit_key)
        cells[(key, st)] = cells.get((key, st), 0.0) + r.value
    keys = sorted({k for k, _ in cells})
    if keys:
        rows = []
        for key in keys:
            unit_ar = UNITS.get(key[2], (key[2], key[2]))[0]
            vals = [cells.get((key, st)) for st in storeys]
            vals = [_fmt_qty(v, key[2]) if v is not None else None for v in vals]
            total = _fmt_qty(sum(v for v in (cells.get((key, st)) for st in storeys) if v), key[2])
            rows.append([key[0], key[1], unit_ar] + vals + [total])
        _table(wb.create_sheet("الكميات حسب الدور"),
               ["البند", "Item", "الوحدة"] + storeys + ["الإجمالي"], rows,
               [34, 32, 10] + [14] * len(storeys) + [14])
    if not extras:
        return
    if extras.get("openings"):
        rows = [[o["kind"].replace("Ifc", ""), o["type"], o["width"], o["height"],
                 o["storey"], o["count"]] for o in extras["openings"]]
        _table(wb.create_sheet("جدول الأبواب والشبابيك"),
               ["النوع", "الطراز", "العرض م", "الارتفاع م", "الدور", "العدد"], rows,
               [12, 40, 12, 12, 16, 10])
    if extras.get("rooms"):
        rows = [[r["name"], r["long_name"], r["storey"], round(r["area"], 2),
                 round(r["perimeter"], 2), round(r["height"], 2),
                 round(r["perimeter"] * r["height"], 2)] for r in extras["rooms"]]
        _table(wb.create_sheet("جدول الغرف"),
               ["الغرفة", "الاسم", "الدور", "المساحة م²", "المحيط م", "الارتفاع م",
                "مساحة الحوائط م² (بدون خصم فتحات)"], rows, [14, 28, 16, 12, 12, 12, 30])
    if extras.get("xray"):
        _xray_sheets(wb, extras["xray"])
    rows = [[a[0], a[1], a[2], a[3]] for a in extras["assumptions"]]
    _table(wb.create_sheet("افتراضات الكميات المشتقة"),
           ["البند", "Item", "الأساس", "Basis"], rows, [18, 18, 70, 70])


def _xray_sheets(wb, x):
    from .xray import STATUS_LABEL

    fills = {"green": "C6EFCE", "orange": "FFE0A8", "red": "F4B6B0"}

    def paint(ws, row_idx, status, col):
        ws.cell(row=row_idx, column=col).fill = PatternFill("solid", fgColor=fills[status])

    # 1. missing
    ws = wb.create_sheet("X-RAY إيه اللي ناقص")
    rows = [[STATUS_LABEL[m["status"]][0], m["where"], m["ar"], m["en"]] for m in x["missing"]]
    _table(ws, ["الحالة", "المكان", "الملاحظة", "Finding"], rows, [10, 34, 70, 70])
    for i, m in enumerate(x["missing"], start=2):
        paint(ws, i, m["status"], 1)
    # 2. purchase list
    ws = wb.create_sheet("X-RAY قائمة المشتريات")
    rows = []
    for p in x["purchase"]:
        rows.append([STATUS_LABEL[p["status"]][0], p["system_ar"], p["ar"], p["en"], p["unit"],
                     round(p["net"], 2), p["waste"], round(p["gross"], 2),
                     p["pack_ar"], p["packs"], p["rooms"]])
    _table(ws, ["الحالة", "النظام", "البند", "Item", "الوحدة", "الكمية الصافية", "الهالك %",
                "بعد الهالك", "العبوة", "عدد العبوات للشراء", "عدد الغرف"], rows,
           [10, 32, 28, 28, 8, 14, 10, 12, 20, 16, 10])
    for i, p in enumerate(x["purchase"], start=2):
        paint(ws, i, p["status"], 1)
    # 3. evidence
    ws = wb.create_sheet("X-RAY دليل الأرقام")
    rows = [[e["room"], e["scope"], e["system"], e["component_en"], e["base_label"], round(e["base"], 3),
             e["base_note"], e["formula"], round(e["net"], 3), e["unit"], e["waste"],
             e["source"], "معتمد" if e["approved"] else "غير معتمد", e["guid"]] for e in x["evidence"]]
    _table(ws, ["الغرفة", "النطاق", "النظام", "المكوّن", "أساس القياس", "القيمة", "ملاحظة القياس",
                "المعادلة", "الكمية الصافية", "الوحدة", "هالك %", "مصدر المعدل", "الاعتماد", "GUID"], rows,
           [22, 10, 28, 24, 18, 10, 34, 40, 14, 8, 8, 50, 12, 26])
    for i, e in enumerate(x["evidence"], start=2):
        paint(ws, i, "green" if e["approved"] else "orange", 13)
